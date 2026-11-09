"""Fictional projects and fake transport; no real data, keys or network."""
import json
from copy import deepcopy
from unittest.mock import patch
import app
import manager_decision as md
import real_task002_once_tool as tool
from tests.test_real_manager_decision import RealManagerDecisionTests
from tests.test_real_ai_safety_budget import Response


class Task002OnceTests(RealManagerDecisionTests):
    def prepare_employee(self):
        self.prepare()
        p = self.saved()
        p['real_ai']['attempts'] = [dict(id=str(i), kind='manager_decision' if i >= 2 else 'task',
            task_id='TASK-001', model='openrouter/free', status='completed', input_bytes=1) for i in range(5)]
        decision = self.decision(md.decision_input(p, 'TASK-001'))
        p['manager_decisions'] = {'enabled': True, 'provider': 'real_openrouter_free',
            'authorization': {'first': '보존'}, 'additional_authorizations': [{'second': '보존'}, {'third': '보존'}],
            'proposals': [{'id': 'proposal-fictional', 'version': 1, 'provider': 'real_openrouter_free',
                'status': 'pending_user_decision', 'decision': decision, 'attempt_id': '4'}], 'answers': []}
        p['manager_decisions']['proposals'][0]['decision'] = self.decision(md.decision_input(p, 'TASK-001'))
        app.save_project(p)
        self.guard = app.PROJECTS_DIR / 'employee.guard'
        self.other = app.PROJECTS_DIR / 'unrelated.json'
        self.other.write_text('{"reservation":"불확정 보존"}')
        self.old_guard = app.PROJECTS_DIR / 'manager.guard'
        self.old_guard.write_text('기존 guard')
        return self.saved()

    def employee(self, confirmed=True):
        return tool.run_once(self.p['id'], md.digest(self.saved()), authorization_id='d'*32,
                             guard_path=self.guard, user_confirmed=confirmed)

    def fake_employee(self, request, **kwargs):
        p = self.saved()
        self.assertEqual(len(p['real_ai']['attempts']), 6)
        self.assertEqual(p['real_ai']['attempts'][-1]['status'], 'reserved')
        body = json.loads(request.data)
        text = body['messages'][1]['content']
        self.assertIn(p['tasks'][0]['result'], text)
        self.assertIn(p['manager_decisions']['proposals'][0]['decision']['payload']['guidance'], text)
        self.assertNotIn('다른프로젝트비밀', text)
        obs = json.loads(self.guard.with_suffix('.observation.json').read_text())
        self.assertEqual(obs['transport_calls'], 1)
        return Response({'choices': [{'finish_reason': 'stop', 'message': {'content': '한국어 1분 대본\n도입: 질문에 목적을 더하세요.\n마무리: 생성 결과는 직접 확인하세요.'}}]})

    def test_employee_success_approval_preservation_and_duplicate(self):
        original = self.prepare_employee()
        with patch('execution_engine.urlopen', side_effect=self.fake_employee) as sender:
            p = self.employee()
            with self.assertRaises(ValueError): self.employee()
            sender.assert_called_once()
        self.assertEqual(p['real_ai']['attempts'][:5], original['real_ai']['attempts'])
        self.assertEqual(p['real_ai']['attempts'][-1]['status'], 'completed')
        self.assertEqual(p['tasks'][1]['status'], '완료')
        self.assertEqual(p['tasks'][1]['review_status'], 'pending')
        self.assertEqual(p['tasks'][0], original['tasks'][0])
        self.assertEqual(p['tasks'][2:], original['tasks'][2:])
        self.assertEqual(p['plan'], original['plan'])
        self.assertEqual(p['user_preferences'], original['user_preferences'])
        proposal = p['manager_decisions']['proposals'][0]
        self.assertEqual(proposal['status'], 'approved')
        self.assertEqual(proposal['decided_by'], '사용자')
        self.assertEqual(proposal['decision'], original['manager_decisions']['proposals'][0]['decision'])
        self.assertEqual(self.other.read_text(), '{"reservation":"불확정 보존"}')
        self.assertEqual(self.old_guard.read_text(), '기존 guard')
        self.guard.unlink()  # Fictional guard only: ledger/history must still block.
        with patch('execution_engine.urlopen') as sender:
            with self.assertRaises(ValueError): self.employee()
            sender.assert_not_called()

    def test_employee_preconditions_never_transmit(self):
        original = self.prepare_employee()
        for mode in ('approved', 'stale', 'budget', 'reserved', 'authorization', 'confirmation', 'guard', 'hash'):
            with self.subTest(mode=mode):
                p = deepcopy(original)
                self.guard = app.PROJECTS_DIR / (mode + '.guard')
                if mode == 'approved': p['manager_decisions']['proposals'][0]['status'] = 'approved'
                if mode == 'stale': p['tasks'][0]['result'] = '바뀐 결과'
                if mode == 'budget': p['real_ai']['limit'] = 5
                if mode == 'reserved': p['real_ai']['attempts'][-1]['status'] = 'reserved'
                if mode == 'authorization': p['history'].append({'event':'task002_once_authorized'})
                if mode == 'guard': self.guard.write_text('기존')
                app.save_project(p)
                with patch('execution_engine.urlopen') as sender:
                    with self.assertRaises((ValueError, FileExistsError)):
                        if mode == 'hash': tool.run_once(p['id'], 'stale', authorization_id='d'*32, guard_path=self.guard, user_confirmed=True)
                        else: self.employee(mode != 'confirmation')
                    sender.assert_not_called()
                self.assertEqual(self.saved()['real_ai']['attempts'], p['real_ai']['attempts'])

    def test_employee_failure_timeout_and_races_no_retry(self):
        original = self.prepare_employee()
        for mode in ('timeout', 'failure', 'ledger', 'project'):
            with self.subTest(mode=mode):
                app.save_project(deepcopy(original))
                self.guard = app.PROJECTS_DIR / (mode + '.guard')
                def fake(request, **kwargs):
                    if mode == 'timeout': raise TimeoutError('PRIVATE')
                    if mode == 'failure': raise OSError('PRIVATE')
                    p = self.saved()
                    if mode == 'ledger': p['real_ai']['attempts'][-1]['input_bytes'] += 1
                    else: p['user_preferences']['focus'] = '경합 보존'
                    app.save_project(p)
                    return Response()
                with patch('execution_engine.urlopen', side_effect=fake) as sender:
                    with self.assertRaises((ValueError, app.TaskExecutionFailure)): self.employee()
                    with self.assertRaises(ValueError): self.employee()
                    sender.assert_called_once()
                p = self.saved()
                self.assertEqual(p['real_ai']['attempts'][:5], original['real_ai']['attempts'])
                self.assertFalse(p['tasks'][1].get('result'))
                self.assertEqual(p['tasks'][2:], original['tasks'][2:])
                if mode == 'project': self.assertEqual(p['user_preferences']['focus'], '경합 보존')
                if mode in ('ledger', 'project'): self.assertEqual(p['real_ai']['attempts'][-1]['status'], 'reserved')
                self.assertNotIn('PRIVATE', json.dumps(p))

    def test_employee_approval_then_changed_project_stops_before_call(self):
        self.prepare_employee()
        respond = app.respond_manager_decision
        def mutate(*args, **kwargs):
            respond(*args, **kwargs)
            p = self.saved()
            p['user_preferences']['focus'] = '승인 뒤 경합 보존'
            app.save_project(p)
        with patch('app.respond_manager_decision', side_effect=mutate), patch('execution_engine.urlopen') as sender:
            with self.assertRaises(ValueError): self.employee()
            sender.assert_not_called()
        p = self.saved()
        self.assertEqual(len(p['real_ai']['attempts']), 5)
        self.assertEqual(p['manager_decisions']['proposals'][0]['status'], 'approved')
        self.assertEqual(p['user_preferences']['focus'], '승인 뒤 경합 보존')
        with patch('execution_engine.urlopen') as sender:
            with self.assertRaises(ValueError): self.employee()
            sender.assert_not_called()
