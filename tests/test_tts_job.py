import base64
from datetime import datetime
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from autonomous_company import CompanyError
from tts_job import TTSJob, sha
from video_production_company import prepare_staff_tts_job


class TTSJobTests(unittest.TestCase):
    def setup_job(self, root):
        reference = Path(root)/'A.wav'; reference.write_bytes(b'preserved reference fixture')
        job = prepare_staff_tts_job('가상 안내입니다.', reference, fictional=True)
        runner = TTSJob(Path(root)/'isolated-project'); runner.create(job)
        approval = dict(scope='tts_mock_once', job_hash=job['job_hash'],
            payload_sha256=job['payload_sha256'], requests=1, max_cost_usd=0)
        evidence = dict(simulation=True, free_tier=True, billing_enabled=False, key_bound=True,
            model=job['model'], region_supported=True, quota_requests=1, quota_output_tokens=1024,
            policy_reviewed=True, checked_at=datetime.now().astimezone().isoformat())
        return runner, job, approval, evidence

    def envelope(self, seconds=1, tokens=25, cost=0):
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\x10\x00'*(24000*seconds))
        return json.dumps(dict(status='completed', usage=dict(mock=True, output_tokens=tokens, cost_usd=cost),
            steps=[dict(type='model_output', content=[dict(type='audio', mime_type='audio/wav',
            data=base64.b64encode(output.getvalue()).decode())])])).encode()

    def test_success_exact_wire_audio_and_restart_duplicate(self):
        with tempfile.TemporaryDirectory() as root, patch('socket.socket.connect', side_effect=AssertionError('network')):
            runner, job, approval, evidence = self.setup_job(root)
            def send(endpoint, raw, timeout, limit):
                self.assertEqual(sha(raw), job['payload_sha256'])
                self.assertEqual(json.loads(raw)['input'][0]['content'][0]['text'], '가상 안내입니다.')
                self.assertTrue((runner.folder/'attempt.json').is_file())
                return self.envelope()
            transport = Mock(side_effect=send)
            result = runner.run_mock(approval, evidence, transport)
            self.assertEqual(result['audio_sha256'], sha((runner.folder/'B_MOCK_NOT_TTS.wav').read_bytes()))
            self.assertFalse(result['publish_ready']); self.assertEqual(result['quality'], 'unassessed')
            with self.assertRaises(FileExistsError): TTSJob(runner.folder).run_mock(approval, evidence, transport)
            self.assertEqual(transport.call_count, 1)

    def test_disabled_evidence_and_consent_never_send(self):
        for field, bad in [('free_tier', False), ('billing_enabled', True), ('quota_requests', 0),
                           ('quota_output_tokens', 0), ('region_supported', False), ('key_bound', False),
                           ('checked_at', '2020-01-01T00:00:00+09:00')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                runner, job, approval, evidence = self.setup_job(root); transport = Mock()
                with self.assertRaises(CompanyError): runner.execute(approval, evidence, transport)
                evidence[field] = bad
                with self.assertRaises(CompanyError): runner.run_mock(approval, evidence, transport)
                transport.assert_not_called(); self.assertFalse((runner.folder/'attempt.json').exists())
        with tempfile.TemporaryDirectory() as root:
            runner, job, approval, evidence = self.setup_job(root)
            approval['scope'] = 'manager_plan_once'
            with self.assertRaises(CompanyError): runner.run_mock(approval, evidence, Mock())

    def test_failure_timeout_limits_and_no_retry(self):
        for response in [TimeoutError('secret response'), self.envelope(tokens=1025), self.envelope(cost=1),
                         self.envelope(seconds=21), b'bad json', b'x'*2000001]:
            with self.subTest(response_type=type(response).__name__), tempfile.TemporaryDirectory() as root:
                runner, job, approval, evidence = self.setup_job(root)
                transport = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=response)
                with self.assertRaisesRegex(RuntimeError, '^tts_attempt_failed_no_retry$'):
                    runner.run_mock(approval, evidence, transport)
                with self.assertRaises(FileExistsError): runner.run_mock(approval, evidence, transport)
                self.assertEqual(transport.call_count, 1)
                self.assertNotIn('secret', (runner.folder/'result.json').read_text())

    def test_tamper_and_fictional_gate(self):
        with tempfile.TemporaryDirectory() as root:
            runner, job, approval, evidence = self.setup_job(root)
            payload = runner.folder/'payload.json'; payload.chmod(0o600); payload.write_bytes(b'{}')
            with self.assertRaises(CompanyError): runner.run_mock(approval, evidence, Mock())
            with self.assertRaises(CompanyError): prepare_staff_tts_job('private', Path(root)/'A.wav', fictional=False)
