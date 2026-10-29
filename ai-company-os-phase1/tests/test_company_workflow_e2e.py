"""End-to-end mock coverage for planning through final report persistence."""

import io
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

import app
import execution_engine
import manager_plan


class CompanyWorkflowEndToEndTests(unittest.TestCase):
    PROJECT_ID = "company-workflow-e2e"
    GOAL = "초보자를 위한 간단한 할 일 관리 프로그램 기획"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.temp_dir.name) / "projects"
        self.projects_dir.mkdir()
        self.engine_env = patch.dict(os.environ, {"AI_ENGINE": "mock"}, clear=True)
        self.engine_env.start()
        self.addCleanup(self.engine_env.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def _post(self, path, form):
        body = urlencode({"id": self.PROJECT_ID, **form}).encode("utf-8")
        handler = app.Handler.__new__(app.Handler)
        handler.path = path
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        with patch.object(app.Handler, "redirect", autospec=True) as redirect:
            with patch.object(app.Handler, "send_html", autospec=True) as send_html:
                app.Handler.do_POST(handler)
        return redirect, send_html

    def test_plan_approval_execution_review_revision_and_final_report(self):
        project = {
            "id": self.PROJECT_ID,
            "name": "전체 업무 흐름 통합 테스트",
            "goal": self.GOAL,
            "status": "active",
            "tasks": [],
            "artifacts": [],
            "history": [],
        }
        with patch.object(app, "PROJECTS_DIR", self.projects_dir), \
             patch.object(manager_plan, "urlopen", side_effect=AssertionError("network call forbidden")) as planner_network, \
             patch.object(execution_engine, "urlopen", side_effect=AssertionError("network call forbidden")) as execution_network:
            app.save_project(project)

            redirect, error = self._post("/manager/plan", {})
            redirect.assert_called_once()
            error.assert_not_called()
            planned = app.load_project(self.PROJECT_ID)
            self.assertEqual(planned["plan"]["status"], "pending_approval")
            self.assertEqual(len(planned["plan"]["stages"]), 4)
            self.assertEqual(planned["manager_goal"], self.GOAL)

            redirect, error = self._post("/manager/approve", {})
            redirect.assert_called_once()
            error.assert_not_called()
            approved = app.load_project(self.PROJECT_ID)
            self.assertEqual(approved["plan"]["status"], "approved")
            self.assertEqual(len(approved["tasks"]), 4)
            self.assertEqual([task["name"] for task in approved["tasks"]], [
                "요구사항 정리", "작업 초안 작성", "검토 및 수정", "최종 보고",
            ])

            for task_index, task in enumerate(approved["tasks"]):
                redirect, error = self._post("/task/execute", {"task_id": task["id"]})
                redirect.assert_called_once()
                error.assert_not_called()
                saved = app.load_project(self.PROJECT_ID)
                completed = next(item for item in saved["tasks"] if item["id"] == task["id"])
                self.assertEqual(completed["status"], "완료")
                self.assertTrue(completed["result"])
                if task_index < len(approved["tasks"]) - 1:
                    redirect, error = self._post("/task/review", {
                        "task_id": task["id"],
                        "decision": "approve",
                    })
                    redirect.assert_called_once()
                    error.assert_not_called()

            completed = app.load_project(self.PROJECT_ID)
            quality_review = completed["tasks"][2]["result"]
            final_report = completed["tasks"][3]["result"]
            self.assertIn("요구사항 충족 여부: 검토 필요", quality_review)
            self.assertIn("수정 제안:", quality_review)
            self.assertIn("작업 초안 작성", quality_review)
            self.assertIn("최종 결과: 검토 및 수정 작업의 결과를 확인했습니다.", final_report)
            self.assertIn("추가 검토가 필요합니다", final_report)
            self.assertTrue(any(event["event"] == "task_execution_succeeded" for event in completed["history"]))

            # Changing an upstream result must mark completed review/report tasks stale.
            redirect, error = self._post("/task/update", {
                "task_id": "TASK-002",
                "status": "완료",
                "result": "수정된 할 일 프로그램 초안 v2",
            })
            redirect.assert_called_once()
            error.assert_not_called()
            revised = app.load_project(self.PROJECT_ID)
            self.assertEqual(revised["tasks"][2]["status"], "재검토 필요")
            self.assertTrue(revised["tasks"][2]["review_required"])
            self.assertEqual(revised["tasks"][3]["status"], "재검토 필요")
            self.assertEqual(revised["tasks"][1]["review_status"], "pending")

            # 수동 결과 변경은 기존 성공 기록과 분리되므로 새 실행 후에 승인한다.
            with patch.object(app, "execute_task", return_value="수정된 할 일 프로그램 초안 v2"):
                redirect, error = self._post("/task/execute", {"task_id": "TASK-002"})
            redirect.assert_called_once()
            error.assert_not_called()

            redirect, error = self._post("/task/review", {
                "task_id": "TASK-002",
                "decision": "approve",
            })
            redirect.assert_called_once()
            error.assert_not_called()

            redirect, error = self._post("/task/execute", {"task_id": "TASK-003"})
            redirect.assert_called_once()
            error.assert_not_called()
            rerun_review = app.load_project(self.PROJECT_ID)
            self.assertEqual(rerun_review["tasks"][2]["review_status"], "pending")
            redirect, error = self._post("/task/review", {
                "task_id": "TASK-003",
                "decision": "approve",
            })
            redirect.assert_called_once()
            error.assert_not_called()
            redirect, error = self._post("/task/execute", {"task_id": "TASK-004"})
            redirect.assert_called_once()
            error.assert_not_called()
            final_state = app.load_project(self.PROJECT_ID)
            self.assertTrue(all(task["status"] == "완료" for task in final_state["tasks"]))
            self.assertTrue(all(not task.get("review_required") for task in final_state["tasks"]))
            self.assertIn("수정된 할 일 프로그램 초안 v2", final_state["tasks"][2]["result"])
            self.assertIn("최종 결과: 검토 및 수정 작업의 결과를 확인했습니다.", final_state["tasks"][3]["result"])
            self.assertTrue(any(event["event"] == "downstream_review_required" for event in final_state["history"]))
            planner_network.assert_not_called()
            execution_network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
