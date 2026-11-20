"""Evaluate observed leads and construct exact public HTML access plans."""
import re

from autonomous_company import digest, require
from production_operating import unit
from web_research import evidence_catalog, source_url


def exact_page(url):
    parsed = source_url(url)
    require(parsed.geturl() == url and re.fullmatch(r'/[A-Za-z0-9._/-]+', parsed.path)
            and '//' not in parsed.path and not {'.', '..'}.intersection(parsed.path.split('/')),
            'publisher_url_blocked')
    return parsed


def access_entry(url, kind):
    parsed = exact_page(url)
    require((kind == 'robots') == (parsed.path == '/robots.txt'), 'publisher_url_blocked')
    return dict(url=url, kind=kind, host=parsed.hostname, path=parsed.path,
                operation=unit('official-get:'+digest(url)[:20], 'bounded_https_get', url,
                               ['public_url_path'], payload_sha256=digest(dict(method='GET', url=url))))


def candidate_plans(observations, approved):
    """Only an exact owner-approved registry entry can produce a request plan."""
    plans = []
    catalog = evidence_catalog(observations)
    leads = {}
    for ref, row in catalog.items():
        if row['scope'] == 'search_lead':
            leads.setdefault(row['url'], []).append(ref)
    attempted = {request['url'] for row in observations for request in row.get('requests', [])}
    blocked = {row['blocked_host'] for row in observations if row.get('blocked_host')}
    for url in dict.fromkeys([*approved, *leads]):
        entry = dict(url=url, lead_refs=leads.get(url, []), authority='unconfirmed',
                     access='not_approved', rights='unconfirmed')
        if url in approved:
            page = access_entry(url, 'page')
            entry.update(approved[url])
            robots = access_entry('https://'+page['host']+'/robots.txt', 'robots')
            if page['host'] in blocked or url in attempted or robots['url'] in attempted:
                entry['access'] = 'previously_attempted'
            else:
                entry.update(access='robots_pending', page=page, robots=robots,
                             maximum_requests=2, transmission=['public_url_path'])
        plans.append(entry)
    return plans
