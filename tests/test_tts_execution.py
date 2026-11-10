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


    def setup_chat(self, root):
        from autonomous_live import LiveStore
        from autonomous_company import digest
        repo = Path(root)/'repo'; (repo/'data/trial').mkdir(parents=True)
        runner, _ = self.setup_scope(repo/'data/trial', approve=False)
        document = repo/'approval.md'; document.write_text('explicit scoped chat approval fixture')
        self.enterContext(patch('tts_execution.REPO_ROOT', repo))
        self.enterContext(patch('tts_execution.CHAT_TRIAL_ROOT', runner.root))
        self.enterContext(patch('tts_execution.CHAT_APPROVAL', document))
        self.enterContext(patch('tts_execution.CHAT_APPROVAL_SHA', sha(document.read_bytes())))
        self.enterContext(patch('tts_execution.CHAT_PROJECT_SHA', sha(b'owner-test-project')))
        self.enterContext(patch('tts_execution.CHAT_PAYLOAD_SHA', sha((runner.root/'payload.json').read_bytes())))
        self.enterContext(patch('tts_execution.CHAT_REFERENCE_SHA', sha(b'fixture reference')))
        listing = repo/'data/gemini_tts_model_list/20261110T160007_KST/result.json'
        listing.parent.mkdir(parents=True)
        listing.write_bytes(canonical_bytes(dict(complete=True, requests=[dict(http_status=200)],
            models=[dict(name='models/gemini-3.8-flash-tts')])))
        previous = repo/'data/gemini_one_call_acceptance'; previous.mkdir()
        signer = LiveStore.__new__(LiveStore); signer.root = previous
        record = dict(project='Default Gemini Project', scope='historical-test',
            credential_binding=signer._sign(dict(scope='historical-test', credential=KEY), create=True))
        (previous/'dialogue-fixture.json').write_bytes(canonical_bytes(dict(acceptance=dict(
            verification=dict(record=record, signature=signer._sign(record))))))
        return runner, repo, document

    def test_chat_only_exact_unknown_quota_receipt_and_default_stays_disabled(self):
        from tts_execution import execute_chat_trial
        import tts_execution
        with tempfile.TemporaryDirectory() as root, patch('socket.socket.connect', side_effect=AssertionError('offline')):
            runner, repo, document = self.setup_chat(root)
            with patch('tts_execution.send_once', return_value=self.response()) as send:
                result = execute_chat_trial(runner, KEY)
                self.assertEqual(send.call_count, 1); self.assertFalse(result['publish_ready'])
                self.assertFalse(tts_execution.TTS_EXECUTION_ENABLED)
                receipt = json.loads((runner.root/'chat_approval_receipt.json').read_bytes())
                self.assertEqual(receipt['consent_source'], 'explicit_chat_user_approval_2026-11-10')
                self.assertEqual(receipt['quota_remaining'], 'unknown')
                self.assertFalse(receipt['independently_verified']); self.assertFalse(receipt['owner_hmac_signature'])
                self.assertFalse((runner.root/'consent.json').exists())
                with self.assertRaises(FileExistsError): execute_chat_trial(runner, KEY)
                with self.assertRaisesRegex(CompanyError, 'tts_execution_disabled'): runner.execute(KEY)
                self.assertEqual(send.call_count, 1)

    def test_chat_wrong_scope_document_credential_paid_or_prior_attempt_block(self):
        from tts_execution import execute_chat_trial
        for fault in ('document', 'key', 'paid', 'prior_attempt', 'project', 'payload', 'root'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as root:
                runner, repo, document = self.setup_chat(root)
                key = KEY
                if fault == 'document': document.write_text('changed approval')
                elif fault == 'key': key += 'changed'
                elif fault == 'paid':
                    (repo/'data/tts_paid').mkdir()
                    (repo/'data/tts_paid/account.json').write_text('{"record":{"evidence":{"billing":"enabled"}}}')
                elif fault == 'prior_attempt':
                    (repo/'data/tts_other').mkdir(); (repo/'data/tts_other/attempt.json').write_text('{}')
                elif fault == 'project': self.enterContext(patch('tts_execution.CHAT_PROJECT_SHA', '0'*64))
                elif fault == 'root': self.enterContext(patch('tts_execution.CHAT_TRIAL_ROOT', repo/'other'))
                elif fault == 'payload':
                    path = runner.root/'payload.json';path.chmod(0o600);path.write_bytes(b'{}')
                with patch('tts_execution.send_once') as send:
                    with self.assertRaises(CompanyError): execute_chat_trial(runner, key)
                    send.assert_not_called(); self.assertFalse((runner.root/'attempt.json').exists())

    def test_chat_http_failure_consumes_global_guard_without_retry(self):
        from tts_execution import execute_chat_trial
        for failure in (TimeoutError(), HTTPError(ENDPOINT, 400, 'private', None, None), HTTPError(ENDPOINT, 429, 'private', None, None)):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as root:
                runner, repo, document = self.setup_chat(root)
                with patch('tts_execution.send_once', side_effect=failure) as send:
                    with self.assertRaisesRegex(CompanyError, 'tts_attempt_failed_no_retry'): execute_chat_trial(runner, KEY)
                    self.assertTrue((runner.root.parent/'trial_attempt.json').exists())
                    self.assertTrue((runner.root/'attempt.json').exists())
                    with self.assertRaises(FileExistsError): execute_chat_trial(runner, KEY)
                    self.assertEqual(send.call_count, 1)
                    result = json.loads((runner.root/'result.json').read_bytes())
                    self.assertIn(result['error_category'], ('timeout', 'http_error'))
                    self.assertNotIn('private', json.dumps(result))

    def setup_148_chat(self, root):
        import tts_execution as execution
        from autonomous_company import digest

        source = Path(__file__).resolve().parents[1]
        document_name = 'docs/RUN_APPROVED_GEMINI_TTS_148_CHARS_20261111.md'
        approval = (source/document_name).read_bytes()
        narration = next(line for line in approval.decode().splitlines() if line.startswith('금요일 세 시.'))
        raw = canonical_bytes(dict(model='gemini-3.8-flash-tts', store=False,
            input=[dict(type='user_input', content=[dict(type='text', text=narration,
                annotations=[dict(type='speech_metadata', style=execution.NEXT_STYLE)])])],
            generation_config=dict(max_output_tokens=1024, speech_config=[dict(voice='Puck')]),
            response_format=dict(type='audio', mime_type='audio/wav', sample_rate=24000)))
        old_runner, repo, _ = self.setup_chat(root)
        approval_path = repo/document_name
        approval_path.parent.mkdir()
        approval_path.write_bytes(approval)
        selection = repo/'data/video_voice_selection/20261110_v1'
        selection.mkdir(parents=True)
        (selection/'next_payload_REVIEW_ONLY.json').write_bytes(raw)
        _, old_scope, _ = old_runner._load()
        listing = repo/'data/gemini_tts_model_list/20261110T160007_KST/result.json'
        consent = dict(scope_hash=digest(old_scope), account_evidence_source='owner_screenshot_free_tier',
            billing='owner_reported_not_linked', model_list_receipt_sha256=sha(listing.read_bytes()))
        old_runner._write('chat_approval_receipt.json', consent)
        old_runner._write('attempt.json', dict(scope_hash=digest(old_scope), consent_hash=digest(consent)))
        old_runner._write('result.json', dict(http_status=200, status='audio_validated'))
        (old_runner.root.parent/'trial_attempt.json').write_bytes(b'{}')
        return selection, approval_path, raw

    def test_148_chat_reserves_before_exact_send_and_decodes_21_seconds(self):
        import base64
        import wave
        from tts_execution import execute_148_char_chat_trial

        with tempfile.TemporaryDirectory() as root, patch('socket.socket.connect', side_effect=AssertionError('offline')):
            selection, _, raw = self.setup_148_chat(root)
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as audio:
                audio.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                audio.writeframes(bytes(21 * 24000 * 2))
            envelope = json.loads(self.envelope())
            envelope['steps'][0]['content'][0]['data'] = base64.b64encode(buf.getvalue()).decode()
            trial = selection/'next_trial'

            def respond(request, timeout):
                self.assertEqual(request.data, raw)
                for path in (trial/'attempt.json', selection/'next_trial_attempt.json'):
                    self.assertEqual(json.loads(path.read_bytes())['payload_sha256'], sha(raw))
                return self.response(json.dumps(envelope).encode())

            with patch('tts_execution.send_once', side_effect=respond) as send:
                result = execute_148_char_chat_trial(KEY)
                self.assertEqual(result['usage']['seconds'], 21)
                self.assertEqual((trial/'B_next_gemini.wav').read_bytes(), buf.getvalue())
                with self.assertRaises(FileExistsError):
                    execute_148_char_chat_trial(KEY)
                send.assert_called_once()
            receipt = json.loads((trial/'chat_approval_receipt.json').read_bytes())
            self.assertEqual(receipt['consent_source'], 'explicit_chat_user_approval_2026-11-11')
            self.assertFalse(receipt['owner_hmac_signature'])
            with self.assertRaisesRegex(CompanyError, 'tts_execution_disabled'):
                TTSExecution(trial).execute(KEY)

    def test_148_chat_blocks_invalid_evidence_and_consumes_oversize_response(self):
        from tts_execution import execute_148_char_chat_trial

        with tempfile.TemporaryDirectory() as root, patch('socket.socket.connect', side_effect=AssertionError('offline')):
            selection, approval, raw = self.setup_148_chat(root)
            payload = selection/'next_payload_REVIEW_ONLY.json'
            with patch('tts_execution.send_once') as send:
                payload.write_bytes(raw + b' ')
                with self.assertRaisesRegex(CompanyError, 'tts_148_payload_changed'):
                    execute_148_char_chat_trial(KEY)
                payload.write_bytes(raw)
                approved = approval.read_bytes()
                approval.write_bytes(approved + b' ')
                with self.assertRaisesRegex(CompanyError, 'tts_148_approval_changed'):
                    execute_148_char_chat_trial(KEY)
                approval.write_bytes(approved)
                with self.assertRaisesRegex(CompanyError, 'tts_chat_key_changed'):
                    execute_148_char_chat_trial(KEY + 'changed')
                account = selection/'account.json'
                account.write_text('{"billing_enabled":true}')
                with self.assertRaisesRegex(CompanyError, 'tts_chat_paid_account_evidence'):
                    execute_148_char_chat_trial(KEY)
                account.unlink()
                prior = selection/'previous_attempt.json'
                prior.write_text('{}')
                with self.assertRaisesRegex(CompanyError, 'tts_148_prior_attempt'):
                    execute_148_char_chat_trial(KEY)
                prior.unlink()
                send.assert_not_called()
                self.assertFalse((selection/'next_trial').exists())

                send.return_value = self.response(raw=b'x' * 2000001)
                with self.assertRaisesRegex(CompanyError, 'tts_attempt_failed_no_retry'):
                    execute_148_char_chat_trial(KEY)
                send.return_value.read.assert_called_once_with(2000001)
                result = json.loads((selection/'next_trial/result.json').read_bytes())
                self.assertEqual(result['validation_code'], 'tts_response_limit')
                with self.assertRaises(FileExistsError):
                    execute_148_char_chat_trial(KEY)
                send.assert_called_once()
