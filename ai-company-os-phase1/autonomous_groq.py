"""Separate Groq free-account namespace, consent and key; shared company workflow."""
from copy import deepcopy
from dataclasses import dataclass,field
from datetime import datetime,timedelta
import hashlib
import json
import os
from autonomous_company import require,exact,digest,parse,now
from autonomous_free import FreeStore,FreeCompany,RULES
from autonomous_live import LiveManagerProvider,LiveEmployeeProvider
from groq_provider import MODEL,ENDPOINT,COST_POLICY,GroqFreeAdapter,require_adapter,numeric_rate_headers,provider_error_diagnostics
from role_json_schema import response_format,matches

GROQ_RULES={**RULES,'provider_cost_must_be_zero':False,'free_account_verification_required':True}
UNVERIFIED={'free_plan':False,'billing_disabled':False,'model_allowed':False,
            'verified_at':None,'credential_binding':None}


def key_binding(key):return hashlib.sha256(key.encode()).hexdigest()


class GroqStore(FreeStore):
    mode='autonomous_groq_free_v2'
    marker_name='.autonomous-groq-free-v2-store'
    policy='groq_free_v2'
    project_prefix='groqcompany-'
    provider_id='groq'
    model=MODEL
    endpoint=ENDPOINT
    rules=GROQ_RULES

    def prepare(self,project_id,*,valid_hours=24,confirm_free_account=False):
        body=super().prepare(project_id,valid_hours=valid_hours)
        account=deepcopy(UNVERIFIED)
        if confirm_free_account:
            key=os.getenv('GROQ_API_KEY','')
            GroqFreeAdapter().build_request(b'{}',key)  # Local key syntax only, no send.
            account={'free_plan':True,'billing_disabled':True,'model_allowed':True,
                     'verified_at':now(),'credential_binding':key_binding(key)}
        body.update(cost_policy=deepcopy(COST_POLICY),account_verification=account)
        return body

    def _check_contract(self,p,b):
        require(isinstance(b,dict),'invalid_fields')
        require(digest(b.get('cost_policy'))==digest(COST_POLICY),'groq_cost_policy')
        account=b.get('account_verification');exact(account,UNVERIFIED)
        require(all(account[k] is True for k in ('free_plan','billing_disabled','model_allowed')),
                'groq_free_account_unverified')
        try:
            checked=datetime.fromisoformat(account['verified_at']);elapsed=datetime.fromisoformat(now())-checked
            valid=checked.utcoffset()==timedelta(hours=9) and timedelta(0)<=elapsed<timedelta(hours=24)
        except (ValueError,TypeError):valid=False
        require(valid,'groq_account_verification_expired')
        key=os.getenv('GROQ_API_KEY','');GroqFreeAdapter().build_request(b'{}',key)
        require(account['credential_binding']==key_binding(key),'groq_account_key_changed')
        super()._check_contract(p,{k:v for k,v in b.items() if k not in ('cost_policy','account_verification')})

    def revoke(self,project_id,*,owner_confirmed=False):
        # Revocation must remain possible even after key/account attestation expiry.
        require(owner_confirmed is True,'explicit_owner_confirmation_required')
        from autonomous_company import fcntl
        import hmac
        path=self._grant_path(project_id);require(fcntl is not None,'cross_process_lock_unavailable')
        with path.with_suffix('.revoke.lock').open('a') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            self.load(project_id)
            require(path.is_file() and not path.is_symlink() and path.stat().st_size<16384,'invalid_operating_consent')
            grant=parse(path.read_text());exact(grant,('record','signature'));r=grant['record']
            require(hmac.compare_digest(str(grant['signature']),self._sign(r)),'invalid_consent_signature')
            require(r['body']['project_id']==project_id,'consent_binding')
            r['revoked_at']=now();self.atomic(path,{'record':r,'signature':self._sign(r)})
        return {'project_id':project_id,'revoked_at':r['revoked_at']}


@dataclass(frozen=True)
class GroqConfig:
    api_key:str=field(repr=False)
    model:str=MODEL
    endpoint:str=ENDPOINT
    @classmethod
    def from_env(cls):return cls(os.getenv('GROQ_API_KEY',''),os.getenv('GROQ_MODEL',''),os.getenv('GROQ_BASE_URL',''))


class GroqCompany(FreeCompany):
    store_type=GroqStore
    config_type=GroqConfig
    def _check_provider_config(self):
        require(os.getenv('GROQ_AUTONOMOUS_FREE_ENABLED')=='1','groq_execution_disabled')
        require(self.config.model==os.getenv('GROQ_MODEL')==MODEL
                and self.config.endpoint==os.getenv('GROQ_BASE_URL')==ENDPOINT,'groq_provider_binding')
        require(self.config.api_key==os.getenv('GROQ_API_KEY') and bool(self.config.api_key),'groq_key_binding')
    def _preflight(self,p):
        grant=super()._preflight(p)
        attempts=self._attempts(p)
        if attempts:
            limits=attempts[-1].get('rate_limits',{})
            require(limits.get('x-ratelimit-remaining-requests')!=0 and
                    limits.get('x-ratelimit-remaining-tokens')!=0,'provider_rate_limit')
        return grant
    def _attempt_identity(self):
        return {'provider_id':'groq','endpoint':ENDPOINT,'cost_policy_hash':digest(COST_POLICY)}
    def _attempt_policy_valid(self,a):
        return (a.get('model')==MODEL and a.get('free_account_policy_verified') is True
                and all(a.get(k)==v for k,v in self._attempt_identity().items()))
    def _adapter(self,model,base_url,api_key):return require_adapter(model,base_url)
    def _prepare_payload(self,payload):return GroqFreeAdapter().prepare_payload(payload)
    def _validate_payload(self,payload):GroqFreeAdapter().validate_payload(payload,self.current['phase'])
    def _output_token_limit(self,payload):return payload['max_completion_tokens']
    def _request_policy(self):return COST_POLICY
    def _response_policy_fields(self):return {'free_account_policy_verified':True,'cost_basis':'signed_free_account_attestation'}
    def _record_rate_headers(self,entry,headers):entry['rate_limits']=numeric_rate_headers(headers)
    def _record_provider_error(self,entry,*,exception=None,envelope=None,http_status=None):
        diagnostics=provider_error_diagnostics(exception=exception,envelope=envelope,http_status=http_status)
        if diagnostics is not None:entry['provider_error_diagnostics']=diagnostics
    def _operation_identity(self,task_id):
        return {**super()._operation_identity(task_id),**self._attempt_identity(),'model':MODEL}
    def _verify_response_policy(self,p,envelope):
        self.store.grant(p)  # Recheck expiry, revoke and signed free-account assertion.
        usage=envelope.get('usage')
        if isinstance(usage,dict) and 'cost' in usage:
            require(type(usage['cost']) in (int,float) and usage['cost']==0,'groq_unexpected_cost')
        # Missing cost is NOT evidence of zero: a different, signed account policy applies.
    def _before_transport(self,p):
        super()._before_transport(p);self._check_provider_config()
    def _parse_role_content(self,raw,phase):
        value=parse(raw)
        require(matches(value,response_format(phase)['json_schema']['schema']),'invalid_role_schema')
        return value['result']
