"""One specifically authorized synthetic POST. No project execution or retries."""
from contextlib import contextmanager
from datetime import datetime,timedelta
import hashlib
import json
import os
from pathlib import Path
import signal
from urllib.error import HTTPError

from ai_safety import guarded_urlopen
from ai_provider_adapter import bounded_response_diagnostics
from autonomous_company import CompanyError,Store,digest,now,parse,require
from autonomous_groq import key_binding
from groq_provider import MODEL,ENDPOINT,COST_POLICY,GroqFreeAdapter,numeric_rate_headers,provider_error_diagnostics,response_source_hints
from role_json_schema import obj,enum,matches

# This authorization belongs to this Codespace/repository, not a configurable store.
REPO=Path('/workspaces/ai-company-os/ai-company-os-phase1')
ROOT=REPO/'data/synthetic-groq-compat-once-20261104'
AUTH_DOC=REPO/'codex_tasks/v01_groq_one_post_synthetic_compat_approved_20261104.md'
AUTH_DOC_SHA='7d93b11dd7d79c53fe1df9ea7bf28b1d491f8cca49643898911626383981f8f0'
ACCOUNT_PROPOSAL=Path('/tmp/groq-account-reviewed-proposal-20261104.json')
ACCOUNT_SHA='e77a83d47b73176faad55fdfee563c357407fef3bcbd8046c11a73d8da9c305a'
REQUEST_SHA='5886294a7a7e81271ebca9f67f25118cec3468b866b3c0eb5463f391a2c9367a'
EXPIRES='2026-11-05T11:35:43+09:00'
TIMEOUT=60
OPERATION={'authorization_document_sha256':AUTH_DOC_SHA,'request_sha256':REQUEST_SHA,
           'provider':'groq','model':MODEL,'endpoint':ENDPOINT+'/chat/completions',
           'expires_at':EXPIRES,'max_posts':1,'max_completion_tokens':512,'timeout_seconds':TIMEOUT,
           'cost_policy':COST_POLICY}


def payload():
    schema=obj(result={'anyOf':[obj(status=enum('ready')),obj(status=enum('stop'),reason={'type':'string'})]})
    return {'model':MODEL,'messages':[
        {'role':'system','content':'Return only JSON matching the supplied schema.'},
        {'role':'user','content':'Return result.status ready. This is a synthetic API compatibility check.'}],
        'max_completion_tokens':512,'reasoning_effort':'low',
        'response_format':{'type':'json_schema','json_schema':{'name':'groq_compat_v1','strict':True,'schema':schema}}}


def canonical_bytes(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


def preflight():
    require(hashlib.sha256(AUTH_DOC.read_bytes()).hexdigest()==AUTH_DOC_SHA,'authorization_document_changed')
    body=canonical_bytes(payload())
    require(hashlib.sha256(body).hexdigest()==REQUEST_SHA,'request_changed')
    account=parse(ACCOUNT_PROPOSAL.read_text())
    require(digest(account)==ACCOUNT_SHA,'account_evidence_changed')
    require(account['provider']=='groq' and account['model']==MODEL and account['endpoint']==ENDPOINT
            and account['cost_policy']==COST_POLICY,'account_policy_mismatch')
    evidence=account['account_verification']
    require(all(evidence.get(k) is True for k in ('free_plan','billing_disabled','model_allowed')),'account_unverified')
    current=datetime.fromisoformat(now());checked=datetime.fromisoformat(evidence['verified_at'])
    require(current.utcoffset()==checked.utcoffset()==timedelta(hours=9)
            and timedelta(0)<=current-checked<timedelta(hours=24)
            and current<datetime.fromisoformat(EXPIRES),'authorization_expired')
    key=os.environ.get('GROQ_API_KEY','')
    request=GroqFreeAdapter().build_request(body,key)
    require(evidence['credential_binding']==key_binding(key),'account_key_changed')
    require(os.getenv('GROQ_MODEL',MODEL)==MODEL and os.getenv('GROQ_BASE_URL',ENDPOINT)==ENDPOINT,'provider_mismatch')
    require(request.full_url==OPERATION['endpoint'] and request.get_method()=='POST'
            and request.data==body and TIMEOUT==60 and payload()['max_completion_tokens']==512,'request_changed')
    require(hasattr(signal,'setitimer'),'wall_timeout_unavailable')
    return request,key


def _sync_directory():
    fd=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def reserve(record):
    require(not ROOT.is_symlink() and not ROOT.parent.is_symlink(),'invalid_diagnostic_path')
    ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
    try:fd=os.open(ROOT/'operation.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    except FileExistsError:raise CompanyError('operation_already_consumed') from None
    with os.fdopen(fd,'w') as file:
        json.dump(record,file,ensure_ascii=False);file.flush();os.fsync(file.fileno())
    _sync_directory()  # Crash from here onward never refunds this single attempt.


def persist(record):
    Store.atomic(ROOT/'operation.json',record)


@contextmanager
def wall_timeout():
    require(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'wall_timeout_in_use')
    def expired(signum,frame):raise TimeoutError()
    previous=signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,TIMEOUT)
    try:yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)


def inspect_response(record,envelope,key):
    require(isinstance(envelope,dict),'invalid_response_envelope')
    if 'error' in envelope:
        record['provider_error_diagnostics']=provider_error_diagnostics(envelope=envelope,http_status=record['http_status'])
        raise CompanyError('provider_error_envelope')
    diagnostics=bounded_response_diagnostics(envelope)
    record['response_diagnostics']=diagnostics
    require(record['http_status']==200,'unexpected_http_status')
    usage=envelope.get('usage')
    if isinstance(usage,dict) and 'cost' in usage:
        cost=usage['cost']
        require(type(cost) in (int,float) and cost==0,'unexpected_cost')
    require(diagnostics['finish']=='stop','incomplete_response')
    choices=envelope.get('choices')
    require(isinstance(choices,list) and len(choices)==1,'invalid_choices')
    message=choices[0].get('message')
    require(isinstance(message,dict) and message.get('role')=='assistant','invalid_message')
    require(not message.get('refusal') and not message.get('tool_calls') and not message.get('function_call'),'response_refused')
    content=message.get('content')
    require(isinstance(content,str) and key not in content,'invalid_or_secret_content')
    value=parse(content)
    record['strict_schema_valid']=matches(value,payload()['response_format']['json_schema']['schema'])
    require(record['strict_schema_valid'],'invalid_strict_schema')
    tokens=diagnostics['tokens']['completion_tokens']
    require(tokens is None or tokens<=512,'reported_token_limit_exceeded')
    record['result_status']=value['result']['status']  # Only ready/stop, never reason/content.
    require(record['result_status']=='ready','model_stopped')


def run_once():
    request,key=preflight()
    record={'operation_fingerprint':digest(OPERATION),'operation':OPERATION,'reserved_at':now(),
            'state':'reserved','post_attempts':0,'http_status':None,'strict_schema_valid':None,
            'result_status':None,'free_account_basis':'owner_attestation_bound_to_credential',
            'response_cost_verified_zero':False}
    reserve(record)
    # Recheck clock/account/key/authorization after reservation and just before send.
    request,key=preflight()
    record.update(state='transport_started',transport_started_at=now(),post_attempts=1)
    persist(record)
    try:
        with wall_timeout():
            try:
                with guarded_urlopen(request,timeout=TIMEOUT) as response:
                    status=getattr(response,'status',None)
                    record['http_status']=status if type(status) is int and 100<=status<=599 else None
                    record['rate_limits']=numeric_rate_headers(response.headers)
                    record['response_source_hints']=response_source_hints(response.headers,record['http_status'])
                    raw=response.read(131073)
                record['response_received_at']=now();record['state']='received';persist(record)
                require(len(raw)<=131072,'response_too_large')
                require(key.encode() not in raw,'secret_in_response')
                envelope=parse(raw.decode('utf-8'))
                inspect_response(record,envelope,key)
                record['response_cost_verified_zero']=record['response_diagnostics']['cost']=='zero'
                record['state']='succeeded'
            except HTTPError as exc:
                try:
                    record['provider_error_diagnostics']=provider_error_diagnostics(exception=exc)
                    record['http_status']=record['provider_error_diagnostics']['http_status']
                    record['rate_limits']=numeric_rate_headers(exc.headers or {})
                    record['response_source_hints']=response_source_hints(exc.headers or {},record['http_status'])
                    record['response_received_at']=now()
                finally:exc.close()
                record.update(state='failed',reason_code='http_rejected')
    except CompanyError as exc:
        record.update(state='failed',reason_code=exc.code)
    except Exception as exc:
        diagnostics=provider_error_diagnostics(exception=exc)
        if diagnostics is not None:record['provider_error_diagnostics']=diagnostics
        record.update(state='uncertain',reason_code='transport_or_response_failure')
    record['finished_at']=now();persist(record)
    return record


def main():
    try:
        record=run_once()
        print(json.dumps(record,ensure_ascii=False,indent=2))
        return 0 if record['state']=='succeeded' else 1
    except (CompanyError,OSError,ValueError,KeyError):
        # No traceback/provider exception text, and no overwrite of consumed record.
        print('합성 진단이 차단되었습니다. 승인·계정·키 결합·유효기간·기존 선예약을 확인하세요. 재송신하지 않습니다.')
        return 1


if __name__=='__main__':raise SystemExit(main())
