"""Synthetic full provider workflow and local HTTP budget forms; external network blocked."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from itertools import count
import json
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from autonomous_company import digest, CompanyError
from autonomous_gemini35 import Gemini35Config, MODEL, ENDPOINT
from autonomous_live import LiveManagerProvider, LiveEmployeeProvider
from budget_video_provider import BudgetVideoCompany
from studio_server import Studio, make_server
from tests.test_script_quality import script_from_beats, script_callbacks
from voice_quality import AUDIENCE


class Response(BytesIO):
    status=200
    headers={}


class FixtureCompany(BudgetVideoCompany):
    source='offline_http_fixture'


class BudgetCutroomTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        original_connect=socket.socket.connect
        original_dns=socket.getaddrinfo
        def connect(sock,address):
            if address[0] not in ('127.0.0.1','::1'):
                raise AssertionError('external network forbidden')
            return original_connect(sock,address)
        def dns(host,*args,**kwargs):
            if host not in ('127.0.0.1','::1'):
                raise AssertionError('external DNS forbidden')
            return original_dns(host,*args,**kwargs)
        self.enterContext(patch.object(socket.socket,'connect',connect))
        self.enterContext(patch('socket.getaddrinfo',dns))
        self.key='synthetic-budget-cutroom-api-key'
        self.enterContext(patch.dict('os.environ',GEMINI_API_KEY=self.key,GEMINI35_MODEL=MODEL,
            GEMINI35_ENDPOINT=ENDPOINT,GEMINI35_AUTONOMOUS_FREE_ENABLED='1',
            BUDGET_GEMINI_ACCOUNT_PROJECT='synthetic-account',BUDGET_GEMINI_FREE_ACCOUNT_CONFIRMED='1'))
        ticks=count()
        self.enterContext(patch('autonomous_free.pacing_now',side_effect=lambda:
            (datetime(2026,1,1,tzinfo=timezone(timedelta(hours=9)))+timedelta(seconds=3*next(ticks))).isoformat()))
        self.studio=Studio(self.root)
        self.pid=self.studio.create(dict(goal='합성 영상 예산 경로',audience=AUDIENCE,language='한국어',
            platform='YouTube',duration=60,notes='오프라인만',key='00000000-0000-4000-8000-000000000081'))['id']
        self.store=self.studio.budget_store()
        self.job=None
        self.studio.budget_company_factory=lambda store:FixtureCompany(store,LiveManagerProvider('fixture-manager'),
            LiveEmployeeProvider('fixture-staff'),Gemini35Config(self.key))
        def beat(a,b,line,shot):
            return dict(start=a,end=b,narration=line,caption='합성 예제',screen='가상 비교',shot_type=shot,
                        source_ref='미확보',source_status='pending',fact_status='illustrative')
        script=script_from_beats([beat(0,3,'왜 다를까요?','card'),beat(3,60,'두 화면을 비교해 보세요.','demo')])
        script['provenance']=dict(author='synthetic fixture',model=MODEL,mock=False)
        manager,employee=script_callbacks(script,script)
        self.phases=[]
        def send(request,timeout):
            p=self.store.load(self.job)
            self.assertEqual(p['real_ai']['attempts'][-1]['status'],'reserved')
            ledger=self.studio.budget_ledger()._load(self.job)
            self.assertEqual(ledger['attempts'][-1]['status'],'reserved')
            self.assertEqual(request.full_url,ENDPOINT)
            message=json.loads(json.loads(request.data)['contents'][0]['parts'][0]['text'])
            phase,context=message['phase'],message['data'];self.phases.append(phase)
            result=json.loads(employee(phase,context) if phase=='execute' else manager(phase,context))
            if phase=='finalize':
                result.update(action='deliver',content='합성 내부 검토 결과',checks=[{**c,'status':'met'} for c in result['checks']])
            result.pop('task_refs',None)
            return Response(json.dumps(dict(candidates=[dict(finishReason='STOP',content=dict(role='model',
                parts=[dict(text=json.dumps(dict(result=result),ensure_ascii=False))]))],
                usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=20,totalTokenCount=40))).encode())
        self.http=self.enterContext(patch('budget_video_provider.send_once',side_effect=send))
        self.server=make_server('127.0.0.1',0,self.studio)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close_server)
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.path=f'/api/project/workspace/{self.pid}'
        status,detail=self.request(self.path+'/budget-prepare',dict(account_project='synthetic-account',confirm_free_account=True))
        self.assertEqual(status,200)
        self.job=detail['budget_setup']['provider_job']
        review=detail['budget_setup']['review_hash']
        self.assertNotIn(self.key,json.dumps(detail))
        self.assertNotIn('credential_binding',json.dumps(detail))
        self.assertEqual(self.request(self.path+'/budget-consent',dict(review_hash=review,action='approve'))[0],200)
        self.assertEqual(self.studio.budget_ledger().view(self.job)['resources']['text']['approved'],0)
        self.assertEqual(self.http.call_count,0)

    def close_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join(5)

    def request(self,path,body=None,token=True):
        headers={}
        if body is not None:
            headers['Content-Type']='application/json'
            if token: headers['X-Studio-Token']=self.studio.token
        req=Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urlopen(req,timeout=10) as response:
                return response.status,json.load(response)
        except HTTPError as exc:
            with exc:
                return exc.code,json.load(exc)

    def estimate(self,n):
        return self.studio.propose_budget(self.pid,{'text':n},reason='합성 관리자 작업계획',progress='대본 단계 보존',
            cost_impact='동일 무료 범위, 비용 미확인',failure_risk='실패도 소모, 자동 재시도 없음',plan_hash=digest('fixture plan'))

    def decide(self,request,action='approve',**kwargs):
        return self.request(self.path+'/budget-decide',dict(request_id=request['id'],
            review_hash=digest(request),action=action),**kwargs)

    def test_http_initial_approval_shortage_extension_continues_same_workflow(self):
        request=self.estimate(2)
        self.assertEqual(self.request('/api/studio')[1]['projects'][0]['budget_pending'],1)
        self.assertEqual(self.decide(request,token=False)[0],403)
        self.assertEqual(self.decide(request)[0],200)
        self.assertEqual(self.request(self.path+'/budget-run',{})[0],200)
        p=self.store.load(self.job)
        self.assertEqual((p['reason_code'],len(p['real_ai']['attempts'])),('budget_approval_required',2))
        self.assertEqual(self.phases,['plan','execute'])
        detail=self.request(self.path)[1]
        pending=detail['budget']['requests'][-1]
        self.assertEqual(self.request(self.path+'/budget-run',{})[0],409)
        self.assertEqual(len(self.studio.budget_ledger().view(self.job)['requests']),2)
        self.assertEqual(self.request(self.path+'/budget-decide',dict(request_id=pending['id'],review_hash='forged',action='approve'))[0],409)
        self.assertEqual(self.request(self.path+'/budget-decide',dict(request_id=pending['id'],review_hash=pending['review_hash'],action='approve'))[0],200)
        self.assertEqual(self.request(self.path+'/budget-decide',dict(request_id=pending['id'],review_hash=pending['review_hash'],action='approve'))[0],409)
        self.assertEqual(pending['amounts'],{'text':4})
        self.assertEqual(self.request(self.path+'/budget-run',{})[0],200)
        final=self.store.load(self.job)
        self.assertEqual(final['status'],'external_clip_pending',final.get('reason_code'))
        self.assertEqual(self.phases,['plan','execute','review','execute','review','finalize'])
        self.assertEqual(self.studio.budget_ledger().view(self.job)['resources']['text']['consumed'],6)
        self.assertEqual(len(final['assignments'][0]['versions']),1)
        self.assertEqual(final['final']['source'],'offline_http_fixture')

    def test_real_provider_key_and_model_guards_before_reservation_and_failure_no_retry(self):
        self.assertEqual(self.decide(self.estimate(2))[0],200)
        with patch.dict('os.environ',GEMINI_API_KEY='wrong-synthetic-key'):
            self.assertEqual(self.request(self.path+'/budget-run',{})[0],409)
        with patch.dict('os.environ',GEMINI35_MODEL='different-model'):
            self.assertEqual(self.request(self.path+'/budget-run',{})[0],409)
        self.assertEqual(self.http.call_count,0)
        self.http.side_effect=TimeoutError('synthetic transport timeout')
        self.assertEqual(self.request(self.path+'/budget-run',{})[0],200)
        self.assertEqual(len(self.store.load(self.job)['real_ai']['attempts']),1)
        self.assertEqual(self.studio.budget_ledger().view(self.job)['resources']['text']['consumed'],1)
        self.assertEqual(self.request(self.path+'/budget-run',{})[0],409)
        self.assertEqual(self.http.call_count,1)

    def fresh_project(self):
        import uuid
        status,value=self.request('/api/project',dict(goal='추가 합성 새 프로젝트',audience=AUDIENCE,
            language='한국어',platform='YouTube',duration=60,notes='합성 fixture',key=str(uuid.uuid4())))
        self.assertEqual(status,201)
        self.pid=value['id'];self.path=f'/api/project/workspace/{self.pid}'

    def prepare_new(self,token=True,account='synthetic-account'):
        return self.request(self.path+'/budget-prepare',dict(account_project=account,confirm_free_account=True),token=token)

    def test_provisioning_auth_account_free_condition_and_idempotent_refresh(self):
        self.fresh_project()
        self.assertEqual(self.prepare_new(token=False)[0],403)
        self.assertEqual(self.prepare_new(account='unauthorized-account')[0],409)
        with patch.dict('os.environ',BUDGET_GEMINI_FREE_ACCOUNT_CONFIRMED='0'):
            self.assertEqual(self.prepare_new()[0],409)
        self.assertEqual(self.request(self.path)[1]['budget_setup']['status'],'available')
        prepared=self.prepare_new()[1]['budget_setup']
        self.assertEqual(prepared,self.prepare_new()[1]['budget_setup'])
        self.assertEqual(prepared,self.request(self.path)[1]['budget_setup'])
        self.assertFalse(self.store._grant_path(prepared['provider_job']).exists())
        rejected=self.request(self.path+'/budget-consent',dict(review_hash=prepared['review_hash'],action='reject'))
        self.assertEqual(rejected[0],200)
        self.assertIsNone(rejected[1]['budget'])
        self.assertEqual(rejected[1]['budget_setup']['status'],'rejected')
        self.assertEqual(self.prepare_new()[0],409)
        self.assertFalse(self.store._grant_path(prepared['provider_job']).exists())
        self.assertEqual(self.http.call_count,0)

    def test_registered_provider_signature_and_grant_expiry_block_without_sending(self):
        later=(datetime.now(timezone(timedelta(hours=9)))+timedelta(hours=2)).isoformat()
        with patch('autonomous_free.now',return_value=later):
            self.assertEqual(self.request(self.path+'/budget-run',{})[0],409)
        grant_path=self.store._grant_path(self.job)
        record=json.loads(grant_path.read_text())
        record['signature']='synthetic tampered signature'
        grant_path.write_text(json.dumps(record))
        self.assertEqual(self.request(self.path+'/budget-run',{})[0],409)
        self.assertEqual(self.http.call_count,0)

    def test_provider_consent_hash_expiry_project_binding_and_changed_key(self):
        old_hash=self.request(self.path)[1]['budget_setup']['review_hash']
        self.fresh_project()
        prepared=self.prepare_new()[1]['budget_setup']
        for bad_hash in ('forged',old_hash):
            self.assertEqual(self.request(self.path+'/budget-consent',dict(review_hash=bad_hash,action='approve'))[0],409)
        with patch.dict('os.environ',GEMINI_API_KEY='different-synthetic-secret'):
            self.assertEqual(self.request(self.path+'/budget-consent',dict(review_hash=prepared['review_hash'],action='approve'))[0],409)
        later=(datetime.now(timezone(timedelta(hours=9)))+timedelta(hours=2)).isoformat()
        with patch('autonomous_free.now',return_value=later):
            self.assertEqual(self.request(self.path+'/budget-consent',dict(review_hash=prepared['review_hash'],action='approve'))[0],409)
        self.assertFalse(self.store._grant_path(prepared['provider_job']).exists())
        self.assertEqual(self.http.call_count,0)

    def test_concurrent_prepare_then_approval_duplicate_and_existing_project_block(self):
        self.fresh_project()
        results=[]
        threads=[threading.Thread(target=lambda:results.append(self.prepare_new())) for _ in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(5)
        prepared=[r[1]['budget_setup'] for r in results if r[0]==200]
        self.assertTrue(prepared)
        self.assertEqual(len({p['provider_job'] for p in prepared}),1)
        approved=self.request(self.path+'/budget-consent',dict(review_hash=prepared[0]['review_hash'],action='approve'))
        self.assertEqual(approved[0],200)
        self.assertEqual(self.request(self.path+'/budget-consent',dict(review_hash=prepared[0]['review_hash'],action='approve'))[0],409)
        self.assertEqual(self.prepare_new()[0],409)
        self.fresh_project()
        self.studio.action('workspace',self.pid,'mission',{})
        self.assertEqual(self.prepare_new()[0],409)
        self.assertEqual(self.http.call_count,0)

    def test_cutroom_provider_link_change_cannot_send(self):
        self.assertEqual(self.decide(self.estimate(1))[0],200)
        project=self.studio.project('workspace',self.pid)
        project['representative']['budget_job']='qualityprovider-'+'0'*32
        self.studio.stores['workspace'].save(project)
        company=self.studio.budget_company_factory(self.store)
        with self.assertRaisesRegex(CompanyError,'budget_cutroom_binding_changed'):
            company.run(self.job,expected_state_hash=self.store.load(self.job)['storage_hash'])
        self.assertEqual(self.http.call_count,0)

    def test_concurrent_http_run_is_blocked(self):
        self.assertEqual(self.decide(self.estimate(1))[0],200)
        entered,release=threading.Event(),threading.Event()
        original=self.http.side_effect
        def blocking(request,timeout):
            entered.set()
            release.wait(5)
            return original(request,timeout)
        self.http.side_effect=blocking
        result=[]
        thread=threading.Thread(target=lambda:result.append(self.request(self.path+'/budget-run',{})))
        thread.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertEqual(self.request(self.path+'/budget-run',{})[0],409)
        finally:
            release.set();thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result[0][0],200)
        self.assertEqual(self.http.call_count,1)

    def test_http_reject_and_provider_revocation_scope_and_key_guards(self):
        req=self.estimate(2)
        self.assertEqual(self.decide(req,'reject')[0],200)
        self.assertEqual(self.request(self.path+'/budget-run',{})[0],200)
        self.assertEqual(self.http.call_count,0)
        pending=self.studio.budget_ledger().view(self.job)['requests'][-1]
        self.assertEqual(self.decide(pending)[0],200)
        self.assertEqual(self.request(self.path+'/budget-revoke',{})[0],200)
        self.assertEqual(self.request(self.path)[1]['budget']['consent_state'],'consent_revoked')
        self.assertEqual(self.request(self.path+'/budget-run',{})[0],409)
        self.assertEqual(self.http.call_count,0)
