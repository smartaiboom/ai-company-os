"""Read-only checkpoints for stopped general research stages."""
from datetime import datetime

from autonomous_company import digest, now, require
from web_research import evidence_catalog


def checkpoint(store, ledger):
    from research_workflow import linked_attempt

    failed = [(name, row) for name, row in ledger.items()
              if (row['result'] or {}).get('status') != 'completed']
    if not failed:
        return None
    completed = sorted(name for name, row in ledger.items()
                       if (row['result'] or {}).get('status') == 'completed')
    names = sorted((path for path in store.root.glob('observation-*.json')
                    if path.stem.rsplit('-', 1)[1].isdigit()), key=lambda path: int(path.stem.rsplit('-', 1)[1]))
    observations = [store.read(path.name) for path in names]
    saved_result = store.read('research-result.json')
    if saved_result:
        observations = saved_result['observations']
    catalog = evidence_catalog(observations)
    response = {}
    eligible = False
    if len(failed) == 1:
        name, row = failed[0]
        attempt = linked_attempt(store, name, row)
        recorded = ((row['result'] or {}).get('diagnostics') or {}).get('provider_response', {})
        response = recorded
        eligible = bool(attempt and attempt.get('provider_response') == recorded
                        and recorded.get('http_status') == 400 and recorded.get('status') == 'INVALID_ARGUMENT'
                        and not recorded.get('reason') and not attempt.get('response_received')
                        and observations and not saved_result)
    return dict(observations=observations, completed=completed, failed=sorted(name for name, _ in failed),
                sources=len(catalog), response=response, eligible=eligible, ledger_sha256=digest(ledger),
                excluded_units=sorted(ledger),
                excluded_payloads=sorted(row['reservation']['payload_sha256'] for row in ledger.values()))


def choose(store, state, route):
    require(state and not store.read('continuation.json') and
            (route == 'hold' or route in ('collect', 'report') and state['eligible']
             or route == 'contract_repair' and state.get('contract_repair')
             or route == 'development_contract' and state.get('development_contract')), 'research_continuation_blocked')
    record = dict(route=route, checkpoint=state, checkpoint_sha256=digest(state), at=now())
    store.write('continuation.json', record)
    return record


def contract_repair_offer(source, base, state, ledger):
    """Only a confirmed first-step option rejection can enter this repair path."""
    from research_work_scope import envelope
    from research_workflow import ENDPOINT, MODEL, linked_attempt

    if (base.get('continuation') or base.get('previous') or not state or state['observations']
            or set(ledger) != {'research-0'} or source.read('revoked.json')
            or source.read('research-result.json') or source.read('manager-review.json')):
        return None
    work = envelope(source, base)
    original, stage = work.read('policy.json'), source.read('policy.json')
    if not original or not stage or work.read('revoked.json'):
        return None
    expiry = min(original['expires_at'], stage['expires_at'])
    if datetime.fromisoformat(expiry) <= datetime.fromisoformat(now()):
        return None
    charges = work.attempts()
    if set(charges) != {'gemini-0'}:
        return None
    row, charge = ledger['research-0'], charges['gemini-0']
    if any(not item['result'] or item['result']['status'] != 'failed_or_uncertain' for item in (row, charge)):
        return None
    reservation, spent = row['reservation'], charge['reservation']
    unit = reservation['unit']
    if (unit not in stage['proposal']['units'] or (unit['model'], unit['endpoint']) != (MODEL, ENDPOINT)
            or original['proposal']['initial_stage_sha256'] != digest(stage['proposal'])
            or reservation['policy_hash'] != digest(stage) or spent['policy_hash'] != digest(original)
            or spent['payload_sha256'] != digest(dict(operation=unit, payload_hash=reservation['payload_sha256']))):
        return None
    attempt = linked_attempt(source, 'research-0', row)
    proof = row['result'].get('diagnostics', {})
    if (not attempt or attempt.get('response_received') is not True or attempt.get('provider_response')
            or attempt.get('reason') != 'research_step_invalid' or attempt.get('failure_type') != 'local_validation_failed'
            or attempt.get('decision_rejection', {}).get('rule') != 'option_not_allowed'
            or proof != charge['result'].get('diagnostics')):
        return None
    observed = dict(attempt_id=attempt['id'], total_tokens=attempt.get('usage', {}).get('total_tokens'),
                    **attempt['decision_rejection'])
    if (type(observed['total_tokens']) is not int or observed['total_tokens'] <= 0
            or proof.get('decision_receipt') != observed):
        return None
    budget = original['proposal']['limits'].copy()
    budget['gemini'] -= 1
    receipt = dict(stage_grant=digest(stage), work_grant=digest(original), work_ledger=digest(charges),
                   rejected_response=observed['response_sha256'], remaining=budget, expires_at=expiry)
    return dict(receipt=receipt, work=work)


def checked_contract_repair(store, base, credential=None, *, scope):
    from research_workflow import continuation_source, parent_store

    continuation = base['continuation']
    source = parent_store(store, continuation)
    snapshot = continuation_source(store, continuation)
    original_base = {key:value for key,value in base.items() if key != 'continuation'}
    repair = contract_repair_offer(source, original_base, snapshot, source.attempts())
    require(repair and snapshot['contract_repair'] == repair['receipt'], 'research_continuation_blocked')
    parent_scope = source.read('policy.json')['proposal']
    require(scope['units'] == parent_scope['units'], 'owner_policy_scope_changed')
    if credential is not None:
        repair['work'].active(credential)
        source.active(credential)
    return repair['receipt']

def development_contract_offer(source, base, state, ledger):
    from decision_recovery import received_contract_stop
    from research_work_scope import CORRECTABLE_RULES, envelope
    from research_workflow import ENDPOINT, MODEL, linked_attempt

    prior = base.get('continuation', {})
    if (not state or state['observations'] or base.get('previous')
            or prior and not prior.get('contract_repair') or set(ledger) != {'research-0'}
            or source.read('revoked.json') or source.read('research-result.json') or source.read('manager-review.json')):
        return None
    row = ledger['research-0']
    proof = received_contract_stop(row, linked_attempt(source, 'research-0', row))
    if not proof or proof['rule'] not in CORRECTABLE_RULES:
        return None
    work = envelope(source, base)
    stage, policy = source.read('policy.json'), work.read('policy.json')
    charges = work.attempts()
    if not stage or not policy or work.read('revoked.json') or set(charges) != {'gemini-0'}:
        return None
    reservation = row['reservation']
    operation = reservation['unit']
    charge = charges['gemini-0']
    if ((operation['model'], operation['endpoint']) != (MODEL, ENDPOINT) or operation not in stage['proposal']['units']
            or reservation['policy_hash'] != digest(stage)
            or policy['proposal']['initial_stage_sha256'] != digest(stage['proposal'])
            or charge['reservation']['policy_hash'] != digest(policy)
            or charge['reservation']['payload_sha256'] != digest(dict(operation=operation,payload_hash=proof['failed_payload_sha256']))
            or not charge['result'] or charge['result']['status'] != 'failed_or_uncertain'
            or charge['result'].get('diagnostics') != row['result'].get('diagnostics')):
        return None
    return dict(stage_grant=digest(stage),work_grant=digest(policy),work_ledger=digest(charges),
                prior_continuation=prior,rule=proof['rule'])


def checked_development_contract(store, base, scope, credential=None):
    from research_workflow import continuation_source, parent_store
    from research_work_scope import envelope

    continuation=base['continuation']
    source=parent_store(store,continuation)
    snapshot=continuation_source(store,continuation)
    parent={key:value for key,value in base.items() if key!='continuation'}
    prior=snapshot['development_contract']['prior_continuation']
    if prior:
        parent['continuation']=prior
    proof=development_contract_offer(source,parent,snapshot,source.attempts())
    require(proof and proof==snapshot['development_contract'],'research_continuation_blocked')
    stage=source.read('policy.json')
    require([unit for unit in scope['units'] if not unit['id'].startswith('correct-')]==stage['proposal']['units'],
            'owner_policy_scope_changed')
    if credential is not None:
        work=envelope(source,parent)
        work.check_credential(work.read('policy.json'),credential)
        source.check_credential(stage,credential)
    return proof
