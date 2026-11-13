"""Explicitly consented representative rework; no web tools, retries or media."""
from copy import deepcopy
import hmac
import json
import re
import os
import inspect
from autonomous_company import CompanyError, Store, digest, parse, require, text, validate_plan
from autonomous_gemini35 import Gemini35Store, Gemini35Config, MODEL, ENDPOINT
from autonomous_live import LiveManagerProvider, LiveEmployeeProvider
from quality_provider import QualityProviderStore
from quality_workflow import VideoProviderQualityCompany
from video_mission_one import MissionOneCompany, MISSION_ACCOUNT, DATA_POLICY, _binding
from role_json_schema import response_format, obj, S, matches
from representative_workflow import _report
from script_quality import SCRIPT_CONTRACT, validate_script_editor

CHECKS=('goal_fit','feedback_applied','subject_story','concrete_hook','claims_supported')
NOTICE=('원 목표와 representative_feedback을 이전 초안과 비교해 재기획하세요. 게임 콘텐츠 자체의 구체적 이야기/장면을 작성하고 '
        '영상 제작법/편집 노하우로 바꾸지 마세요. 기존 관측은 참고일 뿐 인기/성과/최적 길이를 입증하지 않습니다. '
        '새 조사/웹/미디어 도구는 없습니다. 근거 부족 시 중단하세요. plan에는 replan={selected_topic,duration_seconds,'
        'duration_reason,feedback_response}를 추가하고 writer와 이에 의존하는 editor만 배정하세요. '
        'review에는 goal_review의 goal_fit/feedback_applied/subject_story/concrete_hook/claims_supported 각각 '
        '{met:boolean,evidence:string}를 추가하세요. evidence는 대본/스토리보드 원문 인용이어야 합니다. '
        '대표 피드백 핵심과 목표 충족을 검토하고 미충족이면 accept 금지. 미확인 권리/성과는 미확인으로 유지.')


PLAN_RULES = (
    'Rework plan contract v3: exactly TWO tasks in order: writer then editor. '
    'Choose your own unique task IDs and criterion IDs. writer.depends_on MUST be []; '
    'editor.depends_on MUST be [the exact writer task ID]. No self, forward, missing or duplicate references. '
    'criteria contains unique IDs. Each task.criteria_ids is a nonempty unique subset of those criterion IDs; '
    'together both tasks use ALL criteria. Do not put task IDs into criteria_ids or criterion IDs into depends_on. '
    'replan.selected_topic must serve the ORIGINAL user goal and representative feedback, not the previous off-goal topic. '
    'Explain duration_seconds (4–180) in duration_reason and the concrete feedback changes in feedback_response. '
    'Keep all eight script criteria; game-story content is required, never video-making tips. '
    'No correction call or automatic retry is authorized by this contract.'
    ' Plan wire contract: output_contract references generationConfig.responseJsonSchema; '
    'the full schema is sent once there. Review wire contracts are unchanged.'
)
PLAN_SCHEMA_REFERENCE='Use generationConfig.responseJsonSchema for the complete result contract.'


def validate_rework_plan(plan):
    """Diagnose relationships without rewriting any AI-generated content."""
    def fail(index,field,detail):
        error=CompanyError('rework_plan_invalid')
        error.diagnostics=dict(task_index=index,field=field,detail=detail)
        raise error
    tasks=plan.get('tasks',[]);criteria=plan.get('criteria',[])
    if len(tasks)!=2:fail(None,'tasks','exactly_two_required')
    ids=[t.get('id') for t in tasks]
    if len(set(ids))!=2:fail(None,'id','duplicate_task_id')
    criterion_ids=[c.get('id') for c in criteria]
    if len(set(criterion_ids))!=len(criterion_ids):fail(None,'criteria','duplicate_criterion_id')
    for index,task in enumerate(tasks):
        if task.get('role')!=('writer','editor')[index]:fail(index,'role','writer_then_editor_required')
        if task.get('depends_on')!= ([] if index==0 else [ids[0]]):
            fail(index,'depends_on','empty_for_writer_exact_writer_id_for_editor')
        refs=task.get('criteria_ids',[])
        if not refs or len(set(refs))!=len(refs) or any(ref not in criterion_ids for ref in refs):
            fail(index,'criteria_ids','nonempty_unique_existing_criterion_ids_required')
    if set(criterion_ids)!={ref for task in tasks for ref in task['criteria_ids']}:
        fail(None,'criteria_ids','every_criterion_must_be_used')
    try:validate_plan(plan)
    except CompanyError as exc:fail(None,'plan',exc.code)
    return plan


def execution_settings():
    missing=[]
    for ok,label in ((os.getenv('GEMINI35_AUTONOMOUS_FREE_ENABLED')=='1','GEMINI35_AUTONOMOUS_FREE_ENABLED=1'),
                     (os.getenv('GEMINI35_MODEL')==MODEL,'GEMINI35_MODEL'),
                     (os.getenv('GEMINI35_ENDPOINT')==ENDPOINT,'GEMINI35_ENDPOINT'),
                     (bool(os.getenv('GEMINI_API_KEY')),'GEMINI_API_KEY 존재')):
        if not ok:missing.append(label)
    return dict(ready=not missing,missing=missing)



def script_review_recovery_audit(job,state):
    """Read-only historical inspection; never validate a transport or resume a stopped job."""
    if not (state.get('status')=='stopped' and state.get('error')=='script_feedback_missing_defect'
            and job.get('status')=='stopped'
            and job.get('reason_code')=='script_feedback_missing_defect'
            and job.get('phase')=='work'):
        return None
    attempts=job.get('real_ai',{}).get('attempts',[])
    writer=next((t for t in job.get('assignments',[])
                 if t.get('role')=='writer' and t.get('versions')),None)
    last=attempts[-1] if attempts else None
    report=dict(kind='script_review_validation_stop',source_job=job.get('id'),
                original_preserved=True,new_requests=0,automatic_resume=False,
                callable_retry_allowed=False,review_committed=False,
                review_available=False,checks_available=False,
                reusable_plan=False,reusable_writer=False,
                safe_for_recovery_proposal=False,
                status='incomplete_evidence',missing_issue_ids=[])
    if not last or not writer:
        return report
    plan_attempts=[a for a in attempts if a.get('phase')=='plan']
    writer_attempts=[a for a in attempts if a.get('phase')=='execute'
                     and a.get('task_id')==writer.get('id')]
    def validated(attempt):
        return (attempt.get('status')=='completed' and attempt.get('http_status')==200
                and attempt.get('role_result_status')=='validated'
                and attempt.get('transport_started_at') and attempt.get('finished_at')
                and attempt.get('response_hash'))
    report['reusable_plan']=bool(job.get('plan')) and len(plan_attempts)==1 and validated(plan_attempts[0])
    report['reusable_writer']=bool(writer.get('versions')) and len(writer_attempts)==1 and validated(writer_attempts[0])
    report['transport']=dict(phase=last.get('phase'),task_id=last.get('task_id'),
        status=last.get('status'),http_status=last.get('http_status'),
        role_result_status=last.get('role_result_status'),
        response_hash=last.get('response_hash'))
    if not (last.get('phase')=='review' and last.get('task_id')==writer.get('id')
            and last.get('status')=='completed' and last.get('http_status')==200
            and last.get('transport_started_at') and last.get('finished_at')
            and last.get('role_result_status')=='json_parsed'
            and not any(a.get('status')=='reserved' for a in attempts)):
        return report
    if len(writer.get('reviews',[]))!=1 or not writer.get('criteria_ids'):
        return report
    review=writer['reviews'][-1]
    if review.get('action')!='revise' or not isinstance(review.get('feedback'),str):
        return report
    report['review_available']=True
    report['manager_action']='revise'
    report['manager_feedback']=review['feedback']
    try:
        from script_quality import inspect_script
        script=parse(writer['versions'][-1]['content'])
        duration=job.get('rework_plan',{}).get('duration_seconds')
        require(type(duration) is int,'rework_duration_invalid')
        inspection=inspect_script(script,job['quality_inputs']['target_segment'],
                                  mock=False,target_duration=duration)
        issues=inspection['defects']
        missing=[d for d in issues if d['issue'] not in review['feedback']]
        report.update(checks_available=True,inspection_hash=digest(inspection),
            saved_script_hash=digest(writer['versions'][-1]),
            saved_review_hash=digest(review),
            defect_count=len(issues),
            missing_issue_ids=[d['issue'] for d in missing],
            missing_defects=[dict(issue=d['issue'],correction=d['correction']) for d in missing])
        report['status']='saved_review_reusable_as_unvalidated_input' if missing else 'review_error_not_reproduced'
        report['safe_for_recovery_proposal']=bool(
            report['reusable_plan'] and report['reusable_writer'] and missing
            and len(attempts)==3 and len(job.get('sessions',[]))==1
            and last.get('response_hash')
            and job.get('final') is None)
    except (CompanyError,ValueError,KeyError,TypeError):
        report['status']='inspection_failed'
    # Historical reviewer transport is NOT validated, and earlier job is immutable.
    return report


def progress_view(job,state):
    """Read-only projection: transport completion never implies server acceptance."""
    from datetime import datetime,timezone,timedelta
    stages=[('consent','전송 동의','대표'),('plan','재기획','AI 관리자'),
            ('writer','대본 작성','대본 직원'),('writer_review','대본 검토','AI 관리자'),
            ('editor','스토리보드 작성','편집 직원'),('editor_review','스토리보드 검토','AI 관리자'),
            ('approval','새 기획 대표 승인 대기','대표')]
    tasks={t['role']:t for t in job.get('assignments',[])}
    completed={'consent':job['real_ai']['consent'].get('approved') is True,'plan':bool(job.get('plan')),
               'approval':state['status']=='completed'}
    for role in ('writer','editor'):
        task=tasks.get(role,{})
        completed[role]=bool(task.get('versions')) and task.get('state')!='revision_requested'
        completed[role+'_review']=task.get('state')=='accepted_by_ai_manager'
    attempts=job['real_ai']['attempts'];latest=attempts[-1] if attempts else None
    current=next((key for key,_,_ in stages if not completed.get(key)), 'approval')
    if state['status']=='running' and latest and latest.get('status')=='reserved':
        role=next((t['role'] for t in tasks.values() if t['id']==latest.get('task_id')),None)
        current='plan' if latest['phase']=='plan' else role+('_review' if latest['phase']=='review' else '') if role else current
    terminal=state['status']=='stopped' or job['status'] in ('stopped','paused','needs_operational_permission')
    error=(state.get('error') or job.get('reason_code')) if terminal else None
    messages={
        'invalid_dependencies':('AI 관리자가 작성한 업무 순서나 참조 관계가 유효하지 않아 기획안 검증에서 중단됐습니다. 새 대본은 아직 생성되지 않았습니다.','담당 개발 점검이 필요합니다. 다시 실행하지 마세요.'),
        'gemini_execution_disabled':('Gemini 실행 설정이 꺼져 있어 시작하지 못했습니다.','서버 실행 설정을 확인하고 재시작하세요. 전송 0 검증을 통과한 경우에만 재개할 수 있습니다.'),
        'consent_expired':('외부 전송 동의의 유효기간이 지났습니다.','새 동의 범위를 확인해야 합니다. 기존 실행을 반복하지 마세요.'),
        'provider_unavailable':('AI 제공자 서비스 오류로 중단됐습니다.','기존 시도를 보존했습니다. 담당자 확인 전 다시 실행하지 마세요.'),
        'provider_rate_limit':('AI 제공자의 요청 한도에 도달했습니다.','한도와 기존 시도 기록 확인이 필요합니다. 자동 재시도하지 않습니다.'),
        'provider_quota_or_billing':('제공자 이용 한도 또는 무료 조건을 확인해야 합니다.','유료 전환 없이 담당자에게 이용 조건 확인을 요청하세요.'),
        'free_request_failed':('연결 오류 또는 응답 미확정으로 중단됐습니다.','수신 여부 확인 전 다시 실행하지 마세요.'),
        'known_script_defects':('대본의 품질 결함이 남아 서버가 수락을 막았습니다.','검토 결과를 보존했습니다. 추가 수정 범위 확인이 필요합니다.'),
        'rework_goal_not_met':('대표 피드백 또는 원 목표 충족 검토를 통과하지 못했습니다.','담당자에게 의미 검토 결과와 추가 수정 범위를 확인해 주세요.')}
    message,action=messages.get(error,('AI 작업 검증 또는 실행 중 문제가 발견되어 중단됐습니다.','기존 기록을 보존했습니다. 담당자 점검 전 다시 실행하지 마세요.')) if terminal else (
        ('새 기획·대본·스토리보드의 검토가 완료됐습니다.','새 버전과 이전 버전을 비교하고 승인 또는 수정 요청을 선택하세요.') if state['status']=='completed' else
        ('승인된 범위의 AI 작업을 진행하고 있습니다.','상태 새로고침으로 진행 상황을 확인하세요. 새로고침은 실행하지 않습니다.') if state['status']=='running' else
        ('외부 전송 동의와 실행 준비를 확인해 주세요.','동의 준비·검토 후 명시적으로 시작하세요.'))
    timestamps=[x.get(k) for x in job.get('events',[])+attempts+state.get('recovery_events',[])
                for k in ('at','finished_at','response_received_at','reserved_at') if x.get(k)]
    updated=None
    for value in timestamps:
        try:
            parsed=datetime.fromisoformat(value)
            if parsed.tzinfo and (updated is None or parsed>updated):updated=parsed
        except (ValueError,TypeError):pass
    cards=[dict(id=key,label=label,actor=actor,state='완료' if completed.get(key) else
                '중단' if terminal and key==current else '진행 중' if state['status']=='running' and key==current else '대기')
           for key,label,actor in stages]
    selected=next(c for c in cards if c['id']==current)
    latest_followup=(job.get('quality_followups') or [None])[-1]
    decision_required=(terminal and latest_followup is not None
                       and latest_followup.get('decision')=='stop'
                       and job.get('reason_code')=='manager_stopped')
    if decision_required:
        items=', '.join(latest_followup.get('failed_checks',{})) or '품질 검토 및 수정 횟수'
        message='AI 관리자 검토 결과 추가 판단이 필요합니다. 문제 항목: '+items+'. 수정 제안: '+latest_followup.get('feedback','')[:900]
        action='대표에게 현 대본과 관리자 수정 지시를 보고하고, 수정·보류·재기획 중 지시를 받으세요. 추가 AI 호출은 자동 실행하지 않습니다.'
    return dict(title='대표 판단 필요 · AI 품질 검토 보고' if decision_required else
                     '재작업 중단 · 새 결과 미완료' if terminal else '새 기획 대표 승인 대기' if state['status']=='completed' else
                     selected['label']+(' 진행 중' if state['status']=='running' else ' 대기'),
        actor=selected['actor'],current=selected['label'],cards=cards,message=message,next_action=action,
        updated_at=updated.astimezone(timezone(timedelta(hours=9))).isoformat() if updated else None,
        counts=dict(attempts=len(attempts),transport_started=sum(bool(a.get('transport_started_at')) for a in attempts),
            http_ok=sum(a.get('http_status')==200 for a in attempts),
            server_validated=sum(a.get('role_result_status')=='validated' for a in attempts),
            failed=sum(a.get('status')=='failed' for a in attempts)),
        ledger=[{k:a.get(k) for k in ('phase','task_id','status','http_status','role_result_status','reserved_at',
                'finished_at','response_hash','request_hash','transport_started_at')} for a in attempts],
        quality_report=latest_followup if decision_required else None)


def snapshot(project):
    flow=project['representative'];prior=flow['plan_versions'][-1];decision=flow['decisions'][-1]
    require(decision['stage']=='plan' and decision['action']=='request_revision'
            and decision['sha256']==prior['sha256'],'rework_feedback_binding')
    editor=next(t for t in prior['task_history'] if t['role']=='editor')
    return dict(representative_project=project['id'],representative_feedback=deepcopy(decision),
        previous_plan=dict(version=prior['version'],sha256=prior['sha256'],script=prior['script'],
                           storyboard=parse(editor['versions'][-1]['content'])),
        observations=deepcopy(prior['research']['observations']))


class ReworkStore(QualityProviderStore):
    max_consent_bytes = 65536
    _limits=staticmethod(Gemini35Store._limits)

    def require_unstarted(self,p):
        # A recovered plan/writer is local provenance only, never a prior send in this job.
        require(self.valid_mode(p) and p.get('simulation') is False
                and p['status']=='ready' and not p.get('reason_code')
                and not p['real_ai']['attempts'] and not p.get('attempts')
                and not p['sessions'] and not p['active_operation']
                and not p.get('run_started_at') and not p.get('next_request_at') and not p.get('providers')
                and not p['artifacts'] and not p['final']
                and len(p['events'])==1 and p['events'][0]['event']=='operating_scope_approved',
                'rework_zero_send_not_proven')
        recovery=p.get('script_recovery')
        if not recovery:
            require(p['phase']=='plan' and not p['plan'] and not p['assignments'],
                    'rework_zero_send_not_proven')
            return
        parent=p['rework_reference'].get('previous_failed_attempt',{})
        require(parent.get('recovery_scope')=='validated_plan_writer_reuse_new_job'
                and parent['job']==recovery['source_job']
                and parent['previous_plan_hash']==recovery['original_plan_hash']
                and parent['previous_writer_hash']==recovery['original_writer_hash']
                and parent['previous_review_hash']==recovery['original_review_hash']
                and parent['inspection_hash']==recovery['inspection_hash']
                and recovery['manager_acceptance'] is False
                and recovery['source_request_replayed'] is False
                and p['phase']=='work' and p['plan'] is not None
                and digest(p['plan'])==recovery['original_plan_hash']
                and len(p['assignments'])==2
                and [t['role'] for t in p['assignments']]==['writer','editor'],
                'rework_recovery_seed_mismatch')
        writer,editor=p['assignments']
        require(writer['state']=='revision_requested' and writer['revisions']==0
                and len(writer['versions'])==1 and len(writer['reviews'])==1
                and writer['reviews'][0].get('approved_by_manager') is False
                and writer['reviews'][0].get('source')=='system_recovery_instruction_from_unvalidated_manager_review'
                and editor['state']=='pending' and not editor['versions'] and not editor['reviews']
                and not editor['revisions'],'rework_recovery_seed_mismatch')
        original=deepcopy(writer['versions'][0]);original.pop('reused_from_job',None)
        require(digest(original)==recovery['original_writer_hash']
                and writer['reviews'][0]['original_review_hash']==recovery['original_review_hash'],
                'rework_recovery_seed_mismatch')

    def verify_disabled_recovery(self,p,state,key):
        require(state.get('status')=='stopped' and state.get('error')=='gemini_execution_disabled',
                'rework_disabled_recovery_forbidden')
        self.require_unstarted(p)
        grant=self.grant(p)
        require(hmac.compare_digest(grant['body']['rework_scope']['credential_binding'],_binding(p['id'],key)),
                'rework_key_changed')
        return grant

    def check_binding(self,p):
        ref=p['rework_reference'];project=Store(self.root.parent).load(ref['project'])
        flow=project['representative'];prior=flow['plan_versions'][ref['version']-1]
        decision=next((d for d in flow['decisions'] if digest(d)==ref['decision_hash']),None)
        require(prior['sha256']==ref['plan_hash'] and decision is not None
                and flow.get('rework',{}).get('job')==p['id'] and project['goal']==p['goal']
                and digest(p['quality_inputs']['answers'])==ref['input_hash'],'rework_source_changed')
        require(digest({k:v for k,v in prior.items() if k!='sha256'})==prior['sha256'], 'rework_plan_tampered')
        parent=ref.get('previous_failed_attempt')
        if parent:
            old=self.load(parent['job']);grant=parse(self._grant_path(parent['job']).read_text())
            require(old['storage_hash']==parent['state_hash'] and digest(grant)==parent['grant_hash']
                    and hmac.compare_digest(grant['signature'],self._sign(grant['record'])), 'rework_parent_changed')


    def prepare(self,pid,*,key,account_project,**kwargs):
        require(account_project==MISSION_ACCOUNT,'rework_free_project_required')
        p=self.load(pid);self.check_binding(p)
        b=super().prepare(pid,confirm_free_account=True,valid_hours=1)
        return dict(b,rework_scope=dict(reference=p['rework_reference'],account_project=account_project,
            credential_binding=_binding(pid,key),data_policy=DATA_POLICY,billing='unverified',quota='unknown',
            new_youtube_calls=0,automatic_retry=False,instructions_hash=digest(NOTICE),plan_contract_hash=digest(PLAN_RULES)))

    def _check_contract(self,p,b):
        self.check_binding(p);scope=b.get('rework_scope',{})
        require(scope.get('reference')==p['rework_reference'] and scope.get('account_project')==MISSION_ACCOUNT
                and scope.get('data_policy')==DATA_POLICY and scope.get('new_youtube_calls')==0
                and scope.get('automatic_retry') is False and scope.get('instructions_hash')==digest(NOTICE),
                'rework_consent_scope')
        if 'plan_contract_hash' in scope:
            require(scope['plan_contract_hash']==digest(PLAN_RULES),'rework_plan_contract_changed')
        super()._check_contract(p,{k:v for k,v in b.items() if k!='rework_scope'})


class ReworkCompany(MissionOneCompany):
    store_type=ReworkStore

    def _validate_script_plan(self,value):
        # Rework grants allow manager-selected criterion IDs, unlike production plans.
        validate_rework_plan(value)

    def run(self,project_id,**kwargs):
        job=self.store.load(project_id)
        require(job['status']=='ready' and not job['sessions'] and not job['real_ai']['attempts'],'rework_restart_forbidden')
        return super().run(project_id,**kwargs)

    def _quality_transport_allowed(self,p):
        record=self.store.grant(p)
        validator=record['body']['rework_scope']['reference'].get('previous_failed_attempt',{}).get('handoff_validator')
        require(validator is None or validator==handoff_validator_identity(),'rework_handoff_validator_changed')
        require(record['body']['rework_scope'].get('plan_contract_hash')==digest(PLAN_RULES),'rework_new_plan_consent_required')
        require(hmac.compare_digest(record['body']['rework_scope']['credential_binding'],_binding(p['id'],self.config.api_key)),
                'rework_key_changed')
        return True

    def _tool_notice(self,p):
        return VideoProviderQualityCompany._tool_notice(self,p).replace('target_duration=60','target_duration=replan.duration_seconds')+NOTICE+PLAN_RULES

    def _manager_selection(self,p):
        return p.get('rework_plan')

    def _script_duration(self,p):
        return p.get('rework_plan',{}).get('duration_seconds',25)

    def _schema(self,phase):
        schema=deepcopy(response_format(phase)['json_schema']['schema'])
        if phase=='plan':
            target=schema['properties']['result']['anyOf'][0]
            target['properties']['replan']=obj(selected_topic=S,duration_seconds={'type':'integer','minimum':4,'maximum':180},duration_reason=S,feedback_response=S)
            target['required'].append('replan')
            target['properties']['tasks'].update(minItems=2,maxItems=2)
            target['properties']['tasks']['items']['description']=PLAN_RULES
        elif phase=='review':
            target=schema['properties']['result']
            target['properties']['goal_review']=obj(**{k:obj(met={'type':'boolean'},evidence=S) for k in CHECKS})
            target['required'].append('goal_review')
        return schema

    def _prepare_payload(self,payload):
        payload=super()._prepare_payload(payload)
        phase=parse(payload['contents'][0]['parts'][0]['text'])['phase']
        if phase in ('plan','review'):
            schema=self._schema(phase);payload['generationConfig']['responseJsonSchema']=schema
            message=parse(payload['contents'][0]['parts'][0]['text']);message['output_contract']=schema
            if phase=='plan':message['output_contract']=PLAN_SCHEMA_REFERENCE
            payload['contents'][0]['parts'][0]['text']=json.dumps(message,ensure_ascii=False)
        return payload

    def _validate_payload(self,payload):
        phase=parse(payload['contents'][0]['parts'][0]['text'])['phase']
        if phase in ('plan','review'):
            require(payload['generationConfig']['responseJsonSchema']==self._schema(phase),'rework_schema_changed')
            if phase=='plan':
                require(parse(payload['contents'][0]['parts'][0]['text']).get('output_contract')==PLAN_SCHEMA_REFERENCE,
                        'rework_schema_reference_changed')
            payload=deepcopy(payload);schema=response_format(phase)['json_schema']['schema']
            payload['generationConfig']['responseJsonSchema']=schema
            message=parse(payload['contents'][0]['parts'][0]['text']);message['output_contract']=schema
            payload['contents'][0]['parts'][0]['text']=json.dumps(message,ensure_ascii=False)
        return super()._validate_payload(payload)

    def _parse_role_content(self,raw,phase):
        if phase in ('plan','review'):
            value=parse(raw);require(matches(value,self._schema(phase)),'rework_response_schema')
            result=value['result']
            if phase=='plan' and 'tasks' in result:
                self._decision=result.pop('replan')
                try:
                    for field in ('selected_topic','duration_reason','feedback_response'):text(self._decision[field],4000)
                    require(type(self._decision['duration_seconds']) is int and 4<=self._decision['duration_seconds']<=180,
                            'rework_duration_invalid')
                    validate_rework_plan(result)
                except CompanyError as exc:
                    state=self._rework_state
                    entry=state['real_ai']['attempts'][-1]
                    entry['plan_validation_diagnostics']=dict(stage='rework_plan_relations',
                        **getattr(exc,'diagnostics',dict(task_index=None,field='replan',detail=exc.code)),response_hash=entry.get('response_hash'))
                    self.store.save(state)
                    raise
            elif phase=='review':
                self._semantic=result.pop('goal_review')
                self._quality_followup=None
                content=self._review_content
                artifact=parse(content)
                def evidence_in_artifact(quote,value):
                    if isinstance(value,str):return quote in value
                    if isinstance(value,list):return any(evidence_in_artifact(quote,v) for v in value)
                    if isinstance(value,dict):return any(evidence_in_artifact(quote,v) for v in value.values())
                    return False
                failed={}
                for name,check in self._semantic.items():
                    if check['met'] is not True:
                        failed[name]='not_met'
                    elif not check['evidence'].strip() or not (
                        check['evidence'] in content or evidence_in_artifact(check['evidence'],artifact)
                    ):
                        failed[name]='evidence_not_found'
                if result['action']=='accept':
                    for criterion in result['checks']:
                        if criterion['status']!='met':
                            failed['criterion:'+criterion['criterion_id']]='criterion_not_met'
                    if re.search(r'골든타임|(?:쇼츠|영상)\s*(?:제작법|만드는\s*방법)|편집\s*노하우',content):
                        failed['subject_story']='obvious_goal_drift'
                if result['action']=='accept' and failed:
                    state=self._rework_state
                    task=next(t for t in state['assignments'] if t['id']==self._review_task_id)
                    revisions_available=(task['revisions']<state['limits']['max_revisions_per_task']
                        and sum(t['revisions'] for t in state['assignments'])<state['limits']['max_total_revisions'])
                    # Preserve the model's judgment. This is a deterministic safety
                    # correction, never a claim that the manager actually chose revise.
                    original=result['action']
                    reasons=', '.join(name+': '+category for name,category in failed.items())
                    feedback=('대표 피드백과 원래 게임 이야기 목표를 재확인하고 다음 항목을 수정하세요: '
                              +reasons+'. 근거 없는 성과 단정은 삭제하거나 미확인으로 표시하세요. '
                              '수정 후 실제 대본 문장을 근거로 다시 검토받으세요.')
                    result['action']='revise' if revisions_available else 'stop'
                    result['feedback']=feedback
                    result['rationale']=(result['rationale']+' [시스템 품질 검증: '
                        +('직원 재수정 필요' if revisions_available else '대표 판단 필요')
                        +'; '+reasons+']')
                    self._quality_followup=dict(task_id=self._review_task_id,
                        original_action=original,decision=result['action'],
                        failed_checks=failed,
                        evidence={name:self._semantic[name]['evidence'][:200] for name in failed if name in self._semantic},
                        feedback=feedback,reason='manager_accept_conflicted_with_goal_review')
                elif result['action']=='stop':
                    self._quality_followup=dict(task_id=self._review_task_id,
                        original_action='stop',decision='stop',
                        failed_checks=failed,feedback=result['feedback'],
                        reason='manager_requested_representative_decision')
                elif result['action']=='revise':
                    state=self._rework_state
                    task=next(t for t in state['assignments'] if t['id']==self._review_task_id)
                    remaining=(task['revisions']<state['limits']['max_revisions_per_task']
                        and sum(t['revisions'] for t in state['assignments'])<state['limits']['max_total_revisions'])
                    if not remaining:
                        self._quality_followup=dict(task_id=self._review_task_id,
                            original_action='revise',decision='stop',
                            failed_checks=failed,feedback=result['feedback'],
                            reason='revision_limit_reached')
                        result['action']='stop'
                        result['rationale']+=' [시스템: 수정 횟수 한도 도달, 대표 판단 필요]'
            raw=json.dumps(value,ensure_ascii=False)
        return super()._parse_role_content(raw,phase)

    def _call(self,p,provider,phase,task_id,context):
        if phase=='finalize':
            self.store.grant(p)
            require(all(t['state']=='accepted_by_ai_manager' for t in p['assignments']),'rework_not_accepted')
            return dict(action='deliver',content='대표 수정 요청에 따른 새 대본·스토리보드 검토 완료',
                rationale=p['rework_plan']['feedback_response'],uncertainty='권리·성과 및 대표 승인 미확정',
                checks=deepcopy(p['assignments'][0]['reviews'][-1]['checks']),
                task_refs=[dict(task_id=r['task_id'],revision=r['revision'],result_hash=digest(r)) for r in context['results']])
        if phase=='review':
            self._review_content=json.dumps(parse(context['result']['content']),ensure_ascii=False)
            self._review_task_id=task_id
            self._quality_followup=None
        from script_quality import writer_contract,validate_writer_contract
        selection=p.get('rework_plan')
        contract=(writer_contract(p['quality_inputs']['target_segment'],selection['duration_seconds'],MODEL,selection['selected_topic'])
                  if selection and phase=='execute' and context['assignment']['role']=='writer' else None)
        if contract:context={**context,'quality':{**context['quality'],'writer_contract':contract}}
        self._research_review_state=None
        self._writer_wire_contract=contract;self._writer_wire_state=p if contract else None
        self._rework_state=p
        try:result=VideoProviderQualityCompany._call(self,p,provider,phase,task_id,context)
        finally:self._writer_wire_contract=None;self._writer_wire_state=None;self._rework_state=None
        if contract:validate_writer_contract(parse(result['content']),contract)
        if phase=='plan' and 'tasks' in result:
            require([t['role'] for t in result['tasks']]==['writer','editor'],'rework_roles_required')
            p['rework_plan']=deepcopy(self._decision)
        if phase=='review':
            p.setdefault('goal_reviews',[]).append(dict(task_id=task_id,review=deepcopy(self._semantic)))
            if self._quality_followup is not None:
                p.setdefault('quality_followups',[]).append(deepcopy(self._quality_followup))
                self.store.save(p)
        return result

    def _validate_review_decision(self,p,task,review):
        # Model-generated Korean revision feedback is valid without repeating
        # machine-only defect codes verbatim. Preserve the manager's original
        # review event; attach deterministic issues for the writer separately.
        if task['role']=='writer' and review['action']=='revise':
            from script_quality import inspect_script
            inspection=inspect_script(
                parse(task['versions'][-1]['content']),
                p['quality_inputs']['target_segment'],
                mock=False,target_duration=self._script_duration(p))
            missing=[d for d in inspection['defects'] if d['issue'] not in review['feedback']]
            if missing:
                original=review['feedback']
                review['feedback']=original+'\n[시스템 자동 검출 항목 — AI 관리자 원문과 별개]\n'+\
                    '\n'.join(d['issue']+': '+d['correction'] for d in missing)
                p['events'].append(dict(at=__import__('autonomous_company').now(),
                    event='system_script_defects_attached',task_id=task['id'],
                    manager_feedback_hash=digest(original),
                    appended_defects=[dict(issue=d['issue'],evidence=d['evidence'],
                                           correction=d['correction']) for d in missing],
                    approved_by_manager=False))
        return super()._validate_review_decision(p,task,review)

    def _delivery_blockers(self,p):
        p['final'].update(provider='system',source='accepted_review_handoff')
        return ['needs_user_review']


def handoff_validator_identity():
    return dict(version='rework-plan-handoff-1c024346',code_hash=digest(
        inspect.getsource(ReworkCompany._validate_script_plan)+inspect.getsource(validate_rework_plan)))


def failed_plan_reference(store,project,key):
    state=project['representative']['rework'];old=store.load(state['job'])
    require(state['status']=='stopped' and old['status'] in ('stopped','paused')
            and old.get('reason_code') in ('invalid_dependencies','rework_plan_invalid','provider_unavailable','script_plan_handoff_required')
            and state.get('error')==old.get('reason_code')
            and old['phase']=='plan' and not old['plan'] and not old['assignments'] and not old['final'],
            'rework_new_attempt_not_eligible')
    store.check_binding(old)
    attempts=old['real_ai']['attempts']
    require(len(attempts)==1 and len(old['sessions'])==1,'rework_new_attempt_uncertain')
    attempt=attempts[0]
    unavailable=old['reason_code']=='provider_unavailable'
    handoff_failure=old['reason_code']=='script_plan_handoff_required'
    prior_validator=old['rework_reference'].get('previous_failed_attempt',{}).get('handoff_validator')
    if handoff_failure:
        require(old['status']=='stopped' and old['active_operation']==attempt['id']
                and attempt.get('finished_at'),'rework_new_attempt_uncertain')
        require(prior_validator!=handoff_validator_identity(),'rework_same_validator_new_attempt_forbidden')
    completed_503=(attempt['status']=='failed' and attempt.get('http_status')==503
        and attempt.get('error_code')=='provider_unavailable' and attempt.get('finished_at')
        and attempt.get('request_hash') and attempt.get('role_result_status')=='unvalidated'
        and attempt.get('response_hash') is None)
    parsed_plan=(attempt['status']=='completed' and attempt.get('http_status')==200
        and attempt.get('role_result_status')=='json_parsed' and attempt.get('response_hash')
        and attempt.get('response_received_at'))
    require(attempt['phase']=='plan' and (completed_503 if unavailable else parsed_plan)
            and attempt.get('transport_started_at')
            and attempt['model']==MODEL and old['active_operation'] in (None,attempt['id']),
            'rework_new_attempt_uncertain')
    if unavailable:
        parent=old['rework_reference'].get('previous_failed_attempt',{})
        require(not parent.get('recovery_scope') or parent.get('contract_hash')!=digest(PLAN_RULES),
                'rework_same_contract_new_attempt_forbidden')
    grant=parse(store._grant_path(old['id']).read_text());record=grant['record'];body=record['body'];scope=body['rework_scope']
    require(hmac.compare_digest(grant['signature'],store._sign(record)) and record['revoked_at'] is None
            and old['real_ai']['consent'].get('operating_grant_id')==record['id']
            and state['proposal']==body and scope['reference']==old['rework_reference']
            and body['quality_contract']['inputs']==old['quality_inputs'] and body['model']==MODEL and body['endpoint']==ENDPOINT
            and body['free_only'] is True and scope['account_project']==MISSION_ACCOUNT and scope['data_policy']==DATA_POLICY,
            'rework_history_signature_invalid')
    require(unavailable or handoff_failure or scope.get('plan_contract_hash')!=digest(PLAN_RULES),'rework_same_contract_new_attempt_forbidden')
    require(hmac.compare_digest(scope['credential_binding'],_binding(old['id'],key)),'rework_key_changed')
    # Expired historical consent proves history only; it never authorizes this new request.
    return dict(job=old['id'],state_hash=old['storage_hash'],grant_hash=digest(grant),
                attempt_id=attempt['id'],contract_hash=digest(PLAN_RULES),
                **(dict(handoff_validator=handoff_validator_identity()) if handoff_failure else
                   dict(handoff_validator=prior_validator) if prior_validator is not None else {}),
                **(dict(recovery_scope='one_new_plan_after_final_http503_no_retry') if unavailable else {}))


def legacy_quality_report(job,state):
    """Historical review rejected after HTTP 200. This is NOT a validated manager review."""
    if not (state.get('status')=='stopped' and state.get('error')=='rework_goal_not_met'
            and job.get('status')=='stopped' and job.get('reason_code')=='rework_goal_not_met'
            and job.get('phase')=='work' and not job.get('final')):
        return None
    attempts=job.get('real_ai',{}).get('attempts',[])
    if not attempts or not all(a.get('status')=='completed' and a.get('http_status')==200
            and a.get('transport_started_at') for a in attempts):
        return None
    last=attempts[-1]
    if last.get('phase')!='review' or last.get('role_result_status')!='unvalidated':
        return None
    writer=next((t for t in job.get('assignments',[])
                 if t.get('role')=='writer' and t.get('versions')),None)
    if writer is None or writer.get('reviews'):
        return None
    return dict(decision='stop',reason='legacy_unvalidated_review',
                original_action='unknown_unvalidated',
                failed_checks=dict(goal_fit='historical_goal_review_failed'),
                evidence=dict(review_status='unvalidated',http_status=200,
                              attempt_id=last.get('id','')),
                feedback=('과거 검토 응답은 서버 검증에 실패했습니다. AI 관리자의 정상 검토 의견으로 간주할 수 없습니다. '
                          '저장된 대본을 직접 검토해 구체적인 수정 지시를 입력하세요.'),
                source='legacy_failure_diagnostic_not_manager_review')


def quality_decision_reference(store,project,key):
    """Allow a new job only after an explicitly recorded CEO correction request."""
    flow=project['representative'];state=flow.get('rework',{})
    decision=state.get('quality_decision')
    require(decision and decision.get('action')=='request_revision'
            and decision.get('job')==state.get('job'),'quality_revision_decision_required')
    old=store.load(state['job'])
    legacy=legacy_quality_report(old,state)
    require((legacy is not None) or (
            state.get('status')=='stopped' and state.get('error')=='manager_stopped'
            and old['status']=='stopped' and old.get('reason_code')=='manager_stopped'
            and old.get('phase')=='work' and not old.get('final')),
            'quality_revision_source_not_stopped')
    store.check_binding(old)
    report=legacy if legacy is not None else progress_view(old,state).get('quality_report')
    require(report is not None and report.get('decision')=='stop'
            and decision.get('report_hash')==digest(report)
            and bool(decision.get('feedback','').strip()),'quality_revision_report_changed')
    attempts=old['real_ai']['attempts']
    require(all(a.get('status')=='completed' and a.get('http_status')==200
                and a.get('transport_started_at') and a.get('finished_at')
                for a in attempts)
            and not any(a.get('status')=='reserved' for a in attempts)
            and (not old.get('active_operation') or
                 (legacy is not None and old['active_operation']==attempts[-1].get('id'))),
            'quality_revision_uncertain_transport')
    writer=next((t for t in old['assignments'] if t.get('role')=='writer' and t.get('versions')),None)
    require(writer is not None and len(old.get('sessions',[]))==1,'quality_revision_missing_writer')
    grant=parse(store._grant_path(old['id']).read_text())
    record=grant['record'];body=record['body'];scope=body['rework_scope']
    require(hmac.compare_digest(grant['signature'],store._sign(record))
            and record.get('revoked_at') is None
            and old['real_ai']['consent'].get('operating_grant_id')==record['id']
            and state.get('proposal')==body and scope.get('reference')==old['rework_reference']
            and body['quality_contract']['inputs']==old['quality_inputs']
            and body.get('free_only') is True and body.get('model')==MODEL
            and body.get('endpoint')==ENDPOINT
            and scope.get('account_project')==MISSION_ACCOUNT
            and scope.get('data_policy')==DATA_POLICY
            and hmac.compare_digest(scope.get('credential_binding',''),_binding(old['id'],key)),
            'quality_revision_history_invalid')
    return dict(job=old['id'],state_hash=old['storage_hash'],grant_hash=digest(grant),
                quality_decision_hash=digest(decision),quality_report_hash=digest(report),
                writer_version_hash=digest(writer['versions'][-1]),
                scope='new_job_after_ceo_quality_instruction')



def script_review_recovery_reference(store,project,key):
    """Signed and immutable source proof for a new, revision-only job."""
    flow=project['representative'];state=flow.get('rework',{})
    old=store.load(state['job'])
    audit=script_review_recovery_audit(old,state)
    require(audit and audit['safe_for_recovery_proposal'],'rework_script_reuse_not_proven')
    store.check_binding(old)
    grant=parse(store._grant_path(old['id']).read_text())
    record=grant['record'];body=record['body']
    require(hmac.compare_digest(grant['signature'],store._sign(record))
            and record['revoked_at'] is None
            and old['real_ai']['consent'].get('operating_grant_id')==record['id']
            and state.get('proposal')==body
            and body.get('model')==MODEL and body.get('endpoint')==ENDPOINT
            and body.get('free_only') is True
            and body.get('rework_scope',{}).get('reference')==old['rework_reference']
            and body['quality_contract']['inputs']==old['quality_inputs']
            and body['rework_scope'].get('account_project')==MISSION_ACCOUNT
            and hmac.compare_digest(body['rework_scope'].get('credential_binding',''),
                                     _binding(old['id'],key)),'rework_history_signature_invalid')
    writer=next(t for t in old['assignments'] if t['role']=='writer')
    require(len(old['assignments'])==2 and old['assignments'][1]['role']=='editor'
            and not old['assignments'][1].get('versions')
            and len(writer['versions'])==1 and writer['reviews'][0]['action']=='revise',
            'rework_script_reuse_not_proven')
    return dict(job=old['id'],state_hash=old['storage_hash'],
                grant_hash=digest(grant),recovery_scope='validated_plan_writer_reuse_new_job',
                previous_plan_hash=digest(old['plan']),
                previous_writer_hash=digest(writer['versions'][-1]),
                previous_review_hash=digest(writer['reviews'][-1]),
                inspection_hash=audit['inspection_hash'],
                previous_attempt_count=len(old['real_ai']['attempts']),
                previous_review_unvalidated=True)


def seed_recovered_script_job(job,old,audit):
    """Reuse validated artifacts, never old consent, calls or a fabricated manager accept."""
    require(audit['safe_for_recovery_proposal'],'rework_script_reuse_not_proven')
    from script_quality import inspect_script
    writer=next(t for t in old['assignments'] if t['role']=='writer')
    inspection=inspect_script(parse(writer['versions'][-1]['content']),
        old['quality_inputs']['target_segment'],mock=False,
        target_duration=old['rework_plan']['duration_seconds'])
    require(digest(inspection)==audit['inspection_hash'],'rework_script_reuse_changed')
    missing=[d for d in inspection['defects'] if d['issue'] not in writer['reviews'][-1]['feedback']]
    feedback=(writer['reviews'][-1]['feedback']+
        ('\n[시스템 검출 결함 — 관리자 원문이 아님]\n'+
         '\n'.join(d['issue']+': '+d['correction'] for d in missing) if missing else ''))
    job['plan']=deepcopy(old['plan'])
    job['rework_plan']=deepcopy(old['rework_plan'])
    job['assignments']=[]
    for task in old['assignments']:
        copy=deepcopy(task)
        copy['reviews']=[]
        copy['versions']=[]
        copy['revisions']=0
        if copy['role']=='writer':
            version=deepcopy(writer['versions'][-1])
            version['reused_from_job']=old['id']
            copy['versions']=[version]
            copy['reviews']=[dict(action='revise',feedback=feedback,
                source='system_recovery_instruction_from_unvalidated_manager_review',
                original_review_hash=digest(writer['reviews'][-1]),
                approved_by_manager=False)]
            copy['state']='revision_requested'
        else:copy['state']='pending'
        job['assignments'].append(copy)
    job['phase']='work'
    job['script_recovery']=dict(source_job=old['id'],
        original_plan_hash=digest(old['plan']),
        original_writer_hash=digest(writer['versions'][-1]),
        original_review_hash=digest(writer['reviews'][-1]),
        inspection_hash=audit['inspection_hash'],manager_acceptance=False,
        original_call_count=len(old['real_ai']['attempts']),
        initial_task_state='revision_requested',source_request_replayed=False)
    return job


def prepare(workflow,pid,key,account,*,previous_job=None,quality_decision=False,script_recovery=False):
    with workflow.store.lock(pid):
        project=workflow.store.load(pid);flow=project['representative']
        require(flow['stage']=='plan_revision','rework_stage')
        store=ReworkStore(workflow.store.root/'representative_rework')
        parent=None
        if previous_job is not None:
            require(flow.get('rework',{}).get('job')==previous_job,'rework_stale_new_attempt')
            parent=(script_review_recovery_reference(store,project,key) if script_recovery
                    else quality_decision_reference(store,project,key) if quality_decision
                    else failed_plan_reference(store,project,key))
            flow.setdefault('rework_history',[]).append(deepcopy(flow['rework']))
        elif flow.get('rework'):
            if flow['rework']['decision_hash']==digest(flow['decisions'][-1]):return
            require(flow['rework']['status']=='completed','rework_already_exists')
            flow.setdefault('rework_history',[]).append(deepcopy(flow['rework']))
        # Refuse an orphan left after a partially saved preparation instead of recreating it.
        archived={item['job'] for item in flow.get('rework_history',[])}
        for path in store.root.glob('qualityprovider-*.json'):
            if '.consent.' not in path.name:
                existing=store.load(path.stem)
                require(existing['id'] in archived or existing.get('rework_reference',{}).get('decision_hash')!=digest(flow['decisions'][-1]),'rework_orphan_exists')
        answers=snapshot(project)
        if quality_decision:
            old=store.load(previous_job);decision=flow['rework']['quality_decision']
            writer=next(t for t in old['assignments'] if t['role']=='writer' and t.get('versions'))
            answers['quality_followup']=dict(
                representative_instruction=decision['feedback'],
                source_job=old['id'],source_report_hash=decision['report_hash'],
                failed_checks=deepcopy(legacy_quality_report(old,flow['rework'])['failed_checks']
                    if legacy_quality_report(old,flow['rework']) else
                    old['quality_followups'][-1].get('failed_checks',{})),
                manager_feedback=(legacy_quality_report(old,flow['rework'])['feedback']
                    if legacy_quality_report(old,flow['rework']) else
                    old['quality_followups'][-1].get('feedback','')),
                previous_writer=deepcopy(parse(writer['versions'][-1]['content'])))
        job=store.create(project['goal'],inputs=dict(domain='video',target_segment=flow['audience'],answers=answers,
            constraints=dict(aspect='9:16',language='한국어',platform='YouTube Shorts'),
            capabilities=dict(script_contract=SCRIPT_CONTRACT),experiences=[],
            feedback_text=(flow['decisions'][-1]['feedback']+
                (' | 대표 추가 수정 지시: '+flow['rework']['quality_decision']['feedback'] if quality_decision else ''))),
            max_calls=7,max_revisions_per_task=1,max_total_revisions=1)
        prior=flow['plan_versions'][-1]
        job['rework_reference']=dict(project=pid,version=prior['version'],plan_hash=prior['sha256'],
            decision_hash=digest(flow['decisions'][-1]),input_hash=digest(answers))
        if parent:job['rework_reference']['previous_failed_attempt']=parent
        if script_recovery:
            old=store.load(previous_job)
            audit=script_review_recovery_audit(old,flow['rework'])
            seed_recovered_script_job(job,old,audit)
        store.save(job)
        flow['rework']=dict(job=job['id'],status='pending',decision_hash=job['rework_reference']['decision_hash'])
        workflow.store.save(project)
        proposal=store.prepare(job['id'],key=key,account_project=account)
        flow['rework']['proposal']=proposal
        workflow.store.save(project)



def cap_pending_proposal(workflow,pid,key):
    """Restrict a not-yet-approved old proposal to seven calls. Never send to a provider."""
    with workflow.store.lock(pid):
        project=workflow.store.load(pid)
        state=project['representative'].get('rework',{})
        require(state.get('status')=='pending' and state.get('proposal'),'rework_pending_cap_required')
        store=ReworkStore(workflow.store.root/'representative_rework')
        job=store.load(state['job'])
        require(job['status']=='ready' and job['phase']=='plan'
                and not job.get('sessions') and not job.get('active_operation')
                and not job['real_ai']['attempts'] and not job['real_ai']['consent']
                and not store._grant_path(job['id']).exists(),
                'rework_pending_cap_required')
        store.check_binding(job)
        require(state['proposal'].get('initial_state_hash')==job['storage_hash']
                and state['proposal'].get('rework_scope',{}).get('credential_binding')
                    ==_binding(job['id'],key),'rework_pending_proposal_changed')
        cap=job['limits']['max_calls']
        require(cap is None or cap==7,'rework_pending_cap_required')
        if cap is None:
            job['limits']['max_calls']=7
            store.save(job)
        state['proposal']=store.prepare(job['id'],key=key,account_project=MISSION_ACCOUNT)
        workflow.store.save(project)


def handoff(workflow,pid,provider,*,allow_fixture=False):
    with workflow.store.lock(pid):
        project=workflow.store.load(pid);flow=project['representative'];job=provider.result(flow['rework']['job'])
        provider.grant(job)
        require(job['status']=='needs_user_review' and job['final']['source']=='accepted_review_handoff'
                and all(t['state']=='accepted_by_ai_manager' for t in job['assignments']),'rework_not_accepted')
        require(all(a['status']=='completed' and a.get('http_status')==200 and a.get('role_result_status')=='validated'
                    for a in job['real_ai']['attempts']),'rework_evidence')
        require(job['plan']['source']=='provider_model_claim' or allow_fixture and job['plan']['source']=='offline_http_fixture','rework_fixture_forbidden')
        if job.get('script_recovery'):
            recovery=job['script_recovery']
            old=provider.load(recovery['source_job'])
            parent=job['rework_reference'].get('previous_failed_attempt',{})
            archived=next((entry for entry in flow.get('rework_history',[])
                           if entry.get('job')==old['id']),None)
            require(archived is not None,'rework_recovery_source_changed')
            audit=script_review_recovery_audit(old,archived)
            original_writer=next(t for t in old['assignments'] if t['role']=='writer')
            require(audit and audit['safe_for_recovery_proposal']
                    and old['storage_hash']==parent.get('state_hash')
                    and digest(old['plan'])==recovery['original_plan_hash']
                    and digest(original_writer['versions'][-1])==recovery['original_writer_hash']
                    and digest(original_writer['reviews'][-1])==recovery['original_review_hash']
                    and digest(job['plan'])==recovery['original_plan_hash']
                    and len(job['assignments'][0]['versions'])>=2
                    and job['assignments'][0]['versions'][0].get('reused_from_job')==old['id']
                    and all(a['role_result_status']=='validated' for a in old['real_ai']['attempts'][:2])
                    and old['real_ai']['attempts'][-1]['role_result_status']=='json_parsed',
                    'rework_recovery_source_changed')
        if flow['plan_versions'][-1].get('internal_job')==job['id']:return
        require(flow['stage']=='plan_revision','rework_stage')
        writer,editor=job['assignments'];script=parse(writer['versions'][-1]['content'])
        validate_script_editor(parse(editor['versions'][-1]['content']),[writer['versions'][-1]])
        prior=flow['plan_versions'][-1]
        report=_report(dict(summary=job['final']['content'],topic=script['topic']['title'],script=script,
            sources=prior['sources'],risks=job['final']['uncertainty'],changes=job['rework_plan']['feedback_response'],
            internal_job=job['id'],previous_plan_sha256=prior['sha256'],render_spec=None,cost_limit_usd=0,
            writer_sha256=digest(writer['versions'][-1]),editor_sha256=digest(editor['versions'][-1]),
            internal_reviews=writer['reviews'],task_history=deepcopy(job['assignments']),manager_plan=job['plan'],
            provenance=job['plan']['source'],representative_feedback=job['quality_inputs']['feedback_text'],
            rework_plan=job['rework_plan'],goal_reviews=job['goal_reviews'],final_evaluation='not_performed_local_handoff',
            research=prior['research'],
            **(dict(recovery_source=deepcopy(job['script_recovery'])) if job.get('script_recovery') else {})
            ),flow['plan_versions'])
        flow['plan_versions'].append(report);flow['rework']['status']='completed'
        workflow._transition(project,'awaiting_plan_approval')
