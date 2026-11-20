"""Bounded evidence gathering over the existing signed operating policy."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import http.client
import json
import re
from time import monotonic
from urllib.parse import urlsplit

from autonomous_company import CompanyError, digest, exact, now, parse, require
from decision_recovery import DecisionViolation, ProviderFailure
from goal_dialogue import safe_text
from role_json_schema import S, arr, enum, obj
from research_https import _PinnedHTTPS, _global_addresses

TAVILY='https://api.tavily.com/search'
SEARCH_FIELDS=dict(search_depth='basic',max_results=5,auto_parameters=False,include_answer=False,
                   include_raw_content=False,include_images=False)
FIELD_LIMIT=600
EVIDENCE_CONTRACT = "evidence_reference_v1"


def source_url(value):
    require(isinstance(value,str) and value.isascii() and len(value)<=900
            and all(32<ord(c)<127 for c in value) and '\\' not in value,'research_source_invalid')
    try:
        url=urlsplit(value)
    except ValueError:
        raise CompanyError('research_source_invalid') from None
    require(url.scheme=='https' and url.hostname==url.netloc and not url.fragment and not url.query
            and re.fullmatch(r'(?:[a-z0-9-]+\.)+[a-z][a-z0-9-]+',url.netloc),'research_source_invalid')
    return url


def evidence(url,title,excerpt,scope,origin=None,observed_at=None,source_date=None):
    host=source_url(url).hostname
    safe_text(title,200)
    safe_text(excerpt,FIELD_LIMIT)
    require(scope in ('search_lead','public_page','api_metric','media_metadata'),'research_source_invalid')
    if observed_at is None:
        observed_at=now()
    row = dict(url=url, title=title, excerpt=excerpt, scope=scope, origin=origin, host=host,
               observed_at=observed_at, source_date=source_date)
    fingerprint = digest(row)
    return dict(id=fingerprint[:24], sha256=fingerprint, **row)


def evidence_catalog(observations):
    catalog = {}
    for group in observations:
        for row in group['sources']:
            exact(row, ('id', 'sha256', 'url', 'title', 'excerpt', 'scope', 'origin', 'host',
                        'observed_at', 'source_date'))
            original = evidence(row['url'], row['title'], row['excerpt'], row['scope'],
                                row['origin'], row['observed_at'], row['source_date'])
            require(row == original and catalog.get(row['id'], row) == row, 'research_source_invalid')
            catalog[row['id']] = dict(row)
    return catalog


def independent_sources(sources):
    eligible = [source for source in sources if source['scope'] in ('public_page', 'api_metric')
                and source['origin']]
    return any(a['origin'] != b['origin'] and a['host'] != b['host']
               for i, a in enumerate(eligible) for b in eligible[i+1:])


def has_reviewable_claim(result):
    return any(claim['assessment'] in ('supported', 'conflicting') for claim in result['claims'])


def tavily_search(query,key):
    safe_text(query,180)
    require(isinstance(key,str) and re.fullmatch(r'[A-Za-z0-9_-]{16,200}',key),'research_search_disabled')
    raw=json.dumps(dict(query=query,**SEARCH_FIELDS),ensure_ascii=False).encode()
    require(key.encode() not in raw,'research_secret_detected')
    deadline=monotonic()+15
    host='api.tavily.com'
    family,address=_global_addresses(host,deadline)
    conn=_PinnedHTTPS(host,family,address,deadline)
    try:
        conn.request('POST','/search',body=raw,headers={'Authorization':'Bearer '+key,
            'Content-Type':'application/json','Accept':'application/json','Accept-Encoding':'identity'})
        with conn.getresponse() as response:
            if response.status != 200:
                raise ProviderFailure('research_search_failed')
            require(response.headers.get_content_type()=='application/json'
                    and response.getheader('Content-Encoding','identity')=='identity','research_search_failed')
            body=response.read(128*1024+1)
        require(len(body)<=128*1024 and key.encode() not in body and monotonic()<=deadline,'research_search_failed')
        data=parse(body.decode('utf-8'))
        require(isinstance(data,dict) and isinstance(data.get('results'),list) and len(data['results'])<=5,
                'research_search_failed')
    except (OSError,UnicodeError,http.client.HTTPException):
        raise CompanyError('research_search_failed') from None
    finally:
        conn.close()
        conn.cancel_timer()
    rows=[]
    observed_at=now()
    for row in data['results']:
        try:
            if isinstance(row,dict) and isinstance(row.get('title'),str) and isinstance(row.get('content'),str):
                rows.append(evidence(row.get('url'),row['title'][:200],row['content'][:FIELD_LIMIT],'search_lead',
                                     observed_at=observed_at))
        except CompanyError:
            continue
    return rows


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    options: dict
    read: object
    operation: dict | None = None
    requests: tuple = ()
    observe: object = None
    preserved: tuple = ()

    def describe(self,used):
        return dict(name=self.name,description=self.description,
                    options={key:value for key,value in self.options.items() if (self.name,key) not in used})


def preserved_observations(tools, *, at=None):
    """Only adapters can provide preserved rows; no tool executor is called."""
    current = datetime.fromisoformat(at or now())
    observations, notes = [], []
    for tool in tools.values():
        if not tool.preserved:
            continue
        require(not tool.operation and not tool.requests and not tool.observe, 'research_source_invalid')
        rows = list(evidence_catalog([{'sources':tool.preserved}]).values())
        selected = []
        stale = excluded = 0
        for row in rows:
            try:
                timestamp = datetime.fromisoformat(row['observed_at'])
                fresh = timedelta(0) <= current - timestamp < timedelta(days=30)
            except (ValueError, TypeError):
                fresh = False
            if row['scope'] not in ('public_page','api_metric','media_metadata'):
                excluded += 1
            elif not fresh:
                stale += 1
            elif sum(len(item['sources']) for item in observations) + len(selected) >= 12:
                excluded += 1
            else:
                selected.append(row)
        notes.append(dict(tool=tool.name, preserved=len(selected), stale=stale, excluded=excluded,
                          interpretation='Historical context. Check measurement scope, conflicts and current rights.'))
        if selected:
            observations.append(dict(tool=tool.name, option='saved', at=None, status='preserved', sources=selected))
    return observations, notes


STEP_RULES = {
    'legacy_step_invalid': 'Use one allowed tool/option or return a complete finish report.',
    'invalid_step_fields': 'Return exactly tool, option, claims and feasibility with their specified types.',
    'finish_required': 'Return finish because no tool selection remains at this step.',
    'tool_not_allowed': 'Choose a tool from the current list or finish.',
    'option_not_allowed': 'Use an unused exact option listed for the chosen tool.',
    'mixed_tool_and_report': 'For a tool choice return empty claims and empty feasibility.',
    'invalid_finish': 'For finish return an empty option, one to five claims and a feasibility statement.',
    'invalid_claim': 'Use an allowed assessment and up to four citations with the required fields.',
    'invalid_report_text': 'Supply nonblank report text within the documented lengths.',
    'invalid_citation': 'Choose each reference ID at most once from the current evidence catalog. Omit references if none apply.',
    'insufficient_independent_evidence': 'Use two independent eligible origins or mark the claim unverified.',
}


def step_schema(context, *, supervised=False):
    catalog = context['evidence_catalog']
    assessments = ('supported', 'conflicting', 'unverified') if independent_sources(list(catalog.values())) else ('unverified',)
    references = {**arr(enum(*catalog) if catalog else S), 'maxItems': min(4, len(catalog))}
    claims = arr(obj(statement=S, assessment=enum(*assessments), citations=references))
    finish = obj(tool=enum('finish'), option=enum(''), claims={**claims, 'minItems': 1, 'maxItems': 5},
                 feasibility=S)
    selections = [
        obj(tool=enum(tool['name']), option=enum(*tool['options']),
            claims={**claims, 'maxItems': 0}, feasibility=enum(''))
        for tool in context['tools']
    ]
    if supervised:
        hold = obj(tool=enum('hold'), option=enum(''), claims={**arr(obj(
            statement=S, assessment=enum('unverified'), citations=references)), 'minItems':1, 'maxItems':5},
            feasibility=S, unavailable={**arr(obj(tool=enum(*(tool['name'] for tool in context['tools']))
                if selections else S, reason=S)), 'minItems':len(selections), 'maxItems':len(selections)})
        choices = [*selections, hold]
        if len(selections) > 1:
            items = [obj(tool=enum(tool['name']), option=enum(*tool['options']), reason=S)
                     for tool in context['tools']]
            choices.append(obj(tool=enum('batch'), option=enum(''), claims={**claims,'maxItems':0},
                               feasibility=enum(''), selections={**arr({'anyOf':items}),'minItems':2,'maxItems':2}))
        if catalog or not selections:
            choices.append(finish)
        return {'anyOf': choices}
    return {'anyOf': [*selections, finish]} if selections else finish


def check_step(condition, rule, code='research_step_invalid'):
    if not condition:
        raise DecisionViolation(code, rule)


def report_text(value, limit):
    # Credential-like text stays a security rejection and is never eligible for correction.
    check_step(isinstance(value, str) and bool(value.strip()) and len(value) <= limit, 'invalid_report_text')
    safe_text(value, limit)


def validate_step(step, tools, used, observations, final=False):
    check_step(isinstance(step, dict) and set(step) == {'tool', 'option', 'claims', 'feasibility'},
               'invalid_step_fields')
    name, option = step['tool'], step['option']
    check_step(isinstance(name, str) and isinstance(option, str) and isinstance(step['claims'], list),
               'invalid_step_fields')
    if name != 'finish':
        check_step(not final, 'finish_required')
        check_step(name in tools, 'tool_not_allowed')
        check_step(option in tools[name].options and (name, option) not in used, 'option_not_allowed')
        check_step(not step['claims'] and step['feasibility'] == '', 'mixed_tool_and_report')
        return

    check_step(option == '' and 1 <= len(step['claims']) <= 5, 'invalid_finish')
    report_text(step['feasibility'], 460)
    known = evidence_catalog(observations)
    for claim in step['claims']:
        check_step(isinstance(claim, dict) and set(claim) == {'statement', 'assessment', 'citations'},
                   'invalid_claim')
        report_text(claim['statement'], 400)
        refs = claim['citations']
        check_step(claim['assessment'] in ('supported', 'conflicting', 'unverified')
                   and isinstance(refs, list) and len(refs) <= 4, 'invalid_claim')
        check_step(all(isinstance(ref, str) and ref in known for ref in refs)
                   and len(set(refs)) == len(refs), 'invalid_citation', 'research_evidence_invalid')
        if claim['assessment'] != 'unverified':
            sources = [known[ref] for ref in refs]
            check_step(independent_sources(sources)
                       and all(row['scope'] in ('public_page', 'api_metric') for row in sources),
                       'insufficient_independent_evidence', 'research_evidence_invalid')


def validate_supervised_step(step, tools, used, observations, final):
    if isinstance(step, dict) and step.get('tool') == 'batch':
        check_step(set(step) == {'tool','option','claims','feasibility','selections'} and step['option'] == ''
                   and step['claims'] == [] and step['feasibility'] == '', 'invalid_tool_batch')
        selections = step['selections']
        check_step(not final and isinstance(selections, list) and len(selections) == 2, 'invalid_tool_batch')
        names = set()
        for item in selections:
            check_step(isinstance(item, dict) and set(item) == {'tool','option','reason'}, 'invalid_tool_batch')
            report_text(item['reason'], 300)
            validate_step(dict(tool=item['tool'], option=item['option'], claims=[], feasibility=''),
                          tools, used, observations, final)
            check_step(item['tool'] not in names, 'invalid_tool_batch')
            names.add(item['tool'])
        # Two pages share a host policy check. Keep that dependency in separate decisions.
        check_step(sum(bool(tools[name].requests) for name in names) <= 1, 'batch_dependency')
        return
    if isinstance(step, dict) and step.get('tool') == 'hold':
        check_step('unavailable' in step, 'missing_hold_reason')
        reasons = step['unavailable']
        available = [tool.describe(used) for tool in tools.values()]
        names = {tool['name'] for tool in available}
        check_step(isinstance(reasons, list) and len(reasons) == len(names), 'missing_hold_reason')
        remaining = names.copy()
        for reason in reasons:
            check_step(isinstance(reason, dict) and set(reason) == {'tool', 'reason'}
                       and isinstance(reason['tool'], str) and reason['tool'] in remaining, 'missing_hold_reason')
            report_text(reason['reason'], 300)
            remaining.remove(reason['tool'])
        payload = {key:value for key,value in step.items() if key != 'unavailable'}
        payload['tool'] = 'finish'
        validate_step(payload, tools, used, observations, final)
        check_step(all(claim['assessment'] == 'unverified' for claim in step['claims']), 'invalid_finish')
        return
    if isinstance(step, dict) and step.get('tool') == 'finish':
        check_step(final or bool(evidence_catalog(observations)), 'early_goal_finish')
    validate_step(step, tools, used, observations, final)


def step_context(tools, observations, final):
    used = {(row['tool'], row['option']) for row in observations}
    remaining = {}
    choices = []
    for tool in tools.values():
        if final or (tool.operation and any(name == tool.name for name, _ in used)):
            continue
        choice = tool.describe(used)
        if choice['options']:
            choices.append(choice)
            remaining[tool.name] = tool
    return (dict(tools=choices, observations=observations, evidence_catalog=evidence_catalog(observations),
                 finish_required=not choices),
            (remaining, used, observations, not choices))


def research_report(step, observations):
    catalog = evidence_catalog(observations)
    claims = [{**claim, 'citations': [
        dict(source=ref, quote=catalog[ref]['excerpt']) for ref in claim['citations']
    ]} for claim in step['claims']]
    return dict(at=now(), claims=claims, feasibility=step['feasibility'], observations=list(observations),
                evidence_contract=EVIDENCE_CONTRACT, evidence_catalog_sha256=digest(catalog),
                status='manager_review', publish_allowed=False)


def collect_observation(tool, option, invoke):
    if tool.observe:
        result = tool.observe(option, invoke)
        require(isinstance(result['sources'], list) and len(result['sources']) <= 8
                and result['status'] in ('observed','empty','unavailable','policy_blocked'),
                'research_source_invalid')
        evidence_catalog([result])
        return {**result, 'tool':tool.name, 'option':option, 'at':now()}
    output = []

    def collect(check):
        check()
        rows = tool.read(option)
        require(isinstance(rows, list) and len(rows) <= 8, 'research_source_invalid')
        evidence_catalog([{'sources': rows}])
        output.extend(rows)

    if tool.operation:
        invoke(tool.operation, digest(dict(tool=tool.name, option=option, value=tool.options[option])), collect)
    else:
        collect(lambda: None)
    return dict(tool=tool.name, option=option, at=now(), status='observed' if output else 'empty', sources=output)


def run(store, tools, decide, invoke, rounds, *, history=()):
    """Continue from verified observations supplied by the domain adapter."""
    observations = list(history)
    for index in range(len(observations), rounds):
        context, runtime = step_context(tools, observations, index == rounds - 1)
        step = decide(index, context)
        validate_step(step, *runtime)
        if step['tool'] == 'finish':
            result = research_report(step, observations)
            store.write('research-result.json', result)
            return result
        record = collect_observation(tools[step['tool']], step['option'], invoke)
        store.write(f'observation-{index}.json', record)
        observations.append(record)
    raise CompanyError('research_step_invalid')
