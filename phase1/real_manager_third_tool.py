"""Explicit local owner runner. No startup hook or HTTP route; no automatic retry."""
import json
import os
from pathlib import Path
import app
import manager_decision as md


def run_once(project_id, expected_hash, *, authorization_id, guard_path, user_confirmed=False):
    if user_confirmed is not True:
        raise ValueError('새 관리자 3차 호출의 직접 승인이 필요합니다.')
    project = app.load_project(project_id)
    if md.digest(project) != expected_hash:
        raise ValueError('실행 전 프로젝트가 변경되었습니다.')
    state = project.get('manager_decisions', {})
    attempts = project.get('real_ai', {}).get('attempts', [])
    app.validate_third_manager_authorization(project, 'TASK-001', authorization_id)
    guard = Path(guard_path)
    # O_EXCL also blocks two local processes before either can reserve a call.
    fd = os.open(guard, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump({'authorization_id': authorization_id, 'project_id': project_id,
                   'at': app.now(), 'max_calls': 1}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    transport_calls = 0
    original = md.urlopen

    def counted_transport(request, **kwargs):
        nonlocal transport_calls
        if transport_calls:
            raise ValueError('도구의 실제 전송 최대 1회에 도달했습니다.')
        current = app.load_project(project_id)
        ledger = current['real_ai']['attempts']
        if (len(ledger) != 5 or ledger[:-1] != attempts
                or ledger[-1].get('status') != 'reserved'
                or ledger[-1].get('kind') != 'manager_decision'
                or ledger[-1].get('task_id') != 'TASK-001'
                or ledger[-1].get('model') != 'openrouter/free'):
            raise ValueError('정확한 단일 예약이 없어 전송하지 않습니다.')
        transport_calls += 1
        observation['transport_calls'] = transport_calls
        observation['transport_started_at'] = app.now()
        save_observation()
        return original(request, **kwargs)

    observation_path = guard.with_suffix('.observation.json')
    observation = {'authorization_id': authorization_id, 'started_at': app.now(),
                   'transport_calls': 0, 'finished': False}

    def save_observation():
        temp = observation_path.with_suffix('.tmp')
        temp.write_text(json.dumps(observation), encoding='utf-8')
        temp.replace(observation_path)

    save_observation()
    md.urlopen = counted_transport
    try:
        return app.propose_real_manager_third_authorized(project_id, 'TASK-001', expected_hash,
            authorization_id=authorization_id, user_confirmed=True,
            reason='새 사용자 승인: 응 호출 승인할게 다음 진행해줘. TASK-001 실제 관리자 판단 최대 1회, TASK-002 실행 및 재시도 미승인.')
    finally:
        md.urlopen = original
        observation.update(finished=True, finished_at=app.now())
        save_observation()
