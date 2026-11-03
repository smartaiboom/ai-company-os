"""Second authorization: fictional projects, blocked network, fake transport only."""
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

import app
import manager_decision as md
import real_manager_second_tool as tool
from tests.test_real_manager_decision import RealManagerDecisionTests


class SecondAuthorizationTests(RealManagerDecisionTests):
    def prepare_second(self):
        self.prepare()
        p = self.saved()
        # Three fictional completed calls, including the stopped first manager.
        p['real_ai']['attempts'] = [dict(id=str(i), kind='manager_decision' if i == 2 else 'task',
            task_id='TASK-001', model='openrouter/free', status='completed', input_bytes=1) for i in range(3)]
        p['manager_decisions'] = {'enabled': True, 'provider': 'real_openrouter_free',
            'authorization': {'old': '첫 승인 보존'}, 'proposals': [], 'answers': []}
        p['history'].append({'event': 'real_manager_stopped', 'details': '과거 원인 불명'})
        app.save_project(p)
        self.old_guard = app.PROJECTS_DIR / 'first.guard'
        self.old_guard.write_text('기존 guard')
        self.guard = app.PROJECTS_DIR / 'second.guard'
        return self.saved()

    def second(self, confirmed=True):
        return tool.run_once(self.p['id'], md.digest(self.saved()), authorization_id='a'*32,
                             guard_path=self.guard, user_confirmed=confirmed)

    def test_second_four_actions_restart_and_preservation(self):
        original = self.prepare_second()
        for action in sorted(md.ACTIONS):
            with self.subTest(action=action):
                app.save_project(deepcopy(original))
                self.guard = app.PROJECTS_DIR / (action + '.guard')
                with patch('manager_decision.urlopen', side_effect=self.transport(action)) as transport:
                    proposal = self.second()
                    with self.assertRaises(ValueError): self.second()
                    transport.assert_called_once()
                p = self.saved()
                self.assertEqual(len(p['real_ai']['attempts']), 4)
                self.assertEqual(p['real_ai']['attempts'][:3], original['real_ai']['attempts'])
                self.assertEqual(p['manager_decisions']['authorization'], original['manager_decisions']['authorization'])
                self.assertEqual(proposal['authorization_id'], 'a'*32)
                self.assertEqual(self.old_guard.read_text(), '기존 guard')
                self.assertEqual(p['tasks'], original['tasks'])
                code = 'import app,json,sys;from pathlib import Path;app.PROJECTS_DIR=Path(sys.argv[1]);print(json.dumps(app.manager_decision_view(sys.argv[2])))'
                read = subprocess.run([sys.executable, '-B', '-c', code, str(app.PROJECTS_DIR), p['id']], capture_output=True, text=True, check=True)
                view = json.loads(read.stdout)[0]
                self.assertFalse(view['stale']); self.assertEqual(view['status'], 'pending_user_decision')
                executor = Mock()
                with self.assertRaises(ValueError): app.execute_project_task(p['id'], 'TASK-002', executor=executor)
                executor.assert_not_called()

    def test_second_errors_and_competing_state(self):
        original = self.prepare_second()
        for mode in ('finish', 'binding', 'timeout', 'result', 'ledger'):
            with self.subTest(mode=mode):
                app.save_project(deepcopy(original)); self.guard = app.PROJECTS_DIR / (mode+'.guard')
                def mutate(d):
                    if mode == 'binding': d['binding']['project_id'] = 'other'
                    if mode in ('result', 'ledger'):
                        p = self.saved()
                        if mode == 'result': p['tasks'][0]['result'] = '경합 결과'
                        else: p['real_ai']['attempts'][-1]['input_bytes'] += 1
                        app.save_project(p)
                fake = self.transport(mutate=mutate, finish='length' if mode == 'finish' else 'stop')
                with patch('manager_decision.urlopen', side_effect=TimeoutError('PRIVATE') if mode == 'timeout' else fake) as transport:
                    with self.assertRaises(RuntimeError): self.second()
                    with self.assertRaises(ValueError): self.second()
                    transport.assert_called_once()
                p = self.saved()
                self.assertEqual(p['manager_decisions']['proposals'], [])
                self.assertEqual(p['real_ai']['attempts'][:3], original['real_ai']['attempts'])
                self.assertIn('stage', p['history'][-1])
                if mode == 'result': self.assertEqual(p['tasks'][0]['result'], '경합 결과')
                # Even removing the tool guard cannot reuse the recorded approval.
                with patch('manager_decision.urlopen') as transport:
                    with self.assertRaises(ValueError):
                        app.propose_real_manager_second_authorized(p['id'], 'TASK-001', md.digest(p),
                            authorization_id='b'*32, user_confirmed=True, reason='새 승인 주장')
                    transport.assert_not_called()

    def test_second_needs_new_confirmation_and_guard(self):
        original = self.prepare_second()
        with patch('manager_decision.urlopen') as transport:
            with self.assertRaises(ValueError): self.second(False)
            with self.assertRaises(ValueError):
                app.propose_real_manager_second_authorized(self.p['id'], 'TASK-001', md.digest(self.saved()),
                    authorization_id='a'*32, reason='확인 없음')
            self.guard.write_text('이미 사용된 guard')
            with self.assertRaises(FileExistsError): self.second()
            transport.assert_not_called()
        self.assertEqual(self.saved(), original)
