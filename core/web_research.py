"""Bounded evidence gathering over the existing signed operating policy."""
from dataclasses import dataclass
import http.client
import json
import re
from time import monotonic
from urllib.parse import urlsplit

from autonomous_company import CompanyError, digest, exact, now, parse, require
from goal_dialogue import safe_text
from research_https import _PinnedHTTPS, _global_addresses

TAVILY='https://api.tavily.com/search'
SEARCH_FIELDS=dict(search_depth='basic',max_results=5,auto_parameters=False,include_answer=False,
                   include_raw_content=False,include_images=False)
FIELD_LIMIT=600


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
    return dict(id=digest([url,excerpt,scope,observed_at])[:24],url=url,title=title,excerpt=excerpt,scope=scope,
                origin=origin,host=host,observed_at=observed_at,source_date=source_date)


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
            require(response.status==200 and response.headers.get_content_type()=='application/json'
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

    def describe(self,used):
        return dict(name=self.name,description=self.description,
                    options={key:value for key,value in self.options.items() if (self.name,key) not in used})


def validate_step(step,tools,used,observations,final=False):
    exact(step,('tool','option','claims','feasibility'))
    name,option=step['tool'],step['option']
    require(isinstance(name,str) and isinstance(option,str) and isinstance(step['claims'],list)
            and len(step['claims'])<=5,'research_step_invalid')
    if name=='finish':
        require(option=='' and step['claims'],'research_step_invalid')
        safe_text(step['feasibility'],460)
        known={row['id']:row for group in observations for row in group['sources']}
        for claim in step['claims']:
            exact(claim,('statement','assessment','citations'))
            safe_text(claim['statement'],400)
            require(claim['assessment'] in ('supported','conflicting','unverified')
                    and isinstance(claim['citations'],list) and len(claim['citations'])<=4,'research_step_invalid')
            seen=set()
            for ref in claim['citations']:
                exact(ref,('source','quote'))
                safe_text(ref['quote'],200)
                require(isinstance(ref['source'],str) and ref['source'] in known and ref['source'] not in seen
                        and ref['quote'] in known[ref['source']]['excerpt'],'research_evidence_invalid')
                seen.add(ref['source'])
            if claim['assessment']!='unverified':
                sources=[known[row['source']] for row in claim['citations']]
                origins={row['origin'] for row in sources if row['origin']}
                require(len(origins)>=2 and len({row['host'] for row in sources if row['origin']})>=2
                        and all(row['scope'] in ('public_page','api_metric') for row in sources),
                        'research_evidence_invalid')
        return
    require(not final and name in tools and option in tools[name].options and (name,option) not in used
            and not step['claims'] and step['feasibility']=='','research_step_invalid')


def run(store, tools, decide, invoke, rounds):
    """Use one consumed operation per new observation. The caller supplies the signed executor."""
    observations=[]
    used=set()
    for index in range(rounds):
        final=index==rounds-1
        remaining={tool.name:tool for tool in tools.values()
                   if not final and (not tool.operation or not any(name==tool.name for name,_ in used))}
        context=dict(tools=[tool.describe(used) for tool in remaining.values()],observations=observations,
                     finish_required=final)
        step=decide(index,context)
        validate_step(step,remaining,used,observations,final)
        if step['tool']=='finish':
            result=dict(at=now(),claims=step['claims'],feasibility=step['feasibility'],observations=observations,
                        status='manager_review',publish_allowed=False)
            store.write('research-result.json',result)
            return result
        tool=remaining[step['tool']]
        option=step['option']
        used.add((tool.name,option))
        output=[]
        def collect(check):
            check()
            rows=tool.read(option)
            require(isinstance(rows,list) and len(rows)<=8,'research_source_invalid')
            output.extend(rows)
        if tool.operation:
            invoke(tool.operation,digest(dict(tool=tool.name,option=option,value=tool.options[option])),collect)
        else:
            collect(lambda:None)
        record=dict(tool=tool.name,option=option,at=now(),status='observed' if output else 'empty',sources=output)
        store.write(f'observation-{index}.json',record)
        observations.append(record)
    raise CompanyError('research_step_invalid')
