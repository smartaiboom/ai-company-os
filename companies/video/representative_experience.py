"""Version-linked preferences in the representative project's existing experience journal."""
from collections import defaultdict
from copy import deepcopy

from autonomous_company import digest, exact, require
from goal_dialogue import safe_text
from quality_feedback import append_experience, select_experiences, withdraw_experience

CATEGORIES = ('tone', 'captions')
SOURCE = 'representative_comparison_v1'
ACTIONS = ('experience-save', 'experience-withdraw')


def work_scope(flow):
    constraints = flow['constraints']
    handoff = flow.get('research_handoff', {})
    return dict(language=constraints.get('language', ''), platform=constraints.get('platform', ''),
                aspect=constraints.get('aspect', '9:16'),
                duration_seconds=handoff.get('duration_seconds', constraints.get('duration_seconds')))


def _classification(report):
    return report.get('provenance') == 'provider_model_claim'


def comparison(flow, stage, current):
    plans = {row['sha256']: row for row in flow['plan_versions']}
    reports = {row['sha256']: row for row in flow[f'{stage}_versions']}
    key = f'previous_{stage}_sha256'
    before = reports.get(current.get(key))
    if not before or (stage == 'video' and before['artifact_sha256'] == current['artifact_sha256']):
        return None
    requests = {row['sha256']: row for row in flow['decisions']
                if row['action'] == 'request_revision' and row['feedback'].strip()}
    decision = requests.get(before['sha256'])
    if stage == 'video':
        old_plan, new_plan = plans[before['plan_sha256']], plans[current['plan_sha256']]
        decision = current.get('revision_feedback') or decision or requests.get(old_plan['sha256'])
    else:
        old_plan, new_plan = before, current
        if before['script'] == current['script'] and before.get('editor_sha256') == current.get('editor_sha256'):
            return None
        if decision is None:
            # Video revision that explicitly reopened the script.
            decision = next((row for row in reversed(list(requests.values()))
                             if row['stage'] == 'video' and row['changes_plan']
                             and any(v['sha256'] == row['sha256'] and v['plan_sha256'] == before['sha256']
                                     for v in flow['video_versions'])), None)
    if not decision:
        return None
    return dict(before={key: before[key] for key in ('version', 'sha256', 'artifact_sha256') if key in before},
        decision=decision, fixture=(
        not (_classification(old_plan) and _classification(new_plan))
        or decision['provenance'] == 'offline_fixture'),
        duration_seconds=new_plan['script']['target_duration'],
        measurements=dict(max_caption_chars_before=_max_caption(old_plan),
                          max_caption_chars_after=_max_caption(new_plan),
                          objective_quality='unassessed'))


def _max_caption(plan):
    return max((len(beat['caption']) for beat in plan['script']['narrative_beats']), default=0)


def review(workflow, pid, name, body):
    from representative_workflow import _match

    with workflow.store.lock(pid):
        project = workflow.store.load(pid)
        flow = project['representative']
        records = flow.setdefault('experiences', [])
        if name == 'experience-withdraw':
            exact(body, ('id', 'record_hash', 'reason'))
            record = next((row for row in records if row['id'] == body['id']), None)
            require(record and record['source'] == SOURCE and digest(record) == body['record_hash'],
                    'experience_record_changed')
            withdraw_experience(records, body['id'], body['reason'])
        else:
            fields = ('stage', 'version', 'sha256', 'category', 'preference', 'replaces', 'confirmed')
            exact(body, fields + ('use_measured_limit',) if 'use_measured_limit' in body else fields)
            measured = body.get('use_measured_limit', False)
            require(type(measured) is bool, 'experience_review_required')
            stage = body['stage']
            require(stage in ('plan', 'video') and body['category'] in CATEGORIES
                    and body['confirmed'] is True and flow['audience'] != '미정', 'experience_review_required')
            current = _match(flow[f'{stage}_versions'], body['version'], body['sha256'])
            compared = comparison(flow, stage, current)
            require(compared is not None, 'experience_review_required')
            before, decision = compared['before'], compared['decision']
            if stage == 'video':
                previous = next(row for row in flow['video_versions'] if row['sha256'] == before['sha256'])
                workflow._verify_video(project, previous)
                workflow._verify_video(project, current)
            measurements = compared['measurements']
            if measured:
                limit = measurements['max_caption_chars_after']
                require(body['category'] == 'captions' and 0 < limit < measurements['max_caption_chars_before'],
                        'experience_review_required')
                preference = f'장면별 대본 자막을 최대 {limit}자로 작성합니다.'
            else:
                safe_text(body['preference'], 500)
                preference = body['preference'].strip()
            fixture = compared['fixture']
            category = body['category']
            scope = {**work_scope(flow), 'duration_seconds': compared['duration_seconds']}
            same = [row for row in records if row['source'] == SOURCE and row['active']
                    and row['category'] == category and row['fixture'] == fixture and row['work_scope'] == scope]
            require(len(same) <= 1 and body['replaces'] == (same[0]['id'] if same else None)
                    and (not same or same[0]['positive_preference'] != preference),
                    'experience_duplicate_or_replacement_required')
            reference = {kind: {key: report[key] for key in ('version', 'sha256', 'artifact_sha256') if key in report}
                         for kind, report in [('before', before), ('after', current)]}
            entry = append_experience(records, decision['feedback'], dict(
                project=pid, domain='video', target_segment=flow['audience'], issue=category,
                positive_preference=preference, proposed_correction=preference, evidence=digest(reference),
                source=SOURCE, confidence=1, verification='hypothesis' if fixture else 'verified'),
                provenance='offline_fixture' if fixture else 'user_structured', replaces=body['replaces'])
            entry.update(category=category, work_scope=scope, fixture=fixture, comparison=reference,
                         review_stage=stage, decision_hash=digest(decision),
                         preference_confirmation='fixture' if fixture else 'representative_confirmed',
                         measurements=measurements, measured_lesson='max_caption_chars' if measured else None)
        workflow.store.save(project)


def candidates(store, *, omit=None):
    for path in sorted(store.root.glob('company-*.json')):
        if path.stem == omit:
            continue
        project = store.load(path.stem)
        yield from (row for row in project.get('representative', {}).get('experiences', [])
                    if row.get('source') == SOURCE)


def select(store, flow, *, omit=None, fixture=False):
    scoped = []
    excluded = []
    groups = defaultdict(list)
    scope = work_scope(flow)
    for record in candidates(store, omit=omit):
        reason = None
        if not record['active']:
            reason = 'inactive'
        elif record['fixture'] != fixture or not fixture and record['verification'] != 'verified':
            reason = 'provenance'
        elif (record['target_segment'] != flow['audience'] or flow['audience'] == '미정'
              or record['work_scope'] != scope):
            reason = 'work_scope'
        item = {**deepcopy(record), 'id': f"{record['project']}:{record['id']}"}
        if reason:
            excluded.append(dict(id=item['id'], record_hash=digest(record), reason=reason))
        else:
            groups[record['category']].append((item, digest(record)))
    for rows in groups.values():
        conflict = len({item['positive_preference'] for item, _ in rows}) > 1
        for index, (item, checksum) in enumerate(rows):
            if conflict or index:
                excluded.append(dict(id=item['id'], record_hash=checksum,
                                     reason='conflict' if conflict else 'duplicate'))
            else:
                scoped.append((item, checksum))
    selected = select_experiences([item for item, _ in scoped], domain='video',
                                  target_segment=flow['audience'])['selected']
    hashes = {item['id']: checksum for item, checksum in scoped}
    for item in selected:
        item.update(record_hash=hashes[item['id']], selection_reason='matching audience and production conditions')
    return dict(selected=selected, excluded=excluded)


def current_selection(store, project, *, fixture=False):
    """Only previously selected records which are still eligible can be used."""
    flow = project['representative']
    snapshot = flow.get('experience_snapshot', {})
    if not snapshot.get('selected'):
        return dict(selected=[], excluded=snapshot.get('excluded', []))
    current = select(store, flow, omit=project['id'], fixture=fixture)
    selected_at_creation = snapshot['selected']
    pinned = {(row['id'], row['record_hash']) for row in selected_at_creation}
    selected = [row for row in current['selected'] if (row['id'], row['record_hash']) in pinned]
    active = {row['id'] for row in selected}
    reasons = {row['id']: row['reason'] for row in current['excluded']}
    excluded = [dict(id=row['id'], record_hash=row['record_hash'],
                     reason=reasons.get(row['id'], 'changed')) for row in selected_at_creation if row['id'] not in active]
    return dict(selected=selected, excluded=snapshot['excluded'] + excluded)
