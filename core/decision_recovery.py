"""Safe decision feedback and separately authorized correction reservations."""
import re

from autonomous_company import CompanyError, digest, require


class DecisionViolation(CompanyError):
    """An application validator rejected a received decision."""

    def __init__(self, code, rule):
        super().__init__(code)
        require(re.fullmatch(r'[a-z][a-z0-9_]{0,63}', rule), 'invalid_decision_rule')
        self.rule = rule


class ProviderFailure(CompanyError):
    """The provider returned an HTTP response indicating failure."""

    failure_category = 'provider_failure'


def failure_kind(attempt):
    reason = attempt.get('reason', '')
    if attempt.get('http_status') is not None or reason == 'gemini_error_envelope':
        return 'provider_failure'
    if attempt.get('decision_rejection'):
        return 'decision_invalid'
    if (reason in ('gemini_request_contract_invalid','prepared_payload_changed')
            or reason.startswith(('owner_policy_', 'secret_', 'fixed_', 'invalid_acceptance_', 'invalid_account_'))
            or reason in ('state_changed', 'production_project_key_unverified', 'production_manager_execution_disabled',
                          'gemini_unexpected_cost')):
        return 'policy_blocked'
    if reason == 'decision_internal_error':
        return 'internal_error'
    if attempt.get('response_received') or 'usage' in attempt or reason == 'invalid_manager_plan_schema':
        return 'provider_response_invalid'
    return 'outcome_uncertain'


def gemini_failure_type(attempt):
    """Detailed fixed labels alongside existing recovery categories."""
    metadata=attempt.get('provider_response') or {}
    status=metadata.get('status')
    reason=metadata.get('reason')
    http=metadata.get('http_status',attempt.get('http_status'))
    if type(http) is int:
        if 500<=http<=599:
            return 'provider_unavailable'
        if (http in (402,429) or status=='RESOURCE_EXHAUSTED'
                or reason in ('BILLING_DISABLED','QUOTA_EXCEEDED','RATE_LIMIT_EXCEEDED')):
            return 'quota_or_billing'
        if http in (401,403) or reason in ('API_KEY_INVALID','API_KEY_SERVICE_BLOCKED'):
            return 'authentication_or_permission'
        return 'request_rejected' if 400<=http<=499 and http!=408 else 'transmission_uncertain'
    if attempt.get('reason') in ('gemini_request_contract_invalid','prepared_payload_changed'):
        return 'request_contract_invalid'
    stage=(attempt.get('diagnostic') or {}).get('stage')
    if stage=='response_parse':
        return 'response_parse_failed'
    if stage=='response_validate':
        return 'response_validation_failed'
    if stage=='decision_validation':
        return 'local_validation_failed'
    return 'transmission_uncertain' if failure_kind(attempt)=='outcome_uncertain' else None


def correction_feedback(attempt, reservation, rules, choices, *, legacy=None):
    """Build feedback exclusively from server-controlled vocabulary and signed scope choices."""
    require(attempt.get('status') == 'uncertain'
            and attempt.get('payload_hash') == reservation['payload_sha256']
            and attempt.get('http_status') is None, 'decision_recovery_blocked')
    usage = attempt.get('usage')
    require(isinstance(usage, dict) and type(usage.get('total_tokens')) is int
            and usage['total_tokens'] >= 0, 'decision_recovery_blocked')
    rejection = attempt.get('decision_rejection')
    if rejection:
        rule = rejection['rule']
        require(re.fullmatch(r'[a-f0-9]{64}', rejection['response_sha256']), 'decision_recovery_blocked')
    else:
        require(legacy and attempt.get('reason') in legacy, 'decision_recovery_blocked')
        rule = legacy[attempt['reason']]
    require(rule in rules and re.fullmatch(r'[a-f0-9]{32}', attempt.get('id', '')),
            'decision_recovery_blocked')
    return dict(rule=rule, instruction=rules[rule], choices=choices,
                step=reservation['unit']['id'], original_attempt=attempt['id'],
                original_reservation_sha256=digest(reservation),
                response_sha256=rejection['response_sha256'] if rejection else None)


def delegated_call(store, key, operation, payload_hash, execute):
    reservation = store.reserve(key, operation, payload_hash)
    try:
        store.active(key)
        execute(reservation['policy_hash'], lambda: store.active(key))
    except Exception as exc:
        category = getattr(exc, 'failure_category', None)
        if category is None:
            category = failure_kind({'reason': exc.code}) if isinstance(exc, CompanyError) else 'internal_error'
        details = getattr(exc, 'decision_receipt', None)
        diagnostics = dict(category=category)
        failure_type=getattr(exc,'failure_type',None)
        if failure_type is None and isinstance(exc,CompanyError) and exc.code in (
                'gemini_request_contract_invalid','prepared_payload_changed'):
            failure_type=gemini_failure_type({'reason':exc.code})
        if failure_type:
            diagnostics['failure_type']=failure_type
        if details:
            diagnostics['decision_receipt'] = details
        provider_response = getattr(exc, 'provider_response', None)
        if provider_response:
            diagnostics['provider_response'] = provider_response
        store.finish(reservation, 'failed_or_uncertain', diagnostics=diagnostics)
        raise
    store.finish(reservation, 'completed')


def correction_call(store, key, operation, payload_hash, feedback, execute):
    """Require a new signed grant and a one-use unit bound to the exact corrective request."""
    grant = store.active(key)
    require(grant['proposal'].get('correction_sha256') == digest(feedback)
            and operation.get('correction_sha256') == digest(feedback)
            and operation.get('payload_sha256') == payload_hash
            and operation['id'] == 'correct-' + feedback['step'], 'decision_recovery_blocked')
    delegated_call(store, key, operation, payload_hash, execute)


def received_contract_stop(row, attempt):
    """Identify a recorded local rejection after delivery, with no provider error."""
    outcome = row['result'] or {}
    diagnostics = outcome.get('diagnostics') or {}
    if not (attempt and outcome.get('status') == 'failed_or_uncertain'
            and diagnostics.get('failure_type') == 'local_validation_failed'
            and attempt.get('status') == 'uncertain'
            and attempt.get('response_received') is True
            and attempt.get('http_status') is None and not attempt.get('provider_response')
            and attempt.get('payload_hash') == row['reservation']['payload_sha256']
            and attempt.get('diagnostic', {}).get('stage') == 'decision_validation'
            and type(attempt.get('usage', {}).get('total_tokens')) is int
            and attempt['usage']['total_tokens'] >= 0):
        return None
    rejection = attempt.get('decision_rejection')
    if rejection and diagnostics.get('decision_receipt') != dict(
            attempt_id=attempt['id'], total_tokens=attempt['usage']['total_tokens'], **rejection):
        return None
    return dict(failed_payload_sha256=attempt['payload_hash'], rule=rejection['rule'] if rejection else None)


def remaining_delegation(source, credential, ledger):
    """Return the still-authorized units after counting every reservation."""
    policy = source.active(credential)
    units = {unit['id']: unit for unit in policy['proposal']['units']}
    require(all(name in units and row['reservation']['unit'] == units[name]
                and row['reservation']['policy_hash'] == digest(policy)
                for name, row in ledger.items()), 'owner_policy_scope_changed')
    return policy, [unit for name, unit in units.items() if name not in ledger]
