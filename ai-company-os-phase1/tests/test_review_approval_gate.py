"""회귀 테스트: 연결된 업무 결과의 검토 승인 게이트."""

import io
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

import app


class ReviewApprovalGateTests(unittest.TestCase):
    PROJECT_ID = "review-gate-test"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.temp_dir.name) / "projects"
        self.projects_dir.mkdir()
        self.engine_env = patch.dict(os.environ, {"AI_ENGINE": "mock"})
        self.engine_env.start()
        self.addCleanup(self.engine_env.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def _project(self, review_status=app.REVIEW_PENDING):
        source = {
            "id": "TASK-001", "name": "시장 조사", "output": "시장 조사 결과",
            "inputs": [], "status": "완료", "result": "조사 결과 v1",
        }
        if review_status is not None:
            source["review_status"] = review_status
        return {
            "id": self.PROJECT_ID,
            "name": "검토 게이트 테스트",
            "goal": "결과를 검토한 뒤 전달",
            "status": "active",
            "tasks": [source, {
                "id": "TASK-002", "name": "제품 기획", "output": "제품 기획안",
                "inputs": ["시장 조사 결과"], "input_task_ids": ["TASK-001"],
                "status": "대기",
            }],
            "history": [{
                "event": "task_execution_succeeded",
                "details": "TASK-001: 작업 실행 성공 (실행 엔진: mock)",
            }],
        }

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

    def test_pending_and_legacy_predecessors_block_before_engine_call(self):
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            for review_status in (app.REVIEW_PENDING, None):
                with self.subTest(review_status=review_status):
                    app.save_project(self._project(review_status))
                    with patch.object(app, "execute_task") as execute:
                        redirect, send_html = self._post(
                            "/task/execute", {"task_id": "TASK-002"}
                        )
                    redirect.assert_not_called()
                    send_html.assert_called_once()
                    self.assertIn("검토 승인이 완료되지 않았습니다", send_html.call_args.args[1])
                    execute.assert_not_called()
                    self.assertEqual(app.load_project(self.PROJECT_ID)["tasks"][1]["status"], "대기")

    def test_approved_predecessor_is_passed_to_engine_and_allows_execution(self):
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(self._project(app.REVIEW_APPROVED))
            with patch.object(app, "execute_task", return_value="기획안") as execute:
                redirect, send_html = self._post(
                    "/task/execute", {"task_id": "TASK-002"}
                )
            self.assertFalse(send_html.called)
            self.assertTrue(redirect.called)
            inputs = execute.call_args.kwargs["previous_results"]
            self.assertEqual([item["task_id"] for item in inputs], ["TASK-001"])
            self.assertIn("조사 결과 v1", inputs[0]["result"])
            self.assertEqual(app.load_project(self.PROJECT_ID)["tasks"][1]["status"], "완료")

    def test_manually_completed_result_without_success_history_cannot_be_approved(self):
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            project = self._project(app.REVIEW_PENDING)
            project["history"] = []
            app.save_project(project)
            redirect, send_html = self._post("/task/review", {
                "task_id": "TASK-001", "decision": "approve",
            })
            redirect.assert_not_called()
            send_html.assert_called_once()
            self.assertIn("실행에 성공해 저장된 결과만 검토", send_html.call_args.args[1])
            self.assertEqual(app.load_project(self.PROJECT_ID)["tasks"][0]["review_status"], app.REVIEW_PENDING)
            with patch.object(app, "execute_task", return_value="검증된 조사 결과") as execute:
                redirect, send_html = self._post("/task/execute", {"task_id": "TASK-001"})
            self.assertFalse(send_html.called)
            execute.assert_called_once()
            self.assertEqual(app.load_project(self.PROJECT_ID)["tasks"][0]["result"], "검증된 조사 결과")

    def test_change_request_requires_feedback_and_feedback_is_rerun_input(self):
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(self._project(app.REVIEW_PENDING))
            redirect, send_html = self._post("/task/review", {
                "task_id": "TASK-001", "decision": "request_changes", "feedback": "  ",
            })
            redirect.assert_not_called()
            send_html.assert_called_once()
            self.assertIn("수정 요청 내용을 입력", send_html.call_args.args[1])

            redirect, send_html = self._post("/task/review", {
                "task_id": "TASK-001", "decision": "request_changes",
                "feedback": "시장 규모 근거를 보완해 주세요.",
            })
            self.assertFalse(send_html.called)
            requested = app.load_project(self.PROJECT_ID)["tasks"][0]
            self.assertEqual(requested["review_status"], app.REVIEW_CHANGES_REQUESTED)
            self.assertEqual(requested["review_feedback"], "시장 규모 근거를 보완해 주세요.")

            with patch.object(app, "execute_task", return_value="조사 결과 v2") as execute:
                redirect, send_html = self._post("/task/execute", {"task_id": "TASK-001"})
            self.assertFalse(send_html.called)
            revisions = execute.call_args.kwargs["previous_results"]
            feedback = next(item for item in revisions if item["input_name"] == "검토 수정 요청")
            self.assertEqual(feedback["result"], "시장 규모 근거를 보완해 주세요.")
            revised = app.load_project(self.PROJECT_ID)["tasks"][0]
            self.assertEqual(revised["review_status"], app.REVIEW_PENDING)
            self.assertEqual(revised["result"], "조사 결과 v2")

            with patch.object(app, "execute_task") as blocked_engine:
                redirect, send_html = self._post("/task/execute", {"task_id": "TASK-002"})
            redirect.assert_not_called()
            send_html.assert_called_once()
            blocked_engine.assert_not_called()
            self._post("/task/review", {"task_id": "TASK-001", "decision": "approve"})
            with patch.object(app, "execute_task", return_value="기획안 v2") as released_engine:
                redirect, send_html = self._post("/task/execute", {"task_id": "TASK-002"})
            self.assertFalse(send_html.called)
            self.assertEqual(released_engine.call_args.kwargs["previous_results"][0]["result"], "조사 결과 v2")

    def test_failed_or_empty_revision_preserves_old_result_and_blocks_downstream(self):
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(self._project(app.REVIEW_PENDING))
            self._post("/task/review", {
                "task_id": "TASK-001", "decision": "request_changes", "feedback": "근거를 보완하세요.",
            })
            for engine_result in (RuntimeError("모의 실행 실패"), None):
                with self.subTest(engine_result=engine_result):
                    if isinstance(engine_result, Exception):
                        engine_patch = patch.object(app, "execute_task", side_effect=engine_result)
                    else:
                        engine_patch = patch.object(app, "execute_task", return_value="")
                    with engine_patch as execute:
                        redirect, send_html = self._post(
                            "/task/execute", {"task_id": "TASK-001"}
                        )
                    self.assertFalse(redirect.called)
                    self.assertTrue(send_html.called)
                    failed = app.load_project(self.PROJECT_ID)["tasks"][0]
                    self.assertEqual(failed["result"], "조사 결과 v1")
                    self.assertEqual(failed["review_status"], app.REVIEW_CHANGES_REQUESTED)
                    self.assertEqual(failed["status"], "실행 실패")
                    self.assertEqual(failed["review_feedback"], "근거를 보완하세요.")
                    with patch.object(app, "execute_task") as downstream:
                        redirect, send_html = self._post("/task/execute", {"task_id": "TASK-002"})
                    redirect.assert_not_called()
                    downstream.assert_not_called()
                    self.assertIn("완료되지 않았습니다", send_html.call_args.args[1])
                    # 다음 반복 전에 테스트 픽스처를 저장해 실패 결과의 원인을 독립시킨다.
                    app.save_project(self._project(app.REVIEW_PENDING))
                    self._post("/task/review", {
                        "task_id": "TASK-001", "decision": "request_changes", "feedback": "근거를 보완하세요.",
                    })

    def test_result_change_revokes_approval_and_marks_existing_downstream_stale(self):
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            project = self._project(app.REVIEW_APPROVED)
            project["tasks"][1].update({"status": "완료", "result": "이전 기획안", "review_status": app.REVIEW_APPROVED})
            app.save_project(project)
            redirect, send_html = self._post("/task/update", {
                "task_id": "TASK-001", "status": "완료", "result": "조사 결과 수정본",
            })
            self.assertFalse(send_html.called)
            saved = app.load_project(self.PROJECT_ID)
            self.assertEqual(saved["tasks"][0]["review_status"], app.REVIEW_PENDING)
            self.assertEqual(saved["tasks"][1]["status"], "재검토 필요")
            with patch.object(app, "execute_task") as execute:
                redirect, send_html = self._post("/task/execute", {"task_id": "TASK-002"})
            redirect.assert_not_called()
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
