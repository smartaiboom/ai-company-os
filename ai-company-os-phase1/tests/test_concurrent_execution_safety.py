"""Socket-free concurrent POST tests using temporary projects and mock execution."""

import io
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import app


class ConcurrentExecutionSafetyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.projects = Path(temp.name)
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = []

    def project(self, project_id="concurrent-test"):
        return {
            "id": project_id, "name": "동시 실행", "goal": "모의 테스트",
            "tasks": [
                {"id": "TASK-001", "name": "조사", "status": "대기", "inputs": [],
                 "input_task_ids": [], "result": "기존 결과"},
                {"id": "TASK-002", "name": "기획", "status": "대기",
                 "input_task_ids": ["TASK-001"]},
            ], "history": [],
        }

    def post(self, path="/task/execute", project_id="concurrent-test", **fields):
        body = urlencode({"id": project_id, "task_id": "TASK-001", **fields}).encode()
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        responses = []
        handler.send_html = lambda content, status=200: responses.append((status, content))
        handler.redirect = lambda location: responses.append((303, location))
        handler.do_POST()
        return responses[0]

    def slow_execute(self, project, task, **kwargs):
        self.calls.append((project["id"], task["id"]))
        if len(self.calls) == 1:
            self.entered.set()
            if not self.release.wait(5):
                raise RuntimeError("test release timeout")
        return "새 결과"

    def test_duplicate_execution_is_rejected_before_second_engine_call(self):
        with patch.object(app, "PROJECTS_DIR", self.projects), \
             patch.object(app, "execute_task", side_effect=self.slow_execute), \
             patch.object(app, "get_execution_engine_name", return_value="mock"), \
             ThreadPoolExecutor(max_workers=1) as pool:
            app.save_project(self.project())
            first = pool.submit(self.post)
            try:
                self.assertTrue(self.entered.wait(2))
                second = self.post()
                self.assertEqual(second[0], 409)
                self.assertIn("처리 중", second[1])
                self.assertEqual(len(self.calls), 1)
            finally:
                self.release.set()
            self.assertEqual(first.result(timeout=2)[0], 303)
            saved = app.load_project("concurrent-test")
            self.assertEqual(saved["tasks"][0]["result"], "새 결과")
            self.assertEqual(sum(e["event"] == "task_execution_succeeded" for e in saved["history"]), 1)

    def test_review_update_and_other_task_cannot_overwrite_running_project(self):
        with patch.object(app, "PROJECTS_DIR", self.projects), \
             patch.object(app, "execute_task", side_effect=self.slow_execute), \
             patch.object(app, "get_execution_engine_name", return_value="mock"), \
             ThreadPoolExecutor(max_workers=1) as pool:
            app.save_project(self.project())
            first = pool.submit(self.post)
            try:
                self.assertTrue(self.entered.wait(2))
                for path, fields in (
                    ("/task/review", {"decision": "approve"}),
                    ("/task/review", {"decision": "request_changes", "feedback": "수정"}),
                    ("/task/update", {"status": "완료", "result": "경합 결과"}),
                    ("/update", {"status": "completed"}),
                    ("/manager/plan", {}),
                    ("/task/execute", {"task_id": "TASK-002"}),
                ):
                    with self.subTest(path=path, fields=fields):
                        self.assertEqual(self.post(path, **fields)[0], 409)
                self.assertEqual(app.load_project("concurrent-test")["tasks"][0]["result"], "기존 결과")
            finally:
                self.release.set()
            self.assertEqual(first.result(timeout=2)[0], 303)
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(self.post("/task/review", decision="approve")[0], 303)
            self.assertEqual(app.load_project("concurrent-test")["tasks"][0]["review_status"], "approved")

    def test_another_project_runs_while_first_project_is_busy(self):
        with patch.object(app, "PROJECTS_DIR", self.projects), \
             patch.object(app, "execute_task", side_effect=self.slow_execute), \
             patch.object(app, "get_execution_engine_name", return_value="mock"), \
             ThreadPoolExecutor(max_workers=2) as pool:
            app.save_project(self.project())
            app.save_project(self.project("other-project"))
            first = pool.submit(self.post)
            try:
                self.assertTrue(self.entered.wait(2))
                other = pool.submit(self.post, project_id="other-project")
                self.assertEqual(other.result(timeout=2)[0], 303)
                self.assertFalse(first.done())
            finally:
                self.release.set()
            self.assertEqual(first.result(timeout=2)[0], 303)

    def test_failed_and_empty_execution_release_lock_for_retry(self):
        with patch.object(app, "PROJECTS_DIR", self.projects), \
             patch.object(app, "get_execution_engine_name", return_value="mock"):
            for failure in (RuntimeError("mock failure"), ""):
                with self.subTest(failure=type(failure).__name__):
                    app.save_project(self.project())
                    with patch.object(app, "execute_task", side_effect=[failure, "재시도 결과"]):
                        self.assertEqual(self.post()[0], 400)
                        self.assertEqual(app.load_project("concurrent-test")["tasks"][0]["result"], "기존 결과")
                        self.assertEqual(self.post()[0], 303)

    def test_execution_cannot_read_half_finished_approval(self):
        with patch.object(app, "PROJECTS_DIR", self.projects), \
             patch.object(app, "get_execution_engine_name", return_value="mock"), \
             patch.object(app, "execute_task", return_value="후속 결과") as execute, \
             ThreadPoolExecutor(max_workers=1) as pool:
            project = self.project()
            project["tasks"][0].update(status="완료", review_status="pending")
            project["history"] = [{"event": "task_execution_succeeded", "details": "TASK-001: 성공"}]
            app.save_project(project)
            original_save = app.save_project

            def slow_save(value):
                self.entered.set()
                if not self.release.wait(5):
                    raise RuntimeError("test release timeout")
                original_save(value)

            with patch.object(app, "save_project", side_effect=slow_save):
                first = pool.submit(self.post, "/task/review", decision="approve")
                try:
                    self.assertTrue(self.entered.wait(2))
                    self.assertEqual(self.post(task_id="TASK-002")[0], 409)
                    execute.assert_not_called()
                finally:
                    self.release.set()
                self.assertEqual(first.result(timeout=2)[0], 303)
            self.assertEqual(self.post(task_id="TASK-002")[0], 303)
            execute.assert_called_once()
            self.assertEqual(app.load_project("concurrent-test")["tasks"][0]["review_status"], "approved")


if __name__ == "__main__":
    unittest.main()
