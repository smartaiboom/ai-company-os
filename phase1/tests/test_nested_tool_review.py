"""Nested tool input errors are failed work; outer role JSON remains strict."""
from io import BytesIO
import json
from unittest.mock import patch
from autonomous_company import CompanyError,digest
from tests.test_autonomous_gemini35 import Gemini35Tests
from tests.test_internal_tool_review import RecoveryModels


class NestedModels(RecoveryModels):
    def __init__(self,content,decision='revise'):
        super().__init__('nested',decision);self.bad_content=content
    def employee_response(self,phase,ctx):
        value=json.loads(super().employee_response(phase,ctx))
        if not ctx['previous_results'] and not ctx['revision_feedback']:value['content']=self.bad_content
        return json.dumps(value,ensure_ascii=False)


BAD_JSON='{"tool":"caption_video_v1","scenes":['
BAD_SCHEMA='{"tool":"caption_video_v1","width":"bad","height":240,"audio":false,"scenes":[]}'


class NestedToolTests(Gemini35Tests):
    def test_nested_failures_manager_revision_media_handoff_final(self):
        for content,category in [(BAD_JSON,'tool_input_invalid_json'),(BAD_SCHEMA,'tool_input_invalid_schema'),
                                  ('{"scenes":[],"width":320}','tool_input_ambiguous')]:
            self.create(video=True);self.models=NestedModels(content);self.approve();self.run_company()
            self.assertEqual('delivered',self.p['status'],self.p.get('reason_code'))
            task=self.p['assignments'][0]
            self.assertEqual(content,task['versions'][0]['content'])
            self.assertEqual('failed',task['versions'][0]['tool_status'])
            self.assertEqual(category,task['versions'][0]['tool_failure']['category'])
            self.assertEqual(1,task['revisions']);self.assertEqual(8,len(self.requests))
            self.assertEqual(category,self.models.failed_reviews[0]['tool_failure']['category'])
            self.assertTrue(all(a['role_result_status']=='validated' for a in self.p['real_ai']['attempts']))
            self.assertIsNone(self.p['active_operation']);self.assertIn('final.md',self.p['artifacts'])
            self.assertTrue(any(n.endswith('.mp4') for n in self.p['artifacts']))
            self.assertTrue([r for r in self.requests if r['role']=='employee'][-1]['data']['previous_results'])
            self.assertEqual(0,self.p['user_business_approval_requests'])
            count=len(self.requests);self.run_company();self.assertEqual(count,len(self.requests))

    def test_normal_data_and_unsafe_tool_selector(self):
        self.create(video=True)
        for content in ('일반 산문입니다.','{"example":{"tool":"caption_video_v1"}}','{"answer":"안내"}','[1,2,3]'):
            self.assertIsNone(self.company._tool_spec(self.p,content))
        for content in ('{"tool":"shell"}','{"tool":[]}'):
            with self.assertRaises(CompanyError) as raised:self.company._tool_spec(self.p,content)
            self.assertEqual('tool_not_allowed',raised.exception.code)
            self.assertIsNone(self.company._nested_tool_error(self.p,raised.exception.code))
        body=self.store.prepare(self.p['id'],confirm_free_account=True)
        self.assertIn('nested_tool_review',body);body.pop('nested_tool_review')
        with self.assertRaises(CompanyError):self.store.approve(self.p['id'],body,review_hash=digest(body),owner_confirmed=True)

    def test_nested_stop_revision_cap_and_outer_json_failure(self):
        self.create(video=True);self.models=NestedModels(BAD_JSON,'stop');self.approve();self.run_company()
        self.assertEqual('manager_stopped',self.p['reason_code']);self.assertEqual(3,len(self.requests))
        self.create(video=True);self.p['limits']['max_revisions_per_task']=0;self.store.save(self.p)
        self.models=NestedModels(BAD_JSON);self.approve();self.run_company()
        self.assertEqual('revision_limit',self.p['reason_code']);self.assertEqual(3,len(self.requests))
        self.create(video=True);self.models=NestedModels(BAD_JSON);self.approve();original=self.fake
        def response(request,timeout):
            data=json.loads(json.loads(request.data)['contents'][0]['parts'][0]['text'])
            if data['phase']!='execute':return original(request,timeout)
            raw={'candidates':[{'finishReason':'STOP','content':{'role':'model','parts':[{'text':'{'}]}}],
                 'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':10,'totalTokenCount':110}}
            out=BytesIO(json.dumps(raw).encode());out.status=200;out.headers={};return out
        with patch('autonomous_live.urlopen',side_effect=response):self.run_company()
        self.assertEqual('invalid_model_json',self.p['reason_code'])
        self.assertTrue(self.p['active_operation']);self.assertFalse(self.p['assignments'][0]['versions'])
        self.assertNotIn('local_tool_failure',self.p['real_ai']['attempts'][-1])


for name in dir(Gemini35Tests):
    if name.startswith('test_') and name not in NestedToolTests.__dict__:setattr(NestedToolTests,name,None)
del Gemini35Tests
