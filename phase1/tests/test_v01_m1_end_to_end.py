"""M1: one loopback goal-to-download flow, with mock execution fixtures."""

from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import app
import quality_review
from tests import test_mock_workflow_http_integration as http_fixture

GOOD = "# 목표\n재고 확인 업무 개선\n## 결과\n주간 확인 절차\n## 미확인 사항\n실사용자 검증 필요"
BAD = "목표\n추가 작성이 필요한 초안"


class M1EndToEndHTTPTests(unittest.TestCase):
    PROJECT_ID = "new-project"
    request = http_fixture.MockWorkflowHTTPTests.request
    saved = http_fixture.MockWorkflowHTTPTests.saved
    tearDown = http_fixture.MockWorkflowHTTPTests.tearDown
    setUp = http_fixture.MockWorkflowHTTPTests.setUp

    def seed(self):
        code, headers, _ = self.request("/create", {"name": "M1 통합 시연", "goal": "재고 확인 업무 개선 제안"})
        self.assertEqual(code, 303)
        self.PROJECT_ID = headers["Location"].split("/")[-1]

    def post(self, path, **form):
        code, _, body = self.request(path, form)
        self.assertEqual(code, 303, body)

    def approve(self, task_id):
        self.post("/task/review", task_id=task_id, decision="approve")

    def prepare_revision(self):
        self.post("/manager/plan")
        self.post("/manager/approve")
        with patch.object(app, "execute_task_mock", return_value="요구사항: 재고 확인 부담 완화") as execute:
            self.post("/workflow/run")
            execute.assert_called_once()
        self.approve("TASK-001")
        with patch.object(app, "execute_task_mock", return_value=BAD) as execute:
            self.post("/workflow/run")
            inputs = execute.call_args.kwargs["previous_results"]
            self.assertEqual(inputs[0]["task_id"], "TASK-001")
            self.assertIn("재고 확인", inputs[0]["result"])
        self.post("/quality/review", task_id="TASK-002", reviewer_id=quality_review.REVIEWER_ID, ruleset_id=quality_review.RULESET_ID)
        self.assertEqual(self.saved()["tasks"][1]["quality_review"]["verdict"], "changes_needed")

    def complete(self):
        self.prepare_revision()
        with patch.object(app, "execute_task_mock", return_value=GOOD) as execute, \
             patch.object(app, "evaluate_format", wraps=quality_review.evaluate_format) as evaluate:
            self.post("/quality/revise-once", task_id="TASK-002")
            execute.assert_called_once()
            evaluate.assert_called_once()
            self.assertEqual(execute.call_args.args[1]["role"], "콘텐츠 제작 담당")
            feedback = next(p for p in execute.call_args.kwargs["previous_results"] if p["input_name"] == "자동 품질 검토 수정 의견")
            self.assertEqual(feedback["task_id"], "TASK-002")
            self.assertIn("미확인 사항", feedback["result"])
            self.assertEqual(self.request("/quality/revise-once", {"task_id": "TASK-002"})[0], 400)
            self.post("/workflow/run")  # Must stop at user approval, without executing.
            execute.assert_called_once()
        revised = self.saved()["tasks"][1]
        self.assertEqual(revised["result_revision"], 2)
        self.assertEqual(revised["quality_review"]["verdict"], "pass")
        self.assertEqual(revised["review_status"], "pending")
        self.approve("TASK-002")
        with patch.object(app, "execute_task_mock", return_value="형식 및 요구사항 대조용 mock 검토 결과") as execute:
            self.post("/workflow/run")
            self.assertIn(GOOD, [item["result"] for item in execute.call_args.kwargs["previous_results"]])
        self.approve("TASK-003")
        with patch.object(app, "execute_task_mock", return_value="최종 제안서\n단계별 실행·검증 계획과 미해결 사항"):
            self.post("/workflow/run")
        self.assertEqual(self.saved()["tasks"][-1]["review_status"], "pending")
        self.assertEqual(self.request(self.download_path())[0], 409)
        self.approve("TASK-004")

    def snapshot_path(self, version=1):
        return app.ARTIFACTS_DIR / self.PROJECT_ID / "final_reports" / f"v{version:06d}.json"

    def download_path(self, version=1):
        return f"/report/{self.PROJECT_ID}/download/v{version:06d}.md"

    def test_one_goal_through_revision_approval_archive_and_download(self):
        self.complete()
        project_before = app.project_path(self.PROJECT_ID).read_bytes()
        archive_before = self.snapshot_path().read_bytes()
        snapshot = json.loads(archive_before)
        code, headers, markdown = self.request(self.download_path())
        self.assertEqual(code, 200)
        self.assertIn("text/markdown", headers["Content-Type"])
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        for expected in (self.PROJECT_ID, "확정 버전: v1", snapshot["confirmed_at"], snapshot["evidence"]["goal"]):
            self.assertIn(expected, markdown)
        for task in snapshot["evidence"]["tasks"]:
            self.assertIn(task["id"], markdown)
            self.assertIn(task["result"], markdown)
        self.assertNotIn(str(app.ARTIFACTS_DIR), markdown)
        self.assertNotIn("AI_API_KEY", markdown)
        self.assertNotIn("execution_context", markdown)
        for path in (f"/project/{self.PROJECT_ID}", f"/report/{self.PROJECT_ID}"):
            html = self.request(path)[2]
            self.assertIn(self.download_path(), html)
            self.assertIn("Markdown 확정본 다운로드", html)
        self.assertEqual(project_before, app.project_path(self.PROJECT_ID).read_bytes())
        self.assertEqual(archive_before, self.snapshot_path().read_bytes())

    def test_unconfirmed_versions_and_path_manipulation_are_rejected(self):
        self.assertEqual(self.request(self.download_path())[0], 409)
        html = self.request(f"/project/{self.PROJECT_ID}")[2]
        self.assertNotIn(self.download_path(), html)
        for path in (
            "/report/../download/v000001.md",
            "/report/%2e%2e/download/v000001.md",
            f"/report/{self.PROJECT_ID}/download/%2fetc%2fpasswd",
            f"/report/{self.PROJECT_ID}/download/v000000.md",
            f"/report/{self.PROJECT_ID}/download/v1.md",
        ):
            self.assertEqual(self.request(path)[0], 400)
        self.complete()
        self.assertEqual(self.request(self.download_path(2))[0], 409)

    def test_corrupt_missing_or_escaping_snapshot_is_not_downloaded(self):
        self.complete()
        before = app.project_path(self.PROJECT_ID).read_bytes()
        original_read = Path.read_text

        def missing_snapshot(path, *args, **kwargs):
            if path == self.snapshot_path():
                raise FileNotFoundError("mock missing")
            return original_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", new=missing_snapshot):
            self.assertEqual(self.request(self.download_path())[0], 409)
        with patch.object(Path, "is_relative_to", return_value=False):
            self.assertEqual(self.request(self.download_path())[0], 409)
        self.snapshot_path().write_text('{"tampered": true}')  # disposable fixture only
        corrupt_before = self.snapshot_path().read_bytes()
        self.assertEqual(self.request(self.download_path())[0], 409)
        self.assertEqual(corrupt_before, self.snapshot_path().read_bytes())
        self.assertEqual(before, app.project_path(self.PROJECT_ID).read_bytes())

    def test_invalidation_and_v2_keep_v1_and_expose_only_current_version(self):
        self.complete()
        archive = self.snapshot_path().read_bytes()
        self.post("/task/review", task_id="TASK-004", decision="request_changes", feedback="최종 검증 계획 보완")
        self.assertEqual(self.request(self.download_path())[0], 409)
        with patch.object(app, "execute_task", return_value="보완한 최종 제안서"):
            self.post("/task/execute", task_id="TASK-004")
        self.approve("TASK-004")
        self.assertEqual(self.request(self.download_path())[0], 409)
        code, _, markdown = self.request(self.download_path(2))
        self.assertEqual(code, 200)
        self.assertIn("확정 버전: v2", markdown)
        self.assertIn("보완한 최종 제안서", markdown)
        self.assertEqual(archive, self.snapshot_path().read_bytes())

    def test_revision_failures_and_save_error_preserve_previous_result(self):
        for outcome in (RuntimeError("mock failure"), "", GOOD):
            self.seed()  # independent disposable project, no reset of an existing project
            self.prepare_revision()
            previous = copy.deepcopy(self.saved()["tasks"][1])
            original_save = app.save_project
            calls = []

            def fail_candidate(project):
                calls.append(1)
                if len(calls) == 2:
                    raise OSError("mock candidate save failure")
                original_save(project)

            with patch.object(app, "execute_task_mock", side_effect=[outcome]) as execute:
                if outcome == GOOD:
                    with patch.object(app, "save_project", side_effect=fail_candidate):
                        self.assertEqual(self.request("/quality/revise-once", {"task_id": "TASK-002"})[0], 400)
                else:
                    self.assertEqual(self.request("/quality/revise-once", {"task_id": "TASK-002"})[0], 400)
                self.assertEqual(self.request("/quality/revise-once", {"task_id": "TASK-002"})[0], 400)
                execute.assert_called_once()
            current = self.saved()["tasks"][1]
            for key in ("result", "result_revision", "review_status"):
                self.assertEqual(previous[key], current[key])

    def test_revision_concurrent_requests_and_download_return_409(self):
        self.prepare_revision()
        entered, release = threading.Event(), threading.Event()

        def delayed(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            return GOOD

        with patch.object(app, "execute_task_mock", side_effect=delayed) as execute, ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.request, "/quality/revise-once", {"task_id": "TASK-002"})
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(self.request("/quality/revise-once", {"task_id": "TASK-002"})[0], 409)
                self.assertEqual(self.request("/task/review", {"task_id": "TASK-002", "decision": "approve"})[0], 409)
                code, _, html = self.request(self.download_path())
                self.assertEqual(code, 409)
                self.assertIn("처리 중", html)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5)[0], 303)
            execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
