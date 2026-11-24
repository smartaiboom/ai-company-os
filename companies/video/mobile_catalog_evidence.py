"""Read a directly observed App Store game listing and link it to video title evidence."""
from collections import defaultdict
from datetime import datetime, timedelta
from html.parser import HTMLParser
import json
import re

from autonomous_company import CompanyError, digest
from commons_discovery import USER_AGENT
from goal_dialogue import safe_text
from mobile_game_evidence import canonical_game, game_evidence, normalized
from research_https import _PinnedHTTPS, _global_addresses, fetch_public_text, observe_approved_page
from web_research import evidence, evidence_catalog, source_url

HOST='apps.apple.com'
APP_PATH=re.compile(r'/[a-z]{2}/app/(?:[a-zA-Z0-9-]+/)?id(\d{6,15})')
ORIGIN='apple_app_store'


def listing_id(url):
    try:
        parsed=source_url(url)
    except (CompanyError,ValueError):
        return None
    match=APP_PATH.fullmatch(parsed.path)
    return match[1] if parsed.hostname==HOST and match else None


class ListingMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.structured=False
        self.parts=[]
        self.records=[]

    def handle_starttag(self, tag, attrs):
        if tag=='script':
            self.structured=dict(attrs).get('type')=='application/ld+json'
            self.parts=[]

    def handle_data(self, data):
        if self.structured:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag=='script' and self.structured:
            self.structured=False
            try:
                self.records.append(json.loads(''.join(self.parts)))
            except (ValueError,RecursionError):
                pass


def listing(url,body):
    parser=ListingMetadata()
    parser.feed(body)
    matches=set()
    for record in parser.records:
        if not isinstance(record,dict) or record.get('@type')!='SoftwareApplication':
            continue
        canonical=record.get('url')
        category=record.get('applicationCategory')
        platform=record.get('operatingSystem')
        name=record.get('name')
        if not all(isinstance(value,str) for value in (canonical,category,platform,name)):
            continue
        if (listing_id(canonical)!=listing_id(url) or category.casefold() not in ('game','gameapplication','games')
                or not re.search(r'\b(?:iOS|iPadOS)\b',platform,re.I)):
            continue
        try:
            safe_text(name,100)
        except CompanyError:
            continue
        matches.add(name.strip())
    if len(matches)!=1:
        return dict(status='empty',sources=[],reason='mobile_listing_unverified')
    name=matches.pop()
    return dict(status='observed',sources=[evidence(url,name,'App Store game listing with iOS or iPadOS support.',
                                                 'public_page',ORIGIN)])


def read_listing(url,robots_operation,page_operation,invoke,cache):
    def entry(target, kind, operation):
        return dict(url=target,host=HOST,path=source_url(target).path,kind=kind,
                    operation={**operation,'payload_sha256':digest(dict(method='GET',url=target))})

    def fetch(target,kind):
        return fetch_public_text(source_url(target),kind,agent=USER_AGENT,connect=_PinnedHTTPS,
                                 resolve=_global_addresses,page_limit=768*1024)

    return observe_approved_page(entry(url,'page',page_operation),
                                 entry('https://'+HOST+'/robots.txt','robots',robots_operation),
                                 invoke,fetch,listing,cache)


def verified_games(observations,at,preserved):
    """Give each recent video at most one game identity, with its independent mobile evidence."""
    catalog=evidence_catalog(observations)
    base=game_evidence(observations,at)
    deadline=datetime.fromisoformat(at)
    apps=defaultdict(list)
    for ref,row in catalog.items():
        if row['scope']=='public_page' and row['origin']==ORIGIN and listing_id(row['url']):
            when=datetime.fromisoformat(row['observed_at'])
            if deadline-timedelta(days=30)<=when<=deadline:
                apps[listing_id(row['url'])].append((ref,row))
    listings=defaultdict(list)
    for pages in apps.values():
        names={canonical_game(page['title']) for _,page in pages} - {None}
        if len(names)<=1:
            game=next(iter(names)) if names else normalized(pages[0][1]['title'])
            if game:
                listings[game].extend(pages)
    candidates=defaultdict(dict)
    for ref,row in base.items():
        if preserved.get(ref)==row:
            candidates[row['video']][row['game']]=(ref,row)
    for ref,row in catalog.items():
        if row['scope']!='api_metric' or row['origin']!='youtube_data_api':
            continue
        try:
            observed=datetime.fromisoformat(row['observed_at'])
            published=datetime.fromisoformat(row['source_date'])
        except (TypeError,ValueError):
            continue
        if (not deadline-timedelta(days=90)<=published<=observed<=deadline
                or observed<deadline-timedelta(days=30) or not re.fullmatch(r'https://youtu\.be/[A-Za-z0-9_-]{11}',row['url'])):
            continue
        title=normalized(row['title'])
        for game,pages in listings.items():
            ids={listing_id(page['url']) for _,page in pages}
            if len(ids)!=1:
                continue
            if not any(re.search(r'(?<!\w)'+re.escape(normalized(page['title']))+r'(?!\w)',title) for _,page in pages):
                continue
            page_ref,page=pages[0]
            if game not in candidates[row['url']]:
                candidates[row['url']][game]=(ref,dict(game=game,video=row['url'],platform_source=page['url'],
                    platform_source_id=page_ref,relation='explicit_title',platform='mobile_available',video_platform='unverified'))
    return dict(next(iter(games.values())) for games in candidates.values() if len(games)==1)
