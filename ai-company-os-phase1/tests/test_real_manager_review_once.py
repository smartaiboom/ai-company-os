"""New one-shot review authorization: temporary fictional data and fake network only."""
import json
import os
import subprocess
import sys
from copy import deepcopy
from unittest.mock import Mock, patch
import app
import manager_decision as md
import real_manager_review_tool as tool
from tests.test_manager_pending_review import PendingReviewTests
from tests.test_real_ai_safety_budget import Response


class RealReviewOnceTests(PendingReviewTests):
    def prepare_real_review(self):
        PendingReviewTests.prepare(self)
        self.enterContext(patch.object(tool, 'PROJECT_ID', self.p['id']))
        self.enterContext(patch.dict(os.environ, {'AI_ENGINE':'openai_compatible','AI_MODEL':'openrouter/free',
            'AI_API_BASE_URL':'https://openrouter.ai/api/v1','AI_API_KEY':'FICTIONAL','AI_REAL_REQUESTS_ENABLED':'1'}, clear=True))
        p = self.saved()
        p['manager_decisions']['provider'] = 'real_openrouter_free'
        p['manager_decisions']['proposals'][0]['provider'] = 'real_openrouter_free'
        p['real_ai']['consent']['goal_hash'] = __import__('ai_safety').goal_hash(p['goal'])
        for i, a in enumerate(p['real_ai']['attempts']):
            a['kind'] = ['plan','task','manager_decision','manager_decision','manager_decision','task'][i]
            a['task_id'] = None if i == 0 else 'TASK-002' if i == 5 else 'TASK-001'
        p['manager_decisions']['proposals'][0]['decision']['binding'] = md.decision_input(p, 'TASK-001')['binding']
        app.save_project(p)
        self.guard = app.PROJECTS_DIR / 'real-review.guard'
        return self.saved()

    def run_review(self, confirmed=True, task_id='TASK-002', purpose=md.REVIEW_PURPOSE):
        return tool.run_once(self.p['id'], task_id, md.digest(self.saved()), authorization_id='e'*32,
            guard_path=self.guard, user_confirmed=confirmed, purpose=purpose)

    def transport_review(self, action='request_revision', mutate=None, finish='stop'):
        def fake(request, **kwargs):
            p = self.saved(); ledger = p['real_ai']['attempts']
            self.assertEqual(len(ledger), 7); self.assertEqual(ledger[-1]['status'], 'reserved')
            self.assertEqual(ledger[-1]['task_id'], 'TASK-002')
            observation = json.loads(self.guard.with_suffix('.observation.json').read_text())
            self.assertEqual(observation['transport_calls'], 1)
            body = json.loads(request.data); data = json.loads(body['messages'][1]['content'])
            self.assertEqual(data['purpose'], md.REVIEW_PURPOSE)
            self.assertNotIn('binding', data)
            self.assertNotIn('다른프로젝트비밀', json.dumps(data, ensure_ascii=False))
            value = self.value(app._manager_review_input(p, 'TASK-002'), action)
            if mutate: mutate(value)
            return Response({'choices':[{'finish_reason':finish,'message':{'content':json.dumps(value,ensure_ascii=False)}}]})
        return fake

    def test_real_review_four_actions_once_restart_and_preservation(self):
        original = self.prepare_real_review()
        for action in sorted(md.ACTIONS):
            with self.subTest(action=action):
                app.save_project(deepcopy(original)); self.guard = app.PROJECTS_DIR / (action + '.guard')
                with patch('manager_decision.urlopen', side_effect=self.transport_review(action)) as sender:
                    proposal = self.run_review()
                    with self.assertRaises(ValueError): self.run_review()
                    sender.assert_called_once()
                p = self.saved()
                self.assertEqual(p['tasks'], original['tasks'])
                self.assertEqual(p['real_ai']['attempts'][:6], original['real_ai']['attempts'])
                self.assertEqual(p['manager_decisions']['proposals'][0], original['manager_decisions']['proposals'][0])
                self.assertEqual(proposal['authorization_id'], 'e'*32)
                self.assertEqual(proposal['purpose'], md.REVIEW_PURPOSE)
                self.assertEqual(proposal['provider'], 'real_openrouter_free')
                view = app.manager_decision_view(p['id'])[-1]
                self.assertFalse(view['stale']); self.assertEqual(view['status'],'pending_user_decision')
                code = 'import sys,json,app;from pathlib import Path;app.PROJECTS_DIR=Path(sys.argv[1]);print(json.dumps(app.manager_decision_view(sys.argv[2])))'
                read = subprocess.run([sys.executable,'-B','-c',code,str(app.PROJECTS_DIR),p['id']],capture_output=True,text=True,check=True)
                self.assertFalse(json.loads(read.stdout)[-1]['stale'])
                executor = Mock()
                with self.assertRaises(ValueError): app.execute_project_task(p['id'],'TASK-003',executor=executor)
                executor.assert_not_called()
                self.assertEqual(self.old_guard.read_text(),'기존 guard 보존')
                self.assertEqual(self.other.read_text(),'{"reservation":"보존"}')
                self.guard.unlink()  # Fictional guard only; ledger/history still block.
                with patch('manager_decision.urlopen') as sender:
                    with self.assertRaises(ValueError): self.run_review()
                    sender.assert_not_called()

    def test_real_review_preconditions_and_no_authorization(self):
        original = self.prepare_real_review()
        for mode in ('confirmation','task','purpose','project','guard','budget','reserved','oldledger','approved','history','hash'):
            with self.subTest(mode=mode):
                p = deepcopy(original); self.guard = app.PROJECTS_DIR / (mode + '.guard')
                if mode == 'budget': p['real_ai']['limit'] = 6
                if mode == 'reserved': p['real_ai']['attempts'][-1]['status'] = 'reserved'
                if mode == 'oldledger': p['real_ai']['attempts'][0]['kind'] = 'other'
                if mode == 'approved': p['tasks'][1]['review_status'] = 'approved'
                if mode == 'history': p['history'].append({'event':'real_manager_review_once_authorized'})
                if mode == 'guard': self.guard.write_text('이미 사용')
                app.save_project(p)
                with patch('manager_decision.urlopen') as sender:
                    with self.assertRaises((ValueError,FileExistsError)):
                        if mode == 'project':
                            with patch.object(tool,'PROJECT_ID','other'): self.run_review()
                        elif mode == 'hash': tool.run_once(p['id'],'TASK-002','stale',authorization_id='e'*32,guard_path=self.guard,user_confirmed=True)
                        else: self.run_review(mode != 'confirmation', 'TASK-001' if mode == 'task' else 'TASK-002', 'other' if mode == 'purpose' else md.REVIEW_PURPOSE)
                    sender.assert_not_called()
                self.assertEqual(self.saved()['real_ai']['attempts'],p['real_ai']['attempts'])

    def test_real_review_failures_races_timeout_no_retry(self):
        original = self.prepare_real_review()
        for mode in ('timeout','finish','payload','result','plan','predecessor','pending','ledger'):
            with self.subTest(mode=mode):
                app.save_project(deepcopy(original)); self.guard = app.PROJECTS_DIR / (mode + '.guard')
                def mutate(value):
                    if mode == 'payload': value['payload']['task_id'] = 'TASK-001'
                    if mode in ('result','plan','predecessor','pending','ledger'):
                        p = self.saved()
                        if mode == 'result': p['tasks'][1]['result'] += '경합'
                        if mode == 'plan': p['plan']['version'] = 22
                        if mode == 'predecessor': p['tasks'][0]['result'] += '경합'
                        if mode == 'pending': p['tasks'][1]['review_status'] = 'approved'
                        if mode == 'ledger': p['real_ai']['attempts'][-1]['input_bytes'] += 1
                        app.save_project(p)
                with patch('manager_decision.urlopen',side_effect=TimeoutError('PRIVATE') if mode == 'timeout' else self.transport_review(mutate=mutate,finish='length' if mode == 'finish' else 'stop')) as sender:
                    with self.assertRaises(RuntimeError): self.run_review()
                    with self.assertRaises(ValueError): self.run_review()
                    sender.assert_called_once()
                p = self.saved()
                self.assertEqual(len(p['manager_decisions']['proposals']),1)
                self.assertEqual(p['real_ai']['attempts'][:6],original['real_ai']['attempts'])
                self.assertIn('stage',p['history'][-1]); self.assertNotIn('PRIVATE',json.dumps(p))
                if mode == 'result': self.assertTrue(p['tasks'][1]['result'].endswith('경합'))

    def test_real_review_storage_failure_consumes_new_authorization(self):
        original = self.prepare_real_review(); save = app.save_project
        for mode in ('reservation_persist','ledger_persist','proposal_persist'):
            with self.subTest(mode=mode):
                save(deepcopy(original)); self.guard = app.PROJECTS_DIR / (mode + '.guard'); failed = False
                def fail_once(p):
                    nonlocal failed
                    ledger = p['real_ai']['attempts']
                    if not failed and ((mode == 'reservation_persist' and len(ledger)==7 and ledger[-1]['status']=='reserved')
                        or (mode == 'ledger_persist' and len(ledger)==7 and ledger[-1]['status']=='completed')
                        or (mode == 'proposal_persist' and len(p['manager_decisions']['proposals'])==2)):
                        failed = True; raise OSError('PRIVATE')
                    return save(p)
                with patch('app.save_project',side_effect=fail_once), patch('manager_decision.urlopen',side_effect=self.transport_review()) as sender:
                    with self.assertRaises(RuntimeError): self.run_review()
                    self.assertEqual(sender.call_count,0 if mode=='reservation_persist' else 1)
                self.guard.unlink()
                with patch('manager_decision.urlopen') as sender:
                    with self.assertRaises(ValueError): self.run_review()
                    sender.assert_not_called()
                self.assertEqual(self.saved()['history'][-1]['stage'],mode)
                self.assertEqual(len(self.saved()['manager_decisions']['proposals']),1)

    def test_real_review_lock_blocks_before_guard_and_transport(self):
        original = self.prepare_real_review()
        with app.project_mutation_lock(original['id']), patch('manager_decision.urlopen') as sender:
            with self.assertRaises(ValueError): self.run_review()
            sender.assert_not_called()
        self.assertEqual(self.saved(), original)
        self.assertFalse(self.guard.exists())
