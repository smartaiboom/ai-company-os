"""Fake native Gemini responses; existing company workflow and real local MP4."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import BytesIO,StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError,URLError
import socket

from autonomous_company import CompanyError,digest
from autonomous_free import FreeStore
from autonomous_gemini import GeminiStore,GeminiCompany,GeminiConfig
from autonomous_live import LiveManagerProvider,LiveEmployeeProvider
from autonomous_live_cli import main
from gemini_provider import MODEL,ENDPOINT,GeminiFreeAdapter
from tests.test_autonomous_free import Clock
from tests.test_local_artifacts import VideoModels
from tests.support.autonomous_company_fixtures import FictionalModels
import gemini_first_project as first

KEY='fake-gemini-key-only'
ENV={'GEMINI_API_KEY':KEY,'GEMINI_MODEL':MODEL,'GEMINI_ENDPOINT':ENDPOINT,'GEMINI_AUTONOMOUS_FREE_ENABLED':'1'}


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        p=patch.dict(os.environ,ENV,clear=True);p.start();self.addCleanup(p.stop)
        for name in ('socket.socket.connect','socket.socket.connect_ex','socket.socket.sendto','socket.create_connection','socket.getaddrinfo','socket.gethostbyname'):
            p=patch(name,side_effect=AssertionError('external network forbidden'));p.start();self.addCleanup(p.stop)
        self.clock=Clock()
        for name,value in [('autonomous_gemini.now',self.clock.now),('autonomous_free.now',self.clock.now),
                           ('autonomous_free.pacing_now',self.clock.now),('autonomous_live.now',self.clock.now),
                           ('autonomous_company.now',self.clock.now),('autonomous_free.time.sleep',self.clock.sleep)]:
            p=patch(name,value);p.start();self.addCleanup(p.stop)
        self.store=GeminiStore(Path(self.tmp.name)/'gemini')
        self.requests=[];self.alter=None;self.models=FictionalModels(revise=True)
        self.create()
        p=patch('autonomous_live.urlopen',self.fake);p.start();self.addCleanup(p.stop)

    def create(self,video=False,max_calls=None):
        self.p=self.store.create('FAKE ONLY 합성 안내 영상' if video else 'FAKE ONLY 범용 목표',
                                 local_tools=['caption_video_v1'] if video else None,max_calls=max_calls)
        self.company=GeminiCompany(self.store,LiveManagerProvider('gemini-free-manager'),
                                  LiveEmployeeProvider('gemini-free-employee'),GeminiConfig(KEY))
        self.requests=[]

    def approve(self):
        b=self.store.prepare(self.p['id'],confirm_free_account=True)
        self.p=self.store.approve(self.p['id'],b,review_hash=digest(b),owner_confirmed=True)
        return b

    def run_company(self,resume=False):
        self.p=self.company.run(self.p['id'],expected_state_hash=self.p['storage_hash'],resume=resume)
        return self.p

    def fake(self,request,timeout):
        self.assertEqual(ENDPOINT,request.full_url)
        self.assertEqual('POST',request.get_method());self.assertEqual(KEY,request.get_header('X-goog-api-key'))
        self.assertNotIn(KEY,request.data.decode());self.assertLessEqual(timeout,90)
        disk=self.store.load(self.p['id']);a=disk['real_ai']['attempts'][-1]
        self.assertEqual('reserved',a['status']);self.assertEqual(a['id'],disk['active_operation'])
        self.assertTrue(a['transport_started_at'])
        payload=json.loads(request.data);data=json.loads(payload['contents'][0]['parts'][0]['text'])
        GeminiFreeAdapter().validate_payload(payload,data['phase'])
        self.requests.append(deepcopy(data))
        fn=self.models.manager_response if data['role']=='manager' else self.models.employee_response
        value=json.loads(fn(data['phase'],data['data']))
        if data['phase']=='finalize':value.pop('task_refs',None)
        envelope={'candidates':[{'finishReason':'STOP','content':{'role':'model','parts':[
            {'thought':True,'text':'private reasoning, ignored'}, {'text':json.dumps({'result':value},ensure_ascii=False)}]}}],
            'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':150,'totalTokenCount':250}}
        if self.alter:envelope=self.alter(envelope)
        response=BytesIO(json.dumps(envelope).encode());response.status=200;response.headers={}
        return response

    def test_workflow_revision_handoff_real_local_video_and_cli(self):
        self.create(video=True);self.models=VideoModels();self.approve()
        with redirect_stdout(StringIO()) as output:
            code=main(['--store',str(self.store.root),'run',self.p['id'],'--state-hash',self.p['storage_hash']])
        self.assertEqual(0,code);self.p=self.store.result(self.p['id'])
        self.assertEqual('delivered',self.p['status'],self.p.get('reason_code'))
        self.assertEqual(8,len(self.requests));self.assertEqual(2,len(self.p['assignments']))
        self.assertEqual(1,sum(t['revisions'] for t in self.p['assignments']))
        self.assertTrue([r for r in self.requests if r['role']=='employee'][-1]['data']['previous_results'])
        self.assertEqual(0,self.p['user_business_approval_requests'])
        receipt=next(e['receipt'] for e in self.p['events'] if e['event']=='local_tool_completed')
        self.assertTrue(receipt['decoded']);self.assertTrue(receipt['audio'])
        self.assertTrue(any(n.endswith('.mp4') for n in self.p['artifacts']))
        self.assertIn('final.md',self.p['artifacts']);self.assertNotIn(KEY,output.getvalue())
        self.assertNotIn('private reasoning',self.store.path(self.p['id']).read_text())
        for a in self.p['real_ai']['attempts']:
            self.assertEqual('gemini',a['provider_id']);self.assertTrue(a['free_account_policy_verified'])
            self.assertNotIn('cost_verified_zero',a);self.assertEqual(250,a['response_diagnostics']['tokens']['total_tokens'])
        self.run_company();self.assertEqual(8,len(self.requests))

    def test_unapproved_expired_mismatched_model_scope_and_environment(self):
        b=self.store.prepare(self.p['id'])
        with self.assertRaises(CompanyError):self.store.approve(self.p['id'],b,review_hash=digest(b),owner_confirmed=True)
        with self.assertRaises(CompanyError):self.run_company()
        self.assertFalse((self.store.root/'.operating-consent.key').exists())
        b=self.store.prepare(self.p['id'],confirm_free_account=True)
        for key,value in [('provider','groq'),('model','gemini-paid'),('endpoint','https://wrong.invalid'),
                          ('scopes',['goal']),('max_cost',1),('cost_policy',{})]:
            changed=deepcopy(b);changed[key]=value
            with self.subTest(field=key),self.assertRaises(CompanyError):
                self.store.approve(self.p['id'],changed,review_hash=digest(changed),owner_confirmed=True)
        self.approve()
        for key,value in [('GEMINI_MODEL','wrong'),('GEMINI_ENDPOINT','https://wrong.invalid'),
                          ('GEMINI_API_KEY','wrong'),('GEMINI_AUTONOMOUS_FREE_ENABLED','0')]:
            with patch.dict(os.environ,{key:value}),self.assertRaises(CompanyError):self.run_company()
        self.clock.value+=__import__('datetime').timedelta(hours=25)
        with self.assertRaises(CompanyError):self.run_company()
        with self.assertRaises(CompanyError):FreeStore(self.store.root).load(self.p['id'])
        self.assertEqual([],self.requests)

    def test_http_and_timeout_stop_without_retry_or_free_text(self):
        for status in (400,401,403,404,429,503):
            self.create();self.approve()
            error=HTTPError(ENDPOINT,status,KEY,{'Retry-After':'10'},BytesIO(KEY.encode()))
            with patch('autonomous_live.urlopen',side_effect=error) as send:
                self.run_company();self.assertEqual(1,send.call_count)
                self.assertEqual(status,self.p['real_ai']['attempts'][-1]['http_status'])
                try:self.run_company(resume=True)
                except CompanyError:pass
                self.assertEqual(1,send.call_count)
                self.assertNotIn(KEY,self.store.path(self.p['id']).read_text())
        for error,category in [(TimeoutError(KEY),'connect_timeout'),(URLError(socket.gaierror(-2,KEY)),'dns_error')]:
            self.create();self.approve()
            with patch('autonomous_live.urlopen',side_effect=error) as send:
                self.run_company();self.assertEqual(1,send.call_count)
                self.assertEqual(category,self.p['real_ai']['attempts'][-1]['provider_error_diagnostics']['category'])
                self.assertTrue(self.p['active_operation'])

    def test_malformed_refused_incomplete_unknown_usage_and_secret(self):
        for kind in ('empty','length','safety','prompt_block','refusal','thought_only','tool','json','schema','usage','tokens','cost','thought_tokens','secret'):
            self.create();self.approve()
            def alter(r):
                c=r['candidates'][0]
                if kind=='empty':r['candidates']=[]
                if kind=='length':c['finishReason']='MAX_TOKENS'
                if kind=='safety':c['finishReason']='SAFETY'
                if kind=='prompt_block':r['promptFeedback']={'blockReason':'SAFETY'}
                if kind=='refusal':c['refusal']=True
                if kind=='thought_only':c['content']['parts']=[{'text':'hidden','thought':True}]
                if kind=='tool':c['content']['parts']=[{'functionCall':{'name':'private'}}]
                if kind=='json':c['content']['parts']=[{'text':'{"result":'}]
                if kind=='schema':c['content']['parts']=[{'text':'{"result":{"extra":"bad"}}'}]
                if kind=='usage':r.pop('usageMetadata')
                if kind=='tokens':r['usageMetadata']['candidatesTokenCount']='unknown'
                if kind=='cost':r['usageMetadata']['cost']=0.1
                if kind=='thought_tokens':r['usageMetadata']['thoughtsTokenCount']=5000
                if kind=='secret':c['content']['parts']=[{'text':KEY}]
                return r
            self.alter=alter;self.run_company();self.assertEqual('stopped',self.p['status'],kind)
            self.assertEqual(1,len(self.requests));self.run_company();self.assertEqual(1,len(self.requests))
            self.assertNotIn(KEY,self.store.path(self.p['id']).read_text())

    def test_crash_after_reservation_and_optional_cap(self):
        self.approve()
        with patch('autonomous_live.urlopen',side_effect=KeyboardInterrupt()),self.assertRaises(KeyboardInterrupt):self.run_company()
        self.p=self.store.load(self.p['id'])
        with self.assertRaises(CompanyError):self.run_company(resume=True)
        self.assertEqual([],self.requests)
        self.create(max_calls=1);self.approve();self.run_company()
        self.assertEqual(1,len(self.requests));self.assertEqual('optional_technical_cap_reached',self.p['reason_code'])

    def test_response_read_timeout_and_broken_envelope_diagnostics(self):
        class ReadTimeout(BytesIO):
            status=200;headers={}
            def read(self,size):raise TimeoutError(KEY)
        for response,category,stage in [(ReadTimeout(),'read_timeout','response_read'),
                                         (BytesIO(b'{'),'parse_error','json_parse')]:
            self.create();self.approve();response.status=200;response.headers={}
            with patch('autonomous_live.urlopen',return_value=response) as send:
                self.run_company();self.assertEqual(1,send.call_count)
                a=self.p['real_ai']['attempts'][-1]
                self.assertEqual({'category':category,'stage':stage},a['provider_error_diagnostics'])
                self.assertEqual(200,a['http_status']);self.assertNotIn(KEY,json.dumps(a))

    def test_cli_prepare_provider_isolation_and_no_key_derivatives(self):
        with redirect_stdout(StringIO()) as output:
            code=main(['--provider','gemini','--store',str(self.store.root),'prepare',self.p['id'],'--confirm-gemini-free-account'])
        self.assertEqual(0,code);value=json.loads(output.getvalue())
        self.assertEqual('gemini',value['contract']['provider'])
        self.assertNotIn('credential_binding',value['contract']['account_verification'])
        self.assertFalse((self.store.root/'.operating-consent.key').exists())
        with redirect_stdout(StringIO()):
            self.assertEqual(1,main(['--provider','groq','--store',str(self.store.root),'status',self.p['id']]))

    def test_first_project_prepare_no_grant_execute_confirmation_and_no_relaunch(self):
        root=Path(self.tmp.name)/'first'
        with patch.object(first,'ROOT',root):
            manifest=first.prepare()
            store=GeminiStore(root);p=store.load(manifest['project_id'])
            self.assertFalse(p['real_ai']['enabled']);self.assertEqual([],p['real_ai']['attempts'])
            self.assertFalse((root/'.operating-consent.key').exists())
            with self.assertRaises(CompanyError):first.prepare()
            with self.assertRaises(CompanyError):first.execute(manifest['review_hash'])
            with self.assertRaises(CompanyError):first.execute('changed',owner_confirmed=True,confirm_free_tier=True)
            self.assertFalse((root/'owner-launch-consumed.json').exists())
            with patch.object(GeminiCompany,'run',return_value={'id':p['id'],'status':'FAKE_ONLY'}) as run:
                self.assertEqual('FAKE_ONLY',first.execute(manifest['review_hash'],owner_confirmed=True,confirm_free_tier=True)['status'])
                self.assertEqual(1,run.call_count)
                with self.assertRaises(CompanyError):first.execute(manifest['review_hash'],owner_confirmed=True,confirm_free_tier=True)
                self.assertEqual(1,run.call_count)
            self.assertEqual([],self.requests)
