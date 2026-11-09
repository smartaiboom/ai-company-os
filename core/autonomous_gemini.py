"""Isolated Gemini policy; reuses the existing autonomous company state machine."""
from dataclasses import dataclass,field
from datetime import datetime,timedelta
from copy import deepcopy
import json
import os
from urllib.error import HTTPError
from autonomous_company import require,exact,digest,now,parse
from autonomous_free import FreeStore,FreeCompany,RULES
from gemini_provider import GeminiFreeAdapter,MODEL,ENDPOINT,COST_POLICY
from gemini_connection_once import error_category
from groq_provider import numeric_rate_headers
from role_json_schema import response_format,matches

GEMINI_RULES={**RULES,'provider_cost_must_be_zero':False,'free_account_verification_required':True}
TOOL_REVIEW_POLICY={'version':1,'scope':'generated_employee_results_and_manager_reviews',
                   'recoverable':['caption_overflow','narration_exceeds_scene','classified_local_subprocess_failure'],
                   'manager_decides':True,'failed_tool_accept_forbidden':True,'transport_retry':False,
                   'revision_limits':'existing_task_and_total_limits'}


class GeminiStore(FreeStore):
    mode='autonomous_gemini_free_v2'
    marker_name='.autonomous-gemini-free-v2-store'
    policy='gemini_free_v2'
    project_prefix='geminicompany-'
    provider_id='gemini'
    model=MODEL
    endpoint=ENDPOINT
    rules=GEMINI_RULES
    cost_policy=COST_POLICY

    def valid_mode(self,p):
        return super().valid_mode(p) and ('tool_failure_review' not in p or
                type(p['tool_failure_review']) is int and p['tool_failure_review']==1)

    def create(self,goal,*,internal_tool_review=True,**kwargs):
        require(type(internal_tool_review) is bool,'invalid_tool_review_policy')
        p=super().create(goal,**kwargs)
        if internal_tool_review:
            p['tool_failure_review']=1;self.save(p)
        return p

    def prepare(self,project_id,*,valid_hours=24,confirm_free_account=False):
        body=super().prepare(project_id,valid_hours=valid_hours)
        if self.load(project_id).get('tool_failure_review')==1:
            body['tool_failure_review']=deepcopy(TOOL_REVIEW_POLICY)
        body.update(cost_policy=deepcopy(self.cost_policy),account_verification={
            'free_tier':confirm_free_account is True,
            'verified_at':now() if confirm_free_account else None})
        return body

    def _check_contract(self,p,b):
        require(isinstance(b,dict) and digest(b.get('cost_policy'))==digest(self.cost_policy),'gemini_cost_policy')
        account=b.get('account_verification');exact(account,('free_tier','verified_at'))
        require(account['free_tier'] is True,'gemini_free_account_unverified')
        try:
            checked=datetime.fromisoformat(account['verified_at']);elapsed=datetime.fromisoformat(now())-checked
            valid=checked.utcoffset()==timedelta(hours=9) and timedelta(0)<=elapsed<timedelta(hours=24)
        except (ValueError,TypeError):valid=False
        require(valid,'gemini_account_verification_expired')
        if p.get('tool_failure_review')==1:
            require(digest(b.get('tool_failure_review'))==digest(TOOL_REVIEW_POLICY),'tool_review_consent_required')
        else:require('tool_failure_review' not in b,'tool_review_policy_mismatch')
        super()._check_contract(p,{k:v for k,v in b.items() if k not in ('cost_policy','account_verification','tool_failure_review')})


@dataclass(frozen=True)
class GeminiConfig:
    api_key:str=field(repr=False)
    model:str=MODEL
    endpoint:str=ENDPOINT
    @classmethod
    def from_env(cls):
        return cls(os.getenv('GEMINI_API_KEY',''),os.getenv('GEMINI_MODEL',''),os.getenv('GEMINI_ENDPOINT',''))


class GeminiCompany(FreeCompany):
    store_type=GeminiStore
    config_type=GeminiConfig
    bound_model=MODEL
    bound_endpoint=ENDPOINT
    cost_policy=COST_POLICY
    adapter_type=GeminiFreeAdapter
    model_env='GEMINI_MODEL'
    endpoint_env='GEMINI_ENDPOINT'
    enabled_env='GEMINI_AUTONOMOUS_FREE_ENABLED'

    def _can_review_tool_failure(self,p):
        return p.get('tool_failure_review')==1

    def _tool_notice(self,p):
        notice=super()._tool_notice(p)
        if p.get('tool_failure_review')==1:
            notice+=(' A result with tool_status=failed is a failed employee attempt retained for review, not an artifact. '
                     'tool_failure contains application-measured fixed stage/category/exit_code only. '
                     'Manager must decide revise with specific corrective feedback, stop, or needs_operational_permission. '
                     'Accepting a failed tool attempt is physically invalid. Do not claim MP4 success from failed evidence. '
                     'A revision uses the existing revision limits; no automatic network replay is available.')
        return notice

    def _check_provider_config(self):
        require(os.getenv(self.enabled_env)=='1','gemini_execution_disabled')
        require(self.config.model==os.getenv(self.model_env)==self.bound_model
                and self.config.endpoint==os.getenv(self.endpoint_env)==self.bound_endpoint,'gemini_provider_binding')
        require(self.config.api_key==os.getenv('GEMINI_API_KEY') and bool(self.config.api_key),'gemini_key_binding')

    def _adapter(self,model,base_url,api_key):
        require(model==self.bound_model and base_url==self.bound_endpoint,'gemini_provider_binding')
        return self.adapter_type()
    def _preflight(self,p):
        grant=super()._preflight(p)
        attempts=self._attempts(p)
        if attempts:
            limits=attempts[-1].get('rate_limits',{})
            require(limits.get('x-ratelimit-remaining-requests')!=0
                    and limits.get('x-ratelimit-remaining-tokens')!=0,'provider_rate_limit')
        return grant
    def _prepare_payload(self,payload):return self.adapter_type().prepare_payload(payload)
    def _validate_payload(self,payload):self.adapter_type().validate_payload(payload,self.current['phase'])
    def _output_token_limit(self,payload):return payload['generationConfig']['maxOutputTokens']
    def _request_policy(self):return self.cost_policy
    def _attempt_identity(self):return {'provider_id':'gemini','endpoint':self.bound_endpoint,'cost_policy_hash':digest(self.cost_policy)}
    def _operation_identity(self,task_id):return {**super()._operation_identity(task_id),**self._attempt_identity(),'model':self.bound_model}
    def _attempt_policy_valid(self,a):
        return a.get('model')==self.bound_model and a.get('free_account_policy_verified') is True and all(
            a.get(k)==v for k,v in self._attempt_identity().items())
    def _response_policy_fields(self):return {'free_account_policy_verified':True,'cost_basis':'signed_free_tier_attestation'}
    def _normalize_envelope(self,envelope):return self.adapter_type().normalize(envelope)
    def _verify_response_policy(self,p,envelope):self.store.grant(p)
    def _parse_role_content(self,raw,phase):
        value=parse(raw);require(matches(value,response_format(phase)['json_schema']['schema']),'invalid_role_schema')
        return value['result']
    def _before_transport(self,p):
        super()._before_transport(p);self._check_provider_config()
    def _record_rate_headers(self,entry,headers,http_status=None):
        entry['rate_limits']=numeric_rate_headers(headers)
        entry['http_status']=http_status if type(http_status) is int and 100<=http_status<=599 else None
        if http_status is not None and 200<=http_status<=299:
            require(http_status==200,'gemini_unexpected_http_status')
    def _record_provider_error(self,entry,*,exception=None,envelope=None,http_status=None):
        if exception is not None:
            # Envelope/schema errors are local validation; no arbitrary exception text.
            stage=('json_parse' if isinstance(exception,(json.JSONDecodeError,UnicodeError)) else
                   'response_validate' if entry.get('response_received_at') else
                   'response_read' if entry.get('http_status')==200 else 'transport_open')
            entry['provider_error_diagnostics']={'category':error_category(exception,stage),'stage':stage}
        if isinstance(exception,HTTPError):entry['http_status']=exception.code
