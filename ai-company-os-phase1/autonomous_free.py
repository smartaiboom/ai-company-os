"""Versioned, isolated free autonomous policy. Legacy budgets are never overridden.

No paid mode, transport injection API, retries, rotating accounts, or hidden resume.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
import re
import threading
import time
import uuid
from urllib.error import HTTPError

import ai_provider_adapter
import ai_safety
from autonomous_company import CompanyError, require, text, exact, digest, now, parse, validate_review
from autonomous_live import (LiveStore, LiveCompany, LiveConfig,
                              LiveManagerProvider, LiveEmployeeProvider, SCOPES)

MODE='autonomous_live_free_v2'
NOTICE='앱의 총/시작당 비용성 호출 상한 없음. 공급자 무료 조건·쿼터·속도 제한 준수. 자동 재시도 없음.'
ZERO_PRICE={'max_price':{'prompt':0,'completion':0},'allow_fallbacks':False}
RULES={'automatic_retry':False,'ambiguous_stop':True,'failed_counted':True,
       'business_approval_required':False,'tools_available':False,
       'max_tasks':8,'max_criteria':8,'max_run_seconds':1800,
       'min_interval_seconds':2,'duplicate_operation_stop':True,'quality_stagnation_stop':True,
       'provider_limits_obeyed':True,'provider_cost_must_be_zero':True}


def pacing_now():
    # Preserve fractional seconds so a two-second pace never rounds down to one.
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


class FreeStore(LiveStore):
    mode=MODE
    marker_name='.autonomous-free-v2-store'

    def valid_mode(self,p):
        return (p.get('mode')==MODE and p.get('simulation') is False
                and p.get('policy_version')==2 and isinstance(p.get('real_ai'),dict)
                and p['real_ai'].get('policy')=='free_autonomous_v2'
                and 'limit' not in p['real_ai'] and 'attempts' not in p)

    def load(self, project_id):
        marker=self.root/self.marker_name
        require(marker.is_file() and marker.read_text()==MODE,'invalid_store')
        path=self.path(project_id);require(path.stat().st_size<=4194304,'state_too_large')
        try:
            p=json.loads(path.read_text(),object_pairs_hook=ai_safety.unique_response_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError,RecursionError):raise CompanyError('invalid_project_state') from None
        require(isinstance(p,dict),'invalid_project_state')
        require(p.get('storage_hash')==digest({k:v for k,v in p.items() if k!='storage_hash'}),'state_changed')
        require(self.valid_mode(p) and p.get('schema_version')==1 and p.get('id')==project_id,'mode_mismatch')
        self._limits(p['limits'])
        return p

    @staticmethod
    def _limits(limits):
        exact(limits,('max_calls','max_revisions_per_task','max_total_revisions'))
        cap=limits['max_calls']
        require(cap is None or type(cap) is int and cap>=1,'invalid_optional_cap')
        require(type(limits['max_revisions_per_task']) is int and 0<=limits['max_revisions_per_task']<=2
                and type(limits['max_total_revisions']) is int and 0<=limits['max_total_revisions']<=4,'invalid_revision_limit')

    def create(self, goal, *, max_calls=None, max_revisions_per_task=1, max_total_revisions=2, local_tools=None):
        text(goal,4000)
        limits={'max_calls':max_calls,'max_revisions_per_task':max_revisions_per_task,
                'max_total_revisions':max_total_revisions}
        self._limits(limits);self._initialize()
        p={'id':'freecompany-'+uuid.uuid4().hex,'schema_version':1,'policy_version':2,
           'mode':MODE,'simulation':False,'goal':goal,'created_at':now(),'status':'ready',
           'phase':'plan','plan':None,'assignments':[],'limits':limits,
           'real_ai':{'enabled':False,'policy':'free_autonomous_v2','attempts':[],'consent':{}},
           'events':[],'providers':None,'active_operation':None,'final':None,'artifacts':{},
           'user_business_approval_requests':0,'sessions':[],'run_started_at':None,'next_request_at':None}
        if local_tools is not None:
            from local_artifacts import TOOLS
            require(local_tools==list(TOOLS),'tool_not_allowed')
            p['local_tools']=deepcopy(local_tools)
        self.save(p);return deepcopy(p)

    def prepare(self, project_id, *, valid_hours=24):
        p=self.load(project_id)
        require(type(valid_hours) is int and 1<=valid_hours<=168,'invalid_validity')
        body={'policy':'free_autonomous_v2','project_id':p['id'],
                'goal_hash':ai_safety.goal_hash(p['goal']),'initial_state_hash':p['storage_hash'],
                'scopes':SCOPES[:],'provider':'openrouter','model':ai_safety.MODEL,
                'endpoint':ai_safety.BASE_URL,'max_cost':0,'free_only':True,
                'limits':deepcopy(p['limits']),'call_policy':{'total':None,'per_run':None,
                    'optional_technical_cap':p['limits']['max_calls']},
                'notice':NOTICE,
                'issued_at':now(),'expires_at':(datetime.fromisoformat(now())+timedelta(hours=valid_hours)).isoformat(),
                'rules':deepcopy(RULES)}
        if p.get('local_tools'):
            from local_artifacts import TOOLS
            body['local_tools']={k:deepcopy(TOOLS[k]) for k in p['local_tools']}
        return body

    def _check_contract(self,p,b):
        require(isinstance(b,dict),'invalid_fields')
        if p.get('local_tools'):
            from local_artifacts import TOOLS
            require(b.get('local_tools')=={k:TOOLS[k] for k in p['local_tools']},'consent_tools')
        else:require('local_tools' not in b,'consent_tools')
        checked={k:v for k,v in b.items() if k!='local_tools'}
        exact(checked,('policy','project_id','goal_hash','initial_state_hash','scopes','provider','model',
                 'endpoint','max_cost','free_only','limits','call_policy','notice','issued_at','expires_at','rules'))
        require(self.valid_mode(p) and b['policy']=='free_autonomous_v2','consent_policy')
        require(b['project_id']==p['id'] and b['goal_hash']==ai_safety.goal_hash(p['goal']),'consent_binding')
        require(b['scopes']==SCOPES and b['provider']=='openrouter' and b['model']==ai_safety.MODEL
                and b['endpoint']==ai_safety.BASE_URL,'consent_scope')
        self._limits(p['limits']);self._limits(b['limits'])
        require(b['limits']==p['limits'] and b['call_policy']=={'total':None,'per_run':None,
                'optional_technical_cap':p['limits']['max_calls']},'consent_limits')
        require(type(b['max_cost']) is int and b['max_cost']==0 and b['free_only'] is True,'free_cost_only')
        require(b['rules']==RULES,'consent_rules');require(b['notice']==NOTICE,'consent_notice')
        # JSON equality alone considers True == 1; compare canonical hashes as well.
        require(digest(b['rules'])==digest(RULES),'consent_rules')
        try:
            issued=datetime.fromisoformat(b['issued_at']);expires=datetime.fromisoformat(b['expires_at'])
            valid=(issued.utcoffset()==timedelta(hours=9) and expires.utcoffset()==timedelta(hours=9)
                   and issued<=datetime.fromisoformat(now())<expires
                   and timedelta(0)<expires-issued<=timedelta(days=7))
        except (ValueError,TypeError):valid=False
        require(valid,'consent_expired')


class FreeCompany(LiveCompany):
    """A single execution owns the finite workflow, with no per-run call budget."""
    def __init__(self,store,manager,employee,config):
        require(type(store) is FreeStore and type(manager) is LiveManagerProvider
                and type(employee) is LiveEmployeeProvider and type(config) is LiveConfig,'free_types_required')
        self.store,self.manager,self.employee,self.config=store,manager,employee,config
        self.session=None;self.used=0;self.current=None;self._execution_lock=threading.Lock()
        self._run_monotonic=None

    def _tool_notice(self,p):
        if not p.get('local_tools'):return ''
        from local_artifacts import TOOLS
        return (' Local artifact capability (no shell, network, file access or uploads): '+
                json.dumps({k:TOOLS[k] for k in p['local_tools']})+
                ' To render, employee execute.content must be a JSON STRING matching the tool input schema. '
                'Other tasks use prose. Put line breaks in captions to fit. System renders before manager review; '
                'LOCAL_TOOL_RECEIPT in evidence is measured metadata, not visual/semantic verification. '
                'Manager must arrange video production and review against goal. Set audio=true for local Korean TTS of captions; false for silent video. '
                'No MP4 means delivery is blocked. Tool permission is separate from model transmission consent.')

    def _preflight(self,p):
        grant=self.store.grant(p)
        require(os.getenv('AI_AUTONOMOUS_FREE_ENABLED')=='1'
                and os.getenv('AI_ENGINE')=='openai_compatible','free_execution_disabled')
        require(self.config.model==ai_safety.MODEL and os.getenv('AI_MODEL')==ai_safety.MODEL,'free_model_only')
        require(self.config.endpoint==ai_safety.BASE_URL and os.getenv('AI_BASE_URL')==ai_safety.BASE_URL,'fixed_endpoint_only')
        key=self.config.api_key
        require(isinstance(key,str) and bool(key.strip()) and len(key)<=4096
                and '\r' not in key and '\n' not in key,'missing_api_key')
        require(key not in json.dumps(p,ensure_ascii=False),'secret_in_state')
        state=p['real_ai'];consent=state['consent']
        require(state['enabled'] is True and consent.get('approved') is True
                and consent.get('approved_at')==grant['approved_at']
                and consent.get('goal_hash')==ai_safety.goal_hash(p['goal'])
                and consent.get('data_scope')=='goal_task_inputs_predecessors_feedback','consent_binding')
        attempts=state['attempts']
        require(isinstance(attempts,list) and all(isinstance(a,dict) and a.get('status')=='completed'
                and isinstance(a.get('id'),str) and type(a.get('input_bytes')) is int
                and 0<=a['input_bytes']<=ai_safety.MAX_INPUT_BYTES
                and a.get('role_result_status')=='validated' and a.get('cost_verified_zero') is True
                and a.get('model')==ai_safety.MODEL for a in attempts),'uncertain_operation')
        require(len({a['id'] for a in attempts})==len(attempts),'duplicate_attempt')
        cap=p['limits']['max_calls']
        require(cap is None or len(attempts)<cap,'optional_technical_cap_reached')
        if self._run_monotonic is not None:
            require(time.monotonic()-self._run_monotonic<RULES['max_run_seconds'],'run_deadline_reached')
        if p['run_started_at']:
            try:elapsed=(datetime.fromisoformat(now())-datetime.fromisoformat(p['run_started_at'])).total_seconds()
            except (ValueError,TypeError):raise CompanyError('invalid_run_deadline') from None
            require(0<=elapsed<RULES['max_run_seconds'],'run_deadline_reached')
        return grant

    def _check_session(self,grant):
        require(grant['body']['call_policy']['per_run'] is None,'consent_limits')

    def _run(self,project_id,*,expected_state_hash,resume=False):
        with self.store.lock(project_id):
            p=self.store.load(project_id)
            require(p['storage_hash']==expected_state_hash,'stale_start_or_resume')
            if p['status'] in ('delivered','stopped','needs_operational_permission'):return self.store.result(project_id)
            # 'continue' is for a clean crash checkpoint, never for quota/failed attempts.
            require((p['status']=='ready' and resume is False) or (p['status']=='running' and resume is True),
                    'explicit_checkpoint_continue_required')
            self._run_monotonic=None
            self._preflight(p);require(not p['active_operation'],'uncertain_operation')
            self.session=uuid.uuid4().hex;self.used=0
            p['run_started_at']=p['run_started_at'] or now()
            p['sessions'].append({'id':self.session,'at':now(),'resume':resume,'starting_hash':expected_state_hash})
            self.store.save(p)
            self._run_monotonic=time.monotonic()
            result=self._run_workflow(project_id)
            if result.get('reason_code') in ('provider_rate_limit','provider_quota_or_billing','provider_unavailable'):
                result['status']='paused'
                result['events'].append({'at':now(),'event':'provider_paused','code':result['reason_code'],
                                         'automatic_retry':False})
                self.store.save(result)
            return self.store.result(project_id)

    def _prepare_payload(self,payload):
        payload=deepcopy(payload)
        payload['messages'][0]['content']+=(' Keep JSON concise and within the 4096 output-token limit. '
            'No markdown fences or separate reasoning text. Use only necessary tasks and concise field values; '
            'do not omit required fields or checks. JSON support is not assumed; malformed output will stop execution.')
        return {**payload,'provider':deepcopy(ZERO_PRICE)}

    def _before_transport(self,p):
        # Persist pacing across process restarts; cancellation/expiry checked while waiting.
        wait_started=time.monotonic()
        while p['next_request_at']:
            require(time.monotonic()-wait_started<=RULES['min_interval_seconds']+1,'clock_or_throttle_stalled')
            self.store.grant(p)
            remaining=(datetime.fromisoformat(p['next_request_at'])-datetime.fromisoformat(pacing_now())).total_seconds()
            if remaining<=0:break
            require(remaining<=RULES['min_interval_seconds'],'clock_changed')
            time.sleep(min(remaining,0.25))
        self.store.grant(p)
        if p['run_started_at']:
            require(0<=(datetime.fromisoformat(now())-datetime.fromisoformat(p['run_started_at'])).total_seconds()
                    <RULES['max_run_seconds'],'run_deadline_reached')
        require(self._run_monotonic is not None and time.monotonic()-self._run_monotonic<RULES['max_run_seconds'],
                'run_deadline_reached')
        p['next_request_at']=(datetime.fromisoformat(pacing_now())+timedelta(seconds=RULES['min_interval_seconds'])).isoformat()
        self.store.save(p)

    def _request_json(self,p,*,model,base_url,body,api_key,timeout,transport,kind,task_id,goal):
        """Separate free policy, same fixed adapter and authoritative durable ledger.

        Never opens legacy request scopes or mutates project_budget policy.
        """
        self._preflight(p)
        adapter=ai_provider_adapter.require_live_adapter(model=model,base_url=base_url,api_key=api_key)
        require(isinstance(body,bytes) and len(body)<=ai_safety.MAX_INPUT_BYTES,'input_too_large')
        payload=parse(body.decode())
        require(payload.get('model')==ai_safety.MODEL and payload.get('provider')==ZERO_PRICE
                and type(payload.get('max_tokens')) is int and 1<=payload['max_tokens']<=4096,'free_payload_required')
        attempts=self._attempts(p)
        operation_hash=digest({'phase':self.current['phase'],'task_id':task_id,'context_hash':self.current['context_hash']})
        require(not p['active_operation'] and not any(a.get('operation_hash')==operation_hash for a in attempts),
                'duplicate_operation')
        entry={'id':uuid.uuid4().hex,'kind':kind,'task_id':task_id,'model':model,'status':'reserved',
               'reserved_at':now(),'input_bytes':len(body),'max_tokens':payload['max_tokens'],
               'operation_hash':operation_hash,'request_hash':digest(payload),'price_policy_hash':digest(ZERO_PRICE)}
        attempts.append(entry);self._persist(p)  # Durable reservation, sole ledger, before any send.
        request=adapter.build_request(body,api_key)
        try:
            with transport(request,timeout=min(90,max(1,int(timeout)))) as response:
                raw=response.read(ai_safety.MAX_RESPONSE_BYTES+1)
            entry['response_received_at']=now()
            entry['response_diagnostics']={'envelope_json':'not_parsed','response_bytes':min(len(raw),ai_safety.MAX_RESPONSE_BYTES+1)}
            self.store.save(p)
            require(len(raw)<=ai_safety.MAX_RESPONSE_BYTES,'response_too_large')
            envelope=json.loads(raw.decode(),object_pairs_hook=ai_safety.unique_response_object,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            entry['response_diagnostics'].update(ai_provider_adapter.bounded_response_diagnostics(envelope),envelope_json='parsed')
            self.store.save(p)
            require(isinstance(envelope,dict),'invalid_response_envelope')
            if 'error' in envelope:
                code=envelope['error'].get('code') if isinstance(envelope['error'],dict) else None
                raise CompanyError(self._provider_code(code))
            cost=envelope.get('usage',{}).get('cost') if isinstance(envelope.get('usage'),dict) else None
            require(type(cost) in (int,float) and cost==0,'provider_cost_unverified_or_nonzero')
        except Exception as exc:
            if isinstance(exc,(ValueError,UnicodeError,RecursionError)) and not isinstance(exc,CompanyError) and entry.get('response_diagnostics',{}).get('envelope_json')=='not_parsed':
                entry['response_diagnostics']['envelope_json']='invalid'
            code=exc.code if isinstance(exc,CompanyError) else 'free_request_failed'
            if isinstance(exc,HTTPError):
                code=self._provider_code(exc.code)
                retry=exc.headers.get('Retry-After') if exc.headers else None
                if isinstance(retry,str) and retry.isdigit():entry['retry_after_seconds']=min(86400,int(retry[:6]))
                exc.close()
            entry.update(status='failed',finished_at=now(),error_code=code)
            self._persist(p)
            raise CompanyError(code) from None
        entry.update(status='completed',finished_at=now(),cost_verified_zero=True)
        self._persist(p)
        return envelope

    def _record_response_validation(self,p,outcome):
        entry=self._attempts(p)[-1]
        diagnostics=entry.get('response_diagnostics')
        if diagnostics is None:return
        allowed=('json_parsed','invalid_model_json','invalid_choices','incomplete_response',
                 'unexpected_tools','secret_in_response','invalid_response_envelope','provider_refusal')
        diagnostics['validation']=outcome if outcome in allowed else 'rejected'
        if outcome=='json_parsed':diagnostics['json_parse']='parsed'
        elif outcome=='invalid_model_json':diagnostics['json_parse']='invalid'
        self.store.save(p)

    @staticmethod
    def _provider_code(code):
        if code==429:return 'provider_rate_limit'
        if code==402:return 'provider_quota_or_billing'
        if code in (502,503,504):return 'provider_unavailable'
        return 'provider_rejected'

    def _call(self,p,provider,phase,task_id,context):
        require(context.get('goal')==p['goal'] and context.get('mode')==p['mode']
                and context.get('limits')==p['limits'],'context_binding')
        result=super()._call(p,provider,phase,task_id,context)
        task=next((t for t in p['assignments'] if t['id']==task_id),None)
        normalize=lambda value:re.sub(r'\s+',' ',value).strip() if isinstance(value,str) else value
        if phase=='execute' and task:
            exact(result,('content','evidence','uncertainty'))
            for value in result.values():text(value)
            require(not any(normalize(result['content'])==normalize(v['content']) for v in task['versions']),
                    'repeated_employee_result')
        if phase=='execute' and p.get('local_tools'):
            # Plain prose is valid for research/script tasks; a tool request must be JSON.
            content=result['content'].strip()
            if content.startswith('{'):
                spec=parse(content)
                if isinstance(spec,dict) and 'tool' in spec:
                    from local_artifacts import execute
                    require(spec['tool'] in p['local_tools'],'tool_not_allowed')
                    self.store.grant(p)
                    folder=self.store.root/'artifacts'/p['id']/('tool-'+self.current['context_hash'])
                    folder.mkdir(parents=True,exist_ok=True)
                    require(folder.resolve().is_relative_to(self.store.root/'artifacts') and not folder.is_symlink(),'invalid_tool_directory')
                    p['events'].append({'at':now(),'event':'local_tool_reserved','input_hash':digest(spec),'task_id':task_id})
                    self.store.save(p)
                    receipt=execute(spec['tool'],spec,folder)
                    receipt['input_hash']=digest(spec)
                    name='video-'+self.current['context_hash']+'.mp4'
                    p['artifacts'][name]={'path':str((folder/'video.mp4').relative_to(self.store.root)), 'sha256':receipt['sha256']}
                    result['evidence']+='\nLOCAL_TOOL_RECEIPT '+json.dumps(receipt,ensure_ascii=False)
                    p['events'].append({'at':now(),'event':'local_tool_completed','task_id':task_id,'receipt':receipt})
                    self.store.save(p)
        if phase=='finalize' and result.get('action')=='deliver' and p.get('local_tools'):
            require(any(name.endswith('.mp4') for name in p['artifacts']),'required_artifact_missing')
            accepted=[]
            for t in p['assignments']:
                if t['state']=='accepted_by_ai_manager' and t['versions'][-1]['content'].strip().startswith('{'):
                    spec=parse(t['versions'][-1]['content'])
                    if isinstance(spec,dict) and spec.get('tool') in p['local_tools']:
                        accepted.append((t['id'],digest(spec)))
            require(any(e['event']=='local_tool_completed' and
                        (e['task_id'],e['receipt']['input_hash']) in accepted
                        for e in p['events']),'accepted_artifact_missing')
            self.store.result(p['id'])
        if phase=='review' and isinstance(result,dict) and result.get('action')=='revise' and task and task['reviews']:
            validate_review(result,task['criteria_ids'])
            previous=task['reviews'][-1]
            fingerprint=lambda r: {'action':r['action'],'feedback':normalize(r['feedback']),
                'checks':sorted((c['criterion_id'],c['status']) for c in r['checks'])}
            require(fingerprint(previous)!=fingerprint(result),'quality_stagnation')
        return result
