from datetime import datetime, timedelta, timezone
from copy import deepcopy
from itertools import count
from io import BytesIO
from http.client import HTTPConnection
from threading import Thread
from uuid import uuid4
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError
import json

from autonomous_company import CompanyError, digest, now
from autonomous_gemini35 import ENDPOINT, MODEL
from collaboration_handoff import GROQ_ENDPOINT, GROQ_MODEL, HandoffCompany, GroqHandoffCompany, GroqHandoffStore, publish_plan, scope as owner_scope
from general_research_report import base_for
from research_workflow import research_store
from studio_server import Studio, make_server
from representative_workflow import RepresentativeVideoWorkflow
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
        for code in ('model_permission_blocked_org','model_permission_blocked_project'):
            with self.subTest(code=code):
                self.exercise_handoff('groq',reject=code)

    def test_signed_development_scope_accumulates_across_revisions(self):
        self.exercise_handoff('gemini',development=True)
        with patch.object(GroqHandoffCompany,'source','offline_http_fixture'):
            self.exercise_handoff('groq',development=True)

    def test_development_provider_failure_blocks_further_execution(self):
        for failure in (503, 429, 'timeout'):
            with self.subTest(failure=failure):
                self.exercise_handoff('gemini',reject=failure,development=True)

    def test_cutroom_feedback_reuse(self):
        self.exercise_handoff('gemini',reuse=True)

    def exercise_handoff(self,provider,*,reject=False,reuse=False,development=False):
        groq=provider=='groq'
        model,endpoint=(GROQ_MODEL,GROQ_ENDPOINT) if groq else (MODEL,ENDPOINT)
        root=Path(self.enterContext(TemporaryDirectory()))
        studio=Studio(root,[])
        studio.collaboration_test_options=dict(company_type=FixtureHandoffCompany,allow_fixture=True)
        root.mkdir(exist_ok=True)
        if reuse:
            studio.workflow=RepresentativeVideoWorkflow(studio.workflow.store,fixture_experiences=True)
            server=self.enterContext(make_server('127.0.0.1',0,studio))
            thread=Thread(target=server.serve_forever,daemon=True)
            thread.start()
            self.addCleanup(server.shutdown)

        def http(path, body=None, *, expected=200, headers=None):
            from socket import socket
            with patch.object(socket,'connect',connect_loopback):
                conn=HTTPConnection('127.0.0.1',server.server_port,timeout=120)
                try:
                    request_headers={'Content-Type':'application/json','X-Studio-Token':studio.token,**(headers or {})}
                    conn.request('GET' if body is None else 'POST',path,
                                 None if body is None else json.dumps(body),request_headers)
                    response=conn.getresponse()
                    payload=response.read()
                    self.assertEqual(response.status,expected,payload[:1000])
                    return json.loads(payload) if response.getheader('Content-Type').startswith('application/json') else payload
                finally:
                    conn.close()

        from socket import socket
        original_connect=socket.connect
        def connect_loopback(sock,address):
            self.assertEqual(address,('127.0.0.1',server.server_port))
            return original_connect(sock,address)

        def create(audience):
            if not reuse:
                return studio.workflow.create('가상 근거 자료에서 초보자용 영상 기획',audience=audience)
            return http('/api/project',dict(goal='가상 안내 영상',audience=audience,language='한국어',platform='YouTube Shorts',
                        duration=60,notes='',key=str(uuid4())),expected=201)['id']

        row=evidence('https://example.org/public/tutorial','공개 자료 예시','제안 화면을 검증해야 합니다.',
                     'public_page','fixture')
        result=research_report(dict(claims=[dict(statement='예시 제안',assessment='unverified',
            citations=[row['id']])],feasibility='제작 소스 권리 미확인'),[dict(sources=[row],tool='fixture',status='observed')])
        topic=dict(title='약속 안내 문자에 들어갈 조건',rationale='가상 자료',length='60초',
                   visuals='자체 화면',source_ids=[row['id']],rights='unverified')

        def prepare_research(pid):
            studio.workflow.stage_mission_one(pid)
            project=studio.project('workspace',pid)
            store=research_store(root,project,dict(base_for(studio.workflow,project),version=1))
            store.root.mkdir(mode=0o700)
            store.write('research-result.json',result)
            store.write('manager-review.json',dict(result_sha256=digest(result),at=now(),provenance='offline_fixture',
                        decision=dict(action='hold',note='자료 한계',topics=[topic])))
            return studio.detail('workspace',pid)['research']['reports'][-1]['report']

        pid=create(AUDIENCE)
        research=prepare_research(pid)
        def action(name,body):
            if reuse and name in ('decide','mission-preview','experience-save','experience-withdraw'):
                return http(f'/api/project/workspace/{pid}/{name}',body)
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
        approval=dict(confirmed=True,provider=provider,review_hash=scope['review_hash'])
        policy=owner_scope(root,studio.workflow.store.load(pid))
        if development:
            offer=studio.detail('workspace',pid)['collaboration']['development_offers'][provider]
            self.assertEqual(offer['proposal']['units'][0]['endpoint'],endpoint)
            self.assertEqual(offer['proposal']['mode'],'development_scope')
            self.assertNotIn('limits',offer['proposal'])
            approval['mode']='development_scope'
            with self.assertRaisesRegex(CompanyError,'owner_policy_scope_changed'):
                action('collaboration-scope-approve',approval)
            approval['review_hash']=offer['review_hash']
        action('collaboration-scope-approve',approval)
        if development:
            with patch('owner_operating_policy.now',return_value='2099-01-01T00:00:00+09:00'):
                with self.assertRaisesRegex(CompanyError,'owner_policy_expired'):
                    action('collaboration-run',{})
            self.assertEqual(policy.attempts(),{})
        if groq:
            with patch.dict('os.environ',GROQ_API_KEY='different-test-key'):
                with self.assertRaisesRegex(CompanyError,'owner_policy_key_changed'):
                    action('collaboration-run',{})

        if development and reject:
            code = {503:'provider_unavailable',429:'provider_rate_limit','timeout':'free_request_failed'}[reject]
            failure = TimeoutError() if reject=='timeout' else HTTPError(endpoint,reject,'Rejected',{},BytesIO())
            with patch('collaboration_handoff.send_once',side_effect=failure) as transport:
                with self.assertRaisesRegex(CompanyError,code):
                    action('collaboration-run',{})
                with self.assertRaisesRegex(CompanyError,'collaboration_duplicate'):
                    action('collaboration-run',{})
                transport.assert_called_once()
            failed,=policy.attempts().values()
            self.assertEqual(failed['result']['status'],'failed_or_uncertain')
            return

        if reject:
            rejected=HTTPError(endpoint,403,'Rejected',{'Via':'synthetic-header-value'},
                               BytesIO(json.dumps({'error':{'code':reject,'message':'synthetic-body-value'}}).encode()))
            with patch('collaboration_handoff.send_once',side_effect=rejected) as transport:
                with self.assertRaisesRegex(CompanyError,'provider_rejected'):
                    action('collaboration-run',{})
                with self.assertRaisesRegex(CompanyError,'collaboration_duplicate'):
                    action('collaboration-run',{})
                transport.assert_called_once()
            state=studio.detail('workspace',pid)
            self.assertEqual(state['collaboration']['status'],'stopped')
            self.assertEqual(state['flow']['plan_versions'],[])
            store=GroqHandoffStore(root/'research_plan_handoff'/pid)
            attempt,=store.load(state['collaboration']['current']['id'])['real_ai']['attempts']
            self.assertEqual(attempt['provider_error_diagnostics']['provider_code'],reject)
            self.assertTrue(attempt['response_source_hints']['header_presence']['via'])
            self.assertEqual(attempt['response_source_hints']['origin_classification'],'unverified')
            self.assertNotIn('synthetic-',json.dumps(attempt))
            return

        def beat(start,end,narration,shot,caption):
            return dict(start=start,end=end,narration=narration,caption=caption,screen='모의 예시 화면',
                shot_type=shot,source_ref='미확보',source_status='pending',fact_status='illustrative')
        calls=[]
        expected_experiences=[]
        def send(request,timeout):
            wire=json.loads(request.data)
            if development:
                reservation=policy.attempts()[f'planning:{len(calls)+1}']
                self.assertIsNone(reservation['result'])
                self.assertEqual(reservation['reservation']['payload_sha256'],digest(wire))
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
            self.assertEqual(context['quality']['experiences'],expected_experiences)
            revised='수정' in feedback or bool(expected_experiences)
            caption='날짜·장소' if revised else '가상 안내 자막입니다'
            draft=script_from_beats([beat(0,3,'무엇이 달라졌을까요?','card',caption),
                beat(3,20,'수정 화면을 확인하세요.' if revised else '첫 줄을 살펴보세요.','demo',caption),
                beat(20,40,'날짜와 장소를 표시해 주세요.','demo',caption),
                beat(40,60,'원본과 한번 대조해 보세요.','card',caption)])
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
                        feedback='수정 화면을 명확하게 보여 주고 자막을 짧게 줄여 주세요.',changes_plan=False)
            if reuse:
                action('decide',{**review,'action':'approve','feedback':''})
                v1=self.render_preview(action,first)
                action('decide',{**review,'stage':'video','sha256':v1['sha256'],'changes_plan':True})
            else:
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

        if development:
            self.assertEqual(len(policy.attempts()),len(calls))
            self.assertGreater(len(calls),10)
            ledger = policy.attempts()
            self.assertTrue(all(row['result']['status']=='completed' for row in ledger.values()))
            from video_mission_one import _binding
            first = ledger['planning:1']['reservation']
            with self.assertRaisesRegex(CompanyError,'owner_policy_replay'):
                policy.reserve(_binding(pid,key),{**first['unit'],'id':f'planning:{len(calls)+1}'},first['payload_sha256'])
            action('collaboration-scope-revoke',{})
            with self.assertRaisesRegex(CompanyError,'owner_policy_revoked'):
                policy.active(_binding(pid,key))
            self.assertEqual(policy.attempts(),ledger)
        else:
            self.assertEqual(policy.attempts(),{})
        if not reuse:
            return
        v2=self.render_preview(action,second)
        for video in (v1,v2):
            self.assertTrue(video['qa']['full_decode'])
            self.assertEqual(video['qa']['perceptual_quality'],'unassessed')
            self.assertEqual(http(video['url'],expected=206,headers={'Range':'bytes=4-7'}),b'ftyp')
        self.assertNotEqual(v1['artifact_sha256'],v2['artifact_sha256'])
        approval=dict(stage='video',version=2,sha256=v2['sha256'],action='approve',feedback='',changes_plan=False)
        route=f'/api/project/workspace/{pid}'
        self.assertEqual(http(route+'/decide',approval,expected=409)['code'],'technical_preview_not_approvable')
        save=dict(stage='video',version=2,sha256=v2['sha256'],category='captions',
                  preference='자막은 핵심 단어 위주로 짧게 적습니다.',confirmed=True,replaces=None)
        self.assertEqual(http(route+'/experience-save',{**save,'sha256':v1['sha256']},expected=409)['code'],
                         'stale_representative_report')
        reviewed=action('experience-save',save)
        record,=reviewed['flow']['experiences']
        self.assertTrue(record['fixture'])
        self.assertLess(record['measurements']['max_caption_chars_after'],record['measurements']['max_caption_chars_before'])
        self.assertEqual(record['comparison']['before']['artifact_sha256'],v1['artifact_sha256'])
        self.assertEqual(record['comparison']['after']['artifact_sha256'],v2['artifact_sha256'])
        self.assertEqual(http(route+'/experience-save',save,expected=409)['code'],
                         'experience_duplicate_or_replacement_required')
        origin=pid
        pid=create('다른 대상')
        different=http(f'/api/project/workspace/{pid}')['flow']['experience_selection']
        self.assertEqual(different['selected'],[])
        self.assertEqual(different['excluded'][0]['reason'],'work_scope')
        normal=RepresentativeVideoWorkflow(studio.workflow.store)
        normal_pid=normal.create('운영 경로의 가상 과제',audience=AUDIENCE, constraints=dict(
            language='한국어',platform='YouTube Shorts',duration_seconds=60))
        self.assertEqual(normal.selected_experiences(normal.store.load(normal_pid))['excluded'][0]['reason'],'provenance')

        pid=create(AUDIENCE)
        next_research=prepare_research(pid)
        state=action('research-plan-handoff',{**choice,'sha256':next_research['sha256']})['collaboration']
        expected_experiences=state['experience_inputs']
        self.assertEqual([row['record_hash'] for row in expected_experiences],[record['record_hash']])
        self.assertEqual(state['proposal']['experiences_sha256'],digest(expected_experiences))
        action('collaboration-scope-approve',dict(confirmed=True,review_hash=state['review_hash']))
        with patch('collaboration_handoff.send_once',side_effect=send):
            next_plan=action('collaboration-run',{})['flow']['plan_versions'][-1]
        self.assertEqual(next_plan['experience_input_hashes'],[record['record_hash']])
        self.assertEqual(next_plan['script']['narrative_beats'][0]['caption'],'날짜·장소')
        self.assertEqual(next_plan['provenance'],'offline_http_fixture')
        from representative_experience import select
        conflict={**record,'id':'experience-conflict','positive_preference':'자막은 완전한 문장으로 씁니다.'}
        with patch('representative_experience.candidates',return_value=[record,conflict]):
            eligible=select(studio.workflow.store,studio.workflow.store.load(pid)['representative'],fixture=True)
        self.assertEqual(eligible['selected'],[])
        self.assertEqual([row['reason'] for row in eligible['excluded']],['conflict','conflict'])

        # A pending signed scope cannot silently change after the source preference is replaced.
        pending=create(AUDIENCE)
        pid=pending
        next_research=prepare_research(pid)
        state=action('research-plan-handoff',{**choice,'sha256':next_research['sha256']})['collaboration']
        action('collaboration-scope-approve',dict(confirmed=True,review_hash=state['review_hash']))
        replaced=http(f'/api/project/workspace/{origin}/experience-save',{**save,'replaces':record['id'],
                      'use_measured_limit':True})['flow']['experiences'][-1]
        self.assertEqual(replaced['measured_lesson'],'max_caption_chars')
        with patch('collaboration_handoff.send_once') as transport:
            with self.assertRaisesRegex(CompanyError,'owner_policy_scope_changed'):
                action('collaboration-run',{})
            transport.assert_not_called()
        http(f'/api/project/workspace/{origin}/experience-withdraw',dict(id=replaced['id'],
             record_hash=replaced['record_hash'],reason='검증용 선호 철회'))
        excluded=http(f'/api/project/workspace/{pending}')['flow']['experience_selection']
        self.assertEqual(excluded['selected'],[])
        self.assertEqual(excluded['excluded'][0]['reason'],'inactive')

    @staticmethod
    def render_preview(action,plan):
        return action('mission-preview',dict(version=plan['version'],sha256=plan['sha256'],
                      audio_mode='none'))['flow']['video_versions'][-1]
