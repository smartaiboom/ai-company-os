"""Compare supplied public evidence before the video workflow starts writing."""
from datetime import date, datetime, timedelta
import math
from urllib.parse import urlsplit

from autonomous_company import digest, exact, require, text

EDITORIAL_WEIGHTS = dict(audience_fit=20, hook=15, takeaway=15, visual_demo=15,
    verification=10, feasibility=10, avoids_static_repetition=5)
GROWTH_WEIGHT = 10
DIRECT_FRESH_DAYS = 14
METRICS = {
    'target_shorts': {'view_count', 'view_gain', 'view_growth_pct', 'channel_relative_multiple'},
    'general_shorts': {'view_count', 'view_gain', 'view_growth_pct', 'channel_relative_multiple', 'format_observation'},
    'search_interest': {'search_growth_pct', 'search_index'},
    'ai_usage': {'monthly_app_users', 'survey_respondents', 'survey_pct'},
    'product_capability': {'capability'},
}
SOURCE_FIELDS = ('id', 'source_url', 'source_date', 'accessed_at', 'observed_through', 'window', 'region', 'sample',
                 'evidence_scope', 'metric_kind', 'metric_value_or_null', 'topic_id', 'observation')
CANDIDATE_FIELDS = ('id', 'topic', 'title_hook', 'who_cares', 'viewer_problem', 'one_takeaway',
                    'demonstrable_action', 'available_visuals_or_missing', 'risk', 'source_ids',
                    'criteria', 'selection_reason')


def _kst(value):
    require(isinstance(value, str), 'invalid_topic_timestamp')
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        require(False, 'invalid_topic_timestamp')
    require(timestamp.utcoffset() == timedelta(hours=9), 'topic_timestamp_requires_kst')
    return timestamp


def _validate_source(source, as_of):
    exact(source, SOURCE_FIELDS)
    for key in ('id', 'source_url', 'window', 'region', 'sample', 'observation'):
        text(source[key], 1200)
    url = urlsplit(source['source_url'])
    require(url.scheme == 'https' and url.hostname and not url.username and not url.password,
            'invalid_topic_source_url')
    accessed = _kst(source['accessed_at'])
    require(accessed <= as_of, 'future_topic_source_access')
    dates = {}
    for key in ('source_date', 'observed_through'):
        value = source[key]
        if value is not None:
            require(isinstance(value, str), 'invalid_topic_source_date')
            try:
                day = date.fromisoformat(value)
            except ValueError:
                require(False, 'invalid_topic_source_date')
            require(day <= accessed.date(), 'future_topic_source_date')
            dates[key] = day
    scope, kind, value = (source[k] for k in ('evidence_scope', 'metric_kind', 'metric_value_or_null'))
    require(isinstance(scope, str) and isinstance(kind, str) and kind in METRICS.get(scope, ()),
            'topic_metric_scope_mismatch')
    qualitative = kind in ('capability', 'format_observation')
    if value is not None:
        require(not qualitative and type(value) in (int, float) and math.isfinite(value)
                and (kind in ('view_growth_pct', 'search_growth_pct') or value >= 0), 'invalid_topic_metric')
    if scope == 'target_shorts':
        text(source['topic_id'], 100)
    else:
        require(source['topic_id'] is None, 'indirect_topic_source_cannot_claim_topic')
    freshness_date = dates.get('observed_through', dates.get('source_date'))
    if scope == 'target_shorts':
        # A freshly republished report cannot make old or undated observations fresh.
        freshness_date = dates.get('observed_through')
    age = (as_of.date() - freshness_date).days if freshness_date is not None else None
    freshness = 'unknown' if age is None else ('recent' if age <= DIRECT_FRESH_DAYS else 'historical')
    return {**source, 'freshness': freshness}


def compare_topics(brief, sources, candidates, *, researched_at):
    """Rank editorial suitability; only recent measured target Shorts growth earns evidence points."""
    exact(brief, ('channel', 'audience', 'language', 'region', 'aspect', 'duration_seconds'))
    for key in ('channel', 'audience', 'language', 'region'):
        text(brief[key], 300)
    require(brief['aspect'] == '9:16' and type(brief['duration_seconds']) is int
            and 30 <= brief['duration_seconds'] <= 60, 'invalid_topic_brief')
    as_of = _kst(researched_at)
    require(isinstance(sources, list) and len(sources) <= 30, 'invalid_topic_sources')
    require(isinstance(candidates, list) and 3 <= len(candidates) <= 5, 'invalid_topic_candidate_count')
    evidence = {}
    for source in sources:
        checked = _validate_source(source, as_of)
        require(checked['id'] not in evidence, 'duplicate_topic_source')
        evidence[checked['id']] = checked

    comparisons = []
    ids, topics = set(), set()
    for candidate in candidates:
        exact(candidate, CANDIDATE_FIELDS)
        for key in CANDIDATE_FIELDS:
            if key not in ('source_ids', 'criteria'):
                text(candidate[key], 1200)
        cid, topic = candidate['id'], candidate['topic'].strip().casefold()
        require(cid not in ids and topic not in topics, 'duplicate_topic_candidate')
        ids.add(cid)
        topics.add(topic)
        refs = candidate['source_ids']
        require(isinstance(refs, list) and all(isinstance(ref, str) and ref in evidence for ref in refs)
                and len(set(refs)) == len(refs), 'unknown_topic_source')
        cited = [evidence[ref] for ref in refs]
        direct = [s for s in cited if s['evidence_scope'] == 'target_shorts']
        require(all(s['topic_id'] == cid and s['region'] == brief['region'] for s in direct),
                'topic_source_target_mismatch')
        growth = [s for s in direct if s['freshness'] == 'recent'
                  and s['metric_value_or_null'] is not None
                  and ((s['metric_kind'] in ('view_gain', 'view_growth_pct') and s['metric_value_or_null'] > 0)
                       or (s['metric_kind'] == 'channel_relative_multiple' and s['metric_value_or_null'] > 1))]
        exact(candidate['criteria'], tuple(EDITORIAL_WEIGHTS))
        score = 0
        for criterion, weight in EDITORIAL_WEIGHTS.items():
            rating = candidate['criteria'][criterion]
            exact(rating, ('score', 'reason'))
            require(type(rating['score']) is int and 0 <= rating['score'] <= 2, 'invalid_topic_rating')
            text(rating['reason'], 500)
            score += weight * rating['score'] // 2
        comparisons.append(dict(**candidate, sources=cited, editorial_score=score,
            growth_points=GROWTH_WEIGHT if growth else 0, total=score + (GROWTH_WEIGHT if growth else 0),
            direct_growth_source_ids=[s['id'] for s in growth],
            evidence_status='observed_growth' if growth else 'unverified_candidate',
            confidence='moderate' if growth else 'low', audience_appeal='unassessed'))
    comparisons.sort(key=lambda row: (-row['total'], -row['growth_points'], row['id']))
    decision = dict(brief=brief, researched_at=researched_at, comparisons=comparisons,
        evidence_snapshot=list(evidence.values()), editorial_weights=EDITORIAL_WEIGHTS, growth_weight=GROWTH_WEIGHT,
        recommended_id=comparisons[0]['id'], alternative_ids=[row['id'] for row in comparisons[1:3]],
        manager_decision='recommend_for_owner_review', owner_review_required=True,
        provenance='deterministic_comparison_of_supplied_research', publish_ready=False)
    return {**decision, 'decision_sha256': digest(decision)}


def writer_topic_handoff(decision, candidate_id):
    candidate = next((row for row in decision['comparisons'] if row['id'] == candidate_id), None)
    require(candidate is not None, 'unknown_topic_candidate')
    fields = ('topic', 'title_hook', 'who_cares', 'viewer_problem', 'one_takeaway', 'demonstrable_action',
              'available_visuals_or_missing', 'risk', 'selection_reason', 'sources', 'evidence_status', 'confidence')
    return {**{key: candidate[key] for key in fields}, 'decision_sha256': decision['decision_sha256'],
            'candidate_id': candidate_id, 'brief': decision['brief']}
