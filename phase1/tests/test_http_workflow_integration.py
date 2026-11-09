"""실제 loopback HTTP 요청으로 검토 승인 업무 흐름을 검증한다."""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import app


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class HttpWorkflowIntegrationTests(unittest.TestCase):
    PROJECT_ID = "http-review-gate"

    def _request(self, opener, base_url, path, form=None):
        url = base_url + path
        if form is None:
            request = urllib.request.Request(url, method="GET")
        else:
            body = urllib.parse.urlencode(form).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
        try:
            response = opener.open(request, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.code, response.headers, response.read().decode("utf-8")

    def test_review_gate_and_revision_flow_over_loopback_http(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            projects_dir = root / "projects"
            artifacts_dir = root / "artifacts"
            projects_dir.mkdir()
            artifacts_dir.mkdir()
            project = {
                "id": self.PROJECT_ID,
                "name": "HTTP 검토 게이트 통합 테스트",
                "goal": "승인된 결과만 후속 업무에 전달",
                "status": "active",
                "plan": {
                    "status": "approved",
                    "goal": "승인된 결과만 후속 업무에 전달",
                    "stages": [],
                    "questions": [],
                    "assumptions": [],
                },
                "tasks": [
                    {
                        "id": "TASK-001", "name": "시장 조사",
                        "output": "시장 조사 결과", "inputs": [],
                        "status": "완료", "result": "초기 조사 결과",
                        "review_status": "pending",
                    },
                    {
                        "id": "TASK-002", "name": "제품 기획",
                        "output": "제품 기획안", "inputs": ["시장 조사 결과"],
                        "input_task_ids": ["TASK-001"], "status": "대기",
                    },
                    {
                        "id": "TASK-003", "name": "기록만 있는 검토 대상",
                        "output": "독립 검토 결과", "inputs": [],
                        "status": "완료", "result": "실행 성공 기록이 없는 수동 결과",
                    },
                    {
                        "id": "TASK-004", "name": "기록 검증 후속",
                        "output": "후속 결과", "inputs": ["독립 검토 결과"],
                        "input_task_ids": ["TASK-003"], "status": "대기",
                    },
                ],
                "history": [{
                    "event": "task_execution_succeeded",
                    "details": "TASK-001: 작업 실행 성공 (실행 엔진: mock)",
                }],
            }

            with patch.object(app, "PROJECTS_DIR", projects_dir), \
                 patch.object(app, "ARTIFACTS_DIR", artifacts_dir), \
                 patch.dict(os.environ, {"AI_ENGINE": "mock"}):
                app.save_project(project)
                server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
                server_thread = threading.Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                base_url = f"http://127.0.0.1:{server.server_port}"
                opener = urllib.request.build_opener(NoRedirectHandler())
                try:
                    code, _, body = self._request(opener, base_url, "/health")
                    self.assertEqual(code, 200)
                    self.assertIn("Phase 1 app is running", body)

                    code, _, body = self._request(
                        opener, base_url, f"/project/{self.PROJECT_ID}"
                    )
                    self.assertEqual(code, 200)
                    self.assertIn("업무 결과 검토: 검토 승인 대기", body)
                    self.assertIn("name='task_id' value='TASK-001'", body)
                    self.assertIn("action='/task/review'", body)
                    self.assertIn("실행 성공 기록이 확인되지 않아 검토할 수 없습니다", body)

                    code, _, body = self._request(
                        opener,
                        base_url,
                        "/task/review",
                        {
                            "id": self.PROJECT_ID,
                            "task_id": "TASK-003",
                            "decision": "approve",
                        },
                    )
                    self.assertEqual(code, 400)
                    self.assertIn("실행에 성공해 저장된 결과만 검토", body)

                    code, _, body = self._request(
                        opener,
                        base_url,
                        "/task/review",
                        {
                            "id": self.PROJECT_ID,
                            "task_id": "TASK-001",
                            "decision": "request_changes",
                            "feedback": "  ",
                        },
                    )
                    self.assertEqual(code, 400)
                    self.assertIn("수정 요청 내용을 입력해 주세요", body)

                    code, _, body = self._request(
                        opener,
                        base_url,
                        "/task/execute",
                        {"id": self.PROJECT_ID, "task_id": "TASK-002"},
                    )
                    self.assertEqual(code, 400)
                    self.assertIn("검토 승인이 완료되지 않았습니다", body)
                    saved = app.load_project(self.PROJECT_ID)
                    self.assertEqual(saved["tasks"][1]["status"], "대기")

                    code, headers, _ = self._request(
                        opener,
                        base_url,
                        "/task/review",
                        {
                            "id": self.PROJECT_ID,
                            "task_id": "TASK-001",
                            "decision": "request_changes",
                            "feedback": "시장 규모 근거를 보완해 주세요.",
                        },
                    )
                    self.assertEqual(code, 303)
                    self.assertEqual(headers.get("Location"), f"/project/{self.PROJECT_ID}#task-TASK-001")

                    with patch.object(
                        app, "execute_task", side_effect=RuntimeError("모의 실행 실패")
                    ):
                        code, _, body = self._request(
                            opener,
                            base_url,
                            "/task/execute",
                            {"id": self.PROJECT_ID, "task_id": "TASK-001"},
                        )
                    self.assertEqual(code, 400)
                    self.assertIn("모의 실행 실패", body)
                    saved = app.load_project(self.PROJECT_ID)
                    self.assertEqual(saved["tasks"][0]["result"], "초기 조사 결과")
                    self.assertEqual(saved["tasks"][0]["review_status"], "changes_requested")

                    with patch.object(app, "execute_task", return_value=""):
                        code, _, body = self._request(
                            opener,
                            base_url,
                            "/task/execute",
                            {"id": self.PROJECT_ID, "task_id": "TASK-001"},
                        )
                    self.assertEqual(code, 400)
                    self.assertIn("빈 작업 결과", body)
                    saved = app.load_project(self.PROJECT_ID)
                    self.assertEqual(saved["tasks"][0]["result"], "초기 조사 결과")
                    self.assertEqual(saved["tasks"][0]["review_status"], "changes_requested")

                    with patch.object(app, "execute_task", return_value="조사 결과 v2") as execute:
                        code, _, _ = self._request(
                            opener,
                            base_url,
                            "/task/execute",
                            {"id": self.PROJECT_ID, "task_id": "TASK-001"},
                        )
                    self.assertEqual(code, 303)
                    feedback = next(
                        item for item in execute.call_args.kwargs["previous_results"]
                        if item["input_name"] == "검토 수정 요청"
                    )
                    self.assertEqual(feedback["result"], "시장 규모 근거를 보완해 주세요.")
                    saved = app.load_project(self.PROJECT_ID)
                    self.assertEqual(saved["tasks"][0]["result"], "조사 결과 v2")
                    self.assertEqual(saved["tasks"][0]["review_status"], "pending")

                    with patch.object(app, "execute_task") as blocked_execution:
                        code, _, body = self._request(
                            opener,
                            base_url,
                            "/task/execute",
                            {"id": self.PROJECT_ID, "task_id": "TASK-002"},
                        )
                    self.assertEqual(code, 400)
                    self.assertIn("검토 승인이 완료되지 않았습니다", body)
                    blocked_execution.assert_not_called()

                    code, _, _ = self._request(
                        opener,
                        base_url,
                        "/task/review",
                        {
                            "id": self.PROJECT_ID,
                            "task_id": "TASK-001",
                            "decision": "approve",
                        },
                    )
                    self.assertEqual(code, 303)

                    with patch.object(app, "execute_task", return_value="제품 기획안 v1") as execute:
                        code, _, _ = self._request(
                            opener,
                            base_url,
                            "/task/execute",
                            {"id": self.PROJECT_ID, "task_id": "TASK-002"},
                        )
                    self.assertEqual(code, 303)
                    linked_input = execute.call_args.kwargs["previous_results"][0]
                    self.assertEqual(linked_input["task_id"], "TASK-001")
                    self.assertEqual(linked_input["result"], "조사 결과 v2")

                    code, _, body = self._request(
                        opener, base_url, f"/project/{self.PROJECT_ID}"
                    )
                    self.assertEqual(code, 200)
                    self.assertIn("업무 결과 검토: 검토 승인됨", body)
                    self.assertIn("제품 기획안 v1", body)

                    saved_path = projects_dir / f"{self.PROJECT_ID}.json"
                    persisted = json.loads(saved_path.read_text(encoding="utf-8"))
                    self.assertEqual(persisted["tasks"][0]["review_status"], "approved")
                    self.assertEqual(persisted["tasks"][1]["status"], "완료")
                    self.assertEqual(persisted["tasks"][1]["result"], "제품 기획안 v1")
                finally:
                    server.shutdown()
                    server.server_close()
                    server_thread.join(timeout=3)
                    self.assertFalse(server_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
