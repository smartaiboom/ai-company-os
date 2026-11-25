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


def completion_snapshot(criteria, available_tools):
    """Facts supplied by a domain adapter, independent of the model's recommendation."""
    records = {}
    for row in criteria:
        key = row['id']
        refs = row['source_ids']
        require(key not in records and row['state'] in ('met','unmet','unknown')
                and type(row['observed']) is int and type(row['target']) is int
                and 0 <= row['observed'] and row['target'] > 0
                and (row['state']=='unknown' or (row['state']=='met') == (row['observed']>=row['target']))
                and len(refs)==len(set(refs)), 'judgment_criteria_invalid')
        records[key] = dict(state=row['state'], observed=row['observed'],
                            target=row['target'], source_ids=sorted(refs))
    facts = dict(criteria=records, available_tools=sorted(set(available_tools)))
    return dict(**facts, sha256=digest(facts))


def judgment_schema(snapshot):
    return obj(snapshot_sha256=enum(snapshot['sha256']),
               criteria=obj(**{key:obj(state=enum('met','unmet','unknown'),
                                      observed={'type':'integer'},source_ids=arr(S))
                               for key in snapshot['criteria']}))


def verify_judgment(value, snapshot):
    require(matches(value,judgment_schema(snapshot)), 'judgment_facts_invalid')
    for key, row in value['criteria'].items():
        bound = snapshot['criteria'][key]
        require(row['state']==bound['state'] and row['observed']==bound['observed']
                and sorted(row['source_ids'])==bound['source_ids'], 'judgment_facts_mismatch')


def completion_record(value, snapshot, attempts):
    """Retain an early stop for the reviewer with a deterministic gap assessment."""
    reason = value['stop_reason']
    require(reason in ('criteria_met','no_useful_path','access_limited','manager_review'), 'judgment_stop_invalid')
    safe_text(value['explanation'],460)
    remaining = [key for key,row in snapshot['criteria'].items() if row['state']!='met']
    require(reason!='criteria_met' or not remaining, 'judgment_premature_completion')
    require(reason!='access_limited' or not snapshot['available_tools']
            or any(row['status'] in ('unavailable','policy_blocked') for row in attempts),
            'judgment_access_unverified')
    return dict(reason=reason, explanation=value['explanation'], remaining=remaining,
                attempts=attempts, available_tools=snapshot['available_tools'],
                reviewer_attention=bool(remaining and snapshot['available_tools']),
                snapshot_sha256=snapshot['sha256'])


def approach_key(value):
    """Compare actual first actions, independent of a paraphrased rationale."""
    return value['tool'], ' '.join(value['option'].casefold().split())
