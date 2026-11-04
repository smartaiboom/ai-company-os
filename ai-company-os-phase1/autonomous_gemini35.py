"""Fixed 3.5 binding and isolated store; never upgrades a 3.1 grant or attempt."""
from dataclasses import dataclass
import os
from autonomous_gemini import GeminiStore,GeminiCompany,GeminiConfig
from autonomous_company import CompanyError,require,parse,digest
from copy import deepcopy
from gemini_provider import GeminiFreeAdapter,COST_POLICY as OLD_COST_POLICY
from ai_provider_adapter import ProviderSpec

MODEL='gemini-3.5-flash-lite'
ENDPOINT='https://generativelanguage.googleapis.com/v1beta/models/'+MODEL+':generateContent'
COST_POLICY={**OLD_COST_POLICY,'pricing_source':'https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite'}
NESTED_POLICY={'version':1,'scope':'generated_employee_results_and_manager_reviews',
               'intent':'root_tool_selector; valid_json_examples_without_root_tool_are_data',
               'ambiguous_json':'manager_review','invalid_tool_schema':'manager_review',
               'automatic_json_repair':False,'transport_retry':False}


class Gemini35Adapter(GeminiFreeAdapter):
    spec=ProviderSpec('gemini35_free',MODEL,'generate_content',ENDPOINT,'x-goog-api-key',4096,
                      'verified_free_tier_only',enabled=False)


class Gemini35Store(GeminiStore):
    mode='autonomous_gemini35_free_v2'
    marker_name='.autonomous-gemini35-free-v2-store'
    policy='gemini35_free_v2'
    project_prefix='gemini35company-'
    model=MODEL
    endpoint=ENDPOINT
    cost_policy=COST_POLICY

    def create(self,goal,*,internal_tool_review=True,**kwargs):
        p=super().create(goal,internal_tool_review=internal_tool_review,**kwargs)
        if internal_tool_review:p['nested_tool_review']=1;self.save(p)
        return p

    def valid_mode(self,p):
        return super().valid_mode(p) and ('nested_tool_review' not in p or
                type(p['nested_tool_review']) is int and p['nested_tool_review']==1 and p.get('tool_failure_review')==1)

    def prepare(self,project_id,**kwargs):
        body=super().prepare(project_id,**kwargs)
        if self.load(project_id).get('nested_tool_review')==1:body['nested_tool_review']=deepcopy(NESTED_POLICY)
        return body

    def _check_contract(self,p,b):
        require(isinstance(b,dict),'invalid_fields')
        if p.get('nested_tool_review')==1:
            require(digest(b.get('nested_tool_review'))==digest(NESTED_POLICY),'nested_tool_consent_required')
        else:require('nested_tool_review' not in b,'nested_tool_policy_mismatch')
        super()._check_contract(p,{k:v for k,v in b.items() if k!='nested_tool_review'})


@dataclass(frozen=True)
class Gemini35Config(GeminiConfig):
    model:str=MODEL
    endpoint:str=ENDPOINT
    @classmethod
    def from_env(cls):
        return cls(os.getenv('GEMINI_API_KEY',''),os.getenv('GEMINI35_MODEL',''),os.getenv('GEMINI35_ENDPOINT',''))


class Gemini35Company(GeminiCompany):
    store_type=Gemini35Store
    config_type=Gemini35Config
    bound_model=MODEL
    bound_endpoint=ENDPOINT
    cost_policy=COST_POLICY
    adapter_type=Gemini35Adapter
    model_env='GEMINI35_MODEL'
    endpoint_env='GEMINI35_ENDPOINT'
    enabled_env='GEMINI35_AUTONOMOUS_FREE_ENABLED'

    def _tool_notice(self,p):
        notice=super()._tool_notice(p)
        if p.get('nested_tool_review')==1:
            notice+=(' Tool execution intent is a JSON object with a root tool selector. '
                     'For examples use prose or a valid JSON object under example without a root tool field. '
                     'Tool content must be valid JSON with exactly tool,width,height,audio,scenes; '
                     'do not use markdown fences for executable tool input. Ambiguous or invalid tool input is failed review material, '
                     'not a successful artifact. Manager decides corrective feedback; application never repairs JSON.')
        return notice

    def _tool_spec(self,p,content):
        if p.get('nested_tool_review')!=1:return super()._tool_spec(p,content)
        if content.startswith('```') and '"tool"' in content:raise CompanyError('tool_input_ambiguous')
        if not content.startswith(('{','[')):return None
        try:spec=parse(content)
        except CompanyError:raise CompanyError('tool_input_invalid_json') from None
        if not isinstance(spec,dict) or 'tool' not in spec:
            require(not isinstance(spec,list) or not any(isinstance(v,dict) and 'tool' in v for v in spec),
                    'tool_input_ambiguous')
            require(not isinstance(spec,dict) or not ('scenes' in spec and any(k in spec for k in ('width','height','audio'))),
                    'tool_input_ambiguous')
            return None
        require(isinstance(spec['tool'],str) and spec['tool'] in p['local_tools'],'tool_not_allowed')
        from local_artifacts import _validate_video
        try:_validate_video(spec,False)  # Shape/bounds only; existing renderer owns reflow.
        except CompanyError:raise CompanyError('tool_input_invalid_schema') from None
        return spec

    def _nested_tool_error(self,p,code):
        if p.get('nested_tool_review')==1 and code in ('tool_input_invalid_json','tool_input_invalid_schema','tool_input_ambiguous'):
            return {'stage':'tool_input_parse' if code=='tool_input_invalid_json' else 'tool_input_validation',
                    'category':code,'exit_code':None}
        return None
