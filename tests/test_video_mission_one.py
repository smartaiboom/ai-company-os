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

    def test_new_consented_rework_after_final_503_to_v2_offline(self):
        self.unavailable_fixture=True
        self.new_attempt_fixture=True
        self.test_representative_feedback_rework_end_to_end_offline()

    def test_new_consented_rework_after_failed_plan_to_v2_offline(self):
        self.new_attempt_fixture=True
        self.test_representative_feedback_rework_end_to_end_offline()

    def test_strict_rework_plan_contract_to_script_offline(self):
        self.strict_plan_fixture=True
        self.test_representative_feedback_rework_end_to_end_offline()

    def test_ceo_quality_instruction_prepares_new_job_without_calls_offline(self):
        self.rework_quality_escalation_fixture=True
        self.strict_plan_fixture=True
        self.test_representative_feedback_rework_end_to_end_offline()

    def test_rework_quality_failure_revises_writer_and_hands_off_offline(self):
        self.rework_quality_revision_fixture=True
        self.rework_criterion_ids_fixture=True
        self.strict_plan_fixture=True
        self.test_representative_feedback_rework_end_to_end_offline()

    def test_rework_manager_criterion_ids_handoff_to_representative_offline(self):
        self.rework_criterion_ids_fixture=True
        self.strict_plan_fixture=True
        self.test_representative_feedback_rework_end_to_end_offline()

    def test_handoff_failure_new_consent_gate_to_v2_offline(self):
        self.handoff_failure_fixture=True
        self.new_attempt_fixture=True
        self.rework_criterion_ids_fixture=True
        self.test_representative_feedback_rework_end_to_end_offline()

    def test_rework_plan_wire_and_http_error_diagnostics_offline(self):
        self.strict_plan_fixture=True
        self.test_representative_feedback_rework_end_to_end_offline()
        from autonomous_gemini import GeminiCompany
        for raw,expected in ((b'{"error":{"code":503,"status":"UNAVAILABLE","code":400}}','unreadable_or_invalid'),
                             (b'{"error":{"code":NaN}}','unreadable_or_invalid'),
                             (b'private HTML instead of JSON','unreadable_or_invalid'),
                             (b'x'*4097,'too_large'),(b'[]','unexpected_shape')):
            entry={};error=HTTPError(ENDPOINT,503,'private',{},BytesIO(raw))
            GeminiCompany._record_http_error_body(entry,error)
            self.assertEqual(entry['provider_error_body'],{'parse':expected})
            error.close()

    def test_disabled_zero_send_recovery_requires_explicit_click(self):
        self.disabled_recovery_fixture=True
        self.test_rework_consent_size_limit_and_approved_start()

    def test_rework_consent_size_limit_and_approved_start(self):
        self.consent_size_fixture=True
        self.test_representative_feedback_rework_end_to_end_offline()

    def test_representative_feedback_rework_end_to_end_offline(self):
        self.representative_rework_fixture=True
        self.test_cli_local_handoff_uses_canonical_store_and_preserves_guards()

    def test_cli_local_handoff_uses_canonical_store_and_preserves_guards(self):
        self.local_handoff_fixture=True
        self.test_caption_revision_new_signed_budget_and_cutroom()

    def test_caption_revision_new_signed_budget_and_cutroom(self):
        self.caption_revision_fixture=True
        self.test_partial_writer_revision_continuation_preserves_feedback_and_hands_off()

    def test_partial_writer_revision_continuation_preserves_feedback_and_hands_off(self):
        self.partial_revision_fixture=True
        self.test_dns_permission_successor_preserves_nine_failures_and_hands_off()

    def test_dns_permission_successor_preserves_nine_failures_and_hands_off(self):
        self.dns_permission_fixture=True
        self.test_native_audience_v2_preserves_history_and_allows_only_changed_contract()

    def test_native_audience_v2_preserves_history_and_allows_only_changed_contract(self):
        self.audience_upgrade_fixture=True
        self.test_unified_writer_successor_preserves_seven_failures_and_hands_off()

    def test_unified_writer_successor_preserves_seven_failures_and_hands_off(self):
        self.unified_successor_fixture=True
        self.test_topic_failure_successor_preserves_six_failures_and_hands_off()

    def test_writer_native_schema_invalid_shot_stops_with_safe_field_diagnostics(self):
        self.writer_schema_mutation=lambda v:v['narrative_beats'][0].update(shot_type='synthetic-invalid-shot')
        self.test_audience_variant_25_second_script_reaches_human_handoff()

    def test_writer_schema_covers_required_fields_and_relational_errors(self):
        from script_quality import writer_contract,validate_writer_contract,script_failure_details,WRITER_FIELDS,BEAT_FIELDS
        from role_json_schema import matches
        def beat(a,b,kind,line):
            return dict(start=a,end=b,shot_type=kind,narration=line,caption='합성',screen='가상 비교',source_ref='미확보',
                source_status='pending',fact_status='illustrative')
        script=script_from_beats([beat(0,3,'card','왜 다를까요?'),beat(3,10,'detail','첫 화면을 보세요.'),beat(10,25,'demo','두 화면을 비교하세요.')])
        script.update(target_duration=25,target_audience='합성 시연을 찾는 시청자')
        script['topic']['title']='합성 관리자 선정 주제'
        script['provenance']=dict(author='synthetic fixture',model=MODEL,mock=False)
        script['unknowns']=['AI 제안(사용자 미확정): 합성 시연을 찾는 시청자. 이유: 합성 주제의 설명 난이도']
        contract=writer_contract('미정',25,MODEL,script['topic']['title'])
        self.assertEqual(set(contract['schema']['required']),set(WRITER_FIELDS))
        self.assertEqual(set(contract['schema']['properties']['narrative_beats']['items']['required']),set(BEAT_FIELDS))
        self.assertTrue(matches(script,contract['schema']))
        original=deepcopy(script)
        self.assertFalse(validate_writer_contract(script,contract)['defects'])
        self.assertEqual(script,original)
        self.assertEqual(contract['version'],2)
        self.assertEqual(contract['audience_input'],dict(target_segment='미정',user_specified=False))
        old=writer_contract('미정',25,MODEL,script['topic']['title'],version=1)
        self.assertNotEqual(digest(old),digest(contract))
        encoded=json.dumps(contract['schema'])
        self.assertNotIn('"not":',encoded);self.assertNotIn('"pattern":',encoded)
        literal=deepcopy(script);literal['target_audience']='미정'
        with self.assertRaisesRegex(CompanyError,'script_audience_inference_required') as caught:
            validate_writer_contract(literal,contract)
        self.assertEqual(caught.exception.detail_code,'literal_unspecified_audience')
        specified=writer_contract(script['target_audience'],25,MODEL,script['topic']['title'])
        self.assertFalse(validate_writer_contract(script,specified)['defects'])
        different=deepcopy(script);different['target_audience']+=' 다른 대상'
        with self.assertRaisesRegex(CompanyError,'script_audience_mismatch'):validate_writer_contract(different,specified)
        for field in WRITER_FIELDS:
            bad=deepcopy(script);bad.pop(field)
            with self.subTest(missing=field), self.assertRaises(CompanyError) as caught:validate_writer_contract(bad,contract)
            self.assertEqual(script_failure_details(bad,caught.exception,contract)['field_path'],field)
        cases=[
            (lambda v:v['narrative_beats'][0].update(shot_type='closeup'),'invalid_script_shot'),
            (lambda v:v['narrative_beats'][0].update(source_status='licensed'),'invalid_script_source'),
            (lambda v:v['narrative_beats'][0].update(source_status='local_example'),'mission_visual_source_unverified'),
            (lambda v:v['narrative_beats'][0].update(fact_status='verified'),'invalid_script_fact'),
            (lambda v:v['topic'].update(title='다른 주제'),'mission_selected_topic_mismatch'),
            (lambda v:v['provenance'].update(model='other-model'),'script_provenance_mismatch'),
            (lambda v:v['provenance'].update(mock=True),'script_provenance_mismatch'),
            (lambda v:v.update(unknowns=[]),'script_audience_inference_required'),
            (lambda v:v['narrative_beats'][0].update(start=1),'invalid_script_timeline'),
            (lambda v:v.update(transcript='다른 본문'),'script_transcript_mismatch'),
            (lambda v:v.update(target_duration=24),'invalid_script_contract')]
        for mutate,code in cases:
            with self.subTest(code=code):
                bad=deepcopy(script);mutate(bad)
                with self.assertRaisesRegex(CompanyError,code) as caught:validate_writer_contract(bad,contract)
                diag=script_failure_details(bad,caught.exception,contract)
                self.assertEqual(diag['error_code'],code)
                for raw in (script['target_audience'],script['topic']['title'],self.key):self.assertNotIn(raw,json.dumps(diag,ensure_ascii=False))
        for kind in ('demo','detail','card'):
            valid=deepcopy(script);valid['narrative_beats'][0]['shot_type']=kind
            self.assertFalse(validate_writer_contract(valid,contract)['defects'])

    def test_topic_failure_successor_preserves_six_failures_and_hands_off(self):
        self.topic_successor_fixture=True
        self.test_audience_failure_successor_preserves_five_failures_and_hands_off()

    def test_selected_topic_copy_contract_25_second_handoff(self):
        self.selected_topic_fixture='합성 관리자 선정 — 두 화면 비교 (주제 식별)'
        self.test_audience_variant_25_second_script_reaches_human_handoff()

    def test_selected_topic_whitespace_mismatch_is_diagnosed_and_rejected(self):
        self.topic_whitespace_tamper=True
        self.test_unspecified_audience_does_not_allow_selected_topic_tampering()

    def test_audience_failure_successor_preserves_five_failures_and_hands_off(self):
        self.audience_successor_fixture=True
        self.free_error='audience'
        self.test_provider_limited_writer_has_no_arbitrary_cap_and_hands_off()

    def test_audience_variant_25_second_script_reaches_human_handoff(self):
        self.audience_variant=True
        self.provenance_case='correct'
        self.audience_case='inferred'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_literal_unspecified_audience_has_safe_detail_and_no_retry(self):
        self.audience_detail='literal_unspecified_audience'
        self.audience_case='missing_inference'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_missing_inference_reason_has_safe_detail_and_no_retry(self):
        self.audience_detail='reason_missing'
        self.audience_case='missing_inference'
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

    def test_provider_limited_writer_has_no_arbitrary_cap_and_hands_off(self):
        self.free_fixture=True
        self.test_doubled_budget_writer_handoff_preserves_four_failures_and_caps()

    def test_provider_limited_writer_preserves_explicit_owner_cap(self):
        self.free_explicit_cap=3
        self.test_provider_limited_writer_has_no_arbitrary_cap_and_hands_off()

    def test_provider_limited_writer_accepts_explicit_cap_above_legacy_twenty(self):
        self.free_explicit_cap=30
        self.test_provider_limited_writer_has_no_arbitrary_cap_and_hands_off()

    def test_generic_quality_store_keeps_its_existing_bounded_policy(self):
        from quality_provider import QualityProviderStore
        for cap in (None,30):
            with self.assertRaisesRegex(CompanyError,'bounded_quality_calls_required'):
                QualityProviderStore._limits(dict(max_calls=cap,max_revisions_per_task=1,max_total_revisions=1))

    def test_provider_limited_writer_stops_on_429_without_retry(self):
        self.free_error='429'
        self.test_provider_limited_writer_has_no_arbitrary_cap_and_hands_off()

    def test_provider_limited_writer_stops_on_quota_or_billing_without_fallback(self):
        self.free_error='quota'
        self.test_provider_limited_writer_has_no_arbitrary_cap_and_hands_off()

    def test_provider_limited_writer_preserves_timeout_without_resend(self):
        self.free_error='timeout'
        self.test_provider_limited_writer_has_no_arbitrary_cap_and_hands_off()

    def test_provider_limited_writer_records_validation_error_without_resend(self):
        self.free_error='provenance'
        self.test_provider_limited_writer_has_no_arbitrary_cap_and_hands_off()

    def test_doubled_budget_writer_handoff_preserves_four_failures_and_caps(self):
        self.budget_fixture=True
        self.writer_fixture=True
        self.successor_fixture=True
        self.resume_fixture=True
        self.review_error='inner_json'
        self.audience_case='inferred'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_doubled_budget_timeout_consumes_once_and_never_retries(self):
        self.budget_timeout=True
        self.test_doubled_budget_writer_handoff_preserves_four_failures_and_caps()

    def test_fixed_provenance_prompt_and_25_second_inferred_audience_handoff(self):
        self.provenance_case='correct'
        self.audience_case='inferred'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_mock_provenance_conflict_stops_with_safe_diagnostics(self):
        self.provenance_case='mock_conflict'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_other_model_provenance_stops_with_safe_diagnostics(self):
        self.provenance_case='other_model'
        self.test_employee_web_queries_to_manager_duration_and_representative()

    def test_writer_stage_resume_preserves_selection_and_hands_off_with_four_calls(self):
        self.writer_fixture=True
        self.successor_fixture=True
        self.resume_fixture=True
        self.review_error='inner_json'
        self.audience_case='inferred'
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
        account='gen-lang-client-0938732315' if getattr(self,'budget_fixture',False) else 'fixture'
        web_account=account if getattr(self,'budget_fixture',False) else 'fixture-youtube'
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
        body=self.store.prepare_mission(self.job,key=self.key,account_project=account,remaining_requests=None,
            quota_note='fixture',youtube_key=youtube_key,youtube_project=web_account,
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
            new_body = self.store.prepare_mission(self.job,key=self.key,account_project=account,quota_note='fixture',
                youtube_key=youtube_key,youtube_project=web_account,confirm_youtube_policy=True)
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
        duration=25 if getattr(self,'provenance_case',None) or getattr(self,'budget_fixture',False) else 34
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
                    contentDetails=dict(duration=f'PT{duration}S'),statistics=dict(viewCount='1234'))])
            return FixtureResponse(json.dumps(response).encode())
        self.enterContext(patch('employee_web_research.send_once',side_effect=web_send))
        def beat(a,b,line,shot):
            return dict(start=a,end=b,narration=line,caption='가상 예시',screen='가상 비교',
                shot_type=shot,source_ref='미확보',source_status='pending',fact_status='illustrative')
        script=script_from_beats([beat(0,3,'왜 달라졌을까요?','card'),beat(3,duration,'두 화면을 비교해 보세요.','demo')])
        script.update(target_duration=duration)
        if getattr(self,'audience_case',None):
            script['target_audience']='합성 예시 게임의 짧은 시연을 보고 싶은 시청자'
            if self.audience_case == 'inferred':
                script['unknowns'].append('AI 추론(사용자 미확정):' + script['target_audience'] + ' 근거: 합성 게임 주제와 관측된 시연 형식')
        if getattr(self,'audience_variant',False):
            script['unknowns']=[f'사용자 확인 전 AI 제안: {script["target_audience"].replace(" ","  ")}. 이유는 합성 주제와 관측된 시연 형식이 맞기 때문입니다.']
        if getattr(self,'audience_detail',None)=='literal_unspecified_audience':
            script['target_audience']='미정'
        elif getattr(self,'audience_detail',None)=='reason_missing':
            script['unknowns']=[f'AI 제안(사용자 미확정): {script["target_audience"]}']
        script['topic']['title']=getattr(self,'selected_topic_fixture','가상 게임의 두 장면')
        script['provenance']=dict(author='fixture',model=MODEL,mock=False)
        revised = deepcopy(script)
        if getattr(self, 'exhaust_resume_budget', False):
            revised['promise'] = '두 화면의 차이를 차례로 비교한다.'
        manager,employee=script_callbacks(script,revised)
        queries=dict(tool=TOOL,queries=[dict(query='fixture employee game query',purpose='shorts_examples',
                                             lookback_days=7,order='relevance')])
        if getattr(self, 'successor_fixture', False):
            queries['queries'].append(dict(query='fixture second query',purpose='game_interest',lookback_days=7,order='relevance'))
        decision=dict(game='가상 게임',selected_topic=script['topic']['title'],duration_seconds=duration,
            duration_reason='관측 예시와 설명 분량',selection_reason='두 장면 비교',other_candidates_reason='다른 예시는 복잡',
            evidence_ids=['q0:'+vid],shorts_status='unverified',rights_plan='직접 녹화 권리 확인 대기')
        def ai_send(request,timeout):
            wire=json.loads(request.data)
            notice=wire['systemInstruction']['parts'][0]['text']
            self.assertIn('provenance.mock=false',notice)
            self.assertIn('provenance.model='+MODEL,notice)
            self.assertIn('provenance.author is your claimed creative role',notice)
            message=json.loads(json.loads(request.data)['contents'][0]['parts'][0]['text'])
            phase,context=message['phase'],message['data']
            role=context.get('assignment',{}).get('role')
            if not (phase == 'review' and role == 'research') and not (phase=='execute' and role=='writer'):
                from role_json_schema import response_format
                self.assertEqual(json.loads(request.data)['generationConfig']['responseJsonSchema'],
                                 response_format(phase)['json_schema']['schema'])
            if phase=='execute' and role=='writer':
                self.assertIn('topic.title = quality.manager_selection.selected_topic',notice)
                self.assertIn('Copy this supplied string character-for-character',notice)
                self.assertIn('hook_0_3s, promise or viewing_reason',notice)
                self.assertEqual(context['quality']['manager_selection']['selected_topic'],script['topic']['title'])
                from role_json_schema import obj, S
                from script_quality import writer_contract
                contract=writer_contract(self.store.load(self.job)['quality_inputs']['target_segment'],duration,MODEL,decision['selected_topic'],
                    version=getattr(self,'writer_contract_version',2))
                self.assertEqual(context['quality']['writer_contract'],contract)
                expected=obj(result=obj(content=contract['schema'],evidence=S,uncertainty=S))
                self.assertEqual(wire['generationConfig']['responseJsonSchema'],expected)
                self.assertEqual(message['output_contract'],expected)
                self.assertIn('result.content MUST be a JSON object',notice)
                if contract['version']==2:
                    self.assertEqual(context['quality']['target_segment'],self.store.load(self.job)['quality_inputs']['target_segment'])
                    self.assertIn('target_segment',contract['audience_input'])
                    if contract['audience']=='미정':
                        self.assertFalse(contract['audience_input']['user_specified'])
                        self.assertIn('입력 target_segment=미정',notice)
                        self.assertIn('입력 상태를 복사하는 필드가 아닙니다',notice)
                        self.assertIn('AI가 제안',contract['schema']['properties']['target_audience']['description'])
                        self.assertTrue(contract['audience_output_example']['template_only'])
            if phase=='execute' and role=='research':
                result=dict(content=json.dumps(queries),evidence='fixture query builder',uncertainty='unverified')
            elif phase=='execute':
                self.assertEqual(context['quality']['manager_selection'],decision)
                result=json.loads(employee(phase,context))
                if role=='writer' and getattr(self,'provenance_case',None) in ('mock_conflict','other_model'):
                    content=json.loads(result['content'])
                    if self.provenance_case=='mock_conflict': content['provenance']['mock']=True
                    else: content['provenance']['model']='synthetic-wrong-model'
                    result['content']=json.dumps(content,ensure_ascii=False)
                if (role=='writer' and getattr(self,'budget_fixture',False)
                        and self.store.load(self.job).get('mission_writer_resume')):
                    content=json.loads(result['content']);content['provenance']['mock']=True
                    result['content']=json.dumps(content,ensure_ascii=False)
                if (role=='writer' and getattr(self,'writer_fixture',False)
                        and not self.store.load(self.job).get('mission_writer_resume')
                        and not self.store.load(self.job).get('mission_budget_writer')
                        and not self.store.load(self.job).get('mission_free_writer')
                        and not self.store.load(self.job).get('mission_audience_successor')
                        and not self.store.load(self.job).get('mission_topic_successor')
                        and not self.store.load(self.job).get('mission_unified_successor')):
                    content=json.loads(result['content'])
                    content['target_audience']='미정'
                    result['content']=json.dumps(content,ensure_ascii=False)
                if (role=='writer' and getattr(self,'free_error',None)=='provenance'
                        and self.store.load(self.job).get('mission_free_writer')):
                    content=json.loads(result['content']);content['provenance']['mock']=True
                    result['content']=json.dumps(content,ensure_ascii=False)
                if (role=='writer' and getattr(self,'free_error',None)=='audience'
                        and self.store.load(self.job).get('mission_free_writer')):
                    content=json.loads(result['content']);content['unknowns']=[]
                    result['content']=json.dumps(content,ensure_ascii=False)
                if (role=='writer' and getattr(self,'topic_successor_fixture',False)
                        and self.store.load(self.job).get('mission_audience_successor')):
                    content=json.loads(result['content']);content['topic']['title']='합성 여섯 번째 실패 제목'
                    result['content']=json.dumps(content,ensure_ascii=False)
                if (role=='writer' and getattr(self,'unified_successor_fixture',False)
                        and self.store.load(self.job).get('mission_topic_successor')):
                    content=json.loads(result['content']);content['narrative_beats'][0]['shot_type']='synthetic-invalid-shot'
                    result['content']=json.dumps(content,ensure_ascii=False)
                if role=='writer' and getattr(self,'script_topic_tamper',False):
                    content=json.loads(result['content'])
                    content['topic']['title']=(content['topic']['title'].replace(' ','  ') if getattr(self,'topic_whitespace_tamper',False)
                                               else '관리자가 선정하지 않은 합성 주제')
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
            if phase=='execute' and role=='writer':
                result['content']=json.loads(result['content'])
                if getattr(self,'writer_schema_mutation',None):
                    self.writer_schema_mutation(result['content'])
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
            b=self.store.prepare_mission(self.job,key=self.key,account_project=account,quota_note='fixture',
                youtube_key=youtube_key,youtube_project=web_account,confirm_youtube_policy=True)
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
        if getattr(self,'writer_schema_mutation',None):
            self.assertEqual(result['reason_code'],'invalid_script_shot')
            self.assertEqual(self.http.call_count,4)
            diag=result['real_ai']['attempts'][-1]['script_validation_diagnostics']
            self.assertEqual(diag['field_path'],'narrative_beats[0].shot_type')
            self.assertEqual(diag['beat_index'],0)
            self.assertFalse(diag['allowed_set_match'])
            self.assertEqual(diag['value_type'],'str')
            self.assertEqual(diag['value_length'],len('synthetic-invalid-shot'))
            self.assertTrue(diag['response_hash'])
            self.assertNotIn('synthetic-invalid-shot',json.dumps(diag))
            self.assertNotIn(self.key,json.dumps(diag))
            before={p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and self.job in p.name}
            with self.assertRaises(CompanyError):self.run_job()
            self.assertEqual(self.http.call_count,4)
            for path,data in before.items():self.assertEqual(path.read_bytes(),data)
            return
        if getattr(self,'provenance_case',None) in ('mock_conflict','other_model'):
            self.assertEqual(result['reason_code'],'script_provenance_mismatch')
            self.assertEqual(self.http.call_count,4)
            entry=result['real_ai']['attempts'][-1]
            self.assertEqual(entry['status'],'completed')
            self.assertEqual(entry['role_result_status'],'json_parsed')
            diag=entry['script_provenance_diagnostics']
            self.assertEqual(diag,dict(stage='writer_script_validation',category='script_provenance_mismatch',
                model_matches=self.provenance_case!='other_model',mock_matches=self.provenance_case!='mock_conflict',
                ledger_model_matches=True,response_hash=entry['response_hash']))
            self.assertNotIn('synthetic-wrong-model',json.dumps(diag))
            self.assertNotIn(self.key,json.dumps(diag))
            original={p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and self.job in p.name}
            with self.assertRaises(CompanyError):self.run_job()
            self.assertEqual(self.http.call_count,4)
            for path,data in original.items():self.assertEqual(path.read_bytes(),data)
            self.assertEqual(result['assignments'][1]['versions'],[])
            return
        if getattr(self,'writer_fixture',False):
            self.assertEqual(result['reason_code'],'script_audience_inference_required')
            self.assertEqual(self.http.call_count,2)
            third=self.job
            before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and third in p.name})
            reference=self.store.writer_reference(result)
            self.assertEqual(reference['consumed_calls'],6)
            self.assertEqual(len(reference['previous_attempt_ids']),6)
            self.assertEqual(reference['selection_hash'],digest(decision))
            with self.assertRaises(CompanyError): self.store.resume_reference(result)
            with self.assertRaises(CompanyError): self.store.successor_reference(result)
            with self.assertRaisesRegex(CompanyError,'explicit_owner_confirmation_required'):
                self.studio.workflow.stage_mission_writer_resume(project)
            self.job=self.studio.workflow.stage_mission_writer_resume(project,owner_confirmed=True)
            fresh=self.store.load(self.job)
            self.assertEqual(fresh['phase'],'work')
            self.assertEqual(fresh['limits']['max_calls'],4)
            self.assertEqual(fresh['assignments'][0],result['assignments'][0])
            self.assertFalse(fresh['sessions'])
            self.assertFalse(fresh['real_ai']['attempts'])
            self.assertFalse(fresh['real_ai']['consent'])
            with self.assertRaises(CompanyError):
                self.studio.workflow.stage_mission_writer_resume(project,owner_confirmed=True)
            with self.assertRaisesRegex(CompanyError,'operating_consent_required'): self.run_job()
            b=self.store.prepare_mission(self.job,key=self.key,account_project=account,quota_note='fixture',
                youtube_key=youtube_key,youtube_project=web_account,confirm_youtube_policy=True)
            for section,key in [('mission_writer_resume','consumed_calls'),('mission_account','approved_max_calls'),
                                ('mission_web','approved_max_searches')]:
                bad=deepcopy(b);bad[section][key]+=1
                with self.assertRaises(CompanyError):
                    self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
            for section in ('mission_account','mission_web'):
                bad=deepcopy(b);bad[section]['account_project']='different-account'
                with self.assertRaisesRegex(CompanyError,'mission_writer_account_changed'):
                    self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
            with self.assertRaises(CompanyError):
                self.store.approve(self.job,b,review_hash=digest(new_body),owner_confirmed=True)
            later=(datetime.now(timezone(timedelta(hours=9)))+timedelta(hours=2)).isoformat()
            with patch('autonomous_free.now',return_value=later):
                with self.assertRaisesRegex(CompanyError,'consent_expired'):
                    self.store.approve(self.job,b,review_hash=digest(b),owner_confirmed=True)
            # Mutated source, receipt, selection, user input and cap cannot be authorized.
            for mutate in (
                lambda p:p['mission_writer_resume'].update(selection_hash='tampered'),
                lambda p:p['quality_inputs'].update(target_segment='tampered'),
                lambda p:p['employee_web'].update(receipt_hash='tampered'),
                lambda p:p['limits'].update(max_calls=5)):
                bad=deepcopy(fresh);mutate(bad)
                with self.assertRaises(CompanyError): self.store.check_scope(bad)
            self.store.approve(self.job,b,review_hash=digest(b),owner_confirmed=True)
            with patch.dict('os.environ',GEMINI_API_KEY='changed-fixture-key'):
                changed_company=OfflineMissionCompany(self.store,LiveManagerProvider('fixture-manager'),
                    LiveEmployeeProvider('fixture-staff'),Gemini35Config('changed-fixture-key'))
                with self.assertRaises(CompanyError):
                    changed_company.run(self.job,expected_state_hash=self.store.load(self.job)['storage_hash'])
            self.http.reset_mock(side_effect=False)
            self.new_phases=[]
            original_send=self.http.side_effect
            def writer_send(request,timeout):
                msg=json.loads(json.loads(request.data)['contents'][0]['parts'][0]['text'])
                self.new_phases.append((msg['phase'],msg['data'].get('assignment',{}).get('role')))
                return original_send(request,timeout)
            self.http.side_effect=writer_send
            result=self.run_job()
            if getattr(self,'budget_fixture',False):
                self.assertEqual(result['reason_code'],'script_provenance_mismatch')
                self.assertEqual(self.http.call_count,1)
                fourth=self.job
                before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and fourth in p.name})
                self.finish_budget_fixture(project,result,before,urls,decision,script,youtube_key,writer_send)
                return
            self.assertEqual(result['status'],'needs_user_review',result.get('reason_code'))
            self.assertEqual(self.new_phases,[('execute','writer'),('review','writer'),('execute','editor'),('review','editor')])
            self.assertEqual(self.http.call_count,4)
            self.assertEqual(result['final']['source'],'accepted_review_handoff')
            self.assertEqual(result['final']['provider'],'system')
            self.assertEqual(len(urls),4)  # Historical mock batch only, no new YouTube requests.
            report=self.studio.workflow.report_plan(project,provider_store=self.store,allow_fixture=True)
            self.assertEqual(self.studio.detail('workspace',project)['stage'],'awaiting_plan_approval')
            self.assertEqual(report['research']['manager_decision'],decision)
            self.assertEqual(report['research']['reuse']['source_job'],third)
            self.assertEqual(report['research']['reuse']['final_evaluation'],'not_performed_local_handoff')
            self.assertEqual(report['provenance'],'offline_http_fixture')
            self.assertEqual(report['script']['target_audience'],script['target_audience'])
            self.assertEqual(report['script']['target_duration'],decision['duration_seconds'])
            with self.assertRaises(CompanyError):
                self.company._preflight(self.store.load(self.job))
            self.assertEqual(self.http.call_count,4)
            for path,content in before.items():self.assertEqual(path.read_bytes(),content)
            return
        if getattr(self,'script_topic_tamper',False):
            self.assertEqual(result['reason_code'],'mission_selected_topic_mismatch')
            diag=result['real_ai']['attempts'][-1]['script_validation_diagnostics']
            self.assertEqual(diag['stage'],'writer_selected_topic_validation')
            self.assertEqual(diag['category'],'mission_selected_topic_mismatch')
            self.assertFalse(diag['exact_match'])
            self.assertEqual(diag['normalized_match'],getattr(self,'topic_whitespace_tamper',False))
            self.assertEqual(diag['expected_title_hash'],digest(decision['selected_topic']))
            self.assertEqual(diag['expected_length'],len(decision['selected_topic']))
            self.assertEqual(diag['response_hash'],result['real_ai']['attempts'][-1]['response_hash'])
            self.assertNotEqual(diag['expected_title_hash'],diag['returned_title_hash'])
            for secret_or_text in (self.key,script['target_audience'],script['topic']['title'],'관리자가 선정하지 않은 합성 주제'):
                self.assertNotIn(secret_or_text,json.dumps(diag,ensure_ascii=False))
            self.assertEqual(result['assignments'][1]['versions'],[])
            preserved={p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and self.job in p.name}
            self.assertEqual(self.http.call_count,4)
            with self.assertRaises(CompanyError):
                self.run_job()
            self.assertEqual(self.http.call_count,4)
            for path,data in preserved.items():self.assertEqual(path.read_bytes(),data)
            return
        if getattr(self,'audience_case',None) in ('concrete_mismatch','missing_inference'):
            expected = 'script_audience_mismatch' if self.audience_case=='concrete_mismatch' else 'script_audience_inference_required'
            self.assertEqual(result['reason_code'],expected)
            diag=result['real_ai']['attempts'][-1]['script_validation_diagnostics']
            self.assertEqual(diag['field'],'target_audience')
            self.assertEqual(diag['audience_unspecified'],self.audience_case=='missing_inference')
            if self.audience_case=='missing_inference':
                self.assertEqual(diag['detail_code'],getattr(self,'audience_detail','inference_marker_missing'))
                self.assertTrue({'stage','category','field','audience_unspecified','response_bytes','response_hash','detail_code'}<=set(diag))
                self.assertNotIn(script['target_audience'],json.dumps(diag,ensure_ascii=False))
                self.assertNotIn(self.key,json.dumps(diag))
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
            self.assertIn('사용자 확인 전 AI 제안:' if getattr(self,'audience_variant',False) else 'AI 추론(사용자 미확정):',report['script']['unknowns'][-1])
            self.assertEqual(report['provenance'],'offline_http_fixture')
        self.assertEqual(report['script']['target_duration'],duration)
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

    def finish_budget_fixture(self,project,failed,before,urls,decision,script,youtube_key,send):
        if getattr(self,'free_fixture',False):
            return self.finish_free_fixture(project,failed,before,urls,decision,script,youtube_key,send)
        from video_mission_one import DOUBLE_BUDGET_POLICY, MISSION_ACCOUNT
        fourth=self.job
        reference=self.store.budget_writer_reference(failed)
        self.assertEqual(reference['policy'],DOUBLE_BUDGET_POLICY)
        self.assertEqual(len(reference['previous_attempt_ids']),7)
        for old_guard in (self.store.resume_reference,self.store.successor_reference,self.store.writer_reference):
            with self.assertRaises(CompanyError):old_guard(failed)
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_budget_writer_resume(project)
        self.job=self.studio.workflow.stage_mission_budget_writer_resume(project,owner_confirmed=True)
        fresh=self.store.load(self.job)
        self.assertEqual(fresh['limits']['max_calls'],13)
        self.assertFalse(fresh['real_ai']['consent'])
        self.assertFalse(fresh['real_ai']['attempts'])
        self.assertEqual(fresh['assignments'],failed['assignments'])
        self.assertEqual(fresh['employee_web'],failed['employee_web'])
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_budget_writer_resume(project,owner_confirmed=True)
        with self.assertRaises(CompanyError):self.run_job()
        body=self.store.prepare_mission(self.job,key=self.key,account_project=MISSION_ACCOUNT,quota_note='synthetic attestation',
            youtube_key=youtube_key,youtube_project=MISSION_ACCOUNT,confirm_youtube_policy=True)
        self.assertEqual(body['mission_account']['remaining_requests'],'unknown')
        self.assertEqual(body['mission_account']['approved_max_calls'],13)
        self.assertEqual(body['mission_web']['approved_max_searches'],6)
        self.assertEqual(body['mission_web']['approved_max_videos'],6)
        self.assertEqual((reference['consumed_calls'],reference['new_max_calls'],reference['total_max_calls']),(7,13,20))
        self.assertEqual((reference['consumed_searches'],reference['new_max_searches'],reference['total_max_searches']),(2,6,8))
        self.assertEqual((reference['consumed_videos'],reference['new_max_videos'],reference['total_max_videos']),(2,6,8))
        for section,key in [('mission_budget_writer','consumed_calls'),('mission_budget_writer','new_max_calls'),
                            ('mission_budget_writer','total_max_calls'),('mission_budget_writer','total_max_searches'),
                            ('mission_budget_writer','total_max_videos'),('mission_budget_writer','execution_max_searches'),
                            ('mission_account','approved_max_calls'),('mission_web','approved_max_searches'),
                            ('mission_web','approved_max_videos')]:
            bad=deepcopy(body);bad[section][key]+=1
            with self.assertRaises(CompanyError):self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
        old_body=json.loads(self.store._grant_path(fourth).read_text())['record']['body']
        with self.assertRaises(CompanyError):self.store.approve(self.job,old_body,review_hash=digest(old_body),owner_confirmed=True)
        for mutate in (lambda p:p['mission_budget_writer'].update(selection_hash='tamper'),
                       lambda p:p['quality_inputs'].update(target_segment='tamper'),
                       lambda p:p['employee_web'].update(receipt_hash='tamper'),
                       lambda p:p['limits'].update(max_calls=14)):
            bad=deepcopy(fresh);mutate(bad)
            with self.assertRaises(CompanyError):self.store.check_scope(bad)
        self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
        for env in ({'GEMINI35_MODEL':'other-model'},{'YOUTUBE_DATA_API_KEY':'changed-fixture-key'}):
            with patch.dict('os.environ',env):
                with self.assertRaises(CompanyError):self.run_job()
        with self.assertRaisesRegex(CompanyError,'mission_cached_research_revision_requires_new_approval'):
            self.company._mission_call(self.store.load(self.job),self.company.employee,'execute','research',
                dict(assignment=dict(role='research')))
        self.http.reset_mock(side_effect=False)
        self.http.side_effect=TimeoutError('synthetic timeout') if getattr(self,'budget_timeout',False) else send
        self.new_phases=[]
        result=self.run_job()
        if getattr(self,'budget_timeout',False):
            self.assertEqual(result['status'],'stopped')
            self.assertEqual(len(result['real_ai']['attempts']),1)
            self.assertEqual(self.http.call_count,1)
            with self.assertRaises(CompanyError):self.run_job()
            self.assertEqual(self.http.call_count,1)
        else:
            self.assertEqual(result['status'],'needs_user_review',result.get('reason_code'))
            self.assertEqual(self.http.call_count,4)
            self.assertEqual(self.new_phases,[('execute','writer'),('review','writer'),('execute','editor'),('review','editor')])
            report=self.studio.workflow.report_plan(project,provider_store=self.store,allow_fixture=True)
            self.assertEqual(self.studio.detail('workspace',project)['stage'],'awaiting_plan_approval')
            self.assertEqual(report['research']['manager_decision'],decision)
            self.assertEqual(report['research']['reuse']['source_job'],fourth)
            self.assertEqual(report['provenance'],'offline_http_fixture')
            self.assertEqual(report['script']['target_duration'],25)
            self.assertEqual(report['script']['target_audience'],script['target_audience'])
            # Synthetic boundary states only: 7 historical + 12 new permits a request;
            # 7 + 13 stops before payload validation or transport. No provider evidence is invented.
            boundary=deepcopy(result)
            entry=deepcopy(result['real_ai']['attempts'][0])
            boundary['real_ai']['attempts']=[{**entry,'id':'synthetic-boundary-'+str(i)} for i in range(12)]
            self.company._preflight(boundary)
            boundary['real_ai']['attempts'].append({**entry,'id':'synthetic-boundary-12'})
            with self.assertRaisesRegex(CompanyError,'optional_technical_cap_reached'):
                self.company._request_json(boundary,model=MODEL,base_url=ENDPOINT,body=b'{}',api_key=self.key,
                    timeout=1,transport=lambda *a: self.fail('cap must block transport'),kind='synthetic',task_id=None,goal=boundary['goal'])
            self.assertEqual(self.http.call_count,4)
        self.assertEqual(len(urls),4)  # Original mock observations only.
        for path,content in before.items():self.assertEqual(path.read_bytes(),content)

    def finish_free_fixture(self,project,failed,before,urls,decision,script,youtube_key,send):
        from video_mission_one import FREE_WRITER_POLICY, MISSION_ACCOUNT
        explicit=getattr(self,'free_explicit_cap',None)
        fourth=self.job
        ref=self.store.free_writer_reference(failed,explicit_max_calls=explicit)
        self.assertEqual(ref['policy'],FREE_WRITER_POLICY)
        self.assertEqual(ref['consumed_calls'],7)
        self.assertEqual(ref['new_max_calls'],explicit)
        self.assertIsNone(ref['total_max_calls'])
        self.assertIsNone(ref['total_max_searches'])
        self.assertIsNone(ref['total_max_videos'])
        for invalid in (True,0,-1,'20'):
            with self.assertRaises(CompanyError):self.store.free_writer_reference(failed,explicit_max_calls=invalid)
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_free_writer_resume(project)
        self.job=self.studio.workflow.stage_mission_free_writer_resume(project,owner_confirmed=True,explicit_max_calls=explicit)
        fresh=self.store.load(self.job)
        self.assertEqual(fresh['limits']['max_calls'],explicit)
        self.assertEqual(fresh['assignments'],failed['assignments'])
        self.assertFalse(fresh['real_ai']['attempts'])
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_free_writer_resume(project,owner_confirmed=True)
        with self.assertRaises(CompanyError):self.run_job()
        body=self.store.prepare_mission(self.job,key=self.key,account_project=MISSION_ACCOUNT,quota_note='synthetic free attestation',
            youtube_key=youtube_key,youtube_project=MISSION_ACCOUNT,confirm_youtube_policy=True)
        self.assertEqual(body['mission_account']['approved_max_calls'],explicit)
        self.assertEqual(body['call_policy']['optional_technical_cap'],explicit)
        self.assertEqual(body['mission_account']['remaining_requests'],'unknown')
        self.assertEqual(body['mission_web']['approved_max_searches'],0)
        self.assertEqual(body['mission_web']['approved_max_videos'],0)
        # A new consent cannot silently enlarge an explicit limit or permit paid/changed scope.
        for mutate in (lambda b:b['mission_account'].update(approved_max_calls=20),
                       lambda b:b['mission_account'].update(billing_disabled=False),
                       lambda b:b['mission_account'].update(account_project='other-account'),
                       lambda b:b.update(free_only=False), lambda b:b.update(model='paid-other-model'),
                       lambda b:b['mission_free_writer'].update(total_max_calls=20),
                       lambda b:b['mission_web'].update(approved_max_searches=8)):
            bad=deepcopy(body);mutate(bad)
            with self.assertRaises(CompanyError):self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
        for old in (failed['mission_writer_resume']['previous_job'],fourth):
            old_body=json.loads(self.store._grant_path(old).read_text())['record']['body']
            with self.assertRaises(CompanyError):self.store.approve(self.job,old_body,review_hash=digest(old_body),owner_confirmed=True)
        self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
        # Signed constraints remain immutable after approval, including null versus explicit caps.
        changed=deepcopy(fresh);changed['limits']['max_calls']=99
        with self.assertRaises(CompanyError):self.store.check_scope(changed)
        for env in ({'GEMINI35_MODEL':'other-model'},{'GEMINI35_ENDPOINT':'https://example.invalid/paid'},
                    {'YOUTUBE_DATA_API_KEY':'changed-fixture-key'}):
            with patch.dict('os.environ',env):
                with self.assertRaises(CompanyError):self.run_job()
        with self.assertRaises(CompanyError):
            self.company._mission_call(self.store.load(self.job),self.company.employee,'execute','research',dict(assignment=dict(role='research')))
        self.http.reset_mock(side_effect=False)
        self.new_phases=[]
        error=getattr(self,'free_error',None)
        self.http.side_effect=(HTTPError(ENDPOINT,429 if error=='429' else 402,'synthetic free limit',{},None)
            if error in ('429','quota') else TimeoutError('synthetic uncertain response') if error=='timeout' else send)
        result=self.run_job()
        if getattr(self,'audience_successor_fixture',False):
            self.assertEqual(result['reason_code'],'script_audience_inference_required')
            self.assertEqual(self.http.call_count,1)
            return self.finish_audience_successor_fixture(project,result,before,urls,decision,script,youtube_key,send)
        if error or explicit is not None and explicit<4:
            expected=('provider_rate_limit' if error=='429' else 'provider_quota_or_billing' if error=='quota' else
                      'free_request_failed' if error=='timeout' else 'script_provenance_mismatch' if error else 'optional_technical_cap_reached')
            self.assertEqual(result.get('reason_code'),expected)
            count=explicit if not error else 1
            self.assertEqual(len(result['real_ai']['attempts']),count)
            self.assertEqual(self.http.call_count,count)
            stopped={p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and self.job in p.name}
            with self.assertRaises(CompanyError):self.run_job()
            self.assertEqual(self.http.call_count,count)
            for path,data in stopped.items():self.assertEqual(path.read_bytes(),data)
        else:
            self.assertEqual(result['status'],'needs_user_review',result.get('reason_code'))
            self.assertEqual(self.http.call_count,4)
            report=self.studio.workflow.report_plan(project,provider_store=self.store,allow_fixture=True)
            self.assertEqual(self.studio.detail('workspace',project)['stage'],'awaiting_plan_approval')
            self.assertEqual(report['research']['manager_decision'],decision)
            self.assertEqual(report['research']['reuse']['source_job'],fourth)
            self.assertEqual(report['script']['target_duration'],25)
            self.assertEqual(report['script']['target_audience'],script['target_audience'])
            self.assertEqual(report['provenance'],'offline_http_fixture')
            self.assertEqual(report['research']['reuse']['final_evaluation'],'not_performed_local_handoff')
            # Only memory fixtures cross old 10/20 counts; no evidence or real usage is created.
            boundary=deepcopy(result);entry=deepcopy(result['real_ai']['attempts'][0])
            for count in (10,20,25):
                boundary['real_ai']['attempts']=[{**entry,'id':'counter-fixture-'+str(i)} for i in range(count)]
                self.company._preflight(boundary)
            # A reserved/unknown operation still blocks even with no counter cap.
            boundary['real_ai']['attempts'][-1]['status']='reserved'
            with self.assertRaises(CompanyError):self.company._preflight(boundary)
            # Provider remaining=0 is authoritative regardless of the internal counter.
            boundary=deepcopy(result);boundary['real_ai']['attempts'][-1]['rate_limits']={'x-ratelimit-remaining-requests':0}
            with self.assertRaisesRegex(CompanyError,'provider_rate_limit'):self.company._preflight(boundary)
            # Same completed operation identity cannot be sent again.
            duplicate=deepcopy(result);duplicate['active_operation']=None
            self.company.current=dict(phase='review',context_hash=result['real_ai']['attempts'][-1]['context_hash'])
            from autonomous_live import CONTRACTS
            payload=self.company._prepare_payload(dict(model=MODEL,max_tokens=4096,messages=[
                dict(role='system',content='synthetic duplicate guard'),dict(role='user',content=json.dumps(
                    dict(phase='review',output_contract=CONTRACTS['review'],data={})))]))
            with self.assertRaisesRegex(CompanyError,'duplicate_operation'):
                self.company._request_json(duplicate,model=MODEL,base_url=ENDPOINT,body=json.dumps(payload).encode(),
                    api_key=self.key,timeout=1,transport=lambda *a:self.fail('duplicate must block transport'),
                    kind='synthetic',task_id=result['assignments'][2]['id'],goal=result['goal'])
            self.assertEqual(self.http.call_count,4)
        self.assertEqual(len(urls),4)  # Reused observations only: no new web request.
        for path,data in before.items():self.assertEqual(path.read_bytes(),data)

    def finish_audience_successor_fixture(self,project,failed,before,urls,decision,script,youtube_key,send):
        from video_mission_one import AUDIENCE_SUCCESSOR_POLICY, MISSION_ACCOUNT
        fifth=self.job
        before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and fifth in p.name})
        reference=self.store.audience_successor_reference(failed)
        self.assertEqual(reference['consumed_calls'],8)
        self.assertEqual(len(reference['previous_attempt_ids']),8)
        self.assertEqual(reference['selection_hash'],digest(decision))
        for guard in (self.store.resume_reference,self.store.successor_reference,self.store.writer_reference,
                      self.store.budget_writer_reference,self.store.free_writer_reference):
            with self.assertRaises(CompanyError):guard(failed)
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_audience_successor(project)
        # Another synthetic cutroom cannot claim this execution even by copying its job pointer.
        other=self.studio.create(dict(goal=GAME_GOAL,audience='',language='한국어',platform='YouTube Shorts',duration=None,
            notes='',key='00000000-0000-4000-8000-000000000099'))['id']
        wrong=self.studio.workflow.store.load(other)
        wrong['representative'].update(stage='research_planning',mission_one_job=fifth)
        self.studio.workflow.store.save(wrong)
        with self.assertRaisesRegex(CompanyError,'mission_scope_mismatch'):
            self.studio.workflow.stage_mission_audience_successor(other,owner_confirmed=True)
        self.job=self.studio.workflow.stage_mission_audience_successor(project,owner_confirmed=True)
        fresh=self.store.load(self.job)
        self.assertIsNone(fresh['limits']['max_calls'])
        self.assertFalse(fresh['real_ai']['attempts'])
        self.assertFalse(fresh['real_ai']['consent'])
        self.assertEqual(fresh['assignments'],failed['assignments'])
        self.assertEqual(fresh['employee_web'],failed['employee_web'])
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_audience_successor(project,owner_confirmed=True)
        with self.assertRaises(CompanyError):self.run_job()
        body=self.store.prepare_mission(self.job,key=self.key,account_project=MISSION_ACCOUNT,quota_note='synthetic attestation',
            youtube_key=youtube_key,youtube_project=MISSION_ACCOUNT,confirm_youtube_policy=True)
        self.assertEqual(body['mission_audience_successor']['policy'],AUDIENCE_SUCCESSOR_POLICY)
        self.assertEqual(body['mission_audience_successor']['consumed_calls'],8)
        self.assertIsNone(body['mission_account']['approved_max_calls'])
        self.assertEqual(body['mission_web']['approved_max_searches'],0)
        old_body=json.loads(self.store._grant_path(fifth).read_text())['record']['body']
        with self.assertRaises(CompanyError):self.store.approve(self.job,old_body,review_hash=digest(old_body),owner_confirmed=True)
        for mutate in (lambda b:b['mission_audience_successor'].update(consumed_calls=0),
                       lambda b:b['mission_audience_successor'].update(selection_hash='tampered'),
                       lambda b:b['mission_web'].update(approved_max_searches=1),
                       lambda b:b['mission_account'].update(account_project='other-account')):
            bad=deepcopy(body);mutate(bad)
            with self.assertRaises(CompanyError):self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
        bad=deepcopy(fresh);bad['quality_inputs']['answers']['representative_project']=other
        with self.assertRaises(CompanyError):self.store.check_scope(bad)
        self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
        self.http.reset_mock(side_effect=False);self.http.side_effect=send;self.new_phases=[]
        result=self.run_job()
        if getattr(self,'topic_successor_fixture',False):
            self.assertEqual(result['reason_code'],'mission_selected_topic_mismatch')
            self.assertEqual(self.http.call_count,1)
            return self.finish_topic_successor_fixture(project,result,before,urls,decision,script,youtube_key,send)
        self.assertEqual(result['status'],'needs_user_review',result.get('reason_code'))
        self.assertEqual(self.http.call_count,4)
        self.assertEqual(self.new_phases,[('execute','writer'),('review','writer'),('execute','editor'),('review','editor')])
        report=self.studio.workflow.report_plan(project,provider_store=self.store,allow_fixture=True)
        self.assertEqual(self.studio.detail('workspace',project)['stage'],'awaiting_plan_approval')
        self.assertEqual(report['research']['manager_decision'],decision)
        self.assertEqual(report['research']['reuse']['source_job'],fifth)
        self.assertEqual(report['script']['target_duration'],25)
        self.assertEqual(report['script']['target_audience'],script['target_audience'])
        self.assertEqual(report['provenance'],'offline_http_fixture')
        self.assertEqual(report['research']['reuse']['final_evaluation'],'not_performed_local_handoff')
        self.assertEqual(len(urls),4)
        for path,data in before.items():self.assertEqual(path.read_bytes(),data)

    def finish_topic_successor_fixture(self,project,failed,before,urls,decision,script,youtube_key,send):
        from video_mission_one import TOPIC_SUCCESSOR_POLICY, MISSION_ACCOUNT
        sixth=self.job
        before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and sixth in p.name})
        reference=self.store.topic_successor_reference(failed)
        self.assertEqual(reference['consumed_calls'],9)
        self.assertEqual(len(reference['previous_attempt_ids']),9)
        for invalid in (lambda p:p.update(reason_code='other'),lambda p:p.update(active_operation=None),
                        lambda p:p['mission_audience_successor'].update(selection_hash='tampered')):
            bad=deepcopy(failed);invalid(bad)
            with self.assertRaises(CompanyError):self.store.topic_successor_reference(bad)
        with self.assertRaises(CompanyError):self.store.audience_successor_reference(failed)
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_topic_successor(project)
        self.job=self.studio.workflow.stage_mission_topic_successor(project,owner_confirmed=True)
        fresh=self.store.load(self.job)
        self.assertIsNone(fresh['limits']['max_calls'])
        self.assertEqual(fresh['assignments'],failed['assignments'])
        self.assertFalse(fresh['real_ai']['attempts'])
        self.assertFalse(fresh['real_ai']['consent'])
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_topic_successor(project,owner_confirmed=True)
        with self.assertRaises(CompanyError):self.run_job()
        body=self.store.prepare_mission(self.job,key=self.key,account_project=MISSION_ACCOUNT,quota_note='synthetic attestation',
            youtube_key=youtube_key,youtube_project=MISSION_ACCOUNT,confirm_youtube_policy=True)
        self.assertEqual(body['mission_topic_successor']['policy'],TOPIC_SUCCESSOR_POLICY)
        self.assertIsNone(body['mission_account']['approved_max_calls'])
        self.assertEqual(body['mission_web']['approved_max_searches'],0)
        old_body=json.loads(self.store._grant_path(sixth).read_text())['record']['body']
        with self.assertRaises(CompanyError):self.store.approve(self.job,old_body,review_hash=digest(old_body),owner_confirmed=True)
        for mutate in (lambda b:b['mission_topic_successor'].update(selection_hash='tampered'),
                       lambda b:b['mission_account'].update(account_project='other-account')):
            bad=deepcopy(body);mutate(bad)
            with self.assertRaises(CompanyError):self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
        self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
        with patch.dict('os.environ',YOUTUBE_DATA_API_KEY='changed-key'):
            with self.assertRaises(CompanyError):self.run_job()
        self.http.reset_mock(side_effect=False);self.http.side_effect=send;self.new_phases=[]
        result=self.run_job()
        if getattr(self,'unified_successor_fixture',False):
            self.assertEqual(result['reason_code'],'invalid_script_shot')
            self.assertEqual(self.http.call_count,1)
            return self.finish_unified_successor_fixture(project,result,before,urls,decision,script,youtube_key,send)
        self.assertEqual(result['status'],'needs_user_review',result.get('reason_code'))
        self.assertEqual(self.http.call_count,4)
        self.assertEqual(self.new_phases,[('execute','writer'),('review','writer'),('execute','editor'),('review','editor')])
        report=self.studio.workflow.report_plan(project,provider_store=self.store,allow_fixture=True)
        self.assertEqual(self.studio.detail('workspace',project)['stage'],'awaiting_plan_approval')
        self.assertEqual(report['research']['manager_decision'],decision)
        self.assertEqual(report['research']['reuse']['source_job'],sixth)
        self.assertEqual(report['script']['target_duration'],25)
        self.assertEqual(report['provenance'],'offline_http_fixture')
        self.assertEqual(len(urls),4)
        for path,data in before.items():self.assertEqual(path.read_bytes(),data)

    def finish_unified_successor_fixture(self,project,failed,before,urls,decision,script,youtube_key,send):
        if getattr(self,'audience_upgrade_fixture',False):
            return self.finish_audience_upgrade_fixture(project,failed,before,urls,decision,script,youtube_key,send)
        from video_mission_one import UNIFIED_SUCCESSOR_POLICY, MISSION_ACCOUNT, UNIFIED_PURPOSE
        from script_quality import writer_contract
        seventh=self.job
        before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and seventh in p.name})
        reference=self.store.unified_successor_reference(failed)
        self.assertEqual(reference['consumed_calls'],10)
        self.assertEqual(len(reference['previous_attempt_ids']),10)
        self.assertEqual(reference['writer_contract_hash'],digest(writer_contract('미정',25,MODEL,decision['selected_topic'])))
        for mutate in (lambda p:p.update(active_operation=None),lambda p:p['real_ai']['attempts'][0].update(status='reserved'),
                       lambda p:p['mission_topic_successor'].update(receipt_hash='tampered')):
            bad=deepcopy(failed);mutate(bad)
            with self.assertRaises(CompanyError):self.store.unified_successor_reference(bad)
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_validated_successor(project)
        self.job=self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True)
        fresh=self.store.load(self.job)
        self.assertIsNone(fresh['limits']['max_calls'])
        self.assertFalse(fresh['real_ai']['consent'])
        self.assertFalse(fresh['real_ai']['attempts'])
        self.assertFalse(fresh['sessions'])
        self.assertEqual(fresh['assignments'],failed['assignments'])
        self.assertEqual(fresh['employee_web'],failed['employee_web'])
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True)
        with self.assertRaises(CompanyError):self.run_job()
        body=self.store.prepare_mission(self.job,key=self.key,account_project=MISSION_ACCOUNT,quota_note='synthetic free attestation',
            youtube_key=youtube_key,youtube_project=MISSION_ACCOUNT,confirm_youtube_policy=True)
        self.assertEqual(body['mission_unified_successor']['policy'],UNIFIED_SUCCESSOR_POLICY)
        self.assertIsNone(body['mission_account']['approved_max_calls'])
        self.assertEqual(body['mission_web']['approved_max_searches'],0)
        old_body=json.loads(self.store._grant_path(seventh).read_text())['record']['body']
        with self.assertRaises(CompanyError):self.store.approve(self.job,old_body,review_hash=digest(old_body),owner_confirmed=True)
        for mutate in (lambda b:b['mission_unified_successor'].update(writer_contract_hash='0'*64),
                       lambda b:b['mission_unified_successor'].update(consumed_calls=0),
                       lambda b:b['mission_account'].update(account_project='other-account')):
            bad=deepcopy(body);mutate(bad)
            with self.assertRaises(CompanyError):self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
        self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
        with patch.dict('os.environ',YOUTUBE_DATA_API_KEY='changed-key'):
            with self.assertRaises(CompanyError):self.run_job()
        self.http.reset_mock(side_effect=False)
        self.http.side_effect=send;self.new_phases=[]
        result=self.run_job()
        self.assertEqual(result['status'],'needs_user_review',result.get('reason_code'))
        self.assertEqual(self.http.call_count,4)
        self.assertEqual(self.new_phases,[('execute','writer'),('review','writer'),('execute','editor'),('review','editor')])
        report=self.studio.workflow.report_plan(project,provider_store=self.store,allow_fixture=True)
        self.assertEqual(self.studio.detail('workspace',project)['stage'],'awaiting_plan_approval')
        self.assertEqual(report['research']['manager_decision'],decision)
        self.assertEqual(report['research']['reuse']['source_job'],seventh)
        self.assertEqual(report['script']['target_duration'],25)
        self.assertEqual(report['provenance'],'offline_http_fixture')
        self.assertEqual(len(urls),4)
        for path,data in before.items():self.assertEqual(path.read_bytes(),data)

    def finish_audience_upgrade_fixture(self,project,failed,before,urls,decision,script,youtube_key,send):
        from video_mission_one import MISSION_ACCOUNT
        from script_quality import writer_contract
        seventh=self.job
        before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and seventh in p.name})
        with patch('video_mission_one.writer_contract',side_effect=lambda *args:writer_contract(*args,version=1)):
            self.writer_contract_version=1
            self.job=self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True)
            body=self.store.prepare_mission(self.job,key=self.key,account_project=MISSION_ACCOUNT,quota_note='synthetic historical v1',
                youtube_key=youtube_key,youtube_project=MISSION_ACCOUNT,confirm_youtube_policy=True)
            self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
            self.http.reset_mock(side_effect=False)
            def unspecified(request,timeout):
                response=send(request,timeout)
                envelope=json.loads(response.getvalue())
                result=json.loads(envelope['candidates'][0]['content']['parts'][0]['text'])
                result['result']['content']['target_audience']='미정'
                envelope['candidates'][0]['content']['parts'][0]['text']=json.dumps(result,ensure_ascii=False)
                return FixtureResponse(json.dumps(envelope).encode())
            self.http.side_effect=unspecified
            old_failed=self.run_job()
            self.assertEqual(old_failed['reason_code'],'script_audience_inference_required')
            self.assertEqual(old_failed['real_ai']['attempts'][-1]['script_validation_diagnostics']['detail_code'],'literal_unspecified_audience')
            self.assertEqual(self.http.call_count,1)
            with self.assertRaises(CompanyError):self.run_job()
            with self.assertRaisesRegex(CompanyError,'mission_unified_unchanged_request'):
                self.store.unified_successor_reference(old_failed,new_purpose='renaming alone cannot replay')
        eighth=self.job
        before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and eighth in p.name})
        self.writer_contract_version=2
        reference=self.store.unified_successor_reference(old_failed)
        self.assertEqual(reference['consumed_calls'],11)
        self.assertNotEqual(reference['writer_contract_hash'],old_failed['mission_unified_successor']['writer_contract_hash'])
        self.assertEqual(reference['writer_contract_hash'],digest(writer_contract('미정',25,MODEL,decision['selected_topic'])))
        self.job=self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True)
        with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True)
        body=self.store.prepare_mission(self.job,key=self.key,account_project=MISSION_ACCOUNT,quota_note='synthetic v2 approval',
            youtube_key=youtube_key,youtube_project=MISSION_ACCOUNT,confirm_youtube_policy=True)
        bad=deepcopy(body);bad['mission_unified_successor']['writer_contract_hash']=old_failed['mission_unified_successor']['writer_contract_hash']
        with self.assertRaises(CompanyError):self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
        self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
        if getattr(self,'dns_permission_fixture',False):
            import socket
            from urllib.error import URLError
            from video_mission_one import DNS_PERMISSION_PURPOSE
            self.http.reset_mock(side_effect=False)
            self.http.side_effect=URLError(socket.gaierror(-3,'synthetic DNS failure'))
            dns_failed=self.run_job()
            self.assertEqual(dns_failed['reason_code'],'free_request_failed')
            self.assertEqual(self.http.call_count,1)
            ninth=self.job
            before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and ninth in p.name})
            with self.assertRaises(CompanyError):self.store.unified_successor_reference(dns_failed)
            reference=self.store.unified_successor_reference(dns_failed,new_purpose=DNS_PERMISSION_PURPOSE)
            self.assertEqual(reference['consumed_calls'],12)
            self.assertEqual(len(reference['previous_attempt_ids']),12)
            for mutate in (lambda j:j['real_ai']['attempts'][0].update(http_status=200),
                           lambda j:j['real_ai']['attempts'][0].update(provider_error_diagnostics=dict(category='connect_timeout',stage='transport_open'))):
                bad=deepcopy(dns_failed);mutate(bad)
                with self.assertRaises(CompanyError):self.store.unified_successor_reference(bad,new_purpose=DNS_PERMISSION_PURPOSE)
            self.job=self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True,new_purpose=DNS_PERMISSION_PURPOSE)
            fresh=self.store.load(self.job)
            self.assertFalse(fresh['real_ai']['attempts']);self.assertFalse(fresh['real_ai']['consent']);self.assertFalse(fresh['sessions'])
            with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True,new_purpose=DNS_PERMISSION_PURPOSE)
            body=self.store.prepare_mission(self.job,key=self.key,account_project=MISSION_ACCOUNT,quota_note='synthetic network permission',
                youtube_key=youtube_key,youtube_project=MISSION_ACCOUNT,confirm_youtube_policy=True)
            self.assertEqual(body['mission_web']['approved_max_searches'],0)
            for mutate in (lambda b:b.update(model='other'),lambda b:b['mission_account'].update(account_project='other'),
                           lambda b:b['mission_unified_successor'].update(writer_contract_hash='0'*64)):
                bad=deepcopy(body);mutate(bad)
                with self.assertRaises(CompanyError):self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
            self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
        if getattr(self,'partial_revision_fixture',False):
            from video_mission_one import PARTIAL_REVISION_PURPOSE
            def partial_send(request,timeout):
                current=self.store.load(self.job);attempt=current['real_ai']['attempts'][-1]
                if len(current['real_ai']['attempts'])==3:
                    raise HTTPError(ENDPOINT,503,'synthetic unavailable',{},None)
                response=send(request,timeout)
                if attempt['phase']=='review':
                    envelope=json.loads(response.getvalue())
                    value=json.loads(envelope['candidates'][0]['content']['parts'][0]['text'])
                    value['result'].update(action='revise',feedback='missing_demo/caption_width/dense_narration: compress preserved draft')
                    envelope['candidates'][0]['content']['parts'][0]['text']=json.dumps(value,ensure_ascii=False)
                    return FixtureResponse(json.dumps(envelope).encode())
                return response
            self.http.reset_mock(side_effect=False);self.http.side_effect=partial_send
            partial=self.run_job()
            self.assertEqual(partial['status'],'paused');self.assertEqual(partial['reason_code'],'provider_unavailable')
            self.assertEqual(self.http.call_count,3)
            old_id=self.job
            before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and old_id in p.name})
            ref=self.store.unified_successor_reference(partial,new_purpose=PARTIAL_REVISION_PURPOSE)
            self.assertEqual(ref['consumed_calls'],15)
            self.assertEqual(ref['writer_v1_hash'],digest(partial['assignments'][1]['versions'][0]))
            for mutate in (lambda j:j['assignments'][1]['reviews'][0].update(feedback='tampered'),
                           lambda j:j['real_ai']['attempts'][-1].update(http_status=429)):
                bad=deepcopy(partial);mutate(bad)
                with self.assertRaises(CompanyError):self.store.unified_successor_reference(bad,new_purpose=PARTIAL_REVISION_PURPOSE)
            self.job=self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True,new_purpose=PARTIAL_REVISION_PURPOSE)
            self.assertEqual(self.store.load(self.job)['assignments'],partial['assignments'])
            with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True,new_purpose=PARTIAL_REVISION_PURPOSE)
            body=self.store.prepare_mission(self.job,key=self.key,account_project=MISSION_ACCOUNT,quota_note='synthetic partial continuation',
                youtube_key=youtube_key,youtube_project=MISSION_ACCOUNT,confirm_youtube_policy=True)
            old_body=json.loads(self.store._grant_path(old_id).read_text())['record']['body']
            with self.assertRaises(CompanyError):self.store.approve(self.job,old_body,review_hash=digest(old_body),owner_confirmed=True)
            for mutate in (lambda b:b.update(model='other'),lambda b:b['mission_account'].update(account_project='other'),
                           lambda b:b['mission_unified_successor'].update(writer_v1_hash='0'*64)):
                bad=deepcopy(body);mutate(bad)
                with self.assertRaises(CompanyError):self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
            self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
            with patch.dict('os.environ',GEMINI_API_KEY='different-key'):
                # Config is bound at construction; test the actual transport binding.
                with patch.object(self.company,'config',Gemini35Config('different-key')):
                    with self.assertRaises(CompanyError):self.run_job()
            original_send=send
            def send(request,timeout):
                message=json.loads(json.loads(request.data)['contents'][0]['parts'][0]['text'])
                from script_quality import CAPTION_WIDTH_INSTRUCTIONS
                wire=json.loads(request.data)
                self.assertIn(CAPTION_WIDTH_INSTRUCTIONS,wire['systemInstruction']['parts'][0]['text'])
                self.assertIn('W 또는 F',CAPTION_WIDTH_INSTRUCTIONS)
                self.assertIn('6+1+3=10폭',CAPTION_WIDTH_INSTRUCTIONS)
                if not self.store.load(self.job)['assignments'][1]['versions'][1:]:
                    context=message['data']
                    self.assertEqual(context['revision_feedback'],partial['assignments'][1]['reviews'][0]['feedback'])
                    self.assertEqual(context['version_history'],partial['assignments'][1]['versions'])
                response=original_send(request,timeout)
                if message['phase']=='execute' and message['data']['assignment']['role']=='writer':
                    envelope=json.loads(response.getvalue())
                    value=json.loads(envelope['candidates'][0]['content']['parts'][0]['text'])
                    value['result']['content']['narrative_beats'][0]['caption']='수정 예시'
                    if getattr(self,'caption_revision_fixture',False):
                        value['result']['content']['narrative_beats'][1]['caption']='가'*19+'A'
                    envelope['candidates'][0]['content']['parts'][0]['text']=json.dumps(value,ensure_ascii=False)
                    return FixtureResponse(json.dumps(envelope).encode())
                if (getattr(self,'caption_revision_fixture',False) and message['phase']=='review'
                        and message['data']['assignment']['role']=='writer'):
                    # Reproduce the real model's invalid accept, then let the server reject it.
                    envelope=json.loads(response.getvalue())
                    value=json.loads(envelope['candidates'][0]['content']['parts'][0]['text'])
                    value['result'].update(action='accept',feedback='')
                    for check in value['result']['checks']:check['status']='met'
                    envelope['candidates'][0]['content']['parts'][0]['text']=json.dumps(value,ensure_ascii=False)
                    return FixtureResponse(json.dumps(envelope).encode())
                return response
        self.http.reset_mock(side_effect=False);self.http.side_effect=send;self.new_phases=[]
        result=self.run_job()
        if getattr(self,'caption_revision_fixture',False):
            from video_mission_one import CAPTION_REVISION_PURPOSE
            self.assertEqual(result['reason_code'],'known_script_defects')
            blocked=result;old_id=self.job
            from production_video import units
            self.assertEqual(units(json.loads(blocked['assignments'][1]['versions'][-1]['content'])['narrative_beats'][1]['caption']),39)
            self.assertEqual(blocked['assignments'][1]['revisions'],1)
            self.assertEqual(len(blocked['assignments'][1]['versions']),2)
            self.assertEqual(len(blocked['assignments'][1]['reviews']),2)
            before.update({p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file() and old_id in p.name})
            ref=self.store.unified_successor_reference(blocked,new_purpose=CAPTION_REVISION_PURPOSE)
            self.assertEqual(ref['consumed_calls'],17)
            self.assertEqual(len(ref['previous_attempt_ids']),17)
            self.assertEqual(ref['writer_v2_hash'],digest(blocked['assignments'][1]['versions'][-1]))
            for mutate in (lambda j:j['assignments'][1].update(revisions=0),
                           lambda j:j['assignments'][1]['reviews'][-1].update(action='revise')):
                bad=deepcopy(blocked);mutate(bad)
                with self.assertRaises(CompanyError):self.store.unified_successor_reference(bad,new_purpose=CAPTION_REVISION_PURPOSE)
            self.job=self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True,new_purpose=CAPTION_REVISION_PURPOSE)
            fresh=self.store.load(self.job)
            self.assertEqual(fresh['assignments'][1]['versions'],blocked['assignments'][1]['versions'])
            self.assertEqual(fresh['assignments'][1]['reviews'],blocked['assignments'][1]['reviews'])
            self.assertEqual(fresh['assignments'][1]['revisions'],2)
            self.assertEqual(fresh['limits']['max_revisions_per_task'],2)
            with self.assertRaises(CompanyError):self.studio.workflow.stage_mission_validated_successor(project,owner_confirmed=True,new_purpose=CAPTION_REVISION_PURPOSE)
            body=self.store.prepare_mission(self.job,key=self.key,account_project=MISSION_ACCOUNT,quota_note='synthetic caption revision',
                youtube_key=youtube_key,youtube_project=MISSION_ACCOUNT,confirm_youtube_policy=True)
            for mutate in (lambda b:b.update(model='other'),lambda b:b['mission_account'].update(account_project='other'),
                           lambda b:b['mission_unified_successor'].update(new_signed_revisions=2),
                           lambda b:b['mission_unified_successor'].update(writer_v2_hash='0'*64)):
                bad=deepcopy(body);mutate(bad)
                with self.assertRaises(CompanyError):self.store.approve(self.job,bad,review_hash=digest(bad),owner_confirmed=True)
            self.store.approve(self.job,body,review_hash=digest(body),owner_confirmed=True)
            with patch.object(self.company,'config',Gemini35Config('different-key')):
                with self.assertRaises(CompanyError):self.run_job()
            def caption_send(request,timeout):
                wire=json.loads(request.data);message=json.loads(wire['contents'][0]['parts'][0]['text'])
                if message['phase']=='execute' and message['data']['assignment']['role']=='writer':
                    context=message['data']
                    self.assertEqual(context['version_history'],blocked['assignments'][1]['versions'])
                    self.assertIn('caption_width',context['revision_feedback'])
                    self.assertIn('W 또는 F',wire['systemInstruction']['parts'][0]['text'])
                    value=json.loads(context['version_history'][-1]['content'])
                    value['narrative_beats'][1]['caption']='자막 수정'
                    return FixtureResponse(json.dumps(dict(candidates=[dict(content=dict(role='model',parts=[dict(text=json.dumps(
                        dict(result=dict(content=value,evidence='offline fixture',uncertainty='unassessed')),ensure_ascii=False))]),
                        finishReason='STOP')],usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=30,totalTokenCount=50))).encode())
                return original_send(request,timeout)
            self.http.reset_mock(side_effect=False);self.http.side_effect=caption_send
            result=self.run_job()
        self.assertEqual(result['status'],'needs_user_review',result.get('reason_code'))
        self.assertEqual(self.http.call_count,4)
        if getattr(self,'local_handoff_fixture',False):
            import runpy
            from representative_workflow import RepresentativeVideoWorkflow
            from video_mission_one import checked_result
            module=runpy.run_module('video_mission_one',run_name='mission_cli_fixture')
            foreign=module['MissionOneStore'](self.store.root)
            self.assertIsNot(type(foreign),MissionOneStore)
            with self.assertRaisesRegex(CompanyError,'mission_scope_mismatch'):
                self.studio.workflow.report_plan(project,provider_store=foreign,allow_fixture=True)
            original=RepresentativeVideoWorkflow.report_plan
            def offline_report(workflow,pid,**kwargs):
                self.assertIs(type(kwargs['provider_store']),MissionOneStore)
                return original(workflow,pid,allow_fixture=True,**kwargs)
            grant_path=self.store._grant_path(self.job);saved=grant_path.read_bytes()
            bad=json.loads(saved);bad['signature']='0'*64;grant_path.write_text(json.dumps(bad))
            with self.assertRaises(CompanyError):
                self.studio.workflow.report_plan(project,provider_store=self.store,allow_fixture=True)
            grant_path.write_bytes(saved)
            bad=deepcopy(result);bad['assignments'][1]['state']='awaiting_ai_review'
            with self.assertRaises(CompanyError):checked_result(bad,allow_fixture=True)
            bad=deepcopy(result);bad['quality_inputs']['answers']['representative_project']='other-mission'
            with self.assertRaises(CompanyError):self.store.check_scope(bad)
            with patch('sys.argv',['video_mission_one','--root',str(self.store.root.parent),'run',project]),                  patch.object(RepresentativeVideoWorkflow,'report_plan',offline_report),                  patch.object(module['MissionOneCompany'],'run',side_effect=AssertionError('production rerun forbidden')):
                module['main']()
            self.assertEqual(len(self.studio.workflow.store.load(project)['representative']['plan_versions']),1)
        report=self.studio.workflow.report_plan(project,provider_store=self.store,allow_fixture=True)
        self.assertEqual(self.studio.detail('workspace',project)['stage'],'awaiting_plan_approval')
        self.assertEqual(report['script']['target_duration'],25)
        self.assertEqual(report['script']['target_audience'],script['target_audience'])
        self.assertEqual(self.store.load(self.job)['quality_inputs']['target_segment'],'미정')
        self.assertEqual(report['provenance'],'offline_http_fixture')
        self.assertEqual(report['research']['manager_decision'],decision)
        self.assertEqual(len(urls),4)
        if getattr(self,'representative_rework_fixture',False):
            self.finish_representative_rework_fixture(project)
        for path,data in before.items():self.assertEqual(path.read_bytes(),data)

    def finish_representative_rework_fixture(self,project):
        from representative_rework import prepare,ReworkStore,ReworkCompany,handoff
        from script_quality import script_editor_handoff
        original=self.studio.workflow.store.load(project)['representative']['plan_versions'][-1]
        original_bytes={p:p.read_bytes() for p in self.store.root.iterdir() if p.is_file()}
        feedback='게임 자체의 재미있는 한 장면을 다루세요. 제작 방법 설명은 원 목표와 다릅니다.'
        self.studio.workflow.decide(project,'plan',version=1,sha256=original['sha256'],action='request_revision',feedback=feedback)
        self.studio.action('workspace',project,'rework-prepare',dict(account_project='gen-lang-client-0938732315',confirm_free_account=True))
        self.assertEqual(self.studio.detail('workspace',project)['rework']['status'],'pending')
        state=self.studio.workflow.store.load(project)['representative']['rework']
        provider=ReworkStore(self.store.root.parent/'representative_rework');pid=state['job']
        self.assertFalse(provider.load(pid)['real_ai']['attempts'])
        prepare(self.studio.workflow,project,self.key,'gen-lang-client-0938732315')
        self.assertEqual(self.studio.workflow.store.load(project)['representative']['rework']['job'],pid)
        class OfflineRework(ReworkCompany):source='offline_http_fixture'
        company=OfflineRework(provider,LiveManagerProvider('fixture-manager'),LiveEmployeeProvider('fixture-staff'),Gemini35Config(self.key))
        def run():return company.run(pid,expected_state_hash=provider.load(pid)['storage_hash'])
        with self.assertRaises(CompanyError):run()
        body=state['proposal']
        if getattr(self,'strict_plan_fixture',False):
            old_contract=deepcopy(body);old_contract['rework_scope']['plan_contract_hash']='old-plan-contract'
            with self.assertRaisesRegex(CompanyError,'rework_plan_contract_changed'):
                provider.approve(pid,old_contract,review_hash=digest(old_contract),owner_confirmed=True)
        if (getattr(self,'new_attempt_fixture',False) and not getattr(self,'unavailable_fixture',False)
                and not getattr(self,'handoff_failure_fixture',False)):
            # Historical fixture uses the old signed plan contract, not the new one.
            body['rework_scope'].pop('plan_contract_hash')
            project_state=self.studio.workflow.store.load(project)
            project_state['representative']['rework']['proposal']=deepcopy(body)
            self.studio.workflow.store.save(project_state)

        bad=deepcopy(body);bad['rework_scope']['reference']['plan_hash']='0'*64
        with self.assertRaises(CompanyError):provider.approve(pid,bad,review_hash=digest(bad),owner_confirmed=True)
        self.studio.action('workspace',project,'rework-consent',dict(review_hash=digest(body),confirm_free_account=True,confirm_data_policy=True))
        if getattr(self,'strict_plan_fixture',False):
            grant=deepcopy(provider.grant(provider.load(pid)))
            grant['body']['rework_scope']['plan_contract_hash']='old-plan-contract'
            with patch.object(provider,'grant',return_value=grant),self.assertRaisesRegex(CompanyError,'rework_new_plan_consent_required'):
                company._quality_transport_allowed(provider.load(pid))
        if getattr(self,'consent_size_fixture',False):
            from autonomous_live import LiveStore
            self.assertEqual(LiveStore.max_consent_bytes,16384)
            self.assertEqual(MissionOneStore.max_consent_bytes,16384)
            path=provider._grant_path(pid);saved=path.read_bytes()
            # Legal serialization padding leaves the signed record untouched.
            target=max(28841,len(saved)+1)
            self.assertLess(target,65536)
            padded=saved+b' '*(target-len(saved));path.write_bytes(padded)
            record=provider.grant(provider.load(pid))
            self.assertEqual(record['id'],provider.load(pid)['real_ai']['consent']['operating_grant_id'])
            generic=LiveStore(self.store.root.parent/'generic-consent-test')
            generic.root.mkdir(exist_ok=True)
            generic._grant_path(pid).write_bytes(padded)
            with self.assertRaisesRegex(CompanyError,'operating_consent_required'):generic.grant(provider.load(pid))
            for changed in (dict(json.loads(saved),signature='0'*64),):
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(CompanyError,'invalid_consent_signature'):provider.grant(provider.load(pid))
            changed=json.loads(saved);changed['record']['body']['rework_scope']['account_project']='tampered'
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(CompanyError,'invalid_consent_signature'):provider.grant(provider.load(pid))
            path.write_bytes(saved+b' '*(65535-len(saved)));provider.grant(provider.load(pid))
            path.write_bytes(saved+b' '*(65536-len(saved)))
            with self.assertRaisesRegex(CompanyError,'operating_consent_required'):provider.grant(provider.load(pid))
            path.write_bytes(padded)
        if getattr(self,'disabled_recovery_fixture',False):
            saved_job=provider.path(pid).read_bytes();saved_grant=provider._grant_path(pid).read_bytes()
            with patch.dict('os.environ',GEMINI35_AUTONOMOUS_FREE_ENABLED='0'):
                with self.assertRaisesRegex(CompanyError,'gemini_execution_disabled'):run()
                self.assertEqual(provider.path(pid).read_bytes(),saved_job)
                # Reproduce the legacy worker's UI failure record without altering the provider ledger.
                with self.studio.workflow.store.lock(project):
                    actual=self.studio.workflow.store.load(project)
                    actual['representative']['rework'].update(status='stopped',error='gemini_execution_disabled')
                    self.studio.workflow.store.save(actual)
                view=self.studio.detail('workspace',project)['rework']
                self.assertFalse(view['settings']['ready']);self.assertTrue(view['recovery']['eligible'])
                with self.assertRaisesRegex(CompanyError,'rework_execution_settings_required'):
                    self.studio.action('workspace',project,'rework-recover',{})
            original_state=self.studio.workflow.store.load(project)['representative']['rework']
            clean=provider.load(pid)
            for change in (dict(active_operation='uncertain'),dict(sessions=[dict(id='uncertain')]),
                           dict(run_started_at='uncertain'),dict(attempts=[dict(status='reserved')])):
                bad=deepcopy(clean);bad.update(change)
                with self.assertRaises(CompanyError):provider.verify_disabled_recovery(bad,original_state,self.key)
            bad=deepcopy(clean);bad['real_ai']['attempts']=[dict(status='reserved')]
            with self.assertRaises(CompanyError):provider.verify_disabled_recovery(bad,original_state,self.key)
            with self.assertRaises(CompanyError):provider.verify_disabled_recovery(clean,dict(status='stopped',error='provider_unavailable'),self.key)
            with self.assertRaisesRegex(CompanyError,'rework_key_changed'):provider.verify_disabled_recovery(clean,original_state,'different-fixture-key-123')
            broken=json.loads(saved_grant);broken['signature']='0'*64
            provider._grant_path(pid).write_text(json.dumps(broken))
            with self.assertRaisesRegex(CompanyError,'invalid_consent_signature'):provider.verify_disabled_recovery(clean,original_state,self.key)
            provider._grant_path(pid).write_bytes(saved_grant)
            from autonomous_company import now
            future=(datetime.fromisoformat(now())+timedelta(hours=2)).isoformat()
            with patch('autonomous_free.now',return_value=future):
                with self.assertRaises(CompanyError):provider.verify_disabled_recovery(clean,original_state,self.key)
            self.assertEqual(provider.path(pid).read_bytes(),saved_job)
            self.assertEqual(provider._grant_path(pid).read_bytes(),saved_grant)
        if getattr(self,'new_attempt_fixture',False):
            from autonomous_company import now
            old_id=pid;old=provider.load(pid)
            old.update(status='stopped',reason_code='invalid_dependencies',active_operation='fixture-completed-plan')
            old['sessions']=[dict(id='fixture-session',at=now(),resume=False)]
            old['real_ai']['attempts']=[dict(id='fixture-completed-plan',phase='plan',model=MODEL,status='completed',
                http_status=200,role_result_status='json_parsed',response_hash='fixture-response',
                transport_started_at=now(),response_received_at=now())]
            if getattr(self,'handoff_failure_fixture',False):
                old['reason_code']='script_plan_handoff_required'
                old['real_ai']['attempts'][0]['finished_at']=now()
            if getattr(self,'unavailable_fixture',False):
                old.update(status='paused',reason_code='provider_unavailable')
                old['real_ai']['attempts'][0].update(status='failed',http_status=503,
                    error_code='provider_unavailable',role_result_status='unvalidated',response_hash=None,
                    request_hash='fixture-request-hash',finished_at=now())
                old['real_ai']['attempts'][0].pop('response_received_at')
            old['events'].append(dict(at=now(),event='system_safety_stop',code=old['reason_code']))
            provider.save(old)
            with self.studio.workflow.store.lock(project):
                current=self.studio.workflow.store.load(project)
                current['representative']['rework'].update(status='stopped',error=old['reason_code'])
                self.studio.workflow.store.save(current)
            preserved={p:p.read_bytes() for p in provider.root.glob(old_id+'.*')}
            if getattr(self,'handoff_failure_fixture',False):
                from representative_rework import failed_plan_reference,handoff_validator_identity
                project_state=self.studio.workflow.store.load(project)
                self.assertEqual(failed_plan_reference(provider,project_state,self.key)['handoff_validator'],handoff_validator_identity())
                for changes in (dict(status='reserved'),dict(http_status=503),dict(response_hash=None),dict(finished_at=None)):
                    bad=deepcopy(old);bad['real_ai']['attempts'][0].update(changes)
                    with patch.object(provider,'load',return_value=bad),self.assertRaises(CompanyError):
                        failed_plan_reference(provider,project_state,self.key)
                for changes in (dict(active_operation=None),dict(active_operation='uncertain'),dict(reason_code='another_error')):
                    bad=deepcopy(old);bad.update(changes)
                    with patch.object(provider,'load',return_value=bad),self.assertRaises(CompanyError):
                        failed_plan_reference(provider,project_state,self.key)
                grant_path=provider._grant_path(old_id);saved=grant_path.read_bytes()
                broken=json.loads(saved);broken['signature']='0'*64
                try:
                    grant_path.write_text(json.dumps(broken))
                    with self.assertRaisesRegex(CompanyError,'rework_history_signature_invalid'):
                        failed_plan_reference(provider,project_state,self.key)
                finally:grant_path.write_bytes(saved)
            if getattr(self,'unavailable_fixture',False):
                from representative_rework import failed_plan_reference
                # Refuse ambiguous/reserved/non-503 records and a repeated recovery scope.
                for changes in (dict(status='reserved'),dict(http_status=502),dict(finished_at=None),
                                dict(error_code='free_request_failed')):
                    bad=deepcopy(old);bad['real_ai']['attempts'][0].update(changes)
                    with patch.object(provider,'load',return_value=bad),self.assertRaises(CompanyError):
                        failed_plan_reference(provider,self.studio.workflow.store.load(project),self.key)
                bad=deepcopy(old);bad['active_operation']='another-reservation'
                with patch.object(provider,'load',return_value=bad),self.assertRaises(CompanyError):
                    failed_plan_reference(provider,self.studio.workflow.store.load(project),self.key)
                bad=deepcopy(old)
                bad['rework_reference']['previous_failed_attempt']=dict(
                    failed_plan_reference(provider,self.studio.workflow.store.load(project),self.key),
                    recovery_scope='already_used')
                with patch.object(provider,'load',return_value=bad),self.assertRaises(CompanyError):
                    failed_plan_reference(provider,self.studio.workflow.store.load(project),self.key)
                preserved={p:p.read_bytes() for p in provider.root.glob(old_id+'.*')}
            self.assertIsNotNone(self.studio.detail('workspace',project)['rework']['new_attempt'])
            request=dict(account_project='gen-lang-client-0938732315',confirm_free_account=True,previous_job=old_id)
            self.studio.action('workspace',project,'rework-new-prepare',request)
            pending=self.studio.detail('workspace',project)['rework'];pid=pending['job']
            self.assertNotEqual(pid,old_id);self.assertEqual(pending['status'],'pending')
            self.assertEqual(provider.load(pid)['real_ai']['attempts'],[])
            with self.assertRaises(CompanyError):self.studio.action('workspace',project,'rework-new-prepare',request)
            with self.assertRaises(CompanyError):provider.approve(pid,body,review_hash=digest(body),owner_confirmed=True)
            self.studio.action('workspace',project,'rework-consent',dict(review_hash=pending['review_hash'],confirm_free_account=True,confirm_data_policy=True))
            if getattr(self,'handoff_failure_fixture',False):
                signed=provider.grant(provider.load(pid))
                self.assertEqual(signed['body']['rework_scope']['reference']['previous_failed_attempt']['handoff_validator'],handoff_validator_identity())
                with patch('representative_rework.handoff_validator_identity',return_value={'version':'changed','code_hash':'changed'}),self.assertRaisesRegex(CompanyError,'rework_handoff_validator_changed'):
                    company._quality_transport_allowed(provider.load(pid))
                repeated=deepcopy(provider.load(pid));repeated.update(status='stopped',reason_code='script_plan_handoff_required',
                    active_operation=old['active_operation'],sessions=deepcopy(old['sessions']))
                repeated['real_ai']['attempts']=deepcopy(old['real_ai']['attempts'])
                current=self.studio.workflow.store.load(project)
                current['representative']['rework'].update(status='stopped',error='script_plan_handoff_required')
                original_load=provider.load
                with patch.object(provider,'load',side_effect=lambda job:repeated if job==pid else original_load(job)),self.assertRaisesRegex(CompanyError,'rework_same_validator_new_attempt_forbidden'):
                    failed_plan_reference(provider,current,self.key)
            self.assertNotEqual(provider.grant(provider.load(pid))['id'],provider.load(old_id)['real_ai']['consent']['operating_grant_id'])
            for path,data in preserved.items():self.assertEqual(path.read_bytes(),data)
            self.assertEqual(self.studio.workflow.store.load(project)['representative']['rework_history'][0]['job'],old_id)
        draft=deepcopy(original['script']);draft['topic']['title']='역전 한 수의 이야기'
        for i,b in enumerate(draft['narrative_beats']):
            b.update(narration=['마지막 한 수가 보이나요?','빈칸에 놓자 길이 열렸어요.','작은 선택이 판을 뒤집었죠.'][i],caption='역전 한 수',screen='가상 보드 한 수 비교',fact_status='illustrative')
        draft.update(hook_0_3s=draft['narrative_beats'][0]['narration'],close=draft['narrative_beats'][-1]['narration'],
            transcript='\n'.join(b['narration'] for b in draft['narrative_beats']))
        manager,_=script_callbacks(draft,draft)
        if getattr(self,'strict_plan_fixture',False):
            from representative_rework import validate_rework_plan,PLAN_RULES
            self.assertEqual(body['rework_scope']['plan_contract_hash'],digest(PLAN_RULES))
            valid=json.loads(manager('plan',{}));original_plan=deepcopy(valid)
            self.assertEqual(validate_rework_plan(valid),original_plan)
            for change,field in (
                (lambda p:p['tasks'][0].update(depends_on=[p['tasks'][1]['id']]),'depends_on'),
                (lambda p:p['tasks'][1].update(depends_on=[]),'depends_on'),
                (lambda p:p['tasks'][1].update(criteria_ids=['missing']),'criteria_ids'),
                (lambda p:p['tasks'][1].update(criteria_ids=['hook','hook']),'criteria_ids')):
                bad=deepcopy(valid);change(bad);before_bad=deepcopy(bad)
                with self.assertRaisesRegex(CompanyError,'rework_plan_invalid') as caught:validate_rework_plan(bad)
                self.assertEqual(caught.exception.diagnostics['field'],field)
                self.assertEqual(bad,before_bad)
            self.assertEqual(valid,original_plan)
        review_count=0
        revision_exec_count=0
        def send(request,timeout):
            nonlocal review_count,revision_exec_count
            wire=json.loads(request.data);message=json.loads(wire['contents'][0]['parts'][0]['text']);phase=message['phase'];context=message['data']
            self.assertEqual(context['quality']['feedback_text'],feedback)
            self.assertEqual(context['quality']['answers']['previous_plan']['sha256'],original['sha256'])
            if phase=='plan':
                from representative_rework import PLAN_SCHEMA_REFERENCE
                self.assertEqual(message['output_contract'],PLAN_SCHEMA_REFERENCE)
                bad=deepcopy(wire);bad['generationConfig']['responseJsonSchema']={}
                with self.assertRaisesRegex(CompanyError,'rework_schema_changed'):company._validate_payload(bad)
                bad=deepcopy(wire)
                bad_message=deepcopy(message);bad_message['output_contract']='changed'
                bad['contents'][0]['parts'][0]['text']=json.dumps(bad_message)
                with self.assertRaisesRegex(CompanyError,'rework_schema_reference_changed'):company._validate_payload(bad)
                if getattr(self,'strict_plan_fixture',False):
                    from representative_rework import PLAN_RULES
                    self.assertIn(PLAN_RULES,wire['systemInstruction']['parts'][0]['text'])
                    tasks_schema=wire['generationConfig']['responseJsonSchema']['properties']['result']['anyOf'][0]['properties']['tasks']
                    self.assertEqual((tasks_schema['minItems'],tasks_schema['maxItems']),(2,2))
                result=json.loads(manager(phase,context));result['replan']=dict(selected_topic=draft['topic']['title'],duration_seconds=25,
                    duration_reason='기존25초 유지, 최적값 주장은 하지 않음',feedback_response='제작법 대신 게임 장면으로 재기획')
                if getattr(self,'rework_criterion_ids_fixture',False):
                    from quality_workflow import _validate_script_plan
                    from representative_rework import validate_rework_plan
                    renamed={criterion['id']:'manager_'+criterion['id'] for criterion in result['criteria']}
                    for criterion in result['criteria']:criterion['id']=renamed[criterion['id']]
                    for task in result['tasks']:task['criteria_ids']=[renamed[c] for c in task['criteria_ids']]
                    plan={k:v for k,v in result.items() if k!='replan'}
                    with self.assertRaisesRegex(CompanyError,'script_plan_handoff_required'):_validate_script_plan(plan)
                    validate_rework_plan(plan)
                    for change in (lambda p:p['tasks'][1].update(depends_on=[]),
                                   lambda p:p['tasks'][0].update(criteria_ids=['missing']),
                                   lambda p:p['tasks'][1].update(role='writer')):
                        bad=deepcopy(plan);change(bad)
                        with self.assertRaises(CompanyError):company._validate_script_plan(bad)
            elif phase=='execute':
                if (getattr(self,'rework_quality_revision_fixture',False)
                        and context['assignment']['role']=='writer'):
                    revision_exec_count+=1
                    if revision_exec_count==2:
                        self.assertIn('goal_fit',context['revision_feedback'])
                        self.assertIn('subject_story',context['revision_feedback'])
                value=deepcopy(draft) if context['assignment']['role']=='writer' else script_editor_handoff(context['previous_results'][0])
                if (getattr(self,'rework_quality_revision_fixture',False)
                        and context['assignment']['role']=='writer' and revision_exec_count==2):
                    # Change visual detail without breaking narration/transcript/close invariants.
                    value['narrative_beats'][1]['caption']='수정된 가상 역전 장면'
                    value['narrative_beats'][1]['screen']='가상 보드의 역전 전후 비교'
                result=dict(content=value if context['assignment']['role']=='writer' else json.dumps(value),evidence='offline fixture',uncertainty='unassessed')
            else:
                result=json.loads(manager(phase,context));result['goal_review']={k:dict(met=True,evidence='역전 한 수') for k in ('goal_fit','feedback_applied','subject_story','concrete_hook','claims_supported')}
                if getattr(self,'rework_quality_escalation_fixture',False) and phase=='review' and context['assignment']['role']=='writer':
                    result['action']='stop'
                    result['goal_review']['goal_fit']['met']=False
                    result['goal_review']['subject_story']['met']=False
                if getattr(self,'rework_quality_revision_fixture',False) and phase=='review' and context['assignment']['role']=='writer':
                    review_count+=1
                    if review_count==1:
                        self.assertEqual(result['action'],'accept')
                        result['goal_review']['goal_fit']['met']=False
                        result['goal_review']['subject_story']['met']=False
            return FixtureResponse(json.dumps(dict(candidates=[dict(finishReason='STOP',content=dict(role='model',parts=[dict(text=json.dumps(dict(result=result),ensure_ascii=False))]))],
                usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=30,totalTokenCount=50))).encode())
        self.http.reset_mock(side_effect=False);self.http.side_effect=send
        queued=[]
        class QueuedThread:
            def __init__(self,*,target,daemon):self.target=target
            def start(self):queued.append(self.target)
        original_handoff=handoff
        def offline_handoff(*args,**kwargs):return original_handoff(*args,allow_fixture=True,**kwargs)
        action='rework-recover' if getattr(self,'disabled_recovery_fixture',False) else 'rework-run'
        with patch('threading.Thread',QueuedThread),patch('representative_rework.ReworkCompany',OfflineRework),patch('representative_rework.handoff',offline_handoff):
            self.studio.action('workspace',project,action,{})
            with self.assertRaises(CompanyError):self.studio.action('workspace',project,action,{})
            self.assertEqual(self.http.call_count,0)
            if getattr(self,'disabled_recovery_fixture',False):
                state=self.studio.workflow.store.load(project)['representative']['rework']
                self.assertEqual(state['recovery_events'][0]['previous_error'],'gemini_execution_disabled')
                self.assertEqual(provider._grant_path(pid).read_bytes(),saved_grant)
            queued.pop()()
        result=provider.load(pid)
        if getattr(self,'rework_quality_escalation_fixture',False):
            self.assertEqual(result['status'],'stopped',result.get('reason_code'))
            self.assertEqual(result.get('reason_code'),'manager_stopped')
            self.assertEqual(self.http.call_count,3)
            panel=self.studio.detail('workspace',project)['rework']
            report=panel['progress']['quality_report']
            self.assertEqual(report['decision'],'stop')
            self.assertIn('goal_fit',report['failed_checks'])
            self.assertIsNone(panel['quality_decision'])
            old_files={path:path.read_bytes() for path in provider.root.glob(pid+'.*')}
            self.studio.action('workspace',project,'rework-quality-decide',
                dict(job=pid,report_hash=panel['quality_report_hash'],action='request_revision',
                     feedback='게임 공략 대신 반전 장면 이야기로 수정하세요.'))
            self.assertEqual(self.http.call_count,3)
            with self.assertRaisesRegex(CompanyError,'quality_decision_already_recorded'):
                self.studio.action('workspace',project,'rework-quality-decide',
                    dict(job=pid,report_hash=panel['quality_report_hash'],action='request_revision',
                         feedback='중복 지시'))
            with self.assertRaises(CompanyError):
                self.studio.action('workspace',project,'rework-new-prepare',
                    dict(account_project='gen-lang-client-0938732315',confirm_free_account=True,previous_job=pid))
            self.studio.action('workspace',project,'rework-quality-prepare',
                dict(account_project='gen-lang-client-0938732315',confirm_free_account=True,previous_job=pid))
            pending=self.studio.detail('workspace',project)['rework']
            self.assertEqual(pending['status'],'pending')
            self.assertNotEqual(pending['job'],pid)
            new=provider.load(pending['job'])
            self.assertEqual(new['real_ai']['attempts'],[])
            self.assertEqual(new['rework_reference']['previous_failed_attempt']['job'],pid)
            self.assertIn('반전 장면',new['quality_inputs']['feedback_text'])
            self.assertIn('quality_followup',new['quality_inputs']['answers'])
            self.assertEqual(self.http.call_count,3)
            for path,data in old_files.items():self.assertEqual(path.read_bytes(),data)
            with self.assertRaises(CompanyError):
                self.studio.action('workspace',project,'rework-quality-prepare',
                    dict(account_project='gen-lang-client-0938732315',confirm_free_account=True,previous_job=pid))
            return
        self.assertEqual(result['status'],'needs_user_review',result.get('reason_code'))
        expected_calls=7 if getattr(self,'rework_quality_revision_fixture',False) else 5
        self.assertEqual(self.http.call_count,expected_calls)
        if getattr(self,'rework_quality_revision_fixture',False):
            writer=next(t for t in result['assignments'] if t['role']=='writer')
            self.assertEqual(len(writer['versions']),2)
            self.assertEqual(writer['revisions'],1)
            self.assertEqual(review_count,2)
            self.assertEqual(revision_exec_count,2)
            self.assertEqual(writer['reviews'][0]['action'],'revise')
            self.assertEqual(writer['reviews'][1]['action'],'accept')
            self.assertEqual(result['quality_followups'][0]['decision'],'revise')
            self.assertEqual(result['quality_followups'][0]['original_action'],'accept')
            self.assertEqual([t['state'] for t in result['assignments']],
                             ['accepted_by_ai_manager','accepted_by_ai_manager'])
        with self.assertRaises(CompanyError):run()
        self.assertEqual(self.http.call_count,expected_calls)
        handoff(self.studio.workflow,project,provider,allow_fixture=True)
        flow=self.studio.workflow.store.load(project)['representative']
        self.assertEqual(flow['stage'],'awaiting_plan_approval');self.assertEqual(len(flow['plan_versions']),2)
        self.assertEqual(flow['plan_versions'][0],original)
        self.assertEqual(flow['plan_versions'][1]['representative_feedback'],feedback)
        if getattr(self,'rework_criterion_ids_fixture',False):
            self.assertTrue(all(c['id'].startswith('manager_') for c in result['plan']['criteria']))
            self.assertEqual([t['role'] for t in result['assignments']],['writer','editor'])
            self.assertTrue(all(t['state']=='accepted_by_ai_manager' for t in result['assignments']))
            for path,data in original_bytes.items():self.assertEqual(path.read_bytes(),data)
            if getattr(self,'handoff_failure_fixture',False):
                for path,data in preserved.items():self.assertEqual(path.read_bytes(),data)
                self.assertEqual(flow['rework_history'][0]['error'],'script_plan_handoff_required')
            return
        if getattr(self,'unavailable_fixture',False):
            for path,data in preserved.items():self.assertEqual(path.read_bytes(),data)
            for path,data in original_bytes.items():self.assertEqual(path.read_bytes(),data)
            self.assertEqual(flow['rework_history'][0]['error'],'provider_unavailable')
            return
        # The server rejects an explicit instructional drift even if the model calls it acceptable.
        company._review_content='쇼츠 만드는 방법'
        review=json.loads(manager('review',dict(plan_inspection={},criteria=[dict(id='hook')])) )
        review['goal_review']={k:dict(met=True,evidence='쇼츠 만드는 방법') for k in ('goal_fit','feedback_applied','subject_story','concrete_hook','claims_supported')}
        with self.assertRaisesRegex(CompanyError,'rework_obvious_goal_drift'):
            company._parse_role_content(json.dumps(dict(result=review)),'review')
        # A later separately consented revision fails once; duplicate starts cannot retry it.
        latest=flow['plan_versions'][-1]
        self.studio.workflow.decide(project,'plan',version=2,sha256=latest['sha256'],action='request_revision',feedback='후크를 더 구체화하세요')
        self.studio.action('workspace',project,'rework-prepare',dict(account_project='gen-lang-client-0938732315',confirm_free_account=True))
        pending=self.studio.detail('workspace',project)['rework']
        self.studio.action('workspace',project,'rework-consent',dict(review_hash=pending['review_hash'],confirm_free_account=True,confirm_data_policy=True))
        class ErrorBody(BytesIO):
            reads=[]
            def read(self,size=-1):
                self.reads.append(size);return super().read(size)
        error_body=ErrorBody(json.dumps(dict(error=dict(code=503,status='UNAVAILABLE',
            message='PRIVATE goal feedback '+self.key,
            details=[dict(reason='PRIVATE_ID'),dict(reason='RATE_LIMIT_EXCEEDED',metadata={'key':self.key})]))).encode())
        self.http.reset_mock(side_effect=False)
        self.http.side_effect=HTTPError(ENDPOINT,503,'private',{'Retry-After':'7'},error_body)
        with patch('threading.Thread',QueuedThread),patch('representative_rework.ReworkCompany',OfflineRework):
            self.studio.action('workspace',project,'rework-run',{});queued.pop()()
            with self.assertRaises(CompanyError):self.studio.action('workspace',project,'rework-run',{})
        self.assertEqual(self.http.call_count,1)
        self.assertEqual(self.studio.detail('workspace',project)['rework']['status'],'stopped')
        self.assertTrue(error_body.closed);self.assertEqual(error_body.reads,[4097])
        failed=provider.load(pending['job']);attempt=failed['real_ai']['attempts'][0]
        self.assertEqual(len(failed['real_ai']['attempts']),1)
        self.assertEqual((failed['status'],attempt['status'],attempt['http_status']),('paused','failed',503))
        self.assertEqual(attempt['retry_after_seconds'],7)
        self.assertEqual(attempt['provider_error_body'],dict(parse='json_error',code=503,status='UNAVAILABLE',reasons=['RATE_LIMIT_EXCEEDED']))
        self.assertNotIn('PRIVATE',json.dumps(failed));self.assertNotIn(self.key,json.dumps(failed))
        if getattr(self,'new_attempt_fixture',False):
            for path,data in preserved.items():self.assertEqual(path.read_bytes(),data)
        for path,data in original_bytes.items():self.assertEqual(path.read_bytes(),data)

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
