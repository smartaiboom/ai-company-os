"""Representative research choice to the existing manager/writer/editor workflow."""
import hmac
import os
from copy import deepcopy
from urllib.parse import urlsplit
from urllib.error import HTTPError

from autonomous_company import CompanyError, Store, digest, exact, now, parse, require
from autonomous_gemini35 import ENDPOINT, MODEL, Gemini35Config, Gemini35Store
from autonomous_live import LiveEmployeeProvider, LiveManagerProvider
from decision_recovery import delegated_call
from goal_dialogue import safe_text
from goal_dialogue_live import send_once
from groq_provider import (MODEL as GROQ_MODEL, ENDPOINT as GROQ_BASE, COST_POLICY as GROQ_COST,
                           GroqConfig, GroqFreeAdapter, provider_error_diagnostics, response_source_hints)
from mission_production import production_keys
from owner_operating_policy import OwnerOperatingPolicy
from production_operating import unit
from quality_provider import QualityProviderStore, experience_context
from quality_workflow import VideoProviderQualityCompany
from representative_experience import current_selection, select, work_scope
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
    initial_scope = work_scope(flow)
    flow['research_handoff']=record
    if work_scope(flow) != initial_scope:
        flow['experience_snapshot'] = select(workflow.store, flow, omit=project['id'],
                                             fixture=workflow.fixture_experiences)
    workflow.store.save(project)


def scope(root, project):
    record=project['representative']['research_handoff']
    return OwnerOperatingPolicy(root/'collaboration_scope'/project['id'],
                                dict(project=project['id'],research_sha256=digest(record),goal_sha256=digest(project['goal'])))


RENDER_MEASUREMENTS='local_render_measurements'
GROQ_ENDPOINT=GROQ_BASE+'/chat/completions'
GROQ_PROJECT='Personal / Default Project'
DEVELOPMENT_SCOPE='development_scope'
DEVELOPMENT_PURPOSE='verify_research_handoff_manager_writer_editor'


def offer(policy, *, include_render_measurements=True, provider='gemini', experiences=(), development=False):
    require(provider in ('gemini','groq'),'collaboration_provider_invalid')
    data=['goal','owner_selection','public_research_evidence','research_limits','planning_and_script','owner_revision_feedback']
    fields = {'provider': 'groq'} if provider == 'groq' else {}
    if experiences:
        data.append('scoped_representative_preferences')
        fields['experiences_sha256'] = digest(experiences)
    if provider=='gemini' and include_render_measurements:
        data.append(RENDER_MEASUREMENTS)
    model, endpoint, account = ((GROQ_MODEL,GROQ_ENDPOINT,GROQ_PROJECT) if provider=='groq'
                                else (MODEL,ENDPOINT,MISSION_ACCOUNT))
    if development:
        fields.update(mode=DEVELOPMENT_SCOPE, provider=provider, verification_purpose=DEVELOPMENT_PURPOSE)
    return dict(policy.proposal([unit('planning',model,endpoint,data)]),
        purpose='research_to_script_handoff',provider_project=account,
        includes_plan_revisions=True,account_evidence='owner_attested_free_only_provider_status_unverified',
        **fields)


def includes_render_measurements(grant):
    return any(RENDER_MEASUREMENTS in item['data_types'] for item in grant['proposal']['units'])


class HandoffStore(QualityProviderStore):
    marker_name='.research-plan-handoff-v1'
    _limits=staticmethod(Gemini35Store._limits)


class GroqHandoffStore(HandoffStore):
    mode='collaboration_groq_free_v1'
    marker_name='.collaboration-groq-free-v1'
    policy=mode
    provider_id='groq'
    model=GROQ_MODEL
    endpoint=GROQ_ENDPOINT
    cost_policy=GROQ_COST
    # A single request per token window keeps this workflow's requests from
    # competing with each other for the Free plan's 8K tokens/minute.
    rules={**HandoffStore.rules,'min_interval_seconds':60}


def provider_config(provider):
    if provider=='groq':
        return GroqConfig.from_env()
    key,_=production_keys()
    config=Gemini35Config.from_env()
    require(config.api_key==key,'gemini_key_binding')
    return config


class HandoffCompany(VideoProviderQualityCompany):
    store_type=HandoffStore
    allowed_video_roles=('writer','editor')

    def __init__(self,store,config,policy,parent_key):
        super().__init__(store,LiveManagerProvider('handoff-manager'),LiveEmployeeProvider('handoff-staff'),config)
        self.policy=policy
        self.parent_key=parent_key

    def _request_json(self, p, **kwargs):
        grant = self.policy.active(self.parent_key)
        if grant['proposal'].get('mode') != DEVELOPMENT_SCOPE:
            return super()._request_json(p, **kwargs)

        operation, = grant['proposal']['units']
        require((operation['model'], operation['endpoint']) == (kwargs['model'], kwargs['base_url']),
                'owner_policy_scope_changed')
        operation = {**operation, 'id': 'planning:'+str(len(self.policy.attempts())+1)}
        response = None

        def run(policy_hash, check):
            nonlocal response
            require(policy_hash == digest(grant), 'owner_policy_scope_changed')
            check()
            response = super(HandoffCompany, self)._request_json(p, **kwargs)

        delegated_call(self.policy, self.parent_key, operation, digest(parse(kwargs['body'].decode())), run)
        return response

    def _quality_transport_allowed(self,p):
        active=self.policy.active(self.parent_key)
        grant=self.store.grant(p)['body']
        experiences = p['quality_inputs']['experiences']
        require(active['proposal']==offer(self.policy,include_render_measurements=includes_render_measurements(active),
                                          provider=self.store.provider_id,experiences=experiences,
                                          development=active['proposal'].get('mode')==DEVELOPMENT_SCOPE)
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
        if p['quality_inputs']['experiences']:
            store = Store(self.policy.root.parent.parent)
            project = store.load(self.policy.binding['project'])
            selection = current_selection(store, project, fixture=self.source == 'offline_http_fixture')
            require(experience_context(selection) == p['quality_inputs']['experiences'], 'owner_policy_scope_changed')

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


class GroqHandoffCompany(HandoffCompany):
    store_type=GroqHandoffStore
    config_type=GroqConfig
    bound_model=GROQ_MODEL
    bound_endpoint=GROQ_ENDPOINT
    cost_policy=GROQ_COST
    adapter_type=GroqFreeAdapter

    def _check_provider_config(self):
        require(self.config==provider_config('groq') and bool(self.config.api_key),'groq_key_binding')

    def _attempt_identity(self):
        return {'provider_id':'groq','endpoint':GROQ_ENDPOINT,'cost_policy_hash':digest(GROQ_COST)}

    def _output_token_limit(self,payload):
        return payload['max_completion_tokens']

    def _normalize_envelope(self,envelope):
        return envelope

    def _verify_response_policy(self,p,envelope):
        super()._verify_response_policy(p,envelope)
        require(envelope.get('model')==GROQ_MODEL,'groq_response_model_mismatch')
        usage=envelope.get('usage')
        if isinstance(usage,dict) and 'cost' in usage:
            require(type(usage['cost']) in (int,float) and usage['cost']==0,'groq_unexpected_cost')

    def _record_provider_error(self,entry,*,exception=None,envelope=None,http_status=None):
        diagnostics=provider_error_diagnostics(exception=exception,envelope=envelope,http_status=http_status)
        if diagnostics is not None:
            entry['provider_error_diagnostics']=diagnostics
        if isinstance(exception,HTTPError):
            entry['response_source_hints']=response_source_hints(exception.headers or {},exception.code)


def state(workflow,project):
    flow=project['representative']
    if not flow.get('research_handoff') or flow['stage'] not in ('research_planning','plan_revision'):
        return None
    policy=scope(workflow.store.root,project)
    grant=policy.read('policy.json')
    provider=grant['proposal'].get('provider','gemini') if grant else 'gemini'
    experiences=experience_context(workflow.selected_experiences(project))
    proposal=grant['proposal'] if grant else offer(policy,experiences=experiences)
    revision=flow['decisions'][-1] if flow['stage']=='plan_revision' else None
    jobs=flow.get('collaboration_jobs',[])
    current=next((job for job in reversed(jobs) if job['revision_sha256']==(digest(revision) if revision else None)),None)
    status='approval_required' if not grant else 'ready'
    try:
        if grant:
            config=provider_config(provider)
            policy.active(_binding(project['id'],config.api_key))
            require(proposal==offer(policy,provider=provider,include_render_measurements=includes_render_measurements(grant),
                                    experiences=experiences,development=proposal.get('mode')==DEVELOPMENT_SCOPE),
                    'owner_policy_scope_changed')
    except CompanyError as exc:
        status=exc.code
    if current:
        status=current['status']
    development_offers = {}
    if not grant and not jobs:
        for name in ('gemini', 'groq') if os.getenv('GROQ_API_KEY') else ('gemini',):
            proposed = offer(policy,provider=name,experiences=experiences,development=True)
            development_offers[name] = dict(proposal=proposed,review_hash=digest(proposed))
    groq_offer=offer(policy,provider='groq',experiences=experiences) if not grant and os.getenv('GROQ_API_KEY') else None
    return dict(status=status,proposal=proposal,review_hash=digest(proposal),
                groq_offer=dict(proposal=groq_offer,review_hash=digest(groq_offer)) if groq_offer else None,
                handoff=flow['research_handoff'], current=current, experience_inputs=experiences,
                development_offers=development_offers,
                development_requests=len(policy.attempts()) if proposal.get('mode')==DEVELOPMENT_SCOPE else None)


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
        existing=policy.read('policy.json')
        experiences=experience_context(workflow.selected_experiences(project))
        require(not experiences or not workflow.fixture_experiences or (
                allow_fixture and company_type.source=='offline_http_fixture'),
                'collaboration_fixture_forbidden')
        if name=='collaboration-scope-approve':
            fields = ('confirmed', 'review_hash')
            exact(body, fields + tuple(key for key in ('provider', 'mode') if key in body))
            require('mode' not in body or body['mode']==DEVELOPMENT_SCOPE, 'owner_policy_scope_changed')
            development = body.get('mode') == DEVELOPMENT_SCOPE
            require(not development or not flow.get('collaboration_jobs'), 'collaboration_provider_stopped')
            provider=body.get('provider','gemini')
            proposal=offer(policy,provider=provider,experiences=experiences,development=development)
            config=provider_config(provider)
            if provider=='groq':
                GroqFreeAdapter().build_request(b'{}',config.api_key)
            credential=_binding(pid,config.api_key)
            require(body['confirmed'] is True,'owner_policy_required')
            policy.root.parent.mkdir(mode=0o700,exist_ok=True)
            policy.approve(proposal,body['review_hash'],credential)
            return
        exact(body,())
        require(existing is not None,'owner_policy_required')
        provider=existing['proposal'].get('provider','gemini')
        config=provider_config(provider)
        credential=_binding(pid,config.api_key)
        grant=policy.active(credential)
        measurements=includes_render_measurements(grant)
        development = grant['proposal'].get('mode') == DEVELOPMENT_SCOPE
        require(grant['proposal']==offer(policy,include_render_measurements=measurements,provider=provider,
                                        experiences=experiences,development=development),
                'owner_policy_scope_changed')
        if provider=='gemini':
            require((config.model,config.endpoint)==(MODEL,ENDPOINT),'gemini_provider_binding')
            require(os.getenv('GEMINI35_AUTONOMOUS_FREE_ENABLED')=='1','gemini_execution_disabled')
        else:
            company_type=GroqHandoffCompany
        require(not experiences or not workflow.fixture_experiences or company_type.source=='offline_http_fixture',
                'collaboration_fixture_forbidden')
        revision=flow['decisions'][-1] if flow['stage']=='plan_revision' else None
        prior=flow['plan_versions'][-1] if revision else None
        video_context=None
        if revision and revision['stage']=='video':
            video=flow['video_versions'][-1]
            require(video['sha256']==revision['sha256'] and video['plan_sha256']==prior['sha256']
                    and revision['changes_plan'],'stale_representative_report')
            workflow._verify_video(project,video)
            receipt=video['render_receipt']
            video_context=dict(version=video['version'],sha256=video['sha256'],plan_sha256=video['plan_sha256'],
                duration_seconds=receipt['duration_seconds'], audio_mode=receipt['audio_mode'],
                visual_scope=receipt.get('visual_scope'), measured_scenes=[
                    {key:scene[key] for key in ('start_seconds','end_seconds','narration_duration_seconds')
                     if key in scene} for scene in receipt['review_material']])
        revision_hash=digest(revision) if revision else None
        jobs=flow.setdefault('collaboration_jobs',[])
        require(not any(job['revision_sha256']==revision_hash for job in jobs),'collaboration_duplicate')
        if provider=='groq' or development:
            require(all(job['status']=='completed' for job in jobs),'collaboration_provider_stopped')
        if development:
            require(all(row['result'] and row['result']['status']=='completed' for row in policy.attempts().values()),
                    'owner_policy_unresolved_attempt')
        store=company_type.store_type(workflow.store.root/'research_plan_handoff'/pid)
        require(not any(job.stem not in {row['id'] for row in jobs}
                        for job in store.root.glob('qualityprovider-*.json') if '.' not in job.stem),
                'collaboration_orphan')
        inputs=dict(domain='video',target_segment=flow['audience'],
            answers=dict(research_handoff=flow['research_handoff'],scope_sha256=digest(grant),
                prior_plan=dict(sha256=prior['sha256'],summary=prior['summary'],script=prior['script']) if prior else None,
                **(dict(reviewed_video=video_context,speech_overruns=revision.get('speech_overruns',[]) if revision else [])
                   if measurements else {})),
            constraints={**flow['constraints'],'aspect':'9:16'},
            capabilities=dict(script_contract=SCRIPT_CONTRACT), experiences=experiences,
            feedback_text=revision['feedback'] if revision else flow['research_handoff']['direction'])
        job=store.create(project['goal'],inputs=inputs,max_calls=None,max_total_revisions=1)
        if (provider=='groq' or development) and jobs:
            job['next_request_at']=store.load(jobs[-1]['id'])['next_request_at']
            store.save(job)
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
            publish_plan(workflow,project,result,prior,grant=store.grant(result),allow_fixture=allow_fixture)
        except CompanyError as exc:
            entry.update(status='stopped',reason=exc.code)
            workflow.store.save(project)
            raise


def publish_plan(workflow, project, job, prior, *, grant, allow_fixture):
    flow=project['representative']
    attempts=job['real_ai']['attempts']
    body=grant['body']
    identity=dict(provider_id=body['provider'],model=body['model'],endpoint=body['endpoint'])
    cost_policy_hash=digest(body['cost_policy'])
    require(job['status']=='needs_user_review' and job['final'] and not job['active_operation']
            and attempts and all(row['status']=='completed' and row.get('role_result_status')=='validated'
                                 and row.get('http_status')==200 and row.get('grant_id')==grant['id']
                                 and row.get('cost_policy_hash')==cost_policy_hash
                                 and all(row.get(key)==value for key,value in identity.items())
                                 for row in attempts),
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
        provenance=provenance,provider_identity=identity,task_history=deepcopy(job['assignments']),manager_plan=job['plan'],
        final_review=job['final'],experience_input_hashes=[item['record_hash']
            for item in job['quality_inputs']['experiences']],research_handoff=deepcopy(record)),flow['plan_versions'])
    flow['plan_versions'].append(report)
    flow['collaboration_jobs'][-1]['status']='completed'
    workflow._transition(project,'awaiting_plan_approval')
