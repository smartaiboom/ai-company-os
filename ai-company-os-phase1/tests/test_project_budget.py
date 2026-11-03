"""Offline budget policy, local signed extensions, no external transport."""
import io
import json
import os
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlencode

import app
import ai_safety as safety
import project_budget as budget
from tests.real_ai_fixtures import approved_project
from tests.test_real_ai_safety_budget import Response


class ProjectBudgetTests(unittest.TestCase):
    def setUp(self):
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(app,'PROJECTS_DIR',root))
        self.enterContext(patch.object(app,'ARTIFACTS_DIR',root/'artifacts'))
        self.enterContext(patch.object(budget,'KEY_PATH',root/'.budget.key'))
        self.enterContext(patch('socket.socket',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('ai_safety.build_opener',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch.dict(os.environ,{'AI_ENGINE':'openai_compatible','AI_MODEL':safety.MODEL,
            'AI_API_BASE_URL':safety.BASE_URL,'AI_REAL_REQUESTS_ENABLED':'1'},clear=True))
        self.p=approved_project({'id':'budget-test','goal':'가상 목표','tasks':[],'history':[]})
        self.p['real_ai']['limit']=20
        app.save_project(self.p)

    def saved(self):return app.load_project(self.p['id'])

    def proposal(self,additional=5):
        return app.request_project_budget(self.p['id'],additional,'추가 검토가 필요합니다.',[{'purpose':'검토·수정','calls':additional}])

    def decide(self,p,response='approve',confirmed=True):
        app.decide_project_budget(self.p['id'],p['body']['id'],budget.digest(p),response,
                                  user_confirmed=confirmed,reason='사용자 명시 결정 fixture')

    def send(self,p,transport):
        return safety.request_json(p,model=safety.MODEL,base_url=safety.BASE_URL,
            body=json.dumps({'model':safety.MODEL,'max_tokens':32,'messages':[]}).encode(),
            api_key='FICTIONAL',timeout=1,transport=transport,kind='task')

    def attempts(self,count,status='completed'):
        return [{'id':str(i),'status':status,'input_bytes':1} for i in range(count)]

    def test_new_project_defaults20_disabled_and_legacy_missing_limit20_explicit7_preserved(self):
        handler=app.Handler.__new__(app.Handler);body=urlencode({'name':'가상 신규','goal':'가상 목표'}).encode()
        handler.path='/create';handler.headers={'Content-Length':str(len(body))};handler.rfile=io.BytesIO(body)
        handler.redirect=lambda location:None
        handler.send_html=lambda *a: self.fail('create error')
        handler.do_POST()
        created=[p for p in app.load_projects() if p['id']!=self.p['id']][0]
        self.assertEqual(created['real_ai'],{'enabled':False,'limit':20,'attempts':[]})
        del self.p['real_ai']['limit'];self.assertEqual(budget.limit(self.p),20)
        self.p['real_ai']['limit']=7;self.assertEqual(budget.limit(self.p),7)

    def test_twentieth_allowed_twentyfirst_requests_budget_without_transport(self):
        p=self.saved();p['real_ai']['attempts']=self.attempts(19);app.save_project(p)
        transport=Mock(return_value=Response())
        with safety.request_scope(app.save_project):self.send(self.saved(),transport)
        with safety.request_scope(app.save_project),self.assertRaisesRegex(ValueError,'소진'):
            self.send(self.saved(),transport)
        self.assertEqual(transport.call_count,1)
        self.assertEqual(len(self.saved()['real_ai']['attempts']),20)
        request=app.project_budget_requests(self.p['id'])[0]
        self.assertEqual(request['body']['additional'],1)
        self.assertEqual(request['body']['snapshot']['remaining'],0)
        self.assertEqual(request['status'],'pending')

    def test_user_extension25_and_twentyfifth_boundary(self):
        p=self.proposal();before=self.saved()['real_ai'];self.decide(p)
        self.assertEqual(budget.limit(self.saved()),25)
        self.assertEqual(self.saved()['real_ai']['attempts'],before['attempts'])
        p=self.saved();p['real_ai']['attempts']=self.attempts(24);app.save_project(p)
        transport=Mock(return_value=Response())
        with safety.request_scope(app.save_project):self.send(self.saved(),transport)
        with safety.request_scope(app.save_project),self.assertRaises(ValueError):self.send(self.saved(),transport)
        self.assertEqual(transport.call_count,1)
        self.assertEqual(len(self.saved()['real_ai']['attempts']),25)

    def test_reject_duplicate_and_unconfirmed_preserve_limit(self):
        p=self.proposal()
        with self.assertRaises(ValueError):self.decide(p,confirmed=False)
        self.decide(p,'reject');self.assertEqual(budget.limit(self.saved()),20)
        before=app.project_path(self.p['id']).read_bytes()
        with self.assertRaises(ValueError):self.decide(p)
        self.assertEqual(app.project_path(self.p['id']).read_bytes(),before)

    def test_tampered_request_and_forged_limit_or_other_project_fail(self):
        proposal=self.proposal();p=self.saved();p['budget_requests'][0]['body']['additional']=50;app.save_project(p)
        forged=self.saved()['budget_requests'][0]
        with self.assertRaises(ValueError):self.decide(forged)
        p=self.saved();p['real_ai']['limit']=25
        with self.assertRaises(ValueError):budget.limit(p)
        p=self.saved();p['budget_requests']=[proposal];app.save_project(p);self.decide(proposal)
        p=self.saved();p['id']='different'
        with self.assertRaises(ValueError):budget.limit(p)

    def test_stale_request_never_increases_budget(self):
        proposal=self.proposal();p=self.saved();p['real_ai']['attempts']=self.attempts(1);app.save_project(p)
        before=app.project_path(self.p['id']).read_bytes()
        with self.assertRaises(ValueError):self.decide(proposal)
        self.assertEqual(app.project_path(self.p['id']).read_bytes(),before)
        self.assertTrue(app.project_budget_requests(self.p['id'])[0]['stale'])
        self.decide(proposal,'reject')
        self.assertEqual(budget.limit(self.saved()),20)

    def test_concurrent_requests_and_approvals_only_one_success(self):
        barrier=threading.Barrier(2);outcomes=[]
        def request():
            barrier.wait()
            try:self.proposal();outcomes.append(True)
            except ValueError:outcomes.append(False)
        workers=[threading.Thread(target=request) for _ in range(2)]
        for t in workers:t.start()
        for t in workers:t.join(2);self.assertFalse(t.is_alive())
        self.assertCountEqual(outcomes,[True,False])
        proposal=self.saved()['budget_requests'][0];outcomes.clear();barrier=threading.Barrier(2)
        def approve():
            barrier.wait()
            try:self.decide(proposal);outcomes.append(True)
            except ValueError:outcomes.append(False)
        workers=[threading.Thread(target=approve) for _ in range(2)]
        for t in workers:t.start()
        for t in workers:t.join(2);self.assertFalse(t.is_alive())
        self.assertCountEqual(outcomes,[True,False]);self.assertEqual(budget.limit(self.saved()),25)

    def test_bad_additions_rejected(self):
        for n in (0,-1,True,1.5,51,100000):
            with self.subTest(n=n),self.assertRaises(ValueError):self.proposal(n)
        self.assertNotIn('budget_requests',self.saved())

    def test_reserved_and_failed_consumed_and_extension_never_unblocks_reserved(self):
        p=self.saved();p['real_ai']['attempts']=self.attempts(19,'failed')+[{'id':'unknown','status':'reserved','input_bytes':1}]
        app.save_project(p);proposal=self.proposal();self.decide(proposal)
        transport=Mock()
        with safety.request_scope(app.save_project),self.assertRaisesRegex(ValueError,'불명확'):self.send(self.saved(),transport)
        transport.assert_not_called();self.assertEqual(budget.summary(self.saved())['used'],20)
        self.assertEqual(self.saved()['real_ai']['attempts'],p['real_ai']['attempts'])

    def test_extension_is_not_execution_consent(self):
        p=self.proposal();self.decide(p)
        for mutation in (lambda p:p['real_ai']['consent'].update(approved=False),lambda p:p['real_ai'].update(enabled=False)):
            p=self.saved();mutation(p);transport=Mock()
            with safety.request_scope(app.save_project),self.assertRaises(ValueError):self.send(p,transport)
            transport.assert_not_called()

    def test_migration_preserves_used_and_other_project(self):
        p=self.saved();p['real_ai']['limit']=7;p['real_ai']['attempts']=self.attempts(2);app.save_project(p)
        other=deepcopy(p);other['id']='other';app.save_project(other)
        original=deepcopy(self.saved());other_raw=app.project_path('other').read_bytes()
        app.raise_project_budget_to_default(p['id'],budget.digest(self.saved()),user_confirmed=True,reason='사용자 확정 정책')
        saved=self.saved();self.assertEqual(saved['real_ai']['limit'],20)
        original['real_ai']['limit']=20
        self.assertEqual(saved['real_ai'],original['real_ai'])
        self.assertEqual(saved['tasks'],original['tasks'])
        self.assertEqual(app.project_path('other').read_bytes(),other_raw)

    def test_forecast_shortage_no_ai_and_sufficient_no_proposal(self):
        self.assertIsNone(app.prepare_project_budget(self.p['id'],[{'purpose':'남은 작업','calls':4}]))
        p=self.saved();p['real_ai']['attempts']=self.attempts(19);app.save_project(p)
        request=app.prepare_project_budget(self.p['id'],[{'purpose':'초안','calls':1},{'purpose':'검토','calls':2}])
        self.assertEqual(request['body']['additional'],2)
        self.assertEqual(budget.limit(self.saved()),20)

    def test_input_total_and_two_per_start_remain_bounded(self):
        p=self.saved();transport=Mock(return_value=Response())
        with safety.request_scope(app.save_project):
            self.send(p,transport);self.send(p,transport)
            with self.assertRaisesRegex(ValueError,'2회'):self.send(p,transport)
        p=self.saved();p['real_ai']['attempts']=self.attempts(19)
        for a in p['real_ai']['attempts']:a['input_bytes']=safety.MAX_INPUT_BYTES
        app.save_project(p)
        with patch.object(safety,'MAX_TOTAL_INPUT_BYTES',19*safety.MAX_INPUT_BYTES):
            with safety.request_scope(app.save_project),self.assertRaisesRegex(ValueError,'누적'):
                self.send(self.saved(),transport)
        self.assertEqual(transport.call_count,2)
