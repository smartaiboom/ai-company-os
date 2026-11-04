"""Fake HTTPS company workflow with real local MP4 output; never actual AI."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from autonomous_company import CompanyError, digest
from autonomous_free import FreeStore
from local_artifacts import VIDEO_TOOL, validate_video, render_video
from tests.test_autonomous_free import FreeTests
from tests.support.autonomous_company_fixtures import FictionalModels

SPEC={'tool':VIDEO_TOOL,'width':1280,'height':720,'audio':True,'scenes':[
    {'text':'좋은 질문은 어떻게 할까요?', 'seconds':6},
    {'text':'목표와 상황을 함께 설명하세요.', 'seconds':6},
    {'text':'원하는 답변 형식을 알려주세요.', 'seconds':6},
    {'text':'답변을 확인하고 질문을 보완하세요.', 'seconds':6}]}

class VideoModels(FictionalModels):
    def __init__(self):super().__init__(revise=True);self.receipts=[]
    def employee_response(self,phase,ctx):
        if ctx['previous_results']:
            return json.dumps({'content':json.dumps(SPEC,ensure_ascii=False),'evidence':'FAKE video timeline from preceding script',
                               'uncertainty':'Synthetic fixture, not actual AI.'},ensure_ascii=False)
        return super().employee_response(phase,ctx)
    def manager_response(self,phase,ctx):
        if phase=='review' and ctx['previous_results']:
            assert 'LOCAL_TOOL_RECEIPT' in ctx['result']['evidence']
            self.receipts.append(ctx['result']['evidence'])
        return super().manager_response(phase,ctx)

# Reuse socket blocking, synthetic grant, fake HTTPS, durable ledger and virtual clock.
class VideoWorkflowTests(FreeTests):
    def setUp(self):
        super().setUp()
        self.p=self.store.create('FAKE ONLY 한국어 질문 설명 영상 20~30초 MP4',local_tools=[VIDEO_TOOL])
        self.fake.project_id=self.p['id'];self.models=VideoModels();self.fake.models=self.models
    def test_video_workflow(self):
        body=self.approve();self.assertIn('local_tools',body)
        self.run_once()
        self.assertEqual('delivered',self.p['status'],self.p.get('reason_code'))
        self.assertEqual(8,len(self.fake.requests));self.assertEqual(1,len(self.models.receipts))
        self.assertEqual(0,self.p['user_business_approval_requests'])
        receipt=next(e['receipt'] for e in self.p['events'] if e['event']=='local_tool_completed')
        self.assertAlmostEqual(24,receipt['duration_seconds'],delta=0.2);self.assertTrue(receipt['decoded']);self.assertTrue(receipt['audio'])
        self.store.result(self.p['id']);self.run_once();self.assertEqual(8,len(self.fake.requests))
    def test_tool_failure_blocks_delivery(self):
        self.approve()
        with patch('local_artifacts.run_command',side_effect=CompanyError('local_tool_failed')):self.run_once()
        self.assertEqual('stopped',self.p['status']);self.assertEqual('local_tool_failed',self.p['reason_code'])
        self.assertNotIn('final.md',self.p['artifacts'])
    def test_missing_video_blocks_model_delivery_claim(self):
        self.fake.models=FictionalModels();self.approve();self.run_once()
        self.assertEqual('required_artifact_missing',self.p['reason_code'])
    def test_tool_permission_bound_to_contract(self):
        body=self.store.prepare(self.p['id']);body['local_tools']={}
        with self.assertRaises(CompanyError):self.store.approve(self.p['id'],body,review_hash=digest(body),owner_confirmed=True)

# Do not inherit the base regression suite with a different domain fixture.
for _name in list(FreeTests.__dict__):
    if _name.startswith('test_') and _name not in VideoWorkflowTests.__dict__:
        setattr(VideoWorkflowTests,_name,None)
del FreeTests

class InputTests(unittest.TestCase):
    def test_untrusted_paths_commands_overflow_and_duration(self):
        for change in [{'tool':'shell'},{'width':True},{'audio':'yes'},
                       {'scenes':[{'text':'x','seconds':float('nan')}]},
                       {'scenes':[{'text':'x'*100,'seconds':2}]}, {'path':'/tmp/out.mp4'}]:
            with self.subTest(change=change),self.assertRaises(CompanyError):validate_video({**deepcopy(SPEC),**change})
    def test_silent_render_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            spec={**deepcopy(SPEC),'width':320,'height':240,'audio':False,'scenes':[{'text':'한국어 자막 %{}','seconds':0.5}]}
            result=render_video(spec,root);self.assertFalse(result['audio']);self.assertTrue(result['decoded'])
            with self.assertRaises(CompanyError):render_video(spec,root)
