"""Mission 01's scoped entry to the existing signed video provider workflow."""
import argparse
import hmac
import json
import os
from pathlib import Path

from autonomous_company import CompanyError, Store, digest, exact, parse, require, text
from autonomous_gemini35 import Gemini35Config, MODEL, ENDPOINT
from autonomous_live import LiveEmployeeProvider, LiveManagerProvider
from goal_dialogue_live import send_once
from employee_web_research import (TOOL as WEB_TOOL, POLICY as WEB_POLICY, collect,
    validate_queries, validate_selection, usable_observations)
from quality_provider import QualityProviderStore
from quality_workflow import VideoProviderQualityCompany
from script_quality import SCRIPT_CONTRACT, inspect_script

SCOPE = 'representative_video_mission_01'
GAME_GOAL = '요즘 인기있는 게임에 대한 흥미있는 쇼츠 영상을 만들어봐. 기본적으로 인기있는 쇼츠는 몇초인지도 확인해보고.'
GAME_SCOPE = 'game_shorts_independent_research_20261111'
GAME_RESEARCH_BLOCKER = 'mission_independent_web_research_unavailable'
MAX_CALLS = 10
ROLES = ('research', 'writer', 'editor')
DATA_POLICY = 'Google unpaid-service input/output may be used for improvement and reviewed by humans.'
DEFAULT_ROOT = Path('data/video_representative_workflow/studio')


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
                approved_max_searches=4, approved_max_videos=4,
                credential_binding=_binding(project_id+':youtube',youtube_key), free_usage_verified=True,
                policy_confirmed=True)
        else:
            web = None
        # These are owner attestations, never a provider billing lookup or a $0 guarantee.
        proof = dict(account_project=account_project, remaining_requests=quota_observation(remaining_requests), quota_note=quota_note,
                     approved_max_calls=MAX_CALLS,
                     credential_binding=_binding(project_id, key), billing_disabled=True,
                     free_data_policy=DATA_POLICY)
        self._check_mission_account(proof)
        require(key not in json.dumps(proof, ensure_ascii=False), 'secret_in_state')
        body = self.prepare(project_id, valid_hours=1, confirm_free_account=True)
        return {**body, 'mission_account': proof, **({'mission_web':web} if web else {})}

    @staticmethod
    def check_scope(p):
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
                and p['limits'] == dict(max_calls=MAX_CALLS, max_revisions_per_task=1, max_total_revisions=1)
                and not p.get('local_tools'), 'mission_scope_mismatch')

    @staticmethod
    def _check_mission_account(value):
        exact(value, ('account_project', 'remaining_requests', 'quota_note', 'credential_binding',
                      'billing_disabled', 'free_data_policy', 'approved_max_calls'))
        text(value['account_project'], 200)
        text(value['quota_note'], 500)
        quota_observation(value['remaining_requests'])
        require(type(value['approved_max_calls']) is int and value['approved_max_calls'] == MAX_CALLS
                and value['billing_disabled'] is True and value['free_data_policy'] == DATA_POLICY
                and isinstance(value['credential_binding'], str) and len(value['credential_binding']) == 64,
                'mission_free_account_unverified')

    def _check_contract(self, p, body):
        require(isinstance(body, dict), 'invalid_fields')
        self.check_scope(p)
        if p['goal'] == GAME_GOAL:
            require(p['quality_inputs']['capabilities'].get('employee_web_research') == WEB_TOOL, GAME_RESEARCH_BLOCKER)
            web = body.get('mission_web')
            exact(web, ('policy','account_project','search_remaining','general_units_remaining',
                        'credential_binding','free_usage_verified','policy_confirmed',
                        'approved_max_searches','approved_max_videos'))
            text(web['account_project'],200)
            quota_observation(web['search_remaining'])
            quota_observation(web['general_units_remaining'])
            require(web['policy']==WEB_POLICY and web['free_usage_verified'] is True
                    and web['policy_confirmed'] is True
                    and type(web['approved_max_searches']) is int and web['approved_max_searches'] == 4
                    and type(web['approved_max_videos']) is int and web['approved_max_videos'] == 4
                    and isinstance(web['credential_binding'],str),
                    'employee_web_scope_unverified')
        else:
            require('mission_web' not in body,'mission_scope_mismatch')
        self._check_mission_account(body.get('mission_account'))
        super()._check_contract(p, {k:v for k,v in body.items() if k not in ('mission_account','mission_web')})


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


class MissionOneCompany(VideoProviderQualityCompany):
    store_type = MissionOneStore
    allowed_video_roles = ('research', 'writer', 'editor')

    def _quality_transport_allowed(self, p):
        self.store.check_scope(p)
        if p['goal'] == GAME_GOAL:
            require(p['quality_inputs']['capabilities'].get('employee_web_research') == WEB_TOOL, GAME_RESEARCH_BLOCKER)
            self._authorize_web(p)
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
        notice = super()._tool_notice(p)
        if p['goal'] == GAME_GOAL:
            return (notice.replace('60초','목표 길이').replace('target_duration=60','target_duration=quality.manager_selection.duration_seconds')+
                ' Research employee constructs its OWN search queries from the representative goal. No game, '
                'ranking, topic or duration is preselected. Exactly research then writer then editor, with dependencies. '
                'Research execute.content must be JSON {tool:"'+WEB_TOOL+'",queries:[{query,purpose,lookback_days,order}]}; '
                '1–4 queries, purpose game_interest|shorts_examples, lookback_days integer 1–30, '
                'order relevance|date|viewCount. System uses YouTube public API top 5 gaming results per query '
                'in KR with Korean relevance. No arbitrary URL fetch or media download. This tool is available '
                'only once for research; failures stop, never repeat the batch. Tool receipt will be in evidence. '
                'Manager reviews observed metadata and evidence limits. On accepting research return feedback as '
                'JSON {game,selected_topic,duration_seconds,duration_reason,selection_reason,other_candidates_reason,'
                'evidence_ids,shorts_status:"unverified",rights_plan}. Choose duration from observed lengths and '
                'story needs, not a preset. Technical validation supports 4–180 seconds, no recommended duration. '
                'Public API does not confirm vertical aspect or Shorts classification. Its short filter includes '
                'non-Shorts; preserve uncertainty and never equate queried views with global game popularity or '
                'growth. Missing/private/non-gaming/outdated samples cannot support the selection. '
                'Writer follows quality.manager_selection for topic and duration. Keep visual sources pending, '
                'Korean full narration and captions, exact target_segment, and rights unverified. '
                'Use evidence_ids only from the tool receipt. Finalize deliver after internal acceptance; '
                'no production, TTS, uploading, publication or representative approval.')
        return (notice +
            ' MISSION 01: planning only. Use exactly one research task, one writer depending on research, '
            'and one editor depending on writer. Research compares 2–4 original topics and outputs JSON '
            '{candidates:[{topic,rationale,evidence_status:"unverified"}],selected_topic,selection_reason,uncertainty}. '
            'No search or supplied verified sources exist for this run. Do not cite invented URLs, dates, rankings, '
            'rights, or real match results. No prior topic was approved. Frame examples as fictional or evergreen, '
            'use illustrative facts or verification_pending, and leave every visual source pending. '
            'Use the exact target_segment in the script; if 미정, describe the audience inference in planning. '
            'Write the full Korean script. The writer topic.title must match the selected research topic verbatim. '
            'The editor output is a storyboard handoff, never a tool or video request. '
            'After all three tasks are accepted, use finalize action=deliver for a text-only representative handoff. '
            'The application stops delivery at human review; do not claim approval or generate media.')

    def _call(self, p, provider, phase, task_id, context):
        selection = self._manager_selection(p)
        if selection:
            context = {**context,'quality':{**context['quality'],'manager_selection':selection}}
        result = super()._call(p, provider, phase, task_id, context)
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
                require(content['topic']['title'] == chosen['selected_topic'],
                        'mission_selected_topic_mismatch')
                require(all(beat['source_status'] == 'pending' for beat in content['narrative_beats']),
                        'mission_visual_source_unverified')
        return result

    def _delivery_blockers(self, p):
        return ['needs_user_review']


def checked_result(job, *, allow_fixture=False):
    if job['goal']==GAME_GOAL:
        require(job['quality_inputs']['capabilities'].get('employee_web_research')==WEB_TOOL,GAME_RESEARCH_BLOCKER)
    attempts = job['real_ai']['attempts']
    require(job['status'] == job.get('reason_code') == 'needs_user_review' and job['final']
            and not job['artifacts'] and not job['active_operation'] and 8 <= len(attempts) <= MAX_CALLS,
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
        if job.get('employee_web',{}).get('status') == 'failed_or_uncertain':
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
    parser.add_argument('action', choices=('connect-web','prepare', 'approve', 'run'))
    parser.add_argument('project')
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
    store = MissionOneStore(workflow.store.root/'mission_one_provider')
    try:
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
