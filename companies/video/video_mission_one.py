"""Mission 01's scoped entry to the existing signed video provider workflow."""
import argparse
import hmac
import json
import os
import unicodedata
from pathlib import Path
from copy import deepcopy

from autonomous_company import CompanyError, Store, digest, exact, parse, require, text
from autonomous_gemini35 import Gemini35Config, Gemini35Store, MODEL, ENDPOINT
from autonomous_live import LiveEmployeeProvider, LiveManagerProvider
from goal_dialogue_live import send_once
from employee_web_research import (TOOL as WEB_TOOL, POLICY as WEB_POLICY, collect,
    validate_queries, validate_selection, usable_observations)
from role_json_schema import response_format, matches, obj, arr, S
from quality_provider import QualityProviderStore
from quality_workflow import VideoProviderQualityCompany
from script_quality import SCRIPT_CONTRACT, inspect_script, AUDIENCE_INSTRUCTIONS, writer_contract

SCOPE = 'representative_video_mission_01'
GAME_GOAL = '요즘 인기있는 게임에 대한 흥미있는 쇼츠 영상을 만들어봐. 기본적으로 인기있는 쇼츠는 몇초인지도 확인해보고.'
GAME_SCOPE = 'game_shorts_independent_research_20261111'
GAME_RESEARCH_BLOCKER = 'mission_independent_web_research_unavailable'
MAX_CALLS = 10  # Historical policy; never rewrite old signed grants.
UNIFIED_SUCCESSOR_POLICY = 'mission01_validated_writer_successor_20261112_v1'
CAPTION_REVISION_PURPOSE = 'revise_preserved_writer_v2_caption_width_under_new_signed_revision_grant'
PARTIAL_REVISION_PURPOSE = 'revise_accepted_format_writer_v1_from_preserved_manager_feedback_after_503'
DNS_PERMISSION_PURPOSE = 'write_new_script_under_native_v2_with_authorized_network_permission'
UNIFIED_PURPOSE = '구조화 writer schema에 맞는 새 대본 작성'
WRITER_FAILURES = frozenset(('invalid_script_shot','invalid_script_source','invalid_script_fact','invalid_script_timeline',
    'invalid_script_contract','invalid_beat_time','invalid_topic_freshness','script_transcript_mismatch',
    'script_audience_mismatch','script_audience_inference_required','script_provenance_mismatch',
    'mission_selected_topic_mismatch','mission_visual_source_unverified','invalid_writer_schema',
    'missing_script_text','invalid_fields','invalid_script_beats','invalid_script_unknowns'))
TOPIC_SUCCESSOR_POLICY = 'mission01_topic_successor_20261112_v1'
AUDIENCE_SUCCESSOR_POLICY = 'mission01_audience_successor_20261112_v1'
FREE_WRITER_POLICY = 'mission01_free_provider_limits_20261112_v1'
DOUBLE_BUDGET_POLICY = 'mission01_double_budget_20261112_v1'
MISSION_ACCOUNT = 'gen-lang-client-0938732315'
ROLES = ('research', 'writer', 'editor')
DATA_POLICY = 'Google unpaid-service input/output may be used for improvement and reviewed by humans.'
DEFAULT_ROOT = Path('data/video_representative_workflow/studio')


def _writer_reuse(p):
    return p.get('mission_unified_successor') or p.get('mission_topic_successor') or p.get('mission_audience_successor') or p.get('mission_free_writer') or p.get('mission_budget_writer') or p.get('mission_writer_resume')


def _web_limit(p):
    return 0 if p.get('mission_unified_successor') or p.get('mission_free_writer') or p.get('mission_audience_successor') or p.get('mission_topic_successor') else 6 if p.get('mission_budget_writer') else 2 if p.get('mission_successor') or p.get('mission_writer_resume') else 4


def _binding(project_id, key):
    require(isinstance(key, str) and 16 <= len(key) <= 4096 and key.isascii()
            and all(32 < ord(c) < 127 for c in key), 'mission_key_missing')
    return hmac.digest(key.encode(), (SCOPE + ':' + project_id).encode(), 'sha256').hex()


def quota_observation(value):
    # Provider availability is not the owner's authorization budget.
    require(value is None or value == 'unknown' or type(value) is int and value >= 0,
            'invalid_quota_observation')
    return 'unknown' if value is None else value


class MissionOneStore(QualityProviderStore):
    # Only this adapter opts into the common optional-cap validator. check_scope keeps old policies exact.
    _limits = staticmethod(Gemini35Store._limits)

    def prepare_mission(self, project_id, *, key, account_project, quota_note, remaining_requests=None,
                        youtube_key=None, youtube_project=None, search_remaining=None, units_remaining=None,
                        confirm_youtube_policy=False):
        p = self.load(project_id)
        self.check_scope(p)
        if p['goal'] == GAME_GOAL:
            require(p['quality_inputs']['capabilities'].get('employee_web_research') == WEB_TOOL, GAME_RESEARCH_BLOCKER)
            require(confirm_youtube_policy is True, 'employee_web_policy_confirmation_required')
            text(youtube_project, 200)
            web = dict(policy=WEB_POLICY, account_project=youtube_project,
                search_remaining=quota_observation(search_remaining),
                general_units_remaining=quota_observation(units_remaining),
                approved_max_searches=_web_limit(p), approved_max_videos=_web_limit(p),
                credential_binding=_binding(project_id+':youtube',youtube_key), free_usage_verified=True,
                policy_confirmed=True)
        else:
            web = None
        # These are owner attestations, never a provider billing lookup or a $0 guarantee.
        proof = dict(account_project=account_project, remaining_requests=quota_observation(remaining_requests), quota_note=quota_note,
                     approved_max_calls=p['limits']['max_calls'],
                     credential_binding=_binding(project_id, key), billing_disabled=True,
                     free_data_policy=DATA_POLICY)
        self._check_mission_account(proof, p['limits']['max_calls'])
        require(key not in json.dumps(proof, ensure_ascii=False), 'secret_in_state')
        body = self.prepare(project_id, valid_hours=1, confirm_free_account=True)
        return {**body, 'mission_account': proof, **({'mission_web':web, 'mission_research_review':research_review_policy()} if web else {}),
                **({'mission_resume':deepcopy(p['mission_resume'])} if 'mission_resume' in p else {}),
                **({'mission_successor':deepcopy(p['mission_successor'])} if 'mission_successor' in p else {}),
                **({'mission_writer_resume':deepcopy(p['mission_writer_resume'])} if 'mission_writer_resume' in p else {}),
                **({'mission_budget_writer':deepcopy(p['mission_budget_writer'])} if 'mission_budget_writer' in p else {}),
                **({'mission_free_writer':deepcopy(p['mission_free_writer'])} if 'mission_free_writer' in p else {}),
                **({'mission_audience_successor':deepcopy(p['mission_audience_successor'])} if 'mission_audience_successor' in p else {}),
                **({'mission_topic_successor':deepcopy(p['mission_topic_successor'])} if 'mission_topic_successor' in p else {}),
                **({'mission_unified_successor':deepcopy(p['mission_unified_successor'])} if 'mission_unified_successor' in p else {})}

    def resume_reference(self, previous):
        require('mission_resume' not in previous, 'mission_resume_not_eligible')
        self.check_scope(previous)
        attempts = previous['real_ai']['attempts']
        require('mission_resume' not in previous and previous['goal'] == GAME_GOAL
                and previous['status'] == 'stopped' and previous.get('reason_code') == 'free_request_failed'
                and len(attempts) == 1 and not previous.get('employee_web')
                and not previous['assignments'] and not previous.get('final'), 'mission_resume_not_eligible')
        # Authenticate historical consent without treating its expired approval as new permission.
        grant = parse(self._grant_path(previous['id']).read_text())
        require(hmac.compare_digest(str(grant['signature']), self._sign(grant['record']))
                and grant['record']['id'] == previous['real_ai']['consent'].get('operating_grant_id')
                and grant['record']['revoked_at'] is None, 'invalid_consent_signature')
        attempt = attempts[0]
        require(attempt['status'] == 'failed' and attempt.get('phase') == 'plan'
                and attempt.get('provider_error_diagnostics') == dict(category='dns_error',stage='transport_open')
                and not attempt.get('http_status') and not attempt.get('response_received_at')
                and previous['active_operation'] == attempt['id'], 'mission_resume_not_eligible')
        return dict(previous_job=previous['id'], previous_state_hash=previous['storage_hash'],
                    failed_attempt=attempt['id'], consumed_calls=1, total_max_calls=MAX_CALLS,
                    new_max_calls=MAX_CALLS-1, provider_receipt='unknown')

    def successor_reference(self, previous):
        """Read-only proof for one review-failure successor; never relax DNS eligibility."""
        require('mission_successor' not in previous and previous['goal'] == GAME_GOAL
                and previous['status'] == 'stopped' and previous.get('reason_code') in
                ('invalid_model_json', 'mission_research_review_structure_invalid'), 'mission_successor_not_eligible')
        first = self.load(previous['mission_resume']['previous_job'])
        require(digest(previous['mission_resume']) == digest(self.resume_reference(first))
                and previous['quality_inputs'] == first['quality_inputs'], 'mission_successor_history_changed')
        grant = parse(self._grant_path(previous['id']).read_text())
        require(hmac.compare_digest(str(grant['signature']), self._sign(grant['record']))
                and grant['record']['id'] == previous['real_ai']['consent'].get('operating_grant_id')
                and grant['record']['revoked_at'] is None, 'invalid_consent_signature')
        attempts = previous['real_ai']['attempts']
        require(len(attempts) == 3 and [a['phase'] for a in attempts] == ['plan','execute','review']
                and all(a['status']=='completed' and a.get('http_status')==200 and a['model']==MODEL
                        and a.get('response_hash') and a.get('free_account_policy_verified') is True for a in attempts)
                and all(a['role_result_status']=='validated' for a in attempts[:2])
                and attempts[-1]['role_result_status']=='json_parsed'
                and previous['active_operation']==attempts[-1]['id'], 'mission_successor_attempts_invalid')
        tasks = previous['assignments']
        require(len(tasks)==3 and [t['role'] for t in tasks]==list(ROLES)
                and tasks[0]['state']=='awaiting_ai_review' and len(tasks[0]['versions'])==1
                and not tasks[0]['reviews'] and all(t['state']=='pending' and not t['versions'] and not t['reviews']
                                                  for t in tasks[1:]), 'mission_successor_research_invalid')
        research = tasks[0]['versions'][0]
        require(digest(research)==attempts[-1]['result_hash'] and not previous.get('final')
                and research['source']==previous['plan']['source']
                and research['source'] in ('provider_model_claim','offline_http_fixture'), 'mission_successor_provenance')
        web = previous['employee_web']
        usable_observations(web)
        require(web['employee_task']==tasks[0]['id'] and web['input']==parse(research['content'])
                and web['input_hash']==digest(web['input']) and web['provenance']==research['source']
                and len(web['attempts'])==4 and all(a['status']=='completed' and a['http_status']==200 for a in web['attempts'])
                and sum(a['quota_bucket']=='search' for a in web['attempts'])==2
                and sum(a['quota_bucket']=='general' for a in web['attempts'])==2, 'mission_successor_web_invalid')
        validate_queries(web['input'])
        return dict(previous_job=previous['id'], previous_state_hash=previous['storage_hash'],
            first_job=first['id'], first_state_hash=first['storage_hash'],
            previous_attempt_ids=[a['id'] for a in first['real_ai']['attempts']+attempts],
            consumed_calls=4, new_max_calls=6, total_max_calls=10,
            consumed_searches=2, consumed_videos=2, new_max_searches=2, new_max_videos=2,
            total_max_searches=4,total_max_videos=4, plan_hash=digest(previous['plan']),
            research_hash=digest(research), receipt_hash=web['receipt_hash'],
            reuse='prior_validated_plan_and_employee_research_pending_new_review')

    def writer_reference(self, previous):
        """Authenticate the stopped writer chain; old grants prove history only."""
        require(previous.get('mission_successor') and not previous.get('mission_writer_resume')
                and previous['status']=='stopped' and previous.get('reason_code') in
                ('script_audience_mismatch','script_audience_inference_required'), 'mission_writer_not_eligible')
        second=self.load(previous['mission_successor']['previous_job'])
        require(digest(previous['mission_successor'])==digest(self.successor_reference(second))
                and previous['goal']==second['goal'] and previous['quality_inputs']==second['quality_inputs']
                and previous['plan']==second['plan'] and previous['employee_web']==second['employee_web']
                and previous['limits']==dict(max_calls=6,max_revisions_per_task=1,max_total_revisions=1),
                'mission_writer_history_changed')
        grant=parse(self._grant_path(previous['id']).read_text())
        require(hmac.compare_digest(str(grant['signature']),self._sign(grant['record']))
                and grant['record']['id']==previous['real_ai']['consent'].get('operating_grant_id')
                and grant['record']['revoked_at'] is None, 'invalid_consent_signature')
        attempts=previous['real_ai']['attempts']
        tasks=previous['assignments']
        require(len(attempts)==2 and [a['phase'] for a in attempts]==['review','execute']
                and all(a['status']=='completed' and a.get('http_status')==200 and a['model']==MODEL
                        and a.get('response_hash') and a.get('free_account_policy_verified') is True for a in attempts)
                and [a['role_result_status'] for a in attempts]==['validated','json_parsed']
                and previous['active_operation']==attempts[-1]['id'] and not previous.get('final'),
                'mission_writer_attempts_invalid')
        require(len(tasks)==3 and [t['role'] for t in tasks]==list(ROLES)
                and tasks[0]['state']=='accepted_by_ai_manager' and len(tasks[0]['reviews'])==1
                and tasks[0]['reviews'][0]['action']=='accept'
                and tasks[0]['versions']==second['assignments'][0]['versions']
                and all(t['state']=='pending' and not t['versions'] and not t['reviews'] for t in tasks[1:]),
                'mission_writer_reuse_invalid')
        selection=validate_selection(parse(tasks[0]['reviews'][0]['feedback']),previous['employee_web'])
        require(attempts[0]['task_id']==tasks[0]['id'] and attempts[1]['task_id']==tasks[1]['id'],
                'mission_writer_attempts_invalid')
        return dict(previous_job=previous['id'],previous_state_hash=previous['storage_hash'],
            history=deepcopy(previous['mission_successor']),
            previous_attempt_ids=previous['mission_successor']['previous_attempt_ids']+[a['id'] for a in attempts],
            consumed_calls=6,new_max_calls=4,total_max_calls=10,
            consumed_searches=2,consumed_videos=2,new_max_searches=2,new_max_videos=2,
            total_max_searches=4,total_max_videos=4,plan_hash=digest(previous['plan']),
            research_hash=digest(tasks[0]),selection_hash=digest(selection),
            receipt_hash=previous['employee_web']['receipt_hash'],
            handoff='accepted_task_reviews_local_assembly_no_new_ai_final_evaluation')

    def budget_writer_reference(self, previous):
        """A new scoped policy after the fourth failure; historical grants stay immutable."""
        require(previous.get('mission_writer_resume') and not previous.get('mission_budget_writer')
                and previous['status']=='stopped' and previous.get('reason_code')=='script_provenance_mismatch',
                'mission_budget_writer_not_eligible')
        third=self.load(previous['mission_writer_resume']['previous_job'])
        require(digest(previous['mission_writer_resume'])==digest(self.writer_reference(third))
                and previous['goal']==third['goal'] and previous['quality_inputs']==third['quality_inputs']
                and previous['plan']==third['plan'] and previous['employee_web']==third['employee_web']
                and previous['assignments']==third['assignments']
                and previous['limits']==dict(max_calls=4,max_revisions_per_task=1,max_total_revisions=1),
                'mission_budget_writer_history_changed')
        grant=parse(self._grant_path(previous['id']).read_text())
        require(hmac.compare_digest(str(grant['signature']),self._sign(grant['record']))
                and grant['record']['id']==previous['real_ai']['consent'].get('operating_grant_id')
                and grant['record']['revoked_at'] is None, 'invalid_consent_signature')
        body=grant['record']['body']
        require(body['mission_account']['account_project']==body['mission_web']['account_project']==MISSION_ACCOUNT
                and body['mission_account']['free_data_policy']==DATA_POLICY
                and body['model']==MODEL and body['endpoint']==ENDPOINT and body['free_only'] is True,
                'mission_budget_writer_scope_changed')
        attempts=previous['real_ai']['attempts']
        require(len(attempts)==1 and attempts[0]['phase']=='execute'
                and attempts[0]['task_id']==previous['assignments'][1]['id']
                and attempts[0]['status']=='completed' and attempts[0].get('http_status')==200
                and attempts[0]['model']==MODEL and attempts[0].get('response_hash')
                and attempts[0].get('free_account_policy_verified') is True
                and attempts[0]['role_result_status']=='json_parsed'
                and previous['active_operation']==attempts[0]['id'] and not previous.get('final'),
                'mission_budget_writer_attempts_invalid')
        ref=previous['mission_writer_resume']
        return dict(policy=DOUBLE_BUDGET_POLICY,previous_job=previous['id'],
            previous_state_hash=previous['storage_hash'],history=deepcopy(ref),
            previous_attempt_ids=ref['previous_attempt_ids']+[attempts[0]['id']],
            consumed_calls=7,new_max_calls=13,total_max_calls=20,
            consumed_searches=2,consumed_videos=2,new_max_searches=6,new_max_videos=6,
            total_max_searches=8,total_max_videos=8,execution_max_searches=0,execution_max_videos=0,
            account_project=MISSION_ACCOUNT,model=MODEL,endpoint=ENDPOINT,data_policy=DATA_POLICY,
            free_quota='unknown',billing_verification='unverified',
            plan_hash=ref['plan_hash'],research_hash=ref['research_hash'],
            selection_hash=ref['selection_hash'],receipt_hash=ref['receipt_hash'],handoff=ref['handoff'])

    def free_writer_reference(self, previous, *, explicit_max_calls=None):
        """Provider-limited policy, separate from every historical counter/grant."""
        require(explicit_max_calls is None or type(explicit_max_calls) is int and explicit_max_calls>=1,
                'invalid_explicit_call_limit')
        reference=self.budget_writer_reference(previous)  # Authenticate only the immutable failure chain.
        reference.update(policy=FREE_WRITER_POLICY,explicit_max_calls=explicit_max_calls,
            new_max_calls=explicit_max_calls,total_max_calls=None,
            new_max_searches=None,new_max_videos=None,total_max_searches=None,total_max_videos=None,
            quota_policy='provider_free_limits_only_unknown_until_observed',
            paid_transition='separate_explicit_owner_approval_required',automatic_retry=False,
            next_request_purpose='write_new_script_with_explicit_server_provenance_contract')
        return reference

    def audience_successor_reference(self, previous):
        """Fifth audience failure only; reuse the authenticated original selection, never a failed script."""
        require(previous.get('mission_free_writer') and not previous.get('mission_audience_successor')
                and previous['status']=='stopped' and previous.get('reason_code')=='script_audience_inference_required',
                'mission_audience_successor_not_eligible')
        fourth=self.load(previous['mission_free_writer']['previous_job'])
        require(digest(previous['mission_free_writer'])==digest(self.free_writer_reference(fourth))
                and previous['goal']==fourth['goal'] and previous['quality_inputs']==fourth['quality_inputs']
                and previous['plan']==fourth['plan'] and previous['employee_web']==fourth['employee_web']
                and previous['assignments']==fourth['assignments']
                and previous['limits']==dict(max_calls=None,max_revisions_per_task=1,max_total_revisions=1),
                'mission_audience_successor_history_changed')
        grant=parse(self._grant_path(previous['id']).read_text())
        require(hmac.compare_digest(str(grant['signature']),self._sign(grant['record']))
                and grant['record']['id']==previous['real_ai']['consent'].get('operating_grant_id')
                and grant['record']['revoked_at'] is None, 'invalid_consent_signature')
        body=grant['record']['body']
        require(body['mission_free_writer']==previous['mission_free_writer']
                and body['mission_account']['account_project']==body['mission_web']['account_project']==MISSION_ACCOUNT
                and body['mission_account']['free_data_policy']==DATA_POLICY
                and body['mission_account']['billing_disabled'] is True
                and body['model']==MODEL and body['endpoint']==ENDPOINT and body['free_only'] is True,
                'mission_audience_successor_scope_changed')
        attempts=previous['real_ai']['attempts']
        require(len(attempts)==1 and attempts[0]['phase']=='execute'
                and attempts[0]['task_id']==previous['assignments'][1]['id']
                and attempts[0]['status']=='completed' and attempts[0].get('http_status')==200
                and attempts[0]['model']==MODEL and attempts[0].get('response_hash')
                and attempts[0].get('free_account_policy_verified') is True
                and attempts[0]['role_result_status']=='json_parsed'
                and previous['active_operation']==attempts[0]['id'] and not previous.get('final'),
                'mission_audience_successor_attempts_invalid')
        ref=deepcopy(previous['mission_free_writer'])
        ref.update(policy=AUDIENCE_SUCCESSOR_POLICY,previous_job=previous['id'],
            previous_state_hash=previous['storage_hash'],history=deepcopy(previous['mission_free_writer']),
            previous_attempt_ids=ref['previous_attempt_ids']+[attempts[0]['id']],consumed_calls=8,
            next_request_purpose='write_new_script_with_revised_explicit_audience_inference_contract')
        return ref

    def topic_successor_reference(self, previous):
        """Sixth selected-topic failure only; reuse the authenticated original selection, never a failed script."""
        require(previous.get('mission_audience_successor') and not previous.get('mission_topic_successor')
                and previous['status']=='stopped' and previous.get('reason_code')=='mission_selected_topic_mismatch',
                'mission_topic_successor_not_eligible')
        fifth=self.load(previous['mission_audience_successor']['previous_job'])
        require(digest(previous['mission_audience_successor'])==digest(self.audience_successor_reference(fifth))
                and previous['goal']==fifth['goal'] and previous['quality_inputs']==fifth['quality_inputs']
                and previous['plan']==fifth['plan'] and previous['employee_web']==fifth['employee_web']
                and previous['assignments']==fifth['assignments']
                and previous['limits']==dict(max_calls=None,max_revisions_per_task=1,max_total_revisions=1),
                'mission_topic_successor_history_changed')
        grant=parse(self._grant_path(previous['id']).read_text())
        require(hmac.compare_digest(str(grant['signature']),self._sign(grant['record']))
                and grant['record']['id']==previous['real_ai']['consent'].get('operating_grant_id')
                and grant['record']['revoked_at'] is None, 'invalid_consent_signature')
        body=grant['record']['body']
        require(body['mission_audience_successor']==previous['mission_audience_successor']
                and body['mission_account']['account_project']==body['mission_web']['account_project']==MISSION_ACCOUNT
                and body['mission_account']['free_data_policy']==DATA_POLICY
                and body['mission_account']['billing_disabled'] is True
                and body['model']==MODEL and body['endpoint']==ENDPOINT and body['free_only'] is True,
                'mission_topic_successor_scope_changed')
        attempts=previous['real_ai']['attempts']
        require(len(attempts)==1 and attempts[0]['phase']=='execute'
                and attempts[0]['task_id']==previous['assignments'][1]['id']
                and attempts[0]['status']=='completed' and attempts[0].get('http_status')==200
                and attempts[0]['model']==MODEL and attempts[0].get('response_hash')
                and attempts[0].get('free_account_policy_verified') is True
                and attempts[0]['role_result_status']=='json_parsed'
                and previous['active_operation']==attempts[0]['id'] and not previous.get('final'),
                'mission_topic_successor_attempts_invalid')
        ref=deepcopy(previous['mission_audience_successor'])
        ref.update(policy=TOPIC_SUCCESSOR_POLICY,previous_job=previous['id'],
            previous_state_hash=previous['storage_hash'],history=deepcopy(previous['mission_audience_successor']),
            previous_attempt_ids=ref['previous_attempt_ids']+[attempts[0]['id']],consumed_calls=9,
            next_request_purpose='write_new_script_with_exact_manager_selected_topic_copy_contract')
        return ref

    def caption_revision_reference(self, previous, new_purpose):
        require(new_purpose==CAPTION_REVISION_PURPOSE and previous==self.load(previous['id'])
                and previous['status']=='stopped' and previous.get('reason_code')=='known_script_defects',
                'mission_caption_not_eligible')
        prior=previous.get('mission_unified_successor',{})
        require(prior.get('new_purpose')==PARTIAL_REVISION_PURPOSE,'mission_caption_not_eligible')
        parent=self.load(prior['previous_job'])
        expected=self.unified_successor_reference(parent,new_purpose=PARTIAL_REVISION_PURPOSE)
        grant=parse(self._grant_path(previous['id']).read_text());record=grant['record'];body=record['body']
        require(hmac.compare_digest(str(grant['signature']),self._sign(record))
                and record['id']==previous['real_ai']['consent'].get('operating_grant_id')
                and record['revoked_at'] is None and body['mission_unified_successor']==prior
                and prior==expected,'mission_caption_history_invalid')
        require(all(previous[k]==parent[k] for k in ('goal','quality_inputs','plan','employee_web','limits'))
                and body['model']==MODEL and body['endpoint']==ENDPOINT and body['free_only'] is True
                and body['mission_account']['account_project']==body['mission_web']['account_project']==MISSION_ACCOUNT
                and body['mission_account']['billing_disabled'] is True
                and body['mission_account']['free_data_policy']==DATA_POLICY, 'mission_caption_scope_invalid')
        tasks=previous['assignments'];writer=tasks[1];old=parent['assignments'][1]
        require(tasks[0]==parent['assignments'][0] and tasks[2]==parent['assignments'][2]
                and all(writer[k]==old[k] for k in ('id','role','title','depends_on','criteria_ids','instructions'))
                and writer['versions'][:1]==old['versions'] and writer['reviews'][:1]==old['reviews']
                and len(writer['versions'])==len(writer['reviews'])==2
                and writer['state']=='awaiting_ai_review' and writer['revisions']==1
                and writer['reviews'][-1]['action']=='accept' and not previous.get('final'), 'mission_caption_artifacts_invalid')
        attempts=previous['real_ai']['attempts']
        require(len(attempts)==2 and previous['active_operation']==attempts[-1]['id'], 'mission_caption_attempts_invalid')
        for attempt,phase,status in zip(attempts,('execute','review'),('validated','json_parsed')):
            require(attempt['phase']==phase and attempt['task_id']==writer['id'] and attempt['model']==MODEL
                    and attempt['status']=='completed' and attempt.get('http_status')==200
                    and attempt.get('response_hash') and attempt.get('free_account_policy_verified') is True
                    and attempt['role_result_status']==status,'mission_caption_attempts_invalid')
        inspection=inspect_script(parse(writer['versions'][-1]['content']),previous['quality_inputs']['target_segment'],
                                  mock=False,target_duration=25)
        require(inspection['defects'] and all(d['issue']=='caption_width' for d in inspection['defects']),
                'mission_caption_defects_invalid')
        ref=deepcopy(prior)
        ref.update(previous_job=previous['id'],previous_state_hash=previous['storage_hash'],previous_grant_hash=digest(grant),
            previous_reference_hash=digest(prior),new_purpose=new_purpose,
            duplicate_key=digest(dict(previous_job_id=previous['id'],new_purpose=new_purpose,writer_contract_hash=prior['writer_contract_hash'])),
            previous_attempt_ids=prior['previous_attempt_ids']+[a['id'] for a in parent['real_ai']['attempts'][1:]]+[a['id'] for a in attempts],
            consumed_calls=prior['consumed_calls']+len(attempts),writer_v2_hash=digest(writer['versions'][-1]),
            manager_latest_hash=digest(writer['reviews'][-1]),writer_history_hash=digest(writer['versions']),
            manager_history_hash=digest(writer['reviews']),historical_revisions=1,new_signed_revisions=1,
            revision_feedback='caption_width: '+__import__('json').dumps(inspection['defects'],ensure_ascii=False)+
                ' Server rejected the latest model accept. Revise the second scene caption (beat index 1, 39 width units) only as needed; preserve topic, narration, transcript, timeline and provenance. Follow the exact caption width system instructions.')
        return ref

    def unified_successor_reference(self, previous, *, new_purpose=UNIFIED_PURPOSE, _history_contract_hash=None):
        """A signed new-purpose receipt, never a replay or mutation of a stopped job.

        Historical schema hashes are accepted only while proving signed ancestors;
        check_scope always computes the current successor contract from server facts.
        """
        text(new_purpose,400)
        if new_purpose==CAPTION_REVISION_PURPOSE:
            return self.caption_revision_reference(previous,new_purpose)
        partial = previous.get('status')=='paused' and previous.get('reason_code')=='provider_unavailable'
        dns = (previous.get('reason_code') == 'free_request_failed'
               and previous.get('mission_unified_successor') is not None)
        require((partial or previous['status']=='stopped' and (previous.get('reason_code') in WRITER_FAILURES or dns))
                and (previous.get('mission_topic_successor') or previous.get('mission_unified_successor')),
                'mission_unified_not_eligible')
        grant=parse(self._grant_path(previous['id']).read_text())
        record=grant['record'];body=record['body']
        require(hmac.compare_digest(str(grant['signature']),self._sign(record))
                and record['id']==previous['real_ai']['consent'].get('operating_grant_id')
                and record['revoked_at'] is None, 'invalid_consent_signature')
        marker='mission_unified_successor' if previous.get('mission_unified_successor') else 'mission_topic_successor'
        prior=previous[marker]
        parent=self.load(prior['previous_job'])
        if marker=='mission_unified_successor':
            expected=self.unified_successor_reference(parent,new_purpose=prior['new_purpose'],
                _history_contract_hash=prior['writer_contract_hash'])
        else:
            require(previous['reason_code']=='invalid_script_shot','mission_unified_anchor_invalid')
            expected=self.topic_successor_reference(parent)
        require(digest(prior)==digest(expected) and body.get(marker)==prior
                and previous['goal']==parent['goal'] and previous['quality_inputs']==parent['quality_inputs']
                and previous['plan']==parent['plan'] and previous['employee_web']==parent['employee_web']
                and (partial or previous['assignments']==parent['assignments'])
                and previous['limits']==dict(max_calls=None,max_revisions_per_task=1,max_total_revisions=1),
                'mission_unified_history_changed')
        require(body['mission_account']['account_project']==body['mission_web']['account_project']==MISSION_ACCOUNT
                and body['mission_account']['billing_disabled'] is True and body['mission_account']['free_data_policy']==DATA_POLICY
                and body['model']==MODEL and body['endpoint']==ENDPOINT and body['free_only'] is True,
                'mission_unified_scope_changed')
        attempts=previous['real_ai']['attempts']
        if partial:
            require(previous==self.load(previous['id']) and new_purpose==PARTIAL_REVISION_PURPOSE
                    and prior['new_purpose']==DNS_PERMISSION_PURPOSE, 'mission_partial_scope_invalid')
            tasks=previous['assignments'];writer=tasks[1]
            require(tasks[0]==parent['assignments'][0] and tasks[2]==parent['assignments'][2]
                    and all(writer[k]==parent['assignments'][1][k] for k in ('id','role','title','depends_on','criteria_ids','instructions'))
                    and writer['state']=='revision_requested' and writer['revisions']==1
                    and len(writer['versions'])==len(writer['reviews'])==1
                    and writer['reviews'][0]['action']=='revise' and writer['reviews'][0]['feedback']
                    and len(attempts)==3 and not previous.get('final'), 'mission_partial_artifacts_invalid')
            for attempt,phase in zip(attempts[:2],('execute','review')):
                require(attempt['task_id']==writer['id'] and attempt['phase']==phase
                        and attempt['model']==MODEL and attempt['status']=='completed'
                        and attempt.get('http_status')==200 and attempt.get('response_hash')
                        and attempt.get('role_result_status')=='validated'
                        and attempt.get('free_account_policy_verified') is True, 'mission_partial_attempts_invalid')
            attempt=attempts[-1]
            require(attempt['task_id']==writer['id'] and attempt['phase']=='execute'
                    and attempt['model']==MODEL and attempt['status']=='failed'
                    and attempt.get('http_status')==503 and attempt.get('error_code')=='provider_unavailable'
                    and attempt.get('provider_error_diagnostics')==dict(category='5xx_server',stage='transport_open')
                    and attempt.get('transport_started_at') and not attempt.get('response_hash')
                    and not attempt.get('response_received_at') and attempt.get('role_result_status')=='unvalidated'
                    and previous['active_operation']==attempt['id'], 'mission_partial_attempts_invalid')
            from script_quality import validate_writer_contract
            selected=validate_selection(parse(tasks[0]['reviews'][-1]['feedback']),previous['employee_web'])
            validate_writer_contract(parse(writer['versions'][0]['content']),writer_contract(
                previous['quality_inputs']['target_segment'],selected['duration_seconds'],MODEL,selected['selected_topic']))
        else:
            require(len(attempts)==1 and attempts[0]['phase']=='execute'
                    and attempts[0]['task_id']==previous['assignments'][1]['id']
                    and attempts[0]['model']==MODEL
                    and previous['active_operation']==attempts[0]['id'] and not previous.get('final'),
                    'mission_unified_attempts_invalid')
            attempt=attempts[0]
            if dns:
                require(attempt['status']=='failed' and attempt.get('error_code')=='free_request_failed'
                        and attempt.get('provider_error_diagnostics')==dict(category='dns_error',stage='transport_open')
                        and attempt.get('transport_started_at') and not attempt.get('http_status')
                        and not attempt.get('response_hash') and not attempt.get('response_received_at')
                        and attempt.get('role_result_status')=='unvalidated'
                        and new_purpose==DNS_PERMISSION_PURPOSE
                        and prior.get('new_purpose')!=DNS_PERMISSION_PURPOSE,
                        'mission_dns_permission_scope_invalid')
            else:
                require(attempt['status']=='completed' and attempt.get('http_status')==200
                        and attempt.get('response_hash') and attempt.get('free_account_policy_verified') is True
                        and attempt['role_result_status']=='json_parsed', 'mission_unified_attempts_invalid')
        selection=validate_selection(parse(previous['assignments'][0]['reviews'][-1]['feedback']),previous['employee_web'])
        contract_hash=_history_contract_hash or digest(writer_contract(previous['quality_inputs']['target_segment'],
            selection['duration_seconds'],MODEL,selection['selected_topic']))
        require(isinstance(contract_hash,str) and len(contract_hash)==64 and all(c in '0123456789abcdef' for c in contract_hash),
                'mission_unified_contract_invalid')
        key=digest(dict(previous_job_id=previous['id'],new_purpose=new_purpose,writer_contract_hash=contract_hash))
        if partial or dns:
            require(contract_hash==prior['writer_contract_hash'], 'mission_dns_contract_changed')
        elif marker=='mission_unified_successor':
            require(contract_hash!=prior['writer_contract_hash'],
                    'mission_unified_unchanged_request')
        return dict(policy=UNIFIED_SUCCESSOR_POLICY,previous_job=previous['id'],previous_state_hash=previous['storage_hash'],
            previous_grant_hash=digest(grant),previous_reference_hash=digest(prior),
            anchor_job=prior.get('anchor_job',previous['id']),new_purpose=new_purpose,writer_contract_hash=contract_hash,
            duplicate_key=key,previous_attempt_ids=prior['previous_attempt_ids']+[attempts[0]['id']],
            consumed_calls=prior['consumed_calls']+len(attempts),
            **(dict(writer_v1_hash=digest(previous['assignments'][1]['versions'][0]),
                    manager_revise_hash=digest(previous['assignments'][1]['reviews'][0])) if partial else {}),new_max_calls=None,total_max_calls=None,
            consumed_searches=2,consumed_videos=2,new_max_searches=None,new_max_videos=None,
            execution_max_searches=0,execution_max_videos=0,total_max_searches=None,total_max_videos=None,
            account_project=MISSION_ACCOUNT,model=MODEL,endpoint=ENDPOINT,data_policy=DATA_POLICY,
            free_quota='unknown',billing_verification='unverified',automatic_retry=False,
            plan_hash=prior['plan_hash'],research_hash=prior['research_hash'],selection_hash=digest(selection),
            receipt_hash=prior['receipt_hash'],handoff=prior['handoff'])

    def check_scope(self, p):
        writer = _writer_reuse(p)
        expanded=p.get('mission_budget_writer')
        free=p.get('mission_free_writer')
        audience=p.get('mission_audience_successor')
        topic=p.get('mission_topic_successor')
        unified=p.get('mission_unified_successor')
        if writer:
            require(not p.get('mission_successor') and not p.get('mission_resume')
                    and sum(bool(p.get(k)) for k in ('mission_writer_resume','mission_budget_writer','mission_free_writer','mission_audience_successor','mission_topic_successor','mission_unified_successor'))==1, 'mission_writer_history_changed')
            previous=self.load(writer['previous_job'])
            expected=(self.unified_successor_reference(previous,new_purpose=writer['new_purpose']) if unified else
                      self.topic_successor_reference(previous) if topic else
                      self.audience_successor_reference(previous) if audience else
                      self.free_writer_reference(previous,explicit_max_calls=writer.get('explicit_max_calls')) if free else
                      self.budget_writer_reference(previous) if expanded else self.writer_reference(previous))
            require(digest(writer)==digest(expected)
                    and p['goal']==previous['goal'] and p['quality_inputs']==previous['quality_inputs']
                    and p['plan']==previous['plan'] and p['employee_web']==previous['employee_web']
                    and p['assignments'][0]==previous['assignments'][0], 'mission_writer_history_changed')
            require(len(p['assignments'])==3 and all(
                all(t[k]==original[k] for k in ('id','role','title','depends_on','criteria_ids','instructions'))
                for t,original in zip(p['assignments'],previous['assignments'])), 'mission_writer_history_changed')
            if unified and writer['new_purpose']==PARTIAL_REVISION_PURPOSE:
                inherited=previous['assignments'][1];current=p['assignments'][1]
                require(current['versions'][:1]==inherited['versions'] and current['reviews'][:1]==inherited['reviews']
                        and current['revisions']==1, 'mission_partial_inheritance_changed')
            if unified and writer['new_purpose']==CAPTION_REVISION_PURPOSE:
                inherited=previous['assignments'][1];current=p['assignments'][1]
                require(current['versions'][:2]==inherited['versions'] and current['reviews'][:2]==inherited['reviews']
                        and current['revisions']==2, 'mission_caption_inheritance_changed')
            studio=Store(self.root.parent).load(p['quality_inputs']['answers']['representative_project'])
            require(studio['representative']['mission_one_job']==p['id'], 'mission_resume_detached')
        successor = p.get('mission_successor')
        if successor:
            require(not p.get('mission_resume'), 'mission_successor_history_changed')
            previous = self.load(successor['previous_job'])
            require(digest(successor)==digest(self.successor_reference(previous))
                    and p['goal']==previous['goal'] and p['quality_inputs']==previous['quality_inputs'],
                    'mission_successor_history_changed')
            studio = Store(self.root.parent).load(p['quality_inputs']['answers']['representative_project'])
            require(studio['representative']['mission_one_job']==p['id'], 'mission_resume_detached')
            require(p['plan']==previous['plan'] and p['employee_web']==previous['employee_web']
                    and p['assignments'][0]['versions']==previous['assignments'][0]['versions'],
                    'mission_successor_reuse_changed')
        resume = p.get('mission_resume')
        if resume is not None:
            previous = self.load(resume['previous_job'])
            require(digest(resume) == digest(self.resume_reference(previous))
                    and p['goal'] == previous['goal']
                    and p['quality_inputs'] == previous['quality_inputs'], 'mission_resume_history_changed')
            studio = Store(self.root.parent).load(p['quality_inputs']['answers']['representative_project'])
            require(studio['representative'].get('mission_one_job') == p['id'], 'mission_resume_detached')
        quality = p['quality_inputs']
        capabilities = {'script_contract': SCRIPT_CONTRACT, 'mission': SCOPE}
        if p['goal'] == GAME_GOAL:
            capabilities['editorial_scope'] = GAME_SCOPE
            if quality['capabilities'].get('employee_web_research') == WEB_TOOL:
                capabilities['employee_web_research'] = WEB_TOOL
            require(set(quality['answers']) == {'audience', 'representative_project'}
                    and 'duration_seconds' not in quality['constraints']
                    and all(quality['constraints'].get(key) == value for key, value in
                            dict(aspect='9:16', language='한국어', platform='YouTube Shorts').items()),
                    'mission_game_scope_mismatch')
        require(quality['capabilities'] == capabilities
                and p['limits'] == dict(max_calls=None if unified or topic or audience else free['explicit_max_calls'] if free else 13 if expanded else 4 if writer else 6 if successor else MAX_CALLS-1 if resume else MAX_CALLS, max_revisions_per_task=2 if unified and unified['new_purpose']==CAPTION_REVISION_PURPOSE else 1,
                    max_total_revisions=2 if unified and unified['new_purpose']==CAPTION_REVISION_PURPOSE else 1)
                and not p.get('local_tools'), 'mission_scope_mismatch')

    @staticmethod
    def _check_mission_account(value, max_calls=MAX_CALLS):
        exact(value, ('account_project', 'remaining_requests', 'quota_note', 'credential_binding',
                      'billing_disabled', 'free_data_policy', 'approved_max_calls'))
        text(value['account_project'], 200)
        text(value['quota_note'], 500)
        quota_observation(value['remaining_requests'])
        require((value['approved_max_calls'] is None if max_calls is None else
                 type(value['approved_max_calls']) is int and value['approved_max_calls'] == max_calls)
                and value['billing_disabled'] is True and value['free_data_policy'] == DATA_POLICY
                and isinstance(value['credential_binding'], str) and len(value['credential_binding']) == 64,
                'mission_free_account_unverified')

    def _check_contract(self, p, body):
        require(isinstance(body, dict), 'invalid_fields')
        self.check_scope(p)
        if p['goal'] == GAME_GOAL:
            require(p['quality_inputs']['capabilities'].get('employee_web_research') == WEB_TOOL, GAME_RESEARCH_BLOCKER)
            require(body.get('mission_research_review') == research_review_policy(), 'mission_research_review_consent')
            web = body.get('mission_web')
            exact(web, ('policy','account_project','search_remaining','general_units_remaining',
                        'credential_binding','free_usage_verified','policy_confirmed',
                        'approved_max_searches','approved_max_videos'))
            text(web['account_project'],200)
            quota_observation(web['search_remaining'])
            quota_observation(web['general_units_remaining'])
            require(web['policy']==WEB_POLICY and web['free_usage_verified'] is True
                    and web['policy_confirmed'] is True
                    and type(web['approved_max_searches']) is int and web['approved_max_searches'] == (_web_limit(p))
                    and type(web['approved_max_videos']) is int and web['approved_max_videos'] == (_web_limit(p))
                    and isinstance(web['credential_binding'],str),
                    'employee_web_scope_unverified')
        else:
            require('mission_web' not in body,'mission_scope_mismatch')
        require(body.get('mission_successor') == p.get('mission_successor'), 'mission_successor_consent_mismatch')
        require(body.get('mission_resume') == p.get('mission_resume'), 'mission_resume_consent_mismatch')
        require(body.get('mission_writer_resume')==p.get('mission_writer_resume'), 'mission_writer_consent_mismatch')
        require(body.get('mission_budget_writer')==p.get('mission_budget_writer'), 'mission_budget_writer_consent_mismatch')
        require(body.get('mission_free_writer')==p.get('mission_free_writer'), 'mission_free_writer_consent_mismatch')
        require(body.get('mission_audience_successor')==p.get('mission_audience_successor'), 'mission_audience_successor_consent_mismatch')
        require(body.get('mission_topic_successor')==p.get('mission_topic_successor'), 'mission_topic_successor_consent_mismatch')
        require(body.get('mission_unified_successor')==p.get('mission_unified_successor'), 'mission_unified_consent_mismatch')
        if _writer_reuse(p):
            old=parse(self._grant_path(_writer_reuse(p)['previous_job']).read_text())['record']['body']
            require(body['mission_account']['account_project']==old['mission_account']['account_project']
                    and body['mission_web']['account_project']==old['mission_web']['account_project'],
                    'mission_writer_account_changed')
        self._check_mission_account(body.get('mission_account'), p['limits']['max_calls'])
        super()._check_contract(p, {k:v for k,v in body.items() if k not in ('mission_account','mission_web','mission_resume','mission_research_review','mission_successor','mission_writer_resume','mission_budget_writer','mission_free_writer','mission_audience_successor','mission_topic_successor','mission_unified_successor')})


def validate_research(value):
    exact(value, ('candidates', 'selected_topic', 'selection_reason', 'uncertainty'))
    for key in ('selected_topic', 'selection_reason', 'uncertainty'):
        text(value[key], 800)
    candidates = value['candidates']
    require(isinstance(candidates, list) and 2 <= len(candidates) <= 4, 'mission_research_candidates')
    topics = []
    for candidate in candidates:
        exact(candidate, ('topic', 'rationale', 'evidence_status'))
        text(candidate['topic'], 200)
        text(candidate['rationale'], 500)
        require(candidate['evidence_status'] == 'unverified', 'mission_research_evidence_unverified')
        topics.append(candidate['topic'])
    require(len(set(topics)) == len(topics) and value['selected_topic'] in topics, 'mission_research_selection')
    return value


def research_review_schema():
    """Mission-only wire contract; feedback stays prose, selection is an object."""
    schema = deepcopy(response_format('review')['json_schema']['schema'])
    selection = obj(game=S, selected_topic=S, duration_seconds={'type':'integer'},
                    duration_reason=S, selection_reason=S, other_candidates_reason=S,
                    evidence_ids=arr(S), shorts_status=S, rights_plan=S)
    review = schema['properties']['result']
    review['properties']['selection'] = {'anyOf':[selection, {'type':'null'}]}
    review['required'].append('selection')
    return schema


def research_review_policy():
    return dict(version=1, schema_hash=digest(research_review_schema()),
                storage='validated_selection_json_in_feedback', automatic_repair=False)


class MissionOneCompany(VideoProviderQualityCompany):
    store_type = MissionOneStore
    allowed_video_roles = ('research', 'writer', 'editor')

    def _prepare_payload(self, payload):
        wire = super()._prepare_payload(payload)
        if getattr(self, '_research_review_state', None) is not None:
            wire['generationConfig']['responseJsonSchema'] = research_review_schema()
            message = parse(wire['contents'][0]['parts'][0]['text'])
            message['output_contract'] = research_review_schema()
            wire['contents'][0]['parts'][0]['text'] = json.dumps(message, ensure_ascii=False)
        contract=getattr(self,'_writer_wire_contract',None)
        if contract is not None:
            schema=obj(result=obj(content=deepcopy(contract['schema']),evidence=S,uncertainty=S))
            wire['generationConfig']['responseJsonSchema']=schema
            message=parse(wire['contents'][0]['parts'][0]['text'])
            message['output_contract']=schema
            wire['contents'][0]['parts'][0]['text']=json.dumps(message,ensure_ascii=False)
            system=wire['systemInstruction']['parts'][0]
            system['text']=system['text'].replace('Writer/editor/voice content must be a JSON string','Editor/voice content must be a JSON string')
            system['text']+=' WRITER NATIVE CONTRACT: result.content MUST be a JSON object, not a JSON string. Follow quality.writer_contract.schema and all quality.writer_contract.invariants. These exact dynamic constraints override generic writer guidance.'
            system['text']+=' '+contract.get('audience_output_instruction','')
        return wire

    def _validate_payload(self, payload):
        if getattr(self, '_research_review_state', None) is not None:
            require(digest(payload['generationConfig']['responseJsonSchema']) == digest(research_review_schema()),
                    'mission_research_payload_contract')
            payload = deepcopy(payload)
            payload['generationConfig']['responseJsonSchema'] = response_format('review')['json_schema']['schema']
        contract=getattr(self,'_writer_wire_contract',None)
        if contract is not None:
            schema=obj(result=obj(content=deepcopy(contract['schema']),evidence=S,uncertainty=S))
            message=parse(payload['contents'][0]['parts'][0]['text'])
            require(digest(payload['generationConfig']['responseJsonSchema'])==digest(schema)
                    and digest(message['output_contract'])==digest(schema)
                    and digest(message['data']['quality']['writer_contract'])==digest(contract), 'mission_writer_payload_contract')
            payload=deepcopy(payload)
            payload['generationConfig']['responseJsonSchema']=response_format('execute')['json_schema']['schema']
        return super()._validate_payload(payload)

    def _research_error(self, raw, stage, code):
        p = self._research_review_state
        entry = p['real_ai']['attempts'][-1]
        entry['mission_review_diagnostics'] = dict(stage=stage, category=code,
            content_bytes=len(raw.encode()), content_hash=digest(raw))
        self.store.save(p)

    def _parse_role_content(self, raw, phase):
        if getattr(self,'_writer_wire_contract',None) is not None:
            require(phase=='execute','mission_writer_payload_contract')
            try:
                value=parse(raw);exact(value,('result',));result=value['result'];exact(result,('content','evidence','uncertainty'))
                require(isinstance(result['content'],dict),'writer_object_required')
                # Lossless serialization only: the shared engine stores content as text.
                return {**result,'content':json.dumps(result['content'],ensure_ascii=False)}
            except CompanyError as exc:
                p=self._writer_wire_state
                entry=p['real_ai']['attempts'][-1]
                entry['script_validation_diagnostics']=dict(stage='writer_wire_contract',category=exc.code,
                    error_code=exc.code,field_path='result.content',response_hash=digest(raw))
                self.store.save(p)
                raise
        if getattr(self, '_research_review_state', None) is None:
            return super()._parse_role_content(raw, phase)
        try:
            value = parse(raw)
        except CompanyError as exc:
            self._research_error(raw, 'research_review_json', exc.code)
            raise CompanyError('mission_research_review_json_invalid') from None
        if not matches(value, research_review_schema()):
            self._research_error(raw, 'research_review_structure', 'invalid_role_schema')
            raise CompanyError('mission_research_review_structure_invalid')
        result = value['result']
        selection = result.pop('selection')
        if result['action'] == 'accept':
            try:
                validate_selection(selection, self._research_review_state.get('employee_web'))
            except CompanyError as exc:
                self._research_error(raw, 'research_selection_validation', exc.code)
                raise CompanyError('mission_research_selection_invalid') from None
            # Explicit validated-object serialization for the existing engine's text review storage.
            result['feedback'] = json.dumps(selection, ensure_ascii=False, sort_keys=True)
        elif selection is not None:
            self._research_error(raw, 'research_selection_validation', 'selection_requires_accept')
            raise CompanyError('mission_research_selection_invalid')
        return result

    def _quality_transport_allowed(self, p):
        self.store.check_scope(p)
        if p.get('mission_successor') or _writer_reuse(p):
            require(p['plan']['source']==self.source, 'mission_successor_provenance')
        if p['goal'] == GAME_GOAL:
            require(p['quality_inputs']['capabilities'].get('employee_web_research') == WEB_TOOL, GAME_RESEARCH_BLOCKER)
            self._authorize_web(p)
        if _writer_reuse(p):
            old_id=_writer_reuse(p)['previous_job']
            old=parse(self.store._grant_path(old_id).read_text())['record']['body']
            require(hmac.compare_digest(old['mission_account']['credential_binding'],_binding(old_id,self.config.api_key))
                    and hmac.compare_digest(old['mission_web']['credential_binding'],
                        _binding(old_id+':youtube',os.getenv('YOUTUBE_DATA_API_KEY',''))), 'mission_key_binding_mismatch')
        if p.get('mission_unified_successor'):
            anchor=p['mission_unified_successor']['anchor_job']
            original=parse(self.store._grant_path(anchor).read_text())['record']['body']
            require(hmac.compare_digest(original['mission_account']['credential_binding'],_binding(anchor,self.config.api_key))
                    and hmac.compare_digest(original['mission_web']['credential_binding'],
                        _binding(anchor+':youtube',os.getenv('YOUTUBE_DATA_API_KEY',''))), 'mission_key_binding_mismatch')
        account = self.store.grant(p)['body']['mission_account']
        require(hmac.compare_digest(account['credential_binding'], _binding(p['id'], self.config.api_key)),
                'mission_key_binding_mismatch')
        return True

    def _open_transport(self, request, timeout):
        return send_once(request, timeout)

    def _run(self, project_id, *, expected_state_hash, resume=False):
        require(resume is False, 'mission_restart_forbidden')
        p = self.store.load(project_id)
        if p['status'] != 'needs_user_review':
            require(p['status'] == 'ready' and not p['sessions'] and not p['real_ai']['attempts'],
                    'mission_restart_forbidden')
        return super()._run(project_id, expected_state_hash=expected_state_hash, resume=False)

    def _authorize_web(self, p):
        body = self.store.grant(p)['body']
        key = os.getenv('YOUTUBE_DATA_API_KEY', '')
        require(hmac.compare_digest(body['mission_web']['credential_binding'], _binding(p['id']+':youtube', key)),
                'employee_web_key_mismatch')
        return key

    def _manager_selection(self, p):
        if p['goal'] != GAME_GOAL:
            return None
        research = next((t for t in p['assignments'] if t['role']=='research'
                         and t['state']=='accepted_by_ai_manager'),None)
        if not research:
            return None
        return validate_selection(parse(research['reviews'][-1]['feedback']), p.get('employee_web'))

    def _script_duration(self, p):
        decision = self._manager_selection(p)
        return decision['duration_seconds'] if decision else 60

    def _tool_notice(self, p):
        notice = super()._tool_notice(p) + AUDIENCE_INSTRUCTIONS
        if p['goal']==GAME_GOAL:
            notice += (' Writer field binding: topic.title = quality.manager_selection.selected_topic. '
                'Copy this supplied string character-for-character, including whitespace and punctuation; '
                'it identifies the AI manager-approved topic, not a viewer-facing headline. '
                'Do not shorten, paraphrase, translate or reselect it. Write creative viewer-facing copy '
                'in the existing hook_0_3s, promise or viewing_reason fields, never in topic.title. '
                'The exact dynamic selected_topic is supplied in the quality.manager_selection context; '
                'do not infer it from the game name or research summary.')
        if _writer_reuse(p):
            return (notice.replace('60초','목표 길이').replace('target_duration=60','target_duration=quality.manager_selection.duration_seconds')+
                ' Writer-stage successor: reuse the authenticated original plan, research and manager_selection '
                'with original evidence IDs, topic, game and duration. Do not select a new topic, game or duration. '
                'Start at writer; no research or new web batch is allowed. Korean narration/captions and '
                'pending visual sources are required. Writer and editor each receive manager review. '
                'After acceptance the system assembles a human-review handoff, not a new AI final evaluation. '+
                ('No arbitrary call counter; respect provider free quota/rate limits and stop on errors. '
                 if p['limits']['max_calls'] is None else f'{p["limits"]["max_calls"]} new Gemini calls maximum. ')+
                'Internal counters are not provider free quota. No retries, paid fallback, media or representative approval.')
        if p.get('mission_successor'):
            notice += (' The validated prior manager plan and employee research are reused with original timestamps '
                       'and receipt evidence. Research is pending your NEW structured review, not approved. '
                       'Do not claim new web observations or prior manager selection. No new research execution '
                       'is available in this successor; if inadequate stop. Revisions consume the same six-call cap.')
        if p['goal'] == GAME_GOAL:
            return (notice.replace('60초','목표 길이').replace('target_duration=60','target_duration=quality.manager_selection.duration_seconds')+
                ' Research employee constructs its OWN search queries from the representative goal. No game, '
                'ranking, topic or duration is preselected. Exactly research then writer then editor, with dependencies. '
                'Research execute.content must be JSON {tool:"'+WEB_TOOL+'",queries:[{query,purpose,lookback_days,order}]}; '
                '1–4 queries, purpose game_interest|shorts_examples, lookback_days integer 1–30, '
                'order relevance|date|viewCount. System uses YouTube public API top 5 gaming results per query '
                'in KR with Korean relevance. No arbitrary URL fetch or media download. This tool is available '
                'only once for research; failures stop, never repeat the batch. Tool receipt will be in evidence. '
                'Manager reviews observed metadata and evidence limits. For research review keep feedback as prose and '
                'return selection as a JSON OBJECT {game,selected_topic,duration_seconds,duration_reason,selection_reason,other_candidates_reason,'
                'evidence_ids,shorts_status:"unverified",rights_plan} on accept; selection must be null otherwise. Never encode selection in feedback. Choose duration from observed lengths and '
                'story needs, not a preset. Technical validation supports 4–180 seconds, no recommended duration. '
                'Public API does not confirm vertical aspect or Shorts classification. Its short filter includes '
                'non-Shorts; preserve uncertainty and never equate queried views with global game popularity or '
                'growth. Missing/private/non-gaming/outdated samples cannot support the selection. '
                'Writer follows quality.manager_selection for topic and duration. Keep visual sources pending, '
                'Korean full narration and captions; apply the specified versus unspecified audience policy; rights unverified. '
                'Use evidence_ids only from the tool receipt. Finalize deliver after internal acceptance; '
                'no production, TTS, uploading, publication or representative approval.')
        return (notice +
            ' MISSION 01: planning only. Use exactly one research task, one writer depending on research, '
            'and one editor depending on writer. Research compares 2–4 original topics and outputs JSON '
            '{candidates:[{topic,rationale,evidence_status:"unverified"}],selected_topic,selection_reason,uncertainty}. '
            'No search or supplied verified sources exist for this run. Do not cite invented URLs, dates, rankings, '
            'rights, or real match results. No prior topic was approved. Frame examples as fictional or evergreen, '
            'use illustrative facts or verification_pending, and leave every visual source pending. '
            'Apply the specified versus unspecified audience policy in the script. '
            'Write the full Korean script. The writer topic.title must match the selected research topic verbatim. '
            'The editor output is a storyboard handoff, never a tool or video request. '
            'After all three tasks are accepted, use finalize action=deliver for a text-only representative handoff. '
            'The application stops delivery at human review; do not claim approval or generate media.')

    def _call(self, p, provider, phase, task_id, context):
        if _writer_reuse(p) and phase=='finalize':
            self.store.grant(p)
            require(all(t['state']=='accepted_by_ai_manager' and t['reviews'][-1]['action']=='accept'
                        for t in p['assignments']), 'mission_internal_review_incomplete')
            checks=[]
            for criterion in p['plan']['criteria']:
                claims=[c for t in p['assignments'] for c in t['reviews'][-1]['checks']
                        if c['criterion_id']==criterion['id']]
                require(claims and all(c['status']=='met' for c in claims), 'final_quality_unverified')
                checks.append(deepcopy(claims[-1]))
            return dict(action='deliver',content='수락된 조사·대본·편집 결과를 대표 검토용으로 묶었습니다. 새 AI 최종 평가는 수행하지 않았습니다.',
                rationale='기존 관리자 선정 및 각 업무의 관리자 수락 기록 참조',
                uncertainty='대상 시청자 제안·Shorts 형식·영상 사용권·성과는 사용자 확인 필요',checks=checks,
                task_refs=[dict(task_id=r['task_id'],revision=r['revision'],result_hash=digest(r)) for r in context['results']])
        self._research_review_state = (p if p['goal'] == GAME_GOAL and phase == 'review'
            and context['assignment']['role'] == 'research' else None)
        try:
            return self._mission_call(p, provider, phase, task_id, context)
        except CompanyError as exc:
            if (phase=='execute' and context['assignment']['role']=='writer'
                    and exc.code in ('script_audience_mismatch','script_audience_inference_required')
                    and p['real_ai']['attempts']):
                entry = p['real_ai']['attempts'][-1]
                entry.setdefault('script_validation_diagnostics',{}).update(stage='writer_script_validation',
                    category=exc.code, field='target_audience',
                    audience_unspecified=p['quality_inputs']['target_segment']=='미정',
                    response_bytes=entry.get('response_diagnostics',{}).get('response_bytes'),
                    response_hash=entry.get('response_hash'))
                if exc.code=='script_audience_inference_required':
                    entry['script_validation_diagnostics']['detail_code']=getattr(exc,'detail_code','inference_marker_missing')
                self.store.save(p)
            raise
        finally:
            self._research_review_state = None

    def _mission_call(self, p, provider, phase, task_id, context):
        if p.get('mission_successor') or _writer_reuse(p):
            require(not (phase=='execute' and context['assignment']['role']=='research'),
                    'mission_cached_research_revision_requires_new_approval')
        continuation=p.get('mission_unified_successor',{})
        if (continuation.get('new_purpose')==CAPTION_REVISION_PURPOSE and phase=='execute'
                and context['assignment']['role']=='writer'):
            context={**context,'revision_feedback':continuation['revision_feedback']}
        selection = self._manager_selection(p)
        if selection:
            context = {**context,'quality':{**context['quality'],'manager_selection':selection}}
        contract=(writer_contract(p['quality_inputs']['target_segment'],selection['duration_seconds'],self.bound_model,
                    selection['selected_topic']) if selection and phase=='execute' and context['assignment']['role']=='writer' else None)
        if contract:
            context={**context,'quality':{**context['quality'],'writer_contract':contract}}
        self._writer_wire_contract=contract
        self._writer_wire_state=p if contract else None
        try:
            result = super()._call(p, provider, phase, task_id, context)
        finally:
            self._writer_wire_contract=None
            self._writer_wire_state=None
        game = p['goal'] == GAME_GOAL
        if game and phase=='review' and context['assignment']['role']=='research' and result['action']=='accept':
            validate_selection(parse(result['feedback']),p.get('employee_web'))
        if phase == 'plan' and 'tasks' in result:
            roles = {task['role']:task for task in result['tasks']}
            require(len(result['tasks']) == 3 and set(roles) == set(ROLES)
                    and roles['research']['id'] in roles['writer']['depends_on'], 'mission_research_dependency')
        if phase == 'execute':
            role = context['assignment']['role']
            content = parse(result['content'])
            if role == 'research':
                if game:
                    validate_queries(content)
                    receipt = collect(self.store,p,task_id,content,self._authorize_web(p),
                                      lambda:self._authorize_web(p),provenance=self.source)
                    result['evidence'] += '\nEMPLOYEE_WEB_RECEIPT '+json.dumps(receipt['observations'],ensure_ascii=False)
                    result['evidence'] += '\nreceipt_hash='+receipt['receipt_hash']
                else:
                    validate_research(content)
            elif role == 'writer':
                research = next(r for r in context['previous_results'] if r['role'] == 'research')
                chosen = selection if game else validate_research(parse(research['content']))
                title,expected=content['topic']['title'],chosen['selected_topic']
                if title!=expected:
                    normalize=lambda v:' '.join(unicodedata.normalize('NFKC',v).split()).casefold()
                    entry=p['real_ai']['attempts'][-1]
                    entry['script_validation_diagnostics']=dict(stage='writer_selected_topic_validation',
                        category='mission_selected_topic_mismatch',exact_match=False,
                        normalized_match=normalize(title)==normalize(expected),
                        expected_length=len(expected),returned_length=len(title),
                        expected_title_hash=digest(expected),returned_title_hash=digest(title),
                        response_hash=entry.get('response_hash'))
                    self.store.save(p)
                    require(False,'mission_selected_topic_mismatch')
                require(all(beat['source_status'] == 'pending' for beat in content['narrative_beats']),
                        'mission_visual_source_unverified')
        return result

    def _delivery_blockers(self, p):
        if _writer_reuse(p):
            p['final'].update(provider='system',source='accepted_review_handoff')
            p['events'][-1].update(event='system_review_handoff',actor='system')
        return ['needs_user_review']


def checked_result(job, *, allow_fixture=False):
    if job['goal']==GAME_GOAL:
        require(job['quality_inputs']['capabilities'].get('employee_web_research')==WEB_TOOL,GAME_RESEARCH_BLOCKER)
    attempts = job['real_ai']['attempts']
    require(job['status'] == job.get('reason_code') == 'needs_user_review' and job['final']
            and not job['artifacts'] and not job['active_operation']
            and (4 if _writer_reuse(job) else 6 if job.get('mission_successor') else 8) <= len(attempts)
            and (job['limits']['max_calls'] is None or len(attempts)<=job['limits']['max_calls']),
            'mission_internal_review_incomplete')
    require(all(a['status'] == 'completed' and a.get('http_status') == 200 and a['model'] == MODEL
                and a['role_result_status'] == 'validated' and a.get('response_hash')
                and a.get('transport_started_at') and a.get('free_account_policy_verified') is True
                for a in attempts), 'mission_provider_evidence_incomplete')
    tasks = {t['role']:t for t in job['assignments']}
    require(set(tasks) == set(ROLES) and len(job['assignments']) == 3
            and all(t['state'] == 'accepted_by_ai_manager' and t['versions'] and t['reviews'][-1]['action'] == 'accept'
                    for t in tasks.values()), 'mission_internal_review_incomplete')
    source = job['final']['source']
    if _writer_reuse(job):
        require(source=='accepted_review_handoff' and job['final']['provider']=='system', 'mission_provider_evidence_incomplete')
        source=job['plan']['source']
    require(source == 'provider_model_claim' or allow_fixture and source == 'offline_http_fixture',
            'mission_provider_evidence_incomplete')
    require(all(v['source'] == source for task in tasks.values() for v in task['versions']),
            'mission_provider_evidence_incomplete')
    duration = 60
    if job['goal']==GAME_GOAL:
        observations = usable_observations(job.get('employee_web'))
        decision = validate_selection(parse(tasks['research']['reviews'][-1]['feedback']),job['employee_web'])
        duration = decision['duration_seconds']
        research = dict(candidates=[dict(topic=decision['selected_topic'],rationale=decision['selection_reason'])],
            selected_topic=decision['selected_topic'],selection_reason=decision['selection_reason'],
            uncertainty='Shorts 형식·채널 규모·증가율·사용권 미확인', manager_decision=decision,
            observations=observations, tool_receipt_hash=job['employee_web']['receipt_hash'])
    else:
        research = validate_research(parse(tasks['research']['versions'][-1]['content']))
    if _writer_reuse(job):
        research['reuse']=dict(source_job=_writer_reuse(job)['previous_job'],
            receipt_hash=_writer_reuse(job)['receipt_hash'],newly_observed=False,
            plan_hash=_writer_reuse(job)['plan_hash'],
            selection_hash=_writer_reuse(job)['selection_hash'],final_evaluation='not_performed_local_handoff')
    if job.get('mission_successor'):
        research['reuse'] = dict(source_job=job['mission_successor']['previous_job'],
            receipt_hash=job['mission_successor']['receipt_hash'], newly_observed=False,
            plan_hash=job['mission_successor']['plan_hash'])
    script = parse(tasks['writer']['versions'][-1]['content'])
    inspection = inspect_script(script, job['quality_inputs']['target_segment'], mock=False,target_duration=duration)
    require(not inspection['defects'] and script['provenance']['model'] == MODEL
            and script['topic']['title'] == research['selected_topic'], 'mission_script_not_ready')
    return research, source


def provider_view(job):
    fields = ('phase', 'task_id', 'role_kind', 'provider', 'model', 'status', 'http_status', 'reserved_at',
              'response_received_at', 'finished_at', 'request_hash', 'response_hash', 'cost_basis')
    attempts = [{**{k:a[k] for k in fields if k in a},
                 'usage':a.get('response_diagnostics', {}).get('tokens', {})}
                for a in job['real_ai']['attempts']]
    reason = job.get('reason_code')
    if job['goal'] == GAME_GOAL:
        scope = job['quality_inputs']['capabilities'].get('editorial_scope')
        if (job.get('employee_web') or {}).get('status') == 'failed_or_uncertain':
            reason = 'employee_web_failed_no_retry'
        elif job['quality_inputs']['capabilities'].get('employee_web_research') == WEB_TOOL:
            reason = reason or ('employee_web_authorization_required' if not job['real_ai']['consent'] else None)
        else:
            reason = GAME_RESEARCH_BLOCKER if scope == GAME_SCOPE else 'mission_old_scope_superseded'
    return dict(id=job['id'], status=job['status'], reason=reason, model=MODEL,
                attempts=attempts, authorized=job['real_ai']['consent'].get('approved') is True,
                assignments=[dict(role=t['role'], state=t['state'], versions=len(t['versions']))
                             for t in job['assignments']])


def main():
    from representative_workflow import RepresentativeVideoWorkflow
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('action', choices=('create-validated-successor','create-topic-successor','create-audience-successor','create-free-writer-resume','create-budget-writer-resume','create-writer-resume','create-successor','create-resume','connect-web','prepare', 'approve', 'run'))
    parser.add_argument('project')
    parser.add_argument('--confirm-new-execution', action='store_true')
    parser.add_argument('--new-purpose',default=UNIFIED_PURPOSE)
    parser.add_argument('--explicit-max-calls',type=int,help='Optional owner-specified limit for create-free-writer-resume; default none.')
    parser.add_argument('--account-project')
    parser.add_argument('--remaining-requests', type=int, help='Observed provider balance; omit for unknown. Not the approved call cap.')
    parser.add_argument('--quota-note')
    parser.add_argument('--youtube-project')
    parser.add_argument('--youtube-searches-remaining',type=int, help='Observed balance; omit for unknown.')
    parser.add_argument('--youtube-units-remaining',type=int, help='Observed balance; omit for unknown.')
    parser.add_argument('--confirm-youtube-policy',action='store_true')
    parser.add_argument('--proposal', type=Path)
    parser.add_argument('--review-hash')
    parser.add_argument('--confirm-free-account', action='store_true')
    parser.add_argument('--confirm-free-data-policy', action='store_true')
    args = parser.parse_args()
    workflow = RepresentativeVideoWorkflow(Store(args.root))
    # -m loads this file as __main__; report_plan requires the canonical store class.
    from video_mission_one import MissionOneStore as CanonicalMissionOneStore
    store = CanonicalMissionOneStore(workflow.store.root/'mission_one_provider')
    try:
        if args.action=='create-validated-successor':
            print(workflow.stage_mission_validated_successor(args.project,owner_confirmed=args.confirm_new_execution,new_purpose=args.new_purpose))
            return
        if args.action=='create-topic-successor':
            print(workflow.stage_mission_topic_successor(args.project,owner_confirmed=args.confirm_new_execution))
            return
        if args.action=='create-audience-successor':
            print(workflow.stage_mission_audience_successor(args.project,owner_confirmed=args.confirm_new_execution))
            return
        if args.action=='create-free-writer-resume':
            print(workflow.stage_mission_free_writer_resume(args.project,owner_confirmed=args.confirm_new_execution,
                explicit_max_calls=args.explicit_max_calls))
            return
        if args.action=='create-budget-writer-resume':
            print(workflow.stage_mission_budget_writer_resume(args.project,owner_confirmed=args.confirm_new_execution))
            return
        if args.action=='create-writer-resume':
            print(workflow.stage_mission_writer_resume(args.project,owner_confirmed=args.confirm_new_execution))
            return
        if args.action=='create-successor':
            print(workflow.stage_mission_successor(args.project, owner_confirmed=args.confirm_new_execution))
            return
        if args.action=='create-resume':
            print(workflow.stage_mission_resume(args.project, owner_confirmed=args.confirm_new_execution))
            return
        if args.action=='connect-web':
            print(workflow.connect_employee_web(args.project))
            return
        p = workflow.store.load(args.project)
        pid = p['representative'].get('mission_one_job')
        require(pid is not None, 'mission_stage_in_studio_first')
        require(p['goal'] == GAME_GOAL, 'mission_game_goal_required')
        config = Gemini35Config.from_env()
        if args.action == 'prepare':
            require(args.confirm_free_account, 'mission_free_account_unverified')
            body = store.prepare_mission(pid, key=config.api_key, account_project=args.account_project,
                                         remaining_requests=args.remaining_requests, quota_note=args.quota_note,
                youtube_key=os.getenv('YOUTUBE_DATA_API_KEY',''),youtube_project=args.youtube_project,
                search_remaining=args.youtube_searches_remaining,units_remaining=args.youtube_units_remaining,
                confirm_youtube_policy=args.confirm_youtube_policy)
            print(json.dumps(dict(review_hash=digest(body), proposal=body, goal=p['goal'],
                input=store.load(pid)['quality_inputs']), ensure_ascii=False, indent=2))
        elif args.action == 'approve':
            require(args.proposal is not None and args.review_hash and args.confirm_free_data_policy,
                    'explicit_owner_confirmation_required')
            body = parse(args.proposal.read_text())['proposal']
            require(hmac.compare_digest(body['mission_account']['credential_binding'], _binding(pid, config.api_key)),
                    'mission_key_binding_mismatch')
            store.approve(pid, body, review_hash=args.review_hash, owner_confirmed=True)
            print('별도 외부 전송 승인 저장. 모델 호출 0회.')
        else:
            job = store.load(pid)
            if job['status'] != 'needs_user_review':
                require(job['status'] == 'ready' and not job['real_ai']['attempts'] and not job['sessions'],
                        'mission_restart_forbidden')
                company = MissionOneCompany(store, LiveManagerProvider('gemini-manager'),
                    LiveEmployeeProvider('gemini-staff'), config)
                job = company.run(pid, expected_state_hash=job['storage_hash'])
            require(job['status'] == 'needs_user_review', job.get('reason_code', 'mission_internal_review_incomplete'))
            report = workflow.report_plan(args.project, provider_store=store)
            print(json.dumps(dict(state='awaiting_plan_approval', version=report['version'],
                                  sha256=report['sha256']), ensure_ascii=False))
    except CompanyError as exc:
        parser.exit(1, exc.code+'\n')


if __name__ == '__main__':
    main()
