"""Loopback-only runner checks with fake transport and isolated JSON state."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch
from urllib.request import build_opener, ProxyHandler

import ai_safety as safety
from tests.real_ai_fixtures import approved_project
from tests.support.m4_runner import ObservedServer


class RunnerShutdownTests(unittest.TestCase):
    def scenario(self, *, fail=False, client_timeout=False, unfinished=False):
        entered, release = threading.Event(), threading.Event()
        errors = []
        project = approved_project({'id': 'fictional-runner', 'goal': 'fictional mock goal'})
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'AI_REAL_REQUESTS_ENABLED': '1', 'AI_ENGINE': 'openai_compatible'}, clear=True), \
             patch('ai_safety.build_opener', side_effect=AssertionError('external network forbidden')):
            path = Path(temp) / 'fictional.json'
            def persist(p):
                tmp = path.with_suffix('.tmp')
                tmp.write_text(json.dumps(p))
                tmp.replace(path)
            def fake_transport(*args, **kwargs):
                server.record('transport_started')
                entered.set()
                if not release.wait(3):
                    raise AssertionError('mock release missing')
                server.record('transport_finished')
                if fail:
                    raise TimeoutError('private mock detail')
                class Response:
                    def __enter__(self): return self
                    def __exit__(self, *args): pass
                    def read(self, size): return b'{}'
                return Response()
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args): pass
                def do_GET(self):
                    try:
                        with safety.request_scope(persist):
                            safety.request_json(project, model=safety.MODEL,
                                base_url=safety.BASE_URL, body=json.dumps({
                                    'model':safety.MODEL, 'max_tokens':1}).encode(),
                                api_key='', timeout=45, transport=fake_transport, kind='plan')
                    except RuntimeError:
                        pass
                    self.send_response(200)
                    self.send_header('Content-Length', '0')
                    self.end_headers()
            server = ObservedServer(Handler)
            def client():
                try:
                    with build_opener(ProxyHandler({})).open(
                        'http://127.0.0.1:'+str(server.server_port),
                        timeout=0.05 if client_timeout else 2) as r:
                        r.read()
                except TimeoutError:
                    server.record('client_timeout')
                except Exception as exc:
                    errors.append(type(exc).__name__)
            caller = threading.Thread(target=client)
            caller.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertFalse(server.requests_finished())
                if client_timeout:
                    caller.join(1)
                    self.assertFalse(caller.is_alive())
                    self.assertIn('client_timeout', [e['phase'] for e in server.events])
                if unfinished:
                    before = path.read_bytes()
                    self.assertFalse(server.stop_and_observe(0.01))
                    self.assertFalse(server.requests_finished())
                    self.assertEqual(before, path.read_bytes())
                    self.assertEqual(json.loads(before)['real_ai']['attempts'][0]['status'], 'reserved')
                    self.assertTrue(any(w.is_alive() for w in server.workers))
                    self.assertTrue(all(not w.daemon for w in server.workers))
                release.set()
                self.assertTrue(server.stop_and_observe(1))
                self.assertTrue(server.requests_finished())
                caller.join(1)
                self.assertFalse(caller.is_alive())
                self.assertEqual(errors, [])
                attempts = json.loads(path.read_text())['real_ai']['attempts']
                self.assertEqual(len(attempts), 1)
                self.assertEqual(attempts[0]['status'], 'failed' if fail else 'completed')
                self.assertTrue(all(e['at'].endswith('+09:00') for e in server.events))
                self.assertEqual([e['elapsed'] for e in server.events],
                                 sorted(e['elapsed'] for e in server.events))
                self.assertNotIn('private', json.dumps(server.events))
                self.assertTrue(all(set(e)=={'phase','at','elapsed'} for e in server.events))
            finally:
                release.set()
                server.stop_and_observe(2)
                caller.join(2)

    def test_normal_completion(self): self.scenario()
    def test_transport_failure(self): self.scenario(fail=True)
    def test_client_times_out_before_worker(self): self.scenario(client_timeout=True)
    def test_shutdown_deadline_preserves_pending_reservation(self):
        self.scenario(client_timeout=True, unfinished=True)
