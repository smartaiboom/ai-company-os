"""Mission 01's scoped entry to the existing signed video provider workflow."""
import argparse
import hmac
import json
from pathlib import Path

from autonomous_company import CompanyError, Store, digest, exact, parse, require, text
from autonomous_gemini35 import Gemini35Config, MODEL, ENDPOINT
from autonomous_live import LiveEmployeeProvider, LiveManagerProvider
from goal_dialogue_live import send_once
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


class MissionOneStore(QualityProviderStore):
    def prepare_mission(self, project_id, *, key, account_project, remaining_requests, quota_note):
        p = self.load(project_id)
        self.check_scope(p)
        require(p['goal'] != GAME_GOAL, GAME_RESEARCH_BLOCKER)
        proof = dict(account_project=account_project, remaining_requests=remaining_requests, quota_note=quota_note,
                     credential_binding=_binding(project_id, key), billing_disabled=True,
                     free_data_policy=DATA_POLICY)
        self._check_mission_account(proof)
        require(key not in json.dumps(proof, ensure_ascii=False), 'secret_in_state')
        body = self.prepare(project_id, valid_hours=1, confirm_free_account=True)
        return {**body, 'mission_account': proof}

    @staticmethod
    def check_scope(p):
        quality = p['quality_inputs']
        capabilities = {'script_contract': SCRIPT_CONTRACT, 'mission': SCOPE}
        if p['goal'] == GAME_GOAL:
            capabilities['editorial_scope'] = GAME_SCOPE
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
                      'billing_disabled', 'free_data_policy'))
        text(value['account_project'], 200)
        text(value['quota_note'], 500)
        require(type(value['remaining_requests']) is int and value['remaining_requests'] >= MAX_CALLS
                and value['billing_disabled'] is True and value['free_data_policy'] == DATA_POLICY
                and isinstance(value['credential_binding'], str) and len(value['credential_binding']) == 64,
                'mission_free_account_unverified')

    def _check_contract(self, p, body):
        require(isinstance(body, dict), 'invalid_fields')
        self.check_scope(p)
        require(p['goal'] != GAME_GOAL, GAME_RESEARCH_BLOCKER)
        self._check_mission_account(body.get('mission_account'))
        super()._check_contract(p, {k:v for k,v in body.items() if k != 'mission_account'})


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
        require(p['goal'] != GAME_GOAL, GAME_RESEARCH_BLOCKER)
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

    def _tool_notice(self, p):
        notice = super()._tool_notice(p)
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
        result = super()._call(p, provider, phase, task_id, context)
        if phase == 'plan' and 'tasks' in result:
            roles = {task['role']:task for task in result['tasks']}
            require(len(result['tasks']) == 3 and set(roles) == set(ROLES)
                    and roles['research']['id'] in roles['writer']['depends_on'], 'mission_research_dependency')
        if phase == 'execute':
            role = context['assignment']['role']
            content = parse(result['content'])
            if role == 'research':
                validate_research(content)
            elif role == 'writer':
                research = next(r for r in context['previous_results'] if r['role'] == 'research')
                chosen = validate_research(parse(research['content']))
                require(content['topic']['title'] == chosen['selected_topic'],
                        'mission_selected_topic_mismatch')
                require(all(beat['source_status'] == 'pending' for beat in content['narrative_beats']),
                        'mission_visual_source_unverified')
        return result

    def _delivery_blockers(self, p):
        return ['needs_user_review']


def checked_result(job, *, allow_fixture=False):
    require(job['goal'] != GAME_GOAL, GAME_RESEARCH_BLOCKER)
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
    research = validate_research(parse(tasks['research']['versions'][-1]['content']))
    script = parse(tasks['writer']['versions'][-1]['content'])
    inspection = inspect_script(script, job['quality_inputs']['target_segment'], mock=False)
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
        reason = GAME_RESEARCH_BLOCKER if scope == GAME_SCOPE else 'mission_old_scope_superseded'
    return dict(id=job['id'], status=job['status'], reason=reason, model=MODEL,
                attempts=attempts, authorized=job['real_ai']['consent'].get('approved') is True,
                assignments=[dict(role=t['role'], state=t['state'], versions=len(t['versions']))
                             for t in job['assignments']])


def main():
    from representative_workflow import RepresentativeVideoWorkflow
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('action', choices=('prepare', 'approve', 'run'))
    parser.add_argument('project')
    parser.add_argument('--account-project')
    parser.add_argument('--remaining-requests', type=int)
    parser.add_argument('--quota-note')
    parser.add_argument('--proposal', type=Path)
    parser.add_argument('--review-hash')
    parser.add_argument('--confirm-free-account', action='store_true')
    parser.add_argument('--confirm-free-data-policy', action='store_true')
    args = parser.parse_args()
    workflow = RepresentativeVideoWorkflow(Store(args.root))
    store = MissionOneStore(workflow.store.root/'mission_one_provider')
    try:
        p = workflow.store.load(args.project)
        pid = p['representative'].get('mission_one_job')
        require(pid is not None, 'mission_stage_in_studio_first')
        require(p['goal'] == GAME_GOAL, 'mission_game_goal_required')
        config = Gemini35Config.from_env()
        if args.action == 'prepare':
            require(args.confirm_free_account, 'mission_free_account_unverified')
            body = store.prepare_mission(pid, key=config.api_key, account_project=args.account_project,
                                         remaining_requests=args.remaining_requests, quota_note=args.quota_note)
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
