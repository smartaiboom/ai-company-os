"""Project-scoped, bounded OpenRouter transport. Disabled unless explicitly armed."""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import uuid
import uncertain_reservations
import project_budget
import ai_provider_adapter
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MODEL = "openrouter/free"
BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_PROJECT_CALL_BUDGET = project_budget.DEFAULT_PROJECT_CALL_BUDGET
MAX_CALLS = DEFAULT_PROJECT_CALL_BUDGET  # Compatibility alias; not a hard maximum.
MAX_CALLS_PER_REQUEST = 2
MAX_INPUT_BYTES = 131072
MAX_TOTAL_INPUT_BYTES = project_budget.MAX_PROJECT_CALL_BUDGET * MAX_INPUT_BYTES
MAX_RESPONSE_BYTES = 262144
MAX_OUTPUT_TOKENS = 4096
_scope = ContextVar("real_ai_scope", default=None)


def now():
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def goal_hash(goal):
    return hashlib.sha256(str(goal).encode("utf-8")).hexdigest()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def unique_response_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("AI 응답 JSON에 중복 필드가 있습니다.")
        result[key] = value
    return result


def guarded_urlopen(request, timeout):
    # Never forward authorization to a redirect host or an environment proxy.
    return build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout)


@contextmanager
def request_scope(persist):
    token = _scope.set({"persist": persist, "used": 0, "project_id": None})
    try:
        yield
    finally:
        _scope.reset(token)


def check_project_permission(project, goal=None):
    if os.getenv("AI_REAL_REQUESTS_ENABLED", "") != "1":
        raise ValueError("실제 AI 요청은 서버에서 비활성화되어 있습니다. M4 별도 승인이 필요합니다.")
    if os.getenv("AI_ENGINE", "mock").strip().lower() not in {"openai_compatible", "openai-compatible"}:
        raise ValueError("실제 AI 엔진 모드가 아닙니다.")
    if not isinstance(project, dict) or not project.get("id"):
        raise ValueError("실제 AI 요청에는 프로젝트 정보가 필요합니다.")
    state = project.get("real_ai", {})
    if not isinstance(state, dict):
        raise ValueError("실제 AI 동의 설정이 올바르지 않습니다.")
    consent = state.get("consent", {})
    effective_goal = goal if goal is not None else project.get("manager_goal") or project.get("goal", "")
    if (state.get("enabled") is not True or not isinstance(consent, dict)
            or consent.get("approved") is not True or not consent.get("approved_at")
            or consent.get("goal_hash") != goal_hash(effective_goal)
            or consent.get("data_scope") != "goal_task_inputs_predecessors_feedback"):
        raise ValueError("해당 목표·업무 입력·선행 결과·의견의 외부 전송 동의와 활성화가 필요합니다.")
    attempts = state.get("attempts", [])
    limit = project_budget.limit(project)
    if (not isinstance(attempts, list)
            or any(not isinstance(a, dict) or a.get("status") not in {"reserved", "completed", "failed"}
                   or not isinstance(a.get("id"), str) or not a["id"]
                   or type(a.get("input_bytes")) is not int or not 0 <= a["input_bytes"] <= MAX_INPUT_BYTES
                   for a in attempts)):
        raise ValueError("실제 AI 예산 기록이 올바르지 않습니다.")
    if len({a["id"] for a in attempts}) != len(attempts):
        raise ValueError("중복된 AI 시도 기록이 있습니다.")
    if (any(a["status"] == "reserved" for a in attempts)
            and not uncertain_reservations.permits(project, effective_goal)):
        raise ValueError("완료 여부가 불명확한 AI 예약이 있습니다. 자동 재전송하지 않습니다.")
    if len(attempts) >= limit:
        scope = _scope.get()
        if scope is not None:
            project_budget.ensure_shortage_request(project, [{"purpose": "다음 승인된 AI 업무 실행", "calls": 1}])
            scope["persist"](project)
        raise ValueError("프로젝트 실제 AI 요청 예산을 소진했습니다.")
    return state, attempts, limit


def request_json(project, *, model, base_url, body, api_key, timeout, transport, kind, task_id=None, goal=None):
    # Validate immediately before every attempt, including manually reused engines.
    if model != MODEL:
        raise ValueError("무료 모델 보호: AI_MODEL은 정확히 openrouter/free여야 합니다.")
    if base_url.rstrip("/") != BASE_URL:
        raise ValueError("허용된 OpenRouter HTTPS API 주소만 사용할 수 있습니다.")
    adapter = ai_provider_adapter.require_live_adapter(model=model, base_url=base_url, api_key=api_key)
    state, attempts, limit = check_project_permission(project, goal)
    scope = _scope.get()
    if scope is None or scope["used"] >= MAX_CALLS_PER_REQUEST:
        raise ValueError("명시적 요청 범위가 없거나 시작·재개당 최대 2회에 도달했습니다.")
    if scope["project_id"] not in (None, project["id"]):
        raise ValueError("한 요청에서 다른 프로젝트 예산을 사용할 수 없습니다.")
    if not isinstance(body, bytes) or len(body) > MAX_INPUT_BYTES:
        raise ValueError("AI 입력 크기 상한을 초과했습니다.")
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("AI 입력 형식이 올바르지 않습니다.") from None
    if (not isinstance(payload, dict) or payload.get("model") != MODEL
            or type(payload.get("max_tokens")) is not int or not 1 <= payload["max_tokens"] <= MAX_OUTPUT_TOKENS):
        raise ValueError("AI 모델 또는 출력 토큰 상한이 올바르지 않습니다.")
    if sum(a.get("input_bytes", 0) for a in attempts) + len(body) > min(limit * MAX_INPUT_BYTES, MAX_TOTAL_INPUT_BYTES):
        raise ValueError("프로젝트 누적 AI 입력 상한을 초과했습니다.")
    entry = {"id": uuid.uuid4().hex, "kind": kind, "task_id": task_id, "model": MODEL,
             "status": "reserved", "reserved_at": now(), "input_bytes": len(body),
             "max_tokens": payload["max_tokens"]}
    if any(a["status"] == "reserved" for a in attempts):
        uncertain_reservations.consume(project, entry["id"])
    state["attempts"] = attempts + [entry]
    state["limit"] = limit
    scope["persist"](project)  # No transport without a durable consumed attempt.
    scope["used"] += 1
    scope["project_id"] = project["id"]
    request = adapter.build_request(body, api_key)
    try:
        with transport(request, timeout=min(90, max(1, int(timeout)))) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("AI 응답 크기 상한을 초과했습니다.")
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_response_object)
        if not isinstance(parsed, dict):
            raise RuntimeError("AI 응답 형식이 올바르지 않습니다.")
    except Exception as exc:
        if isinstance(exc, HTTPError):
            exc.close()
        entry.update(status="failed", finished_at=now())
        state["stop_reason"] = "AI 요청 오류로 정지했습니다. 자동 재전송하지 않습니다."
        scope["persist"](project)
        if isinstance(exc, HTTPError):
            raise RuntimeError(f"AI API 요청 실패 (HTTP {exc.code}). 제공자 오류 본문은 표시하지 않습니다.") from None
        if isinstance(exc, (URLError, TimeoutError)):
            raise RuntimeError("AI API 연결 실패 또는 시간 초과. 오류 상세는 표시하지 않습니다.") from None
        raise RuntimeError("AI 요청 또는 응답 처리 실패. 오류 상세는 표시하지 않습니다.") from None
    entry.update(status="completed", finished_at=now())
    scope["persist"](project)
    return parsed
