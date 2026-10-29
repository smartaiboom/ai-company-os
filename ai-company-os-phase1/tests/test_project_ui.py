"""User-facing rendering tests for project plan and task state screens."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class ProjectUITests(unittest.TestCase):
    PROJECT_ID = "project-ui-test"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.temp_dir.name) / "projects"
        self.projects_dir.mkdir()
        self.addCleanup(self.temp_dir.cleanup)

    def _render(self, method, project):
        app.save_project(project)
        handler = app.Handler.__new__(app.Handler)
        with patch.object(app.Handler, "send_html", autospec=True) as send_html:
            method(handler, self.PROJECT_ID)
        return send_html.call_args.args[1]

    def test_pending_plan_is_visible_and_can_be_approved(self):
        project = {
            "id": self.PROJECT_ID,
            "name": "계획 표시 테스트",
            "goal": "할 일 관리 도구 기획",
            "status": "active",
            "tasks": [{
                "id": "TASK-001",
                "name": "초안 작성",
                "role": "작성 담당",
                "inputs": [],
                "output": "초안",
                "status": "대기",
            }],
            "history": [],
            "plan": {
                "status": "pending_approval",
                "goal": "할 일 관리 도구 기획",
                "cost_note": "모의 계획 단계: 외부 AI API 호출 없음",
                "questions": ["완료 시점은 언제인가요?"],
                "assumptions": ["작은 단계로 나누어 진행합니다."],
                "stages": [{
                    "name": "요구사항 정리",
                    "role": "AI 관리자",
                    "output": "성공 기준",
                    "risk": "요구사항 확인 필요",
                }],
            },
        }
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            html = self._render(app.Handler.project_detail, project)

        self.assertIn("계획 상태: 승인 대기", html)
        self.assertIn("요구사항 정리", html)
        self.assertIn("성공 기준", html)
        self.assertIn("action='/manager/approve'", html)
        self.assertIn("계획 승인", html)
        self.assertIn("action='/task/update' data-processing-form", html)
        self.assertIn("action='/task/execute' data-processing-form", html)
        self.assertIn("action='/manager/reject' data-processing-form", html)
        self.assertIn("action='/manager/approve' data-processing-form", html)
        self.assertIn('action="/update" data-processing-form', html)
        self.assertIn('action="/manager/plan" data-processing-form', html)
        self.assertIn('data-processing-label=\'실행 중...\'', html)
        self.assertIn("data-processing-status aria-live='polite' hidden", html)

    def test_project_creation_form_shows_processing_and_restores_on_error(self):
        handler = app.Handler.__new__(app.Handler)
        with patch.object(app, "load_projects", return_value=[]):
            with patch.object(app.Handler, "send_html", autospec=True) as send_html:
                app.Handler.home(handler)
        html = send_html.call_args.args[1]

        self.assertIn('action="/create" data-processing-form', html)
        self.assertIn('data-processing-label="처리 중..."', html)
        self.assertIn('form.dataset.processing === "true"', html)
        self.assertIn("button.disabled = true", html)
        self.assertIn("button.disabled = originalDisabled", html)
        self.assertIn("status.textContent = message", html)
        self.assertIn("window.location.assign(response.url)", html)
        self.assertIn('querySelector("[data-task-status]")', html)
        self.assertIn("statusSelect.value = taskStatus", html)

    def test_processing_modal_locks_and_restores_page_for_all_forms(self):
        handler = app.Handler.__new__(app.Handler)
        with patch.object(app, "load_projects", return_value=[]):
            with patch.object(app.Handler, "send_html", autospec=True) as send_html:
                app.Handler.home(handler)
        html = send_html.call_args.args[1]

        self.assertIn('id="processing-modal" class="processing-modal"', html)
        self.assertIn('role="dialog" aria-modal="true"', html)
        self.assertIn("작업 처리 중입니다. 잠시만 기다려 주세요.", html)
        self.assertIn("background:rgba(0,0,0,.58)", html)
        self.assertIn('id="page-content"', html)
        self.assertIn("pageContent.inert = visible", html)
        self.assertIn('pageContent.setAttribute("aria-busy", "true")', html)
        self.assertIn('pageContent.removeAttribute("aria-busy")', html)
        self.assertIn('document.body.style.overflow = "hidden"', html)
        self.assertIn('document.body.style.overflow = ""', html)
        self.assertIn("if (activeFormRequest || form.dataset.processing === \"true\") return", html)
        self.assertIn("activeFormRequest = false", html)
        self.assertIn("finally", html)
        self.assertIn("setModalVisible(false)", html)

    def test_execution_failure_status_is_visible_in_project_and_report(self):
        project = {
            "id": self.PROJECT_ID,
            "name": "실행 실패 표시 테스트",
            "goal": "실행 실패 상태 표시",
            "status": "active",
            "history": [],
            "plan": {"status": "approved", "goal": "실행 실패 상태 표시", "stages": []},
            "tasks": [{
                "id": "TASK-001",
                "name": "실패한 개발 작업",
                "role": "개발 담당",
                "output": "개발 결과",
                "status": "실행 실패",
            }],
        }
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            detail_html = self._render(app.Handler.project_detail, project)
            report_html = self._render(app.Handler.project_report, project)

        self.assertIn("실행 실패:</strong> 1개", detail_html)
        self.assertIn("value='실행 실패' selected", detail_html)
        self.assertIn("상태: 실행 실패", report_html)
        self.assertIn("실행 실패:</strong> 1개", report_html)
        self.assertIn("실패한 개발 작업 — 실행 실패", report_html)

    def test_review_required_state_is_counted_and_shown_in_final_report(self):
        project = {
            "id": self.PROJECT_ID,
            "name": "재검토 표시 테스트",
            "goal": "결과 재검토",
            "status": "active",
            "history": [],
            "plan": {"status": "approved", "goal": "결과 재검토", "stages": []},
            "tasks": [
                {
                    "id": "TASK-001",
                    "name": "검토 재실행 실패",
                    "role": "품질 검토 담당",
                    "output": "최신 검토 결과",
                    "status": "진행 중",
                    "review_required": True,
                    "review_reason": "선행 결과가 변경되었습니다.",
                    "result": "이전 검토 결과",
                },
                {
                    "id": "TASK-002",
                    "name": "완료된 보고서",
                    "role": "AI 관리자",
                    "output": "최종 보고서",
                    "status": "완료",
                    "result": "저장된 최종 결과",
                },
            ],
        }
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            detail_html = self._render(app.Handler.project_detail, project)
            report_html = self._render(app.Handler.project_report, project)

        self.assertIn("대기:</strong> 0개", detail_html)
        self.assertIn("진행 중:</strong> 0개", detail_html)
        self.assertIn("재검토 필요:</strong> 1개", detail_html)
        self.assertIn("완료:</strong> 1개", detail_html)
        self.assertIn("선행 결과가 변경되었습니다.", detail_html)
        self.assertIn("계획 상태: 승인됨", detail_html)
        self.assertIn("이전 검토 결과", detail_html)
        self.assertIn("value='진행 중' selected", detail_html)
        self.assertNotIn("action='/manager/approve'", detail_html)
        self.assertIn("재검토 필요:</strong> 1개", report_html)
        self.assertIn("진행 중 · 재검토 필요", report_html)
        self.assertIn("검토 재실행 실패", report_html)
        self.assertIn("선행 결과가 변경되었습니다.", report_html)
        self.assertIn("저장된 최종 결과", report_html)


if __name__ == "__main__":
    unittest.main()
