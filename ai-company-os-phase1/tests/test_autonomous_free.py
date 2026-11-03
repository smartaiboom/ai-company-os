"""Offline free-policy acceptance through the production adapter and durable ledger."""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from autonomous_company import CompanyError, digest, now
from autonomous_free import FreeStore, FreeCompany, ZERO_PRICE, RULES
from autonomous_live import LiveStore, LiveCompany, LiveManagerProvider, LiveEmployeeProvider, LiveConfig
from tests.test_autonomous_live import FakeHTTPS, KEY
from tests.support.autonomous_company_fixtures import FictionalModels

FREE_ENV={'AI_REAL_REQUESTS_ENABLED':'0','AI_AUTONOMOUS_FREE_ENABLED':'1','AI_ENGINE':'openai_compatible',
          'AI_MODEL':'openrouter/free','AI_BASE_URL':'https://openrouter.ai/api/v1','AI_API_KEY':KEY}


class Clock:
    def __init__(self):self.value=datetime.fromisoformat(now());self.waits=[]
    def now(self):return self.value.isoformat()
    def sleep(self,seconds):self.waits.append(seconds);self.value+=timedelta(seconds=seconds)


class EventGuideModels(FictionalModels):
    """Eight useful, dependent documents; two concrete omissions need correction."""
    sections=['요구사항','시간표','장소 동선','접근성','안전 대응','개인정보','자원봉사','안내 통합']
    def manager_response(self,phase,ctx):
        if phase=='plan':
            value={'tasks':[],'criteria':[],'rationale':'행사 안내에 필요한 여덟 영역을 순서대로 작성한다.',
                   'uncertainty':'기관 일정과 현장 정보는 미확인이다.'}
            for i,title in enumerate(self.sections):
                task_id='section-'+str(i);cid='criterion-'+str(i)
                value['criteria'].append({'id':cid,'description':title+' 절차 및 미확인 정보 구분'})
                value['tasks'].append({'id':task_id,'title':title,'role':title+' 담당',
                    'instructions':title+' 문서를 작성하고 선행 자료와 빠진 정보를 대조한다.',
                    'depends_on':['section-'+str(i-1)] if i else [],'criteria_ids':[cid]})
        elif phase=='review':
            needs=ctx['assignment']['id'] in ('section-0','section-1') and ctx['result']['revision']==1
            value={'action':'revise' if needs else 'accept','rationale':'담당 영역의 구체적 누락을 대조했다.',
                'evidence':ctx['result']['content'],'uncertainty':'실제 현장 정보는 독립 확인하지 않았다.',
                'checks':[{'criterion_id':c['id'],'status':'unmet' if needs else 'met',
                    'evidence':'비상 연락 확인 절차/일정 변경 공지 절차의 표기를 점검했다.','source':'model_claim'} for c in ctx['criteria']],
                'feedback':'비상 연락 확인 담당과 일정 변경 공지 절차를 명시한다.' if needs else '', 'operation':None}
        else:
            value={'action':'deliver','content':'지역 행사 안내서\n'+'\n'.join(r['content'] for r in ctx['results']),
                'task_refs':[{'task_id':r['task_id'],'revision':r['revision'],'result_hash':digest(r)} for r in ctx['results']],
                'rationale':'수락한 여덟 담당 문서와 두 누락 보완을 통합했다.','uncertainty':'실제 일정·담당자·장소는 확인 필요.',
                'checks':[{'criterion_id':c['id'],'status':'met','evidence':'최신 영역 문서를 대조했다.',
                    'source':'model_claim'} for c in ctx['plan']['criteria']]}
        return json.dumps(value,ensure_ascii=False)
    def employee_response(self,phase,ctx):
        assignment=ctx['assignment'];prior=[r['task_id'] for r in ctx['previous_results']]
        content=assignment['title']+' 문서: 담당자는 필요한 자료를 수집하고 확인 결과와 미확인 항목을 분리한다. '
        if ctx['revision_feedback']:
            content+='보완: 운영 담당자가 비상 연락처를 확인하며, 일정 변경 시 안내 담당자가 변경 시각과 공지를 기록한다. '
        else:content+='초안: 실제 담당자 이름과 운영 시간은 미확인이다. '
        content+='연계한 선행 자료: '+', '.join(prior)
        return json.dumps({'content':content,'evidence':'해당 배정과 선행 결과를 문서 수준에서 대조했다.',
                           'uncertainty':'현장·기관 자료의 독립 검증은 미실시.'},ensure_ascii=False)


class FreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.env=patch.dict(os.environ,FREE_ENV);self.env.start();self.addCleanup(self.env.stop)
        for name in ('socket.socket.connect','socket.socket.connect_ex','socket.socket.sendto',
                     'socket.create_connection','socket.getaddrinfo','socket.gethostbyname'):
            p=patch(name,side_effect=AssertionError('external network forbidden'));p.start();self.addCleanup(p.stop)
        self.clock=Clock()
        for name,value in [('autonomous_free.now',self.clock.now),('autonomous_free.pacing_now',self.clock.now),
                           ('autonomous_live.now',self.clock.now),
                           ('autonomous_company.now',self.clock.now),('autonomous_free.time.sleep',self.clock.sleep)]:
            p=patch(name,value);p.start();self.addCleanup(p.stop)
        self.store=FreeStore(Path(self.tmp.name)/'free');self.p=self.store.create('도서관 초방문 안내문')
        self.models=FictionalModels();self.fake=FakeHTTPS(self.store,self.p['id'],self.models)
        self.alter=None
        def decorate(response):
            response['usage']={'cost':0}
            return self.alter(response) if self.alter else response
        self.fake.alter=decorate
        def transport(request,timeout):
            assert json.loads(request.data)['provider']==ZERO_PRICE
            return self.fake(request,timeout)
        self.transport=transport
        p=patch('autonomous_live.urlopen',transport);p.start();self.addCleanup(p.stop)
        self.company=self.engine()
    def engine(self,config=None):
        return FreeCompany(self.store,LiveManagerProvider(),LiveEmployeeProvider(),config or LiveConfig(KEY))
    def project(self,goal='도서관 초방문 안내문',**kwargs):
        self.p=self.store.create(goal,**kwargs);self.fake.project_id=self.p['id'];self.fake.requests=[]
        return self.p
    def approve(self):
        body=self.store.prepare(self.p['id'])
        self.p=self.store.approve(self.p['id'],body,review_hash=digest(body),owner_confirmed=True)
        return body
    def run_once(self,resume=False):
        p=self.store.load(self.p['id'])
        self.p=self.company.run(p['id'],expected_state_hash=p['storage_hash'],resume=resume)
        return self.p
    def assert_no_send(self):
        self.assertEqual([],self.fake.requests)
        self.assertEqual([],self.store.load(self.p['id'])['real_ai']['attempts'])
    def test_two_goals_one_run_each_with_revision_files_and_no_business_gates(self):
        for goal,revise,count in [('도서관 초방문 안내문',False,6),('창고 재고 인수인계',True,8)]:
            with self.subTest(goal=goal):
                self.project(goal);self.models=FictionalModels(revise=revise);self.fake.models=self.models
                body=self.approve();self.assertIsNone(body['call_policy']['total']);self.assertIsNone(body['call_policy']['per_run'])
                self.run_once();self.assertEqual('delivered',self.p['status']);self.assertEqual(count,len(self.fake.requests))
                self.assertEqual(1,len(self.p['sessions']));self.assertEqual(0,self.p['user_business_approval_requests'])
                self.assertEqual(int(revise),sum(t['revisions'] for t in self.p['assignments']))
                self.assertFalse(any(e['event']=='session_paused' for e in self.p['events']))
                self.assertNotIn('limit',self.p['real_ai']);self.assertNotIn('attempts',self.p)
                for e in self.p['real_ai']['attempts']:
                    self.assertEqual('completed',e['status']);self.assertEqual('validated',e['role_result_status'])
                    self.assertTrue(e['cost_verified_zero']);self.assertIn('+09:00',e['reserved_at'])
                self.assertEqual(count,len({a['operation_hash'] for a in self.p['real_ai']['attempts']}))
                self.store.result(self.p['id'])
                for name in ('final.json','final.md'):self.assertTrue((self.store.root/self.p['artifacts'][name]['path']).is_file())
                worker=[r for r in self.fake.requests if r['role']=='employee'];self.assertTrue(worker[-1]['data']['previous_results'])
                self.run_once();self.assertEqual(count,len(self.fake.requests))
    def test_legitimate_eight_document_dag_exceeds_twenty_in_one_run(self):
        self.project('지역 행사 운영 안내서 작성');self.fake.models=EventGuideModels();self.approve();self.run_once()
        self.assertEqual('delivered',self.p['status']);self.assertEqual(22,len(self.fake.requests))
        self.assertEqual(8,len(self.p['assignments']));self.assertEqual(2,sum(t['revisions'] for t in self.p['assignments']))
        self.assertEqual(1,len(self.p['sessions']));self.assertEqual(0,self.p['user_business_approval_requests'])
        self.assertGreaterEqual(sum(self.clock.waits),42)
    def test_no_consent_prepare_and_owner_confirmation(self):
        with self.assertRaises(CompanyError):self.run_once()
        b=self.store.prepare(self.p['id']);self.assertIn('상한 없음',b['notice'])
        self.assertFalse((self.store.root/'.operating-consent.key').exists())
        for owner,review in [(False,digest(b)),(True,'stale')]:
            with self.assertRaises(CompanyError):self.store.approve(self.p['id'],b,review_hash=review,owner_confirmed=owner)
        self.assert_no_send()
    def test_contract_policy_scope_cost_identity_and_deadline(self):
        b=self.store.prepare(self.p['id'])
        for field,value in [('policy','legacy'),('scopes',['goal']),('max_cost',1),('free_only',False),
                            ('model','paid'),('endpoint','http://openrouter.ai/api/v1'),('project_id','other'),
                            ('goal_hash','other'),('expires_at','2020-01-01T00:00:00+09:00'),
                            ('call_policy',{'total':None,'per_run':2,'optional_technical_cap':None}),
                            ('rules',{**RULES,'max_run_seconds':999999})]:
            changed=deepcopy(b);changed[field]=value
            with self.subTest(field=field),self.assertRaises(CompanyError):
                self.store.approve(self.p['id'],changed,review_hash=digest(changed),owner_confirmed=True)
        self.assert_no_send()
    def test_signature_stale_goal_changed_scope_expiry_and_revoke(self):
        self.approve();grant_path=self.store._grant_path(self.p['id']);original=grant_path.read_text()
        g=json.loads(original);g['record']['body']['free_only']=False;grant_path.write_text(json.dumps(g))
        with self.assertRaises(CompanyError):self.run_once()
        grant_path.write_text(original)
        with patch('autonomous_free.now',return_value='2099-01-01T00:00:00+09:00'),self.assertRaises(CompanyError):self.run_once()
        self.store.revoke(self.p['id'],owner_confirmed=True)
        with self.assertRaises(CompanyError):self.run_once()
        self.assert_no_send()
    def test_free_guard_model_url_key_and_old_guard_are_separate(self):
        self.approve()
        for env,config in [({'AI_AUTONOMOUS_FREE_ENABLED':'0'},LiveConfig(KEY)),({'AI_MODEL':'paid'},LiveConfig(KEY)),
                            ({'AI_BASE_URL':'https://evil.test'},LiveConfig(KEY)),({},LiveConfig('')),
                            ({},LiveConfig(KEY,model='paid')),({},LiveConfig(KEY,endpoint='http://openrouter.ai/api/v1'))]:
            with patch.dict(os.environ,env),self.assertRaises(CompanyError):
                self.engine(config).run(self.p['id'],expected_state_hash=self.p['storage_hash'])
        self.assertEqual('0',os.environ['AI_REAL_REQUESTS_ENABLED']);self.assert_no_send()
    def test_provider_rate_quota_and_unavailable_pause_without_retry(self):
        for code,reason in [(429,'provider_rate_limit'),(402,'provider_quota_or_billing'),(503,'provider_unavailable')]:
            self.project();self.approve()
            error=HTTPError('https://openrouter.ai',code,KEY,{'Retry-After':'60'},BytesIO(KEY.encode()))
            with patch('autonomous_live.urlopen',side_effect=error):self.run_once()
            self.assertEqual('paused',self.p['status']);self.assertEqual(reason,self.p['reason_code'])
            self.assertEqual(1,len(self.p['real_ai']['attempts']));self.assertEqual('failed',self.p['real_ai']['attempts'][0]['status'])
            with self.assertRaises(CompanyError):self.run_once(resume=True)
            self.assertNotIn(KEY,self.store.path(self.p['id']).read_text());self.assertEqual([],self.fake.requests)
    def test_provider_error_envelope_and_nonzero_unknown_cost(self):
        for value in [None,0.01,True,'0']:
            self.project();self.approve()
            self.alter=lambda r:{**r,'usage':{'cost':value}}
            self.run_once();self.assertEqual('stopped',self.p['status']);self.assertEqual(1,len(self.fake.requests))
            self.assertEqual('provider_cost_unverified_or_nonzero',self.p['reason_code'])
        self.project();self.approve();self.alter=lambda r:{'error':{'code':429,'message':KEY}}
        self.run_once();self.assertEqual('paused',self.p['status']);self.assertEqual('provider_rate_limit',self.p['reason_code'])
        self.assertNotIn(KEY,self.store.path(self.p['id']).read_text())
    def test_timeout_and_uncertain_attempts_never_replay(self):
        self.approve()
        with patch('autonomous_live.urlopen',side_effect=TimeoutError(KEY)):self.run_once()
        self.assertEqual('stopped',self.p['status']);self.run_once(resume=True)
        self.assertEqual(1,len(self.p['real_ai']['attempts']))
        self.project();self.approve();p=self.store.load(self.p['id']);p['status']='running';p['active_operation']='uncertain'
        p['real_ai']['attempts']=[{'id':'uncertain','status':'reserved','input_bytes':100}];self.store.save(p)
        with self.assertRaises(CompanyError):self.run_once(resume=True)
        self.assertEqual([],self.fake.requests)
    def test_crash_clean_checkpoint_continue_no_repeated_plan(self):
        self.approve();original=self.company._commit
        def crash(p,event,**details):original(p,event,**details);raise KeyboardInterrupt()
        with patch.object(self.company,'_commit',crash),self.assertRaises(KeyboardInterrupt):self.run_once()
        self.company=self.engine();self.run_once(resume=True)
        self.assertEqual('delivered',self.p['status']);self.assertEqual(6,len(self.fake.requests))
        self.assertEqual(1,sum(r['phase']=='plan' for r in self.fake.requests))
    def test_crash_completed_response_before_commit_blocks(self):
        self.approve();original=self.company._persist
        def crash(p):
            original(p)
            if p['real_ai']['attempts'][-1]['status']=='completed':raise KeyboardInterrupt()
        with patch.object(self.company,'_persist',crash),self.assertRaises(KeyboardInterrupt):self.run_once()
        self.company=self.engine()
        with self.assertRaises(CompanyError):self.run_once(resume=True)
        self.assertEqual(1,len(self.fake.requests))
    def test_cancel_during_throttle_prevents_next_send(self):
        self.approve()
        def cancel(seconds):
            self.clock.sleep(seconds);self.store.revoke(self.p['id'],owner_confirmed=True)
        with patch('autonomous_free.time.sleep',cancel):self.run_once()
        self.assertEqual('stopped',self.p['status']);self.assertEqual(1,len(self.fake.requests))
        self.assertEqual('failed',self.p['real_ai']['attempts'][-1]['status'])
    def test_explicit_optional_cap_and_execution_deadline(self):
        self.project(max_calls=3);self.approve();self.run_once()
        self.assertEqual(3,len(self.fake.requests));self.assertEqual('optional_technical_cap_reached',self.p['reason_code'])
        self.project();self.approve();original=self.fake.alter
        def advance(r):self.clock.value+=timedelta(seconds=1801);return original(r)
        self.fake.alter=advance;self.run_once()
        self.assertEqual('run_deadline_reached',self.p['reason_code']);self.assertEqual(1,len(self.fake.requests))
    def test_duplicate_revised_content_and_stagnant_reviews_stop(self):
        self.approve();self.models.always_revise=True
        original=self.models.employee_response
        def repeat(phase,ctx):return original(phase,{**ctx,'revision_feedback':''})
        self.models.employee_response=repeat;self.run_once()
        self.assertEqual('repeated_employee_result',self.p['reason_code'])
        self.project(max_revisions_per_task=2);self.approve();self.models.employee_response=original
        self.run_once();self.assertEqual('quality_stagnation',self.p['reason_code'])
    def test_revision_bound_quality_unknown_and_invalid_responses(self):
        self.project(max_revisions_per_task=0);self.approve();self.models.always_revise=True;self.run_once()
        self.assertEqual('revision_limit',self.p['reason_code'])
        self.project();self.approve();self.models.unknown=True;self.run_once()
        self.assertEqual('stopped',self.p['status']);self.assertFalse(self.p['artifacts'])
        for alteration in ['finish','json','secret','tools']:
            self.project();self.approve();self.models.unknown=False
            def alter(r):
                c=r['choices'][0]
                if alteration=='finish':c['finish_reason']='length'
                if alteration=='json':c['message']['content']='{'
                if alteration=='secret':c['message']['content']=KEY
                if alteration=='tools':c['message']['tool_calls']=[{}]
                return r
            self.alter=alter;self.run_once();self.assertEqual('stopped',self.p['status']);self.assertEqual(1,len(self.fake.requests))
            self.assertNotIn(KEY,self.store.path(self.p['id']).read_text())
    def test_duplicate_operation_and_concurrency(self):
        self.approve();original=self.company._commit
        def crash(p,event,**details):original(p,event,**details);raise KeyboardInterrupt()
        with patch.object(self.company,'_commit',crash),self.assertRaises(KeyboardInterrupt):self.run_once()
        p=self.store.load(self.p['id']);p['phase']='plan';self.store.save(p)
        self.company=self.engine();self.run_once(resume=True)
        self.assertEqual('duplicate_operation',self.p['reason_code']);self.assertEqual(1,len(self.fake.requests))
        self.project();self.approve()
        with self.store.lock(self.p['id']),self.assertRaises(CompanyError):self.run_once()
        with self.company._execution_lock,self.assertRaises(CompanyError):self.run_once()
    def test_legacy_namespace_and_contract_cannot_be_lifted(self):
        legacy=LiveStore(Path(self.tmp.name)/'legacy');p=legacy.create('과거 한도 프로젝트',max_calls=3)
        body=legacy.prepare(p['id']);legacy.approve(p['id'],body,review_hash=digest(body),owner_confirmed=True)
        before=legacy.path(p['id']).read_bytes()
        with self.assertRaises(CompanyError):FreeStore(legacy.root).load(p['id'])
        with self.assertRaises(CompanyError):FreeStore(legacy.root).create('새 프로젝트')
        with self.assertRaises(CompanyError):FreeCompany(legacy,LiveManagerProvider(),LiveEmployeeProvider(),LiveConfig(KEY))
        with self.assertRaises(CompanyError):LiveCompany(self.store,LiveManagerProvider(),LiveEmployeeProvider(),LiveConfig(KEY))
        self.assertEqual(before,legacy.path(p['id']).read_bytes())
        self.assertEqual(3,legacy.load(p['id'])['limits']['max_calls']);self.assertEqual(2,legacy.grant(legacy.load(p['id']))['body']['per_start'])
    def test_stale_goal_preview_replay_and_limit_expansion_rejected(self):
        b=self.store.prepare(self.p['id']);p=self.store.load(self.p['id']);p['goal']='수정한 목표';self.store.save(p)
        with self.assertRaises(CompanyError):self.store.approve(p['id'],b,review_hash=digest(b),owner_confirmed=True)
        self.approve()
        with self.assertRaises(CompanyError):self.approve()
        p=self.store.load(p['id']);p['limits']['max_total_revisions']=4;self.store.save(p)
        with self.assertRaises(CompanyError):self.run_once()
        self.assert_no_send()

    def test_unapproved_context_and_secret_input_zero_send(self):
        self.approve();p=self.store.load(self.p['id'])
        with self.assertRaises(CompanyError):
            self.company._call(p,LiveManagerProvider(),'plan',None,{'goal':p['goal'],'unapproved_files':[]})
        self.assert_no_send()
        self.project('목표 '+KEY);self.approve()
        with self.assertRaises(CompanyError):self.run_once()
        self.assert_no_send()

    def test_price_filter_and_response_size_cannot_be_relaxed(self):
        self.approve()
        with patch.object(self.company,'_prepare_payload',lambda p:{**p,'provider':{'allow_fallbacks':True}}):self.run_once()
        self.assertEqual('free_payload_required',self.p['reason_code']);self.assert_no_send()
        self.project();self.approve()
        with patch('autonomous_live.urlopen',return_value=BytesIO(b'x'*262145)):self.run_once()
        self.assertEqual('response_too_large',self.p['reason_code'])
        self.assertEqual('failed',self.p['real_ai']['attempts'][0]['status'])

    def test_revised_content_with_changed_evidence_is_still_stagnant(self):
        self.approve();self.models.always_revise=True;original=self.models.employee_response
        def repeat(phase,ctx):
            result=json.loads(original(phase,{**ctx,'revision_feedback':''}))
            result['evidence']+=' 다른 설명' if ctx['revision_feedback'] else ''
            return json.dumps(result)
        self.models.employee_response=repeat;self.run_once()
        self.assertEqual('repeated_employee_result',self.p['reason_code'])

    def test_cli_create_prepare_approve_run_once_and_legacy_dispatch(self):
        from autonomous_live_cli import main
        root=Path(self.tmp.name)/'cli';prefix=['--store',str(root)];out=StringIO()
        with redirect_stdout(out):self.assertEqual(0,main(prefix+['create','--goal','도서관 안내문']))
        created=json.loads(out.getvalue());project_id=created['id'];self.fake.store=FreeStore(root);self.fake.project_id=project_id
        self.assertIsNone(self.fake.store.load(project_id)['limits']['max_calls'])
        out=StringIO();proposal=Path(self.tmp.name)/'proposal.json'
        with redirect_stdout(out):self.assertEqual(0,main(prefix+['prepare',project_id,'--proposal-out',str(proposal)]))
        b=json.loads(proposal.read_text());self.assertFalse((root/'.operating-consent.key').exists())
        out=StringIO()
        with redirect_stdout(out):self.assertEqual(0,main(prefix+['approve',project_id,'--proposal',str(proposal),
                                                 '--review-hash',digest(b),'--owner-confirmed']))
        approved=json.loads(out.getvalue());out=StringIO()
        with redirect_stdout(out):self.assertEqual(0,main(prefix+['run',project_id,'--state-hash',approved['storage_hash']]))
        result=json.loads(out.getvalue());self.assertEqual('delivered',result['status']);self.assertEqual(6,result['calls_used'])
        self.assertNotIn(KEY,out.getvalue())


if __name__=='__main__':unittest.main()
