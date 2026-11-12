"""Dedicated real-provider preparation boundary. Production transport remains disabled.

Reuses signed Gemini35 consent, strict native wire schema and durable attempt ledger.
No mock store migration, new transport, credential loading or automatic retry.
"""
from copy import deepcopy
import json
from autonomous_company import require, exact, digest, parse
from autonomous_gemini35 import Gemini35Store, Gemini35Company
from quality_feedback import ROLE_CONTRACTS, EXPERIENCE_FIELDS
from goal_dialogue import safe_text

# Deliberately NOT an environment toggle. Tests replace this only with HTTP mocked.
QUALITY_TRANSPORT_ENABLED = False
INPUT_FIELDS = ('domain','target_segment','answers','constraints','capabilities','experiences','feedback_text')
EXPERIENCE_CONTEXT_FIELDS = ('id','domain','target_segment','issue','positive_preference',
                             'proposed_correction','verification','record_hash')
POLICY = dict(version=1, transport_default='disabled', automatic_retry=False,
              fields=list(INPUT_FIELDS), source='provider_model_claim',
              feedback_verification='hypothesis', media_evaluation='unassessed',
              required_account_evidence='separate current key/project/free-tier/billing verification')


def validate_inputs(value):
    exact(value, INPUT_FIELDS)
    for key in ('domain','target_segment'):safe_text(value[key],300)
    safe_text(value['feedback_text'],4000) if value['feedback_text'] else require(value['feedback_text']=='','invalid_feedback_text')
    for key in ('answers','constraints','capabilities'):
        require(isinstance(value[key],dict), 'invalid_quality_inputs')
    require(isinstance(value['experiences'],list) and len(value['experiences'])<=20,'invalid_experiences')
    for e in value['experiences']:
        exact(e,EXPERIENCE_CONTEXT_FIELDS)
        for item in e.values():safe_text(item,2000)
        require(e['domain']==value['domain'] and e['target_segment']==value['target_segment'],
                'experience_scope_mismatch')
        require(e['verification'] in ('hypothesis','verified'),'invalid_verification')
    # Reject NaN and duplicate JSON-like values using the existing strict parser.
    encoded=json.dumps(value,ensure_ascii=False)
    parse(encoded);safe_text(encoded,24000)
    # Only explicit planning inputs are accepted; store/grant/ledger records are not inputs.
    forbidden={'real_ai','consent','signature','api_key','password','storage_hash','attempts','local_path'}
    def inspect(item):
        if isinstance(item,dict):
            require(not forbidden.intersection(k.lower() for k in item),'private_quality_input')
            for child in item.values():inspect(child)
        elif isinstance(item,list):
            for child in item:inspect(child)
    inspect(value)
    return value


def experience_context(selection):
    """Drop original project records, paths, raw feedback and journal metadata from wire."""
    return [{k:deepcopy(e[k]) for k in EXPERIENCE_CONTEXT_FIELDS} for e in selection['selected']]


def validate_feedback_claim(value, inputs):
    """Validate a model extraction without accepting its claimed verification or scope."""
    exact(value,EXPERIENCE_FIELDS)
    for key in EXPERIENCE_FIELDS:
        if key!='confidence':safe_text(value[key],2000)
    require(type(value['confidence']) in (int,float) and 0<=value['confidence']<=1,'invalid_confidence')
    require(value['domain']==inputs['domain'] and value['target_segment']==inputs['target_segment'],
            'feedback_scope_mismatch')
    require(value['verification']=='hypothesis','model_cannot_verify_experience')
    require(value['evidence'] in inputs['feedback_text'] and bool(value['evidence'].strip()),
            'feedback_evidence_not_in_original')
    return deepcopy(value)


class QualityProviderStore(Gemini35Store):
    mode='quality_provider_gemini35_v1'
    marker_name='.quality-provider-gemini35-v1'
    policy='quality_provider_gemini35_v1'
    project_prefix='qualityprovider-'

    @staticmethod
    def _limits(limits):
        Gemini35Store._limits(limits)
        require(type(limits['max_calls']) is int and 1<=limits['max_calls']<=20,'bounded_quality_calls_required')

    def create(self, goal, *, inputs, max_calls=12, max_revisions_per_task=1, max_total_revisions=2):
        safe_text(goal,4000);validate_inputs(inputs)
        self._limits(dict(max_calls=max_calls,max_revisions_per_task=max_revisions_per_task,
                          max_total_revisions=max_total_revisions))
        p=super().create(goal,max_calls=max_calls,max_revisions_per_task=max_revisions_per_task,
                         max_total_revisions=max_total_revisions,internal_tool_review=False)
        p['quality_inputs']=deepcopy(inputs);p['feedback_proposals']=[]
        self.save(p);return deepcopy(p)

    def prepare(self, project_id, **kwargs):
        p=self.load(project_id);validate_inputs(p['quality_inputs'])
        body=super().prepare(project_id,**kwargs)
        body['quality_contract']=dict(policy=deepcopy(POLICY),inputs=deepcopy(p['quality_inputs']),
                                      inputs_hash=digest(p['quality_inputs']),prompt_hash=digest(ROLE_CONTRACTS))
        return body

    def _check_contract(self,p,body):
        require(isinstance(body,dict),'invalid_fields')
        expected=dict(policy=POLICY,inputs=p['quality_inputs'],inputs_hash=digest(p['quality_inputs']),
                      prompt_hash=digest(ROLE_CONTRACTS))
        require(digest(body.get('quality_contract'))==digest(expected),'quality_consent_binding')
        validate_inputs(p['quality_inputs'])
        super()._check_contract(p,{k:v for k,v in body.items() if k!='quality_contract'})

    def record_feedback(self, project_id, task_id, *, replaces=None):
        """Receive only validated provider-task content into this real-mode store, no inference."""
        with self.lock(project_id):
            p=self.load(project_id)
            task=next((t for t in p['assignments'] if t['id']==task_id),None)
            require(task is not None and task['role']=='feedback' and task['state']=='accepted_by_ai_manager',
                    'feedback_task_not_accepted')
            result=task['versions'][-1]
            require(result['source']=='provider_model_claim','provider_feedback_required')
            claim=validate_feedback_claim(parse(result['content']),p['quality_inputs'])
            require(claim['project']==project_id,'feedback_project_mismatch')
            refs=p['feedback_proposals']
            require(not any(e['result_hash']==digest(result) for e in refs),'duplicate_feedback_receipt')
            old=next((e for e in refs if e['id']==replaces),None)
            require(replaces is None or old and old['active'],'invalid_replacement')
            if old:old['active']=False
            record=dict(id='provider-experience-'+str(len(refs)+1),
                        original_text=p['quality_inputs']['feedback_text'],active=True,
                        version=old['version']+1 if old else 1,replaces=replaces,
                        result_hash=digest(result),**{**claim,'source':'provider_model_claim'})
            refs.append(record);self.save(p);return deepcopy(record)

    def withdraw_feedback(self,project_id,experience_id,reason):
        safe_text(reason)
        with self.lock(project_id):
            p=self.load(project_id)
            e=next((e for e in p['feedback_proposals'] if e['id']==experience_id),None)
            require(e is not None and e['active'],'experience_not_active')
            e.update(active=False,withdrawal_reason=reason);self.save(p)

    def select_feedback(self,project_id,*,domain,target_segment):
        from quality_feedback import select_experiences
        p=self.load(project_id)
        return {**select_experiences(p['feedback_proposals'],domain=domain,target_segment=target_segment),
                'journal_hash':p['storage_hash']}


class QualityProviderCompany(Gemini35Company):
    store_type=QualityProviderStore

    def _quality_transport_allowed(self, p):
        return QUALITY_TRANSPORT_ENABLED is True

    def _preflight(self,p):
        require(self._quality_transport_allowed(p),'quality_transport_disabled')
        return super()._preflight(p)

    def _additional_context_fields(self,phase):
        return {'quality','role_contracts','handoff_refs','version_history'}

    def _workflow_context(self,p):
        return dict(quality=deepcopy(p['quality_inputs']),role_contracts=deepcopy(ROLE_CONTRACTS),handoff_refs=[],version_history=[])

    def _tool_notice(self,p):
        return (' '+ROLE_CONTRACTS['manager']+' '+ROLE_CONTRACTS['employee']+' '+ROLE_CONTRACTS['feedback']+
                ' Roles and strategies are model decisions, not fixed questions or scripts. '
                'If clarification is essential, stop with the necessary question and reason. '
                'No media is attached: sensory scores must remain unassessed. '
                'A feedback task returns content as a JSON string with fields '+','.join(EXPERIENCE_FIELDS)+
                '. Project must be '+p['id']+'. Evidence must quote a substring of feedback_text; verification=hypothesis.')

    def _call(self,p,provider,phase,task_id,context):
        if 'previous_results' in context:
            context={**context,'handoff_refs':[dict(task_id=r['task_id'],revision=r['revision'],
                      result_hash=digest(r),source=r['source']) for r in context['previous_results']]}
        task=next((t for t in p['assignments'] if t['id']==task_id),None)
        context={**context,'version_history':deepcopy(task['versions']) if task else []}
        result=super()._call(p,provider,phase,task_id,context)
        if phase=='execute' and task and task['role']=='feedback':
            claim=validate_feedback_claim(parse(result['content']),p['quality_inputs'])
            require(claim['project']==p['id'],'feedback_project_mismatch')
        return result

    def _run(self,project_id,*,expected_state_hash,resume=False):
        # Inherited public run still owns the engine lock. Waiting work is never re-sent.
        with self.store.lock(project_id):
            p=self.store.load(project_id)
            require(p['storage_hash']==expected_state_hash,'stale_start_or_resume')
            if p['status'] in ('external_clip_pending','needs_user_review'):
                return self.store.result(project_id)
        return super()._run(project_id,expected_state_hash=expected_state_hash,resume=resume)

    def _delivery_blockers(self,p):
        return ['needs_user_review']
