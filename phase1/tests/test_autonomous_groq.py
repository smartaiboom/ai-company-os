"""Fake Groq wire protocol, signed synthetic consent, actual local FFmpeg."""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import timedelta
from io import BytesIO,StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from autonomous_company import CompanyError,digest,now
from autonomous_free import FreeStore,FreeCompany
from autonomous_groq import GroqStore,GroqCompany,GroqConfig
from autonomous_live import LiveManagerProvider,LiveEmployeeProvider,LiveConfig
from autonomous_live_cli import main
from groq_provider import MODEL,ENDPOINT,COST_POLICY,GroqFreeAdapter
from role_json_schema import response_format,matches
from tests.test_autonomous_free import Clock
from tests.support.autonomous_company_fixtures import FictionalModels
from tests.test_local_artifacts import VideoModels

KEY='synthetic-groq-only-key'
ENV={'GROQ_API_KEY':KEY,'GROQ_MODEL':MODEL,'GROQ_BASE_URL':ENDPOINT,
     'GROQ_AUTONOMOUS_FREE_ENABLED':'1','AI_REAL_REQUESTS_ENABLED':'0','AI_API_KEY':'synthetic-other-provider-key'}


class GroqVideoModels(VideoModels):
    """Fictional video decisions live only in this fixture, never in engine code."""
    def manager_response(self,phase,ctx):
        value=json.loads(super().manager_response(phase,ctx))
        if phase=='plan':
            value['criteria']=[{'id':'owner','description':'초보자를 위한 구체적인 한국어 질문 작성 안내'},
                               {'id':'uncertain','description':'20~30초 MP4 기술 검사와 미확인 품질 구분'}]
            for task,title,role,instructions in zip(value['tasks'],
                    ['대본 작성','장면 구성 및 로컬 영상 제작'],['대본 담당','영상 담당'],
                    ['짧고 구체적인 질문 작성법 대본을 준비한다.',
                     '수락된 선행 대본을 받아 자막 장면 JSON을 제출하고 실제 렌더 측정 결과를 보고한다.']):
                task.update(title=title,role=role,instructions=instructions)
            value['rationale']='대본 검토와 후속 영상 제작을 분담한다. 모의 출력이다.'
        elif phase=='review':
            value['rationale']='모의 관리자: 대본의 구체성과 제출된 렌더 메타데이터를 기준으로 검토한다.'
            if value['action']=='revise':value['feedback']='목표·상황·답변 형식을 포함한 구체적인 질문 예시를 추가한다.'
        else:
            value['content']='FAKE_GROQ_HTTPS_NOT_ACTUAL_AI: 자막·한국어 음성 MP4 제작 보고. 도구 측정 정보: '+ctx['results'][-1]['evidence']
        return json.dumps(value,ensure_ascii=False)
    def employee_response(self,phase,ctx):
        if ctx['previous_results']:return super().employee_response(phase,ctx)
        return json.dumps({'content':('목표·상황·답변 형식을 알려주세요. 예: 초보자에게 좋은 질문법을 세 문장으로 설명해 주세요.'
                                     if ctx['revision_feedback'] else '질문을 구체적으로 작성하세요. 예시 보완이 필요한 초안.'),
                           'evidence':'FAKE fixture 대본. 외부 자료 사용 없음.',
                           'uncertainty':'실제 AI 응답이나 교육 효과 검증이 아니다.'},ensure_ascii=False)


class FakeGroqHTTPS:
    def __init__(self,store,project_id,models):
        self.store,self.project_id,self.models=store,project_id,models
        self.requests=[];self.alter=None;self.headers={'x-ratelimit-remaining-requests':'999'}
    def __call__(self,request,timeout):
        assert request.full_url==ENDPOINT+'/chat/completions'
        assert request.get_header('Authorization')=='Bearer '+KEY
        p=self.store.load(self.project_id);entry=p['real_ai']['attempts'][-1]
        assert entry['status']=='reserved' and p['active_operation']==entry['id'] and entry['transport_started_at']
        payload=json.loads(request.data);data=json.loads(payload['messages'][1]['content'])
        phase=data['phase'];GroqFreeAdapter().validate_payload(payload,phase)
        assert KEY not in request.data.decode() and 'synthetic-other-provider-key' not in request.data.decode()
        self.requests.append(deepcopy(data))
        fn=self.models.manager_response if data['role']=='manager' else self.models.employee_response
        value=json.loads(fn(phase,data['data']))
        if phase=='finalize':value.pop('task_refs',None)
        wrapped={'result':value};assert matches(wrapped,response_format(phase)['json_schema']['schema'])
        response={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(wrapped,ensure_ascii=False)}}],
                  'usage':{'prompt_tokens':120,'completion_tokens':180,'total_tokens':300}}
        if self.alter:response=self.alter(response)
        stream=BytesIO(json.dumps(response).encode());stream.headers=self.headers
        return stream


class GroqTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        p=patch.dict(os.environ,ENV,clear=True);p.start();self.addCleanup(p.stop)
        for name in ('socket.socket.connect','socket.socket.connect_ex','socket.socket.sendto','socket.create_connection','socket.getaddrinfo','socket.gethostbyname'):
            p=patch(name,side_effect=AssertionError('external network forbidden'));p.start();self.addCleanup(p.stop)
        self.clock=Clock()
        for name,value in [('autonomous_groq.now',self.clock.now),('autonomous_free.now',self.clock.now),
                           ('autonomous_free.pacing_now',self.clock.now),('autonomous_live.now',self.clock.now),
                           ('autonomous_company.now',self.clock.now),('autonomous_free.time.sleep',self.clock.sleep)]:
            p=patch(name,value);p.start();self.addCleanup(p.stop)
        self.store=GroqStore(Path(self.tmp.name)/'groq')
        self.p=self.store.create('FAKE ONLY: 한국어 20~30초 자막 MP4',local_tools=['caption_video_v1'])
        self.models=GroqVideoModels();self.fake=FakeGroqHTTPS(self.store,self.p['id'],self.models)
        p=patch('autonomous_live.urlopen',self.fake);p.start();self.addCleanup(p.stop)
        self.company=self.engine()
    def engine(self,config=None):
        return GroqCompany(self.store,LiveManagerProvider('groq-free-manager'),LiveEmployeeProvider('groq-free-employee'),config or GroqConfig(KEY))
    def approve(self):
        body=self.store.prepare(self.p['id'],confirm_free_account=True)
        self.p=self.store.approve(self.p['id'],body,review_hash=digest(body),owner_confirmed=True);return body
    def run_once(self,resume=False):
        p=self.store.load(self.p['id']);self.p=self.company.run(p['id'],expected_state_hash=p['storage_hash'],resume=resume)
        return self.p
    def reset(self):
        self.p=self.store.create('FAKE generic text goal');self.fake.project_id=self.p['id'];self.fake.requests=[]
        self.fake.models=FictionalModels();self.fake.alter=None;self.fake.headers={}
    def test_cli_one_run_collaboration_revision_video_and_receipts(self):
        self.approve()
        with redirect_stdout(StringIO()) as out:
            code=main(['--store',str(self.store.root),'run',self.p['id'],'--state-hash',self.p['storage_hash']])
        self.assertEqual(0,code);self.p=self.store.result(self.p['id'])
        self.assertEqual('delivered',self.p['status'],self.p.get('reason_code'))
        self.assertEqual(8,len(self.fake.requests));self.assertEqual(1,len(self.p['sessions']))
        self.assertEqual(2,len(self.p['assignments']));self.assertEqual(1,sum(t['revisions'] for t in self.p['assignments']))
        self.assertTrue([r for r in self.fake.requests if r['role']=='employee'][-1]['data']['previous_results'])
        self.assertEqual(0,self.p['user_business_approval_requests'])
        receipt=next(e['receipt'] for e in self.p['events'] if e['event']=='local_tool_completed')
        self.assertTrue(receipt['decoded']);self.assertAlmostEqual(24,receipt['duration_seconds'],delta=.2)
        for a in self.p['real_ai']['attempts']:
            self.assertEqual('groq',a['provider_id']);self.assertEqual(MODEL,a['model'])
            self.assertTrue(a['free_account_policy_verified']);self.assertNotIn('cost_verified_zero',a)
            self.assertEqual('unverified',a['response_diagnostics']['cost'])
        self.run_once();self.assertEqual(8,len(self.fake.requests));self.assertNotIn(KEY,out.getvalue())
    def test_unverified_account_prepare_no_side_effects_and_no_send(self):
        before=self.store.path(self.p['id']).read_bytes();b=self.store.prepare(self.p['id'])
        self.assertFalse(b['account_verification']['free_plan'])
        with self.assertRaises(CompanyError):self.store.approve(self.p['id'],b,review_hash=digest(b),owner_confirmed=True)
        with self.assertRaises(CompanyError):self.run_once()
        self.assertEqual(before,self.store.path(self.p['id']).read_bytes());self.assertFalse((self.store.root/'.operating-consent.key').exists())
        self.assertEqual([],self.fake.requests)
    def test_contract_provider_model_scope_schema_cost_and_key_guards(self):
        b=self.store.prepare(self.p['id'],confirm_free_account=True)
        for field,value in [('provider','openrouter'),('model','openai/gpt-oss-120b'),('endpoint','https://evil.test'),
                            ('max_cost',1),('scopes',['goal']),('cost_policy',{}),('local_tools',{})]:
            changed=deepcopy(b);changed[field]=value
            with self.subTest(field=field),self.assertRaises(CompanyError):
                self.store.approve(self.p['id'],changed,review_hash=digest(changed),owner_confirmed=True)
        self.approve()
        for name,value in [('GROQ_API_KEY',''),('GROQ_API_KEY','different-key'),('GROQ_MODEL','paid'),
                           ('GROQ_BASE_URL','https://evil.test'),('GROQ_AUTONOMOUS_FREE_ENABLED','0')]:
            with patch.dict(os.environ,{name:value}),self.assertRaises(CompanyError):self.run_once()
        self.assertEqual([],self.fake.requests)
        with self.assertRaises(CompanyError):FreeCompany(self.store,LiveManagerProvider(),LiveEmployeeProvider(),LiveConfig(KEY))
        with self.assertRaises(CompanyError):FreeStore(self.store.root).load(self.p['id'])
    def test_invalid_finish_json_schema_refusal_and_cost_stop_without_retry(self):
        for kind in ('length','tools','unknown','json','schema','refusal','cost','key'):
            self.reset();self.approve()
            def alter(r):
                c=r['choices'][0];msg=c['message']
                if kind=='length':c['finish_reason']='length'
                if kind=='tools':c['finish_reason']='tool_calls'
                if kind=='unknown':c['finish_reason']=KEY
                if kind=='json':msg['content']='{'
                if kind=='schema':msg['content']='{"result":{"extra":"x"}}'
                if kind=='refusal':msg['refusal']='no'
                if kind=='cost':r['usage']['cost']=0.1
                if kind=='key':msg['content']=KEY
                return r
            self.fake.alter=alter;self.run_once();self.assertEqual('stopped',self.p['status'])
            count=len(self.fake.requests);self.run_once();self.assertEqual(count,len(self.fake.requests))
            self.assertNotIn(KEY,self.store.path(self.p['id']).read_text())
    def test_429_402_401_and_retry_headers_are_safe_no_auto_retry(self):
        for status in (429,402,401):
            self.reset();self.approve()
            headers={'retry-after':'12','x-ratelimit-remaining-tokens':'0','x-private':KEY}
            error=HTTPError(ENDPOINT,status,KEY,headers,BytesIO(KEY.encode()))
            with patch('autonomous_live.urlopen',side_effect=error):self.run_once()
            a=self.p['real_ai']['attempts'][-1]
            self.assertEqual('failed',a['status']);self.assertEqual(12,a['rate_limits']['retry-after'])
            self.assertNotIn(KEY,json.dumps(a));self.assertEqual([],self.fake.requests)
            if status in (429,402):
                with self.assertRaises(CompanyError):self.run_once(resume=True)
    def test_reported_quota_zero_stops_before_next_send(self):
        self.reset();self.approve();self.fake.headers={'x-ratelimit-remaining-requests':'0'}
        self.run_once();self.assertEqual(1,len(self.fake.requests));self.assertEqual('provider_rate_limit',self.p['reason_code'])
    def test_crash_receive_uncertain_and_continue_no_replay(self):
        self.reset();self.approve();original=self.company._persist
        def crash(p):
            original(p)
            if p['real_ai']['attempts'][-1]['status']=='completed':raise KeyboardInterrupt()
        with patch.object(self.company,'_persist',crash),self.assertRaises(KeyboardInterrupt):self.run_once()
        self.company=self.engine()
        with self.assertRaises(CompanyError):self.run_once(resume=True)
        self.assertEqual(1,len(self.fake.requests))
    def test_account_expiry_revocation_and_wrong_payload(self):
        self.reset();self.approve()
        self.clock.value+=timedelta(hours=25)
        with self.assertRaises(CompanyError):self.run_once()
        self.store.revoke(self.p['id'],owner_confirmed=True)
        self.assertEqual([],self.fake.requests)
        self.reset();self.approve()
        with patch.object(self.company,'_prepare_payload',lambda p:{**p,'provider':{'max_price':0}}):self.run_once()
        self.assertEqual('invalid_fields',self.p['reason_code']);self.assertEqual([],self.fake.requests)
    def test_cli_draft_dispatch_and_provider_switch_block(self):
        root=Path(self.tmp.name)/'cli'
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(0,main(['--provider','groq','--store',str(root),'create','--goal','FAKE goal']))
        created=json.loads(out.getvalue());store=GroqStore(root)
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(0,main(['--store',str(root),'prepare',created['id']]))
        b=json.loads(out.getvalue())['contract'];self.assertEqual('groq',b['provider']);self.assertFalse(b['account_verification']['free_plan'])
        self.assertFalse((root/'.operating-consent.key').exists())
        with redirect_stdout(StringIO()):
            self.assertEqual(1,main(['--provider','openrouter','--store',str(root),'status',created['id']]))


class SchemaTests(unittest.TestCase):
    def test_all_objects_closed_and_required_and_no_paid_selector(self):
        def walk(s):
            if s.get('type')=='object':
                self.assertFalse(s['additionalProperties']);self.assertEqual(set(s['required']),set(s['properties']))
                for p in s['properties'].values():walk(p)
            if 'anyOf' in s:
                for p in s['anyOf']:walk(p)
            if 'items' in s:walk(s['items'])
        for phase in ('plan','execute','review','finalize'):walk(response_format(phase)['json_schema']['schema'])
