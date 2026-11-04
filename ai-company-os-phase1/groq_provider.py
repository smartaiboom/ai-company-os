"""Groq-specific wire format. No retries, mutable provider registry or billing APIs."""
from copy import deepcopy
import json
import re
from urllib.request import Request
from urllib.error import HTTPError,URLError
from ai_provider_adapter import ProviderSpec, response_metadata
from autonomous_company import require, exact, digest, parse
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


# Exact, finite diagnostic vocabulary, never message/param/failed_generation text.
# A matching code is a provider claim, not proof of a particular root cause.
ERROR_CODES={
    'invalid_api_key':'authentication',
    'model_not_found':'model_or_resource_not_found',
    'model_permission_blocked':'permission',
    'invalid_json_schema':'invalid_json_schema',
    'json_validate_failed':'json_schema_validation',
    'unsupported_parameter':'unsupported_parameter',
    'context_length_exceeded':'token_limit',
    'rate_limit_exceeded':'rate_limit',
}


def provider_error_diagnostics(*,exception=None,envelope=None,http_status=None):
    """Read at most 8193 bytes to extract one allowlisted code; retain no body.

    Reading/parsing failures must not replace the original failure or enable retry.
    Only HTTP/transport failures and explicit error envelopes produce diagnostics.
    """
    status=None;error=None;category='provider_error'
    if isinstance(exception,HTTPError):
        value=exception.code
        status=value if type(value) is int and 100<=value<=599 else None
        category={400:'invalid_request',401:'authentication',402:'quota_or_billing',
                  403:'permission',404:'model_or_resource_not_found',413:'request_too_large',
                  422:'request_validation',429:'rate_limit'}.get(status,'http_error')
        if status is not None and status>=500:category='server_error'
        try:
            raw=exception.read(8193)
            if isinstance(raw,bytes) and len(raw)<=8192:
                body=parse(raw.decode('utf-8'))
                if isinstance(body,dict):error=body.get('error')
        except Exception:pass
    elif envelope is not None:
        status=http_status if type(http_status) is int and 100<=http_status<=599 else None
        if isinstance(envelope,dict):error=envelope.get('error')
    elif isinstance(exception,(TimeoutError,URLError,ConnectionError,OSError)):
        reason=exception.reason if isinstance(exception,URLError) else exception
        category='timeout' if isinstance(reason,TimeoutError) else 'connection_error'
    else:return None
    code=error.get('code') if isinstance(error,dict) else None
    code=code if isinstance(code,str) and code in ERROR_CODES else 'other'
    # Status is authoritative for auth/quota/server failures. Refine only ambiguous
    # request failures or a 200 error envelope, not contradictory provider claims.
    if (envelope is not None or status in (400,422)) and code in ERROR_CODES:category=ERROR_CODES[code]
    return {'http_status':status,'category':category,'provider_code':code}
