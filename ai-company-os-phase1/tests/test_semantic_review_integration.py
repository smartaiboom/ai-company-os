"""M3 transport fixtures only: no provider network or real credentials."""

import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

import ai_safety
import app
import manager_plan
import semantic_review
from tests.real_ai_fixtures import approved_project
from tests.test_real_ai_safety_budget import Response
from tests import test_concurrent_execution_safety as handlers
from tests import test_mock_workflow_http_integration as http

GOAL = "소규모 매장 재고 업무 개선 제안"
CRITERION = "재고 부족 확인 절차와 담당자가 명시되어야 한다"


def response(content):
    return Response({"choices": [{"finish_reason": "stop", "message": {"content": content}}]})


class SemanticIntegrationTests(unittest.TestCase):
    post = handlers.ConcurrentExecutionSafetyTests.post

    def setUp(self):
        handlers.ConcurrentExecutionSafetyTests.setUp(self)
        self.project_id = "concurrent-test"
        self.employee_payloads = []
        self.semantic_payloads = []
        self.verdict = "changes_needed"
        for context in (
            patch.object(app, "PROJECTS_DIR", self.projects),
            patch.object(app, "ARTIFACTS_DIR", self.projects / "artifacts"),
            patch.dict(os.environ, {"AI_ENGINE": "openai_compatible", "AI_MODEL": ai_safety.MODEL,
                                   "AI_API_BASE_URL": ai_safety.BASE_URL, "AI_REAL_REQUESTS_ENABLED": "1",
                                   "AI_API_KEY": "FICTIONAL_TEST_KEY"}, clear=True),
            patch("ai_safety.build_opener", side_effect=AssertionError("external network forbidden")),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.employee = patch("execution_engine.urlopen", side_effect=self.employee_response).start()
        self.addCleanup(patch.stopall)
        self.semantic = patch("semantic_review.urlopen", side_effect=self.review_response).start()
        self.planner = patch("manager_plan.urlopen", return_value=response(json.dumps({
            "stages": [{"input_task_ids": [], **stage} for stage in manager_plan.STARTER_STAGES], "questions": [], "assumptions": []}, ensure_ascii=False))).start()
        self.seed()

    def seed(self):
        app.save_project(approved_project({"id": self.project_id, "name": "재고 개선", "goal": GOAL,
                                           "tasks": [], "history": [], "status": "active"}))

    def saved(self):
        return app.load_project(self.project_id)

    def employee_response(self, request, **kwargs):
        payload = json.loads(request.data)
        self.employee_payloads.append(payload)
        text = payload["messages"][1]["content"]
        self.assertIn(GOAL, text)
        self.assertNotIn("AI Company OS", text)
        return response("재고 개선 제안\n매장 담당자가 매일 마감 전 부족 품목을 확인한다. 실제 매장 검증은 미실시.")

    def review_response(self, request, **kwargs):
        payload = json.loads(request.data)
        self.semantic_payloads.append(payload)
        data = json.loads(payload["messages"][1]["content"])
        self.assertIn("재고", data["target_result"])
        result = self.contract(data["binding"], self.verdict)
        return response(json.dumps(result, ensure_ascii=False))

    def contract(self, binding, verdict="changes_needed"):
        return {"schema_version": 1, "binding": binding, "verdict": verdict,
                "checks": [{"criterion": CRITERION, "status": {"pass": "met", "changes_needed": "unmet", "inconclusive": "unknown"}[verdict],
                            "evidence": "제출된 재고 절차에 담당자 연결 근거를 대조함",
                            "risk": "실제 매장 확인은 안 됨", "suggestion": "마감 담당자와 부족 확인 절차를 함께 적으세요",
                            "source": "model_claim"}]}

    def ok(self, path, **fields):
        code, body = self.post(path, project_id=self.project_id, **fields)
        self.assertEqual(code, 303, body)

    def approve(self, task_id):
        self.ok("/task/review", task_id=task_id, decision="approve")

    def prepare(self):
        self.ok("/manager/plan")
        self.ok("/manager/approve")
        self.ok("/semantic/configure", target_task_id="TASK-002", reviewer_task_id="TASK-003", criteria=CRITERION)
        for task_id in ("TASK-001", "TASK-002"):
            self.ok("/task/execute", task_id=task_id)
            self.approve(task_id)

    def review(self):
        self.ok("/semantic/review")

    def decision(self, decision="approve"):
        self.ok("/semantic/revision-decision", decision=decision,
                binding_hash=app._digest(app.semantic_binding(self.saved())))

    def revise_and_reapprove(self):
        self.decision()
        self.ok("/task/execute", task_id="TASK-002")
        self.approve("TASK-002")

    def test_goal_to_seven_calls_final_json_markdown_and_preserved_archive(self):
        self.prepare()
        project = self.saved()
        project["tasks"][1]["quality_revision_once"] = {"phase": "reserved", "operation_id": "old-mock-reservation"}
        app.save_project(project)
        before = copy.deepcopy(self.saved()["tasks"][1])
        self.review()
        self.assertEqual(self.saved()["tasks"][1], before)  # No automatic approval withdrawal.
        self.assertEqual(self.post("/task/execute", task_id="TASK-002")[0], 400)
        self.decision()
        baseline = self.saved()
        self.assertEqual(baseline["tasks"][1]["result"], before["result"])
        self.assertEqual(baseline["semantic"]["revision"]["previous_approval"]["review_status"], "approved")
        self.assertEqual(baseline["tasks"][1]["review_status"], "changes_requested")
        self.assertEqual(self.post("/semantic/review")[0], 400)
        self.ok("/task/execute", task_id="TASK-002")
        self.assertIn("마감 담당자", self.employee_payloads[-1]["messages"][1]["content"])
        self.assertEqual(self.saved()["tasks"][1]["result_revision"], 2)
        self.assertEqual(self.post("/semantic/review")[0], 400)
        self.approve("TASK-002")
        self.verdict = "pass"
        self.review()
        self.assertEqual(self.saved()["semantic"]["review"]["binding"]["result_revision"], 2)
        self.approve("TASK-003")
        self.ok("/task/execute", task_id="TASK-004")
        self.assertEqual(self.saved()["tasks"][-1]["review_status"], "pending")
        self.approve("TASK-004")
        project = self.saved()
        snapshot = app.load_confirmed_snapshot(project)
        self.assertEqual(len(project["real_ai"]["attempts"]), 7)
        self.assertEqual([a["kind"] for a in project["real_ai"]["attempts"]],
                         ["plan", "task", "task", "semantic_review", "task", "semantic_review", "task"])
        self.assertEqual(project["tasks"][1]["role"], "콘텐츠 제작 담당")
        self.assertEqual(project["tasks"][1]["quality_revision_once"], before["quality_revision_once"])
        self.assertIn(GOAL, json.loads(self.planner.call_args.args[0].data)["messages"][1]["content"])
        self.assertIn("TASK-002", self.semantic_payloads[-1]["messages"][1]["content"])
        self.assertIn("pass", json.dumps(snapshot["evidence"]["semantic"]))
        self.assertIn(GOAL, app.confirmed_markdown(snapshot))
        self.assertNotIn("FICTIONAL_TEST_KEY", json.dumps(snapshot))
        archive = app.ARTIFACTS_DIR / self.project_id / "final_reports" / "v000001.json"
        old_bytes = archive.read_bytes()
        self.assertEqual(self.post("/task/execute", task_id="TASK-002")[0], 400)
        self.assertEqual(self.post("/semantic/review")[0], 400)
        self.assertEqual(self.post("/semantic/configure", criteria="overwrite")[0], 400)
        self.assertEqual(archive.read_bytes(), old_bytes)

    def test_pass_and_inconclusive_do_not_grant_revision(self):
        for verdict in ("pass", "inconclusive"):
            with self.subTest(verdict=verdict):
                self.seed()
                self.prepare()
                self.verdict = verdict
                self.review()
                self.assertEqual(self.post("/semantic/revision-decision", decision="approve",
                                           binding_hash=app._digest(app.semantic_binding(self.saved())))[0], 400)
                if verdict == "inconclusive":
                    self.assertEqual(self.post("/task/review", task_id="TASK-003", decision="approve")[0], 400)
                    self.assertEqual(self.post("/task/execute", task_id="TASK-004")[0], 400)
                self.assertEqual(self.post("/semantic/review")[0], 400)

    def test_strict_contract_stale_and_reasoning_only_are_not_pass(self):
        self.prepare()
        binding = app.semantic_binding(self.saved())
        good = self.contract(binding, "pass")
        for change in (
            {"verdict": "invalid"}, {"verdict": "changes_needed"}, {"binding": {**binding, "result_revision": 0}},
            {"extra": True}, {"checks": []}, {"schema_version": True},
            {"binding": {**binding, "result_revision": True}}, {"verdict": []},
            {"checks": [{**good["checks"][0], "source": "verified_fact"}]},
            {"checks": [{**good["checks"][0], "evidence": ""}]},
        ):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                semantic_review.validate({**good, **change}, binding, [CRITERION])
        for content in ("", "not JSON", json.dumps({**good, "binding": {}}), '{"verdict":"pass","verdict":"pass"}'):
            project = self.saved()
            project["semantic"]["reviews"] = []
            project["tasks"][2]["status"] = "대기"
            app.save_project(project)
            with patch("semantic_review.urlopen", return_value=response(content)):
                self.assertEqual(self.post("/semantic/review")[0], 400)
            self.assertNotIn("review", self.saved()["semantic"])
            self.assertEqual(self.post("/semantic/review")[0], 400)

    def test_reasoning_only_timeout_and_reservation_failure_stop_review(self):
        self.prepare()
        baseline = self.saved()
        failures = [TimeoutError(), Response({"choices": [{"finish_reason": "stop", "message": {
            "reasoning": json.dumps(self.contract(app.semantic_binding(baseline), "pass"))}}]})]
        for failure in failures:
            app.save_project(copy.deepcopy(baseline))
            with patch("semantic_review.urlopen", side_effect=[failure]) as transport:
                self.assertEqual(self.post("/semantic/review")[0], 400)
                self.assertEqual(self.post("/semantic/review")[0], 400)
                self.assertEqual(transport.call_count, 1)
            self.assertEqual(self.saved()["tasks"][1], baseline["tasks"][1])
            self.assertEqual(len(self.saved()["real_ai"]["attempts"]), 4)
        app.save_project(baseline)
        with patch.object(app, "save_project", side_effect=OSError("fixture write failure")), patch("semantic_review.urlopen") as transport:
            self.assertEqual(self.post("/semantic/review")[0], 400)
            transport.assert_not_called()
        self.assertEqual(self.saved(), baseline)

    def test_reevaluation_inconclusive_and_insufficient_revision_budget_stop(self):
        self.prepare()
        self.review()
        baseline = self.saved()
        project = copy.deepcopy(baseline)
        project["real_ai"]["limit"] = 5
        app.save_project(project)
        self.assertEqual(self.post("/semantic/revision-decision", decision="approve",
                                   binding_hash=app._digest(app.semantic_binding(project)))[0], 400)
        self.assertEqual(self.saved()["tasks"][1]["review_status"], "approved")
        app.save_project(baseline)
        self.revise_and_reapprove()
        self.verdict = "inconclusive"
        self.review()
        self.assertEqual(self.post("/semantic/review")[0], 400)
        self.assertEqual(self.post("/task/execute", task_id="TASK-002")[0], 400)
        self.assertEqual(self.post("/task/execute", task_id="TASK-004")[0], 400)
        self.assertEqual(self.post("/task/review", task_id="TASK-003", decision="approve")[0], 400)
        self.assertEqual(len(self.saved()["real_ai"]["attempts"]), 6)
        self.assertEqual(self.saved()["tasks"][1]["result_revision"], 2)

    def test_rejection_and_direct_route_bypass_are_blocked(self):
        self.prepare()
        self.review()
        baseline = self.saved()["tasks"][1]
        self.decision("reject")
        self.assertEqual(self.saved()["tasks"][1], baseline)
        for path, fields in (
            ("/task/update", {"task_id": "TASK-002", "status": "진행 중"}),
            ("/task/execute", {"task_id": "TASK-002"}),
            ("/task/execute", {"task_id": "TASK-003"}),
            ("/task/review", {"task_id": "TASK-002", "decision": "request_changes", "feedback": "bypass"}),
            ("/quality/revise-once", {"task_id": "TASK-002"}),
            ("/semantic/revision-decision", {"decision": "approve", "binding_hash": app._digest(app.semantic_binding(self.saved()))}),
        ):
            self.assertEqual(self.post(path, **fields)[0], 400, path)
        self.assertEqual(len(self.saved()["real_ai"]["attempts"]), 4)

    def test_stale_result_and_context_prevent_revision_approval(self):
        self.prepare()
        self.review()
        original = self.saved()
        for mutate in (lambda p: p["tasks"][1].update(result="changed"),
                       lambda p: p["tasks"][1].update(result_revision=3),
                       lambda p: p["semantic"].update(criteria=["changed"]),
                       lambda p: p["tasks"][2].update(output="changed")):
            project = copy.deepcopy(original)
            mutate(project)
            app.save_project(project)
            self.assertEqual(self.post("/semantic/revision-decision", decision="approve",
                                       binding_hash=app._digest(original["semantic"]["review"]["binding"]))[0], 400)
            self.assertEqual(self.saved()["tasks"][1]["review_status"], "approved")

    def test_failure_empty_revision_and_reservation_failure_preserve_results(self):
        self.prepare()
        self.review()
        self.decision()
        baseline = self.saved()
        for effect in (TimeoutError(), response("")):
            app.save_project(copy.deepcopy(baseline))
            with patch("execution_engine.urlopen", side_effect=[effect]) as transport:
                self.assertEqual(self.post("/task/execute", task_id="TASK-002")[0], 400)
                self.assertEqual(self.post("/task/execute", task_id="TASK-002")[0], 400)
                self.assertEqual(transport.call_count, 1)
            saved = self.saved()
            self.assertEqual(saved["tasks"][1]["result"], baseline["tasks"][1]["result"])
            self.assertEqual(saved["tasks"][1]["result_revision"], 1)
            self.assertEqual(len(saved["real_ai"]["attempts"]), 5)
        app.save_project(baseline)
        with patch.object(app, "save_project", side_effect=OSError("fixture write failure")), patch("execution_engine.urlopen") as transport:
            self.assertEqual(self.post("/task/execute", task_id="TASK-002")[0], 400)
            transport.assert_not_called()
        self.assertEqual(self.saved(), baseline)

    def test_missing_consent_budget_and_duplicate_semantic_review(self):
        self.prepare()
        baseline = self.saved()
        with patch.dict(os.environ, {"AI_REAL_REQUESTS_ENABLED": ""}):
            self.assertEqual(self.post("/semantic/review", approved="true")[0], 400)
        self.assertEqual(self.saved(), baseline)
        project = copy.deepcopy(baseline)
        project["real_ai"]["limit"] = 3
        app.save_project(project)
        self.assertEqual(self.post("/semantic/review")[0], 400)
        app.save_project(baseline)
        def slow(request, **kwargs):
            self.entered.set()
            if not self.release.wait(5):
                raise RuntimeError("test release timeout")
            return self.review_response(request, **kwargs)
        with patch("semantic_review.urlopen", side_effect=slow) as transport, ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.post, "/semantic/review")
            try:
                self.assertTrue(self.entered.wait(2))
                self.assertEqual(self.post("/semantic/review")[0], 409)
                self.assertEqual(self.post("/task/review", task_id="TASK-002", decision="approve")[0], 409)
            finally:
                self.release.set()
            self.assertEqual(first.result(timeout=2)[0], 303)
            self.assertEqual(transport.call_count, 1)


class SemanticHTTPTests(SemanticIntegrationTests):
    """Run the same scenarios through HTTP, including actual attachment GET."""

    request = http.MockWorkflowHTTPTests.request

    def setUp(self):
        # The shared fixture starts a loopback server and isolated directories only.
        http.MockWorkflowHTTPTests.setUp(self)
        self.projects = app.PROJECTS_DIR
        SemanticIntegrationTests.setUp(self)

    def seed(self, approved=True):
        self.project_id = "concurrent-test"
        self.PROJECT_ID = self.project_id
        app.save_project(approved_project({"id": self.project_id, "name": "재고 개선", "goal": GOAL,
                                           "tasks": [], "history": [], "status": "active"}))

    def post(self, path="/task/execute", project_id="concurrent-test", **fields):
        code, _, body = self.request(path, fields)
        return code, body

    def test_goal_to_seven_calls_final_json_markdown_and_preserved_archive(self):
        super().test_goal_to_seven_calls_final_json_markdown_and_preserved_archive()
        before = app.project_path(self.project_id).read_bytes()
        code, headers, body = self.request(f"/report/{self.project_id}/download/v000001.md")
        self.assertEqual(code, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn(GOAL, body)
        self.assertIn("model_claim", body)
        snapshot = app.load_confirmed_snapshot(self.saved())
        self.assertEqual(body, app.confirmed_markdown(snapshot))
        code, headers, body = self.request(f"/report/{self.project_id}/download/v000001.json")
        self.assertEqual(code, 200)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(json.loads(body), snapshot)
        self.assertEqual(self.request(f"/report/{self.project_id}/download/v000002.json")[0], 409)
        self.assertEqual(self.request(f"/report/{self.project_id}/download/v01.json")[0], 400)
        self.assertEqual(app.project_path(self.project_id).read_bytes(), before)
        code, _, html = self.request(f"/project/{self.project_id}")
        self.assertEqual(code, 200)
        self.assertIn("남은 API 예산 0회", html)
