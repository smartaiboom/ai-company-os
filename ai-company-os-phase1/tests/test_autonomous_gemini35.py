"""3.5 isolated binding with inherited offline manager-directed recovery scenarios."""
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
from unittest.mock import patch
from autonomous_company import CompanyError,digest
from autonomous_gemini import GeminiStore,GeminiConfig
from autonomous_gemini35 import Gemini35Store,Gemini35Company,Gemini35Config,Gemini35Adapter,MODEL,ENDPOINT
from autonomous_live import LiveManagerProvider,LiveEmployeeProvider
from gemini_provider import GeminiFreeAdapter,ENDPOINT as OLD_ENDPOINT
from tests.test_autonomous_gemini import KEY
from tests.test_internal_tool_review import InternalToolReviewTests
import gemini35_first_project as first35


class Gemini35Tests(InternalToolReviewTests):
    def create(self,video=False,max_calls=None,internal_tool_review=True):
        os.environ.update(GEMINI35_MODEL=MODEL,GEMINI35_ENDPOINT=ENDPOINT,GEMINI35_AUTONOMOUS_FREE_ENABLED='1')
        self.store=Gemini35Store(Path(self.tmp.name)/'gemini35')
        self.p=self.store.create('FAKE ONLY 합성 목표',local_tools=['caption_video_v1'] if video else None,
                                 max_calls=max_calls,internal_tool_review=internal_tool_review)
        self.company=Gemini35Company(self.store,LiveManagerProvider('gemini35-free-manager'),
                                     LiveEmployeeProvider('gemini35-free-employee'),Gemini35Config(KEY))
        self.requests=[]

    def fake(self,request,timeout):
        self.assertEqual(ENDPOINT,request.full_url);self.assertEqual('POST',request.get_method())
        self.assertEqual(KEY,request.get_header('X-goog-api-key'));self.assertNotIn(KEY,request.data.decode())
        p=self.store.load(self.p['id']);a=p['real_ai']['attempts'][-1]
        self.assertEqual(MODEL,a['model']);self.assertEqual(ENDPOINT,a['endpoint'])
        self.assertEqual('reserved',a['status']);self.assertEqual(a['id'],p['active_operation'])
        self.assertTrue(a['transport_started_at'])
        payload=json.loads(request.data);data=json.loads(payload['contents'][0]['parts'][0]['text'])
        Gemini35Adapter().validate_payload(payload,data['phase']);self.requests.append(deepcopy(data))
        fn=self.models.manager_response if data['role']=='manager' else self.models.employee_response
        value=json.loads(fn(data['phase'],data['data']))
        if data['phase']=='finalize':value.pop('task_refs',None)
        envelope={'candidates':[{'finishReason':'STOP','content':{'role':'model','parts':[
                   {'text':json.dumps({'result':value},ensure_ascii=False)}]}}],
                  'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':150,'totalTokenCount':250}}
        response=BytesIO(json.dumps(envelope).encode());response.status=200;response.headers={}
        return response

    def test_model_contract_old_namespace_and_no_cross_approval(self):
        old=GeminiStore(Path(self.tmp.name)/'old31');p=old.create('FAKE legacy goal')
        before=old.path(p['id']).read_bytes()
        body=self.store.prepare(self.p['id'],confirm_free_account=True)
        self.assertEqual(MODEL,body['model']);self.assertEqual(ENDPOINT,body['endpoint'])
        oldbody=old.prepare(p['id'],confirm_free_account=True)
        self.assertEqual('gemini-3.1-flash-lite',oldbody['model'])
        self.assertEqual(OLD_ENDPOINT,GeminiFreeAdapter().build_request(b'{}',KEY).full_url)
        self.assertEqual(ENDPOINT,Gemini35Adapter().build_request(b'{}',KEY).full_url)
        for changed in (oldbody,{**body,'model':'gemini-3.1-flash-lite'}, {**body,'endpoint':OLD_ENDPOINT},
                        {**body,'cost_policy':oldbody['cost_policy']}):
            with self.assertRaises(CompanyError):self.store.approve(self.p['id'],changed,review_hash=digest(changed),owner_confirmed=True)
        with self.assertRaises(CompanyError):Gemini35Store(old.root).load(p['id'])
        with self.assertRaises(CompanyError):GeminiStore(self.store.root).load(self.p['id'])
        self.assertEqual(before,old.path(p['id']).read_bytes())
        self.approve()
        for key,value in [('GEMINI35_MODEL','gemini-3.1-flash-lite'),('GEMINI35_ENDPOINT',OLD_ENDPOINT),
                          ('GEMINI35_AUTONOMOUS_FREE_ENABLED','0')]:
            with patch.dict(os.environ,{key:value}),self.assertRaises(CompanyError):self.run_company()
        self.assertEqual([],self.requests)

    def test_isolated_launcher_prepare_no_grant_and_wrong_hash_blocked(self):
        root=Path(self.tmp.name)/'launcher35'
        with patch.object(first35,'ROOT',root):
            manifest=first35.prepare();store=Gemini35Store(root);p=store.load(manifest['project_id'])
            self.assertEqual('ready',p['status']);self.assertFalse(p['real_ai']['enabled'])
            self.assertEqual([],p['real_ai']['attempts']);self.assertFalse(store._grant_path(p['id']).exists())
            with self.assertRaises(CompanyError):first35.execute('wrong',owner_confirmed=True,confirm_free_tier=True)
            self.assertFalse((root/'owner-launch-consumed.json').exists())
            with self.assertRaises(CompanyError):first35.prepare()


del InternalToolReviewTests
