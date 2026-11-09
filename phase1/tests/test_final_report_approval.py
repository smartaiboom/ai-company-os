"""Final approval and immutable archives; isolated storage, forbidden AI network."""

import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

import app
from tests import test_concurrent_execution_safety as concurrency


class FinalReportApprovalTests(unittest.TestCase):
    post = concurrency.ConcurrentExecutionSafetyTests.post

    def setUp(self):
        concurrency.ConcurrentExecutionSafetyTests.setUp(self)
        self.artifacts = self.projects / "artifacts"
        for context in (
            patch.object(app, "PROJECTS_DIR", self.projects),
            patch.object(app, "ARTIFACTS_DIR", self.artifacts),
            patch.dict(os.environ, {"AI_ENGINE": "mock", "AI_API_KEY": "test-secret-excluded"}, clear=True),
            patch("execution_engine.urlopen", side_effect=AssertionError("no API")),
            patch("manager_plan.urlopen", side_effect=AssertionError("no API")),
        ):
            context.start()
            self.addCleanup(context.stop)
        project = concurrency.ConcurrentExecutionSafetyTests.project(self)
        project["plan"] = {"status": "approved", "stages": []}
        project["tasks"][0].update(status="완료", review_status="approved", reviewed_at=app.now())
        project["tasks"][1]["name"] = "이름이 다른 마지막 산출물"
        project["history"] = [{"at": app.now(), "event": "task_execution_succeeded", "details": "TASK-001: 성공"}]
        app.save_project(project)

    def saved(self):
        return app.load_project("concurrent-test")

    def execute(self, result="최종 결과"):
        with patch.object(app, "execute_task", return_value=result):
            self.assertEqual(self.post(task_id="TASK-002")[0], 303)

    def approve(self):
        return self.post("/task/review", task_id="TASK-002", decision="approve")

    def snapshot(self, version=1):
        return self.artifacts / "concurrent-test" / "final_reports" / f"v{version:06d}.json"

    def confirm(self):
        self.execute()
        self.assertEqual(self.approve()[0], 303)
        self.assertIn("확정 v1", app.final_report_state(self.saved()))

    def test_final_pending_changes_retry_and_version_one(self):
        self.execute()
        self.assertEqual(self.saved()["tasks"][-1]["review_status"], "pending")
        self.assertNotIn("최종 보고서 · 확정", app.final_report_state(self.saved()))
        html = app.task_review_controls(self.saved(), 1)
        self.assertIn("수정 요청", html)
        self.assertEqual(self.post("/task/review", task_id="TASK-002", decision="request_changes", feedback="")[0], 400)
        self.assertEqual(self.post("/task/review", task_id="TASK-002", decision="request_changes", feedback="근거 보완")[0], 303)
        self.assertEqual(self.approve()[0], 400)
        for failure in (RuntimeError("mock fail"), ""):
            with patch.object(app, "execute_task", side_effect=[failure]):
                self.assertEqual(self.post(task_id="TASK-002")[0], 400)
            self.assertEqual(self.saved()["tasks"][-1]["result"], "최종 결과")
            self.assertEqual(self.saved()["tasks"][-1]["review_status"], "changes_requested")
        with patch.object(app, "execute_task", return_value="수정 결과") as execute:
            self.post(task_id="TASK-002")
            self.assertIn("근거 보완", str(execute.call_args.kwargs["previous_results"]))
        self.assertEqual(self.approve()[0], 303)
        snapshot = json.loads(self.snapshot().read_text())
        self.assertTrue(snapshot["confirmed_at"].endswith("+09:00"))
        self.assertEqual(snapshot["evidence"]["tasks"][-1]["result"], "수정 결과")
        self.assertNotIn("test-secret-excluded", self.snapshot().read_text())
        self.assertEqual(self.approve()[0], 400)
        self.assertFalse(self.snapshot(2).exists())

    def test_upstream_change_invalidates_and_new_approval_keeps_old_snapshot(self):
        self.confirm()
        before = self.snapshot().read_bytes()
        self.assertEqual(self.post("/task/update", result="새 선행 결과", status="완료")[0], 303)
        self.assertNotIn("최종 보고서 · 확정", app.final_report_state(self.saved()))
        self.assertEqual(self.saved()["tasks"][-1]["status"], "재검토 필요")
        with patch.object(app, "execute_task", return_value="새 선행 결과"):
            self.assertEqual(self.post()[0], 303)
        self.assertEqual(self.post("/task/review", decision="approve")[0], 303)
        self.execute("다시 생성한 최종 결과")
        self.assertEqual(self.approve()[0], 303)
        self.assertIn("확정 v2", app.final_report_state(self.saved()))
        self.assertEqual(before, self.snapshot().read_bytes())

    def test_business_changes_invalidate_but_ui_status_and_history_do_not(self):
        self.confirm()
        original = self.saved()
        for change in (
            lambda p: p.update(goal="바뀐 목표"),
            lambda p: p.update(manager_goal="새 관리자 목표"),
            lambda p: p["plan"].update(stages=[{"name": "변경"}]),
            lambda p: p["tasks"][0].update(result="바뀐 결과"),
            lambda p: p["tasks"][0].update(status="진행 중"),
            lambda p: p["tasks"][0].update(review_status="changes_requested"),
            lambda p: p["tasks"][-1].update(result="수동 변경"),
            lambda p: p["tasks"].reverse(),
        ):
            project = copy.deepcopy(original)
            change(project)
            self.assertNotIn("최종 보고서 · 확정", app.final_report_state(project))
            app.save_project(project)
            self.assertEqual(self.saved()["final_report"]["status"], "invalidated")
        project = copy.deepcopy(original)
        project.update(status="paused", workflow={"reason": "표시 변경"})
        project["history"].append({"at": app.now(), "event": "project_saved", "details": "표시 변경"})
        app.save_project(project)
        self.assertIn("확정 v1", app.final_report_state(self.saved()))

    def test_missing_corrupt_and_tampered_archives_never_confirm(self):
        self.confirm()
        reference = self.saved()
        path = self.snapshot()
        with patch.object(Path, "read_text", side_effect=FileNotFoundError("mock missing")):
            self.assertNotIn("최종 보고서 · 확정", app.final_report_state(reference))
        path.write_text("{broken")
        self.assertNotIn("최종 보고서 · 확정", app.final_report_state(reference))
        path.write_text(json.dumps({"evidence": app.final_evidence(reference)}))
        self.assertNotIn("최종 보고서 · 확정", app.final_report_state(reference))

    def test_snapshot_write_and_reread_failures_leave_project_unconfirmed(self):
        self.execute()
        before = app.project_path("concurrent-test").read_bytes()
        original_open = Path.open

        def fail_archive_write(path, mode="r", *args, **kwargs):
            if mode == "x":
                raise OSError("mock archive write failure")
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, "open", new=fail_archive_write):
            self.assertEqual(self.approve()[0], 400)
        self.assertEqual(before, app.project_path("concurrent-test").read_bytes())
        original_read = Path.read_text

        def fail_snapshot_read(path, *args, **kwargs):
            if path.parent.name == "final_reports":
                raise OSError("mock archive reread failure")
            return original_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", new=fail_snapshot_read):
            self.assertEqual(self.approve()[0], 400)
        self.assertEqual(before, app.project_path("concurrent-test").read_bytes())
        self.assertTrue(self.snapshot().exists())
        self.assertEqual(self.approve()[0], 303)
        self.assertIn("확정 v2", app.final_report_state(self.saved()))

    def test_project_save_failure_leaves_orphan_and_retry_uses_new_version(self):
        self.execute()
        before = app.project_path("concurrent-test").read_bytes()
        with patch.object(app, "save_project", side_effect=OSError("mock project write failure")):
            self.assertEqual(self.approve()[0], 400)
        self.assertEqual(before, app.project_path("concurrent-test").read_bytes())
        self.assertTrue(self.snapshot().exists())
        self.assertNotIn("최종 보고서 · 확정", app.final_report_state(self.saved()))
        self.assertEqual(self.approve()[0], 303)
        self.assertIn("확정 v2", app.final_report_state(self.saved()))

    def test_legacy_read_only_get_and_failed_preconditions(self):
        project = self.saved()
        project["tasks"][-1].update(status="완료", result="수동 구형 결과", review_status="not_required")
        app.save_project(project)
        before = app.project_path("concurrent-test").read_bytes()
        handler = app.Handler.__new__(app.Handler)
        with patch.object(app.Handler, "send_html", autospec=True) as send:
            handler.project_detail("concurrent-test")
            self.assertIn("미확정", send.call_args.args[1])
            handler.project_report("concurrent-test")
            self.assertIn("업무 실행 완료율", send.call_args.args[1])
        self.assertEqual(before, app.project_path("concurrent-test").read_bytes())
        self.assertEqual(self.approve()[0], 400)
        self.assertFalse(self.artifacts.exists())

    def test_mock_run_stops_at_final_approval_and_get_does_not_write(self):
        with patch.object(app, "execute_task_mock", return_value="최종 모의 결과") as execute:
            self.assertEqual(self.post("/workflow/run")[0], 303)
            execute.assert_called_once()
        self.assertEqual(self.saved()["tasks"][-1]["review_status"], "pending")
        self.assertIn("승인 대기", self.saved()["workflow"]["reason"])
        self.assertFalse(self.artifacts.exists())
        self.assertEqual(self.approve()[0], 303)
        before = app.project_path("concurrent-test").read_bytes()
        archive = self.snapshot().read_bytes()
        handler = app.Handler.__new__(app.Handler)
        with patch.object(app.Handler, "send_html", autospec=True) as send:
            handler.project_detail("concurrent-test")
            self.assertIn("최종 확정 여부", send.call_args.args[1])
            handler.project_report("concurrent-test")
            self.assertIn("최종 보고서 · 확정 v1", send.call_args.args[1])
        self.assertEqual(before, app.project_path("concurrent-test").read_bytes())
        self.assertEqual(archive, self.snapshot().read_bytes())

    def test_final_approval_serializes_with_duplicate_and_manual_execution(self):
        self.execute()
        archive = app.archive_final_report

        def slow_archive(project):
            self.entered.set()
            if not self.release.wait(5):
                raise RuntimeError("test timeout")
            archive(project)

        with patch.object(app, "archive_final_report", side_effect=slow_archive), \
             patch.object(app, "execute_task") as execute, ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.approve)
            try:
                self.assertTrue(self.entered.wait(2))
                self.assertEqual(self.approve()[0], 409)
                self.assertEqual(self.post(task_id="TASK-002")[0], 409)
                execute.assert_not_called()
            finally:
                self.release.set()
            self.assertEqual(first.result(timeout=2)[0], 303)
        self.assertTrue(self.snapshot().exists())
        self.assertFalse(self.snapshot(2).exists())

    def test_stale_execution_context_and_duplicate_ids_cannot_be_approved(self):
        self.execute()
        project = self.saved()
        project["goal"] = "성공 후 바뀐 목표"
        app.save_project(project)
        self.assertEqual(self.approve()[0], 400)
        project["tasks"][-1]["id"] = "TASK-001"
        app.save_project(project)
        self.assertEqual(self.post("/task/review", decision="approve")[0], 400)
        self.assertFalse(self.artifacts.exists())

    def test_confirmed_final_change_request_keeps_feedback_and_archived_version(self):
        self.confirm()
        original = self.snapshot().read_bytes()
        self.assertEqual(self.post("/task/review", task_id="TASK-002", decision="request_changes", feedback="확정 후 수정 의견")[0], 303)
        self.assertEqual(self.saved()["tasks"][-1]["review_status"], "changes_requested")
        with patch.object(app, "execute_task", return_value="확정 후 수정 결과") as execute:
            self.assertEqual(self.post(task_id="TASK-002")[0], 303)
            self.assertIn("확정 후 수정 의견", str(execute.call_args.kwargs["previous_results"]))
        self.assertEqual(self.approve()[0], 303)
        self.assertIn("확정 v2", app.final_report_state(self.saved()))
        self.assertEqual(original, self.snapshot().read_bytes())


if __name__ == "__main__":
    unittest.main()
