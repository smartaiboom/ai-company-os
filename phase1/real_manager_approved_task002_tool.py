"""Owner-only approved TASK-002 next decision, one new approval, no HTTP or worker execution."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import uuid
import app
import manager_decision as md
import ai_safety

PROJECT_ID = 'cb44b605b498'
PURPOSE = 'approved_result_next_decision'
USER_APPROVAL = '그래 진행해줘'


def preconditions(project, task_id, expected_hash, authorization_id, purpose):
    state = project.get('manager_decisions', {})
    attempts = project.get('real_ai', {}).get('attempts', [])
    proposals = state.get('proposals', [])
    if (project.get('id') != PROJECT_ID or task_id != 'TASK-002' or purpose != PURPOSE
            or md.digest(project) != expected_hash
            or not isinstance(authorization_id, str) or not re.fullmatch('[a-f0-9]{32}', authorization_id)
            or len(attempts) != 7 or any(a.get('status') != 'completed' or a.get('model') != ai_safety.MODEL for a in attempts)
            or [a.get('kind') for a in attempts] != ['plan', 'task', 'manager_decision', 'manager_decision', 'manager_decision', 'task', 'manager_decision']
            or [a.get('task_id') for a in attempts] != [None, 'TASK-001', 'TASK-001', 'TASK-001', 'TASK-001', 'TASK-002', 'TASK-002']
            or state.get('enabled') is not True or state.get('provider') != 'real_openrouter_free'
            or len(proposals) != 2 or len(proposals) >= 50 or proposals[0].get('purpose') is not None
            or proposals[0].get('status') != 'approved' or proposals[0].get('provider') != 'real_openrouter_free'
            or proposals[0]['decision']['action'] != 'proceed'
            or proposals[0]['decision']['binding']['task_id'] != 'TASK-001'
            or proposals[1].get('purpose') != md.REVIEW_PURPOSE or proposals[1].get('status') != 'accepted_for_review'
            or proposals[1].get('provider') != 'real_openrouter_free'
            or proposals[1]['decision']['binding']['task_id'] != 'TASK-002'
            or any(h.get('event') in ('real_manager_approved_next_once_authorized', 'real_manager_approved_next_stopped') or h.get('authorization_id') == authorization_id
                   for h in project.get('history', []))
            or any(t.get('status') != '대기' or t.get('result') for t in project['tasks'][2:])):
        raise ValueError('새 단일 후속 판단 승인 사전조건 불일치 또는 사용된 승인입니다.')
    ai_safety.check_project_permission(project)
    if (os.getenv('AI_MODEL') != ai_safety.MODEL or os.getenv('AI_API_BASE_URL', '').rstrip('/') != ai_safety.BASE_URL
            or not os.getenv('AI_API_KEY')):
        raise ValueError('무료 모델·고정 주소·키 조건을 확인해 주세요.')
    context = app._manager_decision_input(project, task_id)
    if any(p['decision']['binding'] == context['binding'] for p in proposals):
        raise ValueError('동일 승인 결과의 관리자 제안이 이미 있습니다.')
    return context


def run_once(project_id, task_id, expected_hash, *, authorization_id, guard_path, user_confirmed=False, purpose=PURPOSE):
    if user_confirmed is not True:
        raise ValueError('이번 후속 판단 호출의 직접 승인이 필요합니다.')
    with app.manager_decision_transaction(project_id) as project:
        context = preconditions(project, task_id, expected_hash, authorization_id, purpose)
        previous_attempts = deepcopy(project['real_ai']['attempts'])
        guard = Path(guard_path)
        fd = os.open(guard, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump({'authorization_id': authorization_id, 'project_id': project_id, 'task_id': task_id,
                       'purpose': purpose, 'at': app.now(), 'max_calls': 1}, f)
            f.flush(); os.fsync(f.fileno())
        observation = {'authorization_id': authorization_id, 'started_at': app.now(), 'transport_calls': 0, 'finished': False}
        observation_path = guard.with_suffix('.observation.json')

        def observe():
            temp = observation_path.with_suffix('.tmp')
            with temp.open('w') as f:
                json.dump(observation, f)
                f.flush(); os.fsync(f.fileno())
            temp.replace(observation_path)

        observe()
        original_transport = md.urlopen
        phase = 'authorization_persist'
        last_saved = deepcopy(project)

        def save_checked(value):
            nonlocal last_saved
            if app.load_project(project_id) != last_saved:
                raise ValueError('후속 판단 저장 중 프로젝트 경합을 감지했습니다.')
            app.save_project(value)
            last_saved = app.load_project(project_id)

        def immutable(value):
            result = deepcopy(value)
            result.pop('updated_at', None)
            result['real_ai'].pop('attempts', None)
            result['real_ai'].pop('stop_reason', None)
            return result

        try:
            project.setdefault('history', []).append({'event': 'real_manager_approved_next_once_authorized', 'at': app.now(),
                'authorization_id': authorization_id, 'project_id': project_id, 'task_id': task_id, 'purpose': purpose,
                'binding': deepcopy(context['binding']), 'project_hash': expected_hash, 'model': ai_safety.MODEL,
                'max_calls': 1, 'previous_attempt_ids': [a['id'] for a in previous_attempts],
                'allowed_data_fields': sorted(context['data']), 'user_approval': USER_APPROVAL,
                'scope': '승인 목표·해당 업무 정의·승인된 TASK-002 결과·허용 선호·직접 후속 업무·관련 사용자 답변·안전 예산 요약'})
            save_checked(project)
            before = deepcopy(last_saved)

            def persist(value):
                nonlocal phase
                ledger = value['real_ai']['attempts']
                phase = 'reservation_persist' if ledger[-1]['status'] == 'reserved' else 'ledger_persist'
                if (len(ledger) != 8 or ledger[:7] != previous_attempts
                        or ledger[-1].get('kind') != 'manager_decision' or ledger[-1].get('task_id') != task_id
                        or ledger[-1].get('model') != ai_safety.MODEL or immutable(value) != immutable(before)):
                    raise ValueError('정확한 단일 후속 판단 예약이 필요합니다.')
                if len(last_saved['real_ai']['attempts']) == 8:
                    reserved = deepcopy(ledger[-1]); reserved['status'] = 'reserved'; reserved.pop('finished_at', None)
                    if last_saved['real_ai']['attempts'][-1] != reserved:
                        raise ValueError('기존 예약이 변경되었습니다.')
                save_checked(value)
                phase = 'transport'

            def transport(request, **kwargs):
                current = app.load_project(project_id)
                ledger = current['real_ai']['attempts']
                if (observation['transport_calls'] or current != last_saved or len(ledger) != 8
                        or ledger[:7] != previous_attempts or ledger[-1]['status'] != 'reserved'
                        or ledger[-1]['task_id'] != task_id or ledger[-1]['kind'] != 'manager_decision'
                        or ledger[-1]['model'] != ai_safety.MODEL):
                    raise ValueError('단일 후속 판단 전송 조건이 맞지 않습니다.')
                observation.update(transport_calls=1, transport_started_at=app.now())
                observe()
                return original_transport(request, **kwargs)

            md.urlopen = transport
            with ai_safety.request_scope(persist):
                decision = md.RealManagerDecisionProvider().generate(project, context)
            phase = 'project_binding'
            current = app.load_project(project_id)
            ledger = current['real_ai']['attempts']
            if (current != last_saved or len(ledger) != 8 or ledger[:7] != previous_attempts
                    or ledger[-1]['status'] != 'completed' or immutable(current) != immutable(before)
                    or app._manager_decision_input(current, task_id)['binding'] != context['binding']):
                raise ValueError('후속 판단 중 프로젝트 지문이 변경되었습니다.')
            phase = 'decision_contract'
            md.parse_and_validate(json.dumps(decision, ensure_ascii=False), context)
            phase = 'proposal_persist'
            proposal = {'id': uuid.uuid4().hex, 'version': len(current['manager_decisions']['proposals']) + 1,
                'provider': 'real_openrouter_free', 'status': 'pending_user_decision',
                'at': app.now(), 'authorization_id': authorization_id, 'attempt_id': ledger[-1]['id'], 'decision': decision}
            current['manager_decisions']['proposals'].append(proposal)
            current['history'].append({'event':'manager_proposal_created', 'at':app.now(), 'purpose':purpose,
                'provider':'real_openrouter_free', 'proposal_id':proposal['id'], 'authorization_id':authorization_id,
                'binding':decision['binding'], 'attempt_id':ledger[-1]['id']})
            save_checked(current)
            return deepcopy(proposal)
        except Exception as exc:
            stage = exc.stage if isinstance(exc, md.DecisionDiagnosticError) else phase
            code = exc.code if isinstance(exc, md.DecisionDiagnosticError) else 'operation_failed'
            current = app.load_project(project_id)
            current.setdefault('history', []).append({'event':'real_manager_approved_next_stopped', 'at':app.now(),
                'authorization_id':authorization_id, 'purpose':purpose, 'task_id':task_id, 'stage':stage, 'error_code':code})
            try:
                app.save_project(current)
            except Exception:
                raise RuntimeError('후속 판단 중단 이력 저장 실패. 재시도하지 않습니다.') from None
            raise RuntimeError('실제 관리자 후속 판단 중단. 원장과 승인을 보존하고 재시도하지 않습니다.') from None
        finally:
            md.urlopen = original_transport
            observation.update(finished=True, finished_at=app.now())
            observe()
