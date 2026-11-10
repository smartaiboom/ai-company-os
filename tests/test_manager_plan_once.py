"""Single plan acceptance safety using mocked HTTP. No real account or AI calls."""
from copy import deepcopy
from datetime import datetime,timedelta
from io import BytesIO,StringIO
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from autonomous_company import CompanyError, digest, now
from goal_dialogue_live import OneCallAcceptanceStore, LiveDialogueStore
from quality_provider import QualityProviderStore
from manager_plan_acceptance import VideoManagerPlanStore
from manager_plan_cli import main


def strategy():
    return dict(action='propose_strategy',audience='한국어 성인 초보자',core_message='목적과 조건을 함께 질문하기',
        hook_plan='처음3초에 모호한 답변의 문제를 사례로 제시',demonstration='가상 메뉴 질문의 조건 추가 전후를 화면녹화로 비교',
        segments=[dict(seconds=6,story=f'이야기 구간{i}',visual=f'수동 시연/장면{i}',source_id=f'shot-{i}') for i in range(10)],
        sources=[dict(id=f'shot-{i}',prompt=f'개인정보 없는 세로 시연 장면{i}',seconds=6,status='external_clip_pending') for i in range(10)],
        script_direction='한 가지 메뉴 질문으로 설명; 사실 확인은 미완료',voice_direction='쉬운 한국어, 자연스러움 미평가',
        tasks=[dict(id='script',role='writer',instructions='목적과 조건 예시를 작성',depends_on=[],completion_criteria='60초 대본과 출처/미확인 구분'),
               dict(id='edit',role='editor',instructions='대본에 맞춘 실제 소스 요청',depends_on=['script'],completion_criteria='반복 없는 장면 수요표')],
        uncertainty=['실제 답변/권리/소스/음성 검증 없음'],questions=[],source_status='external_clip_pending',
        rights_status='unverified',video_status='not_created')


def envelope(value):
    return BytesIO(json.dumps(dict(candidates=[dict(finishReason='STOP',content=dict(role='model',parts=[dict(text=json.dumps(value,ensure_ascii=False))]))],
        usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=20,totalTokenCount=40))).encode())


class ManagerPlanOnceTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.store=VideoManagerPlanStore(self.root/'scope');self.p=self.store.create();self.pid=self.p['id']
        self.key='new-scope-fixture-credential'
        self.enterContext(patch('socket.socket.connect',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')))
        self.http=self.enterContext(patch('goal_dialogue_live.send_once'))

    def verify(self,**overrides):
        args=dict(api_key=self.key,project_api_key=self.key,project=self.store.acceptance_project,
                  free_tier_confirmed=True,billing_disabled=True,quota_available=True,official_docs_reviewed=True)
        args.update(overrides)
        return self.store.verify_project_key(self.pid,**args)

    def approve(self):
        self.verify();review=self.store.prepare_consent(self.pid)
        self.store.approve_consent(self.pid,review['review_hash'],api_key=self.key,owner_confirmed=True,
                                   free_project_confirmed=True,google_data_policy_accepted=True)
        return review

    def ask(self):
        with patch('manager_plan_once.MANAGER_PLAN_EXECUTION_ENABLED',True):
            return self.store.ask_ai(self.pid,api_key=self.key)

    def fresh(self,name):
        self.store=VideoManagerPlanStore(self.root/name);self.p=self.store.create();self.pid=self.p['id']

    def test_exact_private_payload_default_block_and_singleton(self):
        review=self.store.prepare_consent(self.pid)
        path=self.store.path(self.pid).with_suffix('.payload.json');raw=path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),review['body']['payload_hash'])
        self.assertEqual(json.loads(raw),review['wire_payload'])
        self.assertEqual(self.store.root.stat().st_mode & 0o077,0);self.assertEqual(path.stat().st_mode & 0o077,0)
        context=json.loads(json.loads(raw)['contents'][0]['parts'][0]['text'])
        self.assertEqual(context['phase'],'plan');self.assertNotIn('real_ai',context)
        self.assertEqual(review['body']['calls'],1);self.assertEqual(review['body']['total_limit'],1)
        self.assertEqual(review['body']['policy']['allowed_phases'],['plan'])
        with self.assertRaises(CompanyError):self.store.create()
        self.approve()
        with patch.dict(os.environ,GEMINI_API_KEY=self.key,QUALITY_TRANSPORT_ENABLED='1',MANAGER_PLAN_EXECUTION_ENABLED='1'):
            with self.assertRaisesRegex(CompanyError,'manager_plan_execution_disabled'):self.store.ask_ai(self.pid,api_key=self.key)
        self.http.assert_not_called();self.assertFalse(self.store.load(self.pid)['real_ai']['attempts'])

    def test_one_plan_native_transport_and_all_followups_blocked(self):
        review=self.approve()
        def response(request,timeout):
            state=self.store.load(self.pid)
            self.assertEqual(state['real_ai']['attempts'][0]['status'],'reserved')
            self.assertEqual(request.data,self.store.path(self.pid).with_suffix('.payload.json').read_bytes())
            self.assertEqual(request.get_header('X-goog-api-key'),self.key)
            self.assertNotIn(self.key,request.full_url);self.assertNotIn(self.key,request.data.decode())
            self.assertEqual(request.full_url,review['body']['policy']['endpoint']);self.assertEqual(timeout,90)
            return envelope(strategy())
        self.http.side_effect=response
        result=self.ask();self.assertEqual(result['status'],'needs_user_review')
        self.assertEqual(result['real_ai']['attempts'][0]['status'],'completed');self.assertFalse(result['simulation'])
        self.assertTrue(all(v['status']=='unassessed' for v in result['strategy_review'].values()))
        with self.assertRaises(CompanyError):self.ask()
        for name in ('answer','revise','confirm','clarify','handoff_video','propose'):
            with self.subTest(method=name):
                with self.assertRaises((CompanyError,ValueError,TypeError)):getattr(self.store,name)(self.pid,None)
        self.assertEqual(self.http.call_count,1)
        self.assertNotIn(self.key,json.dumps(result))
        target=os.getenv('MANAGER_PLAN_SAMPLE_OUTPUT')
        if target:
            path=Path(target);self.assertTrue(path.is_absolute() and path.is_relative_to('/tmp'))
            path.write_text(json.dumps(dict(provenance='mock HTTP; no real AI inference',result=result),ensure_ascii=False,indent=2))

    def test_necessary_clarification_consumes_only_request(self):
        self.approve()
        value=dict(action='needs_clarification',audience='초보자',questions=[dict(question='필수 시연 환경은 무엇인가요?',reason='실제 시연 가능 여부 판단')],
                   uncertainty=['시연 환경 미확인'],source_status='external_clip_pending',rights_status='unverified',video_status='not_created')
        self.http.side_effect=lambda *a,**k:envelope(value)
        result=self.ask();self.assertEqual(result['manager_plan']['action'],'needs_clarification')
        with self.assertRaises(CompanyError):self.ask()
        self.assertEqual(self.http.call_count,1)

    def test_account_key_docs_and_exact_review_binding(self):
        initial=self.store.prepare_consent(self.pid)
        with self.assertRaises(CompanyError):self.store.approve_consent(self.pid,initial['review_hash'],api_key=self.key,
            owner_confirmed=True,free_project_confirmed=True,google_data_policy_accepted=True)
        for kwargs in ({'billing_disabled':False},{'quota_available':False},{'official_docs_reviewed':False},
                       {'project_api_key':'other-key'},{'free_tier_confirmed':False}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(CompanyError):self.verify(**kwargs)
        self.verify()
        with self.assertRaises(CompanyError):self.store.approve_consent(self.pid,initial['review_hash'],api_key=self.key,
            owner_confirmed=True,free_project_confirmed=True,google_data_policy_accepted=True)
        review=self.store.prepare_consent(self.pid)
        with self.assertRaisesRegex(CompanyError,'active_key_changed'):self.store.approve_consent(self.pid,review['review_hash'],api_key='other-key',
            owner_confirmed=True,free_project_confirmed=True,google_data_policy_accepted=True)
        self.approve()
        with patch('manager_plan_once.MANAGER_PLAN_EXECUTION_ENABLED',True):
            with self.assertRaisesRegex(CompanyError,'active_key_changed'):self.store.ask_ai(self.pid,api_key='changed-key')
        self.http.assert_not_called()

    def test_expiry_signature_input_change_and_mode_isolation(self):
        self.approve()
        later=(datetime.fromisoformat(now())+timedelta(hours=2)).isoformat()
        with patch('goal_dialogue_live.now',return_value=later):
            with self.assertRaises(CompanyError):self.ask()
        p=self.store.load(self.pid);p['grants'][-1]['signature']='invalid';self.store.save(p)
        with self.assertRaisesRegex(CompanyError,'invalid_consent_signature'):self.ask()
        self.fresh('changed-input');self.approve()
        p=self.store.load(self.pid);p['goal']='changed';self.store.save(p)
        with self.assertRaisesRegex(CompanyError,'manager_plan_scope_changed'):self.ask()
        for cls in (OneCallAcceptanceStore,LiveDialogueStore,QualityProviderStore):
            with self.subTest(cls=cls):
                with self.assertRaises(CompanyError):cls(self.store.root).load(self.pid)
        self.http.assert_not_called()

    def test_timeout_http_invalid_response_and_interrupt_are_consumed(self):
        for failure in ('timeout','429','503','invalid_json','interrupt'):
            with self.subTest(failure=failure):
                self.fresh(failure);self.approve()
                if failure=='timeout':self.http.side_effect=TimeoutError('private exception text')
                elif failure in ('429','503'):self.http.side_effect=HTTPError('https://invalid',int(failure),'private',{},BytesIO(b'private'))
                elif failure=='interrupt':self.http.side_effect=KeyboardInterrupt()
                else:self.http.side_effect=lambda *a,**k:BytesIO(b'invalid json')
                with self.assertRaises((CompanyError,KeyboardInterrupt)):self.ask()
                count=self.http.call_count
                with self.assertRaises(CompanyError):self.ask()
                self.assertEqual(self.http.call_count,count)
                p=self.store.load(self.pid);self.assertEqual(len(p['real_ai']['attempts']),1)
                self.assertIn(p['real_ai']['attempts'][0]['status'],('reserved','uncertain'))
                self.assertNotIn('private exception text',json.dumps(p));self.assertNotIn('manager_plan',p)

    def test_fabricated_source_rights_bad_timeline_and_invalid_schema_rejected(self):
        variants=[]
        for field,value in [('rights_status','verified'),('video_status','created'),('source_status','available')]:
            data=strategy();data[field]=value;variants.append(data)
        data=strategy();data['segments'][0]['seconds']=True;variants.append(data)
        data=strategy();data['sources'][0]['seconds']=1;variants.append(data)
        data=strategy();data['segments'][0]['seconds']=5;variants.append(data)
        data=strategy();data['tasks'][0]['depends_on']=['edit'];variants.append(data)
        for index,value in enumerate(variants):
            with self.subTest(index=index):
                self.fresh('invalid-'+str(index));self.approve();self.http.side_effect=lambda *a,**k:envelope(value)
                with self.assertRaises(CompanyError):self.ask()
                self.assertEqual(len(self.store.load(self.pid)['real_ai']['attempts']),1)
                self.assertNotIn('manager_plan',self.store.load(self.pid))

    def test_cli_preparation_never_transmits_or_prompts_in_insecure_terminal(self):
        output=StringIO();errors=StringIO()
        with patch('sys.stdout',output),patch('sys.stderr',errors):
            root=str(self.root/'cli')
            self.assertEqual(main(['--root',root,'create']),0)
            pid=json.loads(output.getvalue())['id'];output.seek(0);output.truncate(0)
            self.assertEqual(main(['--root',root,'prepare',pid]),0)
            data=json.loads(output.getvalue());self.assertEqual(data['execution'],'disabled')
            with patch('sys.stdin.isatty',return_value=False):self.assertEqual(main(['--root',root,'verify-key',pid]),1)
            self.assertEqual(main(['--root',root,'execute',pid]),1)
        self.http.assert_not_called()
