"""Deterministic budget proposals and local signed user approvals; no AI transport."""
import hashlib
import hmac
import json
import os
import threading
from pathlib import Path
import uuid
from datetime import datetime, timezone, timedelta

DEFAULT_PROJECT_CALL_BUDGET = 20
MAX_PROJECT_CALL_BUDGET = 200
MAX_ADDITIONAL_CALLS = 50
KEY_PATH = Path(__file__).resolve().parent / 'data/.budget-approvals/local.key'
_KEY_LOCK = threading.Lock()


def now():
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def signature(value, create=False):
    with _KEY_LOCK:
        return _signature(value, create)


def _signature(value, create):
    if create:
        KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(KEY_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'wb') as f:
                f.write(os.urandom(32));f.flush();os.fsync(f.fileno())
    try:
        key = KEY_PATH.read_bytes()
    except OSError:
        raise ValueError('로컬 예산 승인 서명 키가 없습니다.') from None
    return hmac.new(key, json.dumps(value, sort_keys=True, ensure_ascii=False,
                                   separators=(',', ':')).encode(), hashlib.sha256).hexdigest()


def identity(project):
    return {'project_id': project['id'], 'goal_hash': digest(project.get('manager_goal') or project.get('goal'))}


def limit(project):
    state = project.get('real_ai', {})
    value = state.get('limit', DEFAULT_PROJECT_CALL_BUDGET)
    if type(value) is not int or not 1 <= value <= MAX_PROJECT_CALL_BUDGET:
        raise ValueError('프로젝트 호출 한도가 올바르지 않습니다.')
    if value > DEFAULT_PROJECT_CALL_BUDGET:
        proof = state.get('budget_authorization', {})
        body = proof.get('body', {})
        expected = {**identity(project), 'limit': value, 'request_id': body.get('request_id')}
        if (body != expected or not isinstance(body.get('request_id'), str) or not body['request_id']
                or not hmac.compare_digest(str(proof.get('signature', '')), signature(body))):
            raise ValueError('사용자 승인 없는 추가 예산입니다.')
    return value


def summary(project):
    attempts = project.get('real_ai', {}).get('attempts', [])
    if not isinstance(attempts, list):
        raise ValueError('예산 사용 기록이 올바르지 않습니다.')
    cap = limit(project)
    return {'limit': cap, 'used': len(attempts), 'reserved': sum(a.get('status') == 'reserved' for a in attempts),
            'remaining': max(0, cap-len(attempts))}


def binding(project):
    return {**identity(project), 'budget_hash': digest(project.get('real_ai', {})),
            'plan_hash': digest(project.get('plan')), 'tasks_hash': digest(project.get('tasks', []))}


def request_more(project, additional, reason, usage_plan):
    current = summary(project)
    if type(additional) is not int or not 1 <= additional <= MAX_ADDITIONAL_CALLS or current['limit']+additional > MAX_PROJECT_CALL_BUDGET:
        raise ValueError('추가 횟수는 1~50회, 프로젝트 전체 한도는 최대 200회입니다.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError('추가 예산 사유가 필요합니다.')
    if not isinstance(usage_plan, list) or not 1 <= len(usage_plan) <= 20:
        raise ValueError('예상 사용 계획을 1~20개로 제시해 주세요.')
    for item in usage_plan:
        if (not isinstance(item, dict) or set(item) != {'purpose', 'calls'}
                or not isinstance(item['purpose'], str) or not item['purpose'].strip() or len(item['purpose']) > 500
                or type(item['calls']) is not int or not 1 <= item['calls'] <= MAX_PROJECT_CALL_BUDGET):
            raise ValueError('예상 사용 계획 항목이 올바르지 않습니다.')
    requested_binding = binding(project)
    requests = project.setdefault('budget_requests', [])
    if any(r['status']=='pending' for r in requests):
        raise ValueError('미결 예산 요청이 있습니다. 기존 요청을 먼저 확인해 주세요.')
    if len(requests) >= 50:
        raise ValueError('예산 요청 기록 상한에 도달했습니다.')
    body = {'id':uuid.uuid4().hex, **identity(project), 'snapshot':current,
            'additional':additional, 'reason':reason, 'usage_plan':usage_plan,
            'created_at':now(), 'binding':requested_binding}
    request = {'body':body, 'signature':signature(body,create=True), 'status':'pending'}
    requests.append(request)
    project.setdefault('history', []).append({'at':now(),'event':'budget_extension_requested',
        'details':'추가 예산 사용자 결정 대기 — 외부 호출·자동 증액 없음','request_id':body['id']})
    return request


def decide(project, request_id, expected_hash, response, user_confirmed, reason):
    if user_confirmed is not True or response not in ('approve','reject') or not isinstance(reason,str) or not reason.strip() or len(reason)>1000:
        raise ValueError('실제 사용자 결정 확인과 승인·거절 근거가 필요합니다.')
    request = next((r for r in project.get('budget_requests',[]) if r['body']['id']==request_id), None)
    if request is None or request['status']!='pending' or digest(request)!=expected_hash:
        raise ValueError('예산 요청이 없거나 이미 결정되었거나 변경되었습니다.')
    body = request['body']
    if ((response=='approve' and body['binding']!=binding(project)) or {k:body[k] for k in identity(project)}!=identity(project)
            or not hmac.compare_digest(str(request['signature']),signature(body))):
        raise ValueError('오래되었거나 변조된 예산 요청입니다.')
    before = limit(project)
    if response=='approve':
        after=before+body['additional']
        if after>MAX_PROJECT_CALL_BUDGET:
            raise ValueError('프로젝트 예산 상한을 초과했습니다.')
        proof={**identity(project),'limit':after,'request_id':request_id}
        project.setdefault('real_ai',{})['limit']=after
        project['real_ai']['budget_authorization']={'body':proof,'signature':signature(proof)}
    else:
        after=before
    request.update(status='approved' if response=='approve' else 'rejected',decided_at=now(),
                   decided_by='사용자',decision_reason=reason,before_limit=before,after_limit=after)
    project.setdefault('history',[]).append({'at':now(),'event':'budget_user_decision',
        'request_id':request_id,'response':response,'before_limit':before,'after_limit':after,
        'details':'예산만 결정 — 실행·외부 전송 허가 없음'})


def ensure_shortage_request(project, usage_plan):
    if (not isinstance(usage_plan, list) or not 1 <= len(usage_plan) <= 20
            or any(not isinstance(i,dict) or set(i)!={'purpose','calls'}
                   or not isinstance(i['purpose'],str) or not i['purpose'].strip() or len(i['purpose'])>500
                   or type(i['calls']) is not int or not 1<=i['calls']<=MAX_PROJECT_CALL_BUDGET for i in usage_plan)):
        raise ValueError('예상 사용 계획이 올바르지 않습니다.')
    required=sum(i['calls'] for i in usage_plan)
    current=summary(project)
    if required<=current['remaining']:
        return None
    for request in project.get('budget_requests',[]):
        if request['status']=='pending':
            return request
    additional=required-current['remaining']
    return request_more(project,additional,'예상 업무 호출 수가 남은 예산보다 많습니다.',usage_plan)
