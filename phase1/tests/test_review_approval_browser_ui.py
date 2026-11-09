"""Real Chromium coverage for the review approval UI and processing flow."""

import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import app

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:  # Keep the normal unittest suite usable without browser extras.
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "install requirements-browser-test.txt to enable Chromium tests")
class ReviewApprovalBrowserUITests(unittest.TestCase):
    PROJECT_ID = "browser-review-gate"

    def test_review_actions_show_modal_prevent_duplicate_and_restore_scroll(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            projects_dir = root / "projects"
            artifacts_dir = root / "artifacts"
            projects_dir.mkdir()
            artifacts_dir.mkdir()

            tasks = [
                {
                    "id": f"TASK-{index:03d}",
                    "name": f"앞쪽 업무 {index}",
                    "role": "모의 담당자",
                    "inputs": [],
                    "output": "앞쪽 결과",
                    "status": "대기",
                }
                for index in range(1, 11)
            ]
            tasks.extend([
                {
                    "id": "TASK-011",
                    "name": "시장 조사",
                    "role": "조사 담당",
                    "inputs": [],
                    "output": "시장 조사 결과",
                    "status": "완료",
                    "result": "브라우저 테스트용 조사 결과",
                    "review_status": "pending",
                },
                {
                    "id": "TASK-012",
                    "name": "제품 기획",
                    "role": "기획 담당",
                    "inputs": ["시장 조사 결과"],
                    "input_task_ids": ["TASK-011"],
                    "output": "제품 기획안",
                    "status": "대기",
                },
            ])
            project = {
                "id": self.PROJECT_ID,
                "name": "브라우저 검토 게이트 테스트",
                "goal": "브라우저 검토 흐름 확인",
                "status": "active",
                "plan": {"status": "approved", "goal": "브라우저 검토 흐름 확인", "stages": []},
                "tasks": tasks,
                "history": [{
                    "event": "task_execution_succeeded",
                    "details": "TASK-011: 작업 실행 성공 (실행 엔진: mock)",
                }],
            }

            first_review_started = threading.Event()
            release_first_review = threading.Event()
            request_count = {"review": 0}

            class DelayedReviewHandler(app.Handler):
                def do_POST(self):
                    if self.path == "/task/review":
                        request_count["review"] += 1
                        if request_count["review"] == 1:
                            first_review_started.set()
                            if not release_first_review.wait(timeout=10):
                                return
                    super().do_POST()

                def log_message(self, format, *args):
                    pass

            with patch.object(app, "PROJECTS_DIR", projects_dir), \
                 patch.object(app, "ARTIFACTS_DIR", artifacts_dir), \
                 patch.object(app, "execute_task", side_effect=AssertionError("review must not run an executor")):
                app.save_project(project)
                server = ThreadingHTTPServer(("127.0.0.1", 0), DelayedReviewHandler)
                server_thread = threading.Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                self.addCleanup(server.server_close)
                self.addCleanup(server.shutdown)
                self.addCleanup(server_thread.join, 5)
                url = f"http://127.0.0.1:{server.server_port}/project/{self.PROJECT_ID}"

                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    try:
                        page = browser.new_page(viewport={"width": 1200, "height": 720})
                        page.goto(url, wait_until="domcontentloaded")

                        row = page.locator("#task-TASK-011")
                        self.assertTrue(row.is_visible())
                        self.assertTrue(row.get_by_text("업무 결과 검토: 검토 승인 대기").is_visible())
                        approve_form = row.locator("form[action='/task/review']").first
                        self.assertEqual(approve_form.locator("input[name='task_id']").input_value(), "TASK-011")

                        row.scroll_into_view_if_needed()
                        page.evaluate("window.scrollBy(0, 120)")
                        page.wait_for_timeout(100)
                        before_scroll = page.evaluate("window.scrollY")
                        self.assertGreater(before_scroll, 0)

                        approve_button = approve_form.locator("button[type='submit']")
                        approve_button.click()
                        self.assertTrue(first_review_started.wait(timeout=5), "review POST did not reach the isolated server")
                        page.wait_for_function(
                            "document.querySelector('#task-TASK-011 form[action=\\'/task/review\\'] button').disabled",
                            timeout=5000,
                        )

                        modal = page.locator("#processing-modal")
                        self.assertTrue(modal.is_visible())
                        self.assertTrue(modal.locator(".processing-spinner").is_visible())
                        self.assertTrue(page.locator("#page-content").evaluate("el => el.inert"))
                        self.assertEqual(page.locator("#page-content").get_attribute("aria-busy"), "true")
                        self.assertEqual(page.locator("body").evaluate("el => el.style.overflow"), "hidden")
                        self.assertTrue(approve_button.is_disabled())
                        self.assertEqual(approve_button.inner_text(), "승인 중...")
                        modal_box = modal.bounding_box()
                        self.assertEqual(modal_box["x"], 0)
                        self.assertEqual(modal_box["y"], 0)
                        self.assertEqual(modal_box["width"], 1200)
                        self.assertEqual(modal_box["height"], 720)

                        approve_form.dispatch_event("submit", {"bubbles": True, "cancelable": True})
                        self.assertEqual(request_count["review"], 1, "a second submit must not send another request")

                        with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
                            release_first_review.set()
                        self.assertTrue(row.get_by_text("업무 결과 검토: 검토 승인됨").is_visible())
                        self.assertFalse(modal.is_visible())
                        self.assertFalse(page.locator("#page-content").evaluate("el => el.inert"))
                        self.assertEqual(page.locator("body").evaluate("el => el.style.overflow"), "")
                        restored = row.bounding_box()
                        center_delta = abs((restored["y"] + restored["height"] / 2) - 360)
                        self.assertLess(center_delta, 60)
                        self.assertIsNone(page.evaluate("sessionStorage.getItem('ai-company-os:scroll-restore')"))

                        saved = app.load_project(self.PROJECT_ID)
                        source = next(task for task in saved["tasks"] if task["id"] == "TASK-011")
                        self.assertEqual(source["review_status"], app.REVIEW_APPROVED)

                        source["review_status"] = app.REVIEW_PENDING
                        source.pop("reviewed_at", None)
                        source.pop("reviewed_by", None)
                        app.save_project(saved)
                        page.reload(wait_until="domcontentloaded")
                        self.assertTrue(row.get_by_text("업무 결과 검토: 검토 승인 대기").is_visible())

                        changes_form = row.locator("form[action='/task/review']").nth(1)
                        changes_form.locator("textarea[name='feedback']").fill("시장 규모 근거를 보완해 주세요.")
                        with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
                            changes_form.get_by_role("button", name="수정 요청").click()

                        self.assertTrue(row.get_by_text("업무 결과 검토: 수정 요청됨").is_visible())
                        self.assertTrue(row.get_by_text("시장 규모 근거를 보완해 주세요.").is_visible())
                        saved = app.load_project(self.PROJECT_ID)
                        source = next(task for task in saved["tasks"] if task["id"] == "TASK-011")
                        self.assertEqual(source["review_status"], app.REVIEW_CHANGES_REQUESTED)
                        self.assertEqual(source["review_feedback"], "시장 규모 근거를 보완해 주세요.")
                        self.assertEqual(request_count["review"], 2)
                    finally:
                        browser.close()


if __name__ == "__main__":
    unittest.main()
