import json
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

    def test_non_free_model_is_rejected_before_plan_api_request(self):
        env = {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "some-provider/some-model",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("manager_plan.urlopen") as mocked_urlopen:
                with self.assertRaisesRegex(ValueError, "openrouter/free"):
                    build_manager_plan("test goal", "time")
                mocked_urlopen.assert_not_called()

    def test_missing_model_is_rejected_before_plan_api_request(self):
        env = {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("manager_plan.urlopen") as mocked_urlopen:
                with self.assertRaisesRegex(ValueError, "openrouter/free"):
                    build_manager_plan("test goal", "time")
                mocked_urlopen.assert_not_called()

    def test_api_plan_accepts_nested_tasks_and_singular_input_response(self):
        stages = [
            {
                "task_name": "요구사항 정리",
                "role": "AI 관리자",
                "input": "프로젝트 목표",
                "deliverable": "목표 및 성공 기준",
                "risk": "요구사항 확인 필요",
            },
            {
                "task_name": "초안 작성",
                "role": "기획 담당",
                "input": "목표 및 성공 기준",
                "deliverable": "초안",
                "risk": "사용자 검토 필요",
            },
        ]
        response_data = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "plan": {"tasks": stages},
                        "questions": [],
                        "assumptions": [],
                    }, ensure_ascii=False)
                }
            }]
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return json.dumps(response_data).encode("utf-8")

        env = {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "openrouter/free",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("manager_plan.urlopen", return_value=FakeResponse()) as mocked_urlopen:
                plan = build_manager_plan("test goal", "time")

        self.assertEqual([stage["name"] for stage in plan["stages"]], ["요구사항 정리", "초안 작성"])
        self.assertEqual(plan["stages"][0]["inputs"], ["프로젝트 목표"])
        self.assertEqual(plan["stages"][1]["output"], "초안")
        mocked_urlopen.assert_called_once()

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
