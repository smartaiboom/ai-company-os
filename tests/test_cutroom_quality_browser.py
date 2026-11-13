"""Real Chromium browser UI test, fully isolated from production data and Gemini.

Run:
  PYTHONPATH=core:companies/video python -B -m unittest tests.test_cutroom_quality_browser -v

Requires a preinstalled Playwright Python package and Chromium browser. The
test never installs dependencies, uses a temporary HTTP server on port 0, and
mocks every /api/ request. Never points at the user's port 8000.
"""
from copy import deepcopy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import json
import unittest
from urllib.parse import urlsplit

ASSETS = Path(__file__).resolve().parents[1] / "companies/video/studio"
PID = "company-" + "a" * 32


def fixture():
    report = dict(
        decision="stop", reason="revision_limit_reached",
        failed_checks={"goal_fit": "not_met", "subject_story": "not_met"},
        evidence={"goal_fit": "합성 대본 문장"},
        feedback="게임 공략 대신 반전 장면 이야기로 수정하세요.",
    )
    progress = dict(
        title="대표 판단 필요 · AI 품질 검토 보고",
        current="대본 검토", actor="AI 관리자", updated_at=None,
        cards=[], message="대표 검토가 필요합니다",
        next_action="수정 또는 보류 지시를 선택하세요",
        counts=dict(attempts=3, transport_started=3, http_ok=3,
                    server_validated=2, failed=0), ledger=[],
        quality_report=report,
    )
    rework = dict(
        status="stopped", job="fixture-job", error="manager_stopped",
        settings={"ready": True}, recovery=None, new_attempt=None,
        history=[], feedback="기존 대표 피드백", proposal=None,
        job_status="stopped", attempts=3, replan=None, reviews=[],
        progress=progress, quality_report_hash="fixture-report-hash",
        quality_script="가상 게임 대본", quality_decision=None,
    )
    detail = dict(
        id=PID, store="workspace", readonly=False, simulation=False,
        goal="가상 게임 쇼츠", updated_at="2026-11-13T10:00:00+09:00",
        stage="plan_revision", audience="초보 시청자", budget=None,
        budget_setup=None, mission=None, rework=rework, jobs=[],
        flow=dict(
            plan_versions=[], video_versions=[], decisions=[], events=[],
            constraints=dict(language="한국어", platform="YouTube Shorts",
                             duration_seconds=25, notes="가상 검증"),
        ),
    )
    return detail


class AssetHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ASSETS), **kwargs)

    def log_message(self, _format, *_args):
        pass

    def do_POST(self):
        self.send_error(403, "All API calls must be intercepted by browser fixture")

    def do_GET(self):
        if urlsplit(self.path).path.startswith("/api/"):
            self.send_error(403, "Real API forbidden")
            return
        return super().do_GET()


class CutroomQualityBrowserTests(unittest.TestCase):
    def test_ceo_quality_report_clicks_and_fresh_prepare_are_isolated(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            self.fail("브라우저 테스트 전용 Playwright Python 패키지가 설치되어 있지 않습니다. "
                      "설치 없이 진행하려면 실행 결과를 알려주세요. 원인: " + str(exc))

        server = ThreadingHTTPServer(("127.0.0.1", 0), AssetHandler)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                try:
                    context = browser.new_context()
                    page = context.new_page()
                    state = {"detail": fixture(), "writes": []}

                    def handle_api(route):
                        request = route.request
                        url = urlsplit(request.url).path
                        if request.method == "GET" and url == "/api/studio":
                            payload = {"projects": [], "deferred": [], "token": "fixture-token"}
                        elif request.method == "GET" and url == f"/api/project/workspace/{PID}":
                            payload = deepcopy(state["detail"])
                        elif request.method == "POST" and url.endswith("/rework-quality-decide"):
                            body = request.post_data_json
                            self.assertEqual(body["job"], "fixture-job")
                            self.assertEqual(body["report_hash"], "fixture-report-hash")
                            self.assertEqual(body["action"], "request_revision")
                            self.assertIn("게임 이야기", body["feedback"])
                            state["writes"].append((url, body))
                            state["detail"]["rework"]["quality_decision"] = dict(
                                action="request_revision", feedback=body["feedback"])
                            payload = {"ok": True}
                        elif request.method == "POST" and url.endswith("/rework-quality-prepare"):
                            body = request.post_data_json
                            self.assertEqual(body["previous_job"], "fixture-job")
                            self.assertEqual(body["account_project"], "gen-lang-client-0938732315")
                            self.assertEqual(body["confirm_free_account"], True)
                            state["writes"].append((url, body))
                            state["detail"]["rework"].update(
                                status="pending", progress=None,
                                quality_decision=None, proposal=None,
                            )
                            payload = {"ok": True}
                        else:
                            raise AssertionError("Unexpected API request: " + request.method + " " + url)
                        route.fulfill(status=200, content_type="application/json",
                                      body=json.dumps(payload, ensure_ascii=False))

                    page.route("**/api/**", handle_api)
                    page.goto(f"http://127.0.0.1:{server.server_port}/#project/workspace/{PID}")
                    page.locator('[data-action="rework-quality-revise"]').wait_for()
                    self.assertTrue(page.get_by_text("AI 관리자 품질 보고").count() >= 1)
                    self.assertTrue(page.get_by_text("goal_fit").count() >= 1)
                    self.assertEqual(len(state["writes"]), 0)
                    page.locator('[data-action="rework-quality-revise"]').click()
                    page.locator('#dialog textarea[name="feedback"]').fill("게임 이야기로 다시 작성")
                    page.locator('#dialog button[type="submit"]').click()
                    page.locator('[data-action="rework-quality-prepare"]').wait_for()
                    self.assertEqual([path.rsplit("/", 1)[-1] for path, _ in state["writes"]],
                                     ["rework-quality-decide"])
                    self.assertEqual(page.locator('[data-action="rework-run"]').count(), 0)
                    page.locator('[data-action="rework-quality-prepare"]').click()
                    page.locator('#dialog input[name="free"]').check()
                    page.locator('#dialog button[type="submit"]').click()
                    page.locator('[data-action="rework-consent"]').wait_for()
                    self.assertEqual([path.rsplit("/", 1)[-1] for path, _ in state["writes"]],
                                     ["rework-quality-decide", "rework-quality-prepare"])
                    self.assertEqual(page.locator('[data-action="rework-run"]').count(), 0)
                    context.close()
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
