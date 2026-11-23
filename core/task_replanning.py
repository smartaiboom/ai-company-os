"""Bounded manager contract for reviewing a failed task."""
from autonomous_company import digest, require
from goal_dialogue import safe_text
from role_json_schema import S, arr, enum, matches, obj

INTENTS = ('review_options', 'prefer_reinvestigation')
ACTIONS = ('reinvestigate', 'alternative', 'hold', 'ask_owner')


def context(goal, stage, failures, observations, tools, contract, limits, owner_intent):
    require(owner_intent in INTENTS, 'replan_invalid')
    require(failures and all(item['response_received'] is True for item in failures), 'replan_blocked')
    return dict(goal=goal, stage=stage, failures=failures, preserved_observations=observations,
                missing_evidence=dict(preserved_source_count=sum(len(row['sources']) for row in observations),
                    instruction='Identify gaps relative to the task and explain how to address them.'),
                available_tools=tools, current_contract=contract, limits=limits, owner_intent=owner_intent)


def schema(tool_names):
    fields = dict(reason=S, next_step=S, success_criteria=S)
    terminal = obj(action=enum(*ACTIONS[1:]), tools={**arr(S), 'maxItems':0}, **fields)
    if not tool_names:
        return terminal
    research = obj(action=enum('reinvestigate'),
                   tools={**arr(enum(*tool_names)), 'minItems':1, 'maxItems':len(tool_names)}, **fields)
    return {'anyOf':[research, terminal]}


def validate(value, contract):
    require(matches(value, contract), 'replan_invalid')
    require(len(set(value['tools'])) == len(value['tools']), 'replan_invalid')
    for field in ('reason', 'next_step', 'success_criteria'):
        safe_text(value[field], 460)


def history_link(policy, ledger, observations):
    return dict(policy_sha256=digest(policy), ledger_sha256=digest(ledger),
                observations_sha256=digest(observations))


def strategy_schema(routes, work_schema):
    return obj(route=enum(*routes),reason=S,success_criteria=S,risk=S,work=arr(work_schema))


def strategy_assignment(decision, contract, inputs, roles):
    """Bind validated work to a specialist and the original approved input."""
    require(matches(decision,contract),'strategy_invalid')
    for field in ('reason','success_criteria','risk'):
        safe_text(decision[field],460)
    role=roles.get(decision['route'])
    require(bool(role)==bool(decision['work']),'strategy_invalid')
    if not role:
        return None
    return dict(role=role,input_sha256=digest(inputs),decision_sha256=digest(decision),
                work=decision['work'],completion=decision['success_criteria'],risk=decision['risk'],
                next_reviewer='owner')
