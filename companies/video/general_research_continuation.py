"""Read-only checkpoints for stopped general research stages."""
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
            (route == 'hold' or route == 'collect' and state['eligible']), 'research_continuation_blocked')
    record = dict(route=route, checkpoint=state, checkpoint_sha256=digest(state), at=now())
    store.write('continuation.json', record)
    return record
