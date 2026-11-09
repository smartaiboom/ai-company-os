"""Real safety/adapter path with synthetic keys, grants and HTTPS responses only."""
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from autonomous_company import Company, CompanyError, MockManagerProvider, MockEmployeeProvider, Store, digest
from autonomous_live import (LiveStore, LiveCompany, LiveConfig, LiveManagerProvider,
                              LiveEmployeeProvider, SCOPES)
from tests.support.autonomous_company_fixtures import FictionalModels

KEY='synthetic-test-key-never-real'
ENV={'AI_ENGINE':'openai_compatible','AI_REAL_REQUESTS_ENABLED':'1',
     'AI_MODEL':'openrouter/free','AI_BASE_URL':'https://openrouter.ai/api/v1'}


class FakeHTTPS:
    def __init__(self,store,project_id,models):
        self.store=store;self.project_id=project_id;self.models=models;self.requests=[];self.alter=None
    def __call__(self,request,timeout):
        p=self.store.load(self.project_id);entry=p['real_ai']['attempts'][-1]
        assert entry['status']=='reserved' and entry['transport_started_at'] and p['active_operation']==entry['id']
        assert request.full_url=='https://openrouter.ai/api/v1/chat/completions'
        assert request.get_header('Authorization')=='Bearer '+KEY
        assert 1<=timeout<=90
        payload=json.loads(request.data);assert payload['model']=='openrouter/free'
        assert KEY not in request.data.decode()
        message=json.loads(payload['messages'][1]['content']);self.requests.append(deepcopy(message))
        phase=message['phase'];ctx=message['data']
        fn=self.models.manager_response if message['role']=='manager' else self.models.employee_response
        value=json.loads(fn(phase,ctx))
        if phase=='finalize':value.pop('task_refs')
        response={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(value,ensure_ascii=False)}}]}
        if self.alter:response=self.alter(response)
        return BytesIO(json.dumps(response).encode())


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.env=patch.dict(os.environ,ENV);self.env.start();self.addCleanup(self.env.stop)
        # Any accidental real TCP or DNS request fails the test before external contact.
        for name in ('socket.socket.connect','socket.getaddrinfo','socket.create_connection'):
            p=patch(name,side_effect=AssertionError('external network forbidden'));p.start();self.addCleanup(p.stop)
        self.store=LiveStore(Path(self.tmp.name)/'live')
        self.p=self.store.create('처음 방문하는 이용자를 위한 도서관 안내문')
        self.models=FictionalModels();self.fake=FakeHTTPS(self.store,self.p['id'],self.models)
        p=patch('autonomous_live.urlopen',self.fake);p.start();self.addCleanup(p.stop)
        self.company=self.engine()
    def engine(self,config=None):
        return LiveCompany(self.store,LiveManagerProvider(),LiveEmployeeProvider(),config or LiveConfig(KEY))
    def approve(self,**kwargs):
        b=self.store.prepare(self.p['id'],**kwargs)
        self.p=self.store.approve(self.p['id'],b,review_hash=digest(b),owner_confirmed=True)
        return b
    def run_once(self,**kwargs):
        self.p=self.store.load(self.p['id'])
        self.p=self.company.run(self.p['id'],expected_state_hash=self.p['storage_hash'],
                                resume=self.p['status']!='ready',**kwargs)
        return self.p
    def finish(self):
        for _ in range(6):
            self.run_once()
            if self.p['status']!='paused':return self.p
        self.fail('never finished')
    def test_two_goals_real_adapter_full_cycle(self):
        for goal,revise,calls in [('처음 방문하는 이용자를 위한 도서관 안내문',False,6),
                                  ('작은 창고의 재고 인수인계 안내문',True,8)]:
            with self.subTest(goal=goal):
                self.p=self.store.create(goal);self.models=FictionalModels(revise=revise)
                self.fake.project_id=self.p['id'];self.fake.models=self.models;self.fake.requests=[]
                self.approve();self.finish()
                self.assertEqual('delivered',self.p['status']);self.assertEqual(0,self.p['user_business_approval_requests'])
                entries=self.p['real_ai']['attempts'];self.assertEqual(calls,len(entries));self.assertNotIn('attempts',self.p)
                self.assertEqual(calls,len(self.fake.requests));self.assertTrue(all(e['status']=='completed' for e in entries))
                for session in self.p['sessions']:
                    self.assertLessEqual(sum(e['session_id']==session['id'] for e in entries),2)
                self.assertEqual(['manager','employee','manager'],[m['role'] for m in self.fake.requests[:3]])
                worker=[m['data'] for m in self.fake.requests if m['role']=='employee']
                self.assertTrue(worker[-1]['previous_results']);self.assertEqual(int(revise),self.p['assignments'][0]['revisions'])
                if revise:self.assertTrue(worker[1]['revision_feedback'])
                for entry in entries:self.assertIn('+09:00',entry['reserved_at']);self.assertTrue(entry['context_hash'])
                for name in ('final.md','final.json'):
                    path=self.store.root/self.p['artifacts'][name]['path'];self.assertTrue(path.is_file())
                self.assertEqual([digest(t['versions'][-1]) for t in self.p['assignments']],
                                 [r['result_hash'] for r in self.p['final']['task_refs']])
                before=len(self.fake.requests);self.run_once();self.assertEqual(before,len(self.fake.requests))
    def test_no_consent_and_prepare_are_zero_send(self):
        with self.assertRaises(CompanyError):self.run_once()
        self.store.prepare(self.p['id']);self.assertFalse((self.store.root/'.operating-consent.key').exists())
        self.assertEqual([],self.fake.requests);self.assertFalse(self.store.load(self.p['id'])['real_ai']['enabled'])
    def test_explicit_owner_review_and_replay(self):
        b=self.store.prepare(self.p['id'])
        for owner,review in [(False,digest(b)),(True,'stale')]:
            with self.assertRaises(CompanyError):self.store.approve(self.p['id'],b,review_hash=review,owner_confirmed=owner)
        self.approve()
        with self.assertRaises(CompanyError):self.store.approve(self.p['id'],b,review_hash=digest(b),owner_confirmed=True)
        self.assertEqual([],self.fake.requests)
    def test_contract_scope_cost_and_binding_fail_before_send(self):
        original=self.store.prepare(self.p['id'])
        for field,value in [('scopes',['goal']),('max_cost',1),('free_only',False),('model','paid'),
                            ('endpoint','http://openrouter.ai/api/v1'),('per_start',3),('goal_hash','other'),
                            ('expires_at','2020-01-01T00:00:00+09:00')]:
            b=deepcopy(original);b[field]=value
            with self.subTest(field=field),self.assertRaises(CompanyError):
                self.store.approve(self.p['id'],b,review_hash=digest(b),owner_confirmed=True)
        self.assertEqual([],self.fake.requests)
    def test_environment_model_endpoint_and_missing_key(self):
        self.approve()
        for changes,config in [({'AI_MODEL':'paid'},LiveConfig(KEY)),
                               ({'AI_BASE_URL':'https://evil.test'},LiveConfig(KEY)),
                               ({'AI_REAL_REQUESTS_ENABLED':'0'},LiveConfig(KEY)),
                               ({},LiveConfig('')),({},LiveConfig(KEY,model='paid')),
                               ({},LiveConfig(KEY,endpoint='http://openrouter.ai/api/v1'))]:
            with patch.dict(os.environ,changes),self.assertRaises(CompanyError):
                self.engine(config).run(self.p['id'],expected_state_hash=self.p['storage_hash'])
        self.assertEqual([],self.fake.requests)
    def test_max_two_explicit_resume_new_engine_no_repeat(self):
        self.approve();old=self.p['storage_hash'];self.run_once()
        self.assertEqual('paused',self.p['status']);self.assertEqual(2,len(self.fake.requests))
        self.assertEqual('work',self.p['phase'])
        with self.assertRaises(CompanyError):self.company.run(self.p['id'],expected_state_hash=old,resume=True)
        with self.assertRaises(CompanyError):self.company.run(self.p['id'],expected_state_hash=self.p['storage_hash'])
        self.company=self.engine();self.finish()
        self.assertEqual(1,sum(r['phase']=='plan' for r in self.fake.requests));self.assertEqual(6,len(self.fake.requests))
    def test_one_per_start_and_budget(self):
        self.approve(per_start=1);self.run_once();self.assertEqual(1,len(self.fake.requests))
        p=self.store.create('예산 한도 시험',max_calls=1);self.p=p;self.fake.project_id=p['id'];self.fake.requests=[]
        self.approve();self.run_once();self.assertEqual('stopped',self.p['status'])
        self.assertEqual('live_budget_exhausted',self.p['reason_code']);self.assertEqual(1,len(self.fake.requests))
    def test_revoke_before_and_during_session(self):
        self.approve();self.store.revoke(self.p['id'],owner_confirmed=True)
        with self.assertRaises(CompanyError):self.run_once()
        self.assertEqual([],self.fake.requests)
        self.p=self.store.create('회수 시험');self.fake.project_id=self.p['id'];self.approve()
        original=self.fake.__call__
        def revoke(request,timeout):
            value=original(request,timeout);self.store.revoke(self.p['id'],owner_confirmed=True);return value
        with patch('autonomous_live.urlopen',revoke):self.run_once()
        self.assertEqual('stopped',self.p['status']);self.assertEqual(1,len(self.fake.requests))
    def test_revoke_after_reservation_before_send(self):
        self.approve();original=self.company._persist
        def persist(p):
            original(p)
            if p['real_ai']['attempts'][-1]['status']=='reserved':self.store.revoke(p['id'],owner_confirmed=True)
        self.company._persist=persist;self.run_once()
        self.assertEqual([],self.fake.requests);self.assertEqual('failed',self.p['real_ai']['attempts'][0]['status'])
    def test_timeout_counts_and_never_retries(self):
        self.approve()
        with patch('autonomous_live.urlopen',side_effect=TimeoutError(KEY)):self.run_once()
        self.assertEqual('stopped',self.p['status']);self.assertEqual('failed',self.p['real_ai']['attempts'][0]['status'])
        self.run_once();self.assertEqual(1,len(self.p['real_ai']['attempts']))
        self.assertNotIn(KEY,self.store.path(self.p['id']).read_text())
    def test_response_contract_failures(self):
        for alteration in ['length','badjson','secret','escaped_secret','tools','unknown','duplicate','envelope']:
            with self.subTest(case=alteration):
                self.p=self.store.create('응답 계약 시험');self.fake.project_id=self.p['id'];self.fake.requests=[];self.approve()
                def alter(r):
                    c=r['choices'][0]
                    if alteration=='length':c['finish_reason']='length'
                    if alteration=='badjson':c['message']['content']='{'
                    if alteration=='secret':c['message']['content']=KEY
                    if alteration=='escaped_secret':c['message']['content']='{"content":"'+''.join('\\u%04x'%ord(ch) for ch in KEY)+'"}'
                    if alteration=='envelope':c['message']=[]
                    if alteration=='tools':c['message']['tool_calls']=[{}]
                    if alteration=='unknown':c['message']['content']='{"action":"ask_user"}'
                    if alteration=='duplicate':c['message']['content']='{"tasks":[],"tasks":[]}'
                    return r
                self.fake.alter=alter;self.run_once()
                self.assertEqual('stopped',self.p['status']);self.assertEqual(1,len(self.fake.requests))
                self.assertNotIn(KEY,self.store.path(self.p['id']).read_text())
    def test_secret_in_input_blocked(self):
        self.p=self.store.create('목표 '+KEY);self.fake.project_id=self.p['id'];self.approve()
        with self.assertRaises(CompanyError):self.run_once()
        self.assertEqual([],self.fake.requests)
    def test_ambiguous_completed_checkpoint_and_reserved_no_replay(self):
        for status in ('reserved','completed'):
            self.p=self.store.create('중단 시험');self.fake.project_id=self.p['id'];self.approve()
            p=self.store.load(self.p['id']);p['status']='running';p['active_operation']='unknown'
            p['real_ai']['attempts']=[{'id':'unknown','status':status,'input_bytes':10}];self.store.save(p)
            with self.assertRaises(CompanyError):self.run_once()
        self.assertEqual([],self.fake.requests)
    def test_unsigned_tampered_grant_and_changed_limits(self):
        self.approve();path=self.store._grant_path(self.p['id']);g=json.loads(path.read_text())
        g['record']['body']['per_start']=1;path.write_text(json.dumps(g))
        with self.assertRaises(CompanyError):self.run_once()
        self.assertEqual([],self.fake.requests)
    def test_stores_and_provider_types_stay_separate(self):
        with self.assertRaises(CompanyError):Store(self.store.root).create('mock',opt_in=True)
        with self.assertRaises(CompanyError):Company(self.store,LiveManagerProvider(),LiveEmployeeProvider())
        with self.assertRaises(CompanyError):LiveCompany(self.store,MockManagerProvider('m',lambda:None),
                                                        MockEmployeeProvider('e',lambda:None),LiveConfig(KEY))
    def test_crash_after_commit_resumes_without_repeating_plan(self):
        self.approve();original=self.company._commit
        def crash(p,event,**details):
            original(p,event,**details)
            raise KeyboardInterrupt('simulated process termination')
        with patch.object(self.company,'_commit',crash),self.assertRaises(KeyboardInterrupt):self.run_once()
        self.company=self.engine();self.finish()
        self.assertEqual('delivered',self.p['status'])
        self.assertEqual(6,len(self.fake.requests))
        self.assertEqual(1,sum(r['phase']=='plan' for r in self.fake.requests))

    def test_crash_after_completed_response_never_replays(self):
        self.approve();original=self.company._persist
        def crash(p):
            original(p)
            if p['real_ai']['attempts'][-1]['status']=='completed':raise KeyboardInterrupt()
        with patch.object(self.company,'_persist',crash),self.assertRaises(KeyboardInterrupt):self.run_once()
        self.company=self.engine()
        with self.assertRaises(CompanyError):self.run_once()
        self.assertEqual(1,len(self.fake.requests))

    def test_expired_and_modified_signed_scope_block(self):
        self.approve();path=self.store._grant_path(self.p['id']);g=json.loads(path.read_text())
        for change in ('expired','limits','scope'):
            record=deepcopy(g['record'])
            if change=='expired':record['body']['expires_at']='2020-01-01T00:00:00+09:00'
            if change=='limits':record['body']['limits']['max_calls']=19
            if change=='scope':record['body']['scopes']=['goal']
            self.store.atomic(path,{'record':record,'signature':self.store._sign(record)})
            with self.assertRaises(CompanyError):self.run_once()
        self.assertEqual([],self.fake.requests)

    def test_lock_and_engine_concurrency_rejected(self):
        self.approve()
        with self.store.lock(self.p['id']),self.assertRaises(CompanyError):self.run_once()
        with self.company._execution_lock,self.assertRaises(CompanyError):self.run_once()
        self.assertEqual([],self.fake.requests)

    def test_oversized_response_fails_and_counts(self):
        self.approve()
        with patch('autonomous_live.urlopen',return_value=BytesIO(b'x'*262145)):self.run_once()
        self.assertEqual('failed',self.p['real_ai']['attempts'][0]['status'])
        self.assertEqual('stopped',self.p['status'])

    def test_cli_prepare_approve_separate_and_start_never_approves(self):
        from autonomous_live_cli import main
        from contextlib import redirect_stdout
        from io import StringIO
        output=StringIO();proposal=Path(self.tmp.name)/'review.json'
        prefix=['--store',str(self.store.root)]
        with redirect_stdout(output):
            self.assertEqual(0,main(prefix+['prepare',self.p['id'],'--proposal-out',str(proposal)]))
        body=json.loads(proposal.read_text())
        self.assertFalse(self.store._grant_path(self.p['id']).exists())
        with redirect_stdout(output):
            self.assertEqual(1,main(prefix+['start',self.p['id'],'--state-hash',self.p['storage_hash']]))
            self.assertEqual(1,main(prefix+['approve',self.p['id'],'--proposal',str(proposal),
                                           '--review-hash',digest(body)]))
        self.assertFalse(self.store._grant_path(self.p['id']).exists());self.assertEqual([],self.fake.requests)
        with redirect_stdout(output):
            self.assertEqual(0,main(prefix+['approve',self.p['id'],'--proposal',str(proposal),
                                           '--review-hash',digest(body),'--owner-confirmed']))
            self.assertEqual(0,main(prefix+['status',self.p['id']]))
        self.assertNotIn(KEY,output.getvalue());self.assertEqual([],self.fake.requests)

    def test_quality_unknown_stops_without_delivery(self):
        self.approve();self.models.unknown=True;self.finish()
        self.assertEqual('stopped',self.p['status']);self.assertFalse(self.p['artifacts'])
    def test_revision_bound_stops(self):
        self.approve();self.models.always_revise=True;self.finish()
        self.assertEqual('revision_limit',self.p['reason_code']);self.assertFalse(self.p['artifacts'])


if __name__=='__main__':unittest.main()
