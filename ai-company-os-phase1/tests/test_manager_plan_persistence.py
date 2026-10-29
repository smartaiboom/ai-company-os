import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

import app


class FakeAPIResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


class ManagerPlanPersistenceTests(unittest.TestCase):
    PROJECT_ID = "plan-persistence-test"
    GOAL = "초보자를 위한 간단한 할 일 관리 프로그램 기획"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.temp_dir.name) / "projects"
        self.projects_dir.mkdir()
        self.project = {
            "id": self.PROJECT_ID,
            "name": "계획 저장 테스트",
            "goal": self.GOAL,
            "status": "active",
            "tasks": [],
            "history": [],
        }
        self.env = patch.dict(os.environ, {
            "AI_ENGINE": "openai_compatible",
            "AI_API_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "openrouter/free",
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def _post_manager_plan(self, manager_goal=None):
        form = {"id": self.PROJECT_ID}
        if manager_goal is not None:
            form["manager_goal"] = manager_goal
        body = urlencode(form).encode("utf-8")
        handler = app.Handler.__new__(app.Handler)
        handler.path = "/manager/plan"
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()

        with patch.object(app.Handler, "redirect", autospec=True) as redirect:
            with patch.object(app.Handler, "send_html", autospec=True) as send_html:
                app.Handler.do_POST(handler)
        return handler, redirect, send_html

    @staticmethod
    def _valid_plan_response():
        stages = [
            {
                "name": "요구사항 정리",
                "role": "AI 관리자",
                "inputs": ["프로젝트 목표"],
                "output": "목표와 성공 기준",
                "risk": "요구사항 추가 확인 필요",
            },
            {
                "name": "화면 및 기능 기획",
                "role": "제품 기획 담당",
                "inputs": ["목표와 성공 기준"],
                "output": "간단한 할 일 관리 프로그램 기획서",
                "risk": "사용성 확인 필요",
            },
        ]
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "stages": stages,
                        "questions": [],
                        "assumptions": [],
                    }, ensure_ascii=False)
                }
            }]
        }

    def test_valid_mock_api_plan_is_saved_through_manager_route(self):
        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(dict(self.project))
            with patch("manager_plan.urlopen", return_value=FakeAPIResponse(
                self._valid_plan_response()
            )) as mocked_urlopen:
                _, redirect, send_html = self._post_manager_plan(self.GOAL)

            saved = app.load_project(self.PROJECT_ID)
            mocked_urlopen.assert_called_once()
            redirect.assert_called_once_with(
                unittest.mock.ANY,
                f"/project/{self.PROJECT_ID}",
            )
            send_html.assert_not_called()

        self.assertEqual(saved["manager_goal"], self.GOAL)
        self.assertEqual(saved["plan"]["goal"], self.GOAL)
        self.assertEqual(saved["plan"]["status"], "pending_approval")
        self.assertEqual(
            [stage["name"] for stage in saved["plan"]["stages"]],
            ["요구사항 정리", "화면 및 기능 기획"],
        )
        self.assertEqual(saved["history"][-1]["event"], "plan_created")

    def test_invalid_mock_api_plan_is_not_saved(self):
        invalid_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "stages": [{
                            "name": "한 단계뿐인 잘못된 계획",
                            "role": "AI 관리자",
                            "inputs": [],
                            "output": "결과",
                            "risk": "없음",
                        }],
                        "questions": [],
                        "assumptions": [],
                    }, ensure_ascii=False)
                }
            }]
        }

        with patch.object(app, "PROJECTS_DIR", self.projects_dir):
            app.save_project(dict(self.project))
            project_path = self.projects_dir / f"{self.PROJECT_ID}.json"
            before = project_path.read_bytes()
            with patch("manager_plan.urlopen", return_value=FakeAPIResponse(
                invalid_response
            )) as mocked_urlopen:
                with patch.object(app, "save_project", wraps=app.save_project) as save_project:
                    _, redirect, send_html = self._post_manager_plan(self.GOAL)

            mocked_urlopen.assert_called_once()
            save_project.assert_not_called()
            redirect.assert_not_called()
            send_html.assert_called_once()
            self.assertEqual(send_html.call_args.args[2], 400)
            self.assertIn("2개 이상 10개 이하", send_html.call_args.args[1])
            self.assertEqual(project_path.read_bytes(), before)
            saved = app.load_project(self.PROJECT_ID)

        self.assertNotIn("plan", saved)
        self.assertNotIn("manager_goal", saved)


if __name__ == "__main__":
    unittest.main()
