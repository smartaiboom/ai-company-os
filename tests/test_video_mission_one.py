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
            remaining_requests=None, quota_note='provider quota not verified; fixture')
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

    # Synthetic cases only: the original failed live review was not retained.
    def test_research_plain_feedback_without_selection_rejected(self):
        self.review_error = 'plain'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_research_malformed_feedback_without_selection_rejected(self):
        self.review_error = 'inner_json'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_research_nonaccept_uses_prose_and_null_selection(self):
        self.company._research_review_state = {'employee_web':None}
        value = dict(action='revise', rationale='합성 예제', evidence='fixture', uncertainty='미확인',
                     checks=[], feedback='조사 근거를 다시 확인하세요', operation=None, selection=None)
        result = self.company._parse_role_content(json.dumps({'result':value}), 'review')
        self.assertEqual(result['feedback'], value['feedback'])
        self.assertNotIn('selection',result)
        self.http.assert_not_called()

    def test_research_missing_selection_field_rejected(self):
        self.review_error = 'missing_field'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_research_invalid_selection_field_rejected(self):
        self.review_error = 'field'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_research_invalid_evidence_rejected(self):
        self.review_error = 'evidence'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_research_outer_json_failure_classified(self):
        self.review_error = 'outer_json'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_unspecified_audience_does_not_allow_selected_topic_tampering(self):
        self.audience_case = 'inferred'
        self.script_topic_tamper = True
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_unspecified_audience_inference_reaches_representative_handoff(self):
        self.audience_case = 'inferred'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_concrete_audience_mismatch_stops_without_retry(self):
        self.audience_case = 'concrete_mismatch'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_unspecified_audience_missing_inference_stops_without_retry(self):
        self.audience_case = 'missing_inference'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_review_failure_successor_enforces_cumulative_ten_call_cap(self):
        self.exhaust_resume_budget = True
        self.test_review_failure_successor_reuses_validated_work_with_six_calls()

    def test_review_failure_successor_reuses_validated_work_with_six_calls(self):
        self.successor_fixture = True
        self.resume_fixture = True
        self.review_error = 'inner_json'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_dns_resume_stops_at_nine_new_calls(self):
        self.resume_fixture = True
        self.exhaust_resume_budget = True
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_dns_resume_preserves_history_and_hands_off_offline(self):
        self.resume_fixture = True
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_employee_web_queries_to_manager_duration_and_representative(self):
        from datetime import datetime,timedelta,timezone
        from urllib.parse import parse_qs, urlsplit
        from employee_web_research import TOOL
        from video_mission_one import _binding
        fixture_audience = '' if getattr(self,'audience_case',None) in ('inferred','missing_inference') else AUDIENCE
        project = self.studio.create(dict(goal=GAME_GOAL,audience=fixture_audience,language='한국어',
            platform='YouTube Shorts',duration=None,notes='',key='00000000-0000-4000-8000-000000000044'))['id']
        previous = self.studio.workflow.stage_mission_one(project)
        self.job = self.studio.workflow.connect_employee_web(project)
        self.assertNotEqual(previous,self.job)
        self.assertEqual(self.studio.workflow.connect_employee_web(project),self.job)
        self.assertEqual(self.store.load(previous)['real_ai']['attempts'],[])
        youtube_key='fixture-youtube-key-secret'
        self.enterContext(patch.dict('os.environ',YOUTUBE_DATA_API_KEY=youtube_key))
        body=self.store.prepare_mission(self.job,key=self.key,account_project='fixture',remaining_requests=None,
            quota_note='fixture',youtube_key=youtube_key,youtube_project='fixture-youtube',
            search_remaining=None,units_remaining=None,confirm_youtube_policy=True)
        self.assertNotIn(youtube_key,json.dumps(body))
        self.assertEqual(body['mission_web']['search_remaining'], 'unknown')
        self.assertEqual(body['mission_web']['general_units_remaining'], 'unknown')
        for field in ('approved_max_searches', 'approved_max_videos'):
            bad = deepcopy(body)
            bad['mission_web'][field] = 5
            with self.assertRaisesRegex(CompanyError, 'employee_web_scope_unverified'):
                self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
        bad = deepcopy(body)
        bad.pop('mission_research_review')
        with self.assertRaisesRegex(CompanyError, 'mission_research_review_consent'):
            self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
        self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
        if getattr(self, 'resume_fixture', False):
            from urllib.error import URLError
            import socket
            self.http.side_effect = URLError(socket.gaierror(-2, 'fixture DNS failure'))
            failed = self.run_job()
            self.assertEqual(failed['status'], 'stopped')
            old = self.job
            before = {p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and old in p.name}
            with self.assertRaisesRegex(CompanyError, 'explicit_owner_confirmation_required'):
                self.studio.workflow.stage_mission_resume(project)
            self.job = self.studio.workflow.stage_mission_resume(project, owner_confirmed=True)
            fresh = self.store.load(self.job)
            self.assertEqual(fresh['limits']['max_calls'], 9)
            self.assertFalse(fresh['real_ai']['consent'])
            self.assertEqual(fresh['mission_resume']['failed_attempt'], failed['real_ai']['attempts'][0]['id'])
            with self.assertRaisesRegex(CompanyError, 'mission_resume_already_created'):
                self.studio.workflow.stage_mission_resume(project, owner_confirmed=True)
            with self.assertRaisesRegex(CompanyError, 'operating_consent_required'):
                self.run_job()
            self.assertEqual(self.http.call_count, 1)
            new_body = self.store.prepare_mission(self.job,key=self.key,account_project='fixture',quota_note='fixture',
                youtube_key=youtube_key,youtube_project='fixture-youtube',confirm_youtube_policy=True)
            self.assertEqual(new_body['mission_account']['approved_max_calls'], 9)
            self.assertEqual(new_body['limits']['max_calls'], 9)
            for field in ('mission_resume', 'mission_account', 'limits'):
                bad = deepcopy(new_body)
                if field == 'mission_resume':
                    bad[field]['consumed_calls'] = 0
                elif field == 'mission_account':
                    bad[field]['approved_max_calls'] = 10
                else:
                    bad[field]['max_calls'] = 10
                with self.assertRaises(CompanyError):
                    self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
            with self.assertRaises(CompanyError):
                self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
            self.store.approve(self.job,new_body,review_hash=digest(new_body),owner_confirmed=True)
            self.http.reset_mock(side_effect=True)
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
        if getattr(self,'audience_case',None):
            script['target_audience']='합성 예시 게임의 짧은 시연을 보고 싶은 시청자'
            if self.audience_case == 'inferred':
                script['unknowns'].append('AI 추론(사용자 미확정):' + script['target_audience'] + ' 근거: 합성 게임 주제와 관측된 시연 형식')
        script['topic']['title']='가상 게임의 두 장면'
        script['provenance']=dict(author='fixture',model=MODEL,mock=False)
        revised = deepcopy(script)
        if getattr(self, 'exhaust_resume_budget', False):
            revised['promise'] = '두 화면의 차이를 차례로 비교한다.'
        manager,employee=script_callbacks(script,revised)
        queries=dict(tool=TOOL,queries=[dict(query='fixture employee game query',purpose='shorts_examples',
                                             lookback_days=7,order='relevance')])
        if getattr(self, 'successor_fixture', False):
            queries['queries'].append(dict(query='fixture second query',purpose='game_interest',lookback_days=7,order='relevance'))
        decision=dict(game='가상 게임',selected_topic=script['topic']['title'],duration_seconds=34,
            duration_reason='관측 예시와 설명 분량',selection_reason='두 장면 비교',other_candidates_reason='다른 예시는 복잡',
            evidence_ids=['q0:'+vid],shorts_status='unverified',rights_plan='직접 녹화 권리 확인 대기')
        def ai_send(request,timeout):
            message=json.loads(json.loads(request.data)['contents'][0]['parts'][0]['text'])
            phase,context=message['phase'],message['data']
            role=context.get('assignment',{}).get('role')
            if not (phase == 'review' and role == 'research'):
                from role_json_schema import response_format
                self.assertEqual(json.loads(request.data)['generationConfig']['responseJsonSchema'],
                                 response_format(phase)['json_schema']['schema'])
            if phase=='execute' and role=='research':
                result=dict(content=json.dumps(queries),evidence='fixture query builder',uncertainty='unverified')
            elif phase=='execute':
                self.assertEqual(context['quality']['manager_selection'],decision)
                result=json.loads(employee(phase,context))
                if role=='writer' and getattr(self,'script_topic_tamper',False):
                    content=json.loads(result['content'])
                    content['topic']['title']='관리자가 선정하지 않은 합성 주제'
                    result['content']=json.dumps(content,ensure_ascii=False)
            else:
                result=json.loads(manager(phase,context))
                if phase=='plan':
                    result['tasks'][0]['depends_on']=['research']
                    result['tasks'].insert(0,dict(id='research',role='research',title='조사',depends_on=[],
                        criteria_ids=['facts'],instructions='직원 직접 질의'))
                if phase=='review' and role=='research':
                    self.assertIn('EMPLOYEE_WEB_RECEIPT',context['result']['evidence'])
                    from video_mission_one import research_review_schema
                    wire = json.loads(request.data)
                    self.assertEqual(wire['generationConfig']['responseJsonSchema'], research_review_schema())
                    result['feedback']='합성 검토: 관측 근거를 선정 객체에 기록했다.'
                    result['selection']=deepcopy(decision)
                    error = getattr(self, 'review_error', None)
                    if error in ('plain','inner_json'):
                        result.pop('selection')
                        result['feedback'] = '일반 검토 문장' if error == 'plain' else '{bad json'
                    elif error == 'missing_field':
                        result['selection'].pop('game')
                    elif error == 'field':
                        result['selection']['duration_seconds'] = 0
                    elif error == 'evidence':
                        result['selection']['evidence_ids'] = ['invented-id']
                if (getattr(self, 'exhaust_resume_budget', False) and phase == 'review'
                        and role == 'writer' and len(self.store.load(self.job)['assignments'][1]['versions']) == 1):
                    result.update(action='revise', feedback='missing_demo fixture: 대본을 다시 확인하세요')
                if phase=='finalize':
                    result.update(action='deliver',content='가상 게임 기획',
                                  checks=[{**c,'status':'met'} for c in result['checks']])
                result.pop('task_refs',None)
            response_text = json.dumps(dict(result=result),ensure_ascii=False)
            if phase == 'review' and role == 'research' and getattr(self,'review_error',None) == 'outer_json':
                response_text = '{synthetic invalid JSON'
            return FixtureResponse(json.dumps(dict(candidates=[dict(finishReason='STOP',content=dict(role='model',
                parts=[dict(text=response_text)]))],
                usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=30,totalTokenCount=50))).encode())
        self.http.side_effect=ai_send
        if getattr(self, 'successor_fixture', False):
            original_parser = self.company._parse_role_content
            def legacy_parser(raw,phase):
                if phase == 'review':
                    return super(MissionOneCompany,self.company)._parse_role_content(raw,phase)
                return original_parser(raw,phase)
            # Synthetic historical contract, not a reconstruction of the missing real response.
            with patch.object(self.company,'_parse_role_content',side_effect=legacy_parser):
                result=self.run_job()
            self.assertEqual(result['reason_code'],'invalid_model_json')
            second = self.job
            before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and second in p.name})
            with self.assertRaisesRegex(CompanyError,'explicit_owner_confirmation_required'):
                self.studio.workflow.stage_mission_successor(project)
            self.job = self.studio.workflow.stage_mission_successor(project,owner_confirmed=True)
            fresh = self.store.load(self.job)
            self.assertEqual(fresh['real_ai']['attempts'],[])
            self.assertEqual(fresh['limits']['max_calls'],6)
            with self.assertRaises(CompanyError):
                self.studio.workflow.stage_mission_successor(project,owner_confirmed=True)
            with self.assertRaisesRegex(CompanyError,'operating_consent_required'):
                self.run_job()
            b=self.store.prepare_mission(self.job,key=self.key,account_project='fixture',quota_note='fixture',
                youtube_key=youtube_key,youtube_project='fixture-youtube',confirm_youtube_policy=True)
            self.assertEqual(b['mission_web']['approved_max_searches'],2)
            self.assertEqual(b['mission_successor']['consumed_calls'],4)
            for section,key in [('mission_successor','consumed_calls'),('mission_account','approved_max_calls'),('mission_web','approved_max_searches')]:
                bad=deepcopy(b); bad[section][key]+=1
                with self.assertRaises(CompanyError):
                    self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
            self.store.approve(self.job,b,review_hash=digest(b),owner_confirmed=True)
            self.review_error=None
            self.http.reset_mock(side_effect=False)
            result=self.run_job()
        else:
            result=self.run_job()
        if getattr(self,'script_topic_tamper',False):
            self.assertEqual(result['reason_code'],'mission_selected_topic_mismatch')
            self.assertEqual(self.http.call_count,4)
            with self.assertRaises(CompanyError):
                self.run_job()
            self.assertEqual(self.http.call_count,4)
            return
        if getattr(self,'audience_case',None) in ('concrete_mismatch','missing_inference'):
            expected = 'script_audience_mismatch' if self.audience_case=='concrete_mismatch' else 'script_audience_inference_required'
            self.assertEqual(result['reason_code'],expected)
            diag=result['real_ai']['attempts'][-1]['script_validation_diagnostics']
            self.assertEqual(diag['field'],'target_audience')
            self.assertEqual(diag['audience_unspecified'],self.audience_case=='missing_inference')
            self.assertEqual(self.http.call_count,4)
            with self.assertRaises(CompanyError):
                self.run_job()
            self.assertEqual(self.http.call_count,4)
            return
        if getattr(self, 'review_error', None):
            error = self.review_error
            expected = ('mission_research_review_json_invalid' if error == 'outer_json' else
                        'mission_research_review_structure_invalid' if error in ('plain','inner_json','missing_field') else
                        'mission_research_selection_invalid')
            self.assertEqual(result['reason_code'], expected)
            self.assertEqual(self.http.call_count,3)
            self.assertEqual(len(urls),2)
            diagnostic = result['real_ai']['attempts'][-1]['mission_review_diagnostics']
            self.assertEqual(set(diagnostic), {'stage','category','content_bytes','content_hash'})
            self.assertEqual(diagnostic['stage'], 'research_review_json' if error == 'outer_json' else
                             'research_review_structure' if error in ('plain','inner_json','missing_field') else 'research_selection_validation')
            self.assertEqual(result['assignments'][0]['reviews'],[])
            with self.assertRaises(CompanyError):
                self.run_job()
            self.assertEqual(self.http.call_count,3)
            return
        if getattr(self, 'exhaust_resume_budget', False):
            self.assertNotEqual(result['status'], 'needs_user_review')
            self.assertEqual(len(result['real_ai']['attempts']), 6 if getattr(self,'successor_fixture',False) else 9, result.get('reason_code'))
            self.assertEqual(self.http.call_count, 6 if getattr(self,'successor_fixture',False) else 9)
            self.assertEqual(result.get('reason_code'), 'optional_technical_cap_reached')
            with self.assertRaises(CompanyError):
                self.run_job()
            for path, content in before.items():
                self.assertEqual(path.read_bytes(), content)
            return
        self.assertEqual(result['status'],'needs_user_review',result.get('reason_code'))
        self.assertEqual(self.http.call_count,6 if getattr(self,'successor_fixture',False) else 8)
        self.assertEqual(len(urls),4 if getattr(self,'successor_fixture',False) else 2)
        report=self.studio.workflow.report_plan(project,provider_store=self.store,allow_fixture=True)
        if getattr(self,'successor_fixture',False):
            self.assertEqual(report['research']['reuse']['source_job'],second)
            self.assertFalse(report['research']['reuse']['newly_observed'])
        if getattr(self,'audience_case',None)=='inferred':
            self.assertEqual(self.store.load(self.job)['quality_inputs']['target_segment'],'미정')
            self.assertEqual(report['script']['target_audience'],script['target_audience'])
            self.assertIn('AI 추론(사용자 미확정):',report['script']['unknowns'][-1])
            self.assertEqual(report['provenance'],'offline_http_fixture')
        self.assertEqual(report['script']['target_duration'],34)
        self.assertEqual(report['research']['observations'][0]['shorts_classification'],'unverified')
        self.assertEqual(report['sources'][0]['url'],'https://www.youtube.com/watch?v='+vid)
        self.assertIsNone(report['render_spec'])
        if getattr(self, 'resume_fixture', False):
            self.assertEqual(report['provenance'], 'offline_http_fixture')
            self.assertEqual(self.studio.detail('workspace',project)['stage'],'awaiting_plan_approval')
            for path, content in before.items():
                self.assertEqual(path.read_bytes(), content)
            with self.assertRaises(CompanyError):
                self.company.run(old,expected_state_hash=self.store.load(old)['storage_hash'])
            self.assertEqual(self.http.call_count,6 if getattr(self,'successor_fixture',False) else 8)
            changed = self.store.load(old)
            changed['events'].append(dict(event='fixture tamper'))
            self.store.save(changed)
            with self.assertRaises(CompanyError):
                self.store.check_scope(self.store.load(self.job))

    def test_unknown_quota_and_signed_caps_cannot_be_increased(self):
        body = self.store.prepare_mission(self.job, key=self.key, account_project='fixture',
            quota_note='unknown provider balance')
        self.assertEqual(body['mission_account']['remaining_requests'], 'unknown')
        self.assertEqual(body['mission_account']['approved_max_calls'], 10)
        bad = deepcopy(body)
        bad['mission_account']['approved_max_calls'] = 11
        with self.assertRaisesRegex(CompanyError, 'mission_free_account_unverified'):
            self.store.approve(self.job, bad, review_hash=digest(bad), owner_confirmed=True)
        bad = deepcopy(body)
        bad['mission_account']['billing_disabled'] = False
        with self.assertRaisesRegex(CompanyError, 'mission_free_account_unverified'):
            self.store.approve(self.job, bad, review_hash=digest(bad), owner_confirmed=True)
        with self.assertRaisesRegex(CompanyError, 'consent_review_changed'):
            self.store.approve(self.job, body, review_hash='wrong', owner_confirmed=True)
        for value in (-1, True, '10', 1.5):
            with self.assertRaisesRegex(CompanyError, 'invalid_quota_observation'):
                self.store.prepare_mission(self.job, key=self.key, account_project='fixture',
                    quota_note='unknown', remaining_requests=value)
        self.http.assert_not_called()

    def test_timeout_is_consumed_and_not_retried(self):
        self.approve()
        self.http.side_effect = TimeoutError('fixture timeout')
        result = self.run_job()
        self.assertEqual(len(result['real_ai']['attempts']), 1)
        with self.assertRaisesRegex(CompanyError, 'mission_restart_forbidden'):
            self.run_job()
        self.http.assert_called_once()

    def test_wrong_paid_endpoint_is_blocked_before_transport(self):
        self.approve()
        self.env['GEMINI35_ENDPOINT'] = 'https://paid.invalid/generate'
        with self.assertRaisesRegex(CompanyError, 'gemini_provider_binding'):
            self.run_job()
        self.http.assert_not_called()
