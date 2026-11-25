"""Read a directly observed App Store game listing and link it to video title evidence."""
from collections import defaultdict
from datetime import datetime, timedelta
from html.parser import HTMLParser
import json
import re

from autonomous_company import CompanyError, digest, require
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
        self.canonical=[]
        self.malformed=False

    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='link' and 'canonical' in (attrs.get('rel') or '').lower().split():
            self.canonical.append(attrs.get('href'))
        if tag=='script':
            self.structured=(attrs.get('type') or '').split(';',1)[0].strip().lower()=='application/ld+json'
            self.parts=[]

    def handle_data(self, data):
        if self.structured:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag=='script' and self.structured:
            self.structured=False
            try:
                self.records.append(json.loads(''.join(self.parts),object_pairs_hook=unique_fields))
            except (ValueError,RecursionError):
                self.malformed=True


def unique_fields(pairs):
    node=dict(pairs)
    if len(node)!=len(pairs):
        raise ValueError('duplicate JSON-LD field')
    return node


def graph_nodes(records):
    stack=list(reversed(records))
    while stack:
        node=stack.pop()
        if isinstance(node,list):
            stack.extend(reversed(node))
        elif isinstance(node,dict):
            yield node
            if isinstance(node.get('@graph'),(dict,list)):
                stack.append(node['@graph'])


def values(value):
    return value if isinstance(value,list) else [value]


def terms(value):
    for text in values(value):
        if isinstance(text,str):
            yield re.sub(r'^https?://schema\.org/', '', text.strip(), flags=re.I).casefold()


def listing(url,body):
    def unavailable(reason):
        return dict(status='empty',sources=[],reason=reason,
                    extraction=dict(method='app_store_json_ld_v2',status='unverified',reason=reason))

    app_id=listing_id(url)
    if not app_id:
        return unavailable('listing_url_not_allowed')
    parser=ListingMetadata()
    parser.feed(body)
    parser.close()
    if any(not isinstance(item,str) or listing_id(item)!=app_id for item in parser.canonical):
        return unavailable('listing_identity_conflict')
    if parser.malformed:
        return unavailable('listing_json_ld_invalid')
    matched=[]
    for record in graph_nodes(parser.records):
        types=set(terms(record.get('@type')))
        if not types & {'softwareapplication','mobileapplication','videogame','gameapplication'}:
            continue
        identities=[]
        for field in ('url','@id'):
            for value in values(record.get(field)):
                if not isinstance(value,str):
                    continue
                if field=='@id' and re.fullmatch(r'[0-9]{6,15}',value):
                    identities.append(value)
                elif field=='url' or value.startswith(('https://','http://')):
                    identities.append(listing_id(value))
        if app_id in identities:
            if set(identities)!={app_id}:
                return unavailable('listing_identity_conflict')
            matched.append((record,types))
    if not matched:
        return unavailable('listing_app_node_unverified')
    names=set()
    categories=set()
    platforms=set()
    valid=[]
    for record,types in matched:
        try:
            name=record.get('name')
            safe_text(name,100)
            name=name.strip()
            names.add(normalized(name))
        except CompanyError:
            name=None
        category=set(terms(record.get('applicationCategory')))
        typed_game=bool(types & {'videogame','gameapplication'})
        category_game=bool(category & {'game','games','gameapplication','videogame'})
        if typed_game and category and not category_game:
            return unavailable('listing_metadata_conflict')
        game=typed_game or category_game
        if category or game:
            categories.add(game)
        os_values=[]
        for item in values(record.get('operatingSystem')):
            if isinstance(item,dict) and 'operatingsystem' in set(terms(item.get('@type'))):
                item=item.get('name')
            if isinstance(item,str):
                os_values.extend(item.split(','))
        mobile={match[1].lower() for text in os_values if (match:=re.fullmatch(
            r'\s*(?:Requires\s+)?(iOS|iPadOS)(?:\s+[0-9]+(?:\.[0-9]+)*\s*(?:or later|and later|\+)?)?\.?\s*',
            text,re.I))}
        if os_values:
            platforms.add(bool(mobile))
        if name and game and mobile:
            valid.append((name,mobile))
    if len(names)>1 or len(categories)>1 or len(platforms)>1:
        return unavailable('listing_metadata_conflict')
    if not valid:
        return unavailable('listing_name_unverified' if not names else
                           'listing_game_category_unverified' if True not in categories else
                           'listing_mobile_platform_unverified' if True not in platforms else
                           'listing_evidence_incomplete')
    name=valid[0][0]
    labels=sorted({{'ios':'iOS','ipados':'iPadOS'}[item] for _,mobile in valid for item in mobile})
    return dict(status='observed',extraction=dict(method='app_store_json_ld_v2',status='verified',
                app_id=app_id,platforms=labels),sources=[evidence(url,name,
                    f"App Store structured game listing explicitly lists {', '.join(labels)}.",
                    'public_page',ORIGIN)])


def read_listing(url,robots_operation,page_operation,invoke,cache):
    require(listing_id(url),'research_evidence_invalid')

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
    aliases=defaultdict(set)
    for app_id,pages in apps.items():
        for _,page in pages:
            aliases[normalized(page['title'])].add(app_id)
    for pages in apps.values():
        storefronts=defaultdict(set)
        for _,page in pages:
            storefronts[source_url(page['url']).path.split('/')[1]].add(normalized(page['title']))
        if any(len(names)>1 for names in storefronts.values()):
            continue
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
            if not any(len(aliases[alias])==1 and re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',title)
                       for _,page in pages if (alias:=normalized(page['title']))):
                continue
            page_ref,page=pages[0]
            if game not in candidates[row['url']]:
                candidates[row['url']][game]=(ref,dict(game=game,video=row['url'],platform_source=page['url'],
                    platform_source_id=page_ref,relation='explicit_title',platform='mobile_available',video_platform='unverified'))
    return dict(next(iter(games.values())) for games in candidates.values() if len(games)==1)
