"""Focused, offline safety tests for rework manager quality follow-ups.

No model calls, network, live state, credentials, or stored user projects.
Run: PYTHONPATH=core:companies/video python -B -m unittest tests.test_rework_quality_followup_unit
"""
import json
import unittest
from unittest.mock import patch

from representative_rework import ReworkCompany
from video_mission_one import MissionOneCompany


class DummyStore:
    def __init__(self):
        self.saves = 0

    def save(self, _state):
        self.saves += 1


def model_review(*, action="accept", met=True, evidence="한 문장", check_status="met"):
    return {
        "result": {
            "action": action,
            "rationale": "검토 의견",
            "evidence": "대본 검토",
            "uncertainty": "실제 성과 미검증",
            "checks": [{
                "criterion_id": "fact",
                "status": check_status,
                "evidence": "근거",
                "source": "model_claim",
            }],
            "feedback": "근거 없는 주장을 수정하세요" if action == "revise" else "",
            "operation": None,
            "goal_review": {
                k: {"met": met, "evidence": evidence}
                for k in (
                    "goal_fit", "feedback_applied", "subject_story",
                    "concrete_hook", "claims_supported"
                )
            },
        }
    }


class QualityFollowupTests(unittest.TestCase):
    def setUp(self):
        self.company = object.__new__(ReworkCompany)
        self.company._review_content = json.dumps({"transcript": "한 문장\n두 번째 문장"}, ensure_ascii=False)
        self.company._review_task_id = "writer_001"
        self.company._quality_followup = None
        self.company.store = DummyStore()
        self.company._rework_state = {
            "assignments": [{
                "id": "writer_001", "role": "writer",
                "revisions": 0, "versions": [], "reviews": [],
            }],
            "limits": {"max_revisions_per_task": 1, "max_total_revisions": 1},
            "real_ai": {"attempts": [{"status": "completed", "http_status": 200}]},
        }

    def parse(self, payload):
        # Control only the generic role wire parser. Exercise the actual
        # ReworkCompany semantic decision branch and its persisted metadata.
        with patch("representative_rework.matches", return_value=True), patch.object(
            MissionOneCompany, "_parse_role_content",
            autospec=True,
            side_effect=lambda _self, raw, phase: json.loads(raw)["result"],
        ):
            return self.company._parse_role_content(json.dumps(payload, ensure_ascii=False), "review")

    def test_valid_accept_hands_off_without_quality_override(self):
        result = self.parse(model_review(evidence="한 문장"))
        self.assertEqual(result["action"], "accept")
        self.assertIsNone(self.company._quality_followup)
        self.assertEqual(self.company.store.saves, 0)

    def test_unmet_manager_accept_becomes_bounded_revision(self):
        result = self.parse(model_review(met=False))
        self.assertEqual(result["action"], "revise")
        self.assertIn("goal_fit", result["feedback"])
        self.assertIn("시스템 품질 검증", result["rationale"])
        self.assertEqual(self.company._quality_followup["original_action"], "accept")
        self.assertEqual(self.company._quality_followup["decision"], "revise")

    def test_missing_evidence_becomes_revision_instead_of_accept(self):
        result = self.parse(model_review(evidence="대본에 없는 내용"))
        self.assertEqual(result["action"], "revise")
        self.assertEqual(
            self.company._quality_followup["failed_checks"]["goal_fit"],
            "evidence_not_found",
        )

    def test_unmet_manager_check_cannot_be_accepted(self):
        result = self.parse(model_review(check_status="unmet"))
        self.assertEqual(result["action"], "revise")
        self.assertEqual(
            self.company._quality_followup["failed_checks"]["criterion:fact"],
            "criterion_not_met",
        )

    def test_revision_exhaustion_requires_representative_decision(self):
        self.company._rework_state["assignments"][0]["revisions"] = 1
        result = self.parse(model_review(met=False))
        self.assertEqual(result["action"], "stop")
        self.assertEqual(self.company._quality_followup["decision"], "stop")
        self.assertEqual(self.company._quality_followup["reason"], "manager_accept_conflicted_with_goal_review")

    def test_manager_revision_at_limit_ends_safely(self):
        self.company._rework_state["assignments"][0]["revisions"] = 1
        result = self.parse(model_review(action="revise", met=False))
        self.assertEqual(result["action"], "stop")
        self.assertEqual(self.company._quality_followup["reason"], "revision_limit_reached")

    def test_original_manager_revision_is_preserved_when_available(self):
        result = self.parse(model_review(action="revise", met=False))
        self.assertEqual(result["action"], "revise")
        self.assertIsNone(self.company._quality_followup)


if __name__ == "__main__":
    unittest.main()
