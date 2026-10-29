import io
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

import app


class TaskExecutionPersistenceTests(unittest.TestCase):
    PROJECT_ID = "task-execution-test"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.temp_dir.name) / "projects"
        self.projects_dir.mkdir()
        self.project = {
            "id": self.PROJECT_ID,
            "name": "업무 실행 테스트",
            "goal": "테스트 목표",
            "manager_goal": "테스트 관리자 목표",
            "status": "active",
            "tasks": [{
                "id": "TASK-001",
                "name": "테스트 업무",
                "role": "테스트 담당",
                "inputs": [],
                "output": "테스트 결과물",
                "risk": "검증 필요",
                "status": "대기",
            }],
            "history": [],
        }
        self.addCleanup(self.temp_dir.cleanup)

    def _post_execute(self, task_id="TASK-001"):
        body = urlencode({
            "id": self.PROJECT_ID,
            "task_id": task_id,
        }).encode("utf-8")
        handler = app.Handler.__new__(app.Handler)
        handler.path = "/task/execute"
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        with patch.object(app.Handler, "redirect", autospec=True) as redirect:
            with patch.object(app.Handler, "send_html", autospec=True) as send_html:
                app.Handler.do_POST(handler)
        return handler, redirect, send_html

    def test_mock_task_result_is_saved_through_execution_route(self):
        fake_result = "모의 직원 결과: 요구사항에 맞춘 초안"
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(dict(self.project))
            with patch.object(app, "execute_task", return_value=fake_result) as execute:
                with patch.object(app, "get_execution_engine_name", return_value="mock"):
                    _, redirect, send_html = self._post_execute()
            saved = app.load_project(self.PROJECT_ID)

        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[0]["manager_goal"], "테스트 관리자 목표")
        self.assertEqual(execute.call_args.kwargs["previous_results"], [])
        redirect.assert_called_once_with(
            unittest.mock.ANY,
            f"/project/{self.PROJECT_ID}#task-TASK-001",
        )
        send_html.assert_not_called()
        task = saved["tasks"][0]
        self.assertEqual(task["status"], "완료")
        self.assertEqual(task["result"], fake_result)
        self.assertFalse(task["review_required"])
        self.assertEqual(saved["history"][0]["event"], "task_execution_succeeded")
        self.assertEqual(saved["history"][1]["event"], "task_status_changed")

    def test_failed_task_execution_persists_failure_state_without_result(self):
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(dict(self.project))
            with patch.object(
                app,
                "execute_task",
                side_effect=RuntimeError("simulated engine failure"),
            ) as execute:
                with patch.object(app, "save_project", wraps=app.save_project) as save_project:
                    _, redirect, send_html = self._post_execute()
            saved = app.load_project(self.PROJECT_ID)

        execute.assert_called_once()
        save_project.assert_called_once()
        redirect.assert_not_called()
        send_html.assert_called_once()
        self.assertEqual(send_html.call_args.args[2], 400)
        self.assertIn("simulated engine failure", send_html.call_args.args[1])
        self.assertIn('data-task-status="실행 실패"', send_html.call_args.args[1])
        task = saved["tasks"][0]
        self.assertEqual(task["status"], "실행 실패")
        self.assertNotIn("result", task)
        self.assertEqual(saved["history"][0]["event"], "task_execution_failed")
        self.assertIn("simulated engine failure", saved["history"][0]["details"])
        self.assertEqual(saved["history"][1]["event"], "task_status_changed")

    def test_empty_execution_result_is_rejected_and_not_saved(self):
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(dict(self.project))
            with patch.object(app, "execute_task", return_value="") as execute:
                _, redirect, send_html = self._post_execute()
            saved = app.load_project(self.PROJECT_ID)

        execute.assert_called_once()
        redirect.assert_not_called()
        send_html.assert_called_once()
        self.assertEqual(send_html.call_args.args[2], 400)
        self.assertIn("빈 작업 결과", send_html.call_args.args[1])
        task = saved["tasks"][0]
        self.assertEqual(task["status"], "실행 실패")
        self.assertNotIn("result", task)
        self.assertEqual(saved["history"][0]["event"], "task_execution_failed")
        self.assertIn("빈 작업 결과", saved["history"][0]["details"])

    def test_failed_rerun_preserves_previously_saved_result(self):
        prior_result = "기존에 저장된 정상 결과"
        self.project["tasks"][0].update({
            "status": "진행 중",
            "result": prior_result,
        })
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(dict(self.project))
            with patch.object(
                app,
                "execute_task",
                side_effect=RuntimeError("simulated rerun failure"),
            ):
                self._post_execute()
            saved = app.load_project(self.PROJECT_ID)

        task = saved["tasks"][0]
        self.assertEqual(task["status"], "실행 실패")
        self.assertEqual(task["result"], prior_result)

    def test_length_terminated_api_response_marks_task_failed_without_saving_partial_result(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return (
                    b'{"choices":[{"finish_reason":"length","message":'
                    b'{"role":"assistant","content":"partial response"}}],'
                    b'"usage":{"completion_tokens":4096}}'
                )

        env = {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "openrouter/free",
        }
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(dict(self.project))
            with patch.dict(os.environ, env, clear=True):
                with patch("execution_engine.urlopen", return_value=FakeResponse()) as mocked_urlopen:
                    with self.assertLogs("execution_engine", level="WARNING"):
                        _, redirect, send_html = self._post_execute()
            saved = app.load_project(self.PROJECT_ID)

        mocked_urlopen.assert_called_once()
        redirect.assert_not_called()
        send_html.assert_called_once()
        self.assertEqual(send_html.call_args.args[2], 400)
        self.assertIn("응답이 중간에 끊겼습니다", send_html.call_args.args[1])
        self.assertIn('data-task-status="실행 실패"', send_html.call_args.args[1])
        task = saved["tasks"][0]
        self.assertEqual(task["status"], "실행 실패")
        self.assertNotIn("result", task)
        self.assertEqual(saved["history"][0]["event"], "task_execution_failed")
        self.assertIn("응답이 중간에 끊겼습니다", saved["history"][0]["details"])

    def test_failed_predecessor_blocks_downstream_execution(self):
        self.project["tasks"][0]["status"] = "실행 실패"
        self.project["tasks"].append({
            "id": "TASK-002",
            "name": "후속 업무",
            "role": "테스트 담당",
            "inputs": ["테스트 결과물"],
            "output": "후속 결과",
            "risk": "검증 필요",
            "status": "대기",
        })
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(dict(self.project))
            with patch.object(app, "execute_task") as execute:
                _, redirect, send_html = self._post_execute("TASK-002")
            saved = app.load_project(self.PROJECT_ID)

        execute.assert_not_called()
        redirect.assert_not_called()
        send_html.assert_called_once()
        self.assertIn("앞선 작업을 먼저 완료해 주세요", send_html.call_args.args[1])
        self.assertEqual(saved["tasks"][1]["status"], "대기")
        self.assertNotIn("result", saved["tasks"][1])


if __name__ == "__main__":
    unittest.main()
