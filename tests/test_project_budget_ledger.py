"""Synthetic offline budget execution; never touches live mission stores."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from autonomous_company import CompanyError
from project_budget import digest
from project_budget_ledger import ProjectBudgetLedger
from video_budget import BudgetedVideoTransport


class ProjectBudgetLedgerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.object(socket.socket, 'connect', side_effect=AssertionError('offline only')))
        self.enterContext(patch('socket.getaddrinfo', side_effect=AssertionError('offline only')))
        self.scope = dict(purpose='합성 직원 계획', data_policy='fixture free policy', free_only=True,
            consent_id='fixture-separate-provider-consent',
            consent_expires_at=(datetime.now(timezone(timedelta(hours=9)))+timedelta(days=2)).isoformat(),
            services={k:dict(provider='fixture-google', model='fixture-model' if k=='text' else 'none',
                account_project='fixture-account', operation=op, unit='request_attempt')
                for k,op in [('text','generateContent'),('search','search.list'),('videos','videos.list')]})
        self.ledger = ProjectBudgetLedger(self.root)
        self.ledger.create('fixture-project',scope=self.scope)
        self.consent = True
        self.adapter = BudgetedVideoTransport(self.ledger,'fixture-project',self.scope,lambda scope:self.consent)
        self.sent = 0

    def request(self, amounts):
        return self.ledger.request('fixture-project',amounts,reason='합성 작업 계획',progress='계획 보존',
            cost_impact='무료 범위, 금액 미확인',failure_risk='실패도 소비',plan_hash=digest('fixture plan'))

    def decide(self, request, action='approve'):
        self.ledger.decide('fixture-project',request['id'],review_hash=digest(request),
                           action=action,owner_confirmed=True)

    def send(self, operation, resource='text', callback=None):
        def transport():
            self.sent += 1
            # Reservation is authenticated and durable BEFORE fake external send.
            state = ProjectBudgetLedger(self.root)._load('fixture-project')
            self.assertEqual(state['attempts'][-1]['status'],'reserved')
            return callback() if callback else 'synthetic result'
        return self.adapter.send(operation,resource,transport)

    def test_initial_estimate_extension_and_preserved_execution(self):
        self.assertEqual(self.adapter.budget_status()['resources']['text']['approved'],0)
        initial = self.request({'text':2,'search':1})
        self.assertEqual(self.adapter.budget_status()['resources']['text']['approved'],0)
        self.decide(initial)
        self.send('writer-1')
        with self.assertRaises(ValueError):
            self.send('writer-2',callback=lambda:(_ for _ in ()).throw(ValueError('synthetic known failure')))
        with self.assertRaisesRegex(CompanyError,'budget_approval_required'):
            self.send('writer-3')
        pending = self.adapter.budget_status()['requests'][-1]
        self.assertEqual(pending,self.request({'text':5}))
        with self.assertRaisesRegex(CompanyError,'budget_approval_required'):
            self.send('writer-3')
        self.decide(pending)
        self.send('writer-3')
        self.send('research-1','search')
        state = self.ledger._load('fixture-project')
        self.assertEqual(len(state['approvals']),2)
        self.assertEqual([a['status'] for a in state['attempts']],['completed','failed','completed','completed'])
        self.assertEqual(self.adapter.budget_status()['resources']['text']['consumed'],3)
        self.assertEqual(self.adapter.budget_status()['resources']['videos']['consumed'],0)
        with self.assertRaisesRegex(CompanyError,'budget_operation_replay'):
            self.send('writer-2')
        self.assertEqual(self.sent,4)
        self.assertEqual(self.adapter.budget_status()['cost']['status'],'unknown')

    def test_rejection_and_duplicate_decision_do_not_grant(self):
        request=self.request({'text':1});self.decide(request,'reject')
        with self.assertRaisesRegex(CompanyError,'budget_decision_replay'):
            self.decide(request)
        with self.assertRaisesRegex(CompanyError,'budget_approval_required'):
            self.send('denied-call')
        shortage = self.adapter.budget_status()['requests'][-1]
        self.decide(shortage,'reject')
        count = len(self.adapter.budget_status()['requests'])
        with self.assertRaisesRegex(CompanyError,'budget_approval_required'):
            self.send('denied-call')
        self.assertEqual(len(self.adapter.budget_status()['requests']),count)
        self.assertEqual(self.sent,0)

    def test_crash_is_consumed_and_never_replayed(self):
        self.decide(self.request({'text':3}))
        with self.assertRaises(KeyboardInterrupt):
            self.send('crash',callback=lambda:(_ for _ in ()).throw(KeyboardInterrupt()))
        with self.assertRaisesRegex(CompanyError,'budget_operation_replay'):
            self.send('crash')
        with self.assertRaisesRegex(CompanyError,'budget_uncertain_operation'):
            self.send('different-call')
        self.assertEqual(self.adapter.budget_status()['resources']['text']['consumed'],1)
        self.assertEqual(self.sent,1)

    def test_timeout_consumes_and_stops_until_explicit_reconciliation(self):
        self.decide(self.request({'text':2}))
        with self.assertRaises(TimeoutError):
            self.send('timeout',callback=lambda:(_ for _ in ()).throw(TimeoutError()))
        with self.assertRaisesRegex(CompanyError,'budget_uncertain_operation'):
            self.send('next-call')
        state=self.adapter.budget_status()['resources']['text']
        self.assertEqual((state['consumed'],state['unresolved']),(1,1))
        self.assertEqual(self.sent,1)

    def test_concurrent_transport_is_exclusive(self):
        self.decide(self.request({'text':2}))
        entered, release = threading.Event(), threading.Event()
        errors=[]
        def background():
            try:
                self.send('first',callback=lambda:(entered.set(),release.wait(5)))
            except BaseException as exc:
                errors.append(exc)
        thread=threading.Thread(target=background);thread.start()
        try:
            self.assertTrue(entered.wait(5))
            with self.assertRaisesRegex(CompanyError,'budget_busy'):
                self.send('second')
        finally:
            release.set();thread.join(5)
        self.assertFalse(errors)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.sent,1)

    def test_expiry_and_review_hash_and_scope_block_before_send(self):
        request=self.request({'text':2})
        with self.assertRaisesRegex(CompanyError,'budget_review_changed'):
            self.ledger.decide('fixture-project',request['id'],review_hash='wrong',action='approve',owner_confirmed=True)
        self.decide(request)
        for field,value in [('free_only',False),('purpose','different'),('consent_id','new-consent')]:
            changed=deepcopy(self.scope);changed[field]=value
            with self.assertRaises(CompanyError):
                self.ledger.execute('fixture-project',operation_id='blocked',resource='text',
                    expected_scope=changed,verify_consent=lambda scope:True,send=lambda:self.fail('sent'))
        later=(datetime.now(timezone(timedelta(hours=9)))+timedelta(days=3)).isoformat()
        with patch('project_budget_ledger.now',return_value=later):
            with self.assertRaisesRegex(CompanyError,'budget_or_consent_expired'):
                self.send('expired')
        self.assertEqual(self.sent,0)

    def test_expired_request_and_missing_separate_consent(self):
        request=self.request({'text':1})
        later=(datetime.now(timezone(timedelta(hours=9)))+timedelta(hours=25)).isoformat()
        with patch('project_budget_ledger.now',return_value=later):
            with self.assertRaisesRegex(CompanyError,'budget_or_consent_expired'):
                self.decide(request)
        self.decide(request)
        self.consent=False
        with self.assertRaisesRegex(CompanyError,'budget_transport_consent_required'):
            self.send('no-provider-consent')
        self.assertEqual(self.sent,0)
        self.assertEqual(self.adapter.budget_status()['resources']['text']['consumed'],0)

    def test_changed_provider_model_account_data_or_units_requires_new_consent(self):
        self.decide(self.request({'text':2}))
        for field,value in [('provider','other'),('model','other'),('account_project','other'),
                            ('operation','different'),('unit','quota_units')]:
            changed=deepcopy(self.scope);changed['services']['text'][field]=value
            with self.subTest(field=field), self.assertRaisesRegex(CompanyError,'budget_scope_changed_new_consent_required'):
                self.ledger.execute('fixture-project',operation_id='scope-test',resource='text',
                    expected_scope=changed,verify_consent=lambda scope:True,send=lambda:self.fail('sent'))
        changed=deepcopy(self.scope);changed['data_policy']='new-data-policy'
        with self.assertRaisesRegex(CompanyError,'budget_scope_changed_new_consent_required'):
            self.ledger.execute('fixture-project',operation_id='data-test',resource='text',
                expected_scope=changed,verify_consent=lambda scope:True,send=lambda:self.fail('sent'))
        with self.assertRaisesRegex(CompanyError,'explicit_budget_decision_required'):
            self.ledger.decide('fixture-project','unknown',review_hash='unknown',action='approve')
        for amounts in ({'unknown':1},{'text':0},{'text':True},{'text':1.5}):
            with self.assertRaisesRegex(CompanyError,'invalid_budget_amounts'):
                self.request(amounts)
        self.assertEqual(self.sent,0)

    def test_existing_signed_provider_grant_revocation_still_blocks_budgeted_transport(self):
        from autonomous_gemini35 import Gemini35Store, MODEL
        provider = Gemini35Store(self.root/'synthetic-provider')
        job = provider.create('합성 승인 분리 검증',max_calls=2)
        body = provider.prepare(job['id'],valid_hours=1,confirm_free_account=True)
        provider.approve(job['id'],body,review_hash=digest(body),owner_confirmed=True)
        grant = provider.grant(provider.load(job['id']))
        scope = deepcopy(self.scope)
        scope['consent_id'] = grant['id']
        scope['consent_expires_at'] = body['expires_at']
        scope['services']['text']['model'] = MODEL
        self.ledger.create('signed-provider-project',scope=scope)
        request = self.ledger.request('signed-provider-project',{'text':1},reason='합성 계획',
            progress='작업 보존',cost_impact='무료만',failure_risk='실패도 소모',plan_hash=digest(body))
        self.ledger.decide('signed-provider-project',request['id'],review_hash=digest(request),
                           action='approve',owner_confirmed=True)
        def verify(actual):
            current = provider.grant(provider.load(job['id']))
            return (current['id']==actual['consent_id'] and current['body']['model']==actual['services']['text']['model']
                    and current['body']['free_only'] is True)
        adapter = BudgetedVideoTransport(self.ledger,'signed-provider-project',scope,verify)
        provider.revoke(job['id'],owner_confirmed=True)
        with self.assertRaisesRegex(CompanyError,'consent_revoked'):
            adapter.send('after-revocation','text',lambda:self.fail('sent'))
        self.assertEqual(adapter.budget_status()['resources']['text']['consumed'],0)

    def test_tampering_project_binding_units_and_paid_creation(self):
        for field,value in [('free_only',False)]:
            bad=deepcopy(self.scope);bad[field]=value
            with self.assertRaisesRegex(CompanyError,'paid_budget_path_forbidden'):
                ProjectBudgetLedger(self.root/'paid').create('other',scope=bad)
        bad=deepcopy(self.scope);bad['services']['search']['unit']='quota_units'
        with self.assertRaisesRegex(CompanyError,'unsupported_budget_unit'):
            ProjectBudgetLedger(self.root/'units').create('other',scope=bad)
        self.decide(self.request({'text':1}))
        path=self.root/'fixture-project.json';record=json.loads(path.read_text())
        (self.root/'different-project.json').write_text(json.dumps(record))
        with self.assertRaisesRegex(CompanyError,'budget_project_mismatch'):
            self.ledger.execute('different-project',operation_id='wrong-project',resource='text',
                expected_scope=self.scope,verify_consent=lambda scope:True,send=lambda:self.fail('sent'))
        record['body']['approvals'][0]['amounts']['text']=999
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(CompanyError,'budget_ledger_tampered'):
            self.send('tampered')
        self.assertEqual(self.sent,0)
