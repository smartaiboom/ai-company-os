"""Evidence for explicit, separately approved recovery after a provider rejection."""
from autonomous_company import digest, require


def service_unavailable_receipt(row, attempt):
    """A linked HTTP 503 is distinct from an unconfirmed delivery or a quota failure."""
    outcome=row['result'] or {}
    metadata=(outcome.get('diagnostics') or {}).get('provider_response')
    if not (attempt and outcome.get('status')=='failed_or_uncertain' and metadata
            and attempt.get('provider_response')==metadata
            and metadata.get('http_status')==503 and metadata.get('status')=='UNAVAILABLE'
            and not metadata.get('reason') and not attempt.get('response_received')
            and not attempt.get('usage') and attempt.get('payload_hash')==row['reservation']['payload_sha256']):
        return None
    return dict(observed_at=outcome['at'],source='signed_provider_http_response',
                model=attempt['model'],endpoint=attempt['endpoint'],response=metadata,
                availability='unknown',billing='unknown',quota='unknown',
                failed_payload_sha256=attempt['payload_hash'],
                failed_reservation_sha256=digest(row['reservation']))


def check_recovery_transition(record, ledger, work_ledger, work_policy, snapshot):
    require(record['ledger_sha256']==digest(ledger)
            and record['work_ledger_sha256']==digest(work_ledger)
            and record['work_policy_sha256']==digest(work_policy)
            and record['snapshot_sha256']==digest(snapshot),
            'research_continuation_blocked')
