"""Reviewed public observations for the representative's game Shorts mission."""
from autonomous_company import exact, require, text

GAME_GOAL = '요즘 인기있는 게임에 대한 흥미있는 쇼츠 영상을 만들어봐. 기본적으로 인기있는 쇼츠는 몇초인지도 확인해보고.'
GAME_SCOPE = 'game_shorts_20261111'
DURATION_RANGE = (15, 60)


def _source(kind, url, observed_at, claim, limits, *, game=None):
    return dict(kind=kind, url=url, observed_at=observed_at, claim=claim, limits=limits, game=game)


def _steam(game, rank, current, peak):
    return _source('steam_players', 'https://store.steampowered.com/charts/mostplayed',
        '2026-11-11 10:58 KST 전후 열람 스냅샷', f'{game}: 현재 접속 기준 {rank}위, 동시 접속 {current:,}명, 오늘 최대 {peak:,}명.',
        'Steam 글로벌 PC 스냅샷. 한국 시청자, YouTube Shorts 조회·성장, 게임의 전체 플랫폼 규모 미검증.',
        game=game)


GAME_EVIDENCE = {
    'steam-cs2': _steam('Counter-Strike 2', 1, 431002, 1071403),
    'steam-dota2': _steam('Dota 2', 2, 330979, 712193),
    'steam-pubg': _steam('PUBG: BATTLEGROUNDS', 8, 100738, 732614),
    'korea-length': _source('length_distribution', 'https://serastudio.app/insights/shorts-length',
        '2026-10-29 원자료 확인일, 2026-11-11 KST 열람',
        '한국 인기 차트의 한국어 쇼츠 4,452편, 중앙값 43초, 60초 이하 71.7%.',
        '여러 카테고리의 차트 진입 영상. 게임 전용 표본도, 길이 효과의 인과 검증도 아님.'),
    'gaming-length': _source('length_distribution', 'https://www.opus.pro/research/best-time-gaming-youtube',
        '2026-04-02 발행, 2026-11-11 KST 열람',
        'YouTube 게임 클립 241,353편에서 15~30초 40.5%, 30~60초 37.2%.',
        '게임 클립의 길이 분포. 고성과 쇼츠 한정 표본, 한국 시청자 또는 조회수 효과는 미검증.'),
    'youtube-rule': _source('platform_rule', 'https://support.google.com/youtube/answer/15424877?hl=en',
        '2026-11-11 KST 열람', '해당 요건의 세로 또는 정사각형 영상은 최대 3분까지 Shorts 분류 가능.',
        '플랫폼 규정이며 권장 길이나 인기 지표가 아님.'),
}


def validate_game_research(value, evidence):
    exact(value, ('candidates', 'uncertainty'))
    text(value['uncertainty'], 800)
    candidates = value['candidates']
    require(isinstance(candidates, list) and 2 <= len(candidates) <= 4, 'mission_research_candidates')
    games, topics = set(), set()
    for candidate in candidates:
        exact(candidate, ('game', 'topic', 'rationale', 'player_evidence_id', 'shorts_evidence_status', 'rights_plan'))
        for key in ('game', 'topic', 'rationale', 'player_evidence_id', 'rights_plan'):
            text(candidate[key], 500)
        source = evidence.get(candidate['player_evidence_id'], {})
        require(source.get('kind') == 'steam_players' and source['game'] == candidate['game']
                and candidate['shorts_evidence_status'] == 'unverified', 'mission_game_evidence_mismatch')
        require(candidate['game'] not in games and candidate['topic'] not in topics, 'mission_research_candidates')
        games.add(candidate['game'])
        topics.add(candidate['topic'])
    return value


def validate_game_decision(value, research, evidence):
    exact(value, ('selected_topic', 'duration_seconds', 'duration_reason', 'selection_reason',
                  'other_candidates_reason', 'considered_durations', 'duration_evidence_ids'))
    for key in ('selected_topic', 'duration_reason', 'selection_reason', 'other_candidates_reason'):
        text(value[key], 800)
    require(any(c['topic'] == value['selected_topic'] for c in research['candidates']), 'mission_research_selection')
    choices = value['considered_durations']
    require(isinstance(choices, list) and 2 <= len(choices) <= 4 and
            all(type(seconds) is int and DURATION_RANGE[0] <= seconds <= DURATION_RANGE[1] for seconds in choices)
            and len(set(choices)) == len(choices)
            and type(value['duration_seconds']) is int and value['duration_seconds'] in choices,
            'mission_invalid_duration_decision')
    ids = value['duration_evidence_ids']
    require(isinstance(ids, list) and len(ids) >= 2 and
            all(isinstance(key, str) and evidence.get(key, {}).get('kind') == 'length_distribution' for key in ids)
            and len(set(ids)) == len(ids), 'mission_duration_evidence_mismatch')
    return value
