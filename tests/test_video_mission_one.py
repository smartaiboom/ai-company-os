"""Mission integration against the existing native wire, with no real network."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
from itertools import count
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from autonomous_company import CompanyError, digest
from autonomous_gemini35 import ENDPOINT, MODEL, Gemini35Config
from autonomous_live import LiveEmployeeProvider, LiveManagerProvider
from studio_server import Studio
from video_mission_one import GAME_GOAL, GAME_RESEARCH_BLOCKER, MissionOneCompany, MissionOneStore
from script_quality import inspect_script
from tests.test_script_quality import script_callbacks, script_from_beats
from voice_quality import AUDIENCE


class FixtureResponse(BytesIO):
    status = 200
    headers = {}


class OfflineMissionCompany(MissionOneCompany):
    source = 'offline_http_fixture'


class MissionOneTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.studio = Studio(root)
        self.project = self.studio.create(dict(goal='가상 업무 예제로 한국어 초보자 쇼츠를 만들어 줘',
            audience=AUDIENCE, language='한국어', platform='YouTube', duration=60, notes='실데이터 없음',
            key='00000000-0000-4000-8000-000000000041'))['id']
        self.job = self.studio.workflow.stage_mission_one(self.project)
        self.store = MissionOneStore(root/'mission_one_provider')
        self.key = 'fixture-only-mission-api-key'
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden')))
        self.http = self.enterContext(patch('video_mission_one.send_once'))
        self.env = self.enterContext(patch.dict('os.environ', GEMINI_API_KEY=self.key, GEMINI35_MODEL=MODEL,
            GEMINI35_ENDPOINT=ENDPOINT, GEMINI35_AUTONOMOUS_FREE_ENABLED='1'))
        ticks = count()
        self.enterContext(patch('autonomous_free.pacing_now', side_effect=lambda:
            (datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=9))) + timedelta(seconds=3*next(ticks))).isoformat()))
        self.company = OfflineMissionCompany(self.store, LiveManagerProvider('fixture-manager'),
            LiveEmployeeProvider('fixture-staff'), Gemini35Config(self.key))

    def approve(self):
        body = self.store.prepare_mission(self.job, key=self.key, account_project='fixture project',
            remaining_requests=10, quota_note='fixture RPM/TPM')
        self.assertNotIn(self.key, json.dumps(body))
        self.store.approve(self.job, body, review_hash=digest(body), owner_confirmed=True)

    def run_job(self, **kwargs):
        return self.company.run(self.job, expected_state_hash=self.store.load(self.job)['storage_hash'], **kwargs)

    def fixture(self):
        def beat(start, end, narration, shot):
            return dict(start=start,end=end,narration=narration,caption='가상 예시',screen='가상 예시 화면',
                        shot_type=shot,source_ref='소스 미확보',source_status='pending',fact_status='illustrative')
        draft = script_from_beats([beat(0,3,'무엇이 달라졌을까요?','card'), beat(3,30,'첫 줄을 살펴보세요.','card'),
                                   beat(30,60,'원본과 한 번 대조해 보세요.','card')])
        draft['topic']['title'] = '가상 문서의 입력 조건 확인'
        draft['provenance'] = dict(author='fixture response', model=MODEL, mock=False)
        revision = deepcopy(draft)
        revision['narrative_beats'][1]['shot_type'] = 'demo'
        research = dict(candidates=[
            dict(topic=draft['topic']['title'],rationale='가상 입력으로 시연 가능',evidence_status='unverified'),
            dict(topic='가상 화면 설정 비교',rationale='두 화면 필요',evidence_status='unverified')],
            selected_topic=draft['topic']['title'],selection_reason='한 화면 시연',uncertainty='최근 유행·실제 성과 미검증')
        manager, employee = script_callbacks(draft, revision)

        def send(request, timeout):
            current = self.store.load(self.job)
            attempt = current['real_ai']['attempts'][-1]
            self.assertEqual(attempt['status'], 'reserved')
            self.assertTrue(attempt['transport_started_at'])
            self.assertEqual(request.full_url, ENDPOINT)
            self.assertEqual(request.get_header('X-goog-api-key'), self.key)
            wire = json.loads(request.data)
            self.assertNotIn('tools', wire)
            self.assertNotIn(self.key, request.data.decode())
            message = json.loads(wire['contents'][0]['parts'][0]['text'])
            phase, context = message['phase'], message['data']
            role = context.get('assignment', {}).get('role')
            if phase == 'execute' and role == 'research':
                response = dict(content=json.dumps(research, ensure_ascii=False),
                                evidence='fixture only', uncertainty='unverified')
            elif phase == 'execute':
                if role == 'writer':
                    self.assertEqual(context['previous_results'][0]['role'], 'research')
                response = json.loads(employee(phase, context))
            else:
                response = json.loads(manager(phase, context))
                if phase == 'plan':
                    response['tasks'][0]['depends_on'] = ['research']
                    response['tasks'].insert(0, dict(id='research',role='research',title='조사',depends_on=[],
                        criteria_ids=['facts'],instructions='근거 미확인과 후보 비교'))
                if phase == 'finalize':
                    response.update(action='deliver', content='60초 가상 예시 기획 및 전체 대본',
                        checks=[{**check,'status':'met'} for check in response['checks']])
                response.pop('task_refs', None)
            return FixtureResponse(json.dumps(dict(candidates=[dict(finishReason='STOP',content=dict(role='model',
                parts=[dict(text=json.dumps(dict(result=response),ensure_ascii=False))]))],
                usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=30,totalTokenCount=50))).encode())
        self.http.side_effect = send

    def test_signed_native_wire_revision_and_studio_handoff(self):
        self.assertEqual(self.studio.action('workspace', self.project, 'mission', {})['mission']['id'], self.job)
        self.assertEqual(self.studio.detail('workspace', self.project)['stage'], 'research_planning')
        with self.assertRaisesRegex(CompanyError, 'mission_internal_review_incomplete'):
            self.studio.workflow.report_plan(self.project, provider_store=self.store)
        with self.assertRaisesRegex(CompanyError, 'operating_consent_required'):
            self.run_job()
        self.http.assert_not_called()
        self.approve()
        self.fixture()
        result = self.run_job()
        self.assertEqual(result['status'], 'needs_user_review', result.get('reason_code'))
        self.assertEqual(self.http.call_count, 10)
        self.assertEqual(len(result['assignments'][1]['versions']), 2)
        with self.assertRaisesRegex(CompanyError, 'mission_provider_evidence_incomplete'):
            self.studio.workflow.report_plan(self.project, provider_store=self.store)
        report = self.studio.workflow.report_plan(self.project, provider_store=self.store, allow_fixture=True)
        self.assertEqual(report, self.studio.workflow.report_plan(self.project, provider_store=self.store, allow_fixture=True))
        detail = self.studio.detail('workspace', self.project)
        self.assertEqual(detail['stage'], 'awaiting_plan_approval')
        self.assertEqual(report['provenance'], 'offline_http_fixture')
        self.assertEqual(detail['mission']['attempts'][-1]['usage']['total_tokens'], 50)
        self.assertIsNone(report['render_spec'])
        self.assertEqual(detail['flow']['video_versions'], [])
        self.run_job()
        self.assertEqual(self.http.call_count, 10)

    def test_failed_call_consumed_and_key_change_blocked_before_transport(self):
        self.approve()
        self.env['GEMINI_API_KEY'] = 'wrong-fixture-key-value'
        self.company.config = Gemini35Config(self.env['GEMINI_API_KEY'])
        with self.assertRaisesRegex(CompanyError, 'mission_key_binding_mismatch'):
            self.run_job()
        self.http.assert_not_called()
        self.env['GEMINI_API_KEY'] = self.key
        self.company.config = Gemini35Config(self.key)
        self.http.side_effect = HTTPError(ENDPOINT, 429, 'test', {}, None)
        result = self.run_job()
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['real_ai']['attempts'][0]['status'], 'failed')
        with self.assertRaisesRegex(CompanyError, 'mission_restart_forbidden'):
            self.run_job(resume=True)
        with self.assertRaises(CompanyError):
            self.run_job()
        self.http.assert_called_once()
        self.assertEqual(self.studio.detail('workspace', self.project)['stage'], 'research_planning')


    def test_game_goal_has_no_injected_data_or_fixed_duration_and_cannot_call(self):
        project = self.studio.create(dict(goal=GAME_GOAL, audience='', language='한국어',
            platform='YouTube Shorts', duration=None, notes='', key='00000000-0000-4000-8000-000000000043'))['id']
        self.job = self.studio.workflow.stage_mission_one(project)
        job = self.store.load(self.job)
        self.store.check_scope(job)
        self.assertEqual(set(job['quality_inputs']['answers']), {'audience','representative_project'})
        self.assertNotIn('duration_seconds', job['quality_inputs']['constraints'])
        with self.assertRaisesRegex(CompanyError, GAME_RESEARCH_BLOCKER):
            self.store.prepare_mission(self.job, key=self.key, account_project='fixture project',
                remaining_requests=10, quota_note='fixture RPM/TPM')
        with self.assertRaisesRegex(CompanyError, GAME_RESEARCH_BLOCKER):
            self.run_job()
        with self.assertRaisesRegex(CompanyError, GAME_RESEARCH_BLOCKER):
            self.studio.workflow.report_plan(project, provider_store=self.store, allow_fixture=True)
        self.http.assert_not_called()
        detail = self.studio.detail('workspace', project)
        self.assertEqual(detail['stage'], 'research_planning')
        self.assertEqual(detail['mission']['reason'], GAME_RESEARCH_BLOCKER)
        self.assertEqual(detail['flow']['plan_versions'], [])

    def test_explicit_script_duration_can_differ_from_legacy_default(self):
        def beat(start, end, text, shot):
            return dict(start=start,end=end,narration=text,caption='가상 예시',screen='가상 화면',
                shot_type=shot,source_ref='미확보',source_status='pending',fact_status='illustrative')
        script = script_from_beats([beat(0,3,'어떻게 달라졌나요?','card'),beat(3,34,'한 장면만 비교해 보세요.','demo')])
        script['target_duration'] = 34
        self.assertFalse(inspect_script(script, AUDIENCE, mock=True, target_duration=34)['defects'])
        with self.assertRaisesRegex(CompanyError,'invalid_script_contract'):
            inspect_script(script, AUDIENCE, mock=True)
        script['narrative_beats'][-1]['end'] = 33
        self.assertIn('total_duration', {d['issue'] for d in inspect_script(script, AUDIENCE, mock=True,
            target_duration=34)['defects']})

    def test_employee_web_queries_to_manager_duration_and_representative(self):
        from datetime import datetime,timedelta,timezone
        from urllib.parse import parse_qs, urlsplit
        from employee_web_research import TOOL
        from video_mission_one import _binding
        project = self.studio.create(dict(goal=GAME_GOAL,audience=AUDIENCE,language='한국어',
            platform='YouTube Shorts',duration=None,notes='',key='00000000-0000-4000-8000-000000000044'))['id']
        previous = self.studio.workflow.stage_mission_one(project)
        self.job = self.studio.workflow.connect_employee_web(project)
        self.assertNotEqual(previous,self.job)
        self.assertEqual(self.studio.workflow.connect_employee_web(project),self.job)
        self.assertEqual(self.store.load(previous)['real_ai']['attempts'],[])
        youtube_key='fixture-youtube-key-secret'
        self.enterContext(patch.dict('os.environ',YOUTUBE_DATA_API_KEY=youtube_key))
        body=self.store.prepare_mission(self.job,key=self.key,account_project='fixture',remaining_requests=10,
            quota_note='fixture',youtube_key=youtube_key,youtube_project='fixture-youtube',
            search_remaining=4,units_remaining=4,confirm_youtube_policy=True)
        self.assertNotIn(youtube_key,json.dumps(body))
        self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
        published=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat().replace('+00:00','Z')
        vid='abcdefghijk'
        urls=[]
        def web_send(request,timeout):
            state=self.store.load(self.job)['employee_web']
            self.assertEqual(state['attempts'][-1]['status'],'reserved')
            self.assertEqual(request.get_header('X-goog-api-key'),youtube_key)
            urls.append(request.full_url)
            self.assertNotIn(youtube_key,request.full_url)
            if urlsplit(request.full_url).path.endswith('/search'):
                response=dict(items=[dict(id=dict(videoId=vid))])
            else:
                response=dict(items=[dict(id=vid,snippet=dict(title='가상 게임 예시',categoryId='20',publishedAt=published),
                    contentDetails=dict(duration='PT34S'),statistics=dict(viewCount='1234'))])
            return FixtureResponse(json.dumps(response).encode())
        self.enterContext(patch('employee_web_research.send_once',side_effect=web_send))
        def beat(a,b,line,shot):
            return dict(start=a,end=b,narration=line,caption='가상 예시',screen='가상 비교',
                shot_type=shot,source_ref='미확보',source_status='pending',fact_status='illustrative')
        script=script_from_beats([beat(0,3,'왜 달라졌을까요?','card'),beat(3,34,'두 화면을 비교해 보세요.','demo')])
        script.update(target_duration=34)
        script['topic']['title']='가상 게임의 두 장면'
        script['provenance']=dict(author='fixture',model=MODEL,mock=False)
        manager,employee=script_callbacks(script,script)
        queries=dict(tool=TOOL,queries=[dict(query='fixture employee game query',purpose='shorts_examples',
                                             lookback_days=7,order='relevance')])
        decision=dict(game='가상 게임',selected_topic=script['topic']['title'],duration_seconds=34,
            duration_reason='관측 예시와 설명 분량',selection_reason='두 장면 비교',other_candidates_reason='다른 예시는 복잡',
            evidence_ids=['q0:'+vid],shorts_status='unverified',rights_plan='직접 녹화 권리 확인 대기')
        def ai_send(request,timeout):
            message=json.loads(json.loads(request.data)['contents'][0]['parts'][0]['text'])
            phase,context=message['phase'],message['data']
            role=context.get('assignment',{}).get('role')
            if phase=='execute' and role=='research':
                result=dict(content=json.dumps(queries),evidence='fixture query builder',uncertainty='unverified')
            elif phase=='execute':
                self.assertEqual(context['quality']['manager_selection'],decision)
                result=json.loads(employee(phase,context))
            else:
                result=json.loads(manager(phase,context))
                if phase=='plan':
                    result['tasks'][0]['depends_on']=['research']
                    result['tasks'].insert(0,dict(id='research',role='research',title='조사',depends_on=[],
                        criteria_ids=['facts'],instructions='직원 직접 질의'))
                if phase=='review' and role=='research':
                    self.assertIn('EMPLOYEE_WEB_RECEIPT',context['result']['evidence'])
                    result['feedback']=json.dumps(decision)
                if phase=='finalize':
                    result.update(action='deliver',content='가상 게임 기획',
                                  checks=[{**c,'status':'met'} for c in result['checks']])
                result.pop('task_refs',None)
            return FixtureResponse(json.dumps(dict(candidates=[dict(finishReason='STOP',content=dict(role='model',
                parts=[dict(text=json.dumps(dict(result=result),ensure_ascii=False))]))],
                usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=30,totalTokenCount=50))).encode())
        self.http.side_effect=ai_send
        result=self.run_job()
        self.assertEqual(result['status'],'needs_user_review',result.get('reason_code'))
        self.assertEqual(self.http.call_count,8)
        self.assertEqual(len(urls),2)
        report=self.studio.workflow.report_plan(project,provider_store=self.store,allow_fixture=True)
        self.assertEqual(report['script']['target_duration'],34)
        self.assertEqual(report['research']['observations'][0]['shorts_classification'],'unverified')
        self.assertEqual(report['sources'][0]['url'],'https://www.youtube.com/watch?v='+vid)
        self.assertIsNone(report['render_spec'])
