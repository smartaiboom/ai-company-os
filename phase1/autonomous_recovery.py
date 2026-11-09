"""Read-only recovery assessment. Proposals never grant or perform a new send."""
from autonomous_company import require, digest, now
from autonomous_free import FreeStore
import ai_safety


def recovery_proposal(store, project_id):
    require(type(store) is FreeStore,'free_store_required')
    p=store.load(project_id)
    attempts=p['real_ai']['attempts'];last=attempts[-1] if attempts else None
    state='no_attempt'
    if last:
        if last['status']=='reserved':
            state=('received_before_cost_commit' if last.get('response_received_at') else
                   'sent_outcome_unknown' if last.get('transport_started_at') else 'reserved_outcome_unknown')
        elif last['status']=='failed':state='failed_or_ambiguous'
        elif last.get('role_result_status')=='validated':state='validated_checkpoint'
        elif last.get('response_received_at'):state='received_unvalidated'
        else:state='completed_unvalidated_legacy'
    d=last.get('response_diagnostics',{}) if last else {}
    # A known length-limited, zero-cost, unaccepted plan can be reviewed for ONE
    # fresh request. Still no execution capability or authorization is issued.
    candidate=bool(last and state=='received_unvalidated' and p['status']=='stopped'
        and p['phase']=='plan' and not p['plan'] and not p['assignments'] and not p['artifacts']
        and p.get('active_operation')==last['id'] and last.get('cost_verified_zero') is True
        and d.get('finish')=='length' and d.get('cost')=='zero'
        and d.get('validation')=='incomplete_response'
        and all(a['status']=='completed' and a.get('role_result_status')=='validated'
                and a.get('cost_verified_zero') is True for a in attempts[:-1]))
    grant_valid=True
    try:grant=store.grant(p)
    except (ValueError,OSError):grant_valid=False;grant=None
    candidate=candidate and grant_valid
    body={'version':1,'created_at':now(),'project_id':p['id'],'goal_hash':ai_safety.goal_hash(p['goal']),
          'state_hash':p['storage_hash'],'store_binding':digest(str(store.root)),
          'attempt_id':last['id'] if last else None,'attempt_hash':digest(last) if last else None,
          'operating_contract_hash':digest(grant['body']) if grant else None,
          'state_class':state,'assessment':'review_one_new_plan_request' if candidate else 'blocked_pending_audit',
          'reason':'known_length_zero_cost_unapplied_plan' if candidate else 'insufficient_safe_recovery_evidence',
          'provider':'openrouter','model':ai_safety.MODEL,'max_cost':0,'free_only':True,
          'proposed_max_additional_attempts':1 if candidate else 0,
          'automatic_retry':False,'execution_authorized':False,'execution_implemented':False,
          'requires_separate_operational_approval':True,'preserve_original_attempt':True,
          'notice':'읽기 전용 검토안. 승인/송신/원장 변경 권한 없음. 기존 run/continue는 복구 실행 명령이 아닙니다.'}
    require(store.load(project_id)['storage_hash']==p['storage_hash'],'state_changed')
    return {'proposal':body,'review_hash':digest(body)}
