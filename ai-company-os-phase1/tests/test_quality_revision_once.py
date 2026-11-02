"""One reserved mock revision, candidate reevaluation and approval boundaries."""

import copy
from concurrent.futures import ThreadPoolExecutor
import os
from unittest.mock import patch
import unittest

import app
import quality_review
from tests import test_quality_review as fixtures


class QualityRevisionOnceTests(unittest.TestCase):
    setUp_base = fixtures.QualityReviewIntegrationTests.setUp
    post = fixtures.QualityReviewIntegrationTests.post
    saved = fixtures.QualityReviewIntegrationTests.saved
    execute = fixtures.QualityReviewIntegrationTests.execute
    approve = fixtures.QualityReviewIntegrationTests.approve
    snapshot = fixtures.QualityReviewIntegrationTests.snapshot
    review = fixtures.QualityReviewIntegrationTests.review

    def setUp(self):
        self.setUp_base()
        project = self.saved()
        project["tasks"][-1]["role"] = "개발 담당"
        app.save_project(project)
        self.execute("목표\n수정 전 결과")
        self.assertEqual(self.review()[0], 303)
        self.baseline = copy.deepcopy(self.saved())

    def revise(self, **fields):
        return self.post("/quality/revise-once", task_id="TASK-002", **fields)

    def test_feedback_same_role_single_revision_reassessment_and_pending(self):
        old = self.saved()["tasks"][-1]
        with patch.object(app, "execute_task_mock", return_value=fixtures.VALID) as execute, \
             patch.object(app, "execute_task", side_effect=AssertionError("no configured engine")), \
             patch.object(app, "evaluate_format", wraps=quality_review.evaluate_format) as evaluate:
            self.assertEqual(self.revise()[0], 303)
            execute.assert_called_once()
            evaluate.assert_called_once()
            inputs = execute.call_args.kwargs["previous_results"]
            feedback = next(p for p in inputs if p["input_name"] == "자동 품질 검토 수정 의견")
            self.assertEqual(feedback["task_id"], "TASK-002")
            self.assertIn("미확인 사항", feedback["result"])
            self.assertEqual(execute.call_args.args[1]["role"], "개발 담당")
            self.assertEqual(self.revise()[0], 400)
            execute.assert_called_once()
        task = self.saved()["tasks"][-1]
        self.assertEqual(task["result_revision"], old["result_revision"] + 1)
        self.assertEqual(task["quality_review"]["verdict"], "pass")
        self.assertEqual(task["review_status"], "pending")
        self.assertEqual(task["quality_revision_once"]["attempts"], 1)
        self.assertEqual(task["quality_revision_once"]["reevaluation_attempts"], 1)
        self.assertTrue(task["quality_revision_once"]["stopped_at"].endswith("+09:00"))
        self.assertFalse(self.artifacts.exists())
        self.assertEqual(self.approve()[0], 303)
        self.assertIn("확정 v1", app.final_report_state(self.saved()))

    def test_still_needs_changes_never_loops_or_resets_after_reinspection(self):
        with patch.object(app, "execute_task_mock", return_value="목표\n여전히 누락") as execute:
            self.assertEqual(self.revise()[0], 303)
            self.assertEqual(self.saved()["tasks"][-1]["quality_review"]["verdict"], "changes_needed")
            self.assertEqual(self.review()[0], 303)
            self.assertEqual(self.revise()[0], 400)
            execute.assert_called_once()
        self.assertIn("남은 수정 횟수: 0회", app.quality_review_controls(self.saved(), 1))

    def test_failed_and_empty_executor_preserve_result_and_user_fields(self):
        for outcome in (RuntimeError("mock failure"), ""):
            app.save_project(copy.deepcopy(self.baseline))
            with self.subTest(outcome=type(outcome).__name__), patch.object(app, "execute_task_mock", side_effect=[outcome]) as execute:
                self.assertEqual(self.revise()[0], 400)
                self.assertEqual(self.revise()[0], 400)
                execute.assert_called_once()
            task = self.saved()["tasks"][-1]
            for key in ("result", "result_revision", "review_status", "status", "quality_review"):
                self.assertEqual(task[key], self.baseline["tasks"][-1][key])
            self.assertEqual(task["quality_revision_once"]["phase"], "error")

    def test_evaluation_error_keeps_original_success_and_consumes_attempt(self):
        with patch.object(app, "execute_task_mock", return_value=fixtures.VALID) as execute, \
             patch.object(app, "evaluate_format", side_effect=RuntimeError("mock evaluation failure")):
            self.assertEqual(self.revise()[0], 400)
            self.assertEqual(self.revise()[0], 400)
            execute.assert_called_once()
        task = self.saved()["tasks"][-1]
        self.assertEqual(task["result"], self.baseline["tasks"][-1]["result"])
        self.assertEqual(task["result_revision"], self.baseline["tasks"][-1]["result_revision"])
        self.assertEqual(task["quality_revision_once"]["reevaluation_verdict"], "inconclusive")

    def test_rejects_modes_stale_pass_inconclusive_and_user_requests(self):
        with patch.object(app, "execute_task_mock") as execute:
            for mode in ("openai_compatible", "openai-compatible", "unknown", ""):
                with patch.dict(os.environ, {"AI_ENGINE": mode}):
                    self.assertEqual(self.revise()[0], 400)
            for mutate in (
                lambda p: p["tasks"][-1].update(result="다른 결과"),
                lambda p: p["tasks"][-1].update(status="실행 실패"),
                lambda p: p["tasks"][-1].update(result=""),
                lambda p: p["tasks"][-1].update(review_status="changes_requested", review_feedback="사용자 의견"),
                lambda p: p["tasks"][-1].update(review_status="approved"),
                lambda p: p["tasks"][-1]["quality_review"].update(**quality_review.inconclusive_review()),
                lambda p: p["tasks"][-1]["quality_review"].update(**quality_review.evaluate_format(fixtures.VALID)),
            ):
                project = copy.deepcopy(self.baseline)
                mutate(project)
                app.save_project(project)
                before = app.project_path("concurrent-test").read_bytes()
                self.assertEqual(self.revise()[0], 400)
                self.assertEqual(before, app.project_path("concurrent-test").read_bytes())
            execute.assert_not_called()

    def test_reservation_failure_does_not_execute_and_commit_failure_does_not_repeat(self):
        with patch.object(app, "save_project", side_effect=OSError("reserve failure")), \
             patch.object(app, "execute_task_mock") as execute:
            self.assertEqual(self.revise()[0], 400)
            execute.assert_not_called()
        self.assertNotIn("quality_revision_once", self.saved()["tasks"][-1])
        original_save = app.save_project
        calls = []

        def fail_candidate(project):
            calls.append(1)
            if len(calls) == 2:
                raise OSError("candidate commit failure")
            original_save(project)

        with patch.object(app, "save_project", side_effect=fail_candidate), \
             patch.object(app, "execute_task_mock", return_value=fixtures.VALID) as execute:
            self.assertEqual(self.revise()[0], 400)
            self.assertEqual(self.revise()[0], 400)
            execute.assert_called_once()
        self.assertEqual(self.saved()["tasks"][-1]["result"], self.baseline["tasks"][-1]["result"])

        app.save_project(copy.deepcopy(self.baseline))
        calls.clear()

        def storage_unavailable_after_reservation(project):
            calls.append(1)
            if len(calls) > 1:
                raise OSError("persistent storage failure")
            original_save(project)

        with patch.object(app, "save_project", side_effect=storage_unavailable_after_reservation), \
             patch.object(app, "execute_task_mock", return_value=fixtures.VALID) as execute:
            self.assertEqual(self.revise()[0], 400)
            execute.assert_called_once()
        self.assertEqual(self.saved()["tasks"][-1]["quality_revision_once"]["phase"], "reserved")
        self.assertEqual(self.saved()["tasks"][-1]["result"], self.baseline["tasks"][-1]["result"])
        with patch.object(app, "execute_task_mock") as execute:
            self.assertEqual(self.revise()[0], 400)
            execute.assert_not_called()

    def test_restart_reserved_attempt_rejects_and_get_is_read_only(self):
        project = self.saved()
        project["tasks"][-1]["quality_revision_once"] = {"phase": "reserved", "attempts": 1}
        app.save_project(project)
        before = app.project_path("concurrent-test").read_bytes()
        html = app.quality_review_controls(self.saved(), 1)
        self.assertIn("중단된 수정 예약", html)
        self.assertIn("남은 수정 횟수: 0회", html)
        handler = app.Handler.__new__(app.Handler)
        with patch.object(app.Handler, "send_html", autospec=True):
            handler.project_detail("concurrent-test")
            handler.project_report("concurrent-test")
        with patch.object(app, "execute_task_mock") as execute:
            self.assertEqual(self.revise()[0], 400)
            execute.assert_not_called()
        self.assertEqual(before, app.project_path("concurrent-test").read_bytes())

    def test_confirmed_final_snapshot_is_never_revised(self):
        self.assertEqual(self.approve()[0], 303)
        archive = self.snapshot().read_bytes()
        before = app.project_path("concurrent-test").read_bytes()
        with patch.object(app, "execute_task_mock") as execute:
            self.assertEqual(self.revise()[0], 400)
            execute.assert_not_called()
        self.assertEqual(before, app.project_path("concurrent-test").read_bytes())
        self.assertEqual(archive, self.snapshot().read_bytes())

    def test_revision_after_upstream_change_keeps_invalidated_archive(self):
        self.assertEqual(self.approve()[0], 303)
        archive = self.snapshot().read_bytes()
        self.assertEqual(self.post("/task/update", task_id="TASK-001", status="완료", result="목표\n새 선행 결과")[0], 303)
        with patch.object(app, "execute_task", return_value="목표\n새 선행 결과"):
            self.assertEqual(self.post(task_id="TASK-001")[0], 303)
        self.assertEqual(self.post("/quality/review", task_id="TASK-001", reviewer_id=quality_review.REVIEWER_ID, ruleset_id=quality_review.RULESET_ID)[0], 303)
        with patch.object(app, "execute_task_mock", return_value=fixtures.VALID) as execute:
            self.assertEqual(self.post("/quality/revise-once", task_id="TASK-001")[0], 303)
            execute.assert_called_once()
        self.assertEqual(self.saved()["tasks"][-1]["status"], "재검토 필요")
        self.assertEqual(self.saved()["final_report"]["status"], "invalidated")
        self.assertEqual(archive, self.snapshot().read_bytes())
        self.assertNotIn("최종 보고서 · 확정", app.final_report_state(self.saved()))

    def test_manual_execute_request_cannot_supply_internal_permission(self):
        with patch.object(app, "execute_task_mock") as execute, patch.object(app, "execute_task") as manual:
            self.assertEqual(self.post(task_id="TASK-002", _quality_revision="true")[0], 400)
            execute.assert_not_called()
            manual.assert_not_called()

    def test_duplicate_and_other_project_requests(self):
        project = copy.deepcopy(self.baseline)
        project["id"] = "other-project"
        project["tasks"][-1].pop("quality_execution_context", None)
        app.save_project(project)
        self.assertEqual(self.review(project_id="other-project")[0], 303)

        def delayed(project, task, **kwargs):
            if project["id"] == "concurrent-test":
                self.entered.set()
                if not self.release.wait(5):
                    raise RuntimeError("test timeout")
            return fixtures.VALID

        with patch.object(app, "execute_task_mock", side_effect=delayed) as execute, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.revise)
            try:
                self.assertTrue(self.entered.wait(2))
                self.assertEqual(self.revise()[0], 409)
                self.assertEqual(self.approve()[0], 409)
                other = pool.submit(self.revise, project_id="other-project")
                self.assertEqual(other.result(timeout=2)[0], 303)
                self.assertFalse(first.done())
            finally:
                self.release.set()
            self.assertEqual(first.result(timeout=2)[0], 303)
            self.assertEqual(execute.call_count, 2)


if __name__ == "__main__":
    unittest.main()
