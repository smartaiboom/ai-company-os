import os
import unittest
from unittest.mock import patch

from manager_plan import _parse_plan_content, build_manager_plan, validate_stages


class ManagerPlanTests(unittest.TestCase):
    def setUp(self):
        self.mock_engine = patch.dict(os.environ, {"AI_ENGINE": "mock"})
        self.mock_engine.start()
        self.addCleanup(self.mock_engine.stop)

    def test_plan_uses_goal_and_waits_for_approval(self):
        plan = build_manager_plan("Build a useful AI product", "2026-10-28T10:00:00+09:00")

        self.assertEqual(plan["goal"], "Build a useful AI product")
        self.assertEqual(plan["status"], "pending_approval")
        self.assertEqual(plan["created_at"], "2026-10-28T10:00:00+09:00")
        self.assertTrue(plan["stages"])
        self.assertTrue(all(stage.get("name") and stage.get("role") for stage in plan["stages"]))

    def test_each_plan_gets_independent_stage_data(self):
        first = build_manager_plan("Goal one", "time-one")
        first["stages"][0]["name"] = "Changed only in this plan"
        second = build_manager_plan("Goal two", "time-two")

        self.assertEqual(second["stages"][0]["name"], "요구사항 정리")

    def test_empty_goal_is_rejected(self):
        with self.assertRaises(ValueError):
            build_manager_plan("   ", "time")

    def test_stage_validation_accepts_variable_number_of_tasks(self):
        stages = [
            {"name": "시장 조사", "role": "시장 조사 담당", "inputs": ["프로젝트 목표"], "output": "시장 조사 결과", "risk": "자료 확인 필요"},
            {"name": "제품 기획", "role": "제품 기획 담당", "inputs": ["시장 조사 결과"], "output": "제품 기획안", "risk": "고객 검증 필요"},
            {"name": "최종 검토", "role": "품질 검토 담당", "inputs": ["제품 기획안"], "output": "검토 보고서", "risk": "추가 검토 가능"},
        ]
        self.assertEqual(validate_stages(stages), stages)

    def test_stage_validation_rejects_too_few_tasks(self):
        with self.assertRaises(ValueError):
            validate_stages([
                {"name": "하나", "role": "AI 관리자", "inputs": [], "output": "결과", "risk": "없음"}
            ])

    def test_stage_validation_rejects_missing_fields(self):
        with self.assertRaises(ValueError):
            validate_stages([
                {"name": "작업 1", "role": "AI 관리자", "inputs": [], "output": "결과", "risk": "없음"},
                {"name": "작업 2", "role": "개발 담당", "inputs": [], "output": "", "risk": "없음"},
            ])

    def test_parse_plan_content_accepts_plain_json(self):
        self.assertEqual(_parse_plan_content('{"stages": []}'), {"stages": []})

    def test_parse_plan_content_accepts_fenced_json(self):
        self.assertEqual(_parse_plan_content('Here is the plan:\n```json\n{"stages": []}\n```'), {"stages": []})

    def test_parse_plan_content_accepts_text_blocks(self):
        self.assertEqual(
            _parse_plan_content([{"type": "text", "text": '{"stages": []}'}]),
            {"stages": []},
        )


if __name__ == "__main__":
    unittest.main()
