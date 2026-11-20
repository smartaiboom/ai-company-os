"""Bounded staff execution and independent manager supervision."""
from autonomous_company import require, validate_checks
from goal_dialogue import safe_text
from role_json_schema import CHECK, S, arr, enum, obj

LIMITS = dict(staff=3, manager=2, initial_staff=2, revisions=1, final_staff_report_reserved=1, final_review_reserved=1)
CONTRACT = 'goal_supervision_v1'


def review_schema(criteria, *, can_accept, can_revise):
    actions = ['hold', 'alternative', 'ask_owner']
    if can_accept:
        actions.append('accept')
    if can_revise:
        actions.append('revise')
    return obj(action=enum(*actions), rationale=S, feedback=S, confirmation=S,
               checks={**arr(CHECK), 'minItems':len(criteria), 'maxItems':len(criteria)})


def validate_review(value, criteria):
    for field in ('rationale', 'feedback', 'confirmation'):
        safe_text(value[field], 460)
    passed = validate_checks(value['checks'], [item['id'] for item in criteria])
    for check in value['checks']:
        safe_text(check['evidence'], 460)
    if value['action'] == 'accept':
        require(passed, 'quality_unverified')


def run(staff, review):
    """Reserve one employee decision and the final independent review for a single revision."""
    final_staff = LIMITS['initial_staff']
    for index in range(final_staff):
        if staff(index, None):
            break
    else:
        staff(final_staff, None)
        return review(1, None)
    first = review(0, None)
    if first['action'] != 'revise':
        return first
    staff(final_staff, first)
    return review(1, first)


def run_action_first(act, report, review):
    """Keep one staff report and final review available after collection."""
    last = LIMITS['initial_staff']
    for index in range(last):
        decision = act(index)
        if decision['action'] in ('report', 'hold'):
            report(index + 1, decision, None)
            first = review(0 if index == 0 else 1, None)
            if index == 0 and first['action'] == 'revise':
                report(last, decision, first)
                return review(1, first)
            return first
    report(last, None, None)
    return review(1, None)
