"""Groq-specific wire format. No retries, mutable provider registry or billing APIs."""
from copy import deepcopy
import json
import re
from urllib.request import Request
from ai_provider_adapter import ProviderSpec, response_metadata
from autonomous_company import require, exact, digest
from role_json_schema import response_format

MODEL='openai/gpt-oss-20b'
ENDPOINT='https://api.groq.com/openai/v1'
COST_POLICY={'basis':'owner_verified_free_account','billing_enabled':False,
             'paid_fallback':False,'response_cost_required':False,'max_cost':0}


class GroqFreeAdapter:
    spec=ProviderSpec('groq_free',MODEL,'chat_completions',ENDPOINT,'bearer',4096,
                      'verified_free_account_only',enabled=False)
    def build_request(self,body,api_key):
        require(isinstance(api_key,str) and bool(api_key.strip()) and len(api_key)<=4096
                and '\r' not in api_key and '\n' not in api_key,'missing_groq_key')
        return Request(ENDPOINT+'/chat/completions',data=body,method='POST',
                       headers={'Content-Type':'application/json','Authorization':'Bearer '+api_key})
    def response_metadata(self,response):return response_metadata(response)
    def prepare_payload(self,payload):
        payload=deepcopy(payload);message=json.loads(payload['messages'][1]['content']);phase=message['phase']
        message['output_contract']={'result':message['output_contract']}
        payload['messages'][1]['content']=json.dumps(message,ensure_ascii=False)
        payload['messages'][0]['content']+=(' Return a JSON object with one field result matching the strict response schema. '
            'Keep values concise within 4096 output tokens. No markdown or separate reasoning text. '
            'A halt decision is also wrapped in result.')
        payload['max_completion_tokens']=payload.pop('max_tokens')
        return {**payload,'reasoning_effort':'low','response_format':response_format(phase)}
    def validate_payload(self,payload,phase):
        exact(payload,('model','messages','max_completion_tokens','reasoning_effort','response_format'))
        require(payload['model']==MODEL and type(payload['max_completion_tokens']) is int
                and 1<=payload['max_completion_tokens']<=4096 and payload['reasoning_effort']=='low'
                and digest(payload['response_format'])==digest(response_format(phase)),'groq_payload_policy')


def require_adapter(model,endpoint):
    require(model==MODEL and endpoint==ENDPOINT,'groq_provider_binding')
    return GroqFreeAdapter()


def numeric_rate_headers(headers):
    result={}
    for name in ('retry-after','x-ratelimit-limit-requests','x-ratelimit-limit-tokens',
                 'x-ratelimit-remaining-requests','x-ratelimit-remaining-tokens'):
        value=headers.get(name)
        if isinstance(value,str) and re.fullmatch(r'[0-9]{1,10}',value):
            result[name]=min(int(value),1000000000 if name!='retry-after' else 86400)
    return result
