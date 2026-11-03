from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager
from urllib.parse import parse_qs, urlparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
import html
import json
import os
import sys
import uuid
import hashlib
import re
import threading
from weakref import WeakValueDictionary
from execution_engine import execute_task, execute_task_mock, get_execution_engine_name
from manager_plan import build_manager_plan, validate_stages
from copy import deepcopy
from quality_review import REVIEWER_ID, RULESET_ID, evaluate_format, validate_review, inconclusive_review
from ai_safety import request_scope, check_project_permission, MAX_CALLS, MAX_CALLS_PER_REQUEST
import semantic_review
import manager_decision
import workflow_guidance
import project_budget

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
PROJECTS_DIR = DATA_DIR / "projects"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
HOST = os.environ.get("AI_COMPANY_OS_HOST", "127.0.0.1")
PORT = int(os.environ.get("AI_COMPANY_OS_PORT", "8000"))
# One process only: keep each project's read/check/write transaction together.
_PROJECT_LOCKS = WeakValueDictionary()
_PROJECT_LOCKS_GUARD = threading.Lock()


def project_mutation_lock(project_id):
    key = str(project_path(project_id))
    with _PROJECT_LOCKS_GUARD:
        lock = _PROJECT_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PROJECT_LOCKS[key] = lock
        return lock


VALID_STATUSES = {"active", "paused", "completed"}
REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_CHANGES_REQUESTED = "changes_requested"
REVIEW_NOT_REQUIRED = "not_required"
VALID_REVIEW_STATUSES = {
    REVIEW_PENDING,
    REVIEW_APPROVED,
    REVIEW_CHANGES_REQUESTED,
    REVIEW_NOT_REQUIRED,
}
PROCESSING_SCRIPT = """<script>
document.addEventListener("DOMContentLoaded", () => {
  const scrollRestoreKey = "ai-company-os:scroll-restore";
  try {
    const savedPosition = JSON.parse(sessionStorage.getItem(scrollRestoreKey) || "null");
    if (savedPosition && savedPosition.path === window.location.pathname) {
      sessionStorage.removeItem(scrollRestoreKey);
      requestAnimationFrame(() => {
        const taskRow = savedPosition.taskRowId && document.getElementById(savedPosition.taskRowId);
        if (taskRow) {
          taskRow.scrollIntoView({ block: "center" });
        } else if (Number.isFinite(savedPosition.scrollY)) {
          window.scrollTo(0, savedPosition.scrollY);
        }
      });
    }
  } catch (_) {
    // 저장소를 사용할 수 없는 브라우저에서는 복원 기능을 건너뛴다.
  }

  let activeFormRequest = false;
  const pageContent = document.querySelector("#page-content");
  const processingModal = document.querySelector("#processing-modal");
  const processingDialog = processingModal?.querySelector(".processing-dialog");
  const setModalVisible = (visible) => {
    if (!pageContent || !processingModal) return;
    processingModal.hidden = !visible;
    pageContent.inert = visible;
    if (visible) {
      pageContent.setAttribute("aria-busy", "true");
      document.body.style.overflow = "hidden";
      processingDialog?.focus();
    } else {
      pageContent.removeAttribute("aria-busy");
      document.body.style.overflow = "";
    }
  };

  document.querySelectorAll("form[data-processing-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (activeFormRequest || form.dataset.processing === "true") return;

      const button = event.submitter || form.querySelector("button[type='submit']");
      const status = form.querySelector("[data-processing-status]");
      if (!button || !status) return;

      const originalLabel = button.textContent;
      const originalDisabled = button.disabled;
      let message = "";
      activeFormRequest = true;
      form.dataset.processing = "true";
      form.setAttribute("aria-busy", "true");
      button.disabled = true;
      button.textContent = form.dataset.processingLabel || "처리 중...";
      status.hidden = true;
      status.textContent = "";

      try {
        setModalVisible(true);
        const body = new URLSearchParams();
        new FormData(form).forEach((value, key) => {
          if (typeof value === "string") body.append(key, value);
        });
        const response = await fetch(form.action, {
          method: form.method || "POST",
          body,
          credentials: "same-origin",
        });
        if (response.redirected) {
          const destination = new URL(response.url, window.location.href);
          const taskRow = form.closest("li[id^='task-']");
          try {
            sessionStorage.setItem(scrollRestoreKey, JSON.stringify({
              path: destination.pathname,
              scrollY: window.scrollY,
              taskRowId: taskRow?.id || "",
            }));
          } catch (_) {
            // 저장소 접근이 불가능해도 서버가 돌려준 화면으로 이동한다.
          }
          window.location.assign(response.url);
          return;
        }

        message = "서버 응답을 확인하지 못했습니다. 다시 시도해 주세요.";
        if (!response.ok) {
          const responseText = await response.text();
          const errorPage = new DOMParser().parseFromString(responseText, "text/html");
          const errorText = errorPage.querySelector("body p")?.textContent?.trim();
          const taskStatus = errorPage.querySelector("[data-task-status]")?.dataset.taskStatus;
          if (taskStatus) {
            const taskRow = form.closest("li");
            const statusSelect = taskRow?.querySelector("form[action='/task/update'] select[name='status']");
            if (statusSelect) statusSelect.value = taskStatus;
          }
          if (errorText) message = errorText;
        }
      } catch (_) {
        message = "연결 문제로 요청을 완료하지 못했습니다. 다시 시도해 주세요.";
      } finally {
        try {
          form.dataset.processing = "false";
          form.removeAttribute("aria-busy");
          button.disabled = originalDisabled;
          button.textContent = originalLabel;
          status.textContent = message;
          status.hidden = !message;
        } finally {
          try {
            setModalVisible(false);
          } finally {
            activeFormRequest = false;
          }
        }
      }
    });
  });
});
</script>"""

for folder in (PROJECTS_DIR, ARTIFACTS_DIR):
    folder.mkdir(parents=True, exist_ok=True)

def now():
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")

def format_time(value):
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value)
        return dt.astimezone(timezone(timedelta(hours=9))).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (ValueError, TypeError):
        return value

def project_path(project_id):
    # Only accept IDs generated by this app; prevents path traversal.
    if not project_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in project_id):
        raise ValueError("Invalid project ID")
    return PROJECTS_DIR / f"{project_id}.json"

def load_projects():
    projects = []
    for path in sorted(PROJECTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(item, dict) and item.get("id"):
                projects.append(item)
        except (OSError, json.JSONDecodeError):
            continue
    return projects

def load_project(project_id):
    return json.loads(project_path(project_id).read_text(encoding="utf-8"))

def save_project(project):
    invalidate_changed_final_report(project)
    project["updated_at"] = now()
    path = project_path(project["id"])
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


@contextmanager
def uncertain_project_lock(project_id, ledger):
    """Explicit tooling only; ordinary HTTP routes keep reserved blocked."""
    if ledger.project_path != project_path(project_id).resolve():
        raise ValueError("판단 기록의 프로젝트 원본 경로가 일치하지 않습니다.")
    lock = project_mutation_lock(project_id)
    if not lock.acquire(blocking=False):
        raise ValueError("프로젝트가 처리 중입니다.")
    try:
        yield load_project(project_id)
    finally:
        lock.release()


def record_uncertain_decision(project_id, ledger, decision, observer):
    """Caller must supply a real, current user judgment; never auto-approve."""
    with uncertain_project_lock(project_id, ledger) as project:
        ledger.record_user_decision(project, decision, observer)


@contextmanager
def uncertain_request_scope(project_id, ledger, observer):
    """One explicit new attempt, preserving both application and ledger locks."""
    with uncertain_project_lock(project_id, ledger) as project:
        with ledger.request_scope(project, observer), request_scope(save_project):
            yield project


def mark_downstream_for_review(project, task_index, reason):
    """진행 중이거나 완료된 후속 작업만 재검토 대상으로 표시한다."""
    tasks = project.get("tasks", [])
    affected = []
    for later_index, later_task in enumerate(tasks[task_index + 1:], start=task_index + 1):
        # 대기 작업은 아직 결과를 만들지 않았으므로 대기 상태를 유지한다.
        # 진행 중/완료 작업은 선행 결과가 바뀌면 기존 작업 내용에 영향이 있을 수 있다.
        if later_task.get("status", "대기") not in ("진행 중", "완료"):
            continue
        later_task["status"] = "재검토 필요"
        later_task["review_required"] = True
        later_task["review_reason"] = reason
        _reset_review_approval(
            later_task,
            task_needs_approval(project, later_index),
        )
        later_task["updated_at"] = now()
        affected.append(later_task.get("name", later_task.get("id", "이름 없는 작업")))
    if affected:
        project.setdefault("history", []).append({
            "at": now(),
            "event": "downstream_review_required",
            "details": f"후속 작업 재검토 필요: {', '.join(affected)} — {reason}",
        })
    return affected

def task_requires_review(task):
    """Treat the review flag and visible review status as the same UI state."""
    return bool(task.get("review_required")) or task.get("status") == "재검토 필요"

def task_review_status(task, has_dependents=False):
    """Read review state safely, treating legacy linked results as pending."""
    status = task.get("review_status")
    if status in VALID_REVIEW_STATUSES:
        if (
            has_dependents
            and status == REVIEW_NOT_REQUIRED
            and task.get("status") == "완료"
        ):
            return REVIEW_PENDING
        return status
    if has_dependents and task.get("status") == "완료":
        return REVIEW_PENDING
    return REVIEW_NOT_REQUIRED

def task_has_successful_result(project, task):
    """Only expose review actions for the latest stored result from a successful run."""
    task_id = task.get("id")
    if not task_id:
        return False
    relevant_events = {
        "task_execution_succeeded",
        "task_execution_failed",
        "task_result_saved",
    }
    for event in reversed(project.get("history", [])):
        if (
            event.get("event") in relevant_events
            and str(event.get("details", "")).startswith(f"{task_id}:")
        ):
            return event.get("event") == "task_execution_succeeded"
    return False

def _task_matches_input(input_name, task):
    """Legacy plan labels are resolved once into explicit task IDs."""
    task_name = task.get("name", "")
    output = task.get("output", "")
    return bool(input_name) and (
        input_name == task_name
        or input_name == output
        or input_name in task_name
        or input_name in output
        or task_name in input_name
        or output in input_name
    )

def _resolve_input_task_ids(task, tasks, task_index):
    """Return only earlier task IDs required by this task, with legacy fallback."""
    previous_tasks = tasks[:task_index]
    if "input_task_ids" in task:
        raw_ids = task.get("input_task_ids")
        if not isinstance(raw_ids, list) or not all(
            isinstance(task_id, str) and task_id.strip() for task_id in raw_ids
        ):
            raise ValueError(f"작업 '{task.get('name', '이름 없는 작업')}'의 선행 작업 ID 연결이 올바르지 않습니다.")
        task_ids = list(dict.fromkeys(task_id.strip() for task_id in raw_ids))
        previous_ids = {item.get("id") for item in previous_tasks}
        invalid_ids = [task_id for task_id in task_ids if task_id not in previous_ids]
        if invalid_ids:
            raise ValueError(
                f"작업 '{task.get('name', '이름 없는 작업')}'의 선행 작업 ID를 찾을 수 없습니다: "
                f"{', '.join(invalid_ids)}"
            )
        return task_ids

    task_ids = []
    for input_name in task.get("inputs", []):
        matched = [item for item in previous_tasks if _task_matches_input(input_name, item)]
        if not matched and task.get("name") == "최종 보고":
            matched = [item for item in previous_tasks if item.get("name") == "검토 및 수정"]
        for item in matched:
            task_id = item.get("id")
            if task_id and task_id not in task_ids:
                task_ids.append(task_id)
    return task_ids

def _task_has_dependents(tasks, task_index):
    task_id = tasks[task_index].get("id")
    if not task_id:
        return False
    for index, candidate in enumerate(tasks[task_index + 1:], start=task_index + 1):
        try:
            if task_id in _resolve_input_task_ids(candidate, tasks, index):
                return True
        except ValueError:
            # 잘못된 연결은 후속 실행 시 오류로 처리하며 여기서는 UI를 중단하지 않는다.
            continue
    return False

def task_needs_approval(project, task_index):
    tasks = project.get("tasks", [])
    return task_index == len(tasks) - 1 or _task_has_dependents(tasks, task_index)


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def final_evidence(project):
    """Only business fields, never environment settings or arbitrary extra keys."""
    fields = ("id", "name", "role", "inputs", "input_task_ids", "output", "risk",
              "result", "status", "review_required", "review_status", "reviewed_at", "reviewed_by")
    tasks = project.get("tasks", [])
    evidence = {
        "project_id": project["id"], "goal": project.get("goal", ""),
        "manager_goal": project.get("manager_goal", ""),
        "plan_status": project.get("plan", {}).get("status"),
        "stages": [{k: stage.get(k) for k in fields[:8]} for stage in project.get("plan", {}).get("stages", [])],
        "tasks": [{k: task.get(k) for k in fields} for task in tasks],
        "execution_events": [],
    }
    for task in tasks:
        event = next((e for e in reversed(project.get("history", []))
                      if e.get("event") in {"task_execution_succeeded", "task_execution_failed", "task_result_saved"}
                      and str(e.get("details", "")).startswith(f"{task.get('id')}:") ), {})
        evidence["execution_events"].append({k: event.get(k) for k in ("event", "at", "details")})
    if project.get("semantic"):
        state = project["semantic"]
        evidence["semantic"] = {k: state.get(k) for k in
                                ("target_task_id", "reviewer_task_id", "criteria", "approved_by", "approved_at", "review")}
    state = project.get("manager_decisions", {})
    if state.get("enabled"):
        evidence["manager_decisions"] = {
            "proposals": [{k: proposal[k] for k in ("id", "provider", "purpose", "status", "decision", "decided_at", "decided_by")
                           if k in proposal} for proposal in state.get("proposals", [])],
            "answers": [{k: answer[k] for k in ("task_id", "proposal_id", "answer", "at", "purpose") if k in answer}
                        for answer in state.get("answers", [])]}
    return evidence


def final_execution_context(project):
    evidence = final_evidence(project)
    final = project.get("tasks", [{}])[-1]
    evidence["final_instructions"] = {k: final.get(k) for k in ("id", "name", "role", "inputs", "input_task_ids", "output", "risk")}
    evidence["tasks"] = evidence["tasks"][:-1]
    evidence["execution_events"] = evidence["execution_events"][:-1]
    return _digest(evidence)


def validate_final_result(project):
    if project.get("semantic"):
        validate_semantic_pass(project)
    tasks = project.get("tasks", [])
    ids = [t.get("id") for t in tasks]
    if not ids or not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("최종 승인에는 고유한 업무 ID가 필요합니다.")
    if project.get("plan") and project["plan"].get("status") != "approved":
        raise ValueError("계획을 먼저 승인해 주세요.")
    for index, task in enumerate(tasks):
        if (task.get("status") != "완료" or task_requires_review(task)
                or not isinstance(task.get("result"), str) or not task["result"].strip()):
            raise ValueError("모든 업무의 유효한 완료 결과와 재검토 해제가 필요합니다.")
        _validate_task_predecessors(task, tasks, index)
    if not task_has_successful_result(project, tasks[-1]):
        raise ValueError("최종 업무의 실행 성공 기록이 필요합니다.")
    if tasks[-1].get("execution_context") != final_execution_context(project):
        raise ValueError("목표·계획·선행 결과를 확인해 최종 업무를 다시 실행해 주세요.")


def invalidate_final_report(project, reason, require_rerun=True):
    reference = project.get("final_report")
    if not isinstance(reference, dict) or reference.get("status") != "confirmed":
        return
    reference.update(status="invalidated", invalidated_at=now(), invalidated_reason=reason)
    if require_rerun and project.get("tasks"):
        final = project["tasks"][-1]
        review_status = REVIEW_CHANGES_REQUESTED if final.get("review_status") == REVIEW_CHANGES_REQUESTED else REVIEW_PENDING
        final.update(status="재검토 필요", review_required=True, review_reason=reason, review_status=review_status)


def invalidate_changed_final_report(project):
    reference = project.get("final_report", {})
    if not isinstance(reference, dict):
        return
    if reference.get("status") == "confirmed" and reference.get("fingerprint") != _digest(final_evidence(project)):
        invalidate_final_report(project, "확정 당시의 목표·계획·업무 결과 또는 승인 근거가 변경됐습니다.")


def archive_final_report(project):
    validate_final_result(project)
    if project["tasks"][-1].get("review_status") != REVIEW_APPROVED:
        raise ValueError("최종 검토 승인 후에만 보관할 수 있습니다.")
    project_path(project["id"])  # Validate ID before using it in the artifacts path.
    folder = ARTIFACTS_DIR / project["id"] / "final_reports"
    folder.mkdir(parents=True, exist_ok=True)
    versions = [int(p.stem[1:]) for p in folder.glob("v*.json") if p.stem[1:].isdigit()]
    previous_version = project.get("final_report", {}).get("version", 0)
    version = max(versions + [previous_version if type(previous_version) is int else 0]) + 1
    evidence = final_evidence(project)
    snapshot = {
        "format_version": 1, "version": version, "project_id": project["id"],
        "final_task_id": project["tasks"][-1]["id"], "confirmed_at": now(),
        "approved_by": "사용자", "review_status": REVIEW_APPROVED,
        "fingerprint": _digest(evidence), "evidence": evidence,
    }
    path = folder / f"v{version:06d}.json"
    content = json.dumps(snapshot, ensure_ascii=False, indent=2)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content)
    if json.loads(path.read_text(encoding="utf-8")) != snapshot:
        raise RuntimeError("최종 스냅샷 재독 검증에 실패했습니다. 확정하지 않았습니다.")
    project["final_report"] = {
        **{k: snapshot[k] for k in ("format_version", "version", "final_task_id", "confirmed_at", "fingerprint")},
        "status": "confirmed", "snapshot_hash": _digest(snapshot), "confirmed_by": "사용자",
    }
    project.setdefault("history", []).append({"at": now(), "event": "final_report_confirmed", "details": f"최종 보고서 확정 v{version}"})


def load_confirmed_snapshot(project, requested_version=None):
    validate_final_result(project)
    tasks = project["tasks"]
    reference = project.get("final_report", {})
    if reference.get("status") != "confirmed" or project["tasks"][-1].get("review_status") != REVIEW_APPROVED:
        raise ValueError("유효한 최종 확정이 필요합니다.")
    version = reference["version"]
    if requested_version is not None and requested_version != version:
        raise ValueError("현재 유효한 확정 버전만 다운로드할 수 있습니다.")
    if type(version) is not int or version < 1:
        raise ValueError("잘못된 보관 버전")
    project_path(project["id"])
    path = ARTIFACTS_DIR / project["id"] / "final_reports" / f"v{version:06d}.json"
    if not path.resolve().is_relative_to(ARTIFACTS_DIR.resolve()):
        raise ValueError("보관 경로가 올바르지 않습니다.")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if (reference.get("snapshot_hash") != _digest(snapshot)
            or snapshot.get("evidence") != final_evidence(project)
            or snapshot.get("fingerprint") != reference.get("fingerprint")
            or reference.get("fingerprint") != _digest(final_evidence(project))
            or snapshot.get("version") != version or snapshot.get("project_id") != project["id"]
            or snapshot.get("final_task_id") != tasks[-1]["id"]
            or reference.get("final_task_id") != tasks[-1]["id"]
            or snapshot.get("confirmed_at") != reference.get("confirmed_at")):
        raise ValueError("보관 파일과 현재 결과 불일치")
    return snapshot


def final_report_state(project):
    reference = project.get("final_report")
    tasks = project.get("tasks", [])
    if not tasks:
        return "작업 결과 현황 · 미확정 (최종 결과 없음)"
    try:
        validate_final_result(project)
        if tasks[-1].get("review_status") == REVIEW_CHANGES_REQUESTED:
            return "작업 결과 현황 · 미확정 (최종 수정 요청됨)"
        if not reference:
            if tasks[-1].get("review_status") == REVIEW_APPROVED:
                return "작업 결과 현황 · 미확정 (보관 확인 필요)"
            return "작업 결과 현황 · 미확정 (최종 검토 승인 대기)"
        if reference.get("status") != "confirmed" or tasks[-1].get("review_status") != REVIEW_APPROVED:
            raise ValueError("최종 확정 무효 · 재검토 필요")
        snapshot = load_confirmed_snapshot(project)
        version = snapshot["version"]
        return f"최종 보고서 · 확정 v{version} · {reference['confirmed_at']}"
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return "작업 결과 현황 · 미확정 (재실행·승인 또는 보관 확인 필요)"


def confirmed_markdown(snapshot):
    """Render only archived business content; no paths, settings or file writes."""
    def block(value):
        text = str(value or "")
        fence = "`" * max(3, max((len(run) for run in re.findall(r"`+", text)), default=0) + 1)
        return f"{fence}text\n{text}\n{fence}"

    evidence = snapshot["evidence"]
    lines = ["# AI Company OS 최종 확정본", "",
             f"- 프로젝트 ID: {snapshot['project_id']}", f"- 확정 버전: v{snapshot['version']}",
             f"- 확정 시각(KST): {snapshot['confirmed_at']}", f"- 최종 업무 ID: {snapshot['final_task_id']}",
             "- 사용자 승인된 보관본입니다. 사실성 검증이 완료됐음을 뜻하지 않습니다.",
             "", "## 목표", block(evidence.get("goal")), "", "## 업무별 결과"]
    if evidence.get("manager_goal") and evidence["manager_goal"] != evidence.get("goal"):
        lines.extend(["", "### 관리자 목표", block(evidence["manager_goal"])])
    for task in evidence["tasks"]:
        lines.extend(["", "### 업무", block(f"ID: {task['id']}\n이름: {task.get('name') or ''}\n담당 역할: {task.get('role') or ''}\n선행 업무: {', '.join(task.get('input_task_ids') or [])}"),
                      "", "결과:", block(task.get("result"))])
    return "\n".join(lines) + "\n"


def final_download_controls(project):
    try:
        snapshot = load_confirmed_snapshot(project)
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return "<p class='muted'>현재 유효한 최종 확정 후 Markdown 확정본을 다운로드할 수 있습니다.</p>"
    return f"<p><a class='button' href='/report/{esc(project['id'])}/download/v{snapshot['version']:06d}.md'>Markdown 확정본 다운로드 (v{snapshot['version']})</a> <a class='button' href='/report/{esc(project['id'])}/download/v{snapshot['version']:06d}.json'>JSON 확정본 다운로드 (v{snapshot['version']})</a></p>"


def _validate_task_predecessors(task, tasks, task_index):
    input_task_ids = _resolve_input_task_ids(task, tasks, task_index)
    previous_tasks_by_id = {
        item.get("id"): item for item in tasks[:task_index]
    }
    for input_task_id in input_task_ids:
        previous_task = previous_tasks_by_id[input_task_id]
        if previous_task.get("status") != "완료" or task_requires_review(previous_task):
            raise ValueError(
                f"필수 선행 업무 '{previous_task.get('name', input_task_id)}'가 "
                f"완료되지 않았습니다 (현재 상태: {previous_task.get('status', '대기')}). "
                "앞선 작업을 먼저 완료해 주세요."
            )
        previous_result = previous_task.get("result")
        if not isinstance(previous_result, str) or not previous_result.strip():
            raise ValueError(
                f"필수 선행 업무 '{previous_task.get('name', input_task_id)}'의 "
                "결과가 비어 있어 실행을 중단했습니다."
            )
        review_status = task_review_status(previous_task, has_dependents=True)
        if review_status != REVIEW_APPROVED:
            if review_status == REVIEW_CHANGES_REQUESTED:
                reason = "수정 요청이 아직 반영·재검토되지 않았습니다"
            else:
                reason = "검토 승인이 완료되지 않았습니다"
            raise ValueError(
                f"필수 선행 업무 '{previous_task.get('name', input_task_id)}'는 "
                f"{reason}. 승인 후 다시 실행해 주세요."
            )
    return input_task_ids

def _reset_review_approval(task, has_dependents):
    task["review_status"] = REVIEW_PENDING if has_dependents else REVIEW_NOT_REQUIRED
    task.pop("reviewed_at", None)
    task.pop("reviewed_by", None)

def result_revision(task):
    revision = task.get("result_revision", 0)
    if type(revision) is not int or revision < 0:
        raise ValueError("업무 결과 버전이 올바르지 않습니다.")
    return revision


def quality_input_context(project, task_index):
    evidence = final_evidence(project)
    evidence.pop("semantic", None)  # Semantic output must not become its own input fingerprint.
    evidence.pop("manager_decisions", None)  # Post-result decisions are not employee execution inputs.
    task = project["tasks"][task_index]
    evidence["tasks"] = evidence["tasks"][:task_index]
    evidence["execution_events"] = evidence["execution_events"][:task_index]
    evidence["instructions"] = {k: task.get(k) for k in ("id", "name", "role", "inputs", "input_task_ids", "output", "risk")}
    evidence["predecessor_revisions"] = [result_revision(t) for t in project["tasks"][:task_index]]
    return _digest(evidence)


def quality_binding(project, task_index, ruleset_id=RULESET_ID, reviewer_id=REVIEWER_ID):
    task = project["tasks"][task_index]
    if (task.get("status") != "완료" or task_requires_review(task)
            or not isinstance(task.get("result"), str) or not task["result"].strip()
            or not task_has_successful_result(project, task)):
        raise ValueError("완료된 성공 결과와 재검토 해제가 있어야 형식을 검사할 수 있습니다.")
    _validate_task_predecessors(task, project["tasks"], task_index)
    context = quality_input_context(project, task_index)
    if task.get("quality_execution_context", context) != context:
        raise ValueError("업무 실행 후 입력 맥락이 변경됐습니다. 다시 실행해 주세요.")
    return {
        "target_task_id": task["id"], "result_revision": result_revision(task),
        "result_hash": _digest(task["result"]), "input_context_hash": context,
        "policy_hash": _digest({"reviewer_id": reviewer_id, "ruleset_id": ruleset_id}),
    }


def attach_quality_review(project, index, ruleset_id=RULESET_ID, reviewer_id=REVIEWER_ID):
    task = project["tasks"][index]
    binding = quality_binding(project, index, ruleset_id, reviewer_id)
    outcome = "succeeded"
    try:
        review = evaluate_format(task["result"], ruleset_id, reviewer_id)
        validate_review(review)
    except Exception:
        review = inconclusive_review()
        outcome = "error"
    task["quality_review"] = {**review, "binding": binding, "outcome": outcome, "review_id": uuid.uuid4().hex, "checked_at": now()}
    project.setdefault("history", []).append({
        "at": now(), "event": "quality_review_completed" if outcome == "succeeded" else "quality_review_failed",
        "details": f"{task['id']}: 모의 형식 검사 {review['verdict']} ({task['quality_review']['review_id']})",
    })


def store_quality_review(project_id, task_id, ruleset_id, reviewer_id):
    if get_execution_engine_name() != "mock":
        raise ValueError("모의 형식 검사는 mock 모드에서만 가능합니다.")
    if ruleset_id != RULESET_ID or reviewer_id != REVIEWER_ID:
        raise ValueError("허용되지 않은 형식 검사 규칙 또는 검토자입니다.")
    project = load_project(project_id)
    matches = [i for i, t in enumerate(project.get("tasks", [])) if t.get("id") == task_id]
    if not task_id or len(matches) != 1:
        raise ValueError("검사할 정확한 업무 ID 하나를 지정해 주세요.")
    index = matches[0]
    task = project["tasks"][index]
    binding = quality_binding(project, index, ruleset_id, reviewer_id)
    previous = task.get("quality_review", {})
    if isinstance(previous, dict) and previous.get("binding") == binding:
        try:
            validate_review(previous)
            return
        except ValueError:
            pass
    attach_quality_review(project, index, ruleset_id, reviewer_id)
    save_project(project)


_QUALITY_REVISION_ONCE = object()


def validate_quality_revision(project, index, reserved=False):
    if get_execution_engine_name() != "mock":
        raise ValueError("수정 1회 및 재검토는 mock 모드에서만 가능합니다.")
    task = project["tasks"][index]
    review = task.get("quality_review")
    validate_review(review)
    if not task_needs_approval(project, index):
        raise ValueError("수정 후 사용자 승인 경계가 있는 업무만 지원합니다.")
    if (review["verdict"] != "changes_needed" or review.get("outcome") != "succeeded"
            or review.get("binding") != quality_binding(project, index)):
        raise ValueError("현재 결과에 일치하는 최신 수정 필요 판정이 있어야 합니다.")
    if (task_review_status(task, task_needs_approval(project, index)) in {REVIEW_APPROVED, REVIEW_CHANGES_REQUESTED}
            or task.get("review_feedback") or project.get("final_report", {}).get("status") == "confirmed"):
        raise ValueError("사용자 승인·수정 요청 또는 최종 확정을 먼저 확인해 주세요. 임의 수정하지 않습니다.")
    cycle = task.get("quality_revision_once")
    if reserved:
        if (not isinstance(cycle, dict) or cycle.get("phase") != "reserved" or cycle.get("attempts") != 1
                or cycle.get("origin_review_id") != review.get("review_id")):
            raise ValueError("유효한 수정 시도 예약이 없습니다.")
    elif cycle is not None:
        raise ValueError("수정 1회 시도를 이미 사용했거나 중단됐습니다. 사용자 확인이 필요합니다.")


def revise_quality_once(project_id, task_id):
    if get_execution_engine_name() != "mock":
        raise ValueError("수정 1회 및 재검토는 mock 모드에서만 가능합니다.")
    project = load_project(project_id)
    matches = [i for i, t in enumerate(project.get("tasks", [])) if t.get("id") == task_id]
    if not task_id or len(matches) != 1:
        raise ValueError("수정할 정확한 업무 ID 하나가 필요합니다.")
    index = matches[0]
    validate_quality_revision(project, index)
    task = project["tasks"][index]
    task["quality_revision_once"] = {
        "operation_id": uuid.uuid4().hex, "origin_review_id": task["quality_review"]["review_id"],
        "origin_binding": task["quality_review"]["binding"], "attempts": 1, "phase": "reserved",
        "reevaluation_attempts": 0,
        "started_at": now(), "reason": "수정 시도 예약됨. 처리 중단 시 자동 재시도하지 않습니다.",
    }
    project.setdefault("history", []).append({"at": now(), "event": "quality_revision_reserved", "details": f"{task_id}: mock 수정 1회 예약"})
    save_project(project)  # Must persist the consumed attempt before invoking an executor.
    reevaluated = False
    try:
        candidate = execute_project_task(project_id, task_id, _quality_revision=_QUALITY_REVISION_ONCE)
        reevaluated = True
        attach_quality_review(candidate, index)
        revised = candidate["tasks"][index]
        if revised["quality_review"]["outcome"] == "error":
            raise RuntimeError("재평가 오류로 이전 성공 결과를 보존했습니다.")
        cycle = revised["quality_revision_once"]
        cycle.update(phase="stopped", reevaluation_attempts=1, reevaluation_verdict=revised["quality_review"]["verdict"], stopped_at=now(), reason=f"수정 1회 완료 · {revised['quality_review']['verdict']} · 사용자 승인 또는 확인 필요")
        candidate.setdefault("history", []).append({"at": now(), "event": "quality_revision_stopped", "details": f"{task_id}: {cycle['reason']}"})
        save_project(candidate)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError):
        # Retain the reserved baseline, including when a candidate save failed.
        original = project
        cycle = original["tasks"][index]["quality_revision_once"]
        cycle.update(phase="error", stopped_at=now(), reason="수정 실행·재평가 또는 저장 오류. 이전 성공 결과를 보존했으며 남은 수정 횟수는 0회입니다.")
        cycle.update(reevaluation_attempts=int(reevaluated), reevaluation_verdict="inconclusive" if reevaluated else None)
        original.setdefault("history", []).append({"at": now(), "event": "quality_revision_failed", "details": f"{task_id}: {cycle['reason']}"})
        save_project(original)
        raise RuntimeError(cycle["reason"])


def quality_review_controls(project, task_index):
    task = project["tasks"][task_index]
    review = task.get("quality_review")
    label, feedback = "미검토", []
    if review is not None:
        try:
            validate_review(review)
            if review.get("binding") != quality_binding(project, task_index):
                raise ValueError("stale")
            label = {"pass": "형식 검사 통과", "changes_needed": "수정 필요", "inconclusive": "판정 불가"}[review["verdict"]]
            feedback = list(review["feedback"])
            feedback.append(f"검사 시각(KST): {review.get('checked_at', '')}")
            feedback += [f"{c['expected']}: {str(c['line']) + '행' if c['satisfied'] else '누락'}" for c in review["checks"]]
        except (ValueError, TypeError, KeyError):
            label = "stale · 이전 판정 (결과·입력·정책 변경 또는 확인 필요)"
    cycle = task.get("quality_revision_once")
    cycle_reason = cycle.get("reason", "중단된 예약 · 사용자 확인 필요") if isinstance(cycle, dict) else "아직 수정 시도를 사용하지 않았습니다."
    if isinstance(cycle, dict) and cycle.get("phase") == "reserved":
        cycle_reason = "처리 중 또는 중단된 수정 예약입니다. 자동 재시도하지 않으며 사용자 확인이 필요합니다."
    remaining = 0 if cycle is not None else 1
    reassessment = {"pass": "형식 검사 통과", "changes_needed": "수정 필요", "inconclusive": "판정 불가"}.get(cycle.get("reevaluation_verdict") if isinstance(cycle, dict) else None, "미실행")
    return f"""<section><p><strong>모의 형식 검사:</strong> {esc(label)}</p>
<p class='muted'>공개 규칙 required-sections-v1: 목표·결과·미확인 사항을 독립된 줄 또는 Markdown 제목으로 검사합니다. 사실성 검증·사용자 승인·자동 수정이 아닙니다.</p>
<ul>{''.join(f'<li>{esc(item)}</li>' for item in feedback)}</ul>
<form method='post' action='/quality/review' data-processing-form data-processing-label='검사 중...'>
<input type='hidden' name='id' value='{esc(project['id'])}'><input type='hidden' name='task_id' value='{esc(task.get('id', ''))}'>
<input type='hidden' name='reviewer_id' value='{REVIEWER_ID}'><input type='hidden' name='ruleset_id' value='{RULESET_ID}'>
<button type='submit'>모의 형식 검사 (mock 전용)</button><p data-processing-status hidden></p></form>
<p>수정 중단 이유: {esc(cycle_reason)} · 남은 수정 횟수: {remaining}회</p>
<p>수정 후 재평가: {esc(reassessment)} · 사용자 승인은 별도입니다.</p>
<form method='post' action='/quality/revise-once' data-processing-form data-processing-label='수정·재검토 중...'>
<input type='hidden' name='id' value='{esc(project['id'])}'><input type='hidden' name='task_id' value='{esc(task.get('id', ''))}'>
<button type='submit'>수정 1회 및 재검토 (mock 전용)</button><p data-processing-status hidden></p></form></section>"""


def task_review_controls(project, task_index):
    project_id = project["id"]
    tasks = project.get("tasks", [])
    task = tasks[task_index]
    if not task_needs_approval(project, task_index):
        return ""

    review_status = task_review_status(task, has_dependents=True)
    labels = {
        REVIEW_PENDING: "검토 승인 대기",
        REVIEW_APPROVED: "검토 승인됨",
        REVIEW_CHANGES_REQUESTED: "수정 요청됨",
        REVIEW_NOT_REQUIRED: "검토 불필요",
    }
    html_parts = [f"<p class='status'>업무 결과 검토: {esc(labels[review_status])}</p>"]
    if task_index == len(tasks) - 1:
        html_parts.append(f"<p><strong>최종 승인 대상:</strong> {esc(task.get('id', ''))} · {esc(task.get('name', ''))}</p>")
    feedback = task.get("review_feedback", "")
    if feedback:
        html_parts.append(f"<p><strong>수정 요청:</strong> {esc(feedback)}</p>")

    result = task.get("result")
    if (
        task.get("status") == "완료"
        and isinstance(result, str)
        and result.strip()
        and not task_has_successful_result(project, task)
        and review_status != REVIEW_APPROVED
    ):
        html_parts.append("<p class='muted'>실행 성공 기록이 확인되지 않아 검토할 수 없습니다. 작업을 다시 실행해 주세요.</p>")
    can_review = (
        task.get("status") == "완료"
        and isinstance(result, str)
        and bool(result.strip())
        and task_has_successful_result(project, task)
        and not task_requires_review(task)
        and review_status != REVIEW_CHANGES_REQUESTED
    )
    if can_review and review_status != REVIEW_APPROVED:
        html_parts.append(f"""<form method='post' action='/task/review' data-processing-form data-processing-label='승인 중...'>
<input type='hidden' name='id' value='{esc(project_id)}'><input type='hidden' name='task_id' value='{esc(task.get('id', ''))}'><input type='hidden' name='decision' value='approve'>
<button type='submit'>검토 승인</button><p class='muted' data-processing-status aria-live='polite' hidden></p></form>
<form method='post' action='/task/review' data-processing-form data-processing-label='요청 중...'>
<input type='hidden' name='id' value='{esc(project_id)}'><input type='hidden' name='task_id' value='{esc(task.get('id', ''))}'><input type='hidden' name='decision' value='request_changes'>
<label for='review-feedback-{esc(task.get('id', ''))}'>수정 요청 내용</label><textarea id='review-feedback-{esc(task.get('id', ''))}' name='feedback' rows='3' required placeholder='수정이 필요한 내용을 적어 주세요.'></textarea>
<button type='submit'>수정 요청</button><p class='muted' data-processing-status aria-live='polite' hidden></p></form>""")
    reviewed_at = task.get("reviewed_at")
    if review_status == REVIEW_APPROVED and reviewed_at:
        html_parts.append(f"<p class='muted'>승인 시각: {esc(format_time(reviewed_at))}</p>")
    return "".join(html_parts)

def _build_previous_results(task, tasks, task_index, input_task_ids):
    """Assemble linked result records using explicit IDs as the source of truth."""
    linked_tasks = [
        item for item in tasks[:task_index]
        if item.get("id") in input_task_ids
    ]
    previous_results = []
    for input_name in task.get("inputs", []):
        matched = [item for item in linked_tasks if _task_matches_input(input_name, item)]
        if not matched and task.get("name") == "최종 보고":
            matched = [item for item in linked_tasks if item.get("name") == "검토 및 수정"]
        for item in matched:
            previous_results.append((input_name, item))

    linked_ids = {item.get("id") for _, item in previous_results}
    for item in linked_tasks:
        if item.get("id") not in linked_ids:
            previous_results.append((item.get("output", "선행 작업 결과"), item))

    results = []
    for input_name, item in previous_results:
        result = item.get("result")
        lines = result.splitlines()
        selected_lines = []
        capture = False
        for line in lines:
            if line.strip() == "모의 결과물:":
                capture = True
                continue
            if line.strip() == "연결된 입력 자료와 실제 결과:":
                capture = False
                continue
            if line.strip() == "현재는 실행 엔진 검증 단계입니다. 실제 AI 처리는 수행하지 않았습니다.":
                capture = False
            if capture:
                selected_lines.append(line)
        selected_result = "\n".join(selected_lines).strip() or result
        results.append({
            "task_id": item.get("id"),
            "input_name": input_name,
            "task_name": item.get("name", item.get("id", "이름 없는 작업")),
            "result": selected_result,
        })
    return results

class TaskExecutionFailure(RuntimeError):
    pass


@contextmanager
def manager_decision_transaction(project_id):
    """Explicit tool handlers own their lock; do not call from locked POST routes."""
    lock = project_mutation_lock(project_id)
    if not lock.acquire(blocking=False):
        raise ValueError("프로젝트의 다른 변경을 처리 중입니다.")
    try:
        yield load_project(project_id)
    finally:
        lock.release()


def configure_mock_manager_decisions(project_id, expected_project_hash):
    """Explicit local opt-in only; never changes any real AI authorization."""
    with manager_decision_transaction(project_id) as project:
        if manager_decision.digest(project) != expected_project_hash or project.get("manager_decisions"):
            raise ValueError("프로젝트가 변경되었거나 이미 관리자 판단이 설정되었습니다.")
        if project.get("plan", {}).get("status") != "approved":
            raise ValueError("승인된 계획이 필요합니다.")
        project["manager_decisions"] = {"enabled": True, "provider": "mock", "proposals": [], "answers": []}
        project.setdefault("history", []).append({"at": now(), "event": "mock_manager_configured",
                                                   "details": "모의 관리자 판단 사용자 결정 게이트 설정"})
        save_project(project)


def request_project_budget(project_id, additional, reason, usage_plan):
    """Local owner tool only; never accepts public HTTP budget approvals."""
    with manager_decision_transaction(project_id) as project:
        proposal = project_budget.request_more(project, additional, reason, usage_plan)
        save_project(project)
        return deepcopy(proposal)


def prepare_project_budget(project_id, usage_plan):
    """Deterministic forecast supplied by the caller, not AI inference."""
    with manager_decision_transaction(project_id) as project:
        proposal = project_budget.ensure_shortage_request(project, usage_plan)
        if proposal is not None:
            save_project(project)
        return deepcopy(proposal)


def project_budget_requests(project_id):
    project = load_project(project_id)
    return [{**deepcopy(r), "expected_hash": project_budget.digest(r),
             "stale": r["body"]["binding"] != project_budget.binding(project)}
            for r in project.get("budget_requests", [])]


def decide_project_budget(project_id, request_id, expected_hash, response, *, user_confirmed=False, reason=""):
    """Trusted local caller must verify the owner's actual decision, never model_claim."""
    with manager_decision_transaction(project_id) as project:
        project_budget.decide(project, request_id, expected_hash, response, user_confirmed, reason)
        save_project(project)


def raise_project_budget_to_default(project_id, expected_project_hash, *, user_confirmed=False, reason=""):
    """Explicit policy migration; never migrate other stored small limits implicitly."""
    with manager_decision_transaction(project_id) as project:
        if (user_confirmed is not True or not reason.strip()
                or project_budget.digest(project) != expected_project_hash
                or project_budget.limit(project) >= project_budget.DEFAULT_PROJECT_CALL_BUDGET):
            raise ValueError("기존 프로젝트의 기본 예산 상향에는 최신 상태와 사용자 승인이 필요합니다.")
        before = project_budget.limit(project)
        project.setdefault("real_ai", {})["limit"] = project_budget.DEFAULT_PROJECT_CALL_BUDGET
        project.setdefault("history", []).append({"at": now(), "event": "budget_policy_user_approved",
            "before_limit": before, "after_limit": project_budget.DEFAULT_PROJECT_CALL_BUDGET,
            "details": reason, "execution_authorized": False})
        save_project(project)


def _manager_decision_input(project, task_id):
    task = next((t for t in project.get("tasks", []) if t.get("id") == task_id), None)
    if task is None or not task_has_successful_result(project, task):
        raise ValueError("성공한 직원 결과만 관리자 판단에 사용할 수 있습니다.")
    _validate_task_predecessors(task, project["tasks"], project["tasks"].index(task))
    return manager_decision.decision_input(project, task_id)


def propose_real_manager_decision_once(project_id, task_id, expected_project_hash, *, user_confirmed=False, reason=""):
    """Original one-shot path remains closed after any manager attempt."""
    return _propose_real_manager_decision(project_id, task_id, expected_project_hash,
        user_confirmed=user_confirmed, reason=reason)


def propose_real_manager_second_authorized(project_id, task_id, expected_project_hash, *,
                                           authorization_id, user_confirmed=False, reason=""):
    """Local owner only: a new, explicitly confirmed second authorization, never HTTP."""
    if not isinstance(authorization_id, str) or not re.fullmatch(r"[a-f0-9]{32}", authorization_id):
        raise ValueError("고유한 새 승인 ID가 필요합니다.")
    return _propose_real_manager_decision(project_id, task_id, expected_project_hash,
        user_confirmed=user_confirmed, reason=reason, second_authorization_id=authorization_id)


def validate_third_manager_authorization(project, task_id, authorization_id):
    state = project.get("manager_decisions", {})
    attempts = project.get("real_ai", {}).get("attempts", [])
    managers = [a for a in attempts if a.get("kind") == "manager_decision"]
    additional = state.get("additional_authorizations", [])
    history = project.get("history", [])
    if (task_id != "TASK-001" or len(attempts) != 4 or len(managers) != 2
            or any(a.get("status") != "completed" for a in attempts)
            or any(a.get("task_id") != task_id or a.get("model") != "openrouter/free" for a in managers)
            or state.get("provider") != "real_openrouter_free" or state.get("enabled") is not True
            or state.get("proposals") != [] or state.get("answers") != []
            or not state.get("authorization") or len(additional) != 1
            or additional[0].get("attempt_number") != 2 or additional[0].get("id") == authorization_id
            or sum(h.get("event") == "real_manager_stopped" for h in history) != 2
            or any(h.get("event") == "real_manager_third_authorized" or h.get("authorization_id") == authorization_id for h in history)):
        raise ValueError("새 3차 승인 사전조건 불일치 또는 이미 사용된 승인입니다.")


def propose_real_manager_third_authorized(project_id, task_id, expected_project_hash, *,
                                          authorization_id, user_confirmed=False, reason=""):
    """Local owner third approval; previous one-shot entrypoints stay closed."""
    if not isinstance(authorization_id, str) or not re.fullmatch(r"[a-f0-9]{32}", authorization_id):
        raise ValueError("고유한 새 승인 ID가 필요합니다.")
    return _propose_real_manager_decision(project_id, task_id, expected_project_hash,
        user_confirmed=user_confirmed, reason=reason, second_authorization_id=authorization_id,
        authorization_number=3)


def _propose_real_manager_decision(project_id, task_id, expected_project_hash, *,
                                   user_confirmed, reason, second_authorization_id=None, authorization_number=2):
    with manager_decision_transaction(project_id) as project:
        if (user_confirmed is not True or not isinstance(reason, str) or not reason.strip()
                or manager_decision.digest(project) != expected_project_hash):
            raise ValueError("직접 승인과 최신 프로젝트 상태가 필요합니다.")
        state = project.get("manager_decisions", {})
        attempts = project.get("real_ai", {}).get("attempts", [])
        managers = [a for a in attempts if a.get("kind") == "manager_decision"]
        if second_authorization_id is None:
            if state or managers:
                raise ValueError("기존 관리자 호출/설정은 재사용하지 않습니다.")
        elif authorization_number == 3:
            validate_third_manager_authorization(project, task_id, second_authorization_id)
        elif (task_id != "TASK-001" or len(attempts) != 3 or len(managers) != 1
                or any(a.get("status") != "completed" for a in attempts)
                or managers[0].get("task_id") != task_id or managers[0].get("model") != "openrouter/free"
                or state.get("provider") != "real_openrouter_free" or state.get("enabled") is not True
                or state.get("proposals") != [] or state.get("answers") != []
                or not state.get("authorization") or state.get("additional_authorizations")
                or not any(h.get("event") == "real_manager_stopped" for h in project.get("history", []))):
            raise ValueError("새 2차 승인 사전조건 불일치 또는 이미 사용된 승인입니다.")
        check_project_permission(project)
        if (os.getenv("AI_MODEL") != "openrouter/free"
                or os.getenv("AI_API_BASE_URL", "").rstrip("/") != "https://openrouter.ai/api/v1"
                or not os.getenv("AI_API_KEY")):
            raise ValueError("실제 관리자 무료 모델·주소·인증키 조건을 확인해 주세요.")
        if second_authorization_id is None:
            project["manager_decisions"] = {"enabled": True, "provider": "real_openrouter_free", "proposals": [], "answers": []}
        context = _manager_decision_input(project, task_id)
        authorization = {
            "task_id": task_id, "binding": context["binding"], "max_calls": 1, "approved_at": now(),
            "scope": "목표·관련 승인 계획·허용 선호·승인된 대상 결과·후속 업무 요약", "reason": reason}
        if second_authorization_id is None:
            project["manager_decisions"]["authorization"] = authorization
        else:
            authorization.update(id=second_authorization_id, attempt_number=authorization_number,
                previous_attempt_id=managers[0]["id"], goal_hash=manager_decision.digest(project.get("manager_goal") or project["goal"]),
                user_approval="응 호출 승인할게 다음 진행해줘" if authorization_number == 3 else "ai관리자 호출 승인할게")
            if authorization_number == 3:
                authorization.update(project_id=project_id, previous_attempt_ids=[a["id"] for a in managers])
            project["manager_decisions"].setdefault("additional_authorizations", []).append(authorization)
        project.setdefault("history", []).append({"at": now(),
            "event": ("real_manager_third_authorized" if authorization_number == 3 else "real_manager_second_authorized") if second_authorization_id else "real_manager_once_authorized",
            "details": reason, "task_id": task_id, "binding": context["binding"], "max_calls": 1,
            **({"authorization_id": second_authorization_id, "attempt_number": authorization_number} if second_authorization_id else {})})
        save_project(project)
        before = deepcopy(project)
        previous_attempts = deepcopy(before["real_ai"]["attempts"])

        def immutable_state(value):
            result = deepcopy(value)
            result.pop("updated_at", None)
            result["real_ai"].pop("attempts", None)
            result["real_ai"].pop("stop_reason", None)
            return result

        phase = "transport"

        def persist_single_attempt(value):
            nonlocal phase
            phase = "reservation_persist" if value["real_ai"]["attempts"][-1]["status"] == "reserved" else "ledger_persist"
            observed = load_project(project_id)
            new_attempts = value["real_ai"]["attempts"]
            old_attempts = observed["real_ai"]["attempts"]
            if (immutable_state(observed) != immutable_state(before)
                    or immutable_state(value) != immutable_state(before)
                    or len(new_attempts) != len(previous_attempts) + 1
                    or new_attempts[:-1] != previous_attempts
                    or old_attempts[:len(previous_attempts)] != previous_attempts
                    or len(old_attempts) not in (len(previous_attempts), len(previous_attempts) + 1)
                    or (len(old_attempts) > len(previous_attempts)
                        and (old_attempts[-1]["id"] != new_attempts[-1]["id"] or old_attempts[-1]["status"] != "reserved"))):
                raise ValueError("단일 예약 저장 중 프로젝트 또는 원장 경합을 감지했습니다.")
            if len(old_attempts) > len(previous_attempts):
                expected_reserved = deepcopy(new_attempts[-1])
                expected_reserved["status"] = "reserved"
                expected_reserved.pop("finished_at", None)
                if old_attempts[-1] != expected_reserved:
                    raise ValueError("기존 예약의 지문이 변경되었습니다.")
            save_project(value)
            phase = "transport"

        try:
            with request_scope(persist_single_attempt):
                decision = manager_decision.RealManagerDecisionProvider().generate(project, context)
            phase = "project_binding"
            current = load_project(project_id)
            attempts = current["real_ai"]["attempts"]
            if (len(attempts) != len(previous_attempts) + 1 or attempts[:-1] != previous_attempts
                    or attempts[-1].get("kind") != "manager_decision" or attempts[-1].get("task_id") != task_id
                    or attempts[-1].get("status") != "completed" or attempts[-1].get("model") != "openrouter/free"):
                raise ValueError("허용된 단일 관리자 호출 이외의 원장 변경을 감지했습니다.")
            comparison = deepcopy(current)
            comparison["real_ai"]["attempts"] = deepcopy(previous_attempts)
            comparison["updated_at"] = before["updated_at"]
            if comparison != before or _manager_decision_input(current, task_id)["binding"] != context["binding"]:
                raise ValueError("판단 중 승인 결과·계획 또는 프로젝트가 변경되었습니다.")
            phase = "decision_contract"
            manager_decision.parse_and_validate(json.dumps(decision, ensure_ascii=False), context)
            phase = "proposal_persist"
            proposal = {"id": uuid.uuid4().hex, "version": 1, "status": "pending_user_decision",
                "provider": "real_openrouter_free", "at": now(), "decision": decision, "attempt_id": attempts[-1]["id"]}
            if second_authorization_id:
                proposal["authorization_id"] = second_authorization_id
            current["manager_decisions"]["proposals"].append(proposal)
            current.setdefault("history", []).append({"at": now(), "event": "manager_proposal_created",
                "details": "실제 무료 AI 관리자 제안 — 사용자 결정 대기", "provider": "real_openrouter_free",
                "binding": decision["binding"], "attempt_id": attempts[-1]["id"], "proposal_id": proposal["id"]})
            save_project(current)
            return deepcopy(proposal)
        except Exception as exc:
            stage = exc.stage if isinstance(exc, manager_decision.DecisionDiagnosticError) else phase
            code = exc.code if isinstance(exc, manager_decision.DecisionDiagnosticError) else "operation_failed"
            # Fixed codes only. The transaction lock remains held during audit save.
            # Reload, never overwrite concurrent changes or reinterpret reservations.
            current = load_project(project_id)
            current.setdefault("history", []).append({"at": now(), "event": "real_manager_stopped",
                "details": "관리자 요청/응답/지문 검증 중단 — 추가 전송 없음", "task_id": task_id,
                "stage": stage, "error_code": code,
                **({"authorization_id": second_authorization_id} if second_authorization_id else {})})
            try:
                save_project(current)
            except Exception:
                raise RuntimeError("관리자 판단 및 중단 이력 저장에 실패했습니다. 재시도하지 않습니다.") from None
            raise RuntimeError("실제 관리자 판단이 완료되지 않았습니다. 저장된 예산·예약을 보존하고 재시도하지 않습니다.") from None


def propose_manager_decision(project_id, task_id, provider):
    """Generate one explicit mock proposal; never execute workers or apply plans."""
    if type(provider) is not manager_decision.MockDecisionProvider:
        raise ValueError("명시적인 모의 판단 공급자만 지원합니다. 실제 모델 연결은 없습니다.")
    with manager_decision_transaction(project_id) as project:
        state = manager_decision.require_enabled(project)
        if state.get("provider") != "mock":
            raise ValueError("실제 관리자 설정에 모의 공급자를 자동 연결하지 않습니다.")
        context = _manager_decision_input(project, task_id)
        if any(p["decision"]["binding"] == context["binding"] for p in state["proposals"]):
            raise ValueError("같은 입력에 대한 관리자 제안이 이미 있습니다.")
        if len(state["proposals"]) >= 50:
            raise ValueError("프로젝트의 모의 관리자 제안 상한에 도달했습니다.")
        snapshot = manager_decision.digest(project)
        decision = manager_decision.parse_and_validate(provider.generate(context), context)
        if manager_decision.digest(load_project(project_id)) != snapshot:
            raise ValueError("판단 중 프로젝트가 변경되었습니다. 제안을 저장하지 않습니다.")
        proposal = {"id": uuid.uuid4().hex, "version": len(state["proposals"]) + 1,
                    "status": "pending_user_decision", "provider": "mock", "at": now(), "decision": decision}
        state["proposals"].append(proposal)
        project.setdefault("history", []).append({"at": now(), "event": "manager_proposal_created",
            "details": "모의 관리자 제안 — 사용자 결정 대기", "proposal_id": proposal["id"],
            "version": proposal["version"], "binding": decision["binding"], "provider": "mock"})
        save_project(project)
        return deepcopy(proposal)


def _manager_review_input(project, task_id):
    task = next((t for t in project.get("tasks", []) if t.get("id") == task_id), None)
    if task is None or not task_has_successful_result(project, task):
        raise ValueError("성공한 완료 결과만 검토할 수 있습니다.")
    _validate_task_predecessors(task, project["tasks"], project["tasks"].index(task))
    return manager_decision.employee_review_input(project, task_id)


def _proposal_context(project, proposal):
    purpose = proposal.get("purpose")
    binding = proposal["decision"]["binding"]
    if purpose == manager_decision.REVIEW_PURPOSE and binding.get("purpose") == purpose:
        return _manager_review_input(project, binding["task_id"])
    if purpose is not None or binding.get("purpose") is not None:
        raise ValueError("관리자 제안 목적이 일치하지 않습니다.")
    return _manager_decision_input(project, binding["task_id"])


def propose_employee_result_review_offline(project_id, task_id, provider):
    """Mock-only review preparation; no real provider, approval or employee execution."""
    if type(provider) is not manager_decision.MockDecisionProvider:
        raise ValueError("오프라인 모의 검토 공급자만 지원합니다.")
    with manager_decision_transaction(project_id) as project:
        state = manager_decision.require_enabled(project)
        if state.get("provider") != "mock":
            raise ValueError("실사용 관리자 설정에 모의 제안을 연결하지 않습니다.")
        context = _manager_review_input(project, task_id)
        if (len(state["proposals"]) >= 50 or any(p["decision"]["binding"] == context["binding"] for p in state["proposals"])):
            raise ValueError("동일 검토 제안이 있거나 제안 한도에 도달했습니다.")
        snapshot = manager_decision.digest(project)
        raw = provider.generate(context)
        decision = manager_decision.validate_provider_response(
            {"choices": [{"finish_reason": "stop", "message": {"content": raw}}]}, context)
        if manager_decision.digest(load_project(project_id)) != snapshot:
            raise ValueError("검토 중 프로젝트가 변경되었습니다.")
        proposal = {"id": uuid.uuid4().hex, "version": len(state["proposals"]) + 1,
            "purpose": manager_decision.REVIEW_PURPOSE, "provider": "mock", "at": now(),
            "status": "pending_user_decision", "decision": decision}
        state["proposals"].append(proposal)
        project.setdefault("history", []).append({"at": now(), "event": "manager_proposal_created",
            "purpose": manager_decision.REVIEW_PURPOSE, "provider": "mock", "proposal_id": proposal["id"],
            "binding": decision["binding"], "details": "미승인 직원 결과 모의 검토 — 사용자 결정 대기"})
        save_project(project)
        return deepcopy(proposal)


def manager_decision_view(project_id):
    """Read-only tool interface for questions, proposals and optimistic tokens."""
    project = load_project(project_id)
    state = manager_decision.require_enabled(project)
    result = []
    for proposal in state["proposals"]:
        item = deepcopy(proposal)
        try:
            context = _proposal_context(project, proposal)
            manager_decision.parse_and_validate(json.dumps(item["decision"], ensure_ascii=False), context)
            item["stale"] = False
        except ValueError:
            item["stale"] = True
        item["expected_hash"] = manager_decision.digest(proposal)
        result.append(item)
    return result


def respond_manager_decision(project_id, proposal_id, expected_hash, response, answer="", *, expected_project_hash=None, user_authorization=None):
    """Caller supplies the actual user's decision; non-proceed acceptance never applies edits."""
    if user_authorization is not None:
        manager_decision.text(user_authorization, 4000)
    with manager_decision_transaction(project_id) as project:
        if expected_project_hash is not None and manager_decision.digest(project) != expected_project_hash:
            raise ValueError("사용자 결정 대상 프로젝트가 변경되었습니다.")
        state = manager_decision.require_enabled(project)
        proposal = next((p for p in state["proposals"] if p["id"] == proposal_id), None)
        if (proposal is None or proposal["status"] != "pending_user_decision"
                or manager_decision.digest(proposal) != expected_hash):
            raise ValueError("제안이 없거나 이미 결정되었거나 변경되었습니다.")
        decision = proposal["decision"]
        context = _proposal_context(project, proposal)
        manager_decision.parse_and_validate(json.dumps(decision, ensure_ascii=False), context)
        if response == "answer":
            if decision["action"] != "ask_user":
                raise ValueError("사용자 질문 제안에만 답변할 수 있습니다.")
            manager_decision.text(answer, 2000)
            state["answers"].append({"task_id": decision["binding"]["task_id"], "proposal_id": proposal_id,
                                      "answer": answer, "at": now(),
                                      **({"purpose": manager_decision.REVIEW_PURPOSE} if proposal.get("purpose") == manager_decision.REVIEW_PURPOSE else {})})
            proposal["status"] = "answered"
        elif response in {"approve", "reject"}:
            if answer:
                raise ValueError("답변은 별도 answer 결정으로 기록해 주세요.")
            proposal["status"] = ("rejected" if response == "reject" else
                                   "approved" if decision["action"] == "proceed" and proposal.get("purpose") != manager_decision.REVIEW_PURPOSE else "accepted_for_review")
        else:
            raise ValueError("사용자 결정은 approve/reject/answer 중 하나여야 합니다.")
        proposal["decided_at"] = now()
        proposal["decided_by"] = "사용자"
        project.setdefault("history", []).append({"at": now(),
            "event": "manager_question_answered" if response == "answer" else "manager_user_decision",
            "proposal_id": proposal_id, "response": response, "binding": decision["binding"],
            **({"purpose": manager_decision.REVIEW_PURPOSE} if proposal.get("purpose") == manager_decision.REVIEW_PURPOSE else {}),
            **({"user_authorization": user_authorization, "answer_hash": manager_decision.digest(answer)}
               if user_authorization is not None else {}),
            "details": "사용자 판단 기록 — 추가 실행·계획 변경·결과 수정 자동 적용 없음"})
        if expected_project_hash is not None and manager_decision.digest(load_project(project_id)) != expected_project_hash:
            raise ValueError("사용자 결정 저장 중 프로젝트 경합을 감지했습니다.")
        save_project(project)


def review_task_result(project_id, task_id, decision, feedback="", *, expected_project_hash=None, approval_audit=None):
    """Shared route/owner review logic; caller must hold the project mutation lock."""
    project = load_project(project_id)
    if expected_project_hash is not None and manager_decision.digest(project) != expected_project_hash:
        raise ValueError("승인할 프로젝트 지문이 변경되었습니다.")
    tasks = project.get("tasks", [])
    task = next((item for item in tasks if item.get("id") == task_id), None)
    if not task:
        raise ValueError("검토할 업무를 찾을 수 없습니다.")

    task_index = tasks.index(task)
    if not task_needs_approval(project, task_index):
        raise ValueError("후속 업무가 연결되지 않은 결과는 이 승인 단계가 필요하지 않습니다.")
    if task.get("status") != "완료":
        raise ValueError("완료된 업무 결과만 검토할 수 있습니다.")
    result = task.get("result")
    if not isinstance(result, str) or not result.strip():
        raise ValueError("결과가 비어 있어 검토할 수 없습니다.")
    if not task_has_successful_result(project, task):
        raise ValueError("실행에 성공해 저장된 결과만 검토할 수 있습니다. 작업을 다시 실행해 주세요.")
    if task_requires_review(task):
        raise ValueError("선행 결과가 바뀌어 업무를 다시 실행해야 검토할 수 있습니다.")
    _validate_task_predecessors(task, tasks, task_index)

    review_status = task_review_status(task, has_dependents=True)
    state = project.get("semantic", {})
    if task_id == state.get("target_task_id") and decision == "request_changes":
        raise ValueError("의미 검토의 별도 수정 요청 승인 경로를 사용해 주세요.")
    if task_id == state.get("reviewer_task_id") and decision == "approve":
        validate_semantic_pass(project)
    if task_index == len(tasks) - 1:
        validate_final_result(project)
    if decision == "approve":
        if review_status == REVIEW_APPROVED:
            raise ValueError("이미 승인된 업무 결과입니다.")
        if review_status == REVIEW_CHANGES_REQUESTED:
            raise ValueError("수정 요청 내용을 반영해 다시 실행한 후 검토해 주세요.")
        task["review_status"] = REVIEW_APPROVED
        task["reviewed_by"] = "사용자"
        task["reviewed_at"] = now()
        task.pop("review_feedback", None)
        event = "task_review_approved"
        details = f"{task_id}: 업무 결과 검토 승인"
    elif decision == "request_changes":
        feedback = feedback.strip()
        if not feedback:
            raise ValueError("수정 요청 내용을 입력해 주세요.")
        task["review_status"] = REVIEW_CHANGES_REQUESTED
        task["review_feedback"] = feedback
        task["reviewed_by"] = "사용자"
        task["reviewed_at"] = now()
        mark_downstream_for_review(
            project,
            task_index,
            f"선행 업무 {task.get('name', task_id)}에 수정 요청이 등록됨",
        )
        event = "task_review_changes_requested"
        details = f"{task_id}: 업무 결과 수정 요청"
    else:
        raise ValueError("검토 결정 값이 올바르지 않습니다.")

    task["updated_at"] = now()
    project.setdefault("history", []).append({
        "at": now(),
        "event": event,
        "details": details,
    })
    if decision == "approve" and task_index == len(tasks) - 1:
        archive_final_report(project)
    if approval_audit is not None:
        project.setdefault("history", []).append(deepcopy(approval_audit))
    if expected_project_hash is not None and manager_decision.digest(load_project(project_id)) != expected_project_hash:
        raise ValueError("결과 승인 중 프로젝트 경합을 감지했습니다.")
    save_project(project)


def execute_project_task(project_id, task_id, executor=None, *, _quality_revision=None, _semantic=None, _persist=None):
    """Execute and save one task; caller must hold the project mutation lock."""
    persist_project = _persist or save_project
    project = load_project(project_id)

    tasks = project.get("tasks", [])
    task = next(
        (t for t in tasks if t.get("id") == task_id),
        None
    )

    if not task:
        raise ValueError("실행할 작업을 찾을 수 없습니다.")

    task_index = tasks.index(task)
    semantic = project.get("semantic", {})
    if semantic and task_id == semantic.get("reviewer_task_id") and _semantic is not _SEMANTIC_EXECUTION:
        raise ValueError("이 업무는 별도 의미 검토 시작·재검토로 실행해 주세요.")
    if semantic and task_index > next(i for i, t in enumerate(tasks) if t["id"] == semantic["reviewer_task_id"]):
        validate_semantic_pass(project)
    cycle = semantic.get("revision") if task_id == semantic.get("target_task_id") else None
    if cycle is not None:
        if cycle.get("phase") != "approved" or task.get("review_status") != REVIEW_CHANGES_REQUESTED:
            raise ValueError("의미 수정 1회 권한을 사용했거나 사용자 승인이 필요합니다.")
        if semantic.get("review", {}).get("binding") != semantic_binding(project):
            raise ValueError("수정 승인 후 대상 지문이 변경됐습니다.")
        check_project_permission(project)
    quality_revision = _quality_revision is _QUALITY_REVISION_ONCE
    if quality_revision:
        validate_quality_revision(project, task_index, reserved=True)
        executor = execute_task_mock
    has_dependents = task_needs_approval(project, task_index)
    current_review_status = task_review_status(
        task,
        has_dependents=has_dependents,
    )
    if (
        task.get("status") == "완료"
        and not task.get("review_required")
        and current_review_status != REVIEW_CHANGES_REQUESTED
        and task_has_successful_result(project, task)
        and not quality_revision
    ):
        raise ValueError(
            "이미 완료된 작업입니다. 재실행하려면 먼저 '진행 중'으로 변경해 주세요."
        )

    input_task_ids = _validate_task_predecessors(task, tasks, task_index)
    if project.get("manager_decisions", {}).get("enabled") is True:
        for predecessor_id in input_task_ids:
            _manager_decision_input(project, predecessor_id)
    manager_guidance = manager_decision.require_proceed(project, task_id, input_task_ids)

    next_revision = result_revision(task) + 1
    execution_input_context = quality_input_context(project, task_index)

    unfinished = [
        t for t in tasks[:task_index]
        if t.get("status") != "완료" or t.get("review_required")
    ]

    if unfinished:
        names = ", ".join(
            t.get("name", t.get("id", "이름 없는 작업"))
            for t in unfinished
        )
        raise ValueError(
            f"앞선 작업을 먼저 완료해 주세요: {names}"
        )

    if cycle is not None:
        cycle.update(phase="reserved", started_at=now())
        persist_project(project)

    invalidate_final_report(project, "업무 재실행", task_index != len(tasks) - 1)
    old_status = task.get("status", "대기")
    old_result = task.get("result", "")
    review_feedback = (
        task.get("review_feedback", "")
        if current_review_status == REVIEW_CHANGES_REQUESTED
        else ""
    )
    _reset_review_approval(task, has_dependents)
    task["status"] = "진행 중"
    task["updated_at"] = now()

    previous_results = _build_previous_results(
        task, tasks, task_index, input_task_ids
    )
    previous_results.extend(manager_guidance)
    previous_results.extend(manager_decision.user_answer_inputs(project, input_task_ids))
    if review_feedback:
        previous_results.append({
            "task_id": task_id,
            "input_name": "검토 수정 요청",
            "task_name": "사용자 검토자",
            "result": review_feedback,
        })
    if quality_revision:
        previous_results.append({
            "task_id": task_id, "input_name": "자동 품질 검토 수정 의견", "task_name": REVIEWER_ID,
            "result": "\n".join(task["quality_review"]["feedback"]),
        })

    try:
        result = (executor or execute_task)(
            project,
            task,
            previous_results=previous_results
        )
        if not isinstance(result, str) or not result.strip():
            raise RuntimeError(
                "실행기가 빈 작업 결과를 반환했습니다. 결과를 저장하지 않았습니다."
            )
        task["result"] = result
        task["result_revision"] = next_revision
        if cycle is not None:
            cycle.update(phase="executed", completed_at=now())
        task["quality_execution_context"] = execution_input_context
        if task_index == len(tasks) - 1:
            task["execution_context"] = final_execution_context(project)
        task["status"] = "완료"
        task["review_required"] = False
        task.pop("review_reason", None)
        task["review_status"] = REVIEW_PENDING if has_dependents else REVIEW_NOT_REQUIRED
        task.pop("review_feedback", None)
        task.pop("reviewed_at", None)
        task.pop("reviewed_by", None)
        task["updated_at"] = now()

        if old_result != result:
            mark_downstream_for_review(
                project,
                task_index,
                f"선행 업무 {task.get('name', task_id)} 결과가 다시 생성됨",
            )

        project.setdefault("history", []).append({
            "at": now(),
            "event": "task_execution_succeeded",
            "details": f"{task_id}: 작업 실행 성공 (실행 엔진: {get_execution_engine_name()})"
        })
    except Exception as exc:
        task["status"] = "실행 실패"
        task["review_status"] = (
            REVIEW_CHANGES_REQUESTED
            if has_dependents and review_feedback
            else REVIEW_PENDING if has_dependents else REVIEW_NOT_REQUIRED
        )
        task["updated_at"] = now()
        project.setdefault("history", []).append({
            "at": now(),
            "event": "task_execution_failed",
            "details": f"{task_id}: 실행 실패 — {exc}"
        })
        if old_status != task["status"]:
            project.setdefault("history", []).append({
                "at": now(),
                "event": "task_status_changed",
                "details": f"{task_id}: {old_status} -> {task['status']}"
            })
        if not quality_revision:
            persist_project(project)
        raise TaskExecutionFailure(str(exc)) from exc

    if old_status != task["status"]:
        project.setdefault("history", []).append({
            "at": now(),
            "event": "task_status_changed",
            "details": (
                f"{task_id}: {old_status} -> {task['status']}"
            )
        })

    project["updated_at"] = now()
    if quality_revision:
        return project
    persist_project(project)


_SEMANTIC_EXECUTION = object()


def edit_pending_plan(project_id, stages, feedback, expected_plan_hash):
    """Locally edit an unapproved draft; never approve or request an AI plan."""
    with project_mutation_lock(project_id):
        project = load_project(project_id)
        plan = project.get("plan", {})
        if (plan.get("status") not in {"pending_approval", "changes_requested"}
                or project.get("tasks") or plan.get("approved_at")):
            raise ValueError("업무가 없는 승인 전 계획만 편집할 수 있습니다.")
        if _digest(plan) != expected_plan_hash:
            raise ValueError("계획이 변경되었습니다. 최신 초안을 확인해 주세요.")
        goal = project.get("manager_goal") or project.get("goal")
        if plan.get("goal") != goal:
            raise ValueError("계획 목표와 프로젝트 목표가 일치하지 않습니다.")
        if not isinstance(feedback, str) or not feedback.strip():
            raise ValueError("계획 수정 사유가 필요합니다.")
        normalized = validate_stages(stages)
        project.setdefault("plan_revisions", []).append({
            "at": now(), "source": "local_draft_edit",
            "plan_hash": _digest(plan), "plan": deepcopy(plan),
            "feedback": feedback.strip(),
        })
        plan["stages"] = normalized
        plan["status"] = "pending_approval"
        plan["feedback"] = feedback.strip()
        plan["edited_at"] = now()
        plan["edit_source"] = "local_draft_edit"
        project.setdefault("history", []).append({
            "at": now(), "event": "plan_draft_edited",
            "details": "승인 전 계획 초안 편집 — 원본 보존, 사용자 승인 대기",
        })
        save_project(project)


def semantic_tasks(project):
    state = project.get("semantic", {})
    tasks = project.get("tasks", [])
    ids = [t.get("id") for t in tasks]
    if len(set(ids)) != len(ids):
        raise ValueError("고유한 업무 ID가 필요합니다.")
    try:
        target = ids.index(state["target_task_id"])
        reviewer = ids.index(state["reviewer_task_id"])
    except (KeyError, ValueError):
        raise ValueError("의미 검토 대상·담당 업무를 확인해 주세요.") from None
    if reviewer != target + 1 or reviewer == len(tasks) - 1 or tasks[reviewer].get("role") != "품질 검토 담당":
        raise ValueError("대상 바로 다음의 품질 검토 담당 업무와 별도 최종 업무가 필요합니다.")
    if tasks[target]["id"] not in _resolve_input_task_ids(tasks[reviewer], tasks, reviewer):
        raise ValueError("품질 업무에 대상 업무의 선행 연결이 필요합니다.")
    return target, reviewer


def semantic_binding(project):
    target, reviewer = semantic_tasks(project)
    binding = {**quality_binding(project, target, "semantic-v1", project["tasks"][reviewer]["id"]),
               "criteria_hash": _digest(project["semantic"]["criteria"]),
               "reviewer_hash": _digest({k: project["tasks"][reviewer].get(k) for k in
                                         ("id", "name", "role", "inputs", "input_task_ids", "output", "risk")})}
    answers = manager_decision.user_answer_inputs(project, [project["tasks"][target]["id"]])
    if answers:
        binding["user_answers_hash"] = manager_decision.digest(answers)
    return binding


def configure_semantic(project_id, target_id, reviewer_id, criteria_text):
    project = load_project(project_id)
    if project.get("semantic") or project.get("plan", {}).get("status") != "approved":
        raise ValueError("승인된 계획에 한 번만 의미 검토 기준을 승인할 수 있습니다.")
    criteria = [line.strip() for line in criteria_text.splitlines() if line.strip()]
    if not 1 <= len(criteria) <= 8 or len(set(criteria)) != len(criteria) or any(len(c) > 500 for c in criteria):
        raise ValueError("성공 기준을 중복 없이 1~8줄, 줄마다 500자 이내로 입력해 주세요.")
    project["semantic"] = {"target_task_id": target_id, "reviewer_task_id": reviewer_id,
                           "criteria": criteria, "approved_by": "사용자", "approved_at": now(), "reviews": []}
    _, reviewer = semantic_tasks(project)
    if any(t.get("status", "대기") != "대기" or t.get("result") for t in project["tasks"][reviewer:]):
        raise ValueError("품질·후속 업무 실행 전에 기준을 승인해 주세요.")
    invalidate_final_report(project, "의미 성공 기준 승인")
    project.setdefault("history", []).append({"at": now(), "event": "semantic_criteria_approved",
                                               "details": f"{target_id}: 사용자 성공 기준 승인"})
    save_project(project)


def validate_semantic_pass(project):
    state = project["semantic"]
    review = state.get("review")
    semantic_review.validate(review, semantic_binding(project), state["criteria"])
    if review["verdict"] != "pass":
        raise ValueError("최신 의미 검토가 통과하지 않았습니다. 자동 진행을 중단합니다.")
    _, reviewer = semantic_tasks(project)
    task = project["tasks"][reviewer]
    if task.get("result") != json.dumps(review, ensure_ascii=False, indent=2) or not task_has_successful_result(project, task):
        raise ValueError("의미 검토 업무의 성공 결과가 일치하지 않습니다.")


def run_semantic_review(project_id):
    project = load_project(project_id)
    check_project_permission(project)
    target, reviewer = semantic_tasks(project)
    state = project["semantic"]
    target_task = project["tasks"][target]
    if target_task.get("review_status") != REVIEW_APPROVED:
        raise ValueError("대상 결과를 사용자가 승인·재승인한 뒤 의미 검토할 수 있습니다.")
    binding = semantic_binding(project)
    reviews = state["reviews"]
    if reviews:
        cycle = state.get("revision", {})
        if (len(reviews) != 1 or reviews[0].get("phase") != "completed"
                or cycle.get("phase") != "executed" or cycle.get("reevaluation_reserved")
                or binding["result_revision"] != cycle.get("origin_revision", -2) + 1):
            raise ValueError("초기 검토 또는 사용자 수정 후 재검토 1회만 허용합니다. 자동 재시도하지 않습니다.")
    # Validate all predecessor approvals before consuming the single review attempt.
    input_ids = _validate_task_predecessors(project["tasks"][reviewer], project["tasks"], reviewer)
    manager_decision.require_proceed(project, project["tasks"][reviewer]["id"], input_ids)
    if reviews:
        state["revision"]["reevaluation_reserved"] = True
    reviews.append({"phase": "reserved", "binding": binding, "reserved_at": now()})
    save_project(project)

    def executor(current, task, previous_results=None):
        current_state = current["semantic"]
        if semantic_binding(current) != binding:
            raise ValueError("의미 검토 입력 지문이 변경됐습니다.")
        review = semantic_review.evaluate(current, task, current["tasks"][target], binding,
                                          current_state["criteria"], previous_results)
        current_state["review"] = review
        current_state["reviews"][-1].update(phase="completed", completed_at=now())
        return json.dumps(review, ensure_ascii=False, indent=2)

    execute_project_task(project_id, project["tasks"][reviewer]["id"], executor=executor,
                         _semantic=_SEMANTIC_EXECUTION)


def decide_semantic_revision(project_id, decision, binding_hash):
    project = load_project(project_id)
    state = project.get("semantic", {})
    target, _ = semantic_tasks(project)
    task = project["tasks"][target]
    review = state.get("review")
    binding = semantic_binding(project)
    semantic_review.validate(review, binding, state["criteria"])
    if (review["verdict"] != "changes_needed" or binding_hash != _digest(binding)
            or task.get("review_status") != REVIEW_APPROVED or state.get("revision") is not None):
        raise ValueError("최신 수정 필요 판정과 기존 승인, 미사용 수정 권한이 필요합니다.")
    if decision not in {"approve", "reject"}:
        raise ValueError("수정 요청 승인 또는 거절을 선택해 주세요.")
    if decision == "approve":
        _, attempts, limit = check_project_permission(project)
        if limit - len(attempts) < 2:
            raise ValueError("수정·재검토에 필요한 최소 2회 예산이 부족합니다.")
    state["revision"] = {"phase": "approved" if decision == "approve" else "rejected",
                         "origin_revision": result_revision(task), "binding_hash": binding_hash,
                         "previous_approval": {k: task.get(k) for k in ("review_status", "reviewed_at", "reviewed_by")},
                         "decided_by": "사용자", "decided_at": now(), "previous_result": task["result"]}
    if decision == "approve":
        task.update(review_status=REVIEW_CHANGES_REQUESTED, reviewed_by="사용자", reviewed_at=now(),
                    review_feedback="\n".join(f"{c['criterion']}: {c['risk']} / {c['suggestion']}" for c in review["checks"]))
        invalidate_final_report(project, "사용자 의미 수정 요청 승인")
        mark_downstream_for_review(project, target, "사용자가 의미 검토 수정 요청을 승인함")
    project.setdefault("history", []).append({"at": now(), "event": "semantic_revision_decided",
                                               "details": f"{task['id']}: 사용자 수정 요청 {decision}"})
    save_project(project)


def semantic_controls(project):
    state = project.get("semantic")
    pid = esc(project["id"])
    if not state:
        target, reviewer, draft = workflow_guidance.criteria_draft(project)
        return f"""<section><h3>의미 검토 성공 기준 승인</h3>
<p>품질 업무 실행 전에 대상 바로 다음의 품질 검토 담당 업무를 지정하세요. 실제 전송 동의는 별도이며 이 승인은 AI 요청을 활성화하지 않습니다.</p>
<form method='post' action='/semantic/configure'><input type='hidden' name='id' value='{pid}'>
<label>대상 업무 ID<input name='target_task_id' value='{esc(target)}' required></label><label>품질 업무 ID<input name='reviewer_task_id' value='{esc(reviewer)}' required></label>
<p>아래는 미승인 초안입니다. 답변에 적은 검토 방향도 기준 승인과 다릅니다. 내용을 검토한 뒤 직접 승인하세요. 외부 출처를 확인할 수 없으면 미확인으로 구분해야 합니다.</p>
<label>사용자 성공 기준 (한 줄에 하나)<textarea name='criteria' required>{esc(draft)}</textarea></label>
<button>성공 기준 승인</button></form></section>"""
    review = state.get("review", {})
    label, binding_hash = "미검토", ""
    try:
        binding = semantic_binding(project)
        binding_hash = _digest(binding)
        semantic_review.validate(review, binding, state["criteria"])
        label = review["verdict"]
    except (ValueError, TypeError, KeyError):
        label = "미검토 또는 stale · 판정 불가"
    remaining = project_budget.summary(project)["remaining"]
    target = next((t for t in project.get("tasks", []) if t.get("id") == state["target_task_id"]), {})
    return f"""<section><h3>의미 검토 (모델 주장이며 독립 확인 아님)</h3>
<p>대상 {esc(state['target_task_id'])} · 검토 담당 {esc(state['reviewer_task_id'])} · 기존 승인 {esc(target.get('review_status'))} {esc(target.get('reviewed_at', ''))}</p>
<p>성공 기준: {esc(' / '.join(state['criteria']))} · 판정: {esc(label)} · 남은 API 예산 {remaining}회</p>
<pre>{esc(json.dumps(review, ensure_ascii=False, indent=2))}</pre>
<p>검토 시도 {len(state.get('reviews', []))}/2회 · 최근 상태 {esc(state.get('reviews', [{}])[-1].get('phase', '미실행') if state.get('reviews') else '미실행')}. 예약이 남으면 중단 여부가 불명확하므로 자동 재전송하지 않습니다.</p>
<p>수정 상태: {esc(state.get('revision', {}).get('phase', '미사용'))}. 수정·재검토 각각 최대 1회이며 자동 반복하지 않습니다. 사용자 재승인·최종 승인은 별도입니다.</p>
<form method='post' action='/semantic/review' data-processing-form data-processing-label='의미 검토 중...'><input type='hidden' name='id' value='{pid}'><button type='submit'>의미 검토 시작·재검토 (실제 경로)</button><p data-processing-status hidden></p></form>
<form method='post' action='/semantic/revision-decision'><input type='hidden' name='id' value='{pid}'>
<input type='hidden' name='binding_hash' value='{binding_hash}'>
<button name='decision' value='approve'>수정 요청 승인 (이후 대상 업무 실행, API 1회·재검토 1회)</button>
<button name='decision' value='reject'>수정 요청 거절</button></form></section>"""


MAX_WORKFLOW_TASKS = 5


def run_mock_workflow(project_id):
    return _run_workflow(project_id)


def run_real_workflow(project_id):
    check_project_permission(load_project(project_id))
    return _run_workflow(project_id, real=True)


def _run_workflow(project_id, real=False):
    """Bounded synchronous run. Caller holds the project lock for the whole run."""
    if not real and get_execution_engine_name() != "mock":
        raise ValueError("자동 진행은 mock 모드에서만 가능합니다. 외부 AI 요청은 보내지 않았습니다.")
    executed = []
    reason = "실행 횟수 상한에 도달했습니다. 확인 후 다시 재개해 주세요."
    for _ in range(MAX_CALLS_PER_REQUEST if real else MAX_WORKFLOW_TASKS):
        project = load_project(project_id)
        if project.get("plan", {}).get("status") != "approved":
            reason = "작업 계획을 먼저 승인해 주세요."
            break
        tasks = project.get("tasks", [])
        candidate = None
        for index, task in enumerate(tasks):
            review = task_review_status(task, task_needs_approval(project, index))
            if review == REVIEW_CHANGES_REQUESTED:
                reason = "수정 요청이 있습니다. 개별 작업을 수정·재실행하고 검토해 주세요."
                break
            if task.get("status") == "실행 실패":
                reason = "실행 실패 업무가 있습니다. 개별 작업을 확인하고 재시도해 주세요."
                break
            if task.get("status") == "완료" and not task_requires_review(task):
                if not isinstance(task.get("result"), str) or not task["result"].strip():
                    reason = "완료 업무의 결과가 비어 있습니다. 개별 작업을 확인해 주세요."
                    break
                if review == REVIEW_PENDING:
                    reason = ("최종 검토 승인 대기 중입니다." if index == len(tasks) - 1
                              else "검토 승인 대기 중입니다. 승인 후 자동 진행을 재개해 주세요.")
                    break
                continue
            if task.get("status", "대기") not in {"대기", "재검토 필요"}:
                reason = "진행 중이거나 상태를 확인해야 하는 업무가 있습니다."
                break
            candidate = task
            break
        else:
            reason = "실행할 업무가 없습니다. 저장된 결과를 확인해 주세요."
        if candidate is None:
            break
        task_id = candidate.get("id")
        if not task_id or task_id in executed:
            reason = "업무 ID가 없거나 중복되어 자동 진행을 중단했습니다."
            break
        try:
            # Explicit mock executor makes this route incapable of selecting a real engine.
            execute_project_task(project_id, task_id, executor=execute_task if real else execute_task_mock)
        except (ValueError, RuntimeError) as exc:
            reason = str(exc)
            break
        executed.append(task_id)
        latest = load_project(project_id)
        latest_tasks = latest.get("tasks", [])
        latest_index = next(i for i, t in enumerate(latest_tasks) if t.get("id") == task_id)
        if task_review_status(latest_tasks[latest_index], task_needs_approval(latest, latest_index)) == REVIEW_PENDING:
            reason = ("최종 검토 승인 대기 중입니다." if latest_index == len(latest_tasks) - 1
                      else "검토 승인 대기 중입니다. 승인 후 자동 진행을 재개해 주세요.")
            break
    project = load_project(project_id)
    project["workflow"] = {"reason": reason, "executed_task_ids": executed, "stopped_at": now()}
    if real:
        project.setdefault("real_ai", {})["stop_reason"] = reason
    project.setdefault("history", []).append({
        "at": now(), "event": "workflow_stopped", "details": f"자동 진행 중단: {reason}",
    })
    save_project(project)


def esc(value):
    return html.escape(str(value), quote=True)

def execution_mode_notice():
    engine = get_execution_engine_name()
    if engine == "mock":
        return "모의 실행 모드: 외부 AI 요청 없음."
    if engine in {"openai_compatible", "openai-compatible"}:
        return (
            "실제 AI 실행 모드: 허용 모델은 openrouter/free입니다. "
            "계획 작성 또는 작업 실행 시 목표·업무 입력·선행 결과가 외부 제공자에 전송될 수 있습니다. "
            "모델 설정이 없거나 openrouter/free와 다르면 요청 전에 중단합니다."
        )
    return "실행 모드 설정 오류: 지원하지 않는 모드에서는 외부 AI 요청을 보내지 않습니다."


def real_ai_controls(project):
    state = project.get("real_ai", {})
    if not isinstance(state, dict):
        state = {}
    attempts = state.get("attempts", [])
    used = len(attempts) if isinstance(attempts, list) else MAX_CALLS
    try:
        limit = project_budget.limit(project)
    except ValueError:
        limit = 0
    stop_reason = state.get("stop_reason", "별도 동의 및 활성화 확인 필요")
    if isinstance(attempts, list) and any(isinstance(a, dict) and a.get("status") == "reserved" for a in attempts):
        stop_reason = "미완료 AI 예약 · 사용자 확인 전 자동 재전송 금지"
    return f"""<section class='card'><h2>실제 무료 AI 시작·재개</h2>
<p>목표·업무 입력·선행 결과·의견이 외부 제공자에 전송될 수 있습니다. 서버 활성화와 해당 프로젝트의 별도 M4 동의가 없으면 요청을 보내지 않습니다. 이 화면에서는 동의를 활성화하지 않습니다.</p>
<p>프로젝트 상한: {limit}회 · 사용/예약: {used}회 · 남은 횟수: {max(0, limit-used)}회 · 시작·재개당 최대 2회</p>
<p>기본 예산 20회는 제공자 무료 할당량이나 비용을 보장하지 않습니다. 실패·시간 초과·예약도 소모하며 자동 재시도하지 않습니다. 증액은 실행 허가가 아닙니다.</p>
<p>추가 예산 요청: {esc([(r['body']['additional'], r['status']) for r in project.get('budget_requests', [])])} · 조회·승인·거절은 소유자가 확인된 로컬 도구에서만 가능합니다.</p>
<p>정지 이유: {esc(stop_reason)}</p>
<form method='post' action='/workflow/run-real' data-processing-form data-processing-label='진행 중...'>
<input type='hidden' name='id' value='{esc(project['id'])}'><button type='submit'>실제 무료 AI 시작·재개 (별도 승인 필요)</button><p data-processing-status hidden></p></form></section>"""

def page(title, body):
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · AI Company OS</title>
<style>
:root {{ color-scheme: light; }}
body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 24px 16px; line-height: 1.55; color: #202124; }}
h1 {{ font-size: 1.6rem; }} h2 {{ font-size: 1.15rem; }}
.card {{ border: 1px solid #ddd; border-radius: 12px; padding: 16px; margin: 12px 0; }}
label {{ display:block; font-weight:600; margin: 10px 0 4px; }}
input, textarea, select {{ box-sizing:border-box; width:100%; padding:10px; border:1px solid #aaa; border-radius:8px; font:inherit; }}
button, .button {{ display:inline-block; background:#1f2937; color:white; border:0; border-radius:8px; padding:10px 14px; font:inherit; text-decoration:none; cursor:pointer; margin-top:10px; }}
.muted {{ color:#666; font-size:.92rem; }} .status {{ font-weight:600; }}
.processing-modal {{ position:fixed; inset:0; z-index:10000; display:flex; align-items:center; justify-content:center; padding:24px; background:rgba(0,0,0,.58); }}
.processing-modal[hidden] {{ display:none; }}
.processing-dialog {{ box-sizing:border-box; width:100%; max-width:420px; padding:28px; border-radius:12px; background:#fff; color:#202124; box-shadow:0 12px 40px rgba(0,0,0,.28); text-align:center; }}
.processing-dialog p {{ margin:0; font-weight:600; }}
.processing-spinner {{ width:36px; height:36px; margin:0 auto 16px; border:4px solid #dbe2ea; border-top-color:#2563eb; border-radius:50%; animation:processing-spin .8s linear infinite; }}
@keyframes processing-spin {{ to {{ transform:rotate(360deg); }} }}
@media (prefers-reduced-motion: reduce) {{ .processing-spinner {{ animation-duration:2s; }} }}
</style></head><body><div id="page-content"><h1><a href="/" style="color:inherit;text-decoration:none">AI Company OS</a></h1>{body}</div><div id="processing-modal" class="processing-modal" role="dialog" aria-modal="true" aria-labelledby="processing-modal-message" hidden><div class="processing-dialog" tabindex="-1"><div class="processing-spinner" role="status" aria-label="작업 처리 중"></div><p id="processing-modal-message">작업 처리 중입니다. 잠시만 기다려 주세요...</p></div></div>{PROCESSING_SCRIPT}</body></html>"""

class Handler(BaseHTTPRequestHandler):
    def _release_project_mutation(self):
        lock = getattr(self, "_mutation_lock", None)
        if lock is not None:
            self._mutation_lock = None
            lock.release()

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_html(self, content, status=200):
        data = content.encode("utf-8")
        self._release_project_mutation()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location):
        self._release_project_mutation()
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def read_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        if not parts:
            self.home()
        elif len(parts) == 2 and parts[0] == "project":
            self.project_detail(parts[1])
        elif len(parts) == 2 and parts[0] == "report":
            self.project_report(parts[1])
        elif len(parts) == 4 and parts[0] == "report" and parts[2] == "download":
            self.download_report(parts[1], parts[3])
        elif parsed.path == "/health":
            self.send_html(page("Health", "<p>OK — Phase 1 app is running.</p>"))
        else:
            self.send_html(page("Not found", "<p>페이지를 찾을 수 없습니다.</p><a class='button' href='/'>홈으로</a>"), 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        form = self.read_form()
        project_routes = {
            "/update", "/manager/plan", "/manager/approve", "/manager/reject",
            "/task/update", "/task/review", "/task/execute", "/workflow/run", "/workflow/run-real", "/quality/review", "/quality/revise-once",
            "/semantic/configure", "/semantic/review", "/semantic/revision-decision",
        }
        if parsed.path not in project_routes:
            return self._handle_post(parsed, form)
        try:
            lock = project_mutation_lock(form.get("id", ""))
        except ValueError:
            self.send_html(page("입력 확인", "<p>프로젝트 ID가 올바르지 않습니다.</p>"), 400)
            return
        if not lock.acquire(blocking=False):
            self.send_html(page(
                "처리 중", "<p>이 프로젝트의 다른 요청을 처리 중입니다. 완료 후 다시 시도해 주세요.</p>"
            ), 409)
            return
        self._mutation_lock = lock
        try:
            with request_scope(save_project):
                return self._handle_post(parsed, form)
        finally:
            self._release_project_mutation()

    def _handle_post(self, parsed, form):
        try:
            if parsed.path == "/manager/decision":
                project_id = form.get("id", "")
                if not form.get("expected_project_hash"):
                    raise ValueError("최신 프로젝트 지문이 필요합니다.")
                respond_manager_decision(project_id, form.get("proposal_id", ""), form.get("expected_hash", ""),
                    form.get("response", ""), answer=form.get("answer", "") if form.get("response") == "answer" else "",
                    expected_project_hash=form["expected_project_hash"])
                self.redirect(f"/project/{project_id}")
            elif parsed.path == "/semantic/configure":
                project_id = form.get("id", "")
                configure_semantic(project_id, form.get("target_task_id", ""), form.get("reviewer_task_id", ""), form.get("criteria", ""))
                self.redirect(f"/project/{project_id}")
            elif parsed.path == "/semantic/review":
                project_id = form.get("id", "")
                run_semantic_review(project_id)
                self.redirect(f"/project/{project_id}")
            elif parsed.path == "/semantic/revision-decision":
                project_id = form.get("id", "")
                decide_semantic_revision(project_id, form.get("decision", ""), form.get("binding_hash", ""))
                self.redirect(f"/project/{project_id}")
            elif parsed.path == "/create":
                name = form.get("name", "").strip()
                goal = form.get("goal", "").strip()
                if not name:
                    self.send_html(page("입력 확인", "<p>프로젝트 이름을 입력해 주세요.</p><a class='button' href='/'>돌아가기</a>"), 400)
                    return
                project_id = uuid.uuid4().hex[:12]
                project = {
                    "id": project_id,
                    "name": name,
                    "goal": goal,
                    "status": "active",
                    "progress": 0,
                    "tasks": [],
                    "artifacts": [],
                    "history": [{"at": now(), "event": "project_created", "details": "프로젝트 생성"}],
                    "created_at": now(),
                    "updated_at": now(),
                    "schema_version": 1
                }
                project["real_ai"] = {"enabled": False, "limit": project_budget.DEFAULT_PROJECT_CALL_BUDGET, "attempts": []}
                save_project(project)
                (ARTIFACTS_DIR / project_id).mkdir(parents=True, exist_ok=True)
                self.redirect(f"/project/{project_id}")
            elif parsed.path == "/manager/plan":
                project_id = form.get("id", "")
                project = load_project(project_id)
                goal = form.get("manager_goal", "").strip() or project.get("goal", "").strip()
                if not goal:
                    raise ValueError("먼저 프로젝트 목표를 입력해 주세요.")
                # Starter plan is isolated in manager_plan.py for future goal-driven planning.
                plan = build_manager_plan(goal, now(), project=project)
                project["manager_goal"] = goal
                project["plan"] = plan
                project.setdefault("history", []).append({"at": now(), "event": "plan_created", "details": "AI 관리자 작업 계획 작성 — 사용자 승인 대기"})
                save_project(project)
                self.redirect(f"/project/{project_id}")
            elif parsed.path == "/manager/approve":
                project_id = form.get("id", "")
                project = load_project(project_id)
                plan = project.get("plan")

                if not plan:
                    raise ValueError("먼저 작업 계획을 작성해 주세요.")

                if plan.get("status") not in ("pending_approval", "changes_requested"):
                    raise ValueError("승인 대기 또는 수정 요청 상태의 계획만 승인할 수 있습니다.")

                plan["status"] = "approved"
                plan["approved_at"] = now()

                tasks = project.setdefault("tasks", [])

                if not tasks:
                    stages = plan.get("stages", [])
                    new_tasks = []
                    for index, stage in enumerate(stages, start=1):
                        task = {
                            "id": f"TASK-{index:03d}",
                            "name": stage.get("name", f"작업 {index}"),
                            "role": stage.get("role", "미지정"),
                            "inputs": stage.get("inputs", []),
                            "output": stage.get("output", ""),
                            "risk": stage.get("risk", ""),
                            "status": "대기",
                            "created_at": now(),
                            "updated_at": now(),
                        }
                        if "input_task_ids" in stage:
                            task["input_task_ids"] = stage["input_task_ids"]
                        new_tasks.append(task)

                    for index, task in enumerate(new_tasks):
                        task["input_task_ids"] = _resolve_input_task_ids(
                            task, new_tasks, index
                        )
                    tasks.extend(new_tasks)

                    project.setdefault("history", []).append({
                        "at": now(),
                        "event": "tasks_created",
                        "details": f"승인된 계획에서 작업 {len(tasks)}개 생성",
                    })

                project.setdefault("history", []).append({
                    "at": now(),
                    "event": "plan_approved",
                    "details": "사용자가 작업 계획 승인",
                })

                save_project(project)
                self.redirect(f"/project/{project_id}")
            elif parsed.path == "/manager/reject":
                project_id = form.get("id", "")
                project = load_project(project_id)
                if project.get("plan"):
                    project["plan"]["status"] = "changes_requested"
                    project["plan"]["feedback"] = form.get("feedback", "").strip()
                    project.setdefault("history", []).append({"at": now(), "event": "plan_changes_requested", "details": "사용자가 계획 수정 요청"})
                    save_project(project)
                self.redirect(f"/project/{project_id}")
            elif parsed.path == "/update":
                project_id = form.get("id", "")
                project = load_project(project_id)
                status = form.get("status", project["status"])
                if status not in VALID_STATUSES:
                    raise ValueError("Invalid status")
                old_status = project["status"]
                project["status"] = status
                project["goal"] = form.get("goal", project.get("goal", "")).strip()
                if old_status != status:
                    project.setdefault("history", []).append({
                        "at": now(), "event": "status_changed",
                        "details": f"{old_status} -> {status}"
                    })
                project.setdefault("history", []).append({
                    "at": now(), "event": "project_saved", "details": "프로젝트 정보 저장"
                })
                save_project(project)
                self.redirect(f"/project/{project_id}")
            

            elif parsed.path == "/task/update":
                project_id = form.get("id", "")
                task_id = form.get("task_id", "")
                project = load_project(project_id)
                state = project.get("semantic", {})
                if task_id in {state.get("target_task_id"), state.get("reviewer_task_id")}:
                    raise ValueError("의미 검토 대상·담당 결과는 전용 수정 승인 및 실행 경로로 변경해 주세요.")

                tasks = project.get("tasks", [])
                task = next(
                    (t for t in tasks if t.get("id") == task_id),
                    None
                )

                if not task:
                    raise ValueError("작업을 찾을 수 없습니다.")

                status = form.get("status", task.get("status", "대기"))
                result = form.get("result", task.get("result", ""))

                if status not in ("대기", "진행 중", "실행 실패", "재검토 필요", "완료"):
                    raise ValueError("잘못된 작업 상태입니다.")

                if status == "완료":
                    task_index = tasks.index(task)
                    _validate_task_predecessors(task, tasks, task_index)
                    unfinished = [
                        previous_task for previous_task in tasks[:task_index]
                        if previous_task.get("status") != "완료"
                        or previous_task.get("review_required")
                    ]
                    if unfinished:
                        names = ", ".join(
                            previous_task.get("name", previous_task.get("id", "이름 없는 작업"))
                            for previous_task in unfinished
                        )
                        raise ValueError(
                            f"앞선 작업의 재검토가 끝나지 않아 완료 처리할 수 없습니다: {names}"
                        )
                    if task.get("review_required"):
                        raise ValueError(
                            "재검토 필요 작업은 상태만 완료로 바꿀 수 없습니다. '작업 실행'으로 다시 실행해 주세요."
                        )
                    if not result.strip():
                        raise ValueError("작업 결과를 입력한 후 완료 처리해 주세요.")

                old_status = task.get("status", "대기")
                old_result = task.get("result", "")
                old_review_status = task_review_status(
                    task,
                    has_dependents=task_needs_approval(project, tasks.index(task)),
                )

                task_index = tasks.index(task)
                result_changed = result != old_result
                status_changed = status != old_status

                if result_changed:
                    task["result_revision"] = result_revision(task) + 1
                task["result"] = result
                task["status"] = status
                task["updated_at"] = now()

                if result_changed:
                    _reset_review_approval(
                        task,
                        task_needs_approval(project, task_index),
                    )
                    task.pop("review_feedback", None)
                elif status_changed and old_review_status == REVIEW_APPROVED:
                    _reset_review_approval(
                        task,
                        task_needs_approval(project, task_index),
                    )

                # 작업 결과/상태가 바뀌면 모든 후속 작업을 재검토 필요로 바꾸고 결과는 보존한다.
                if result_changed or status_changed:
                    reason = (
                        f"선행 작업 {task.get('name', task_id)}의 결과 또는 상태가 변경됨"
                    )
                    mark_downstream_for_review(project, task_index, reason)

                if old_status != status:
                    project.setdefault("history", []).append({
                        "at": now(),
                        "event": "task_status_changed",
                        "details": f"{task_id}: {old_status} -> {status}"
                    })

                if old_result != result:
                    project.setdefault("history", []).append({
                        "at": now(),
                        "event": "task_result_saved",
                        "details": f"{task_id}: 작업 결과 저장"
                    })

                save_project(project)
                self.redirect(f"/project/{project_id}#task-{task_id}")

            elif parsed.path == "/task/review":
                project_id = form.get("id", "")
                task_id = form.get("task_id", "")
                decision = form.get("decision", "")
                review_task_result(project_id, task_id, decision, form.get("feedback", ""))
                self.redirect(f"/project/{project_id}#task-{task_id}")

            elif parsed.path == "/quality/revise-once":
                project_id = form.get("id", "")
                revise_quality_once(project_id, form.get("task_id", ""))
                self.redirect(f"/project/{project_id}")

            elif parsed.path == "/quality/review":
                project_id = form.get("id", "")
                store_quality_review(project_id, form.get("task_id", ""), form.get("ruleset_id", ""), form.get("reviewer_id", ""))
                self.redirect(f"/project/{project_id}")

            elif parsed.path == "/workflow/run-real":
                project_id = form.get("id", "")
                run_real_workflow(project_id)
                self.redirect(f"/project/{project_id}")

            elif parsed.path == "/workflow/run":
                project_id = form.get("id", "")
                run_mock_workflow(project_id)
                self.redirect(f"/project/{project_id}")

            elif parsed.path == "/task/execute":
                project_id = form.get("id", "")
                task_id = form.get("task_id", "")
                execute_project_task(project_id, task_id)
                self.redirect(f"/project/{project_id}#task-{task_id}")

            else:
                self.send_html(page("Not found", "<p>요청을 처리할 수 없습니다.</p><a class='button' href='/'>홈으로</a>"), 404)
        except (ValueError, OSError, json.JSONDecodeError, KeyError, RuntimeError) as exc:
            safe_project_id = locals().get("project_id", "")
            if safe_project_id and all(
                c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
                for c in safe_project_id
            ):
                back_link = (
                    f"<a class='button' href='/project/{esc(safe_project_id)}'>"
                    "프로젝트 상세로 돌아가기</a>"
                )
            else:
                back_link = "<a class='button' href='/'>홈으로</a>"
            task_status = ' data-task-status="실행 실패"' if isinstance(exc, TaskExecutionFailure) else ""
            self.send_html(
                page(
                    "오류",
                    f"<p{task_status}>요청을 처리하지 못했습니다: {esc(exc)}</p>{back_link}",
                ),
                400,
            )

    def download_report(self, project_id, filename):
        try:
            project_path(project_id)
            match = re.fullmatch(r"v([0-9]{6,9})\.(md|json)", filename)
            if not match or int(match.group(1)) < 1 or filename != f"v{int(match.group(1)):06d}.{match.group(2)}":
                raise ValueError("잘못된 확정 버전")
        except ValueError:
            self.send_html(page("입력 확인", "<p>프로젝트 ID 또는 확정 버전이 올바르지 않습니다.</p>"), 400)
            return
        lock = project_mutation_lock(project_id)
        if not lock.acquire(blocking=False):
            self.send_html(page("처리 중", "<p>프로젝트를 처리 중입니다. 완료 후 다시 시도해 주세요.</p>"), 409)
            return
        self._mutation_lock = lock
        try:
            project = load_project(project_id)
            snapshot = load_confirmed_snapshot(project, int(match.group(1)))
            extension = match.group(2)
            data = (confirmed_markdown(snapshot) if extension == "md" else
                    json.dumps(snapshot, ensure_ascii=False, indent=2)).encode("utf-8")
        except (ValueError, OSError, KeyError, TypeError, AttributeError):
            self.send_html(page("미확정", "<p>현재 유효한 확정본을 확인할 수 없어 다운로드하지 않았습니다.</p>"), 409)
            return
        finally:
            self._release_project_mutation()
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8" if extension == "md" else "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{project_id}-v{snapshot["version"]:06d}.{extension}"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def home(self):
        projects = load_projects()
        cards = ""
        for p in projects:
            cards += f"""<section class="card"><h2><a href="/project/{esc(p['id'])}">{esc(p.get('name','이름 없는 프로젝트'))}</a></h2>
<p>{esc(p.get('goal') or '목표가 입력되지 않았습니다.')}</p>
<p class="muted">상태: <span class="status">{esc(p.get('status','active'))}</span> · 최근 수정: {esc(p.get('updated_at',''))}</p></section>"""
        if not cards:
            cards = '<p class="muted">아직 프로젝트가 없습니다. 아래에서 첫 프로젝트를 만들어 보세요.</p>'
        body = f"""<p>프로젝트를 만들고 저장된 작업 상태를 관리하는 1단계 기본 버전입니다.</p>
<section class="card"><h2>새 프로젝트</h2><form method="post" action="/create" data-processing-form data-processing-label="처리 중...">
<label for="name">프로젝트 이름</label><input id="name" name="name" required maxlength="120" placeholder="예: 신규 서비스 조사">
<label for="goal">목표 (선택)</label><textarea id="goal" name="goal" rows="3" maxlength="4000" placeholder="무엇을 이루고 싶은지 자유롭게 적어 주세요."></textarea>
<button type="submit">프로젝트 만들기</button><p class="muted" data-processing-status aria-live="polite" hidden></p></form></section>
<h2>프로젝트 목록 ({len(projects)})</h2>{cards}
<p class="muted">Phase 1 · 로컬 JSON 저장 · API 호출 없음</p>"""
        self.send_html(page("프로젝트 목록", body))

    def render_plan(self, p):
        plan = p.get("plan")
        if not plan:
            return "<p class='muted'>아직 계획이 없습니다. 목표를 입력하고 계획 작성을 눌러 주세요.</p>"
        stages = "".join(
            f"<li><strong>{esc(stage.get('name',''))}</strong> — 담당: {esc(stage.get('role',''))}<br>결과물: {esc(stage.get('output',''))}<br><span class='muted'>위험/확인사항: {esc(stage.get('risk',''))}</span></li>"
            for stage in plan.get("stages", [])
        )
        questions = "".join(f"<li>{esc(q)}</li>" for q in plan.get("questions", []))
        assumptions = "".join(f"<li>{esc(a)}</li>" for a in plan.get("assumptions", []))
        status = plan.get("status", "pending_approval")
        status_labels = {"pending_approval": "승인 대기", "approved": "승인됨", "changes_requested": "수정 요청됨"}
        feedback = f"<p><strong>수정 요청:</strong> {esc(plan.get('feedback',''))}</p>" if plan.get("feedback") else ""
        
        tasks = p.get("tasks", [])
        
        task_rows = "".join(
            f"""<li id="task-{esc(task.get('id', ''))}">
<strong>{esc(task.get('name', ''))}</strong> — 담당: {esc(task.get('role', ''))}<br>
{f"<p><strong>⚠ 재검토 필요:</strong> {esc(task.get('review_reason', '선행 작업이 변경되었습니다.'))}</p>" if task_requires_review(task) else ""}
{task_review_controls(p, task_index)}
{quality_review_controls(p, task_index)}
결과물 설명: {esc(task.get('output', ''))}<br>

<form method='post' action='/task/update' data-processing-form data-processing-label='저장 중...'>
<input type='hidden' name='id' value='{esc(p['id'])}'>
<input type='hidden' name='task_id' value='{esc(task.get('id', ''))}'>

<label>실제 작업 결과
<textarea name='result' rows='5' placeholder='작업 결과 내용을 입력하세요.'>{esc(task.get('result', ''))}</textarea>
</label>

<label>작업 상태
<select name='status'>
{''.join(f"<option value='{s}' {'selected' if task.get('status', '대기') == s else ''}>{s}</option>" for s in ('대기', '진행 중', '실행 실패', '재검토 필요', '완료'))}
</select>
</label>
<button type='submit'>상태 저장</button><p class='muted' data-processing-status aria-live='polite' hidden></p>
</form>
<form method='post' action='/task/execute' data-processing-form data-processing-label='실행 중...'>
<input type='hidden' name='id' value='{esc(p['id'])}'>
<input type='hidden' name='task_id' value='{esc(task.get('id', ''))}'>
<button type='submit'>{'수정 반영 후 다시 실행' if task.get('review_status') == REVIEW_CHANGES_REQUESTED else '작업 실행'}</button><p class='muted' data-processing-status aria-live='polite' hidden></p>
</form>
</li>"""
            for task_index, task in enumerate(tasks)
        )
        task_section = (
            f"<h3>생성된 작업 목록 ({len(tasks)}개)</h3><ol>{task_rows}</ol>"
            if tasks else ""
        )

        actions = ""
        if status in ("pending_approval", "changes_requested"):
            actions = f"""<form method='post' action='/manager/reject' data-processing-form data-processing-label='처리 중...'><input type='hidden' name='id' value='{esc(p['id'])}'><label for='feedback'>계획 수정 요청 내용 (선택)</label><textarea id='feedback' name='feedback' rows='3' placeholder='추가하거나 변경할 내용을 입력하세요.'></textarea><button type='submit'>수정 요청</button><p class='muted' data-processing-status aria-live='polite' hidden></p></form>
<form method='post' action='/manager/approve' data-processing-form data-processing-label='처리 중...'><input type='hidden' name='id' value='{esc(p['id'])}'><button type='submit'>계획 승인</button><p class='muted' data-processing-status aria-live='polite' hidden></p></form>"""
        return f"""<hr><h3>계획 상태: {esc(status_labels.get(status, status))}</h3>
<p><strong>목표:</strong> {esc(plan.get('goal',''))}</p><p><strong>예상 비용:</strong> {esc(plan.get('cost_note',''))}</p>
<h3>관리자가 확인할 질문</h3><ul>{questions}</ul><h3>현재 가정</h3><ul>{assumptions}</ul><h3>작업 단계</h3><ol>{stages}</ol>{task_section}{feedback}{actions}"""

    def project_detail(self, project_id):
        try:
            p = load_project(project_id)
        except (ValueError, OSError, json.JSONDecodeError):
            self.send_html(page("Not found", "<p>프로젝트를 찾을 수 없습니다.</p><a class='button' href='/'>홈으로</a>"), 404)
            return
        history_items = p.get("history", [])
        
        tasks = p.get("tasks", [])
        total_tasks = len(tasks)
        completed_tasks = sum(
            1 for task in tasks if task.get("status") == "완료" and not task_requires_review(task)
        )
        review_tasks = sum(
            1 for task in tasks if task_requires_review(task)
        )
        in_progress_tasks = sum(
            1 for task in tasks if task.get("status") == "진행 중" and not task_requires_review(task)
        )
        failed_tasks = sum(1 for task in tasks if task.get("status") == "실행 실패")
        waiting_tasks = sum(
            1 for task in tasks if task.get("status", "대기") == "대기" and not task_requires_review(task)
        )
        task_progress = (
            round(completed_tasks / total_tasks * 100)
            if total_tasks else 0
        )

        event_names = {
            "task_status_changed": "작업 상태 변경",
            "task_result_saved": "작업 결과 저장",
            "plan_changes_requested": "계획 수정 요청",
            "task_execution_succeeded": "작업 실행 성공",
            "task_execution_failed": "작업 실행 실패",
            "task_review_approved": "업무 결과 검토 승인",
            "task_review_changes_requested": "업무 결과 수정 요청",
            "downstream_review_required": "후속 작업 재검토 필요",
            "project_created": "프로젝트 생성",
            "plan_created": "작업 계획 작성",
            "tasks_created": "작업 생성",
            "plan_approved": "작업 계획 승인",
            "status_changed": "프로젝트 상태 변경",
            "project_saved": "프로젝트 정보 저장",
        }

        history = "".join(
            f"<li>"
            f"<strong>{esc(event_names.get(x.get('event', ''), x.get('event', '기록')))}</strong><br>"
            f"{esc(format_time(x.get('at', '')))}<br>"
            f"{esc(x.get('details', ''))}"
            f"</li>"
            for x in reversed(history_items[-20:])
        )
        artifacts_path = ARTIFACTS_DIR / p["id"]
        body = f"""<p><a href="/">← 프로젝트 목록</a></p>
<section class="card"><h2>{esc(p.get('name',''))}</h2>
<p><strong>프로젝트 ID:</strong> {esc(p['id'])}</p>

<p><strong>업무 실행 완료율:</strong> {task_progress}%</p>
<p><a class="button" href="/report/{esc(p['id'])}">작업 결과·최종 확정 확인</a></p>
<p><strong>최종 확정 여부:</strong> {esc(final_report_state(p))}</p>
{final_download_controls(p)}
<p><strong>전체 작업:</strong> {total_tasks}개</p>
<p><strong>대기:</strong> {waiting_tasks}개 · <strong>진행 중:</strong> {in_progress_tasks}개 · <strong>실행 실패:</strong> {failed_tasks}개 · <strong>재검토 필요:</strong> {review_tasks}개 · <strong>완료:</strong> {completed_tasks}개</p>

<p><strong>생성일:</strong> {esc(p.get('created_at',''))}</p>
<p><strong>최근 수정:</strong> {esc(p.get('updated_at',''))}</p></section>
<section class="card"><h2>프로젝트 정보</h2><form method="post" action="/update" data-processing-form data-processing-label="저장 중...">
<input type="hidden" name="id" value="{esc(p['id'])}">
<label for="goal">목표</label><textarea id="goal" name="goal" rows="4" maxlength="4000">{esc(p.get('goal',''))}</textarea>
<label for="status">상태</label><select id="status" name="status">
<option value="active" {"selected" if p.get("status")=="active" else ""}>진행 중</option>
<option value="paused" {"selected" if p.get("status")=="paused" else ""}>일시 중지</option>
<option value="completed" {"selected" if p.get("status")=="completed" else ""}>완료</option>
</select><button type="submit">저장</button><p class="muted" data-processing-status aria-live="polite" hidden></p></form></section>
<section class="card"><h2>AI 관리자 · 작업 계획</h2>
<p class="muted">{esc(execution_mode_notice())} 계획을 작성한 뒤 사용자가 승인해야 다음 단계로 진행합니다.</p>
<form method="post" action="/manager/plan" data-processing-form data-processing-label="작성 중..."><input type="hidden" name="id" value="{esc(p['id'])}">
<label for="manager_goal">하고 싶은 일 / 목표</label><textarea id="manager_goal" name="manager_goal" rows="4" maxlength="4000" placeholder="원하는 일을 자연어로 입력해 주세요.">{esc(p.get('manager_goal', p.get('goal','')))}</textarea>
<button type="submit">관리자 계획 작성</button><p class="muted" data-processing-status aria-live="polite" hidden></p></form>
{self.render_plan(p)}
</section>
<section class="card"><h2>모의 업무 자동 진행</h2>
<p class="muted">mock 모드에서 요청 한 번에 최대 {MAX_WORKFLOW_TASKS}개 업무를 처리합니다. 검토 승인 대기·수정 요청·실패 시 멈춥니다. 승인 후 다시 재개해 주세요.</p>
<p><strong>멈춘 이유:</strong> {esc(p.get('workflow', {}).get('reason', '아직 시작하지 않았습니다.'))}</p>
<form method="post" action="/workflow/run" data-processing-form data-processing-label="진행 중...">
<input type="hidden" name="id" value="{esc(p['id'])}">
<button type="submit">자동 진행 시작·재개 (mock 전용)</button><p class="muted" data-processing-status aria-live="polite" hidden></p></form></section>
{workflow_guidance.render(p, runtime=sys.modules[__name__])}
{real_ai_controls(p)}
{semantic_controls(p)}
<section class="card"><h2>결과물 보관 폴더</h2><p class="muted">프로젝트별 결과물은 이 폴더에 보관하도록 준비되어 있습니다.</p><code>data/artifacts/{esc(p['id'])}/</code></section>
<section class="card"><h2>최근 변경 기록</h2><ul>{history or '<li>기록 없음</li>'}</ul></section>"""
        self.send_html(page(p.get("name", "프로젝트"), body))


    def project_report(self, project_id):
        try:
            p = load_project(project_id)
        except (ValueError, OSError, json.JSONDecodeError):
            self.send_html(
                page("Not found", "<p>프로젝트를 찾을 수 없습니다.</p><a class='button' href='/'>홈으로</a>"),
                404
            )
            return

        tasks = p.get("tasks", [])
        total_tasks = len(tasks)
        completed_tasks = sum(1 for task in tasks if task.get("status") == "완료" and not task_requires_review(task))
        review_tasks = sum(1 for task in tasks if task_requires_review(task))
        in_progress_tasks = sum(1 for task in tasks if task.get("status") == "진행 중" and not task_requires_review(task))
        failed_tasks = sum(1 for task in tasks if task.get("status") == "실행 실패")
        waiting_tasks = sum(1 for task in tasks if task.get("status", "대기") == "대기" and not task_requires_review(task))
        progress = round(completed_tasks / total_tasks * 100) if total_tasks else 0

        
        task_rows = "".join(
            f"<li><strong>{esc(task.get('name', ''))}</strong> — "
            f"상태: {esc(task.get('status', '대기'))}"
            f"{' · 재검토 필요' if task_requires_review(task) and task.get('status') != '재검토 필요' else ''}<br>"
            f"{f'<p><strong>⚠ 재검토 필요:</strong> {esc(task.get("review_reason", "선행 작업이 변경되었습니다."))}</p>' if task_requires_review(task) else ''}"
            f"담당: {esc(task.get('role', '미지정'))}<br>"
            f"결과물 설명: {esc(task.get('output', '미등록'))}<br>"
            f"실제 작업 결과:<br>"
            f"<p style='margin: 4px 0 12px 0; white-space: pre-wrap; "
            f"font-family: inherit; font-size: inherit; line-height: 1.5;'>"
            f"{esc(task.get('result', '아직 입력된 결과가 없습니다.'))}</p>"
            f"</li>"
            for task in tasks
        )


        unfinished = [
            task for task in tasks if task.get("status") != "완료" or task.get("review_required")
        ]
        unfinished_rows = "".join(
            f"<li>{esc(task.get('name', ''))} — "
            f"{esc(task.get('status', '대기'))}</li>"
            for task in unfinished
        )

        body = f"""
<p><a href="/project/{esc(project_id)}">← 프로젝트로 돌아가기</a></p>
<section class="card">
<h2>{esc(final_report_state(p))}</h2>
{final_download_controls(p)}
<p><strong>프로젝트:</strong> {esc(p.get('name', ''))}</p>
<p><strong>목표:</strong> {esc(p.get('goal', ''))}</p>
<p><strong>업무 실행 완료율:</strong> {progress}%</p>
<p><strong>전체 작업:</strong> {total_tasks}개</p>
<p><strong>대기:</strong> {waiting_tasks}개 ·
<strong>진행 중:</strong> {in_progress_tasks}개 ·
<strong>실행 실패:</strong> {failed_tasks}개 ·
<strong>재검토 필요:</strong> {review_tasks}개 ·
<strong>완료:</strong> {completed_tasks}개</p>
</section>
<section class="card">
<h3>작업별 결과 현황</h3>
<ol>{task_rows or '<li>등록된 작업이 없습니다.</li>'}</ol>
</section>
<section class="card">
<h3>미완료 작업 및 확인 사항</h3>
<ul>{unfinished_rows or '<li>미완료 작업이 없습니다.</li>'}</ul>
<p class="muted">이 보고서는 저장된 작업 데이터를 모아 생성한 기본 보고서이며, AI가 작성한 분석이나 검증 결과는 포함하지 않습니다.</p>
</section>
"""
        self.send_html(page("최종 보고서", body))

if __name__ == "__main__":
    print(f"AI Company OS Phase 1 running at http://{HOST}:{PORT}")
    print(f"Data directory: {DATA_DIR}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
