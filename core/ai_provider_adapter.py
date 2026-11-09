"""Wire-format boundary only. Metadata never grants permission to send requests."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from urllib.request import Request

FREE_PROVIDER_ID = 'openrouter_free'
FREE_MODEL = 'openrouter/free'
FREE_BASE_URL = 'https://openrouter.ai/api/v1'
LIVE_PROVIDER_IDS = (FREE_PROVIDER_ID,)


@dataclass(frozen=True)
class ProviderSpec:
    identifier: str
    model: str
    api_format: str
    base_url: str
    authentication: str
    max_output_tokens: int
    cost_policy: str
    requires_project_approval: bool = True
    enabled: bool = False


class FinishClass(str, Enum):
    STOP = 'stop'
    LENGTH = 'length'
    CONTENT_FILTER = 'content_filter'
    ERROR = 'error'
    UNKNOWN = 'unknown'


class FailureClass(str, Enum):
    TIMEOUT = 'timeout'
    TRANSPORT = 'transport'


def classify_finish_reason(value):
    # Never return unknown provider text, including arbitrary strings or objects.
    return FinishClass(value) if isinstance(value, str) and value in ('stop','length','content_filter','error') else FinishClass.UNKNOWN


def classify_transport_error(error):
    return FailureClass.TIMEOUT if isinstance(error, TimeoutError) else FailureClass.TRANSPORT


@dataclass(frozen=True)
class ResponseMetadata:
    structure_valid: bool
    finish: FinishClass
    content_chars: int | None


def response_metadata(response):
    """Bounded metadata only; no response text, model name, arbitrary fields or logs."""
    try:
        choice = response['choices'][0]
        reason = choice['finish_reason']
        content = choice['message']['content']
    except (KeyError, IndexError, TypeError):
        return ResponseMetadata(False, FinishClass.UNKNOWN, None)
    return ResponseMetadata(True, classify_finish_reason(reason), min(len(content),262144) if isinstance(content,str) else None)


class ProviderAdapter(Protocol):
    @property
    def spec(self) -> ProviderSpec: ...

    def build_request(self, body: bytes, api_key: str) -> Request: ...

    def response_metadata(self, response: object) -> ResponseMetadata: ...


class OpenRouterFreeAdapter:
    """No transport, retry, budget, permission or credential storage in the adapter."""
    spec = ProviderSpec(FREE_PROVIDER_ID, FREE_MODEL, 'chat_completions', FREE_BASE_URL,
                        'bearer', 4096, 'free_only', enabled=True)

    def build_request(self, body, api_key):
        if not isinstance(api_key,str) or not api_key.strip():
            raise ValueError('실제 AI 요청에는 인증키가 필요합니다.')
        return Request(FREE_BASE_URL + '/chat/completions', data=body,
                       headers={'Content-Type':'application/json', 'Authorization':f'Bearer {api_key}'}, method='POST')

    def response_metadata(self, response):
        return response_metadata(response)


def require_live_adapter(*, model, base_url, api_key, provider_id=FREE_PROVIDER_ID):
    # Deliberately no mutable registry/config lookup. Future specs stay declarations.
    if provider_id != FREE_PROVIDER_ID or model != FREE_MODEL or not isinstance(base_url,str) or base_url.rstrip('/') != FREE_BASE_URL:
        raise ValueError('미설정 또는 비활성 AI 공급자·모델·주소입니다. 현재 무료 OpenRouter만 허용합니다.')
    if not isinstance(api_key,str) or not api_key.strip():
        raise ValueError('실제 AI 요청에는 인증키가 필요합니다.')
    return OpenRouterFreeAdapter()


def bounded_response_diagnostics(envelope):
    """Untrusted provider text, IDs, headers and content never enter diagnostics."""
    result={'envelope_object':isinstance(envelope,dict),'finish':'missing',
            'choice_count':None,'content_present':False,'content_chars':None,
            'refusal_present':False,'tool_request_present':False,
            'json_parse':'not_attempted','cost':'unverified',
            'tokens':{k:None for k in ('prompt_tokens','completion_tokens','total_tokens')}}
    if not isinstance(envelope,dict):return result
    usage=envelope.get('usage')
    if isinstance(usage,dict):
        for key in result['tokens']:
            value=usage.get(key)
            if type(value) is int and 0<=value<=1000000000:result['tokens'][key]=value
        cost=usage.get('cost')
        if type(cost) in (int,float):
            if cost==0:result['cost']='zero'
            elif cost>0:result['cost']='nonzero'
    choices=envelope.get('choices')
    if not isinstance(choices,list):return result
    result['choice_count']=min(len(choices),2)
    if len(choices)!=1 or not isinstance(choices[0],dict):return result
    choice=choices[0]
    if 'finish_reason' in choice:
        finish=choice['finish_reason']
        result['finish']=finish if isinstance(finish,str) and finish in (
            'stop','length','tool_calls','function_call','content_filter','error') else 'unknown'
    message=choice.get('message')
    if isinstance(message,dict):
        content=message.get('content')
        result['content_present']=isinstance(content,str) and bool(content)
        result['content_chars']=min(len(content),262144) if isinstance(content,str) else None
        result['refusal_present']=bool(message.get('refusal'))
        result['tool_request_present']=bool(message.get('tool_calls') or message.get('function_call'))
    return result
