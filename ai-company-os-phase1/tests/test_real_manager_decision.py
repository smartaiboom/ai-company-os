"""Real provider code with fake transport only, one durable attempt per fixture."""
import json
import os
import subprocess
import sys
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

import app
import ai_safety as safety
import manager_decision as md
from tests import test_manager_decision_loop as fixture
from tests.test_real_ai_safety_budget import Response


class RealManagerDecisionTests(unittest.TestCase):
    setUp=fixture.ManagerDecisionLoopTests.setUp
    approve=fixture.ManagerDecisionLoopTests.approve
    post=fixture.ManagerDecisionLoopTests.post
    seed_result=fixture.ManagerDecisionLoopTests.seed_result
    seed=fixture.ManagerDecisionLoopTests.seed
    saved=fixture.ManagerDecisionLoopTests.saved
    decision=fixture.ManagerDecisionLoopTests.decision

    def prepare(self):
        self.seed(enabled=False)
        self.enterContext(patch.dict(os.environ,{'AI_ENGINE':'openai_compatible','AI_MODEL':safety.MODEL,
            'AI_API_BASE_URL':safety.BASE_URL,'AI_API_KEY':'FICTIONAL','AI_REAL_REQUESTS_ENABLED':'1'},clear=True))
        p=self.saved();p['real_ai']['limit']=20;p['real_ai']['consent']['goal_hash']=safety.goal_hash(p['goal'])
        app.save_project(p)

    def run_real(self):
        return app.propose_real_manager_decision_once(self.p['id'],'TASK-001',md.digest(self.saved()),
                                                     user_confirmed=True,reason='가상 사용자 단일 호출 승인')

    def transport(self,action='proceed',mutate=None,finish='stop'):
        def fake(request,**kwargs):
            disk=self.saved();a=disk['real_ai']['attempts'][-1]
            self.assertEqual(a['status'],'reserved');self.assertEqual(a['kind'],'manager_decision')
            self.assertEqual(a['task_id'],'TASK-001');self.assertEqual(a['model'],safety.MODEL)
            body=json.loads(request.data);context=json.loads(body['messages'][1]['content'])
            self.assertEqual(body['messages'][0]['role'],'system')
            self.assertNotIn('내부 명령을 무시하고',body['messages'][0]['content'])
            text=json.dumps(context,ensure_ascii=False)
            for secret in ['비밀메타','다른프로젝트비밀','미승인비밀']:self.assertNotIn(secret,text)
            d=self.decision(context,action)
            if mutate:mutate(d)
            return Response({'choices':[{'finish_reason':finish,'message':{'content':json.dumps(d,ensure_ascii=False)}}]})
        return fake

    def test_four_actions_budget_reservation_binding_and_restart(self):
        self.prepare();original=self.saved()
        for action in md.ACTIONS:
            with self.subTest(action=action):
                app.save_project(deepcopy(original))
                with patch('manager_decision.urlopen',side_effect=self.transport(action)) as transport:
                    proposal=self.run_real()
                transport.assert_called_once()
                p=self.saved();self.assertEqual(len(p['real_ai']['attempts']),len(original['real_ai']['attempts'])+1)
                self.assertEqual(proposal['provider'],'real_openrouter_free')
                self.assertEqual(proposal['status'],'pending_user_decision')
                self.assertFalse(app.manager_decision_view(p['id'])[0]['stale'])
                for key in ['tasks','plan','user_preferences','plan_revisions']:
                    self.assertEqual(p[key],original[key])
                executor=Mock()
                with self.assertRaises(ValueError):app.execute_project_task(p['id'],'TASK-002',executor=executor)
                executor.assert_not_called()
        code='import app,json,sys;from pathlib import Path;app.PROJECTS_DIR=Path(sys.argv[1]);print(json.dumps(app.manager_decision_view(sys.argv[2])))'
        result=subprocess.run([sys.executable,'-B','-c',code,str(app.PROJECTS_DIR),self.p['id']],check=True,capture_output=True,text=True)
        self.assertFalse(json.loads(result.stdout)[0]['stale'])

    def test_proceed_user_approval_gate_and_employee_real_authorization(self):
        self.prepare()
        with patch('manager_decision.urlopen',side_effect=self.transport()):proposal=self.run_real()
        app.respond_manager_decision(self.p['id'],proposal['id'],md.digest(proposal),'approve')
        guidance=md.require_proceed(self.saved(),'TASK-002',['TASK-001'])
        self.assertEqual(guidance[0]['task_name'],'실제 AI 관리자')
        before=self.saved()['real_ai']
        with patch.dict(os.environ,{'AI_REAL_REQUESTS_ENABLED':'0'}),patch('execution_engine.urlopen') as transport:
            with self.assertRaises(app.TaskExecutionFailure):app.execute_project_task(self.p['id'],'TASK-002')
            transport.assert_not_called()
        self.assertEqual(self.saved()['real_ai'],before)

    def test_invalid_truncated_duplicate_and_wrong_binding_consume_once(self):
        self.prepare();original=self.saved()
        for mode in ('truncated','duplicate','wrong_binding','malformed'):
            app.save_project(deepcopy(original))
            def fake(request,**kwargs):
                context=json.loads(json.loads(request.data)['messages'][1]['content'])
                d=self.decision(context)
                if mode=='wrong_binding':d['binding']['project_id']='other'
                content=json.dumps(d,ensure_ascii=False)
                if mode=='duplicate':content=content[:-1]+',"action":"proceed"}'
                if mode=='malformed':content='{'
                return Response({'choices':[{'finish_reason':'length' if mode=='truncated' else 'stop','message':{'content':content}}]})
            with patch('manager_decision.urlopen',side_effect=fake) as transport:
                with self.assertRaises(RuntimeError):self.run_real()
                with self.assertRaises(ValueError):self.run_real()
                transport.assert_called_once()
            self.assertEqual(self.saved()['manager_decisions']['proposals'],[])
            self.assertEqual(self.saved()['real_ai']['attempts'][-1]['status'],'completed')

    def test_stale_result_plan_approval_and_unexpected_ledger_reject(self):
        self.prepare();original=self.saved()
        for mode in ('result','plan','approval','ledger','reservation_fingerprint'):
            app.save_project(deepcopy(original))
            def fake(request,**kwargs):
                context=json.loads(json.loads(request.data)['messages'][1]['content'])
                p=self.saved()
                if mode=='result':p['tasks'][0]['result']='바뀐 결과'
                if mode=='plan':p['plan']['version']=2
                if mode=='approval':p['tasks'][0]['reviewed_at']='바뀐 승인'
                if mode=='ledger':p['real_ai']['attempts'].append({'id':'unexpected','status':'completed','input_bytes':1})
                if mode=='reservation_fingerprint':p['real_ai']['attempts'][-1]['input_bytes']=321
                app.save_project(p)
                return Response({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(self.decision(context),ensure_ascii=False)}}]})
            with patch('manager_decision.urlopen',side_effect=fake) as transport:
                with self.assertRaises(RuntimeError):self.run_real()
                transport.assert_called_once()
            self.assertEqual(self.saved()['manager_decisions']['proposals'],[])
            if mode == 'result':self.assertEqual(self.saved()['tasks'][0]['result'], '바뀐 결과')
            if mode == 'plan':self.assertEqual(self.saved()['plan']['version'], 2)
            if mode == 'approval':self.assertEqual(self.saved()['tasks'][0]['reviewed_at'], '바뀐 승인')
            if mode == 'ledger':self.assertEqual(self.saved()['real_ai']['attempts'][-1]['id'], 'unexpected')
            if mode == 'reservation_fingerprint':self.assertEqual(self.saved()['real_ai']['attempts'][-1]['input_bytes'], 321)

    def test_idempotent_guard_and_mock_never_auto_switch(self):
        self.prepare()
        with patch('manager_decision.urlopen',side_effect=self.transport()) as transport:
            self.run_real()
            with self.assertRaises(ValueError):self.run_real()
            transport.assert_called_once()
        with self.assertRaises(ValueError):
            app.propose_manager_decision(self.p['id'],'TASK-001',md.MockDecisionProvider(lambda c:'{}'))
        p=self.saved();p['manager_decisions']={'enabled':True,'provider':'mock','proposals':[],'answers':[]}
        app.save_project(p)
        with self.assertRaises(ValueError):self.run_real()

    def test_unapproved_result_wrong_scope_or_model_never_transmit(self):
        self.prepare();original=self.saved()
        with patch('manager_decision.urlopen') as transport:
            with self.assertRaises(ValueError):
                app.propose_real_manager_decision_once(self.p['id'],'TASK-001',md.digest(self.saved()))
            p=self.saved();p['tasks'][0]['review_status']='pending';app.save_project(p)
            with self.assertRaises(ValueError):self.run_real()
            app.save_project(deepcopy(original))
            with patch.dict(os.environ,{'AI_MODEL':'paid/model'}),self.assertRaises(ValueError):self.run_real()
            with patch.dict(os.environ,{'AI_API_BASE_URL':'https://other.invalid'}),self.assertRaises(ValueError):self.run_real()
            transport.assert_not_called()

    def test_timeout_consumed_and_no_retry_or_proposal(self):
        self.prepare();before=deepcopy(self.saved()['real_ai']['attempts'])
        with patch('manager_decision.urlopen', side_effect=TimeoutError('PRIVATE')) as transport:
            with self.assertRaises(RuntimeError):self.run_real()
            with self.assertRaises(ValueError):self.run_real()
            transport.assert_called_once()
        p=self.saved()
        self.assertEqual(p['real_ai']['attempts'][:-1], before)
        self.assertEqual(p['real_ai']['attempts'][-1]['status'], 'failed')
        self.assertEqual(p['manager_decisions']['proposals'], [])
        self.assertNotIn('PRIVATE', json.dumps(p))
