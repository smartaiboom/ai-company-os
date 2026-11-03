"""Explicit owner-only approval and one employee call; no HTTP/startup hooks."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import app
import ai_safety
import execution_engine
import manager_decision as md

USER_APPROVAL = ('프로젝트 cb44b605b498의 실제 AI 관리자 proceed 제안은 승인합니다. '
                 'TASK-002 실제 AI 직원 호출 최대 1회는 승인. 승인된 경우 기존 예산과 보안 원칙을 지키고 '
                 'TASK-003 이후는 실행하지 않도록 Codex 작업 지시서를 GitHub에 작성해 줘.')


def preconditions(project_id, expected_hash):
    p = app.load_project(project_id)
    if md.digest(p) != expected_hash:
        raise ValueError('최신 프로젝트 지문이 필요합니다.')
    attempts = p.get('real_ai', {}).get('attempts', [])
    view = app.manager_decision_view(project_id)
    if (len(attempts) != 5 or any(a.get('status') != 'completed' for a in attempts)
            or attempts[-1].get('kind') != 'manager_decision' or attempts[-1].get('task_id') != 'TASK-001'
            or any(h.get('event') == 'task002_once_authorized' for h in p.get('history', []))
            or len(view) != 1 or view[0]['status'] != 'pending_user_decision' or view[0]['stale']
            or view[0]['provider'] != 'real_openrouter_free' or view[0]['decision']['action'] != 'proceed'
            or 'TASK-002' not in view[0]['decision']['payload']['next_task_ids']
            or any(t.get('status') != '대기' or t.get('result') for t in p['tasks'][1:])):
        raise ValueError('단일 직원 호출 사전조건 불일치 또는 이미 사용된 승인입니다.')
    ai_safety.check_project_permission(p)
    if (os.getenv('AI_MODEL') != ai_safety.MODEL or os.getenv('AI_API_BASE_URL', '').rstrip('/') != ai_safety.BASE_URL
            or not os.getenv('AI_API_KEY')):
        raise ValueError('무료 모델·고정 주소·키 조건을 확인해 주세요.')
    return p, view[0]


def run_once(project_id, expected_hash, *, authorization_id, guard_path, user_confirmed=False):
    if user_confirmed is not True or not isinstance(authorization_id, str) or not re.fullmatch('[a-f0-9]{32}', authorization_id):
        raise ValueError('직접 사용자 승인과 고유 승인 ID가 필요합니다.')
    p, view = preconditions(project_id, expected_hash)
    guard = Path(guard_path)
    fd = os.open(guard, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump({'authorization_id': authorization_id, 'project_id': project_id, 'task_id': 'TASK-002', 'at': app.now(), 'max_calls': 1}, f)
        f.flush()
        os.fsync(f.fileno())
    observation = {'authorization_id': authorization_id, 'started_at': app.now(), 'transport_calls': 0, 'finished': False}
    observation_path = guard.with_suffix('.observation.json')

    def observe():
        temp = observation_path.with_suffix('.tmp')
        with temp.open('w') as f:
            json.dump(observation, f)
            f.flush()
            os.fsync(f.fileno())
        temp.replace(observation_path)

    observe()
    original_transport = execution_engine.urlopen
    try:
        # Uses the actual persisted proposal ID and hash, never supplied guessed values.
        app.respond_manager_decision(project_id, view['id'], view['expected_hash'], 'approve')
        with app.manager_decision_transaction(project_id) as approved:
            proposal = approved['manager_decisions']['proposals'][0]
            expected = deepcopy(p)
            expected_proposal = expected['manager_decisions']['proposals'][0]
            expected_proposal.update(status='approved', decided_at=proposal.get('decided_at'), decided_by='사용자')
            expected['history'] = approved['history']
            expected['updated_at'] = approved['updated_at']
            if (approved != expected or approved['history'][:-1] != p['history']
                    or approved['history'][-1].get('event') != 'manager_user_decision'
                    or proposal.get('decided_by') != '사용자'):
                raise ValueError('승인 중 프로젝트 변경을 감지했습니다.')
            md.require_proceed(approved, 'TASK-002', ['TASK-001'])
            ai_safety.check_project_permission(approved)
            approved.setdefault('history', []).append({'event': 'task002_once_authorized', 'at': app.now(),
                'authorization_id': authorization_id, 'project_id': project_id, 'task_id': 'TASK-002',
                'proposal_id': proposal['id'], 'binding': deepcopy(proposal['decision']['binding']),
                'project_hash_before_approval': expected_hash, 'max_calls': 1, 'model': ai_safety.MODEL,
                'user_approval': USER_APPROVAL,
                'scope': '승인 목표·TASK-002 정의·허용 선호·TASK-001 승인 결과·승인 관리자 판단 및 지침'})
            app.save_project(approved)
            last_saved = app.load_project(project_id)
            previous_attempts = deepcopy(p['real_ai']['attempts'])

            def persist(value):
                nonlocal last_saved
                disk = app.load_project(project_id)
                ledger = value['real_ai']['attempts']
                if (disk != last_saved or len(ledger) != 6 or ledger[:5] != previous_attempts
                        or ledger[-1].get('kind') != 'task' or ledger[-1].get('task_id') != 'TASK-002'
                        or ledger[-1].get('model') != ai_safety.MODEL
                        or len(last_saved['real_ai']['attempts']) == 6 and last_saved['real_ai']['attempts'][-1]['status'] != 'reserved'):
                    raise ValueError('단일 직원 예약 저장 중 경합을 감지했습니다.')
                app.save_project(value)
                last_saved = app.load_project(project_id)

            def transport(request, **kwargs):
                disk = app.load_project(project_id)
                ledger = disk['real_ai']['attempts']
                if (observation['transport_calls'] or disk != last_saved or len(ledger) != 6
                        or ledger[:5] != previous_attempts or ledger[-1]['status'] != 'reserved'
                        or ledger[-1]['task_id'] != 'TASK-002' or ledger[-1]['kind'] != 'task'
                        or ledger[-1]['model'] != ai_safety.MODEL):
                    raise ValueError('정확한 단일 직원 예약이 없어 전송하지 않습니다.')
                observation.update(transport_calls=1, transport_started_at=app.now())
                observe()
                return original_transport(request, **kwargs)

            def save_execution(value):
                nonlocal last_saved
                if app.load_project(project_id) != last_saved:
                    raise ValueError('직원 결과 저장 중 경합을 감지했습니다. 재전송하지 않습니다.')
                app.save_project(value)
                last_saved = app.load_project(project_id)

            execution_engine.urlopen = transport
            with ai_safety.request_scope(persist):
                app.execute_project_task(project_id, 'TASK-002', _persist=save_execution)
            return app.load_project(project_id)
    finally:
        execution_engine.urlopen = original_transport
        observation.update(finished=True, finished_at=app.now())
        observe()
