"""Representative research choice to the existing manager/writer/editor workflow."""
import hmac
import os
from copy import deepcopy
from urllib.parse import urlsplit

from autonomous_company import CompanyError, digest, exact, now, parse, require
from autonomous_gemini35 import ENDPOINT, MODEL, Gemini35Config, Gemini35Store
from autonomous_live import LiveEmployeeProvider, LiveManagerProvider
from goal_dialogue import safe_text
from goal_dialogue_live import send_once
from mission_production import production_keys
from owner_operating_policy import OwnerOperatingPolicy
from production_operating import unit
from quality_provider import QualityProviderStore
from quality_workflow import VideoProviderQualityCompany
from representative_workflow import _report, portrait_script_spec
from script_quality import SCRIPT_CONTRACT, script_editor_handoff, validate_script_editor
from video_mission_one import MISSION_ACCOUNT, _binding
from web_research import evidence_catalog

ACTIONS = ('collaboration-scope-approve','collaboration-scope-revoke','collaboration-run')


def choose(workflow, project, body):
    from general_research_report import versions

    exact(body,('version','sha256','candidate','direction','goal_changed','duration_seconds','confirm_limits'))
    require(body['confirm_limits'] is True and isinstance(body['direction'],str) and type(body['goal_changed']) is bool
            and type(body['duration_seconds']) is int and 4<=body['duration_seconds']<=120,
            'collaboration_choice_invalid')
    if body['direction']:
        safe_text(body['direction'],1200)
    require(body['candidate'] is not None or bool(body['direction'].strip()),'collaboration_choice_invalid')
    require(not body['goal_changed'] or bool(body['direction'].strip()),'collaboration_choice_invalid')
    flow=project['representative']
    require(not flow.get('research_handoff') and flow['constraints'].get('aspect','9:16')=='9:16',
            'collaboration_choice_invalid')
    base,store,history=versions(workflow,project)
    require(history and base['version']==history[-1]['report']['version'],'general_report_changed')
    latest=history[-1]
    report=latest['report']
    require((body['version'],body['sha256'])==(report['version'],report['sha256'])
            and (not latest['decision'] or latest['decision']['action'] in ('approve','plan')),
            'general_report_changed')
    index=body['candidate']
    topics=report['manager']['topics']
    require(index is None or type(index) is int and 0<=index<len(topics),'collaboration_choice_invalid')
    topic=topics[index] if index is not None else None
    catalog=evidence_catalog(report['staff']['observations'])
    refs=list(dict.fromkeys(topic['source_ids'])) if topic else list(dict.fromkeys([
        *(ref['source'] for claim in report['staff']['claims'] for ref in claim['citations']),
        *(ref for item in topics for ref in item['source_ids'])]))
    require(all(ref in catalog for ref in refs),'research_evidence_invalid')
    observed=[{key:catalog[ref][key] for key in ('id','url','title','excerpt','scope','observed_at')}
              for ref in refs[:8]]
    record=dict(report_version=report['version'],report_sha256=report['sha256'],
                manager_action=report['manager']['action'], manager_note=report['manager']['note'],
                candidate=index, topic=deepcopy(topic), direction=body['direction'].strip(),
                goal_changed=body['goal_changed'],duration_seconds=body['duration_seconds'], evidence_ids=refs,
                evidence=observed,limits='영상 플랫폼·Shorts 분류·편집/게시 권리·성과 원인 미확인. 기획과 대본 범위.')
    if latest['decision'] and latest['decision']['action']=='plan':
        require(latest['decision']['handoff_sha256']==digest(record),'general_report_changed')
    elif not latest['decision']:
        store.write('owner-review.json',dict(action='plan',feedback=record['direction'],report_sha256=report['sha256'],
                                             handoff_sha256=digest(record),at=now()))
    flow['research_handoff']=record
    workflow.store.save(project)


def scope(root, project):
    record=project['representative']['research_handoff']
    return OwnerOperatingPolicy(root/'collaboration_scope'/project['id'],
                                dict(project=project['id'],research_sha256=digest(record),goal_sha256=digest(project['goal'])))


def offer(policy):
    return dict(policy.proposal([unit('planning',MODEL,ENDPOINT,
        ['goal','owner_selection','public_research_evidence','research_limits','planning_and_script','owner_revision_feedback'])]),
        purpose='research_to_script_handoff',provider_project=MISSION_ACCOUNT,
        includes_plan_revisions=True,account_evidence='owner_attested_free_only_provider_status_unverified')


class HandoffStore(QualityProviderStore):
    marker_name='.research-plan-handoff-v1'
    _limits=staticmethod(Gemini35Store._limits)


class HandoffCompany(VideoProviderQualityCompany):
    store_type=HandoffStore
    allowed_video_roles=('writer','editor')

    def __init__(self,store,config,policy,parent_key):
        super().__init__(store,LiveManagerProvider('handoff-manager'),LiveEmployeeProvider('handoff-staff'),config)
        self.policy=policy
        self.parent_key=parent_key

    def _quality_transport_allowed(self,p):
        active=self.policy.active(self.parent_key)
        grant=self.store.grant(p)['body']
        require(active['proposal']==offer(self.policy)
                and p['quality_inputs']['answers']['scope_sha256']==digest(active)
                and grant['expires_at']<=active['expires_at']
                and hmac.compare_digest(self.parent_key,_binding(self.policy.binding['project'],self.config.api_key)),
                'owner_policy_scope_changed')
        return True

    def _open_transport(self,request,timeout):
        return send_once(request,timeout)

    def _before_transport(self,p):
        super()._before_transport(p)
        self._quality_transport_allowed(p)

    def _delivery_blockers(self,p):
        return ['needs_user_review']

    def _script_duration(self,p):
        return p['quality_inputs']['answers']['research_handoff']['duration_seconds']

    def _tool_notice(self,p):
        return super()._tool_notice(p)+(
            ' Scope is script planning only. Plan exactly one writer and one editor dependent on the writer. '
            'Use the research_handoff and any representative revision feedback. If a candidate was selected, '
            'keep its exact title as script topic title. Preserve evidence limitations; metadata is not footage '
            'or a license. Write for the exact requested duration using 2–12 scenes of 1–20 seconds each. '
            'Captions: up to two lines, each up to 14 Korean syllables or 28 ASCII characters. '
            'Do not download, generate media or publish.')

    def _validate_review_decision(self,p,task,review):
        super()._validate_review_decision(p,task,review)
        if task['role']=='writer' and review['action']=='accept':
            writer=task['versions'][-1]
            script=parse(writer['content'])
            topic=p['quality_inputs']['answers']['research_handoff']['topic']
            require(not topic or script['topic']['title']==topic['title'],'collaboration_candidate_changed')
            portrait_script_spec(script,script_editor_handoff(writer),'none')

    def _validate_script_plan(self,value):
        super()._validate_script_plan(value)
        require(len(value['tasks'])==2 and {task['role'] for task in value['tasks']}=={'writer','editor'},
                'script_plan_handoff_required')


def state(workflow,project):
    flow=project['representative']
    if not flow.get('research_handoff') or flow['stage'] not in ('research_planning','plan_revision'):
        return None
    policy=scope(workflow.store.root,project)
    proposal=offer(policy)
    grant=policy.read('policy.json')
    revision=flow['decisions'][-1] if flow['stage']=='plan_revision' else None
    jobs=flow.get('collaboration_jobs',[])
    current=next((job for job in reversed(jobs) if job['revision_sha256']==(digest(revision) if revision else None)),None)
    status='approval_required' if not grant else 'ready'
    try:
        if grant:
            key,_=production_keys()
            policy.active(_binding(project['id'],key))
    except CompanyError as exc:
        status=exc.code
    if current:
        status=current['status']
    return dict(status=status,proposal=proposal,review_hash=digest(proposal),
                handoff=flow['research_handoff'], current=current)


def execute(workflow,pid,name,body,*,company_type=HandoffCompany,allow_fixture=False):
    if name=='collaboration-scope-revoke':
        exact(body,())
        project=workflow.store.load(pid)
        require(project['representative'].get('research_handoff'),'collaboration_choice_required')
        return scope(workflow.store.root,project).revoke()
    # Serialize local project edits and job creation. The provider engine owns its job lock.
    with workflow.store.lock(pid):
        project=workflow.store.load(pid)
        flow=project['representative']
        require(flow.get('research_handoff') and flow['stage'] in ('research_planning','plan_revision'),
                'collaboration_choice_required')
        policy=scope(workflow.store.root,project)
        proposal=offer(policy)
        key,_=production_keys()
        credential=_binding(pid,key)
        if name=='collaboration-scope-approve':
            exact(body,('confirmed','review_hash'))
            require(body['confirmed'] is True,'owner_policy_required')
            policy.root.parent.mkdir(mode=0o700,exist_ok=True)
            policy.approve(proposal,body['review_hash'],credential)
            return
        exact(body,())
        grant=policy.active(credential)
        require(grant['proposal']==proposal,'owner_policy_scope_changed')
        config=Gemini35Config.from_env()
        require((config.model,config.endpoint)==(MODEL,ENDPOINT),'gemini_provider_binding')
        require(os.getenv('GEMINI35_AUTONOMOUS_FREE_ENABLED')=='1','gemini_execution_disabled')
        revision=flow['decisions'][-1] if flow['stage']=='plan_revision' else None
        prior=flow['plan_versions'][-1] if revision else None
        revision_hash=digest(revision) if revision else None
        jobs=flow.setdefault('collaboration_jobs',[])
        require(not any(job['revision_sha256']==revision_hash for job in jobs),'collaboration_duplicate')
        store=HandoffStore(workflow.store.root/'research_plan_handoff'/pid)
        require(not any(job.stem not in {row['id'] for row in jobs}
                        for job in store.root.glob('qualityprovider-*.json') if '.' not in job.stem),
                'collaboration_orphan')
        inputs=dict(domain='video',target_segment=flow['audience'],
            answers=dict(research_handoff=flow['research_handoff'],scope_sha256=digest(grant),
                prior_plan=dict(sha256=prior['sha256'],summary=prior['summary'],script=prior['script']) if prior else None),
            constraints={**flow['constraints'],'aspect':'9:16'},
            capabilities=dict(script_contract=SCRIPT_CONTRACT), experiences=[],
            feedback_text=revision['feedback'] if revision else flow['research_handoff']['direction'])
        job=store.create(project['goal'],inputs=inputs,max_calls=None,max_total_revisions=1)
        consent=store.prepare(job['id'],confirm_free_account=True)
        consent['expires_at']=min(consent['expires_at'],grant['expires_at'])
        store.approve(job['id'],consent,review_hash=digest(consent),owner_confirmed=True)
        entry=dict(id=job['id'],status='running',revision_sha256=revision_hash)
        jobs.append(entry)
        workflow.store.save(project)
        try:
            signed=store.load(job['id'])
            company=company_type(store,config,policy,credential)
            result=company.run(job['id'],expected_state_hash=signed['storage_hash'])
            require(result['status']=='needs_user_review',result.get('reason_code') or 'collaboration_internal_review_incomplete')
            publish_plan(workflow,project,result,prior,allow_fixture=allow_fixture)
        except CompanyError as exc:
            entry.update(status='stopped',reason=exc.code)
            workflow.store.save(project)
            raise


def publish_plan(workflow, project, job, prior, *, allow_fixture):
    flow=project['representative']
    attempts=job['real_ai']['attempts']
    require(job['status']=='needs_user_review' and job['final'] and not job['active_operation']
            and attempts and all(row['status']=='completed' and row.get('role_result_status')=='validated'
                                 and row.get('http_status')==200 and row['model']==MODEL for row in attempts),
            'collaboration_internal_review_incomplete')
    tasks={task['role']:task for task in job['assignments']}
    require(set(tasks)=={'writer','editor'} and len(job['assignments'])==2
            and all(task['state']=='accepted_by_ai_manager' and task['reviews'][-1]['action']=='accept'
                    for task in tasks.values()),'collaboration_internal_review_incomplete')
    writer=tasks['writer']['versions'][-1]
    editor=tasks['editor']['versions'][-1]
    provenance=job['plan']['source']
    require(provenance=='provider_model_claim' or allow_fixture and provenance=='offline_http_fixture',
            'collaboration_fixture_forbidden')
    require(all(item['source']==provenance for task in tasks.values() for item in task['versions']),
            'collaboration_internal_review_incomplete')
    board=parse(editor['content'])
    validate_script_editor(board,[writer])
    script=parse(writer['content'])
    portrait_script_spec(script,board,'none')
    record=flow['research_handoff']
    topic=record['topic']
    require(not topic or script['topic']['title']==topic['title'],'collaboration_candidate_changed')
    sources=[dict(url=row['url'],observed_at=row['observed_at'],claim=row['excerpt'],
                  rights='편집·게시 권리 미확인') for row in record['evidence'] if urlsplit(row['url']).scheme=='https']
    report=_report(dict(summary=job['final']['content'],sources=sources,risks=record['limits'],
        changes=job['quality_inputs']['feedback_text'] or '조사 선택에서 인계된 첫 기획·대본',
        topic=script['topic']['title'],script=script,render_spec=None,cost_limit_usd=0,
        internal_job=job['id'],writer_sha256=digest(writer),editor_sha256=digest(editor),
        internal_reviews=tasks['writer']['reviews'],previous_plan_sha256=prior['sha256'] if prior else None,
        provenance=provenance,task_history=deepcopy(job['assignments']),manager_plan=job['plan'],
        final_review=job['final'],research_handoff=deepcopy(record)),flow['plan_versions'])
    flow['plan_versions'].append(report)
    flow['collaboration_jobs'][-1]['status']='completed'
    workflow._transition(project,'awaiting_plan_approval')
