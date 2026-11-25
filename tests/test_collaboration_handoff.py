from datetime import datetime, timedelta, timezone
from copy import deepcopy
from itertools import count
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError
import json

from autonomous_company import CompanyError, digest, now
from autonomous_gemini35 import ENDPOINT, MODEL
from collaboration_handoff import GROQ_ENDPOINT, GROQ_MODEL, HandoffCompany, GroqHandoffCompany, publish_plan
from general_research_report import base_for
from research_workflow import research_store
from studio_server import Studio
from tests.test_script_quality import script_callbacks, script_from_beats
from tests.test_video_mission_one import FixtureResponse
from voice_quality import AUDIENCE
from web_research import evidence, research_report


class FixtureHandoffCompany(HandoffCompany):
    source = 'offline_http_fixture'


class CollaborationHandoffTests(TestCase):
    def test_review_choice_revision_and_production_handoff(self):
        self.exercise_handoff('gemini')

    def test_groq_signed_scope_and_chat_completion_handoff(self):
        with patch.object(GroqHandoffCompany,'source','offline_http_fixture'):
            self.exercise_handoff('groq')

    def test_groq_http_403_stops_and_preserves_attempt(self):
        self.exercise_handoff('groq',reject=True)

    def exercise_handoff(self,provider,*,reject=False):
        groq=provider=='groq'
        model,endpoint=(GROQ_MODEL,GROQ_ENDPOINT) if groq else (MODEL,ENDPOINT)
        root=Path(self.enterContext(TemporaryDirectory()))
        studio=Studio(root,[])
        studio.collaboration_test_options=dict(company_type=FixtureHandoffCompany,allow_fixture=True)
        pid=studio.workflow.create('가상 근거 자료에서 초보자용 영상 기획',audience=AUDIENCE)
        studio.workflow.stage_mission_one(pid)
        project=studio.project('workspace',pid)
        store=research_store(root,project,dict(base_for(studio.workflow,project),version=1))
        row=evidence('https://example.org/public/tutorial','공개 자료 예시','제안 화면을 검증해야 합니다.',
                     'public_page','fixture')
        result=research_report(dict(claims=[dict(statement='예시 제안',assessment='unverified',
            citations=[row['id']])],feasibility='제작 소스 권리 미확인'),[dict(sources=[row],tool='fixture',status='observed')])
        topic=dict(title='약속 안내 문자에 들어갈 조건',rationale='가상 자료',length='60초',
                   visuals='자체 화면',source_ids=[row['id']],rights='unverified')
        store.root.mkdir(mode=0o700)
        store.write('research-result.json',result)
        store.write('manager-review.json',dict(result_sha256=digest(result),at=now(),provenance='offline_fixture',
                    decision=dict(action='hold',note='자료 한계',topics=[topic])))
        def action(name,body):
            return studio.action('workspace',pid,name,body)
        research=studio.detail('workspace',pid)['research']['reports'][-1]['report']
        choice=dict(version=1,sha256=research['sha256'],candidate=0,direction='자체 화면으로 구성',
                    goal_changed=False,duration_seconds=60,confirm_limits=True)
        with self.assertRaisesRegex(CompanyError,'general_report_changed'):
            action('research-plan-handoff',{**choice,'sha256':'0'*64})
        prepared=action('research-plan-handoff',choice)
        self.assertEqual(prepared['research']['reports'][-1]['report']['manager']['action'],'hold')
        self.assertEqual(prepared['collaboration']['handoff']['evidence_ids'],[row['id']])
        with self.assertRaises(CompanyError):
            action('research-plan-handoff',choice)

        key='fixture-only-collaboration-key'
        self.enterContext(patch.dict('os.environ',GEMINI_API_KEY=key,GEMINI_PRODUCTION_PROJECT_API_KEY=key,
            GROQ_API_KEY=key,GEMINI35_MODEL=MODEL,GEMINI35_ENDPOINT=ENDPOINT,GEMINI35_AUTONOMOUS_FREE_ENABLED='1'))
        self.enterContext(patch('socket.socket.connect',side_effect=AssertionError('external network forbidden')))
        tick=count()
        self.enterContext(patch('autonomous_free.pacing_now',side_effect=lambda:
            (datetime(2026,1,1,tzinfo=timezone(timedelta(hours=9)))+timedelta(seconds=61*next(tick))).isoformat()))
        with self.assertRaisesRegex(CompanyError,'owner_policy_required'):
            action('collaboration-run',{})
        scope=studio.detail('workspace',pid)['collaboration']
        if groq:
            with self.assertRaisesRegex(CompanyError,'owner_policy_scope_changed'):
                action('collaboration-scope-approve',dict(confirmed=True,provider='groq',review_hash=scope['review_hash']))
            scope=scope['groq_offer']
            self.assertNotIn('local_render_measurements',scope['proposal']['units'][0]['data_types'])
        action('collaboration-scope-approve',dict(confirmed=True,provider=provider,review_hash=scope['review_hash']))
        if groq:
            with patch.dict('os.environ',GROQ_API_KEY='different-test-key'):
                with self.assertRaisesRegex(CompanyError,'owner_policy_key_changed'):
                    action('collaboration-run',{})

        if reject:
            rejected=HTTPError(endpoint,403,'Rejected',{},BytesIO(b'{"error":{"code":"other"}}'))
            with patch('collaboration_handoff.send_once',side_effect=rejected) as transport:
                with self.assertRaisesRegex(CompanyError,'provider_rejected'):
                    action('collaboration-run',{})
                with self.assertRaisesRegex(CompanyError,'collaboration_duplicate'):
                    action('collaboration-run',{})
                transport.assert_called_once()
            state=studio.detail('workspace',pid)
            self.assertEqual(state['collaboration']['status'],'stopped')
            self.assertEqual(state['flow']['plan_versions'],[])
            return

        def beat(start,end,narration,shot):
            return dict(start=start,end=end,narration=narration,caption='가상 예시',screen='모의 예시 화면',
                shot_type=shot,source_ref='미확보',source_status='pending',fact_status='illustrative')
        calls=[]
        def send(request,timeout):
            wire=json.loads(request.data)
            self.assertEqual(request.full_url,endpoint)
            self.assertNotIn(key,request.data.decode())
            if groq:
                self.assertEqual(wire['model'],model)
                self.assertTrue(wire['response_format']['json_schema']['strict'])
                self.assertEqual(request.get_header('Authorization'),'Bearer '+key)
                message=json.loads(wire['messages'][1]['content'])
                self.assertNotIn('reviewed_video',message['data']['quality']['answers'])
                self.assertNotIn('speech_overruns',message['data']['quality']['answers'])
            else:
                message=json.loads(wire['contents'][0]['parts'][0]['text'])
            phase,context=message['phase'],message['data']
            feedback=context['quality']['feedback_text']
            calls.append((phase,context.get('assignment',{}).get('role'),feedback))
            self.assertEqual(context['quality']['answers']['research_handoff']['evidence_ids'],[row['id']])
            draft=script_from_beats([beat(0,3,'무엇이 달라졌을까요?','card'),
                beat(3,20,'수정 화면을 확인하세요.' if '수정' in feedback else '첫 줄을 살펴보세요.','demo'),
                beat(20,40,'날짜와 장소를 표시해 주세요.','demo'),
                beat(40,60,'원본과 한번 대조해 보세요.','card')])
            draft['provenance']=dict(author='fixture response',model=model,mock=False)
            manager,employee=script_callbacks(draft,draft)
            value=json.loads((employee if phase=='execute' else manager)(phase,context))
            if phase=='finalize':
                value.update(action='deliver',content='가상 기획 및 대본',
                             checks=[{**item,'status':'met'} for item in value['checks']])
                value.pop('task_refs',None)
            if groq:
                return FixtureResponse(json.dumps(dict(model=model,choices=[dict(finish_reason='stop',
                    message=dict(role='assistant',content=json.dumps(dict(result=value),ensure_ascii=False)))]),
                    ensure_ascii=False).encode())
            return FixtureResponse(json.dumps(dict(candidates=[dict(finishReason='STOP',content=dict(role='model',
                parts=[dict(text=json.dumps(dict(result=value),ensure_ascii=False))]))],
                usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=30,totalTokenCount=50))).encode())

        def checked_publish(workflow,project,job,prior,**kwargs):
            for field in ('provider_id','model','endpoint','grant_id','cost_policy_hash','role_result_status'):
                mismatched=deepcopy(job)
                mismatched['real_ai']['attempts'][0][field]='mismatch'
                with self.assertRaisesRegex(CompanyError,'collaboration_internal_review_incomplete'):
                    publish_plan(workflow,project,mismatched,prior,**kwargs)
            return publish_plan(workflow,project,job,prior,**kwargs)

        with patch('collaboration_handoff.send_once',side_effect=send), patch(
                'collaboration_handoff.publish_plan',side_effect=checked_publish):
            first=action('collaboration-run',{})['flow']['plan_versions'][-1]
            self.assertEqual(first['provenance'],'offline_http_fixture')
            self.assertEqual(first['provider_identity'],dict(provider_id=provider,model=model,endpoint=endpoint))
            self.assertEqual(first['research_handoff']['report_sha256'],research['sha256'])
            review=dict(stage='plan',version=1,sha256=first['sha256'],action='request_revision',
                        feedback='수정 화면을 명확하게 보여 주세요.',changes_plan=False)
            action('decide',review)
            second=action('collaboration-run',{})['flow']['plan_versions'][-1]
            self.assertEqual(second['previous_plan_sha256'],first['sha256'])
            self.assertNotEqual(second['script']['transcript'],first['script']['transcript'])
        approved=action('decide',{**review,'version':2,'sha256':second['sha256'],'action':'approve','feedback':''})
        self.assertEqual(approved['stage'],'production')
        flow=studio.project('workspace',pid)['representative']
        spec=studio.workflow.mission_production_spec(flow,2,second['sha256'],'none')
        self.assertEqual(spec['scenes'][1]['narration'],'수정 화면을 확인하세요.')
        self.assertTrue(any(phase=='execute' and role=='writer' for phase,role,_ in calls))
        self.assertTrue(any(phase=='review' and role=='editor' for phase,role,_ in calls))
        self.assertEqual(flow['plan_versions'][0],first)
