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
    if (reason.startswith(('owner_policy_', 'secret_', 'fixed_', 'invalid_acceptance_', 'invalid_account_'))
            or reason in ('state_changed', 'production_project_key_unverified', 'production_manager_execution_disabled',
                          'gemini_unexpected_cost')):
        return 'policy_blocked'
    if reason == 'decision_internal_error':
        return 'internal_error'
    if attempt.get('response_received') or 'usage' in attempt or reason == 'invalid_manager_plan_schema':
        return 'provider_response_invalid'
    return 'outcome_uncertain'


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
        if details:
            diagnostics['decision_receipt'] = details
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
