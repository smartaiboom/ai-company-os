"""M2 safety and durable limits: all AI transports are fake or forbidden."""

import copy
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import ai_safety as safety
import app
import execution_engine
from tests.real_ai_fixtures import approved_project
from tests import test_concurrent_execution_safety as handlers


class Response:
    def __init__(self, payload=None):
        self.body = json.dumps(payload or {"choices": [{"message": {"content": "모의 제공자 결과"}}]}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body[:size] if size >= 0 else self.body


class RealAISafetyBudgetTests(unittest.TestCase):
    post = handlers.ConcurrentExecutionSafetyTests.post

    def setUp(self):
        handlers.ConcurrentExecutionSafetyTests.setUp(self)
        self.project = approved_project(handlers.ConcurrentExecutionSafetyTests.project(self))
        self.project["plan"] = {"status": "approved"}
        for context in (
            patch('project_budget.KEY_PATH', self.projects / '.budget.key'),
            patch.object(app, "PROJECTS_DIR", self.projects),
            patch.object(app, "ARTIFACTS_DIR", self.projects / "artifacts"),
            patch.dict(os.environ, {"AI_ENGINE": "openai_compatible", "AI_MODEL": safety.MODEL,
                                   "AI_API_BASE_URL": safety.BASE_URL, "AI_REAL_REQUESTS_ENABLED": "1",
                                   "AI_API_KEY": "TEST_AUTH_NEVER_LOG"}, clear=True),
            patch("ai_safety.guarded_urlopen", side_effect=AssertionError("real network forbidden")),
            patch("ai_safety.build_opener", side_effect=AssertionError("real network forbidden")),
        ):
            context.start()
            self.addCleanup(context.stop)
        app.save_project(self.project)

    def saved(self):
        return app.load_project(self.project["id"])

    def payload(self):
        return json.dumps({"model": safety.MODEL, "max_tokens": 32, "messages": [{"role": "user", "content": "모의 업무"}]}).encode()

    def send(self, project, transport, **overrides):
        args = dict(model=safety.MODEL, base_url=safety.BASE_URL, body=self.payload(), api_key="TEST_AUTH_NEVER_LOG",
                    timeout=90, transport=transport, kind="task")
        return safety.request_json(project, **{**args, **overrides})

    def test_no_activation_or_consent_no_transport_or_budget_write(self):
        original = self.saved()
        for mutation in (
            lambda p: p.pop("real_ai"),
            lambda p: p["real_ai"].update(enabled=False),
            lambda p: p["real_ai"]["consent"].update(approved=False),
            lambda p: p.update(goal="not approved goal"),
        ):
            project = copy.deepcopy(original)
            mutation(project)
            with patch("execution_engine.urlopen") as transport, safety.request_scope(app.save_project):
                with self.assertRaises(ValueError):
                    self.send(project, transport)
                transport.assert_not_called()
        with patch.dict(os.environ, {"AI_REAL_REQUESTS_ENABLED": ""}), patch("execution_engine.urlopen") as transport:
            self.assertEqual(self.post("/workflow/run-real", enabled="1", approved="true")[0], 400)
            transport.assert_not_called()
        with patch.dict(os.environ, {"AI_ENGINE": "mock"}), patch("execution_engine.urlopen") as transport:
            self.assertEqual(self.post("/workflow/run-real")[0], 400)
            transport.assert_not_called()
        self.assertEqual(original, self.saved())

    def test_model_host_input_output_and_request_scope_checks(self):
        with patch("execution_engine.urlopen") as transport:
            for args in (
                {"model": "paid/model"}, {"model": ""}, {"base_url": "http://openrouter.ai/api/v1"},
                {"base_url": "https://openrouter.ai.attacker.invalid/api/v1"},
                {"base_url": "https://openrouter.ai/api/v1?redirect=bad"},
                {"base_url": "https://user@openrouter.ai/api/v1"},
                {"body": b"X" * (safety.MAX_INPUT_BYTES + 1)},
                {"body": json.dumps({"model": safety.MODEL, "max_tokens": 4097}).encode()},
                {"body": json.dumps({"model": "paid/model", "max_tokens": 1}).encode()},
            ):
                with self.subTest(args=list(args)), safety.request_scope(app.save_project), self.assertRaises(ValueError):
                    self.send(self.saved(), transport, **args)
            with self.assertRaises(ValueError):
                self.send(self.saved(), transport)
            transport.assert_not_called()
        self.assertEqual(self.saved()["real_ai"]["attempts"], [])

    def test_engine_model_mutation_is_rechecked_before_transmission(self):
        engine = execution_engine.OpenAICompatibleExecutionEngine()
        engine.model = "paid/model"
        with safety.request_scope(app.save_project), patch("execution_engine.urlopen") as transport:
            with self.assertRaisesRegex(ValueError, "openrouter/free"):
                engine.execute(self.saved(), {"id": "TASK-001", "name": "mock"})
            transport.assert_not_called()

    def test_reserve_before_transport_and_two_per_request_seven_total(self):
        def fake(request, **kwargs):
            reserved = self.saved()["real_ai"]["attempts"]
            self.assertEqual(reserved[-1]["status"], "reserved")
            self.assertTrue(reserved[-1]["reserved_at"].endswith("+09:00"))
            self.assertEqual(request.full_url, safety.BASE_URL + "/chat/completions")
            return Response()

        with patch("execution_engine.urlopen", side_effect=fake) as transport:
            for _ in range(3):
                with safety.request_scope(app.save_project):
                    self.send(self.saved(), transport)
                    self.send(self.saved(), transport)
                    with self.assertRaisesRegex(ValueError, "2회"):
                        self.send(self.saved(), transport)
            with safety.request_scope(app.save_project):
                self.send(self.saved(), transport)
                with self.assertRaisesRegex(ValueError, "소진"):
                    self.send(self.saved(), transport)
            self.assertEqual(transport.call_count, 7)
        self.assertEqual(len(self.saved()["real_ai"]["attempts"]), 7)

    def test_pending_reservation_survives_reload_and_blocks_restart(self):
        project = self.saved()
        project["real_ai"]["attempts"] = [{"id": "interrupted", "status": "reserved", "input_bytes": 1}]
        app.save_project(project)
        before = app.project_path(project["id"]).read_bytes()
        with safety.request_scope(app.save_project), patch("execution_engine.urlopen") as transport:
            with self.assertRaisesRegex(ValueError, "불명확"):
                self.send(self.saved(), transport)
            transport.assert_not_called()
        self.assertIn("미완료 AI 예약", app.real_ai_controls(self.saved()))
        self.assertEqual(before, app.project_path(project["id"]).read_bytes())

    def test_timeout_http_body_and_connection_errors_are_sanitized_and_consumed(self):
        for error in (TimeoutError("TEST_AUTH_NEVER_LOG"), URLError("TEST_AUTH_NEVER_LOG"),
                      HTTPError(safety.BASE_URL, 429, "TEST_AUTH_NEVER_LOG", {}, io.BytesIO(b"TEST_AUTH_NEVER_LOG"))):
            app.save_project(copy.deepcopy(self.project))
            with safety.request_scope(app.save_project), patch("execution_engine.urlopen", side_effect=error) as transport:
                with self.assertRaises(RuntimeError) as exc:
                    self.send(self.saved(), transport)
                transport.assert_called_once()
            self.assertNotIn("TEST_AUTH_NEVER_LOG", str(exc.exception))
            state = self.saved()["real_ai"]
            self.assertEqual(len(state["attempts"]), 1)
            self.assertEqual(state["attempts"][0]["status"], "failed")
            self.assertNotIn("TEST_AUTH_NEVER_LOG", json.dumps(state))
        with self.assertLogs("execution_engine", level="WARNING") as logs:
            execution_engine._log_response_diagnostics(
                {"finish_reason": "TEST_AUTH_NEVER_LOG"}, {"TEST_AUTH_NEVER_LOG": "private", "content": ""}, ""
            )
        self.assertNotIn("TEST_AUTH_NEVER_LOG", " ".join(logs.output))

    def test_reservation_write_failure_never_calls_transport(self):
        with safety.request_scope(lambda project: (_ for _ in ()).throw(OSError("mock storage error"))), \
             patch("execution_engine.urlopen") as transport:
            with self.assertRaises(OSError):
                self.send(self.saved(), transport)
            transport.assert_not_called()

    def test_response_bound_and_invalid_json_consume_one_attempt(self):
        for raw in (b"X" * (safety.MAX_RESPONSE_BYTES + 1), b"not json"):
            app.save_project(copy.deepcopy(self.project))
            response = Response()
            response.body = raw
            with safety.request_scope(app.save_project), patch("execution_engine.urlopen", return_value=response) as transport:
                with self.assertRaises(RuntimeError):
                    self.send(self.saved(), transport)
                transport.assert_called_once()
            self.assertEqual(self.saved()["real_ai"]["attempts"][0]["status"], "failed")

    def test_redirect_handler_does_not_follow_other_hosts(self):
        handler = safety.NoRedirect()
        self.assertIsNone(handler.redirect_request(Request(safety.BASE_URL), None, 302, "redirect", {}, "https://attacker.invalid"))

    def test_plan_and_two_roles_share_budget_and_approval_gates(self):
        stages = [
            {"name": "조사", "role": "시장 조사 담당", "inputs": [], "input_task_ids": [], "output": "조사 결과", "risk": "mock"},
            {"name": "기획", "role": "제품 기획 담당", "inputs": ["조사 결과"], "input_task_ids": ["TASK-001"], "output": "기획 결과", "risk": "mock"},
        ]
        project = self.saved()
        project["tasks"] = []
        app.save_project(project)
        plan_response = Response({"choices": [{"message": {"content": json.dumps({"stages": stages, "questions": [], "assumptions": []})}}]})
        with patch("manager_plan.urlopen", return_value=plan_response) as planner:
            self.assertEqual(self.post("/manager/plan")[0], 303)
            planner.assert_called_once()
        self.assertEqual(len(self.saved()["real_ai"]["attempts"]), 1)
        self.assertEqual(self.post("/manager/approve")[0], 303)
        with patch("execution_engine.urlopen", return_value=Response()) as transport:
            self.assertEqual(self.post("/workflow/run-real")[0], 303)
            self.assertEqual(self.saved()["tasks"][0]["review_status"], "pending")
            self.post("/workflow/run-real")
            transport.assert_called_once()
            self.assertEqual(self.post("/task/review", decision="approve")[0], 303)
            self.assertEqual(self.post("/workflow/run-real")[0], 303)
            self.assertEqual(transport.call_count, 2)
            payload = json.loads(transport.call_args.args[0].data)
            self.assertIn("TASK-001", payload["messages"][1]["content"])
        self.assertEqual(len(self.saved()["real_ai"]["attempts"]), 3)
        self.assertEqual([a["kind"] for a in self.saved()["real_ai"]["attempts"]], ["plan", "task", "task"])
        self.assertIn("사용/예약: 3회", app.real_ai_controls(self.saved()))

    def test_timeout_in_real_workflow_preserves_result_and_does_not_retry(self):
        with patch("execution_engine.urlopen", side_effect=TimeoutError("private")) as transport:
            self.assertEqual(self.post("/workflow/run-real")[0], 303)
            self.assertEqual(self.saved()["tasks"][0]["result"], "기존 결과")
            self.assertEqual(self.saved()["tasks"][0]["status"], "실행 실패")
            self.post("/workflow/run-real")
            transport.assert_called_once()
        self.assertEqual(len(self.saved()["real_ai"]["attempts"]), 1)

    def test_concurrent_real_request_returns_409_and_one_transport_call(self):
        def slow(*args, **kwargs):
            self.entered.set()
            if not self.release.wait(5):
                raise RuntimeError("test timeout")
            return Response()

        with patch("execution_engine.urlopen", side_effect=slow) as transport, ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.post, "/workflow/run-real")
            try:
                self.assertTrue(self.entered.wait(2))
                self.assertEqual(self.post("/workflow/run-real")[0], 409)
            finally:
                self.release.set()
            self.assertEqual(first.result(timeout=2)[0], 303)
            transport.assert_called_once()

    def test_real_start_runs_at_most_two_independent_tasks(self):
        project = self.saved()
        project["tasks"] = [
            {"id": f"TASK-{i:03d}", "name": "독립 업무", "role": "모의 역할", "status": "대기", "input_task_ids": []}
            for i in range(1, 4)
        ]
        app.save_project(project)
        with patch("execution_engine.urlopen", return_value=Response()) as transport:
            self.assertEqual(self.post("/workflow/run-real")[0], 303)
            self.assertEqual(transport.call_count, 2)
            self.assertEqual(self.saved()["tasks"][2]["status"], "대기")
            self.assertIn("상한", self.saved()["real_ai"]["stop_reason"])
            self.assertEqual(self.post("/workflow/run-real")[0], 303)
            self.assertEqual(transport.call_count, 3)
            self.assertEqual(self.saved()["tasks"][2]["review_status"], "pending")
