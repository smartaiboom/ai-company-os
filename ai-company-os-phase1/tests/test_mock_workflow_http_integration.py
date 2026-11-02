"""Mock orchestration through real loopback HTTP and isolated JSON storage."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request

import app


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class MockWorkflowHTTPTests(unittest.TestCase):
    PROJECT_ID = "mock-http-workflow"

    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        projects, artifacts = root / "projects", root / "artifacts"
        projects.mkdir()
        artifacts.mkdir()
        stack.enter_context(patch.object(app, "PROJECTS_DIR", projects))
        stack.enter_context(patch.object(app, "ARTIFACTS_DIR", artifacts))
        stack.enter_context(patch.dict(os.environ, {"AI_ENGINE": "mock"}, clear=True))
        self.planner_api = stack.enter_context(patch("manager_plan.urlopen", side_effect=AssertionError("no AI API")))
        self.employee_api = stack.enter_context(patch("execution_engine.urlopen", side_effect=AssertionError("no AI API")))

        class QuietHandler(app.Handler):
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        self.base = f"http://127.0.0.1:{server.server_port}"
        self.seed()

    def tearDown(self):
        self.planner_api.assert_not_called()
        self.employee_api.assert_not_called()

    def seed(self, approved=True):
        project = {
            "id": self.PROJECT_ID, "name": "HTTP 자동 진행 검증", "goal": "모의 협업",
            "tasks": [], "history": [], "status": "active",
            "plan": app.build_manager_plan("모의 협업", app.now()),
        }
        app.save_project(project)
        if approved:
            self.assertEqual(self.request("/manager/approve", {})[0], 303)

    def request(self, path, form=None):
        data = None if form is None else urllib.parse.urlencode({"id": self.PROJECT_ID, **form}).encode()
        request = urllib.request.Request(self.base + path, data=data)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            response = opener.open(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.code, response.headers, response.read().decode()

    def saved(self):
        return app.load_project(self.PROJECT_ID)

    def test_approval_start_stop_resume_and_saved_html_match(self):
        code, _, html = self.request(f"/project/{self.PROJECT_ID}")
        self.assertEqual(code, 200)
        self.assertIn('action="/workflow/run" data-processing-form', html)
        self.assertIn("자동 진행 시작·재개 (mock 전용)", html)
        self.assertIn('id="processing-modal"', html)
        with patch.object(app, "execute_task_mock", return_value="승인할 첫 결과") as execute:
            code, headers, _ = self.request("/workflow/run", {})
            self.assertEqual(code, 303)
            self.assertEqual(headers["Location"], f"/project/{self.PROJECT_ID}")
            execute.assert_called_once()
            saved = self.saved()
            self.assertEqual(saved["workflow"]["executed_task_ids"], ["TASK-001"])
            self.assertIn("승인 대기", saved["workflow"]["reason"])
            html = self.request(f"/project/{self.PROJECT_ID}")[2]
            self.assertIn(saved["workflow"]["reason"], html)
            self.assertIn("업무 결과 검토: 검토 승인 대기", html)
            self.request("/workflow/run", {})
            execute.assert_called_once()
            self.assertEqual(self.request("/task/review", {"task_id": "TASK-001", "decision": "approve"})[0], 303)
            self.assertEqual(self.request("/workflow/run", {})[0], 303)
            self.assertEqual(execute.call_count, 2)
            self.assertEqual(execute.call_args.kwargs["previous_results"][0]["task_id"], "TASK-001")
            self.assertIn("승인할 첫 결과", execute.call_args.kwargs["previous_results"][0]["result"])
            self.assertEqual(self.saved()["workflow"]["executed_task_ids"], ["TASK-002"])

    def test_stop_conditions_preserve_results_and_limit_execution(self):
        self.seed(approved=False)
        with patch.object(app, "execute_task_mock") as execute:
            self.request("/workflow/run", {})
            self.assertIn("계획을 먼저 승인", self.saved()["workflow"]["reason"])
            execute.assert_not_called()
        for failure in (RuntimeError("mock failure"), ""):
            with self.subTest(failure=type(failure).__name__):
                self.seed()
                project = self.saved()
                project["tasks"][0]["result"] = "보존할 결과"
                app.save_project(project)
                with patch.object(app, "execute_task_mock", side_effect=[failure]) as execute:
                    self.assertEqual(self.request("/workflow/run", {})[0], 303)
                    self.assertEqual(self.saved()["tasks"][0]["result"], "보존할 결과")
                    self.assertEqual(self.saved()["tasks"][0]["status"], "실행 실패")
                    self.request("/workflow/run", {})
                    execute.assert_called_once()
        for changes, reason in (
            ({"input_task_ids": ["MISSING"]}, "선행 작업 ID"),
            ({"status": "완료", "result": "", "review_status": "approved"}, "결과가 비어"),
            ({"status": "완료", "result": "초안", "review_status": "changes_requested"}, "수정 요청"),
        ):
            with self.subTest(changes=changes):
                self.seed()
                project = self.saved()
                project["tasks"][0].update(changes)
                app.save_project(project)
                with patch.object(app, "execute_task_mock") as execute:
                    self.request("/workflow/run", {})
                    self.assertIn(reason, self.saved()["workflow"]["reason"])
                    execute.assert_not_called()
        project = self.saved()
        project["tasks"] = [
            {"id": f"TASK-{i:03d}", "name": "독립 업무", "status": "대기", "input_task_ids": []}
            for i in range(1, app.MAX_WORKFLOW_TASKS + 3)
        ]
        app.save_project(project)
        with patch.object(app, "execute_task_mock", return_value="모의 결과") as execute:
            self.request("/workflow/run", {})
            self.assertEqual(execute.call_count, app.MAX_WORKFLOW_TASKS)
            self.assertIn("상한", self.saved()["workflow"]["reason"])

    def test_other_modes_reject_without_project_changes(self):
        before = app.project_path(self.PROJECT_ID).read_bytes()
        for engine in ("openai_compatible", "openai-compatible", "unknown", ""):
            with self.subTest(engine=engine), patch.dict(os.environ, {"AI_ENGINE": engine}), \
                 patch.object(app, "execute_task_mock") as execute:
                code, _, html = self.request("/workflow/run", {})
                self.assertEqual(code, 400)
                self.assertIn("mock 모드에서만", html)
                self.assertEqual(before, app.project_path(self.PROJECT_ID).read_bytes())
                execute.assert_not_called()

    def test_concurrent_run_returns_409_and_does_not_start_second_execution(self):
        entered, release = threading.Event(), threading.Event()

        def delayed(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            return "한 번만 생성한 결과"

        with patch.object(app, "execute_task_mock", side_effect=delayed) as execute, ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.request, "/workflow/run", {})
            try:
                self.assertTrue(entered.wait(2))
                code, _, html = self.request("/workflow/run", {})
                self.assertEqual(code, 409)
                self.assertIn("완료 후 다시 시도", html)
                execute.assert_called_once()
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5)[0], 303)
            self.assertEqual(self.saved()["tasks"][0]["result"], "한 번만 생성한 결과")


if __name__ == "__main__":
    unittest.main()
