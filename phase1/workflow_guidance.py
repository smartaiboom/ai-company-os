"""Read-only generic workflow preparation and explicit user-decision controls."""
import json
from html import escape
import manager_decision as md


def inspect(project, *, runtime=None):
    if runtime is None:
        import app as runtime
    app=runtime
    rows=[]
    semantic=project.get('semantic',{})
    for index,task in enumerate(project.get('tasks',[])):
        blockers=[]
        if task.get('status')=='완료':
            if task.get('review_status')=='changes_requested':
                blockers.append('사용자 수정 요청 상태 · 별도 실행 승인 후 수정·결과 재승인 필요')
            elif semantic and task['id']==semantic.get('reviewer_task_id') and semantic.get('review',{}).get('verdict') in ('changes_needed','inconclusive'):
                blockers.append('수정 필요 · 사용자 수정 여부 결정 후 진행' if semantic['review']['verdict']=='changes_needed'
                                else '판정 불가 · 추가 근거와 사용자 검토 필요, 자동 진행·재전송 금지')
            elif task.get('review_status')!='approved':blockers.append('사용자 결과 검토·승인 필요')
        else:
            try:
                inputs=app._validate_task_predecessors(task,project['tasks'],index)
                md.require_proceed(project,task['id'],inputs)
            except ValueError as exc:
                blockers.append(str(exc))
            if task.get('role')=='품질 검토 담당' and not semantic:
                blockers.append('품질 성공 기준의 사용자 승인·의미 검토 담당 설정 필요')
            if semantic and task['id']==semantic.get('reviewer_task_id'):
                if any(r.get('phase')=='reserved' for r in semantic.get('reviews',[])):
                    blockers.append('의미 검토 예약이 남아 있음 · 자동 재전송 금지')
            if semantic and index>next((i for i,t in enumerate(project['tasks']) if t['id']==semantic.get('reviewer_task_id')),len(project['tasks'])):
                try:app.validate_semantic_pass(project)
                except (ValueError,KeyError,TypeError):blockers.append('최신 의미 검토 통과와 사용자 검토 승인 필요')
        rows.append({'task_id':task['id'],'name':task.get('name',''),'status':task.get('status','대기'),
                     'review_status':task.get('review_status','미검토'),'blockers':blockers})
    attempts=project.get('real_ai',{}).get('attempts',[])
    failures=[h for h in project.get('history',[]) if h.get('stage') and h.get('error_code')]
    return {'tasks':rows,'unresolved_reservations':sum(a.get('status')=='reserved' for a in attempts),
            'last_diagnostic':{k:failures[-1][k] for k in ('stage','error_code')} if failures else None,
            'actual_call_approval_required':True}


def criteria_draft(project):
    """Suggestions are displayed, never saved or treated as approved criteria."""
    tasks=project.get('tasks',[])
    target=reviewer=''
    for index,task in enumerate(tasks):
        if 0<index<len(tasks)-1 and task.get('role')=='품질 검토 담당':
            previous=tasks[index-1]
            if previous['id'] in task.get('input_task_ids',[]):
                target,reviewer=previous['id'],task['id'];break
    draft=project.get('success_criteria_draft',{})
    items=[v for v in draft.get('items',[]) if isinstance(v,str)][:8]
    return target,reviewer,'\n'.join(items)


def render(project, *, runtime=None):
    if runtime is None:
        import app as runtime
    app=runtime
    esc=lambda value:escape(str(value),quote=True)
    state=inspect(project, runtime=app)
    parts=['<section class="card"><h2>업무 연결과 다음 사용자 결정</h2>',
           '<p>답변·제안 수락·결과 승인·품질 기준 승인·실제 호출 승인은 각각 별도입니다. 이 화면의 결정 저장은 AI를 호출하지 않습니다.</p>']
    if state['unresolved_reservations']:
        parts.append('<p>미완료 AI 예약이 있습니다. 원장·관측 확인 전 재전송하지 마세요.</p>')
    if state['last_diagnostic']:
        d=state['last_diagnostic']
        parts.append(f"<p>과거 중단 기록: {esc(d['stage'])} / {esc(d['error_code'])}. 소모된 시도는 재사용하지 않으며 새 실제 요청은 별도 승인이 필요합니다.</p>")
    parts.append('<ul>')
    for row in state['tasks']:
        detail=' / '.join(row['blockers']) or ('완료·사용자 승인됨' if row['status']=='완료' else '선행 조건 확인됨 · 실제 호출은 별도 승인 필요')
        parts.append(f"<li>{esc(row['task_id'])} {esc(row['name'])}: {esc(row['status'])} · {esc(row['review_status'])}<br>{esc(detail)}</li>")
    parts.append('</ul>')
    if project.get('manager_decisions',{}).get('enabled'):
        for proposal in app.manager_decision_view(project['id']):
            decision=proposal['decision']
            parts.append(f"<article><h3>관리자 판단: {esc(decision['action'])}</h3><p>{esc(proposal['status'])} · {esc('현재 입력과 다름 · 과거 기록' if proposal['stale'] else '현재 입력과 일치')}</p>")
            for label,key in (('판단 근거','rationale'),('자료 대조','evidence'),('다음 단계','next_step'),('불확실성','uncertainty')):
                parts.append(f'<p>{label}: {esc(decision[key])}</p>')
            payload=decision['payload']
            if decision['action']=='ask_user':
                parts.append(f"<p>질문: {esc(payload['question'])}</p><p>{esc(payload['why_needed'])}</p><ul>"+''.join(f'<li>{esc(v)}</li>' for v in payload['options'])+'</ul>')
            else:parts.append(f'<pre>{esc(json.dumps(payload,ensure_ascii=False,indent=2))}</pre>')
            for answer in project['manager_decisions'].get('answers',[]):
                if answer['proposal_id']==proposal['id']:parts.append(f"<p>사용자 답변: {esc(answer['answer'])}</p>")
            if proposal['status']=='pending_user_decision' and not proposal['stale']:
                parts.append('<form method="post" action="/manager/decision">')
                for key,value in {'id':project['id'],'proposal_id':proposal['id'],'expected_hash':proposal['expected_hash'],
                                  'expected_project_hash':md.digest(project)}.items():
                    parts.append(f'<input type="hidden" name="{key}" value="{esc(value)}">')
                if decision['action']=='ask_user':
                    parts.append('<label>사용자 답변<textarea name="answer" maxlength="2000" required></textarea></label><button name="response" value="answer">답변만 저장 (실제 호출 없음)</button>')
                else:
                    label='진행 제안 승인 (실제 호출은 별도)' if decision['action']=='proceed' and not proposal.get('purpose') else '검토·변경 제안 수락 (자동 적용 없음)'
                    parts.append(f'<button name="response" value="approve">{label}</button>')
                parts.append('<button name="response" value="reject" formnovalidate>거절</button></form>')
            parts.append('</article>')
        parts.append('<p>답변 후에는 현재 입력에 대한 새 관리자 판단이 필요합니다. request_revision·계획 변경 수락은 자동 수정·계획 적용이 아닙니다. 모델의 사실 확인 주장은 독립 검증이 아닙니다.</p>')
    parts.append('</section>')
    return ''.join(parts)
