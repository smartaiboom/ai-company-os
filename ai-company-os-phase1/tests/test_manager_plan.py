import unittest

from manager_plan import build_manager_plan


class ManagerPlanTests(unittest.TestCase):
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

        self.assertEqual(second["stages"][0]["name"], "要求사항 정리".replace("要求", "요구"))

    def test_empty_goal_is_rejected(self):
        with self.assertRaises(ValueError):
            build_manager_plan("   ", "time")


if __name__ == "__main__":
    unittest.main()
