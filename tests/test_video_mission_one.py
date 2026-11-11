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
from mission_game_evidence import GAME_EVIDENCE, GAME_GOAL, validate_game_decision, validate_game_research
from studio_server import Studio
from video_mission_one import MissionOneCompany, MissionOneStore
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

    def fixture(self, *, game=False, wrong_duration=False):
        def beat(start, end, narration, shot):
            return dict(start=start,end=end,narration=narration,caption='가상 예시',screen='가상 예시 화면',
                        shot_type=shot,source_ref='소스 미확보',source_status='pending',fact_status='illustrative')
        draft = script_from_beats([beat(0,3,'무엇이 달라졌을까요?','card'), beat(3,30,'첫 줄을 살펴보세요.','card'),
                                   beat(30,60,'원본과 한 번 대조해 보세요.','card')])
        draft['topic']['title'] = '가상 문서의 입력 조건 확인'
        draft['provenance'] = dict(author='fixture response', model=MODEL, mock=False)
        if game:
            draft['topic']['title'] = '가상 역전의 한 장면'
            draft['target_duration'] = 34
            draft['narrative_beats'][1]['end'] = 17
            draft['narrative_beats'][2].update(start=17,end=34)
        revision = deepcopy(draft)
        revision['narrative_beats'][1]['shot_type'] = 'demo'
        research = dict(candidates=[
            dict(topic=draft['topic']['title'],rationale='가상 입력으로 시연 가능',evidence_status='unverified'),
            dict(topic='가상 화면 설정 비교',rationale='두 화면 필요',evidence_status='unverified')],
            selected_topic=draft['topic']['title'],selection_reason='한 화면 시연',uncertainty='최근 유행·실제 성과 미검증')
        decision = None
        if game:
            research = dict(candidates=[
                dict(game='Counter-Strike 2',topic=draft['topic']['title'],rationale='가상 한 장면 시연',
                     player_evidence_id='steam-cs2',shorts_evidence_status='unverified',rights_plan='권리 확인 전 미확보'),
                dict(game='Dota 2',topic='가상 시야 설명',rationale='설명 분량이 더 필요',
                     player_evidence_id='steam-dota2',shorts_evidence_status='unverified',rights_plan='권리 확인 대기')],
                uncertainty='한국 게임 쇼츠 실적 미검증')
            decision = dict(selected_topic=draft['topic']['title'],duration_seconds=34,duration_reason='후크와 두 장면 배치',
                selection_reason='한 장면에 집중',other_candidates_reason='시야 규칙 설명이 추가로 필요',
                considered_durations=[22,34,45],duration_evidence_ids=['korea-length','gaming-length'])
            validate_game_research(research,GAME_EVIDENCE)
            with self.assertRaisesRegex(CompanyError, 'mission_duration_evidence_mismatch'):
                validate_game_decision({**decision,'duration_evidence_ids':['korea-length','youtube-rule']},research,GAME_EVIDENCE)
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
                if game:
                    self.assertEqual(context['quality']['manager_selection'],decision)
                    self.assertEqual(context['quality']['answers']['public_evidence'],GAME_EVIDENCE)
                response = json.loads(employee(phase, context))
                if game and wrong_duration and role == 'writer':
                    script = json.loads(response['content'])
                    script['target_duration'] = 60
                    response['content'] = json.dumps(script,ensure_ascii=False)
            else:
                response = json.loads(manager(phase, context))
                if phase == 'plan':
                    response['tasks'][0]['depends_on'] = ['research']
                    response['tasks'].insert(0, dict(id='research',role='research',title='조사',depends_on=[],
                        criteria_ids=['facts'],instructions='근거 미확인과 후보 비교'))
                if game and phase == 'review' and role == 'research':
                    response['feedback'] = json.dumps(decision, ensure_ascii=False)
                if phase == 'finalize':
                    response.update(action='deliver', content='가상 예시 기획 및 전체 대본',
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


    def _stage_game(self):
        self.project = self.studio.create(dict(goal=GAME_GOAL, audience=AUDIENCE, language='한국어',
            platform='YouTube Shorts', duration=None, notes='', key='00000000-0000-4000-8000-000000000042'))['id']
        self.job = self.studio.workflow.stage_mission_one(self.project)
        staged = self.store.load(self.job)
        self.assertNotIn('duration_seconds', staged['quality_inputs']['constraints'])
        self.assertEqual(staged['quality_inputs']['answers']['public_evidence'],GAME_EVIDENCE)

    def test_game_manager_selects_topic_and_length_before_writer_and_report(self):
        self._stage_game()
        self.approve()
        self.fixture(game=True)
        result = self.run_job()
        self.assertEqual(result['status'], 'needs_user_review', result.get('reason_code'))
        self.assertEqual(self.http.call_count, 10)
        report = self.studio.workflow.report_plan(self.project, provider_store=self.store, allow_fixture=True)
        self.assertEqual(report['script']['target_duration'], 34)
        self.assertEqual(report['script']['narrative_beats'][-1]['end'], 34)
        self.assertEqual(report['research']['manager_decision']['considered_durations'], [22,34,45])
        self.assertEqual(len(report['sources']), 4)
        self.assertIsNone(report['render_spec'])

    def test_game_writer_cannot_restore_60_seconds_after_manager_decision(self):
        self._stage_game()
        self.approve()
        self.fixture(game=True, wrong_duration=True)
        result = self.run_job()
        self.assertEqual(result['reason_code'], 'invalid_script_contract')
        self.assertEqual(self.http.call_count, 4)
        self.assertEqual(self.studio.detail('workspace', self.project)['stage'], 'research_planning')
