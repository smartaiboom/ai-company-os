from datetime import datetime, timedelta
from email.message import Message
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor

from autonomous_company import CompanyError, now
from manager_plan_once import canonical_bytes
from tts_job import prepare_voice_job, sha
from tts_execution import TTSExecution, GeminiTTSAdapter, ENDPOINT
from tts_cli import main
from tests import test_tts_job as mock_fixtures

KEY = 'fake-test-key-no-real-credential'
TEXT = '실제 사용자 자료가 아닌 합성용 가상 테스트 대본입니다.'


class ExecutionTests(unittest.TestCase):
    def setup_scope(self, root, approve=True):
        self.enterContext(patch('tts_execution.SCRIPT_SHA', sha(TEXT.encode())))
        reference = Path(root)/'A.wav'; reference.write_bytes(b'fixture reference')
        job = prepare_voice_job(TEXT, reference, fictional=True)
        source = Path(root)/'source.json'; source.write_bytes(canonical_bytes(job))
        runner = TTSExecution(Path(root)/'production'); runner.create(source, 'owner-test-project')
        start = datetime.fromisoformat(now())
        evidence = dict(project='owner-test-project', model=job['model'],
            method='owner_aistudio_review_not_independent_verification', tier='Free', billing='disabled',
            model_access='available', region_supported=True, paid_fallback=False,
            remaining_requests=1, remaining_input_tokens=2048, remaining_output_tokens=1024,
            checked_at=start.isoformat(), expires_at=(start+timedelta(minutes=30)).isoformat(),
            evidence_sha256='a'*64, source_url='https://aistudio.google.com/',
            observation='Test fixture observation only; never an actual account confirmation.')
        if approve:
            runner.verify_key(KEY, KEY, evidence); review = runner.review(KEY)
            runner.approve(review['review_hash'], KEY, owner_confirmed=True, accept_google_data_policy=True)
        return runner, evidence

    def envelope(self):
        envelope = json.loads(mock_fixtures.TTSJobTests().envelope())
        envelope.update(object='interaction', model='gemini-3.8-flash-tts',
            usage=dict(total_input_tokens=100, total_output_tokens=25, total_tokens=125,
                total_thought_tokens=0, total_tool_use_tokens=0))
        return json.dumps(envelope).encode()

    def response(self, raw=None, length=None, status=200):
        response = Mock(); response.status = status
        response.headers = Message(); response.headers['Content-Type'] = 'application/json'
        if length is not None: response.headers['Content-Length'] = str(length)
        response.read.return_value = self.envelope() if raw is None else raw
        response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
        return response

    def test_real_wire_signed_success_and_duplicate(self):
        with tempfile.TemporaryDirectory() as root, patch('socket.socket.connect', side_effect=AssertionError('network')):
            runner, _ = self.setup_scope(root)
            def send(request, timeout):
                self.assertEqual(request.full_url, ENDPOINT); self.assertEqual(request.get_method(), 'POST')
                self.assertEqual(request.get_header('X-goog-api-key'), KEY); self.assertNotIn(KEY, request.data.decode())
                payload = json.loads(request.data)
                self.assertFalse(payload['store']); self.assertEqual(payload['generation_config']['max_output_tokens'], 1024)
                self.assertEqual(payload['input'][0]['content'][0]['text'], TEXT)
                self.assertTrue((runner.root/'attempt.json').exists()); self.assertEqual(timeout, 30)
                return self.response()
            with patch('tts_execution.TTS_EXECUTION_ENABLED', True), patch('tts_execution.send_once', side_effect=send) as transport:
                result = runner.execute(KEY)
                self.assertEqual(result['audio_sha256'], sha((runner.root/'B_gemini.wav').read_bytes()))
                self.assertFalse(result['publish_ready']); self.assertEqual(result['rights'], 'unverified')
                with self.assertRaises(FileExistsError): TTSExecution(runner.root).execute(KEY)
                self.assertEqual(transport.call_count, 1)
            for path in runner.root.iterdir():
                if path.name != '.operating-consent.key': self.assertNotIn(KEY.encode(), path.read_bytes())

    def test_disabled_unsigned_old_scope_and_key(self):
        with tempfile.TemporaryDirectory() as root:
            runner, _ = self.setup_scope(root)
            with patch('tts_execution.send_once') as send:
                with self.assertRaisesRegex(CompanyError, 'tts_execution_disabled'): runner.execute(KEY)
                with patch.dict('os.environ', TTS_EXECUTION_ENABLED='1', GEMINI_API_KEY=KEY):
                    with self.assertRaises(CompanyError): runner.execute(KEY)
                with patch('tts_execution.TTS_EXECUTION_ENABLED', True):
                    with self.assertRaises(CompanyError): runner.execute(KEY+'changed')
                    consent = runner.root/'consent.json'; value = json.loads(consent.read_bytes())
                    value['record']['scope'] = 'manager_plan_only'; consent.write_bytes(canonical_bytes(value))
                    with self.assertRaises(CompanyError): runner.execute(KEY)
                send.assert_not_called(); self.assertFalse((runner.root/'attempt.json').exists())

    def test_evidence_missing_quota_expiry_and_project_key(self):
        for field, value in [('tier', 'Paid'), ('billing', 'enabled'), ('model_access', 'unavailable'),
            ('region_supported', False), ('paid_fallback', True), ('remaining_requests', 0), ('remaining_input_tokens', 0),
            ('remaining_output_tokens', 0), ('evidence_sha256', ''), ('project', 'different'),
            ('checked_at', '2020-01-01T00:00:00+09:00')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                runner, evidence = self.setup_scope(root, approve=False); evidence[field] = value
                with self.assertRaises(CompanyError): runner.verify_key(KEY, KEY, evidence)
                self.assertFalse((runner.root/'account.json').exists())
        with tempfile.TemporaryDirectory() as root:
            runner, evidence = self.setup_scope(root, approve=False)
            with self.assertRaises(CompanyError): runner.verify_key(KEY, KEY+'other', evidence)
            with patch('tts_execution.TTS_EXECUTION_ENABLED', True):
                with self.assertRaises(CompanyError): runner.execute(KEY)

    def test_review_expiry_payload_tamper_and_exact_consent(self):
        with tempfile.TemporaryDirectory() as root:
            runner, _ = self.setup_scope(root)
            with self.assertRaises(CompanyError): runner.approve('old-hash', KEY, owner_confirmed=True, accept_google_data_policy=True)
            with self.assertRaises(CompanyError): runner.approve('anything', KEY, owner_confirmed=True)
            future = (datetime.fromisoformat(now())+timedelta(hours=2)).isoformat()
            with patch('tts_execution.now', return_value=future), patch('tts_execution.TTS_EXECUTION_ENABLED', True):
                with self.assertRaises(CompanyError): runner.execute(KEY)
            path = runner.root/'payload.json'; path.chmod(0o600); path.write_bytes(b'{}')
            with patch('tts_execution.TTS_EXECUTION_ENABLED', True):
                with self.assertRaises(CompanyError): runner.execute(KEY)
            self.assertFalse((runner.root/'attempt.json').exists())

    def test_failures_consumed_no_retry_and_no_raw_error(self):
        invalid = json.loads(self.envelope()); invalid['usage']['total_output_tokens'] = 1025
        wrong_mime = json.loads(self.envelope()); wrong_mime['steps'][0]['content'][0]['mime_type'] = 'audio/mp3'
        for error in [TimeoutError('secret'), HTTPError(ENDPOINT, 429, 'secret', None, None),
                      self.response(length=2000001), self.response(raw=b'x'*2000001),
                      self.response(raw=json.dumps(invalid).encode()), self.response(raw=json.dumps(wrong_mime).encode()),
                      self.response(raw=b'{"status":"incomplete"}'), self.response(raw=b'bad json')]:
            with self.subTest(kind=type(error).__name__), tempfile.TemporaryDirectory() as root:
                runner, _ = self.setup_scope(root)
                with patch('tts_execution.TTS_EXECUTION_ENABLED', True), patch('tts_execution.send_once') as send:
                    if isinstance(error, Exception): send.side_effect = error
                    else: send.return_value = error
                    with self.assertRaisesRegex(CompanyError, 'tts_attempt_failed_no_retry'): runner.execute(KEY)
                    with self.assertRaises(FileExistsError): runner.execute(KEY)
                    self.assertEqual(send.call_count, 1)
                self.assertNotIn('secret', (runner.root/'result.json').read_text())

    def test_interruption_and_concurrent_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            runner, _ = self.setup_scope(root)
            with patch('tts_execution.TTS_EXECUTION_ENABLED', True), patch('tts_execution.send_once', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt): runner.execute(KEY)
                with self.assertRaises(FileExistsError): TTSExecution(runner.root).execute(KEY)
                self.assertFalse((runner.root/'result.json').exists())
        with tempfile.TemporaryDirectory() as root:
            runner, _ = self.setup_scope(root)
            def attempt(_):
                try: return runner.execute(KEY)['status']
                except FileExistsError: return 'already_consumed'
            with patch('tts_execution.TTS_EXECUTION_ENABLED', True), patch('tts_execution.send_once', return_value=self.response()) as send:
                with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(attempt, range(2)))
                self.assertEqual(sorted(outcomes), ['already_consumed', 'audio_validated']); self.assertEqual(send.call_count, 1)

    def test_cli_non_tty_and_proxy_redirect_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            runner, _ = self.setup_scope(root)
            with patch('tts_cli.sys.stdin.isatty', return_value=False), patch('tts_cli.getpass.getpass') as prompt, patch('sys.stderr', new=io.StringIO()):
                self.assertEqual(main(['--root', str(runner.root), 'execute']), 1); prompt.assert_not_called()
        from goal_dialogue_live import send_once, NoRedirect
        with patch('goal_dialogue_live.build_opener') as opener:
            send_once(GeminiTTSAdapter.request(b'{}', KEY), 30)
            handlers = opener.call_args.args
            self.assertEqual(handlers[0].proxies, {}); self.assertIsInstance(handlers[1], NoRedirect)
            with self.assertRaises(CompanyError): handlers[1].redirect_request(None, None, 302, '', {}, 'https://other.test')
