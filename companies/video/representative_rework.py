"""Explicitly consented representative rework; no web tools, retries or media."""
from copy import deepcopy
import hmac
import json
import re
from autonomous_company import Store, digest, parse, require, text
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

    def check_binding(self,p):
        ref=p['rework_reference'];project=Store(self.root.parent).load(ref['project'])
        flow=project['representative'];prior=flow['plan_versions'][ref['version']-1]
        decision=next((d for d in flow['decisions'] if digest(d)==ref['decision_hash']),None)
        require(prior['sha256']==ref['plan_hash'] and decision is not None
                and flow.get('rework',{}).get('job')==p['id'] and project['goal']==p['goal']
                and digest(p['quality_inputs']['answers'])==ref['input_hash'],'rework_source_changed')
        require(digest({k:v for k,v in prior.items() if k!='sha256'})==prior['sha256'], 'rework_plan_tampered')

    def prepare(self,pid,*,key,account_project,**kwargs):
        require(account_project==MISSION_ACCOUNT,'rework_free_project_required')
        p=self.load(pid);self.check_binding(p)
        b=super().prepare(pid,confirm_free_account=True,valid_hours=1)
        return dict(b,rework_scope=dict(reference=p['rework_reference'],account_project=account_project,
            credential_binding=_binding(pid,key),data_policy=DATA_POLICY,billing='unverified',quota='unknown',
            new_youtube_calls=0,automatic_retry=False,instructions_hash=digest(NOTICE)))

    def _check_contract(self,p,b):
        self.check_binding(p);scope=b.get('rework_scope',{})
        require(scope.get('reference')==p['rework_reference'] and scope.get('account_project')==MISSION_ACCOUNT
                and scope.get('data_policy')==DATA_POLICY and scope.get('new_youtube_calls')==0
                and scope.get('automatic_retry') is False and scope.get('instructions_hash')==digest(NOTICE),
                'rework_consent_scope')
        super()._check_contract(p,{k:v for k,v in b.items() if k!='rework_scope'})


class ReworkCompany(MissionOneCompany):
    store_type=ReworkStore

    def run(self,project_id,**kwargs):
        job=self.store.load(project_id)
        require(job['status']=='ready' and not job['sessions'] and not job['real_ai']['attempts'],'rework_restart_forbidden')
        return super().run(project_id,**kwargs)

    def _quality_transport_allowed(self,p):
        record=self.store.grant(p)
        require(hmac.compare_digest(record['body']['rework_scope']['credential_binding'],_binding(p['id'],self.config.api_key)),
                'rework_key_changed')
        return True

    def _tool_notice(self,p):
        return VideoProviderQualityCompany._tool_notice(self,p).replace('target_duration=60','target_duration=replan.duration_seconds')+NOTICE

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
            payload['contents'][0]['parts'][0]['text']=json.dumps(message,ensure_ascii=False)
        return payload

    def _validate_payload(self,payload):
        phase=parse(payload['contents'][0]['parts'][0]['text'])['phase']
        if phase in ('plan','review'):
            require(payload['generationConfig']['responseJsonSchema']==self._schema(phase),'rework_schema_changed')
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
            elif phase=='review':
                self._semantic=result.pop('goal_review')
                if result['action']=='accept':
                    content=self._review_content
                    require(all(v['met'] is True and v['evidence'].strip() and v['evidence'] in content
                                for v in self._semantic.values()),'rework_goal_not_met')
                    require(not re.search(r'골든타임|(?:쇼츠|영상)\s*(?:제작법|만드는\s*방법)|편집\s*노하우',content),
                            'rework_obvious_goal_drift')
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
        if phase=='review':self._review_content=json.dumps(parse(context['result']['content']),ensure_ascii=False)
        from script_quality import writer_contract,validate_writer_contract
        selection=p.get('rework_plan')
        contract=(writer_contract(p['quality_inputs']['target_segment'],selection['duration_seconds'],MODEL,selection['selected_topic'])
                  if selection and phase=='execute' and context['assignment']['role']=='writer' else None)
        if contract:context={**context,'quality':{**context['quality'],'writer_contract':contract}}
        self._research_review_state=None
        self._writer_wire_contract=contract;self._writer_wire_state=p if contract else None
        try:result=VideoProviderQualityCompany._call(self,p,provider,phase,task_id,context)
        finally:self._writer_wire_contract=None;self._writer_wire_state=None
        if contract:validate_writer_contract(parse(result['content']),contract)
        if phase=='plan' and 'tasks' in result:
            require([t['role'] for t in result['tasks']]==['writer','editor'],'rework_roles_required')
            p['rework_plan']=deepcopy(self._decision)
        if phase=='review':
            p.setdefault('goal_reviews',[]).append(dict(task_id=task_id,review=deepcopy(self._semantic)))
        return result

    def _delivery_blockers(self,p):
        p['final'].update(provider='system',source='accepted_review_handoff')
        return ['needs_user_review']


def prepare(workflow,pid,key,account):
    with workflow.store.lock(pid):
        project=workflow.store.load(pid);flow=project['representative']
        require(flow['stage']=='plan_revision','rework_stage')
        store=ReworkStore(workflow.store.root/'representative_rework')
        if flow.get('rework'):
            if flow['rework']['decision_hash']==digest(flow['decisions'][-1]):return
            require(flow['rework']['status']=='completed','rework_already_exists')
            flow.setdefault('rework_history',[]).append(deepcopy(flow['rework']))
        # Refuse an orphan left after a partially saved preparation instead of recreating it.
        for path in store.root.glob('qualityprovider-*.json'):
            if '.consent.' not in path.name:
                existing=store.load(path.stem)
                require(existing.get('rework_reference',{}).get('decision_hash')!=digest(flow['decisions'][-1]),'rework_orphan_exists')
        answers=snapshot(project)
        job=store.create(project['goal'],inputs=dict(domain='video',target_segment=flow['audience'],answers=answers,
            constraints=dict(aspect='9:16',language='한국어',platform='YouTube Shorts'),
            capabilities=dict(script_contract=SCRIPT_CONTRACT),experiences=[],feedback_text=flow['decisions'][-1]['feedback']),
            max_calls=None,max_revisions_per_task=1,max_total_revisions=1)
        prior=flow['plan_versions'][-1]
        job['rework_reference']=dict(project=pid,version=prior['version'],plan_hash=prior['sha256'],
            decision_hash=digest(flow['decisions'][-1]),input_hash=digest(answers))
        store.save(job)
        flow['rework']=dict(job=job['id'],status='pending',decision_hash=job['rework_reference']['decision_hash'])
        workflow.store.save(project)
        proposal=store.prepare(job['id'],key=key,account_project=account)
        flow['rework']['proposal']=proposal
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
            research=prior['research']),flow['plan_versions'])
        flow['plan_versions'].append(report);flow['rework']['status']='completed'
        workflow._transition(project,'awaiting_plan_approval')
