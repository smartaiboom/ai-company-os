"""Offline staff tool preparation. No credentials, HTTP client, or execution switch.

Published rates are estimates, not account quotes. Readiness never grants consent.
Existing scene request validation and disabled execution boundary are reused.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
import json
from autonomous_company import (Company, MockManagerProvider, MockEmployeeProvider,
                                require, exact, digest, text)
from ai_clip_pipeline import validate_request, DisabledAPIProvider

PRICE_DATE = '2026-11-10'
_TOOLS = {
    'runway_gen4_turbo': dict(kind='video', model='gen4_turbo', unit='second',
        usd_per_unit='0.05', request_seconds=[5, 10], minimum_funding_usd='10',
        price_source='https://docs.dev.runwayml.com/guides/pricing/',
        contract_source='https://docs.dev.runwayml.com/api/'),
    'eleven_multilingual_v2': dict(kind='voice', model='eleven_multilingual_v2',
        unit='character', usd_per_unit='0.00008', max_characters=10000,
        commercial='paid plan required; beta/voice rights must be checked',
        price_source='https://elevenlabs.io/pricing/api',
        contract_source='https://elevenlabs.io/docs/api-reference/text-to-speech/convert'),
    'google_chirp3_hd': dict(kind='voice', model='Chirp3-HD', unit='character',
        usd_per_unit='0.00003', max_utf8_bytes=5000,
        commercial='Cloud terms and input rights; billing/API enablement required',
        price_source='https://cloud.google.com/text-to-speech/pricing',
        contract_source='https://docs.cloud.google.com/text-to-speech/docs/create-audio'),
}


def capabilities():
    return dict(price_date=PRICE_DATE, tools=deepcopy(_TOOLS), transport_enabled=False,
                automatic_retry=False, automatic_fallback=False, quality='unassessed',
                estimate_excludes=['tax', 'retries', 'reference image', 'subscription/funding',
                                   'cloud extras'],
                qwen='blocked by recorded RAM gate; no repeated preflight')


def _money(value):
    require(isinstance(value, str) and bool(re.fullmatch(r'\d+(?:\.\d{1,8})?', value)),
            'invalid_usd_cap')
    try: amount = Decimal(value)
    except InvalidOperation: require(False, 'invalid_usd_cap')
    require(amount.is_finite() and amount >= 0, 'invalid_usd_cap')
    return amount


def prepare(tool, request):
    """One proposed request; never an authorization or an executed tool result.

    Reference bytes/URIs and credentials deliberately cannot enter this contract.
    A future approved transport must resolve assets and reserve its durable attempt.
    """
    require(isinstance(tool, str) and tool in _TOOLS, 'unknown_quality_tool')
    exact(request, ('input', 'quality_spec', 'cap_usd', 'rights', 'upstream_hash'))
    spec = request['quality_spec']
    exact(spec, ('audience', 'acceptance', 'human_review_required'))
    text(spec['audience'], 300);text(spec['acceptance'], 2000)
    require(spec['human_review_required'] is True, 'human_quality_review_required')
    require(request['rights'] in ('unverified', 'owned_input_pending_output_terms'), 'invalid_rights')
    require(isinstance(request['upstream_hash'], str) and
            bool(re.fullmatch('[a-f0-9]{64}', request['upstream_hash'])), 'invalid_upstream_hash')
    cap = _money(request['cap_usd']); item = _TOOLS[tool]; value = request['input']
    if item['kind'] == 'video':
        validate_request(value)
        require(value['reference_image'] is None, 'reference_upload_not_authorized')
        require(type(value['duration_target']) is int and
                value['duration_target'] in item['request_seconds'], 'unsupported_tool_duration')
        units = value['duration_target']
        payload = dict(model=item['model'], promptText=value['prompt'],
                       duration=units, ratio='720:1280', promptImage=None)
        missing = ['reference_image_and_upload_approval']
    else:
        exact(value, ('text', 'language', 'voice_id'))
        text(value['text'], item.get('max_characters', 10000))
        require(value['language'] == 'ko-KR', 'unsupported_language')
        require(value['voice_id'] is None, 'voice_selection_requires_account_verification')
        if 'max_utf8_bytes' in item:
            require(len(value['text'].encode('utf-8')) <= item['max_utf8_bytes'], 'tts_byte_limit')
        units = len(value['text'])  # Unicode characters, NOT UTF-8 billing bytes.
        if tool == 'eleven_multilingual_v2':
            # language_code is unsupported by this model; do not add it.
            payload = dict(text=value['text'], model_id=item['model'], output_format='mp3_44100_128')
        else:
            payload = dict(input={'text': value['text']},
                voice={'languageCode': 'ko-KR', 'name': None}, audioConfig={'audioEncoding': 'LINEAR16'})
        missing = ['korean_voice_selection_and_commercial_terms']
    estimate = Decimal(units) * Decimal(item['usd_per_unit'])
    require(estimate <= cap, 'quality_tool_cost_cap_exceeded')
    result = dict(schema_version=1, source='offline_request_preparation', tool=tool,
        upstream_hash=request['upstream_hash'], input_hash=digest(value),
        quality_spec=deepcopy(spec), rights=request['rights'], units=units,
        estimated_usd=str(estimate), cap_usd=str(cap), price_date=PRICE_DATE,
        payload_template=payload, ready_to_execute=False, automatic_retry=False,
        blockers=['transport_not_implemented', 'bounded_user_approval_missing',
                  'account_billing_and_current_rate_unverified', 'output_not_generated',
                  'rights_and_human_quality_unverified'] + missing,
        result_verification=['request/attempt binding', 'output SHA256', 'probe/decode',
            'duration/resolution or sample rate/clipping', 'rights/watermark review',
            'human visual/voice A-B preference'], output=None)
    result['preparation_hash'] = digest(result)
    return result


def inspect_handoff(preparation, *, upstream_hash):
    """QA checks integrity and missing media without mistaking a plan for delivery."""
    require(isinstance(preparation, dict), 'invalid_preparation')
    value = deepcopy(preparation); expected = value.pop('preparation_hash', None)
    require(expected == digest(value), 'quality_preparation_changed')
    require(value['upstream_hash'] == upstream_hash, 'quality_upstream_changed')
    require(value['source'] == 'offline_request_preparation' and value['output'] is None
            and value['ready_to_execute'] is False, 'invalid_preparation_state')
    return dict(preparation_hash=expected, upstream_hash=upstream_hash, publishable=False,
                sensory_quality='unassessed', blockers=deepcopy(value['blockers']))


def execute(preparation):
    """Intentionally disabled, including for caller-supplied permission fields."""
    require(False, 'quality_tool_transport_disabled')


class PreparedSceneProvider(DisabledAPIProvider):
    """Keeps existing SceneProvider execution refusal; adds preparation only."""
    def prepare(self, request):
        return prepare('runway_gen4_turbo', request)


def run_offline_contract(store, project_id, script, video_request, voice_request, *, voice_tool):
    """Execute authored callbacks on the existing mock engine, not AI judgment.

    The caller supplies a newly authored script and a separately isolated Store.
    Only preparation is accepted; QA always stops before a media delivery claim.
    Existing engine owns dependency ordering, attempt limits and version storage.
    """
    text(script)
    require(voice_tool in ('eleven_multilingual_v2', 'google_chirp3_hd'), 'unsupported_voice_tool')
    require(video_request['upstream_hash'] == voice_request['upstream_hash'] == digest(script),
            'quality_upstream_changed')

    def checks(status, evidence):
        return [dict(criterion_id='prepared', status=status, evidence=evidence, source='model_claim')]

    def manager(phase, context):
        if phase == 'plan':
            tasks = []
            for role, deps in [('writer', []), ('video', ['writer']),
                               ('voice', ['writer']), ('qa', ['writer', 'video', 'voice'])]:
                tasks.append(dict(id=role, title=role, role=role, depends_on=deps,
                    instructions='Offline authored contract only; inspect hashes, limits and blockers.',
                    criteria_ids=['prepared']))
            value = dict(tasks=tasks, criteria=[dict(id='prepared',
                description='Preparation and blocker trace only; no media quality pass')],
                rationale='Authored executable contract demonstration', uncertainty='No model judgment')
        elif phase == 'review':
            value = dict(action='accept', rationale='Accept planning contract only',
                evidence=context['result']['evidence'], uncertainty='Media absent; no sensory assessment',
                checks=checks('met', 'Authored planning result recorded'), feedback='', operation=None)
        else:
            value = dict(action='stop', content='No generated media; publication blocked',
                rationale='QA records missing transport, rights and human evaluation',
                uncertainty='Real visual and voice quality unassessed',
                checks=checks('unknown', 'No video or new voice'),
                task_refs=[dict(task_id=r['task_id'], revision=r['revision'], result_hash=digest(r))
                           for r in context['results']])
        return json.dumps(value, ensure_ascii=False)

    def employee(phase, context):
        role = context['assignment']['role']; previous = context['previous_results']
        if role == 'writer': content = script
        else:
            require(previous[0]['task_id'] == 'writer' and previous[0]['content'] == script,
                    'quality_writer_handoff_changed')
            if role in ('video', 'voice'):
                content = json.dumps(prepare('runway_gen4_turbo' if role == 'video' else voice_tool,
                    video_request if role == 'video' else voice_request), ensure_ascii=False)
            else:
                content = json.dumps(dict(publishable=False, source='offline_authored_qa',
                    inspections=[inspect_handoff(json.loads(r['content']), upstream_hash=digest(script))
                                 for r in previous[1:]],
                    handoff_refs=[dict(task_id=r['task_id'], result_hash=digest(r)) for r in previous]),
                    ensure_ascii=False)
        return json.dumps(dict(content=content, evidence='New supplied input; authored offline contract',
                               uncertainty='No remote model/API call; no generated media'), ensure_ascii=False)

    class ContextCompany(Company):
        def _workflow_context(self, project):
            return deepcopy(project.get('quality_context', {}))

    return ContextCompany(store, MockManagerProvider('codex-authored-manager', manager),
                          MockEmployeeProvider('codex-authored-staff', employee)).run(project_id)
