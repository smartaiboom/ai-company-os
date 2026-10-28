import unittest

from app import mark_downstream_for_review


class DownstreamReviewTests(unittest.TestCase):
    def test_waiting_tasks_remain_waiting(self):
        project = {
            "tasks": [
                {"name": "선행 작업", "status": "완료"},
                {"name": "대기 작업", "status": "대기"},
                {"name": "다른 대기 작업", "status": "대기"},
            ]
        }

        affected = mark_downstream_for_review(project, 0, "선행 결과 변경")

        self.assertEqual(affected, [])
        self.assertEqual(project["tasks"][1]["status"], "대기")
        self.assertEqual(project["tasks"][2]["status"], "대기")
        self.assertNotIn("history", project)

    def test_in_progress_and_completed_tasks_are_flagged(self):
        project = {
            "tasks": [
                {"name": "선행 작업", "status": "완료"},
                {"name": "진행 중 작업", "status": "진행 중"},
                {"name": "완료 작업", "status": "완료"},
                {"name": "대기 작업", "status": "대기"},
            ]
        }

        affected = mark_downstream_for_review(project, 0, "선행 결과 변경")

        self.assertEqual(affected, ["진행 중 작업", "완료 작업"])
        self.assertEqual(project["tasks"][1]["status"], "재검토 필요")
        self.assertEqual(project["tasks"][2]["status"], "재검토 필요")
        self.assertEqual(project["tasks"][3]["status"], "대기")
        self.assertTrue(project["tasks"][1]["review_required"])
        self.assertTrue(project["tasks"][2]["review_required"])
        self.assertEqual(len(project["history"]), 1)


if __name__ == "__main__":
    unittest.main()
