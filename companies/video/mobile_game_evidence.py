"""Conservative title attribution and independently documented mobile availability."""
from datetime import datetime, timedelta
import re
import unicodedata

from web_research import evidence_catalog

# Publisher pages establish availability of the game on mobile, never the video platform or rights.
MOBILE_GAMES={
    '마인크래프트': (('마인크래프트','minecraft'),'https://www.minecraft.net/en-us/article/what-minecraft'),
    '브롤스타즈': (('브롤스타즈','브롤 스타즈','brawl stars'),'https://supercell.com/brawlstars/en/'),
    '클래시 로얄': (('클래시 로얄','클래시로얄','clash royale'),'https://supercell.com/en/games/clashroyale/'),
    '원신': (('원신','genshin impact'),'https://genshin.hoyoverse.com/m/en/game'),
}


def normalized(value):
    return unicodedata.normalize('NFKC',value).casefold().strip()


def canonical_game(value):
    return next((name for name,(aliases,_) in MOBILE_GAMES.items() if normalized(value) in aliases),None)


def title_game(title):
    value=normalized(title)
    games=[name for name,(aliases,_) in MOBILE_GAMES.items()
           if any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',value) for alias in aliases)]
    return games[0] if len(games)==1 else None


def game_evidence(observations, at):
    deadline=datetime.fromisoformat(at)
    rows={}
    by_url={}
    for ref,row in evidence_catalog(observations).items():
        if row['scope']!='api_metric' or row['origin']!='youtube_data_api':
            continue
        try:
            observed=datetime.fromisoformat(row['observed_at'])
            published=datetime.fromisoformat(row['source_date'])
            if not (deadline-timedelta(days=30)<=observed<=deadline and
                    deadline-timedelta(days=90)<=published<=observed):
                continue
        except (ValueError,TypeError):
            continue
        game=title_game(row['title'])
        if not game or not re.fullmatch(r'https://youtu\.be/[A-Za-z0-9_-]{11}',row['url']):
            continue
        by_url.setdefault(row['url'],set()).add(game)
        rows[ref]=dict(game=game,video=row['url'],platform_source=MOBILE_GAMES[game][1],
                       relation='explicit_title',platform='mobile_available',video_platform='unverified')
    output={}
    seen=set()
    for ref,row in rows.items():
        url=row['video']
        if len(by_url[url])==1 and url not in seen:
            output[ref]=row
            seen.add(url)
    return output


def planned_queries(observations, at):
    found={row['game'] for row in game_evidence(observations,at).values()}
    # An unresolved publisher-backed game can be searched by name in multiple distinct ways.
    choices=[]
    for name, (aliases,_) in MOBILE_GAMES.items():
        if name in found:
            continue
        choices.extend([(name,f'{name} 쇼츠'),(name,f'{aliases[-1]} gameplay highlights')])
    return [*choices,(None,'모바일 게임 최신 플레이 쇼츠'),(None,'mobile game highlights'),
            (None,'모바일 신작 게임 플레이')]
