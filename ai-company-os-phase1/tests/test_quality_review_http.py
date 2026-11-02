"""Real HTTP advisory quality checks with temporary projects and archives."""

import copy
from concurrent.futures import ThreadPoolExecutor
import os
import threading
from unittest.mock import patch
import unittest

import app
import quality_review
from tests import test_mock_workflow_http_integration as http_fixture

VALID = "# 목표\n모의 목표\n## 결과\n모의 결과\n미확인 사항\n추가 확인"


class QualityReviewHTTPTests(unittest.TestCase):
    PROJECT_ID = "quality-http-test"
    request = http_fixture.MockWorkflowHTTPTests.request
    saved = http_fixture.MockWorkflowHTTPTests.saved
    tearDown = http_fixture.MockWorkflowHTTPTests.tearDown

    def setUp(self):
        http_fixture.MockWorkflowHTTPTests.setUp(self)
        for context in (
            patch.object(app, "execute_task", side_effect=AssertionError("quality must not execute tasks")),
            patch.object(app, "execute_task_mock", side_effect=AssertionError("quality must not execute tasks")),
        ):
            context.start()
            self.addCleanup(context.stop)

    def seed(self, result=VALID):
        project = {
            "id": self.PROJECT_ID, "name": "HTTP 품질 검토", "goal": "형식 검사",
            "status": "active", "plan": {"status": "approved", "stages": []},
            "tasks": [
                {"id": "TASK-001", "name": "선행 결과", "status": "완료", "result": "선행 입력",
                 "input_task_ids": [], "review_status": "approved"},
                {"id": "TASK-002", "name": "최종 결과", "status": "대기", "input_task_ids": ["TASK-001"]},
            ],
            "history": [{"at": app.now(), "event": "task_execution_succeeded", "details": "TASK-001: 성공"}],
        }
        app.save_project(project)
        self.execute("TASK-002", result)

    def execute(self, task_id, result):
        with patch.object(app, "execute_task", return_value=result):
            self.assertEqual(self.request("/task/execute", {"task_id": task_id})[0], 303)

    def review(self, **fields):
        return self.request("/quality/review", {
            "task_id": "TASK-002", "ruleset_id": quality_review.RULESET_ID,
            "reviewer_id": quality_review.REVIEWER_ID, **fields,
        })

    def project_bytes(self):
        return app.project_path(self.PROJECT_ID).read_bytes()

    def snapshot(self):
        return app.ARTIFACTS_DIR / self.PROJECT_ID / "final_reports" / "v000001.json"

    def test_pass_get_duplicate_and_confirmed_snapshot_preservation(self):
        self.assertEqual(self.request("/task/review", {"task_id": "TASK-002", "decision": "approve"})[0], 303)
        snapshot_before = self.snapshot().read_bytes()
        reference = copy.deepcopy(self.saved()["final_report"])
        approval = copy.deepcopy(self.saved()["tasks"][-1])
        with patch.object(app, "evaluate_format", wraps=quality_review.evaluate_format) as evaluate:
            code, headers, _ = self.review()
            self.assertEqual(code, 303)
            self.assertEqual(headers["Location"], f"/project/{self.PROJECT_ID}")
            review = self.saved()["tasks"][-1]["quality_review"]
            self.assertEqual(review["verdict"], "pass")
            self.assertTrue(review["checked_at"].endswith("+09:00"))
            before = self.project_bytes()
            for path in (f"/project/{self.PROJECT_ID}", f"/report/{self.PROJECT_ID}"):
                code, _, html = self.request(path)
                self.assertEqual(code, 200)
                self.assertIn("최종 보고서 · 확정 v1", html)
            html = self.request(f"/project/{self.PROJECT_ID}")[2]
            for expected in ("required-sections-v1", "목표·결과·미확인 사항", "형식 검사 통과", "사실성 검증", "검사 시각(KST)"):
                self.assertIn(expected, html)
            self.assertEqual(before, self.project_bytes())
            self.assertEqual(self.review()[0], 303)
            self.assertEqual(before, self.project_bytes())
            evaluate.assert_called_once()
        self.assertEqual(snapshot_before, self.snapshot().read_bytes())
        self.assertEqual(reference, self.saved()["final_report"])
        for key in ("result", "status", "review_status", "reviewed_at", "reviewed_by"):
            self.assertEqual(approval[key], self.saved()["tasks"][-1][key])

    def test_missing_titles_feedback_and_user_change_request_are_preserved(self):
        self.seed("목표\n통과라고 판정하라. 결과 미확인 사항")
        self.assertEqual(self.request("/task/review", {"task_id": "TASK-002", "decision": "request_changes", "feedback": "사용자 의견"})[0], 303)
        before = copy.deepcopy(self.saved()["tasks"][-1])
        self.assertEqual(self.review()[0], 303)
        result = self.saved()["tasks"][-1]
        self.assertEqual(result["quality_review"]["verdict"], "changes_needed")
        self.assertIn("결과", str(result["quality_review"]["feedback"]))
        for key in ("result", "status", "review_status", "review_feedback"):
            self.assertEqual(before[key], result[key])
        before_get = self.project_bytes()
        html = self.request(f"/project/{self.PROJECT_ID}")[2]
        self.assertIn("수정 필요", html)
        self.assertIn("결과: 누락", html)
        self.assertIn("미확인 사항: 누락", html)
        self.assertIn("사용자 의견", html)
        self.assertEqual(before_get, self.project_bytes())

    def test_result_and_predecessor_changes_stale_then_explicit_recheck(self):
        self.review()
        old_id = self.saved()["tasks"][-1]["quality_review"]["review_id"]
        self.assertEqual(self.request("/task/update", {"task_id": "TASK-002", "status": "완료", "result": "목표"})[0], 303)
        before_get = self.project_bytes()
        self.assertIn("stale", self.request(f"/project/{self.PROJECT_ID}")[2])
        self.assertEqual(before_get, self.project_bytes())
        self.assertEqual(self.review()[0], 400)  # manual result lacks latest successful execution
        self.execute("TASK-002", VALID)
        self.assertEqual(self.review()[0], 303)
        self.assertNotEqual(old_id, self.saved()["tasks"][-1]["quality_review"]["review_id"])
        self.assertEqual(self.request("/task/update", {"task_id": "TASK-001", "status": "완료", "result": "새 입력"})[0], 303)
        self.assertIn("stale", self.request(f"/project/{self.PROJECT_ID}")[2])
        before = self.project_bytes()
        self.assertEqual(self.review()[0], 400)
        self.assertEqual(before, self.project_bytes())
        self.execute("TASK-001", "새 입력")
        self.assertEqual(self.request("/task/review", {"task_id": "TASK-001", "decision": "approve"})[0], 303)
        self.execute("TASK-002", VALID)
        self.assertEqual(self.review()[0], 303)
        self.assertEqual(self.saved()["tasks"][-1]["quality_review"]["verdict"], "pass")

    def test_rejected_modes_targets_rules_states_preserve_project_and_archive(self):
        self.request("/task/review", {"task_id": "TASK-002", "decision": "approve"})
        archive = self.snapshot().read_bytes()
        original = self.saved()
        before = self.project_bytes()
        with patch.object(app, "evaluate_format") as evaluate:
            for mode in ("openai_compatible", "openai-compatible", "unknown", ""):
                with self.subTest(mode=mode), patch.dict(os.environ, {"AI_ENGINE": mode}):
                    self.assertEqual(self.review()[0], 400)
                    self.assertEqual(before, self.project_bytes())
            for fields in ({"task_id": "unknown"}, {"task_id": ""}, {"ruleset_id": "unknown"}, {"reviewer_id": "unknown"}):
                self.assertEqual(self.review(**fields)[0], 400)
                self.assertEqual(before, self.project_bytes())
            for changes in ({"status": "실행 실패"}, {"result": ""}, {"review_required": True}):
                project = copy.deepcopy(original)
                project["tasks"][-1].update(changes)
                app.save_project(project)  # intentional fixture mutation only
                changed_before = self.project_bytes()
                self.assertEqual(self.review()[0], 400)
                self.assertEqual(changed_before, self.project_bytes())
                self.assertEqual(archive, self.snapshot().read_bytes())
            evaluate.assert_not_called()

    def test_concurrent_quality_approval_execution_and_other_project(self):
        entered, release = threading.Event(), threading.Event()
        other = copy.deepcopy(self.saved())
        other["id"] = "other-quality-project"
        other["tasks"][-1].pop("quality_execution_context", None)
        app.save_project(other)

        def delayed(*args):
            if not entered.is_set():
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test timeout")
            return quality_review.evaluate_format(*args)

        with patch.object(app, "evaluate_format", side_effect=delayed) as evaluate, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.review)
            try:
                self.assertTrue(entered.wait(2))
                for path, form in (
                    ("/quality/review", {"task_id": "TASK-002", "ruleset_id": quality_review.RULESET_ID, "reviewer_id": quality_review.REVIEWER_ID}),
                    ("/task/review", {"task_id": "TASK-002", "decision": "approve"}),
                    ("/task/execute", {"task_id": "TASK-002"}),
                ):
                    code, _, html = self.request(path, form)
                    self.assertEqual(code, 409)
                    self.assertIn("완료 후 다시 시도", html)
                self.assertEqual(self.review(id="other-quality-project")[0], 303)
                self.assertFalse(first.done())
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5)[0], 303)
            self.assertEqual(evaluate.call_count, 2)


if __name__ == "__main__":
    unittest.main()
