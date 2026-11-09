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
