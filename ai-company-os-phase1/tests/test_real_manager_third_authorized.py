"""Third authorization: fictional projects, blocked network, fake transport only."""
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

import app
import manager_decision as md
import real_manager_third_tool as tool
from tests.test_real_manager_decision import RealManagerDecisionTests


class ThirdAuthorizationTests(RealManagerDecisionTests):
    def prepare_third(self):
        RealManagerDecisionTests.prepare(self)
        p = self.saved()
        # Four fictional completed calls, including the stopped first manager.
        p['real_ai']['attempts'] = [dict(id=str(i), kind='manager_decision' if i >= 2 else 'task',
            task_id='TASK-001', model='openrouter/free', status='completed', input_bytes=1) for i in range(4)]
        p['manager_decisions'] = {'enabled': True, 'provider': 'real_openrouter_free',
            'authorization': {'old': '첫 승인 보존'}, 'proposals': [], 'answers': [], 'additional_authorizations': [{'id': 'c'*32, 'attempt_number': 2}]}
        p['history'].append({'event': 'real_manager_stopped', 'details': '과거 원인 불명'})
        p['history'].append({'event': 'real_manager_stopped', 'details': '두 번째 중단'})
        app.save_project(p)
        self.old_guard = app.PROJECTS_DIR / 'first.guard'
        self.old_guard.write_text('기존 guard')
        self.guard = app.PROJECTS_DIR / 'third.guard'
        return self.saved()

    def third(self, confirmed=True):
        return tool.run_once(self.p['id'], md.digest(self.saved()), authorization_id='a'*32,
                             guard_path=self.guard, user_confirmed=confirmed)

    def test_third_four_actions_restart_and_preservation(self):
        original = self.prepare_third()
        for action in sorted(md.ACTIONS):
            with self.subTest(action=action):
                app.save_project(deepcopy(original))
                self.guard = app.PROJECTS_DIR / (action + '.guard')
                with patch('manager_decision.urlopen', side_effect=self.transport(action)) as transport:
                    proposal = self.third()
                    with self.assertRaises(ValueError): self.third()
                    transport.assert_called_once()
                p = self.saved()
                self.assertEqual(len(p['real_ai']['attempts']), 5)
                self.assertEqual(p['real_ai']['attempts'][:4], original['real_ai']['attempts'])
                self.assertEqual(p['manager_decisions']['authorization'], original['manager_decisions']['authorization'])
                self.assertEqual(proposal['authorization_id'], 'a'*32)
                self.assertEqual(self.old_guard.read_text(), '기존 guard')
                self.assertEqual(p['tasks'], original['tasks'])
                self.assertEqual(p['manager_decisions']['additional_authorizations'][:1], original['manager_decisions']['additional_authorizations'])
                self.assertEqual(p['manager_decisions']['additional_authorizations'][-1]['previous_attempt_ids'], ['2', '3'])
                code = 'import app,json,sys;from pathlib import Path;app.PROJECTS_DIR=Path(sys.argv[1]);print(json.dumps(app.manager_decision_view(sys.argv[2])))'
                read = subprocess.run([sys.executable, '-B', '-c', code, str(app.PROJECTS_DIR), p['id']], capture_output=True, text=True, check=True)
                view = json.loads(read.stdout)[0]
                self.assertFalse(view['stale']); self.assertEqual(view['status'], 'pending_user_decision')
                executor = Mock()
                with self.assertRaises(ValueError): app.execute_project_task(p['id'], 'TASK-002', executor=executor)
                executor.assert_not_called()

    def test_third_errors_and_competing_state(self):
        original = self.prepare_third()
        for mode in ('finish', 'binding', 'timeout', 'result', 'ledger'):
            with self.subTest(mode=mode):
                app.save_project(deepcopy(original)); self.guard = app.PROJECTS_DIR / (mode+'.guard')
                def mutate(d):
                    if mode == 'binding': d['binding'] = {'project_id': 'other'}
                    if mode in ('result', 'ledger'):
                        p = self.saved()
                        if mode == 'result': p['tasks'][0]['result'] = '경합 결과'
                        else: p['real_ai']['attempts'][-1]['input_bytes'] += 1
                        app.save_project(p)
                fake = self.transport(mutate=mutate, finish='length' if mode == 'finish' else 'stop')
                with patch('manager_decision.urlopen', side_effect=TimeoutError('PRIVATE') if mode == 'timeout' else fake) as transport:
                    with self.assertRaises(RuntimeError): self.third()
                    with self.assertRaises(ValueError): self.third()
                    transport.assert_called_once()
                p = self.saved()
                self.assertEqual(p['manager_decisions']['proposals'], [])
                self.assertEqual(p['real_ai']['attempts'][:4], original['real_ai']['attempts'])
                self.assertIn('stage', p['history'][-1])
                if mode == 'result': self.assertEqual(p['tasks'][0]['result'], '경합 결과')
                # Even removing the tool guard cannot reuse the recorded approval.
                with patch('manager_decision.urlopen') as transport:
                    with self.assertRaises(ValueError):
                        app.propose_real_manager_third_authorized(p['id'], 'TASK-001', md.digest(p),
                            authorization_id='b'*32, user_confirmed=True, reason='새 승인 주장')
                    transport.assert_not_called()

    def test_third_needs_new_confirmation_and_guard(self):
        original = self.prepare_third()
        with patch('manager_decision.urlopen') as transport:
            with self.assertRaises(ValueError): self.third(False)
            with self.assertRaises(ValueError):
                app.propose_real_manager_third_authorized(self.p['id'], 'TASK-001', md.digest(self.saved()),
                    authorization_id='a'*32, reason='확인 없음')
            self.guard.write_text('이미 사용된 guard')
            with self.assertRaises(FileExistsError): self.third()
            transport.assert_not_called()
        self.assertEqual(self.saved(), original)

    def direct_third(self):
        return app.propose_real_manager_third_authorized(self.p['id'], 'TASK-001', md.digest(self.saved()),
            authorization_id='a'*32, user_confirmed=True, reason='가상 새 3차 승인')

    def test_third_diagnostics(self):
        with patch.object(self, 'prepare', self.prepare_third), patch.object(self, 'run_real', self.direct_third):
            RealManagerDecisionTests.test_diagnostic_response_boundaries_and_no_retry(self)

    def test_third_storage_failures(self):
        original = self.prepare_third()
        save = app.save_project
        for mode in ('reservation_persist', 'ledger_persist', 'proposal_persist'):
            with self.subTest(mode=mode):
                save(deepcopy(original))
                failed = False
                def failing_save(p):
                    nonlocal failed
                    a = p['real_ai']['attempts']
                    if not failed and ((mode == 'reservation_persist' and len(a) == 5 and a[-1]['status'] == 'reserved')
                        or (mode == 'ledger_persist' and len(a) == 5 and a[-1]['status'] == 'completed')
                        or (mode == 'proposal_persist' and p['manager_decisions']['proposals'])):
                        failed = True
                        raise OSError('PRIVATE')
                    return save(p)
                with patch('app.save_project', side_effect=failing_save), patch('manager_decision.urlopen', side_effect=self.transport()) as transport:
                    with self.assertRaises(RuntimeError): self.direct_third()
                    self.assertEqual(transport.call_count, 0 if mode == 'reservation_persist' else 1)
                p = self.saved()
                self.assertEqual(p['history'][-1]['stage'], mode)
                self.assertEqual(p['manager_decisions']['proposals'], [])
                self.assertEqual(p['tasks'], original['tasks'])
                self.assertEqual(p['real_ai']['attempts'][:4], original['real_ai']['attempts'])

    def test_third_preconditions_budget_and_previous_entrypoints(self):
        original = self.prepare_third()
        for mode in ('missing', 'duplicate', 'task', 'budget', 'reserved', 'history'):
            with self.subTest(mode=mode):
                p = deepcopy(original)
                if mode == 'missing': p['manager_decisions']['additional_authorizations'] = []
                if mode == 'duplicate': p['manager_decisions']['additional_authorizations'][0]['id'] = 'a'*32
                if mode == 'task': p['real_ai']['attempts'][-1]['task_id'] = 'TASK-002'
                if mode == 'budget': p['real_ai']['limit'] = 4
                if mode == 'reserved': p['real_ai']['attempts'][-1]['status'] = 'reserved'
                if mode == 'history': p['history'].append({'event': 'real_manager_third_authorized'})
                app.save_project(p)
                self.guard = app.PROJECTS_DIR / (mode + '-blocked.guard')
                with patch('manager_decision.urlopen') as transport:
                    with self.assertRaises(ValueError): self.third()
                    transport.assert_not_called()
        app.save_project(original)
        with patch('manager_decision.urlopen') as transport:
            with self.assertRaises(ValueError):
                app.propose_real_manager_decision_once(self.p['id'], 'TASK-001', md.digest(original), user_confirmed=True, reason='이전 승인')
            with self.assertRaises(ValueError):
                app.propose_real_manager_second_authorized(self.p['id'], 'TASK-001', md.digest(original), authorization_id='b'*32, user_confirmed=True, reason='이전 승인')
            with self.assertRaises(ValueError):
                app.propose_real_manager_third_authorized(self.p['id'], 'TASK-002', md.digest(original), authorization_id='a'*32, user_confirmed=True, reason='타 업무')
            transport.assert_not_called()
