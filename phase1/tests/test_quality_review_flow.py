import io
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

import app


class QualityReviewFlowTests(unittest.TestCase):
    PROJECT_ID = "quality-review-flow-test"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.temp_dir.name) / "projects"
        self.projects_dir.mkdir()
        self.engine_env = patch.dict(os.environ, {"AI_ENGINE": "mock"})
        self.engine_env.start()
        self.addCleanup(self.engine_env.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def _post(self, path, form):
        body = urlencode({"id": self.PROJECT_ID, **form}).encode("utf-8")
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        with patch.object(app.Handler, "redirect", autospec=True) as redirect:
            with patch.object(app.Handler, "send_html", autospec=True) as send_html:
                app.Handler.do_POST(handler)
        return redirect, send_html

    def test_review_result_revision_request_and_rereview_flow(self):
        project = {
            "id": self.PROJECT_ID,
            "name": "검토 흐름 테스트",
            "goal": "초안 검토 및 최종 보고",
            "manager_goal": "초안 검토 및 최종 보고",
            "status": "active",
            "tasks": [
                {
                    "id": "TASK-001",
                    "name": "작업 초안",
                    "role": "콘텐츠 제작 담당",
                    "inputs": [],
                    "output": "작업 초안",
                    "risk": "요구사항 확인 필요",
                    "status": "완료",
                    "result": "초안 v1",
                },
                {
                    "id": "TASK-002",
                    "name": "검토 및 수정",
                    "role": "품질 검토 담당",
                    "inputs": ["작업 초안"],
                    "output": "검토 의견 및 수정본",
                    "risk": "검토 기준 확인 필요",
                    "status": "대기",
                },
            ],
            "history": [{
                "event": "task_execution_succeeded",
                "details": "TASK-001: 작업 실행 성공 (실행 엔진: mock)",
            }],
        }

        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(project)

            redirect, send_html = self._post("/task/review", {
                "task_id": "TASK-001",
                "decision": "approve",
            })
            self.assertFalse(send_html.called)
            self.assertTrue(redirect.called)

            # 실제 API 대신 기존 MockExecutionEngine 경로로 검토를 실행한다.
            redirect, send_html = self._post(
                "/task/execute", {"task_id": "TASK-002"}
            )
            self.assertFalse(send_html.called)
            self.assertTrue(redirect.called)
            reviewed = app.load_project(self.PROJECT_ID)
            review_task = reviewed["tasks"][1]
            self.assertEqual(review_task["status"], "완료")
            self.assertIn("요구사항 충족 여부: 검토 필요", review_task["result"])
            self.assertIn("수정 제안:", review_task["result"])
            self.assertIn("초안 v1", review_task["result"])

            # 이미 작업된 후속 업무를 추가하고, 사용자가 선행 초안을 수정한다.
            reviewed["tasks"].append({
                "id": "TASK-003",
                "name": "최종 보고",
                "role": "AI 관리자",
                "inputs": ["검토 의견 및 수정본"],
                "output": "최종 보고서",
                "risk": "미해결 사항 확인 필요",
                "status": "완료",
                "result": "이전 최종 보고서",
            })
            app.save_project(reviewed)

            redirect, send_html = self._post("/task/update", {
                "task_id": "TASK-001",
                "status": "완료",
                "result": "초안 v2 — 검토 의견 반영",
            })
            self.assertFalse(send_html.called)
            self.assertTrue(redirect.called)
            revised = app.load_project(self.PROJECT_ID)
            self.assertTrue(revised["tasks"][1]["review_required"])
            self.assertEqual(revised["tasks"][1]["status"], "재검토 필요")
            self.assertTrue(revised["tasks"][2]["review_required"])
            self.assertEqual(revised["tasks"][2]["status"], "재검토 필요")
            self.assertTrue(any(
                item["event"] == "downstream_review_required"
                for item in revised["history"]
            ))

            # 수동 편집 결과는 실행 성공 기록이 없으므로 재실행으로 검증한다.
            with patch.object(app, "execute_task", return_value="초안 v2 — 검토 의견 반영"):
                redirect, send_html = self._post("/task/execute", {"task_id": "TASK-001"})
            self.assertFalse(send_html.called)
            self.assertTrue(redirect.called)

            redirect, send_html = self._post("/task/review", {
                "task_id": "TASK-001",
                "decision": "approve",
            })
            self.assertFalse(send_html.called)
            self.assertTrue(redirect.called)

            # 상태만 완료로 바꾸어 검토 표시를 건너뛰는 요청은 거부되고 저장되지 않는다.
            project_path = self.projects_dir / f"{self.PROJECT_ID}.json"
            before = project_path.read_bytes()
            redirect, send_html = self._post("/task/update", {
                "task_id": "TASK-002",
                "status": "완료",
                "result": revised["tasks"][1]["result"],
            })
            redirect.assert_not_called()
            send_html.assert_called_once()
            self.assertEqual(send_html.call_args.args[2], 400)
            self.assertIn("재검토 필요 작업은 상태만 완료로 바꿀 수 없습니다", send_html.call_args.args[1])
            self.assertEqual(project_path.read_bytes(), before)

            # 검토 업무를 다시 실행하면 최신 선행 결과를 반영하고 review_required가 해제된다.
            redirect, send_html = self._post(
                "/task/execute", {"task_id": "TASK-002"}
            )
            self.assertFalse(send_html.called)
            rereviewed = app.load_project(self.PROJECT_ID)
            review_task = rereviewed["tasks"][1]
            self.assertEqual(review_task["status"], "완료")
            self.assertFalse(review_task.get("review_required", False))
            self.assertNotIn("review_reason", review_task)
            self.assertIn("초안 v2 — 검토 의견 반영", review_task["result"])
            self.assertEqual(review_task["review_status"], "pending")

            redirect, send_html = self._post("/task/review", {
                "task_id": "TASK-002",
                "decision": "approve",
            })
            self.assertFalse(send_html.called)
            self.assertTrue(redirect.called)

            # 최종 업무도 검토 결과를 다시 받아 재실행할 수 있다.
            redirect, send_html = self._post(
                "/task/execute", {"task_id": "TASK-003"}
            )
            self.assertFalse(send_html.called)
            final = app.load_project(self.PROJECT_ID)
            self.assertEqual(final["tasks"][2]["status"], "완료")
            self.assertFalse(final["tasks"][2].get("review_required", False))
            self.assertIn("검토 의견 및 수정본", final["tasks"][2]["result"])


if __name__ == "__main__":
    unittest.main()
