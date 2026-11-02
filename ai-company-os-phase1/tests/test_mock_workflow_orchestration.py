"""Bounded orchestration using temporary storage, no sockets or AI requests."""

import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import unittest

import app
from tests import test_concurrent_execution_safety as concurrency


class MockWorkflowTests(unittest.TestCase):
    setUp_storage = concurrency.ConcurrentExecutionSafetyTests.setUp
    project = concurrency.ConcurrentExecutionSafetyTests.project
    post = concurrency.ConcurrentExecutionSafetyTests.post
    slow_execute = concurrency.ConcurrentExecutionSafetyTests.slow_execute

    def setUp(self):
        self.setUp_storage()
        for context in (
            patch.object(app, "PROJECTS_DIR", self.projects),
            patch.dict(os.environ, {"AI_ENGINE": "mock"}, clear=True),
            patch("execution_engine.urlopen", side_effect=AssertionError("no API")),
            patch("manager_plan.urlopen", side_effect=AssertionError("no API")),
        ):
            context.start()
            self.addCleanup(context.stop)

    def save(self, project=None):
        project = project or self.project()
        project["plan"] = {"status": "approved"}
        app.save_project(project)

    def saved(self):
        return app.load_project("concurrent-test")

    def test_plan_approval_run_review_and_resume(self):
        project = self.project()
        project["tasks"] = []
        project["plan"] = app.build_manager_plan("모의 협업", app.now())
        app.save_project(project)
        self.assertEqual(self.post("/manager/approve")[0], 303)
        with patch.object(app, "execute_task_mock", return_value="초안") as execute:
            self.assertEqual(self.post("/workflow/run")[0], 303)
            execute.assert_called_once()
            self.assertEqual(self.saved()["workflow"]["executed_task_ids"], ["TASK-001"])
            self.assertIn("승인 대기", self.saved()["workflow"]["reason"])
            self.post("/workflow/run")
            execute.assert_called_once()
            self.assertEqual(self.post("/task/review", decision="approve")[0], 303)
            self.post("/workflow/run")
            self.assertEqual(execute.call_count, 2)
            self.assertEqual(self.saved()["workflow"]["executed_task_ids"], ["TASK-002"])
            self.assertEqual(execute.call_args.kwargs["previous_results"][0]["task_id"], "TASK-001")
        handler = app.Handler.__new__(app.Handler)
        with patch.object(app.Handler, "send_html", autospec=True) as send:
            handler.project_detail("concurrent-test")
        self.assertIn('action="/workflow/run"', send.call_args.args[1])
        self.assertIn("검토 승인 대기 중", send.call_args.args[1])

    def test_real_unknown_and_empty_modes_reject_without_writes(self):
        self.save()
        before = app.project_path("concurrent-test").read_bytes()
        for mode in ("openai_compatible", "openai-compatible", "unknown", ""):
            with self.subTest(mode=mode), patch.dict(os.environ, {"AI_ENGINE": mode}), \
                 patch.object(app, "execute_task_mock") as execute:
                self.assertEqual(self.post("/workflow/run")[0], 400)
                execute.assert_not_called()
                self.assertEqual(before, app.project_path("concurrent-test").read_bytes())

    def test_unapproved_plan_and_missing_inputs_stop(self):
        self.save()
        project = self.saved()
        project["plan"]["status"] = "pending_approval"
        app.save_project(project)
        with patch.object(app, "execute_task_mock") as execute:
            self.post("/workflow/run")
            self.assertIn("계획을 먼저 승인", self.saved()["workflow"]["reason"])
            self.save()
            project = self.saved()
            project["tasks"][0]["input_task_ids"] = ["MISSING"]
            app.save_project(project)
            self.post("/workflow/run")
            self.assertIn("선행 작업 ID", self.saved()["workflow"]["reason"])
            execute.assert_not_called()

    def test_missing_result_and_change_request_require_manual_attention(self):
        for changes in (
            {"status": "완료", "result": "", "review_status": "approved"},
            {"status": "완료", "review_status": "changes_requested"},
        ):
            with self.subTest(changes=changes), patch.object(app, "execute_task_mock") as execute:
                project = self.project()
                project["tasks"][0].update(changes)
                self.save(project)
                self.post("/workflow/run")
                self.assertEqual(self.saved()["workflow"]["executed_task_ids"], [])
                execute.assert_not_called()

    def test_failure_and_empty_result_preserve_old_result_and_do_not_retry(self):
        for failure in (RuntimeError("mock failure"), ""):
            self.save()
            with self.subTest(failure=type(failure).__name__), \
                 patch.object(app, "execute_task_mock", side_effect=[failure]) as execute:
                self.assertEqual(self.post("/workflow/run")[0], 303)
                self.assertEqual(self.saved()["tasks"][0]["result"], "기존 결과")
                self.assertEqual(self.saved()["tasks"][0]["status"], "실행 실패")
                self.post("/workflow/run")
                execute.assert_called_once()

    def test_limit_and_completed_tasks_never_repeat(self):
        project = self.project()
        project["tasks"] = [
            {"id": f"TASK-{i:03d}", "name": "독립 업무", "status": "대기", "input_task_ids": []}
            for i in range(1, app.MAX_WORKFLOW_TASKS + 3)
        ]
        self.save(project)
        with patch.object(app, "execute_task_mock", return_value="결과") as execute:
            self.post("/workflow/run")
            self.assertEqual(execute.call_count, app.MAX_WORKFLOW_TASKS)
            self.assertIn("상한", self.saved()["workflow"]["reason"])
            self.post("/workflow/run")
            self.assertEqual(execute.call_count, app.MAX_WORKFLOW_TASKS + 2)
            self.post("/workflow/run")
            self.assertEqual(execute.call_count, app.MAX_WORKFLOW_TASKS + 2)
            self.assertIn("실행할 업무가 없습니다", self.saved()["workflow"]["reason"])

    def test_duplicate_manual_and_automatic_requests_share_project_lock(self):
        self.save()
        self.save(self.project("other-project"))
        with patch.object(app, "execute_task_mock", side_effect=self.slow_execute), \
             patch.object(app, "execute_task") as manual, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.post, "/workflow/run")
            try:
                self.assertTrue(self.entered.wait(2))
                self.assertEqual(self.post("/workflow/run")[0], 409)
                self.assertEqual(self.post("/task/execute")[0], 409)
                manual.assert_not_called()
                other = pool.submit(self.post, "/workflow/run", project_id="other-project")
                self.assertEqual(other.result(timeout=2)[0], 303)
                self.assertFalse(first.done())
            finally:
                self.release.set()
            self.assertEqual(first.result(timeout=2)[0], 303)
            self.assertEqual(len(self.calls), 2)


if __name__ == "__main__":
    unittest.main()
