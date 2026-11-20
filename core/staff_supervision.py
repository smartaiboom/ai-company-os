"""Bounded staff execution and independent manager supervision."""
from autonomous_company import require, validate_checks
from goal_dialogue import safe_text
from role_json_schema import CHECK, S, arr, enum, obj

LIMITS = dict(staff=3, manager=2, initial_staff=2, revisions=1, final_review_reserved=1)
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
    for index in range(LIMITS['initial_staff']):
        if staff(index, None):
            break
    first = review(0, None)
    if first['action'] != 'revise':
        return first
    staff(LIMITS['initial_staff'], first)
    return review(1, first)
