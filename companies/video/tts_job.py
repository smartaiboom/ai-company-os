"""Private, single-attempt voice jobs. Production HTTP deliberately unavailable.

Only injected offline transports exist. Preparation is never execution consent.
"""
import base64
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import wave

from autonomous_company import require, digest, now
from manager_plan_once import canonical_bytes
from local_artifacts import run_command

TTS_EXECUTION_ENABLED = False
MODELS = ('gemini-3.8-flash-tts', 'gemini-3.8-flash-lite-tts')
ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/interactions'
STYLE = '친근한 한국어 직장인 쇼츠 안내. 또박또박 경쾌하고 자연스러운 대화체. 과장하거나 특정 성우를 흉내 내지 마세요.'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def private_write(path, raw):
    # Exclusive creation + fsync: an interrupted reservation remains consumed.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(directory)
    finally: os.close(directory)


def prepare_voice_job(text, reference, *, fictional, model=MODELS[0], voice='Puck'):
    require(fictional is True, 'fictional_script_required')
    require(isinstance(text, str) and 0 < len(text.encode()) <= 1000, 'tts_input_limit')
    require(model in MODELS and voice in ('Puck', 'Kore'), 'tts_model_voice_policy')
    reference = Path(reference)
    require(reference.is_file() and not reference.is_symlink(), 'tts_reference_missing')
    payload = dict(model=model, input=[dict(type='user_input', content=[dict(type='text', text=text,
        annotations=[dict(type='speech_metadata', style=STYLE)])])],
        response_format=dict(type='audio', mime_type='audio/wav', sample_rate=24000),
        generation_config=dict(speech_config=[dict(voice=voice)]))
    # Token cap is a local acceptance bound; not an undocumented wire parameter.
    job = dict(schema_version=1, kind='voice', provider='gemini_developer', model=model,
        endpoint=ENDPOINT, voice=voice, fictional=True, text_sha256=sha(text.encode()),
        reference_sha256=sha(reference.read_bytes()), payload=payload,
        payload_sha256=sha(canonical_bytes(payload)), max_requests=1, max_cost_usd=0,
        max_input_bytes=1000, max_output_tokens=1024, max_seconds=20,
        max_response_bytes=2000000, quality='unassessed', publish_ready=False,
        automatic_retry=False, automatic_fallback=False)
    job['job_hash'] = digest(job)
    return job


class TTSJob:
    def __init__(self, folder):
        self.folder = Path(folder).absolute()
        require(not any(p.is_symlink() for p in (self.folder, *self.folder.parents)), 'tts_symlink')

    def create(self, job):
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=False)
        self._validate(job)
        private_write(self.folder/'job.json', canonical_bytes(job))
        private_write(self.folder/'payload.json', canonical_bytes(job['payload']))
        (self.folder/'payload.json').chmod(0o400)
        return deepcopy(job)

    def _validate(self, job):
        value = deepcopy(job); expected = value.pop('job_hash', None)
        require(expected == digest(value), 'tts_job_changed')
        require(job['provider'] == 'gemini_developer' and job['model'] in MODELS
                and job['endpoint'] == ENDPOINT, 'tts_provider_policy')
        # Reconstruct the whole contract so recomputing a hash cannot widen limits.
        text = job['payload']['input'][0]['content'][0]['text']
        payload = job['payload']
        require(payload == dict(model=job['model'], input=[dict(type='user_input', content=[dict(
            type='text', text=text, annotations=[dict(type='speech_metadata', style=STYLE)])])],
            response_format=dict(type='audio', mime_type='audio/wav', sample_rate=24000),
            generation_config=dict(speech_config=[dict(voice=job['voice'])])), 'tts_payload_policy')
        require(job['voice'] in ('Puck', 'Kore') and job['fictional'] is True
                and 0 < len(text.encode()) <= 1000 and sha(text.encode()) == job['text_sha256']
                and sha(canonical_bytes(payload)) == job['payload_sha256'], 'tts_payload_changed')
        for key, val in dict(max_requests=1, max_cost_usd=0, max_input_bytes=1000,
            max_output_tokens=1024, max_seconds=20, max_response_bytes=2000000,
            quality='unassessed', publish_ready=False, automatic_retry=False, automatic_fallback=False).items():
            require(job[key] == val, 'tts_limit_policy')

    def run_mock(self, approval, evidence, transport):
        """Explicit test-only transport: no credentials accepted, no real HTTP implementation."""
        require(self.folder.stat().st_mode & 0o077 == 0, 'tts_private_folder_required')
        require(not any((self.folder/name).is_symlink() for name in
            ('job.json', 'payload.json', 'attempt.json', 'result.json', 'B_MOCK_NOT_TTS.wav')), 'tts_symlink')
        job = json.loads((self.folder/'job.json').read_bytes()); self._validate(job)
        raw = (self.folder/'payload.json').read_bytes()
        require(raw == canonical_bytes(job['payload']), 'tts_payload_changed')
        require(approval == dict(scope='tts_mock_once', job_hash=job['job_hash'],
            payload_sha256=sha(raw), requests=1, max_cost_usd=0), 'tts_approval_required')
        require(evidence.get('simulation') is True and evidence.get('free_tier') is True
                and evidence.get('billing_enabled') is False and evidence.get('key_bound') is True
                and evidence.get('model') == job['model'] and evidence.get('region_supported') is True
                and evidence.get('quota_requests', 0) >= 1
                and evidence.get('quota_output_tokens', 0) >= job['max_output_tokens']
                and evidence.get('policy_reviewed') is True, 'tts_free_evidence_required')
        try: checked = datetime.fromisoformat(evidence['checked_at'])
        except (KeyError, ValueError, TypeError): require(False, 'tts_evidence_expired')
        require(checked.tzinfo is not None and timedelta(0) <= datetime.now(checked.tzinfo)-checked <= timedelta(hours=1),
                'tts_evidence_expired')
        private_write(self.folder/'attempt.json', canonical_bytes(dict(status='reserved_consumed',
            at=now(), simulation=True, job_hash=job['job_hash'], approval_hash=digest(approval), evidence_hash=digest(evidence))))
        try:
            response = transport(job['endpoint'], raw, 30, job['max_response_bytes'])
            require(isinstance(response, bytes) and len(response) <= job['max_response_bytes'], 'tts_response_limit')
            envelope = json.loads(response)
            require(envelope.get('status') == 'completed' and 'error' not in envelope, 'tts_incomplete')
            usage = envelope.get('usage', {})
            # Provider-specific real usage schema still needs account review; mocks are explicit.
            require(usage.get('mock') is True and type(usage.get('output_tokens')) is int
                    and 0 < usage['output_tokens'] <= 1024 and usage.get('cost_usd') == 0, 'tts_usage_limit')
            steps = envelope['steps']
            require(len(steps) == 1 and steps[0]['type'] == 'model_output', 'tts_audio_envelope')
            content = steps[0]['content']
            require(len(content) == 1 and content[0]['type'] == 'audio'
                    and content[0]['mime_type'] == 'audio/wav', 'tts_audio_envelope')
            audio = base64.b64decode(content[0]['data'], validate=True)
            with wave.open(io.BytesIO(audio)) as wav:
                require(wav.getnchannels() == 1 and wav.getsampwidth() == 2
                        and wav.getframerate() == 24000 and wav.getcomptype() == 'NONE'
                        and 0 < wav.getnframes() <= 480000, 'tts_audio_format')
                frames = wav.getnframes(); require(len(wav.readframes(frames)) == frames*2, 'tts_audio_truncated')
            output = self.folder/'B_MOCK_NOT_TTS.wav'; private_write(output, audio)
            probe = json.loads(run_command(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(output)], stage='ffprobe_final'))
            require(len(probe['streams']) == 1 and probe['streams'][0]['codec_name'] == 'pcm_s16le', 'tts_codec')
            run_command(['ffmpeg', '-v', 'error', '-xerror', '-i', str(output), '-f', 'null', '-'], stage='ffmpeg_decode')
            result = dict(status='mock_validated', simulation=True, audio_sha256=sha(audio),
                seconds=frames/24000, quality='unassessed', publish_ready=False,
                spoken_text_match='unverified_requires_listening', text_sha256=job['text_sha256'])
        except Exception:
            private_write(self.folder/'result.json', canonical_bytes(dict(status='failed_or_uncertain', retry=False)))
            raise RuntimeError('tts_attempt_failed_no_retry') from None
        private_write(self.folder/'result.json', canonical_bytes(result))
        return result

    def execute(self, *args, **kwargs):
        require(False, 'tts_production_transport_disabled')
