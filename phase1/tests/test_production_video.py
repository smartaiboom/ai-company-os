"""Offline production profile and real vector MP4; no cloud voices or media."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest
from autonomous_company import CompanyError,digest
from autonomous_gemini35 import Gemini35Config,Gemini35Store
from autonomous_live import LiveManagerProvider,LiveEmployeeProvider
from local_artifacts import LocalToolError,TOOLS as V1
from production_video import validate,scene_svg,render,TOOL
from video_quality_pilot import sample
from video_production_company import VideoProductionStore,VideoProductionCompany
from tests.support.autonomous_company_fixtures import FictionalModels
from tests.test_autonomous_gemini35 import Gemini35Tests


class ProductionModels(FictionalModels):
    def __init__(self):super().__init__(revise=True)
    def employee_response(self,phase,ctx):
        if ctx['previous_results']:return super().employee_response(phase,ctx)
        spec=sample();spec['width']=640;spec['height']=360;spec['scenes']=spec['scenes'][:1]
        spec['scenes'][0]['seconds']=1
        spec['scenes'][0]['title']='수정본' if ctx['revision_feedback'] else '초안'
        return json.dumps({'content':json.dumps(spec,ensure_ascii=False),'evidence':'FAKE production submission',
                           'uncertainty':'Visual/audio aesthetic review not performed'},ensure_ascii=False)


class ProductionWorkflowTests(Gemini35Tests):
    def create(self,video=False,max_calls=None,internal_tool_review=True):
        super().create(video,max_calls,internal_tool_review)
        self.store=VideoProductionStore(Path(self.tmp.name)/'production')
        self.p=self.store.create('FAKE ONLY 영상 제작 목표',max_calls=max_calls)
        self.company=VideoProductionCompany(self.store,LiveManagerProvider('video-executive'),
                          LiveEmployeeProvider('video-specialist'),Gemini35Config(self.company.config.api_key))

    def test_profile_failure_revision_media_delivery_and_isolation(self):
        self.models=ProductionModels();body=self.approve()
        self.assertIn('production_profile',body)
        self.assertEqual([TOOL],list(body['local_tools']))
        self.assertEqual(['caption_video_v1'],list(V1))
        calls=0
        def execute(spec,folder):
            nonlocal calls
            calls+=1
            if calls==1:raise LocalToolError('ffmpeg_segment','exit_nonzero',1)
            return render(spec,folder)
        with patch('video_production_company.render',side_effect=execute):self.run_company()
        self.assertEqual('delivered',self.p['status'],self.p.get('reason_code'))
        self.assertEqual(0,self.p['user_business_approval_requests']);self.assertEqual(8,len(self.requests))
        receipt=next(e['receipt'] for e in self.p['events'] if e['event']=='local_tool_completed')
        self.assertEqual(TOOL,receipt['tool']);self.assertFalse(receipt['audio'])
        self.assertFalse(receipt['model_visual_review_performed'])
        self.assertEqual('CC0-1.0',receipt['source_licenses'][0]['license'])
        self.assertTrue(receipt['review_material']);self.assertTrue(receipt['decoded'])
        with self.assertRaises(CompanyError):Gemini35Store(self.store.root).load(self.p['id'])


for name in dir(Gemini35Tests):
    if name.startswith('test_') and name not in ProductionWorkflowTests.__dict__:setattr(ProductionWorkflowTests,name,None)
del Gemini35Tests


class ProductionInputTests(unittest.TestCase):
    def test_schema_injections_and_external_voice_refused(self):
        base=sample()
        for change in ({'source':'https://bad.invalid/a.svg'}, {'audio_mode':'azure'},
                       {'width':True},{'width':641},{'palette':{'background':'red;movie=https://bad.invalid'}},
                       {'scenes':[]},{'scenes':[{**base['scenes'][0],'seconds':float('nan')}]},
                       {'scenes':[{**base['scenes'][0],'graphic':{'kind':'https://bad.invalid','labels':['x']}}]}):
            with self.subTest(fields=list(change)),self.assertRaises(CompanyError):validate({**deepcopy(base),**change})
        safe=sample();safe['scenes'][0]['title']='<script>x</script>'
        svg=scene_svg(safe,safe['scenes'][0],0)
        self.assertNotIn('<script>',svg);self.assertIn('&lt;script&gt;',svg)

    def test_profile_contract_and_output_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            store=VideoProductionStore(Path(d)/'profile');p=store.create('FAKE goal')
            body=store.prepare(p['id'],confirm_free_account=True);body.pop('production_profile')
            with self.assertRaises(CompanyError):store.approve(p['id'],body,review_hash=digest(body),owner_confirmed=True)
            output=Path(d)/'output';output.mkdir();(output/'receipt.json').symlink_to(Path(d)/'missing')
            with self.assertRaises(CompanyError):render(sample(),output)
            self.assertFalse((Path(d)/'missing').exists())
