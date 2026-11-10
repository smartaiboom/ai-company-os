"""Exact-payload manager-plan acceptance. Reuses single-use consent and credential proof.

No production activation this milestone; tests mock HTTP and replace only this gate.
The independent quality-provider/global dialogue gates are never changed.
"""
from copy import deepcopy
import hashlib
import hmac
import os
from autonomous_company import require, digest, now, parse
from goal_dialogue_live import OneCallAcceptanceStore
from role_json_schema import matches

MANAGER_PLAN_EXECUTION_ENABLED = False


def canonical_bytes(value):
    import json
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


class ManagerPlanAcceptanceStore(OneCallAcceptanceStore):
    mode='manager_plan_acceptance_v1'
    marker_name='.manager-plan-acceptance-v1'
    acceptance_scope='manager_plan_only_20261110_v1'
    contract=None  # Domain supplies immutable fictional input, prompt and output schema.

    def __init__(self, root):
        from pathlib import Path
        require(not Path(root).is_symlink(),'invalid_acceptance_path')
        super().__init__(root)

    def _initialize(self):
        if self.root.exists():require(self.root.stat().st_mode & 0o077 == 0,'private_store_required')
        super()._initialize()

    @property
    def acceptance_goal(self):return self.contract['input']['goal']

    @property
    def acceptance_scope_hash(self):
        return digest(dict(scope=self.acceptance_scope,contract=self.contract,calls=1,
                           model=self._policy_model(),phase='plan'))

    @staticmethod
    def _policy_model():
        from autonomous_gemini35 import MODEL,ENDPOINT
        return dict(model=MODEL,endpoint=ENDPOINT)

    def create(self):
        require(isinstance(self.contract,dict),'domain_contract_required')
        return super().create(self.acceptance_goal)

    def _context(self,p):return deepcopy(self.contract['input'])

    def _payload(self,p):
        return dict(systemInstruction=dict(parts=[dict(text=self.contract['system'])]),
                    contents=[dict(role='user',parts=[dict(text=canonical_bytes(self._context(p)).decode())])],
                    generationConfig=dict(maxOutputTokens=4096,temperature=0.2,responseMimeType='application/json',
                                          responseJsonSchema=deepcopy(self.contract['schema'])))

    _wire_bytes=staticmethod(canonical_bytes)

    def _check_budget(self,p):
        require(p['goal']==self.acceptance_goal and type(p['max_rounds']) is int and p['max_rounds']==2
                and p['rounds']==0 and type(p['real_ai']['limit']) is int and p['real_ai']['limit']==1
                and p['limits']['max_calls']==1 and p['handoff'] is None
                and p['questions']==[] and p['answers']=={} and p['spec'] is None
                and p.get('user_notes',[])==[] and
                all(e['action'] in ('created','acceptance_key_compared_locally','manager_account_attested',
                                    'transmission_consent_approved','gemini_request_reserved',
                                    'gemini_request_unresolved','manager_plan_received') for e in p['history']),
                'manager_plan_scope_changed')

    def _policy(self,p):
        policy=super()._policy(p)
        policy.update(phase='plan',allowed_phases=['plan'],request_hash=digest(self._payload(p)),
                      staff_calls=0,review_calls=0,finalize_calls=0,feedback_calls=0,production_calls=0,
                      docs_and_quota_evidence_hash=digest(p['acceptance'].get('account_evidence')),
                      actual_execution_default='disabled',billing_and_quota_independently_verified=False)
        return policy

    def prepare_consent(self,project_id):
        result=super().prepare_consent(project_id)
        raw=self._wire_bytes(result['wire_payload'])
        path=self.path(project_id).with_suffix('.payload.json')
        require(not path.is_symlink(),'invalid_acceptance_path')
        if path.exists():require(path.read_bytes()==raw,'prepared_payload_changed')
        else:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        require(hashlib.sha256(raw).hexdigest()==result['body']['payload_hash'],'wire_hash_mismatch')
        return result

    def verify_project_key(self,project_id,*,api_key,project_api_key,project,free_tier_confirmed=False,
                           billing_disabled=False,quota_available=False,official_docs_reviewed=False):
        require(quota_available is True and official_docs_reviewed is True,'current_docs_and_quota_confirmation_required')
        # Parent requires local key comparison and signed Free/Billing evidence; never calls an API.
        super().verify_project_key(project_id,api_key=api_key,project_api_key=project_api_key,project=project,
                                   free_tier_confirmed=free_tier_confirmed,billing_disabled=billing_disabled)
        with self.lock(project_id):
            p=self.load(project_id)
            proof=dict(scope_hash=self.acceptance_scope_hash,project_id=project_id,
                       verification_hash=digest(p['acceptance']['verification']),quota_available=True,
                       official_docs_reviewed=True,method='owner_attestation_not_independent_verification',checked_at=now())
            p['acceptance']['account_evidence']=dict(record=proof,signature=self._sign(proof))
            return self._event(p,'manager_account_attested')

    def _verified_account(self,p,api_key=None):
        result=super()._verified_account(p,api_key)
        extra=p['acceptance'].get('account_evidence')
        require(isinstance(extra,dict) and set(extra)=={'record','signature'},'manager_account_evidence_required')
        proof=extra['record']
        require(hmac.compare_digest(str(extra['signature']),self._sign(proof)),'invalid_account_signature')
        require(proof.get('scope_hash')==self.acceptance_scope_hash and proof.get('project_id')==p['id']
                and proof.get('verification_hash')==digest(p['acceptance']['verification'])
                and proof.get('quota_available') is True and proof.get('official_docs_reviewed') is True,
                'manager_account_evidence_binding')
        return result

    def approve_consent(self,project_id,review_hash,*,api_key,**kwargs):
        self._verified_account(self.load(project_id),api_key)
        return super().approve_consent(project_id,review_hash,**kwargs)

    def _authorize_transport(self,p,api_key):
        require(MANAGER_PLAN_EXECUTION_ENABLED is True,'manager_plan_execution_disabled')
        super()._authorize_transport(p,api_key)

    def _accept_proposal(self,p,value,provider_name):
        require(matches(value,self.contract['schema']),'invalid_manager_plan_schema')
        self.validate_plan(value)
        p['manager_plan']=deepcopy(value)
        p['status']='needs_user_review'
        p['strategy_review']={k:dict(status='unassessed',evaluator='human_pending') for k in (
            'audience_fit','single_useful_message','hook_and_demo','source_feasibility',
            'role_handoff','honest_uncertainty','necessary_questions')}
        return self._event(p,'manager_plan_received',source='provider_model_claim')

    def validate_plan(self,value):
        raise NotImplementedError('Domain must validate its strategy and source claims')

    def answer(self,*args,**kwargs):raise ValueError('manager_plan_has_no_followup_permission')
    def revise(self,*args,**kwargs):raise ValueError('manager_plan_has_no_followup_permission')
    def confirm(self,*args,**kwargs):raise ValueError('manager_plan_has_no_followup_permission')
    def clarify(self,*args,**kwargs):raise ValueError('manager_plan_has_no_followup_permission')
