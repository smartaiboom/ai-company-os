"""All requests are fake HTTPS; socket/DNS blocked by shared free fixture."""
from io import BytesIO,StringIO
from contextlib import redirect_stdout
import json
import unittest
from unittest.mock import patch
from autonomous_company import CompanyError,digest
from autonomous_recovery import recovery_proposal
from ai_provider_adapter import bounded_response_diagnostics
from tests import test_autonomous_free as free
from tests.test_autonomous_live import KEY


class RecoveryTests(unittest.TestCase):
    engine=free.FreeTests.engine
    project=free.FreeTests.project
    approve=free.FreeTests.approve
    run_once=free.FreeTests.run_once
    def setUp(self):free.FreeTests.setUp(self)
    def diag(self):return self.p['real_ai']['attempts'][-1]['response_diagnostics']
    def alter_choice(self,**changes):
        def alter(r):r['choices'][0].update(changes);return r
        self.alter=alter
    def test_stop_and_bounded_private_metadata(self):
        def alter(r):
            r['id']=KEY;r['private_header']=KEY
            r['usage'].update(prompt_tokens=12,completion_tokens=34,total_tokens=46)
            return r
        self.alter=alter;self.approve();self.run_once()
        self.assertEqual('delivered',self.p['status'])
        d=self.diag();self.assertEqual('stop',d['finish']);self.assertEqual('parsed',d['json_parse'])
        self.assertEqual(34,d['tokens']['completion_tokens']);self.assertNotIn(KEY,json.dumps(d))
    def test_nonstop_missing_unknown_and_tool_finish_never_accepted(self):
        for finish in ('length','tool_calls','function_call','content_filter','error',KEY,None,{}):
            self.project();self.approve();self.alter_choice(finish_reason=finish);self.run_once()
            self.assertEqual('stopped',self.p['status']);self.assertEqual('incomplete_response',self.p['reason_code'])
            self.assertEqual(finish if isinstance(finish,str) and finish!=KEY else 'unknown',self.diag()['finish'])
            self.assertEqual('not_attempted',self.diag()['json_parse']);self.assertNotIn(KEY,json.dumps(self.diag()))
            count=len(self.fake.requests);self.run_once();self.assertEqual(count,len(self.fake.requests))
    def test_absent_choices_finish_content_and_refusal(self):
        for kind in ('choices','finish','content','refusal'):
            self.project();self.approve()
            def alter(r):
                if kind=='choices':r.pop('choices')
                elif kind=='finish':r['choices'][0].pop('finish_reason')
                elif kind=='content':r['choices'][0]['message'].pop('content')
                else:r['choices'][0]['message']['refusal']=KEY
                return r
            self.alter=alter;self.run_once();self.assertEqual('stopped',self.p['status'])
            if kind=='finish':self.assertEqual('missing',self.diag()['finish'])
            if kind=='refusal':self.assertTrue(self.diag()['refusal_present']);self.assertEqual('provider_refusal',self.p['reason_code'])
            self.assertNotIn(KEY,json.dumps(self.diag()))
    def test_json_invalid_and_long_envelope(self):
        self.approve()
        self.alter_choice(message={'role':'assistant','content':'{"unfinished":'})
        self.run_once();self.assertEqual('invalid',self.diag()['json_parse'])
        self.project();self.approve()
        with patch('autonomous_live.urlopen',return_value=BytesIO(b'x'*262145)):self.run_once()
        self.assertEqual('response_too_large',self.p['reason_code']);self.assertEqual(262145,self.diag()['response_bytes'])
        self.project();self.approve()
        with patch('autonomous_live.urlopen',return_value=BytesIO(b'{')):self.run_once()
        self.assertEqual('invalid',self.diag()['envelope_json'])
    def test_cost_errors_and_provider_envelope_never_allow_recovery(self):
        for cost in (None,True,0.1,'0'):
            self.project();self.approve();self.alter=lambda r:{**r,'usage':{'cost':cost}}
            self.run_once();self.assertEqual('provider_cost_unverified_or_nonzero',self.p['reason_code'])
            self.assertEqual(0,recovery_proposal(self.store,self.p['id'])['proposal']['proposed_max_additional_attempts'])
        for code in (429,402,503):
            self.project();self.approve();self.alter=lambda r:{'error':{'code':code,'message':KEY}}
            self.run_once();self.assertEqual('failed',self.p['real_ai']['attempts'][-1]['status'])
            self.assertNotIn(KEY,self.store.path(self.p['id']).read_text())
    def test_readonly_proposal_no_grant_or_duplicate_send(self):
        self.approve();self.alter_choice(finish_reason='length');self.run_once()
        before={str(p):p.read_bytes() for p in self.store.root.rglob('*') if p.is_file()}
        result=recovery_proposal(self.store,self.p['id']);b=result['proposal']
        self.assertEqual('review_one_new_plan_request',b['assessment']);self.assertEqual(1,b['proposed_max_additional_attempts'])
        self.assertFalse(b['execution_authorized']);self.assertFalse(b['execution_implemented'])
        self.assertEqual(digest(b),result['review_hash']);self.assertEqual(self.p['storage_hash'],b['state_hash'])
        from autonomous_live_cli import main
        with redirect_stdout(StringIO()):
            self.assertEqual(0,main(['--store',str(self.store.root),'recovery-proposal',self.p['id']]))
        self.run_once();self.assertEqual(1,len(self.fake.requests))
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.store.root.rglob('*') if p.is_file()})
    def test_legacy_unvalidated_and_crash_states_blocked(self):
        self.approve();self.alter_choice(finish_reason='length');self.run_once()
        cases=[('reserved',False),('reserved',True),('failed',True),('completed',True)]
        for status,sent in cases:
            p=self.store.load(self.p['id']);a=p['real_ai']['attempts'][-1]
            a['status']=status;a.pop('response_diagnostics',None);a.pop('response_received_at',None)
            if not sent:a.pop('transport_started_at',None)
            else:a['transport_started_at']=a['reserved_at']
            self.store.save(p)
            b=recovery_proposal(self.store,p['id'])['proposal'];self.assertEqual('blocked_pending_audit',b['assessment'])
            self.assertEqual(0,b['proposed_max_additional_attempts'])
        self.assertEqual(1,len(self.fake.requests))
    def test_crash_after_receive_before_cost_stays_reserved(self):
        self.approve();original=self.store.save
        def crash(p):
            original(p)
            if p['real_ai']['attempts'] and p['real_ai']['attempts'][-1].get('response_received_at'):raise KeyboardInterrupt()
        with patch.object(self.store,'save',crash),self.assertRaises(KeyboardInterrupt):self.run_once()
        self.company=self.engine()
        with self.assertRaises(CompanyError):self.run_once(resume=True)
        b=recovery_proposal(self.store,self.p['id'])['proposal']
        self.assertEqual('received_before_cost_commit',b['state_class']);self.assertEqual(1,len(self.fake.requests))


class MetadataTests(unittest.TestCase):
    def test_arbitrary_private_strings_and_token_types_are_dropped(self):
        d=bounded_response_diagnostics({'id':KEY,'usage':{'cost':KEY,'prompt_tokens':True,'completion_tokens':10**99,'total_tokens':KEY},
            'choices':[{'finish_reason':KEY,'message':{'content':KEY,'refusal':KEY}}]})
        self.assertNotIn(KEY,json.dumps(d));self.assertEqual('unknown',d['finish'])
        self.assertEqual({'prompt_tokens':None,'completion_tokens':None,'total_tokens':None},d['tokens'])
