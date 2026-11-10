"""Independent signed TTS execution boundary. No live calls are enabled by default."""
import base64
from copy import deepcopy
from datetime import datetime, timedelta
import hmac
import io
import json
import os
from pathlib import Path
import re
import wave
from urllib.request import Request

from autonomous_company import require, digest, now, CompanyError
from autonomous_live import LiveStore
from goal_dialogue_live import send_once
from manager_plan_once import canonical_bytes
from local_artifacts import run_command
from tts_job import TTSJob, ENDPOINT, private_write, sha

TTS_EXECUTION_ENABLED = False
SCOPE = 'video_tts_exact_once_v1'
SCRIPT_SHA = 'ec1e2906fd065530a2bbfc79bfab9d3769a9f72296897887f5b02d4efeeffa59'


def fresh(issued, expires):
    try:
        start, end, current = datetime.fromisoformat(issued), datetime.fromisoformat(expires), datetime.fromisoformat(now())
        return start.utcoffset() == end.utcoffset() == timedelta(hours=9) and start <= current < end and timedelta(0) < end-start <= timedelta(hours=1)
    except (TypeError, ValueError): return False


class GeminiTTSAdapter:
    @staticmethod
    def payload(job):
        payload = deepcopy(job['payload'])
        payload['store'] = False
        payload['generation_config']['max_output_tokens'] = 1024
        return payload

    @staticmethod
    def request(raw, key):
        require(isinstance(key, str) and 16 <= len(key) <= 4096
                and all(32 < ord(c) < 127 for c in key), 'tts_key_invalid')
        return Request(ENDPOINT, data=raw, method='POST', headers={
            'Content-Type': 'application/json', 'x-goog-api-key': key})

    @staticmethod
    def decode(raw, job):
        require(isinstance(raw, bytes) and len(raw) <= job['max_response_bytes'], 'tts_response_limit')
        envelope = json.loads(raw)
        require(envelope.get('object') == 'interaction' and envelope.get('model') == job['model']
                and envelope.get('status') == 'completed' and not envelope.get('error'), 'tts_incomplete')
        usage = envelope.get('usage', {})
        for field, limit in [('total_input_tokens', 2048), ('total_output_tokens', 1024)]:
            require(type(usage.get(field)) is int and 0 < usage[field] <= limit, 'tts_usage_limit')
        require(type(usage.get('total_tokens')) is int and usage['total_tokens'] ==
                usage['total_input_tokens']+usage['total_output_tokens']
                and usage.get('total_thought_tokens', 0) == 0
                and usage.get('total_tool_use_tokens', 0) == 0, 'tts_usage_limit')
        steps = envelope['steps']
        require(len(steps) == 1 and steps[0]['type'] == 'model_output', 'tts_audio_envelope')
        parts = steps[0]['content']
        require(len(parts) == 1 and parts[0]['type'] == 'audio' and parts[0]['mime_type'] == 'audio/wav'
                and not parts[0].get('uri'), 'tts_audio_envelope')
        audio = base64.b64decode(parts[0]['data'], validate=True)
        with wave.open(io.BytesIO(audio)) as wav:
            frames = wav.getnframes()
            require(wav.getnchannels() == 1 and wav.getsampwidth() == 2 and wav.getframerate() == 24000
                    and wav.getcomptype() == 'NONE' and 0 < frames <= 480000
                    and len(wav.readframes(frames)) == frames*2, 'tts_audio_format')
        return audio, dict(input_tokens=usage['total_input_tokens'], output_tokens=usage['total_output_tokens'], seconds=frames/24000)


class TTSExecution:
    _sign = LiveStore._sign  # Same signing primitive; independent private signing key/root/scope.

    def __init__(self, folder):
        self.root = Path(folder).absolute()
        require(not any(p.is_symlink() for p in (self.root, *self.root.parents)), 'tts_symlink')

    def _read(self, name):
        require(not any(p.is_symlink() for p in (self.root, *self.root.parents)), 'tts_symlink')
        require(self.root.is_dir() and self.root.stat().st_mode & 0o077 == 0, 'tts_private_folder_required')
        path = self.root/name
        require(not path.is_symlink() and path.is_file() and path.stat().st_size <= 2000000
                and path.stat().st_mode & 0o077 == 0, 'tts_private_file_required')
        return path.read_bytes()

    def _write(self, name, value):
        private_write(self.root/name, canonical_bytes(value))

    def _signed(self, record):
        return dict(record=record, signature=self._sign(record, create=True))

    def _verified(self, name):
        value = json.loads(self._read(name)); record = value['record']
        self._read('.operating-consent.key')
        require(hmac.compare_digest(str(value['signature']), self._sign(record)), 'tts_signature_invalid')
        return record

    def create(self, source, project):
        require(isinstance(project, str) and re.fullmatch('[a-z][a-z0-9-]{3,62}', project), 'tts_project_invalid')
        source = Path(source)
        require(not source.is_symlink() and source.is_file(), 'tts_source_invalid')
        job = json.loads(source.read_bytes()); TTSJob(self.root)._validate(job)
        require(job['text_sha256'] == SCRIPT_SHA and job['model'] == 'gemini-3.8-flash-tts'
                and job['voice'] == 'Puck', 'tts_fixed_sample_required')
        raw = canonical_bytes(GeminiTTSAdapter.payload(job))
        self.root.mkdir(mode=0o700, parents=True, exist_ok=False)
        self._write('source_job.json', job)
        private_write(self.root/'payload.json', raw); (self.root/'payload.json').chmod(0o400)
        self._write('scope.json', dict(scope=SCOPE, project=project, job_hash=job['job_hash'],
            model=job['model'], endpoint=ENDPOINT, voice=job['voice'], payload_sha256=sha(raw),
            output=str(self.root/'B_gemini.wav'), requests=1, max_cost_usd=0, store=False,
            max_output_tokens=1024, local_max_seconds=20, local_max_response_bytes=2000000,
            google_unpaid_data_policy='inputs_and_outputs_may_be_used_for_improvement_and_human_review',
            quality='unassessed', publish_ready=False))
        return self.status()

    def _load(self):
        job = json.loads(self._read('source_job.json')); TTSJob(self.root)._validate(job)
        scope = json.loads(self._read('scope.json')); raw = self._read('payload.json')
        require(scope['scope'] == SCOPE and scope['job_hash'] == job['job_hash']
                and job['text_sha256'] == SCRIPT_SHA and job['model'] == 'gemini-3.8-flash-tts'
                and job['voice'] == 'Puck' and scope['model'] == job['model'] and scope['voice'] == job['voice']
                and scope['endpoint'] == ENDPOINT and scope['requests'] == 1 and scope['max_cost_usd'] == 0
                and scope['output'] == str(self.root/'B_gemini.wav')
                and raw == canonical_bytes(GeminiTTSAdapter.payload(job)) and sha(raw) == scope['payload_sha256'], 'tts_scope_changed')
        return job, scope, raw

    def verify_key(self, key, project_key, evidence):
        job, scope, raw = self._load()
        GeminiTTSAdapter.request(raw, key)  # Local encoding validation only.
        require(isinstance(project_key, str) and hmac.compare_digest(key.encode(), project_key.encode()), 'tts_project_key_mismatch')
        require(key not in canonical_bytes(evidence).decode(), 'tts_secret_in_evidence')
        require(evidence.get('project') == scope['project'] and evidence.get('model') == job['model']
                and evidence.get('method') == 'owner_aistudio_review_not_independent_verification'
                and evidence.get('tier') == 'Free' and evidence.get('billing') == 'disabled'
                and evidence.get('model_access') == 'available' and evidence.get('region_supported') is True
                and evidence.get('paid_fallback') is False, 'tts_account_evidence_required')
        for field, minimum in [('remaining_requests', 1), ('remaining_input_tokens', 2048), ('remaining_output_tokens', 1024)]:
            require(type(evidence.get(field)) is int and evidence[field] >= minimum, 'tts_quota_evidence_required')
        require(fresh(evidence.get('checked_at'), evidence.get('expires_at')), 'tts_account_expired')
        require(isinstance(evidence.get('evidence_sha256'), str) and re.fullmatch('[a-f0-9]{64}', evidence['evidence_sha256'])
                and evidence.get('source_url') == 'https://aistudio.google.com/'
                and isinstance(evidence.get('observation'), str) and 20 <= len(evidence['observation']) <= 1500,
                'tts_account_observation_required')
        record = dict(scope_hash=digest(scope), root=str(self.root), evidence=evidence,
            credential_binding=self._sign(dict(scope=SCOPE, project=scope['project'], credential=key), create=True))
        self._write('account.json', self._signed(record))

    def _account(self, scope, key):
        proof = self._verified('account.json')
        require(proof['scope_hash'] == digest(scope) and proof['root'] == str(self.root), 'tts_account_binding')
        evidence = proof['evidence']
        require(fresh(evidence['checked_at'], evidence['expires_at']), 'tts_account_expired')
        require(hmac.compare_digest(proof['credential_binding'], self._sign(dict(scope=SCOPE,
                project=scope['project'], credential=key))), 'tts_active_key_changed')
        return proof

    def review(self, key):
        _, scope, _ = self._load(); account = self._account(scope, key)
        issued = now(); expires = min(datetime.fromisoformat(issued)+timedelta(hours=1),
            datetime.fromisoformat(account['evidence']['expires_at'])).isoformat()
        record = dict(scope=scope, root=str(self.root), account_hash=digest(account), issued_at=issued, expires_at=expires)
        self._write('review.json', self._signed(record))
        return dict(review_hash=digest(record), payload_sha256=scope['payload_sha256'], expires_at=expires)

    def approve(self, review_hash, key, *, owner_confirmed=False, accept_google_data_policy=False):
        _, scope, _ = self._load(); account = self._account(scope, key); review = self._verified('review.json')
        require(owner_confirmed is True and accept_google_data_policy is True, 'tts_explicit_consent_required')
        require(digest(review) == review_hash and review['scope'] == scope and review['root'] == str(self.root)
                and review['account_hash'] == digest(account) and fresh(review['issued_at'], review['expires_at']), 'tts_review_invalid')
        self._write('consent.json', self._signed(dict(scope=SCOPE, review_hash=review_hash,
            account_hash=digest(account), root=str(self.root), owner_confirmed=True,
            accept_google_data_policy=True, issued_at=now(), expires_at=review['expires_at'])))

    def status(self):
        _, scope, _ = self._load()
        return dict(project=scope['project'], payload_sha256=scope['payload_sha256'],
            execution_enabled=TTS_EXECUTION_ENABLED, attempts_used=int((self.root/'attempt.json').exists()),
            account_record_present=(self.root/'account.json').is_file(),
            consent_record_present=(self.root/'consent.json').is_file(), quality='unassessed', publish_ready=False)

    def execute(self, key):
        require(TTS_EXECUTION_ENABLED is True, 'tts_execution_disabled')
        job, scope, raw = self._load(); account = self._account(scope, key)
        review = self._verified('review.json'); consent = self._verified('consent.json')
        require(review['scope'] == scope and review['root'] == str(self.root)
                and review['account_hash'] == digest(account) and fresh(review['issued_at'], review['expires_at'])
                and consent == dict(scope=SCOPE, review_hash=digest(review), account_hash=digest(account),
                    root=str(self.root), owner_confirmed=True, accept_google_data_policy=True,
                    issued_at=consent['issued_at'], expires_at=review['expires_at'])
                and fresh(consent['issued_at'], consent['expires_at']), 'tts_consent_invalid')
        request = GeminiTTSAdapter.request(raw, key)
        require(key.encode() not in raw and key not in canonical_bytes(scope).decode(), 'tts_secret_in_payload')
        if (self.root/'attempt.json').exists() or (self.root/'attempt.json').is_symlink():
            raise FileExistsError('tts_attempt_already_consumed')
        for name in ('B_gemini.wav', 'result.json'):
            require(not (self.root/name).exists() and not (self.root/name).is_symlink(), 'tts_output_exists')
        self._write('attempt.json', dict(status='reserved_consumed', at=now(), scope_hash=digest(scope),
            consent_hash=digest(consent), retry=False))
        try:
            # send_once uses a direct opener with no proxy, redirects, or retry.
            with send_once(request, 30) as response:
                require(response.status == 200, 'tts_http_failed')
                declared = response.headers.get('Content-Length')
                require(declared is None or 0 <= int(declared) <= 2000000, 'tts_response_limit')
                require(response.headers.get_content_type() == 'application/json', 'tts_response_type')
                encoded = response.read(2000001)
            audio, usage = GeminiTTSAdapter.decode(encoded, job)
            require(key.encode() not in audio, 'tts_secret_in_response')
            output = self.root/'B_gemini.wav'; private_write(output, audio)
            probe = json.loads(run_command(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(output)], stage='ffprobe_audio'))
            require(len(probe['streams']) == 1 and probe['streams'][0]['codec_name'] == 'pcm_s16le', 'tts_codec')
            run_command(['ffmpeg', '-v', 'error', '-xerror', '-i', str(output), '-f', 'null', '-'], stage='ffmpeg_decode')
            result = dict(status='audio_validated', audio_sha256=sha(audio), codec='pcm_s16le', sample_rate=24000,
                decoded=True, usage=usage, quality='unassessed', publish_ready=False, rights='unverified',
                spoken_text_match='unverified_requires_human_AB', retry=False,
                cost='not_independently_measured_free_account_owner_attested')
        except Exception:
            self._write('result.json', dict(status='failed_or_uncertain', retry=False))
            raise CompanyError('tts_attempt_failed_no_retry') from None
        self._write('result.json', result)
        return result
