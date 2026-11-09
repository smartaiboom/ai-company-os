"""Fictional manager choices only: production decisions remain model outputs."""
from copy import deepcopy
import json
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO
from autonomous_company import CompanyError,digest
from local_artifacts import execute,LocalToolError
from tests.test_autonomous_gemini import GeminiTests
from tests.support.autonomous_company_fixtures import FictionalModels


class RecoveryModels(FictionalModels):
    def __init__(self,failure='caption_overflow',decision='revise'):
        super().__init__();self.failure=failure;self.decision=decision;self.failed_reviews=[]
    def employee_response(self,phase,ctx):
        if ctx['previous_results']:return super().employee_response(phase,ctx)
        revised=bool(ctx['revision_feedback'])
        text='수정한 합성 안내입니다.' if revised else '초기 합성 안내입니다.'
        if self.failure=='caption_overflow' and not revised:text='가'*29
        spec={'tool':'caption_video_v1','width':320,'height':240,'audio':False,
              'scenes':[{'text':text,'seconds':1}]}
        if self.failure=='narration_exceeds_scene' and not revised:
            spec['audio']=True;spec['scenes']=[{'text':'합성 안내를 설명합니다.','seconds':0.5}]
        return json.dumps({'content':json.dumps(spec,ensure_ascii=False),
                           'evidence':'FAKE model claim; physical tool result comes from application.',
                           'uncertainty':'Not actual Gemini.'},ensure_ascii=False)
    def manager_response(self,phase,ctx):
        value=json.loads(super().manager_response(phase,ctx))
        if phase=='review' and ctx['result'].get('tool_status')=='failed':
            self.failed_reviews.append(deepcopy(ctx['result']))
            value.update(action=self.decision,feedback='기술 실패 원인을 반영해 새 도구 입력을 작성하고 실제 렌더 결과를 확인하세요.'
                         if self.decision=='revise' else '',
                         operation='external_permission' if self.decision=='needs_operational_permission' else None)
            for check in value['checks']:check['status']='met' if self.decision=='accept' else 'unmet'
        return json.dumps(value,ensure_ascii=False)


class InternalToolReviewTests(GeminiTests):
    def setup_recovery(self,failure='caption_overflow',decision='revise'):
        self.create(video=True);self.models=RecoveryModels(failure,decision);self.approve()

    def test_failure_manager_revision_real_mp4_handoff_and_final(self):
        for failure in ('caption_overflow','local_tool_failed','narration_exceeds_scene'):
            self.setup_recovery(failure)
            count=0
            def tool(*args):
                nonlocal count
                count+=1
                if count==1 and failure=='local_tool_failed':raise LocalToolError('ffmpeg_segment','exit_nonzero',1)
                return execute(*args)
            with patch('local_artifacts.execute',side_effect=tool):self.run_company()
            self.assertEqual('delivered',self.p['status'],self.p.get('reason_code'))
            self.assertEqual(1,len(self.models.failed_reviews));self.assertEqual(8,len(self.requests))
            first=self.p['assignments'][0]
            self.assertEqual('failed',first['versions'][0]['tool_status'])
            self.assertEqual(failure if failure!='local_tool_failed' else 'exit_nonzero',
                             first['versions'][0]['tool_failure']['category'])
            self.assertNotIn('tool_status',first['versions'][-1]);self.assertEqual(1,first['revisions'])
            self.assertTrue([r for r in self.requests if r['role']=='employee'][-1]['data']['previous_results'])
            self.assertTrue(any(n.endswith('.mp4') for n in self.p['artifacts']))
            self.assertIn('final.md',self.p['artifacts']);self.assertEqual(0,self.p['user_business_approval_requests'])
            self.assertTrue(all(a['status']=='completed' and a['role_result_status']=='validated' for a in self.p['real_ai']['attempts']))
            self.assertIsNone(self.p['active_operation'])
            calls=len(self.requests);self.run_company();self.assertEqual(calls,len(self.requests))

    def test_manager_stop_permission_and_failed_accept(self):
        for decision,reason in [('stop','manager_stopped'),('needs_operational_permission','external_permission'),
                                ('accept','failed_tool_cannot_be_accepted')]:
            self.setup_recovery(decision=decision);self.run_company()
            self.assertEqual(reason,self.p['reason_code']);self.assertEqual(3,len(self.requests))
            self.assertFalse(self.p['artifacts']);self.assertEqual(1,len(self.p['assignments'][0]['versions']))
            self.assertNotEqual('accepted_by_ai_manager',self.p['assignments'][0]['state'])

    def test_revision_budget_hard_safety_and_manager_api_failure(self):
        self.create(video=True)
        self.p['limits']['max_revisions_per_task']=0;self.store.save(self.p)
        self.models=RecoveryModels();self.approve();self.run_company()
        self.assertEqual('revision_limit',self.p['reason_code']);self.assertEqual(3,len(self.requests))
        self.setup_recovery()
        with patch('local_artifacts.execute',side_effect=CompanyError('invalid_tool_directory')):self.run_company()
        self.assertEqual('invalid_tool_directory',self.p['reason_code']);self.assertEqual(2,len(self.requests))
        self.assertFalse(self.p['assignments'][0]['versions'])
        self.setup_recovery();original=self.fake
        def failure(request,timeout):
            data=json.loads(json.loads(request.data)['contents'][0]['parts'][0]['text'])
            if data['phase']=='review':raise HTTPError('https://fake.invalid',429,'private',{},BytesIO())
            return original(request,timeout)
        with patch('autonomous_live.urlopen',side_effect=failure):self.run_company()
        attempts=self.p['real_ai']['attempts']
        self.assertEqual(['completed','completed','failed'],[a['status'] for a in attempts])
        self.assertEqual('validated',attempts[1]['role_result_status'])
        self.assertEqual(attempts[-1]['id'],self.p['active_operation'])
        self.assertEqual('failed',self.p['assignments'][0]['versions'][0]['tool_status'])
        calls=len(self.requests)
        with self.assertRaises(CompanyError):self.run_company(resume=True)
        self.assertEqual(calls,len(self.requests))

    def test_total_revision_budget_and_repeated_failure_stop(self):
        self.create(video=True)
        self.p['limits']['max_total_revisions']=0;self.store.save(self.p)
        self.models=RecoveryModels();self.approve();self.run_company()
        self.assertEqual('revision_limit',self.p['reason_code']);self.assertEqual(3,len(self.requests))
        self.setup_recovery('local_tool_failed')
        with patch('local_artifacts.execute',side_effect=LocalToolError('ffmpeg_segment','timeout')) as tool:
            self.run_company()
            self.assertIn(self.p['reason_code'],('quality_stagnation','revision_limit'))
            self.assertEqual(2,tool.call_count);self.assertEqual(5,len(self.requests))
            self.assertFalse(self.p['artifacts'])

    def test_signed_policy_no_silent_upgrade_and_crash_no_replay(self):
        body=self.store.prepare(self.p['id'],confirm_free_account=True)
        self.assertIn('tool_failure_review',body)
        body.pop('tool_failure_review')
        with self.assertRaises(CompanyError):self.store.approve(self.p['id'],body,review_hash=digest(body),owner_confirmed=True)
        self.setup_recovery();original=self.company._commit
        def crash(p,event,**kw):
            if event=='ai_employee_result':raise KeyboardInterrupt()
            return original(p,event,**kw)
        with patch.object(self.company,'_commit',side_effect=crash),self.assertRaises(KeyboardInterrupt):self.run_company()
        self.p=self.store.load(self.p['id'])
        self.assertEqual('json_parsed',self.p['real_ai']['attempts'][-1]['role_result_status'])
        with self.assertRaises(CompanyError):self.run_company(resume=True)
        self.assertEqual(2,len(self.requests))

    def test_clean_failure_checkpoint_resumes_review_without_employee_replay(self):
        self.setup_recovery();original=self.company._commit
        def crash(p,event,**kw):
            original(p,event,**kw)
            if event=='ai_employee_result':raise KeyboardInterrupt()
        with patch.object(self.company,'_commit',side_effect=crash),self.assertRaises(KeyboardInterrupt):self.run_company()
        self.p=self.store.load(self.p['id'])
        self.assertEqual('awaiting_ai_review',self.p['assignments'][0]['state'])
        self.assertIsNone(self.p['active_operation'])
        self.assertEqual(2,len(self.requests))
        self.run_company(resume=True)
        self.assertEqual('delivered',self.p['status'],self.p.get('reason_code'))
        self.assertEqual(8,len(self.requests))
        self.assertEqual('review',self.requests[2]['phase'])


for name in list(GeminiTests.__dict__):
    if name.startswith('test_') and name not in InternalToolReviewTests.__dict__:setattr(InternalToolReviewTests,name,None)
del GeminiTests
