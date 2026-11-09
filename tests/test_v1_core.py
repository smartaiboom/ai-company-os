"""V1 standalone offline smoke tests. Run: PYTHONPATH=src python -m unittest discover -s tests -v

No imports from phase1 or ai-company-os-phase1. No real AI connections.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autonomous_company import Company, CompanyError, MockEmployeeProvider, Store
from tests.support.autonomous_company_fixtures import FictionalModels


class V1StandaloneTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp) / "projects"
        self.store = Store(self.root)
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("network forbidden")))
        self.enterContext(patch("socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")))

    def create(self, model, **options):
        goal = "지역 도서관 이용 안내를 작성하세요" if model.domain == "library" else "소형 매장 재고 인수인계 안내를 작성하세요"
        project = self.store.create(goal, opt_in=True, **options)
        return project, Company(self.store, model.manager, model.employee)

    def test_two_domains_complete_and_preserve_outputs(self):
        for domain in ("library", "stock"):
            with self.subTest(domain=domain):
                model = FictionalModels(domain, revise=domain == "stock")
                project, company = self.create(model)
                outcome = company.run(project["id"])
                self.assertEqual(outcome["status"], "delivered")
                self.assertEqual(outcome["user_business_approval_requests"], 0)
                self.assertFalse(outcome["real_calls_allowed"])
                self.assertTrue(all(a["reserved_at"].endswith("+09:00") for a in outcome["attempts"]))
                self.assertEqual(len({x["role"] for x in outcome["assignments"]}), 2)
                self.assertTrue(any(x["event"] == "ai_manager_decision" for x in outcome["events"]))
                artifact = self.root / outcome["artifacts"]["final.md"]["path"]
                self.assertTrue(artifact.is_file())
                self.assertIn(outcome["final"]["content"], artifact.read_text(encoding="utf-8"))
                self.assertTrue(any(ctx["previous_results"] for phase, ctx in model.contexts if phase == "execute"))
                if domain == "stock":
                    self.assertEqual(outcome["assignments"][0]["revisions"], 1)
                count = len(model.calls)
                company.run(project["id"])
                self.assertEqual(len(model.calls), count)

    def test_bounded_failure_does_not_publish(self):
        for model, limits, expected in (
            (FictionalModels(unknown=True), {}, "manager_stopped"),
            (FictionalModels(always_revise=True), {}, "revision_limit"),
            (FictionalModels(), {"max_calls": 2}, "mock_budget_exhausted"),
            (FictionalModels(fail=True), {}, "mock_provider_failed"),
        ):
            with self.subTest(expected=expected):
                project, company = self.create(model, **limits)
                outcome = company.run(project["id"])
                self.assertEqual(outcome["status"], "stopped")
                self.assertEqual(outcome["reason_code"], expected)
                self.assertFalse(outcome["artifacts"])

    def test_interrupted_operation_does_not_auto_retry(self):
        model = FictionalModels()
        project, company = self.create(model)
        worker = MockEmployeeProvider(model.employee.name, lambda phase, context: (_ for _ in ()).throw(KeyboardInterrupt()))
        with self.assertRaises(KeyboardInterrupt):
            Company(self.store, model.manager, worker).run(project["id"])
        before = len(model.calls)
        outcome = company.run(project["id"])
        self.assertEqual(outcome["reason_code"], "uncertain_operation")
        self.assertEqual(len(model.calls), before)
        self.assertFalse(outcome["artifacts"])

    def test_no_unapproved_project(self):
        with self.assertRaises(CompanyError):
            self.store.create("목표")
        self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()
