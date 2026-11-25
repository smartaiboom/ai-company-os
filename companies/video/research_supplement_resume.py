"""Reconstruct a stopped supplement from its signed records."""
import re

from autonomous_company import CompanyError, digest, require
from autonomous_gemini35 import ENDPOINT, MODEL
from decision_recovery import received_contract_stop, remaining_delegation


def execution_slots(offer, state=None):
    steps = offer['limits']['collection_actions']
    if state is None:
        return 0, list(range(1,steps+1)), steps+1, steps+2
    original_steps = offer['resume_original_steps']
    available = sorted(int(unit['id'].split('-')[1]) for unit in offer['units']
                       if unit['id'].startswith('research-'))
    report, review = original_steps+1, original_steps+2
    if state['stage'] == 'report':
        report = next(index for index in available if index != review)
    elif state['stage'] == 'review':
        review = available[0]
    choices = [index for index in available if index not in (report,review)][:steps]
    return len(state['observations']), choices, report, review


def parent(source, offer):
    from research_workflow import parent_store

    return parent_store(source, {'source_sha256': offer['resume_source_input_sha256']})


def ancestry(source):
    current = source
    while True:
        yield current
        offer = current.read('policy.json')['proposal']
        if 'resume_source_input_sha256' not in offer:
            return
        current = parent(current, offer)


def check_ancestors(source, credential):
    for current in ancestry(source):
        require(not current.read('supplement-closed.json'), 'research_continuation_blocked')
        current.active(credential)


def checkpoint(source, prior):
    from research_workflow import linked_attempt

    policy = source.read('policy.json')
    if not policy or source.read('manager-review.json') or source.read('supplement-outcome.json'):
        return None
    offer = policy['proposal']
    inherited = None
    if offer.get('resume_checkpoint_sha256'):
        inherited = checkpoint(parent(source, offer), prior)
        if not inherited or digest(inherited) != offer['resume_checkpoint_sha256']:
            return None
    ledger = source.attempts()
    units = {unit['id']: unit for unit in offer['units']}
    if (offer.get('prior_report_sha256') != prior['sha256']
            or any(name not in units or row['reservation']['unit'] != units[name]
                   or row['reservation']['policy_hash'] != digest(policy) for name, row in ledger.items())):
        return None
    failures = [name for name, row in ledger.items() if (row['result'] or {}).get('status') != 'completed']
    if len(failures) != 1:
        return None
    failed = failures[0]
    match = re.fullmatch(r'research-(\d+)', failed)
    start, selections, report_index, review_index = execution_slots(offer, inherited)
    steps = offer['limits']['collection_actions']
    index = int(match[1]) if match else None
    if index not in (*selections, report_index, review_index):
        return None
    stage = 'review' if index == review_index else 'report' if index == report_index else 'selection'
    attempt = linked_attempt(source, failed, ledger[failed])
    rejection = received_contract_stop(ledger[failed], attempt)
    if not rejection or (attempt['model'], attempt['endpoint']) != (MODEL, ENDPOINT):
        return None
    # Missing historical rule is allowed only for the older selection contract.
    known = {'supplement_finish_option_not_empty', 'supplement_query_whitespace', 'invalid_finish'}
    if stage == 'review':
        known.add('supplement_worker_shape')
    if rejection['rule'] not in known and not (
            not inherited and rejection['rule'] is None and stage == 'selection'
            and attempt['reason'] == 'research_step_invalid'):
        return None
    corrections = list(inherited['corrections']) if inherited else []
    correction = [stage, rejection['rule']]
    if correction in corrections:
        return None
    corrections.append(correction)
    plan = source.read('supplement-plan.json')
    if not plan or plan['decision']['action'] != 'reinvestigate':
        return None
    if inherited:
        if plan != inherited['plan']:
            return None
    else:
        plan_model = linked_attempt(source, 'research-0', ledger['research-0']) if 'research-0' in ledger else None
        reconsider = f'research-{steps+3}'
        if source.read('supplement-initial-plan.json') and reconsider in ledger:
            plan_model = linked_attempt(source, reconsider, ledger[reconsider])
        if (not plan_model or plan_model['status'] != 'completed'
                or plan_model['response_hash'] != digest({'decision': plan['decision']})):
            return None
    observations = list(inherited['observations']) if inherited else []
    collection_units = set()
    for offset, path in enumerate(sorted(source.root.glob('observation-*.json'))):
        i = start + offset
        if path.name != f'observation-{i:02}.json' or offset >= len(selections):
            return None
        row = source.read(path.name)
        kind = row['tool']
        if kind == f'youtube_sample_{i}':
            kind = 'youtube'
        expected = {
            'youtube': {f'youtube-search-{i}'},
            'web': {f'supplement-web-{i}'},
            'official_listing': {f'listing-page-{i}'},
        }.get(kind)
        if not expected or not expected <= ledger.keys() or row.get('blocked_host') or row['status'] == 'policy_blocked':
            return None
        if kind == 'youtube':
            requests = [f'youtube-search-{i}']
            if f'youtube-videos-{i}' in ledger:
                requests.append(f'youtube-videos-{i}')
            if [entry['request_hash'] for entry in row['requests']] != [
                    ledger[name]['reservation']['payload_sha256'] for name in requests]:
                return None
            expected.update(requests)
        if kind == 'web' and ledger[f'supplement-web-{i}']['reservation']['payload_sha256'] != digest(row['option']):
            return None
        if kind == 'official_listing':
            requests = [entry for entry in row['requests'] if entry['kind'] == 'page']
            if len(requests) != 1 or ledger[f'listing-page-{i}']['reservation']['payload_sha256'] != digest(
                    dict(method='GET',url=requests[0]['url'])):
                return None
        selection = f'research-{selections[offset]}'
        selected = linked_attempt(source, selection, ledger[selection]) if selection in ledger else None
        if (not selected or selected['status'] != 'completed'
                or selected['response_hash'] != digest(dict(tool=kind, option=row['query'] if kind == 'youtube' else row['option']))):
            return None
        collection_units.update(expected)
        observations.append(row)
    if any(row['tool'] == 'official_listing' for row in observations[start:]):
        collection_units.add('listing-robots')
    if collection_units != {name for name in ledger if not name.startswith('research-')}:
        return None
    if stage == 'selection' and selections.index(index) != len(observations) - start:
        return None
    result = source.read('research-result.json')
    stop = source.read('supplement-collection-stop.json')
    if stage == 'review':
        if not result or result['observations'] != prior['staff']['observations'] + observations:
            return None
        if inherited and inherited['result']:
            if result != inherited['result']:
                return None
        else:
            staff = f'research-{report_index}'
            completed = linked_attempt(source, staff, ledger[staff]) if staff in ledger else None
            claims = [{**claim,'citations':[ref['source'] for ref in claim['citations']]}
                      for claim in result['claims']]
            existing = dict(tool='finish',option='',claims=claims,feasibility=result['feasibility'])
            if not completed or completed['status'] != 'completed' or completed['response_hash'] != digest(existing):
                return None
    elif result:
        return None
    if stage != 'selection' and (not stop or stop['observations_sha256'] != digest(prior['staff']['observations'] + observations)):
        return None
    return dict(stage=stage, plan=plan, observations=observations, result=result,
                stop=stop and stop['reason'], corrections=corrections, policy_sha256=digest(policy), ledger_sha256=digest(ledger), **rejection)


def proposal(source, child, prior, credential, receipt):
    check_ancestors(source, credential)
    state = checkpoint(source, prior)
    require(state and digest(state) == receipt['checkpoint_sha256'], 'research_continuation_blocked')
    policy, units = remaining_delegation(source, credential, source.attempts())
    original = policy['proposal']
    steps = original.get('resume_original_steps', original['limits']['collection_actions'])
    units = [unit for unit in units if unit['id'] != f'research-{steps+3}']
    models = [unit for unit in units if unit['id'].startswith('research-')]
    reserved_for_delivery = 1 if state['stage'] == 'review' else 2
    require(len(models) >= reserved_for_delivery + (state['stage'] == 'selection'), 'owner_policy_exhausted')
    collected = len(list(source.root.glob('observation-*.json')))
    available_actions = original['limits']['collection_actions'] - collected
    actions = min(available_actions, len(models) - reserved_for_delivery) if state['stage'] == 'selection' else 0
    require(state['stage'] != 'selection' or actions > 0, 'owner_policy_exhausted')
    slots = {str(i) for i in range(len(state['observations']),len(state['observations'])+actions)}
    units = [unit for unit in units if unit['id'].startswith('research-')
             or unit['id'].rsplit('-',1)[-1] in slots
             or (slots and unit['id'] == 'listing-robots')]
    limits = dict(original['limits'], gemini=len(models), collection_actions=actions)
    for field, prefix in (('youtube_search', 'youtube-search-'), ('youtube_details', 'youtube-videos-'),
                          ('tavily', 'supplement-web-'), ('official_listing', 'listing-page-'), ('robots', 'listing-robots')):
        limits[field] = sum(unit['id'].startswith(prefix) for unit in units)
    return state, policy, {**original, 'binding': child.binding, 'units': units, 'limits': limits,
                           'resume_checkpoint_sha256': receipt['checkpoint_sha256'], 'resume_original_steps': steps,
                           'resume_source_input_sha256': source.binding['input_sha256']}


def status(source, child, prior, credential, receipt):
    try:
        _, policy, offer = proposal(source, child, prior, credential, receipt)
        return dict(state='available', limits=offer['limits'], expires_at=policy['expires_at'])
    except CompanyError as exc:
        return dict(state='blocked', reason=exc.code)
