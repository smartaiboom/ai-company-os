"""Tests for task-ID based predecessor result delivery."""

import io
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

import app


class ExplicitWorkflowLinkTests(unittest.TestCase):
    PROJECT_ID = "explicit-workflow-test"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.temp_dir.name) / "projects"
        self.projects_dir.mkdir()
        self.project = {
            "id": self.PROJECT_ID,
            "name": "명시적 업무 연결 테스트",
            "goal": "시장 조사 결과를 바탕으로 제품을 기획하고 개발",
            "status": "active",
            "tasks": [
                {
                    "id": "TASK-001",
                    "name": "시장 조사",
                    "inputs": [],
                    "output": "시장 조사 보고서",
                    "status": "대기",
                    "input_task_ids": [],
                },
                {
                    "id": "TASK-002",
                    "name": "제품 기획",
                    "inputs": ["시장 조사 보고서"],
                    "output": "제품 기획서",
                    "status": "대기",
                    "input_task_ids": ["TASK-001"],
                },
                {
                    "id": "TASK-003",
                    "name": "개발",
                    "inputs": ["제품 기획서"],
                    "output": "개발 결과물",
                    "status": "대기",
                    "input_task_ids": ["TASK-002"],
                },
            ],
            "history": [],
        }
        self.addCleanup(self.temp_dir.cleanup)

    def _post_execute(self, task_id):
        body = urlencode({
            "id": self.PROJECT_ID,
            "task_id": task_id,
        }).encode("utf-8")
        handler = app.Handler.__new__(app.Handler)
        handler.path = "/task/execute"
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        with patch.object(app.Handler, "redirect", autospec=True) as redirect:
            with patch.object(app.Handler, "send_html", autospec=True) as send_html:
                app.Handler.do_POST(handler)
        return redirect, send_html

    def test_market_research_product_planning_and_development_share_results_by_task_id(self):
        outputs = [
            "시장 조사 결과: 사용자는 반복 업무 자동화를 원한다.",
            "제품 기획 결과: 조사 결과를 반영한 간단한 자동화 도구.",
            "개발 결과: 기획서에 정의한 기능을 구현한다.",
        ]
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(self.project)
            with patch.object(app, "execute_task", side_effect=outputs) as execute:
                for task_id in ("TASK-001", "TASK-002", "TASK-003"):
                    redirect, send_html = self._post_execute(task_id)
                    redirect.assert_called_once()
                    send_html.assert_not_called()

            saved = app.load_project(self.PROJECT_ID)

        self.assertEqual(
            [task["input_task_ids"] for task in saved["tasks"]],
            [[], ["TASK-001"], ["TASK-002"]],
        )
        self.assertEqual(execute.call_args_list[0].kwargs["previous_results"], [])
        product_inputs = execute.call_args_list[1].kwargs["previous_results"]
        self.assertEqual(len(product_inputs), 1)
        self.assertEqual(product_inputs[0]["task_id"], "TASK-001")
        self.assertEqual(product_inputs[0]["result"], outputs[0])
        development_inputs = execute.call_args_list[2].kwargs["previous_results"]
        self.assertEqual(len(development_inputs), 1)
        self.assertEqual(development_inputs[0]["task_id"], "TASK-002")
        self.assertEqual(development_inputs[0]["result"], outputs[1])
        self.assertEqual([task["result"] for task in saved["tasks"]], outputs)

    def test_required_predecessor_without_result_blocks_execution(self):
        for missing_result in (None, "   "):
            with self.subTest(result=missing_result):
                project = {
                    **self.project,
                    "tasks": [dict(task) for task in self.project["tasks"]],
                }
                predecessor = project["tasks"][0]
                predecessor["status"] = "완료"
                if missing_result is not None:
                    predecessor["result"] = missing_result
                dependent = project["tasks"][1]

                with patch.object(app, "PROJECTS_DIR", self.projects_dir):
                    app.save_project(project)
                    with patch.object(app, "execute_task") as execute:
                        redirect, send_html = self._post_execute("TASK-002")

                execute.assert_not_called()
                redirect.assert_not_called()
                send_html.assert_called_once()
                self.assertIn("필수 선행 업무", send_html.call_args.args[1])
                self.assertIn("결과가 비어 있어 실행을 중단했습니다", send_html.call_args.args[1])
                self.assertEqual(dependent["status"], "대기")


if __name__ == "__main__":
    unittest.main()
