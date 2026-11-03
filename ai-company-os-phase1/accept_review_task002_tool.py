"""Local owner acceptance and result approval only. No engines or network."""
from copy import deepcopy
import hashlib
import app
import manager_decision as md

PROJECT_ID = 'cb44b605b498'
USER_APPROVAL = '응 다음 품질검토 단계로 진행하자'


def run_once(project_id, proposal_id, expected_project_hash, expected_result_hash, *, user_approval):
    p = app.load_project(project_id)
    if (project_id != PROJECT_ID or user_approval != USER_APPROVAL or md.digest(p) != expected_project_hash
            or len(p['real_ai']['attempts']) != 7 or any(a['status'] != 'completed' for a in p['real_ai']['attempts'])
            or any(t['status'] != '대기' or t.get('result') for t in p['tasks'][2:])):
        raise ValueError('이번 사용자 승인 및 최신 프로젝트 상태가 필요합니다.')
    task = next(t for t in p['tasks'] if t['id'] == 'TASK-002')
    if (task.get('review_status') != 'pending' or task['status'] != '완료'
            or hashlib.sha256(task['result'].encode()).hexdigest() != expected_result_hash):
        raise ValueError('승인할 결과 원문 또는 검토 상태가 변경되었습니다.')
    view = next((v for v in app.manager_decision_view(project_id) if v['id'] == proposal_id), None)
    if (view is None or view['purpose'] != md.REVIEW_PURPOSE or view['provider'] != 'real_openrouter_free'
            or view['status'] != 'pending_user_decision' or view['stale']
            or view['decision']['binding']['task_id'] != 'TASK-002' or view['decision']['action'] != 'proceed'
            or set(view['decision']['payload']['next_task_ids']) != {'TASK-003','TASK-004'}):
        raise ValueError('현재 실제 관리자 review proceed 제안이 필요합니다.')
    app.respond_manager_decision(project_id, proposal_id, view['expected_hash'], 'approve',
                                expected_project_hash=expected_project_hash)
    with app.manager_decision_transaction(project_id) as accepted:
        proposal = next(v for v in accepted['manager_decisions']['proposals'] if v['id'] == proposal_id)
        expected = deepcopy(p)
        e = next(v for v in expected['manager_decisions']['proposals'] if v['id'] == proposal_id)
        e.update(status='accepted_for_review', decided_at=proposal.get('decided_at'), decided_by='사용자')
        expected['history'] = accepted['history']; expected['updated_at'] = accepted['updated_at']
        if (accepted != expected or accepted['history'][:-1] != p['history']
                or accepted['history'][-1].get('event') != 'manager_user_decision'
                or accepted['tasks'][1]['review_status'] != 'pending'):
            raise ValueError('관리자 수락 후 프로젝트 변경을 감지했습니다. 재실행하지 않습니다.')
        audit = {'at':app.now(), 'event':'review_proceed_and_result_user_approved', 'project_id':project_id,
            'task_id':'TASK-002', 'proposal_id':proposal_id, 'user_approval':user_approval,
            'result_sha256':expected_result_hash, 'result_revision':task.get('result_revision',0),
            'binding':deepcopy(proposal['decision']['binding']), 'actual_ai_call_authorized':False,
            'details':'관리자 검토 수락 후 사용자 결과 승인. 모델의 승인 표현은 사용자 승인 근거가 아니며 실제 호출은 미승인.'}
        app.review_task_result(project_id,'TASK-002','approve',expected_project_hash=md.digest(accepted),approval_audit=audit)
    return app.load_project(project_id)
