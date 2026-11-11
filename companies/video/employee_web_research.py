"""Employee-selected YouTube public searches, using the project's signed grant and ledger."""
from datetime import datetime, timedelta
import json
import re
from urllib.parse import urlencode
from urllib.request import Request

from autonomous_company import CompanyError, digest, exact, now, require, text
from goal_dialogue_live import send_once

TOOL = 'youtube_public_research_v1'
POLICY = dict(tool=TOOL, provider='youtube_data_api_v3', max_requests=8, max_searches=4,
    max_cost_usd=0, automatic_retry=False, fallback=False, max_response_bytes=1000000,
    api_metadata_retention_days=30, shorts_classification='unverified')
ENDPOINT = 'https://www.googleapis.com/youtube/v3/'


def validate_queries(value):
    exact(value, ('tool', 'queries'))
    require(value['tool'] == TOOL and isinstance(value['queries'], list) and 1 <= len(value['queries']) <= 4,
            'invalid_employee_search_request')
    for query in value['queries']:
        exact(query, ('query', 'purpose', 'lookback_days', 'order'))
        text(query['query'], 200)
        require(query['purpose'] in ('game_interest', 'shorts_examples')
                and type(query['lookback_days']) is int and 1 <= query['lookback_days'] <= 30
                and query['order'] in ('relevance', 'date', 'viewCount'), 'invalid_employee_search_request')
    return value


def _seconds(duration):
    match = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration or '')
    require(match is not None and any(match.groups()), 'invalid_youtube_duration')
    hours, minutes, seconds = (int(item or 0) for item in match.groups())
    return hours*3600 + minutes*60 + seconds


def _timestamp(value):
    require(isinstance(value, str) and len(value) <= 40, 'invalid_youtube_date')
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise CompanyError('invalid_youtube_date') from None
    require(date.utcoffset() is not None, 'invalid_youtube_date')
    return date


def collect(store, project, task_id, request, key, authorize, *, provenance=None):
    """One employee tool batch. Every GET is consumed before transport; never replay it."""
    validate_queries(request)
    require(isinstance(key,str) and len(key)>=16 and key.isascii()
            and key not in json.dumps(request,ensure_ascii=False), 'invalid_employee_web_key')
    authorize()
    require('employee_web' not in project, 'employee_web_already_consumed')
    state = dict(policy=POLICY, employee_task=task_id,
                 provenance=provenance or ('offline_fixture' if project['simulation'] else 'employee_requested_api'),
                 input=request, input_hash=digest(request),
                 at=now(), status='reserved', attempts=[], observations=[])
    project['employee_web'] = state
    store.save(project)

    def get(resource, params):
        authorize()
        require(len(state['attempts']) < POLICY['max_requests'], 'employee_web_limit')
        url = ENDPOINT + resource + '?' + urlencode(params)
        require(key not in url, 'secret_in_web_request')
        entry = dict(method='GET', url=url, request_hash=digest(dict(resource=resource, params=params)),
                     at=now(), status='reserved', cost_usd=0, quota_bucket='search' if resource=='search' else 'general',
                     quota_units=1)
        state['attempts'].append(entry)
        store.save(project)
        try:
            req = Request(url, headers={'x-goog-api-key':key, 'Accept':'application/json'}, method='GET')
            with send_once(req, 30) as response:
                entry['http_status'] = response.status
                require(response.status == 200, 'employee_web_http_error')
                raw = response.read(POLICY['max_response_bytes']+1)
            require(len(raw) <= POLICY['max_response_bytes'], 'employee_web_response_limit')
            require(key.encode() not in raw, 'secret_in_web_response')
            data = json.loads(raw)
            require(isinstance(data, dict) and isinstance(data.get('items'), list)
                    and len(data['items']) <= 10 and 'error' not in data, 'employee_web_invalid_response')
        except Exception as exc:
            entry.update(status='failed', finished_at=now())
            if hasattr(exc, 'code') and type(exc.code) is int:
                entry['http_status'] = exc.code
            if hasattr(exc, 'close'):
                exc.close()
            state['status'] = 'failed_or_uncertain'
            store.save(project)
            raise CompanyError('employee_web_failed_no_retry') from None
        entry.update(status='completed', response_sha256=digest(data), finished_at=now())
        store.save(project)
        return data, entry

    try:
        for index, query in enumerate(request['queries']):
            window_end = _timestamp(now())
            window_start = window_end - timedelta(days=query['lookback_days'])
            params = dict(part='snippet', type='video', q=query['query'], regionCode='KR',
                relevanceLanguage='ko', maxResults=5, videoCategoryId='20', order=query['order'],
                publishedAfter=window_start.isoformat(), publishedBefore=window_end.isoformat())
            if query['purpose'] == 'shorts_examples':
                params['videoDuration'] = 'short'
            search, _ = get('search', params)
            ids = [item.get('id', {}).get('videoId') for item in search['items']]
            require(all(isinstance(vid, str) and re.fullmatch(r'[A-Za-z0-9_-]{11}', vid) for vid in ids)
                    and len(set(ids)) == len(ids), 'employee_web_invalid_video_ids')
            if not ids:
                state['observations'].append(dict(id=f'q{index}', query=query, status='unverified', reason='no_results'))
                continue
            videos, entry = get('videos', dict(part='snippet,contentDetails,statistics', id=','.join(ids)))
            returned = set()
            for item in videos['items']:
                vid = item.get('id')
                require(vid in ids and vid not in returned, 'employee_web_invalid_video_ids')
                returned.add(vid)
                snippet, details, statistics = (item.get(k,{}) for k in ('snippet','contentDetails','statistics'))
                title = snippet.get('title')
                text(title, 500)
                published = snippet.get('publishedAt')
                date = _timestamp(published)
                duration = _seconds(details.get('duration'))
                views = statistics.get('viewCount')
                view_count = int(views) if isinstance(views,str) and re.fullmatch(r'\d{1,18}', views) else None
                reason = []
                if snippet.get('categoryId') != '20':
                    reason.append('not_gaming_category')
                if not window_start <= date <= window_end:
                    reason.append('outside_requested_window')
                if view_count is None:
                    reason.append('view_count_unavailable')
                if query['purpose']=='shorts_examples' and not 0 < duration <= 180:
                    reason.append('outside_short_duration')
                state['observations'].append(dict(id=f'q{index}:{vid}', query=query,
                    url='https://www.youtube.com/watch?v='+vid, source='YouTube Data API v3',
                    api_request_url=entry['url'], observed_at=entry['finished_at'], published_at=published,
                    title=title, duration_seconds=duration, view_count=view_count, region_filter='KR',
                    category_id=snippet.get('categoryId'), sample_scope='employee query top 5; KR availability, not audience location; language relevance, not proof; channel size unknown',
                    status='unverified' if reason else 'metadata_verified', limitations=reason,
                    shorts_classification='unverified', growth_rate=None, rights='unverified',
                    raw_evidence_sha256=digest(item),
                    expires_at=(window_end+timedelta(days=30)).isoformat()))
                store.save(project)
            for vid in set(ids)-returned:
                state['observations'].append(dict(id=f'q{index}:{vid}', query=query, status='unverified',
                                                  reason='metadata_unavailable'))
        state.update(status='completed', finished_at=now(), receipt_hash=digest(state['observations']))
        store.save(project)
    except Exception as exc:
        state['status'] = 'failed_or_uncertain'
        state['reason'] = exc.code if isinstance(exc,CompanyError) else 'employee_web_invalid_metadata'
        store.save(project)
        if isinstance(exc,CompanyError):
            raise
        raise CompanyError('employee_web_invalid_metadata') from None
    return state


def usable_observations(state):
    require(state and state['status']=='completed' and state['receipt_hash']==digest(state['observations']),
            'employee_web_evidence_missing')
    observations = [item for item in state['observations'] if item['status']=='metadata_verified']
    require(observations and all(_timestamp(item['expires_at']) > _timestamp(now()) for item in observations),
            'employee_web_evidence_expired_or_empty')
    return observations


def validate_selection(value, state):
    exact(value, ('game', 'selected_topic', 'duration_seconds', 'duration_reason', 'selection_reason',
                  'other_candidates_reason', 'evidence_ids', 'shorts_status', 'rights_plan'))
    for key in ('game','selected_topic','duration_reason','selection_reason','other_candidates_reason','rights_plan'):
        text(value[key], 800)
    require(type(value['duration_seconds']) is int and 4 <= value['duration_seconds'] <= 180
            and value['shorts_status']=='unverified', 'mission_invalid_duration_or_shorts_claim')
    available = {item['id']:item for item in usable_observations(state)}
    ids = value['evidence_ids']
    require(isinstance(ids,list) and ids and all(isinstance(i,str) and i in available for i in ids)
            and len(set(ids))==len(ids)
            and any(available[i]['query']['purpose']=='shorts_examples' for i in ids),
            'mission_selection_evidence_mismatch')
    return value
