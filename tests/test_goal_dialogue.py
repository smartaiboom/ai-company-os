"""Offline integration across persistent dialogue, CLI and the existing company plan loop."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from autonomous_company import Company, CompanyError, MockManagerProvider, digest
from goal_dialogue import DialogueStore, FIELDS
from goal_dialogue_cli import main
from video_production_company import VideoProductionStore
from tests.support.autonomous_company_fixtures import FictionalModels


def spec(state):
    answer = state['answers'].get('audience', {}).get('value')
    result = {field: {'value': '미정', 'evidence': []} for field in FIELDS}
    result['audience'] = {'value': answer or '미정', 'evidence': ['audience'] if answer else []}
    result.update(summary='영상 요구사항', assumptions=['근거가 없는 항목은 미확정 가정'])
    return result


class AdaptiveMock:
    offline = True
    name = 'test_only_adaptive_mock'
    def respond(self, state):
        questions = []
        if 'audience' not in state['answers']:
            questions = [dict(id='audience', text='누가 보나요?', reason='시청자에 따라 설명 수준 결정')]
        elif state['answers']['audience']['value'] == '초등학생' and 'duration' not in state['answers']:
            questions = [dict(id='duration', text='어린이용 영상 길이 제한은?', reason='어린 시청자의 집중 시간 확인')]
        return json.dumps(dict(questions=questions, sufficient=not questions, spec=spec(state)), ensure_ascii=False)


class DialogueIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.store = DialogueStore(self.root/'dialogues')
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden')))

    def test_adaptive_resume_confirmation_video_plan_context(self):
        p = self.store.create('안전 교육 영상'); key = p['id']
        with self.assertRaises(CompanyError): self.store.handoff_video(key, self.root/'video')
        self.store.propose(key, AdaptiveMock())
        self.store.answer(key, 'audience', '성인')
        self.store.answer(key, 'audience', '초등학생')
        self.store = DialogueStore(self.root/'dialogues')
        p = self.store.propose(key, AdaptiveMock())
        self.assertEqual(p['questions'][-1]['id'], 'duration')
        self.store.answer(key, 'duration', skip=True)
        p = self.store.propose(key, AdaptiveMock())
        with self.assertRaises(CompanyError): self.store.confirm(key, 'stale')
        self.store.confirm(key, digest(p['spec']))
        project = self.store.handoff_video(key, self.root/'video')
        video = VideoProductionStore(self.root/'video')
        self.assertFalse(project['real_ai']['enabled'])
        self.assertFalse(video._grant_path(project['id']).exists())
        with self.assertRaises(CompanyError): self.store.handoff_video(key, self.root/'video')
        contexts = []
        model = FictionalModels()
        def manager(phase, context):
            contexts.append(deepcopy(context))
            result = json.loads(model.manager.respond(phase, context))
            if phase == 'plan':
                result['tasks'][0]['instructions'] = json.loads(context['goal'])['requirements']['audience']['value'] + ' 대상 설명'
            return json.dumps(result)
        # Same inherited Company plan loop on the actual VideoProductionStore-created draft;
        # bypass only live execution plumbing with a test-only offline harness.
        class OfflineVideoCompany(Company):
            def __init__(self):
                self.store = video; self.manager = MockManagerProvider('offline', manager); self.employee = model.employee
            def _validate_mode(self, p): pass
            def _attempts(self, p): return p['real_ai']['attempts']
            def _call(self, p, provider, phase, task_id, context):
                if phase == 'plan': return json.loads(provider.respond(phase, context))
                raise CompanyError('offline_plan_only')
        OfflineVideoCompany().run(project['id'])
        plan = video.load(project['id'])['plan']
        self.assertIn('초등학생', plan['tasks'][0]['instructions'])
        goal = json.loads(contexts[0]['goal'])
        self.assertEqual(goal['requirements']['audience']['value'], '초등학생')
        self.assertEqual(goal['user_answers']['audience']['value'], '초등학생')
        self.assertTrue(all(e['at'].endswith('+09:00') for e in self.store.load(key)['history']))

    def test_duplicate_limits_validation_and_uncertain_proposal(self):
        key = self.store.create('영상', max_rounds=2)['id']
        self.store.propose(key, AdaptiveMock())
        self.store.answer(key, 'audience', '성인')
        with self.assertRaises(CompanyError): self.store.answer(key, 'audience', '성인')
        class Repeat(AdaptiveMock):
            def respond(self, state):
                return super().respond({**state, 'answers': {}})
        with self.assertRaises(CompanyError): self.store.propose(key, Repeat())
        with self.assertRaises(CompanyError): self.store.propose(key, AdaptiveMock())
        p = self.store.load(key)
        self.store.revise(key, spec(p))
        self.store.confirm(key, digest(spec(p)))
        with self.assertRaises(CompanyError): self.store.answer(key, 'audience', '변경')
        with self.assertRaises(CompanyError): self.store.create('api_key=secret')
        with self.assertRaises(CompanyError): self.store.propose(key, object())

    def test_cli_resume_and_explicit_revision(self):
        root = str(self.root/'cli')
        with patch('builtins.print'):
            self.assertEqual(main(['--root', root, 'create', '영상']), 0)
            store = DialogueStore(root)
            key = next(store.root.glob('dialogue-*.json')).stem
            proposal = self.root/'proposal.json'
            proposal.write_text(AdaptiveMock().respond(store.load(key)))
            self.assertEqual(main(['--root', root, 'propose', key, str(proposal)]), 0)
            self.assertEqual(main(['--root', root, 'answer', key, 'audience', '성인']), 0)
            self.assertEqual(main(['--root', root, 'show', key]), 0)
            proposal.write_text(AdaptiveMock().respond(store.load(key)))
            self.assertEqual(main(['--root', root, 'propose', key, str(proposal)]), 0)
            self.assertEqual(main(['--root', root, 'confirm', key, digest(store.load(key)['spec'])]), 0)
            self.assertEqual(main(['--root', root, 'handoff', key, '--projects', str(self.root/'cli-video')]), 0)


# Native Gemini wire simulation. No external HTTP is permitted in this suite.
from datetime import datetime, timedelta
from io import BytesIO
import goal_dialogue_live as live
from goal_dialogue_live import LiveDialogueStore, dialogue_context, payload_for


def envelope(value, **updates):
    result = dict(candidates=[dict(finishReason='STOP', content=dict(role='model', parts=[dict(text=json.dumps(value))]))],
                  usageMetadata=dict(promptTokenCount=10, candidatesTokenCount=20, totalTokenCount=30))
    result.update(updates)
    return result


class LiveDialogueIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.store = LiveDialogueStore(self.root/'live')
        self.key = 'test-only-credential'
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden')))
        self.transport = self.enterContext(patch('goal_dialogue_live.send_once'))

    def create(self, **kwargs):
        return self.store.create('어린이 안전 영상', **kwargs)['id']

    def approve(self, key):
        prepared = self.store.prepare_consent(key)
        self.store.approve_consent(key, prepared['review_hash'], owner_confirmed=True, free_project_confirmed=True)
        return prepared

    def response(self, value):
        self.transport.side_effect = lambda *a, **kw: BytesIO(json.dumps(envelope(value)).encode())

    def ask(self, key):
        # Only this test fixture enables the gate; HTTP remains replaced and sockets blocked.
        with patch('goal_dialogue_live.LIVE_TRANSPORT_ENABLED', True):
            return self.store.ask_ai(key, api_key=self.key)

    def test_signed_native_wire_adaptive_answers_corrections_and_handoff(self):
        key = self.create()
        prepared = self.approve(key)
        with self.assertRaisesRegex(CompanyError, 'live_transport_disabled'):
            self.store.ask_ai(key, api_key=self.key)
        self.assertFalse(self.store.simulation)
        self.assertFalse(self.store.load(key)['simulation'])
        self.assertFalse(self.store.load(key)['real_ai']['attempts'])
        contexts = []
        def adaptive(request, timeout):
            state = self.store.load(key)
            self.assertEqual(state['real_ai']['attempts'][-1]['status'], 'reserved')
            self.assertEqual(state['status'], 'awaiting_proposal')
            self.assertEqual(request.full_url, live.ENDPOINT)
            self.assertEqual(request.get_header('X-goog-api-key'), self.key)
            self.assertNotIn(self.key, request.full_url)
            self.assertEqual(timeout, 90)
            body = json.loads(request.data)
            self.assertEqual(body['generationConfig']['responseJsonSchema'], live.response_schema())
            self.assertNotIn('tools', body)
            context = json.loads(body['contents'][0]['parts'][0]['text']); contexts.append(context)
            self.assertEqual(set(context), {'goal', 'questions', 'answers', 'specification', 'user_notes',
                                           'user_spec_revisions', 'round', 'max_rounds'})
            if not context['answers']:
                value = json.loads(AdaptiveMock().respond(state))
            else:
                result = spec(state)
                if context['user_notes']:
                    result['style'] = dict(value=context['user_notes'][-1]['value'], evidence=['note-1'])
                value = dict(questions=[], sufficient=True, spec=result)
            return BytesIO(json.dumps(envelope(value)).encode())
        self.transport.side_effect = adaptive
        p = self.ask(key)
        self.assertEqual(p['questions'][0]['id'], 'audience')
        with self.assertRaises(CompanyError): self.ask(key)
        self.store.answer(key, 'audience', '초등학생')
        self.approve(key)
        self.store.clarify(key, '친근한 애니메이션')
        with self.assertRaisesRegex(CompanyError, 'consent_input_changed'): self.ask(key)
        self.assertEqual(self.transport.call_count, 1)
        self.approve(key)
        p = self.ask(key)
        self.assertEqual(p['status'], 'review')
        self.assertEqual(contexts[1]['answers']['audience']['value'], '초등학생')
        self.assertEqual(p['spec']['style']['evidence'], ['note-1'])
        self.assertEqual(p['spec']['quality']['evidence'], [])
        with self.assertRaises(CompanyError): self.store.confirm(key, 'outdated')
        self.store.confirm(key, digest(p['spec']))
        project = self.store.handoff_video(key, self.root/'video')
        goal = json.loads(project['goal'])
        self.assertEqual(goal['requirements']['audience']['value'], '초등학생')
        self.assertEqual(goal['user_notes'][0]['value'], '친근한 애니메이션')
        self.assertFalse(project['real_ai']['enabled'])
        self.assertFalse(VideoProductionStore(self.root/'video')._grant_path(project['id']).exists())
        with self.assertRaises(CompanyError): self.store.handoff_video(key, self.root/'video')
        saved = self.store.load(key)
        self.assertEqual([a['status'] for a in saved['real_ai']['attempts']], ['completed', 'completed'])
        self.assertTrue(all(a['reserved_at'].endswith('+09:00') for a in saved['real_ai']['attempts']))
        self.assertNotIn(self.key, json.dumps(saved))
        self.assertEqual(len(saved['grants']), 3)  # Superseded signed approvals are preserved.
        self.assertEqual(prepared['body']['calls'], 1)

    def test_no_approval_wrong_binding_and_offline_isolation(self):
        key = self.create()
        with self.assertRaisesRegex(CompanyError, 'transmission_consent_required'): self.ask(key)
        prepared = self.store.prepare_consent(key)
        for options in ({}, dict(owner_confirmed=True), dict(free_project_confirmed=True)):
            with self.assertRaises(CompanyError): self.store.approve_consent(key, prepared['review_hash'], **options)
        with self.assertRaisesRegex(CompanyError, 'consent_review_changed'):
            self.store.approve_consent(key, 'wrong', owner_confirmed=True, free_project_confirmed=True)
        self.approve(key)
        for params in (dict(model='other'), dict(endpoint='https://example.com')):
            with self.assertRaisesRegex(CompanyError, 'fixed_gemini_binding_required'):
                self.store.ask_ai(key, api_key=self.key, **params)
        self.transport.assert_not_called()
        with self.assertRaises(CompanyError): DialogueStore(self.store.root).load(key)
        with self.assertRaises(CompanyError): self.store.propose(key, AdaptiveMock())
        offline = DialogueStore(self.root/'offline')
        before = offline.create('보존할 오프라인 목표')
        raw = offline.path(before['id']).read_bytes()
        with self.assertRaises(CompanyError): LiveDialogueStore(offline.root).create('승격 금지')
        self.assertEqual(offline.path(before['id']).read_bytes(), raw)
        with self.assertRaises(CompanyError): self.store.handoff_video(key, self.root/'video')
        self.assertFalse((self.root/'video').exists())

    def test_state_staleness_signature_expiry_and_revision_binding(self):
        key = self.create()
        prepared = self.store.prepare_consent(key)
        p = self.store.load(key)
        self.store._event(p, 'local_review_only')
        with self.assertRaisesRegex(CompanyError, 'consent_state_changed'):
            self.store.approve_consent(key, prepared['review_hash'], owner_confirmed=True, free_project_confirmed=True)
        prepared = self.store.prepare_consent(key)
        self.store.clarify(key, '수정한 목표 조건')
        with self.assertRaises(CompanyError):
            self.store.approve_consent(key, prepared['review_hash'], owner_confirmed=True, free_project_confirmed=True)
        self.approve(key)
        p = self.store.load(key)
        p['grants'][-1]['record']['body']['policy']['max_cost'] = 100
        self.store.save(p)
        with self.assertRaisesRegex(CompanyError, 'invalid_consent_signature'): self.ask(key)
        self.approve(key)
        future = (datetime.fromisoformat(live.now())+timedelta(hours=2)).isoformat()
        with patch('goal_dialogue_live.now', return_value=future):
            with self.assertRaisesRegex(CompanyError, 'consent_expired'): self.ask(key)
        self.transport.assert_not_called()
        # User-supplied spec changes and notes are in the reviewed transmission payload.
        p = self.store.load(key)
        changed = spec(p); changed['style'] = dict(value='다큐', evidence=[])
        self.store.revise(key, changed)
        self.store.clarify(key, '명세 수정 후 추가 검토')
        prepared = self.store.prepare_consent(key)
        self.assertEqual(prepared['transmission']['user_spec_revisions'][-1], changed)
        self.assertEqual(prepared['body']['payload_hash'], digest(payload_for(self.store.load(key))))

    def test_failed_responses_and_transport_are_consumed_without_replay(self):
        bad = dict(questions=[], sufficient=True, spec={})
        cases = [
            ('malformed', b'{'),
            ('invalid_spec', json.dumps(envelope(bad)).encode()),
            ('refused', json.dumps(envelope({}, promptFeedback=dict(blockReason='SAFETY'))).encode()),
            ('truncated', json.dumps(dict(candidates=[dict(finishReason='MAX_TOKENS')])).encode()),
            ('paid', json.dumps(envelope({}, usageMetadata=dict(cost=1))).encode()),
            ('oversize', b' ' * 131073),
            ('timeout', TimeoutError('sensitive arbitrary provider text')),
        ]
        for name, raw in cases:
            with self.subTest(case=name):
                key = self.create(); self.approve(key)
                if isinstance(raw, Exception): self.transport.side_effect = raw
                else: self.transport.side_effect = lambda *a, data=raw, **kw: BytesIO(data)
                with self.assertRaises(CompanyError): self.ask(key)
                p = self.store.load(key)
                self.assertEqual(p['real_ai']['attempts'][0]['status'], 'uncertain')
                count = self.transport.call_count
                with self.assertRaises(CompanyError): self.ask(key)
                with self.assertRaises(CompanyError): self.store.prepare_consent(key)
                self.assertEqual(count, self.transport.call_count)
                self.assertNotIn('sensitive arbitrary', json.dumps(p))

    def test_budget_interrupt_duplicate_response_secret_and_lock(self):
        key = self.create(max_rounds=1); self.approve(key)
        self.response(dict(questions=[], sufficient=True, spec=spec(self.store.load(key))))
        self.ask(key)
        self.store.clarify(key, '추가 조건')
        with self.assertRaises(CompanyError): self.store.prepare_consent(key)
        self.assertEqual(len(self.store.load(key)['real_ai']['attempts']), 1)
        key = self.create(); self.approve(key)
        self.transport.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.ask(key)
        self.assertEqual(self.store.load(key)['real_ai']['attempts'][0]['status'], 'reserved')
        with self.assertRaises(CompanyError): LiveDialogueStore(self.store.root).prepare_consent(key)
        key = self.create(); self.approve(key)
        result = dict(questions=[], sufficient=True, spec=spec(self.store.load(key)))
        result['spec']['summary'] = self.key
        self.response(result)
        with self.assertRaisesRegex(CompanyError, 'secret_in_response'): self.ask(key)
        self.assertNotIn(self.key, self.store.path(key).read_text())
        key = self.create(); self.approve(key)
        def locked(request, timeout):
            with self.assertRaisesRegex(CompanyError, 'project_busy'):
                self.store.prepare_consent(key)
            return BytesIO(json.dumps(envelope(dict(questions=[], sufficient=True, spec=spec(self.store.load(key))))).encode())
        self.transport.side_effect = locked
        self.ask(key)

    def test_duplicate_questions_and_invalid_evidence_rejected(self):
        for invalid in ('duplicate', 'evidence'):
            key = self.create(); self.approve(key)
            p = self.store.load(key)
            result = json.loads(AdaptiveMock().respond(p))
            if invalid == 'duplicate': result['questions'] *= 2
            else: result['spec']['audience']['evidence'] = ['not-answered']
            self.response(result)
            with self.assertRaises(CompanyError): self.ask(key)
            self.assertEqual(self.store.load(key)['real_ai']['attempts'][-1]['status'], 'uncertain')

    def test_cli_live_no_json_authorize_answer_revise_confirm_handoff(self):
        from goal_dialogue_cli import main
        root = str(self.store.root)
        prefix = ['--live', '--root', root]
        output = self.enterContext(patch('builtins.print'))
        self.assertEqual(main(prefix+['create', '안전 교육 영상']), 0)
        key = next(self.store.root.glob('dialogue-*.json')).stem
        self.assertEqual(main(prefix+['prepare-consent', key]), 0)
        body = json.loads(self.store._proposal_path(key).read_text())
        self.assertEqual(main(prefix+['approve-consent', key, digest(body), '--owner-confirmed', '--verified-free-project']), 0)
        self.assertEqual(main(prefix+['ask-ai', key]), 2)  # Default gate remains closed.
        self.assertEqual(self.transport.call_count, 0)
        for number in range(2):
            p = self.store.load(key)
            value = json.loads(AdaptiveMock().respond(p))
            self.response(value)
            with patch('goal_dialogue_live.LIVE_TRANSPORT_ENABLED', True), patch.dict('os.environ', GEMINI_API_KEY=self.key):
                self.assertEqual(main(prefix+['ask-ai', key]), 0)
            if number == 0:
                with patch('builtins.input', return_value='성인'):
                    self.assertEqual(main(prefix+['answer', key, 'audience']), 0)
                self.assertEqual(main(prefix+['revise', key, '--text', '따뜻한 분위기']), 0)
                self.assertEqual(main(prefix+['prepare-consent', key]), 0)
                body = json.loads(self.store._proposal_path(key).read_text())
                self.assertEqual(main(prefix+['approve-consent', key, digest(body), '--owner-confirmed', '--verified-free-project']), 0)
        with patch('builtins.input', return_value='확정'):
            self.assertEqual(main(prefix+['confirm', key]), 0)
        self.assertEqual(main(prefix+['handoff', key, '--projects', str(self.root/'video')]), 0)
        rendered = '\n'.join(str(call) for call in output.call_args_list)
        self.assertIn('누가 보나요?', rendered)
        self.assertIn('검토 해시', rendered)
        self.assertNotIn(self.key, rendered)


class OneCallAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.store = live.OneCallAcceptanceStore(self.root/'acceptance')
        self.draft_id = self.store.create()['id']
        self.key = 'acceptance-test-credential'
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden')))
        self.transport = self.enterContext(patch('goal_dialogue_live.send_once'))

    def verify(self):
        return self.store.verify_project_key(self.draft_id, api_key=self.key, project_api_key=self.key,
            project=live.ACCEPTANCE_PROJECT, free_tier_confirmed=True, billing_disabled=True)

    def approve(self):
        prepared = self.store.prepare_consent(self.draft_id)
        self.store.approve_consent(self.draft_id, prepared['review_hash'], owner_confirmed=True,
            free_project_confirmed=True, google_data_policy_accepted=True)
        return prepared

    def test_prepare_requires_real_local_key_comparison_and_explicit_data_consent(self):
        prepared = self.store.prepare_consent(self.draft_id)
        self.assertFalse(live.LIVE_TRANSPORT_ENABLED)
        self.assertFalse(live.POLICY['account_quota_verified'])
        self.assertEqual(prepared['body']['total_limit'], 1)
        self.assertEqual(prepared['body']['policy']['scope_hash'], live.ACCEPTANCE_SCOPE_HASH)
        self.assertEqual(digest(prepared['wire_payload']), prepared['body']['payload_hash'])
        self.assertEqual(prepared['transmission']['goal'], live.ACCEPTANCE_GOAL)
        self.assertEqual(prepared['transmission']['max_rounds'], 2)  # Allows questions, not a second call.
        self.assertEqual(prepared['transmission']['answers'], {})
        with self.assertRaises(CompanyError): self.store.ask_ai(self.draft_id, api_key=self.key)
        with self.assertRaises(CompanyError): self.store.approve_consent(self.draft_id, prepared['review_hash'],
            owner_confirmed=True, free_project_confirmed=True, google_data_policy_accepted=True)
        for changed in (dict(project_api_key='other'), dict(billing_disabled=False),
                        dict(free_tier_confirmed=False), dict(project='other project')):
            options = dict(api_key=self.key, project_api_key=self.key, project=live.ACCEPTANCE_PROJECT,
                           free_tier_confirmed=True, billing_disabled=True)
            options.update(changed)
            with self.assertRaises(CompanyError): self.store.verify_project_key(self.draft_id, **options)
        self.verify()
        with self.assertRaises(CompanyError): self.store.approve_consent(self.draft_id, prepared['review_hash'],
            owner_confirmed=True, free_project_confirmed=True, google_data_policy_accepted=True)
        prepared = self.store.prepare_consent(self.draft_id)
        with self.assertRaisesRegex(CompanyError, 'google_unpaid_data_consent_required'):
            self.store.approve_consent(self.draft_id, prepared['review_hash'], owner_confirmed=True, free_project_confirmed=True)
        with self.assertRaises(CompanyError): self.store.approve_consent(self.draft_id, 'wrong-hash',
            owner_confirmed=True, free_project_confirmed=True, google_data_policy_accepted=True)
        self.transport.assert_not_called()
        self.assertFalse(self.store.load(self.draft_id)['real_ai']['attempts'])
        self.assertNotIn(self.key, ''.join(p.read_text() for p in self.store.root.glob('*.json')))

    def test_one_scoped_native_request_questions_usage_and_no_global_unlock(self):
        self.verify(); self.approve()
        def response(request, timeout):
            disk = self.store.load(self.draft_id)
            self.assertEqual(len(disk['real_ai']['attempts']), 1)
            self.assertEqual(disk['real_ai']['attempts'][0]['status'], 'reserved')
            body = json.loads(request.data)
            self.assertEqual(body['generationConfig']['maxOutputTokens'], 4096)
            self.assertEqual(request.full_url, live.ENDPOINT)
            value = json.loads(AdaptiveMock().respond(disk))
            return BytesIO(json.dumps(envelope(value)).encode())
        self.transport.side_effect = response
        result = self.store.ask_ai(self.draft_id, api_key=self.key)  # Global gate stays FALSE.
        self.assertEqual(len(result['questions']), 1)
        self.assertEqual(result['real_ai']['attempts'][0]['usage']['total_tokens'], 30)
        self.assertEqual(result['real_ai']['attempts'][0]['status'], 'completed')
        self.store.answer(self.draft_id, 'audience', 'AI 초보자')
        with self.assertRaises(CompanyError): self.store.ask_ai(self.draft_id, api_key=self.key)
        with self.assertRaises(CompanyError): live.OneCallAcceptanceStore(self.store.root).create()
        with self.assertRaises(CompanyError): self.store.prepare_consent(self.draft_id)
        with self.assertRaises(CompanyError): self.store.handoff_video(self.draft_id, self.root/'video')
        self.assertFalse((self.root/'video').exists())
        self.assertEqual(self.transport.call_count, 1)
        ordinary = LiveDialogueStore(self.root/'ordinary')
        key = ordinary.create('일반 문답')['id']
        prepared = ordinary.prepare_consent(key)
        ordinary.approve_consent(key, prepared['review_hash'], owner_confirmed=True, free_project_confirmed=True)
        with self.assertRaisesRegex(CompanyError, 'live_transport_disabled'):
            ordinary.ask_ai(key, api_key=self.key)
        self.assertFalse(live.LIVE_TRANSPORT_ENABLED)
        self.assertFalse(live.POLICY['account_quota_verified'])
        self.assertEqual(self.transport.call_count, 1)

    def test_changed_key_account_signature_expiry_input_and_mode_blocked(self):
        self.verify(); self.approve()
        with self.assertRaisesRegex(CompanyError, 'active_key_changed'):
            self.store.ask_ai(self.draft_id, api_key='different-credential')
        with self.assertRaisesRegex(CompanyError, 'fixed_gemini_binding_required'):
            self.store.ask_ai(self.draft_id, api_key=self.key, endpoint='https://example.com')
        p = self.store.load(self.draft_id)
        p['acceptance']['verification']['record']['project'] = 'tampered'
        self.store.save(p)
        with self.assertRaises(CompanyError): self.store.ask_ai(self.draft_id, api_key=self.key)
        self.verify(); self.approve()
        future = (datetime.fromisoformat(live.now())+timedelta(hours=2)).isoformat()
        with patch('goal_dialogue_live.now', return_value=future):
            with self.assertRaises(CompanyError): self.store.ask_ai(self.draft_id, api_key=self.key)
        with self.assertRaises(CompanyError): LiveDialogueStore(self.store.root).load(self.draft_id)
        self.store.clarify(self.draft_id, '추가 자료 전송 금지')
        with self.assertRaisesRegex(CompanyError, 'acceptance_scope_changed'):
            self.store.prepare_consent(self.draft_id)
        self.transport.assert_not_called()

    def test_timeout_interrupt_invalid_json_and_rate_limit_consume_attempt(self):
        from urllib.error import HTTPError
        for index, failure in enumerate((TimeoutError(), KeyboardInterrupt(), b'{',
                                        HTTPError(live.ENDPOINT, 429, 'do not log', {}, None))):
            self.store = live.OneCallAcceptanceStore(self.root/('failure-'+str(index)))
            self.draft_id = self.store.create()['id']
            self.verify(); self.approve()
            if isinstance(failure, BaseException): self.transport.side_effect = failure
            else: self.transport.side_effect = lambda *a, **kw: BytesIO(failure)
            with self.assertRaises((CompanyError, KeyboardInterrupt)):
                self.store.ask_ai(self.draft_id, api_key=self.key)
            p = self.store.load(self.draft_id)
            self.assertEqual(len(p['real_ai']['attempts']), 1)
            self.assertIn(p['real_ai']['attempts'][0]['status'], ('reserved', 'uncertain'))
            if isinstance(failure, HTTPError): self.assertEqual(p['real_ai']['attempts'][0]['http_status'], 429)
            count = self.transport.call_count
            with self.assertRaises(CompanyError): self.store.ask_ai(self.draft_id, api_key=self.key)
            with self.assertRaises(CompanyError): self.store.create()
            self.assertEqual(count, self.transport.call_count)
            self.assertNotIn('do not log', json.dumps(p))

    def test_cli_secure_input_review_and_scoped_single_request(self):
        root = str(self.store.root)
        prefix = ['--acceptance', '--root', root]
        output = self.enterContext(patch('builtins.print'))
        self.enterContext(patch.dict('os.environ', GEMINI_API_KEY=self.key))
        self.assertEqual(main(prefix+['prepare-consent', self.draft_id]), 0)
        with patch('sys.stdin.isatty', return_value=False):
            self.assertEqual(main(prefix+['verify-acceptance-key', self.draft_id, '--free-tier-confirmed', '--billing-disabled']), 2)
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value=self.key):
            self.assertEqual(main(prefix+['verify-acceptance-key', self.draft_id, '--free-tier-confirmed', '--billing-disabled']), 0)
        self.assertEqual(main(prefix+['prepare-consent', self.draft_id]), 0)
        body = json.loads(self.store._proposal_path(self.draft_id).read_text())
        self.assertEqual(main(prefix+['approve-consent', self.draft_id, digest(body), '--owner-confirmed',
                                     '--verified-free-project', '--accept-google-data-policy']), 0)
        self.transport.side_effect = lambda *a, **kw: BytesIO(json.dumps(envelope(dict(questions=[], sufficient=True,
            spec=spec(self.store.load(self.draft_id))))).encode())
        self.assertEqual(main(prefix+['ask-ai', self.draft_id]), 0)
        self.assertEqual(main(prefix+['ask-ai', self.draft_id]), 2)
        self.assertEqual(self.transport.call_count, 1)
        rendered = '\n'.join(str(call) for call in output.call_args_list)
        self.assertIn('전체 요청 본문', rendered)
        self.assertIn('제품 개선', rendered)
        self.assertNotIn(self.key, rendered)
