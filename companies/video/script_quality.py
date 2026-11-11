"""Short-form script checks and editor handoff for the existing video workflow."""
import re

from autonomous_company import digest, exact, parse, require
from production_video import units

MAX_SHORTS_SECONDS = 180
SCRIPT_CONTRACT = 'short_script_v1'
CRITERIA = {
    'hook': '첫 3초 관심', 'message': '한 가지 메시지', 'utility': '구체적인 시청자 효용',
    'density': '중복과 군더더기', 'demo': '구체 사례와 실제 시연 가능성',
    'facts': '사실·시점 근거', 'duration': '60초 분량과 자막', 'editability': '편집 현실성',
}
AUDIENCE_INFERENCE_PREFIX = 'AI 추론(사용자 미확정):'
AUDIENCE_INSTRUCTIONS = (
    ' A concrete user target_segment requires exactly matching target_audience. '
    'target_segment=미정 means the user did not specify an audience, never a literal audience name. '
    'In that case propose a concrete target_audience from the goal, selected topic and available evidence. '
    'Add an unknowns entry starting with "AI 추론(사용자 미확정):", containing the exact proposed '
    'target_audience and "근거:" followed by a nonempty explanation. Do not claim user confirmation. '
    'Keep the original input target_segment unchanged; appeal and retention remain unassessed.'
)
WRITER_FIELDS = (
    'contract', 'target_audience', 'topic', 'viewer_problem', 'promise', 'viewing_reason',
    'hook_0_3s', 'payoff', 'narrative_beats', 'close', 'transcript', 'target_duration',
    'estimation_method', 'unknowns', 'provenance',
)
BEAT_FIELDS = (
    'start', 'end', 'narration', 'caption', 'screen', 'shot_type', 'source_ref', 'source_status',
    'fact_status',
)
SCRIPT_INSTRUCTIONS = (
    'Plan one writer reviewed against all eight criteria ids and one editor depending on the writer. '
    'Criteria ids: ' + ', '.join(CRITERIA) + '. '
    'Select one useful evergreen topic for the target audience, or mark current claims verification_pending. '
    'Writer JSON keys: ' + ', '.join(WRITER_FIELDS) + '. Beat keys: ' + ', '.join(BEAT_FIELDS) + '. '
    'contract=short_script_v1; target_duration=60; topic={title,freshness}, freshness=evergreen|current; '
    'unknowns=list of strings; provenance={author,model,mock}; use actual invocation provenance. '
    'Use contiguous integer seconds, a 0–3s opening, transcript joined with newlines, and close as the last narration. '
    'Give a concrete screen action and caption per beat; shot_type=demo|detail|card, source_status=pending|local_example, '
    'fact_status=illustrative|verification_pending. Local examples are demonstrations prepared as text. '
    'Editor must consume the accepted writer version and output {contract,writer_ref,shots}; writer_ref includes '
    'task_id,revision,result_hash; each shot includes start,end,narration,caption,screen,shot_type,source_ref,source_status. '
    'Review criteria: ' + ', '.join(CRITERIA.values()) + '. Cite actual passages and give severity, owner, and a concrete edit. '
    'On revision read previous version and revision_feedback. Keep audience appeal and retention unassessed without evidence.'
    + AUDIENCE_INSTRUCTIONS
)


def _nonempty(value):
    require(isinstance(value, str) and bool(value.strip()), 'missing_script_text')


def inspect_script(value, audience, *, mock, target_duration=60):
    exact(value, WRITER_FIELDS)
    require(type(target_duration) is int and 4 <= target_duration <= MAX_SHORTS_SECONDS, 'invalid_script_duration')
    require(value['contract'] == SCRIPT_CONTRACT and type(value['target_duration']) is int
            and value['target_duration'] == target_duration, 'invalid_script_contract')
    for field in ('target_audience', 'viewer_problem', 'promise', 'viewing_reason', 'hook_0_3s',
                  'payoff', 'close', 'transcript', 'estimation_method'):
        _nonempty(value[field])
    if audience != '미정':
        require(value['target_audience'] == audience, 'script_audience_mismatch')
    exact(value['topic'], ('title', 'freshness'))
    _nonempty(value['topic']['title'])
    require(value['topic']['freshness'] in ('evergreen', 'current'), 'invalid_topic_freshness')
    exact(value['provenance'], ('author', 'model', 'mock'))
    _nonempty(value['provenance']['author'])
    require(value['provenance']['mock'] is mock, 'script_provenance_mismatch')
    if mock:
        require(value['provenance']['model'] is None, 'script_provenance_mismatch')
    else:
        _nonempty(value['provenance']['model'])
    require(isinstance(value['unknowns'], list), 'invalid_script_unknowns')
    for unknown in value['unknowns']:
        _nonempty(unknown)

    if audience == '미정':
        require(value['target_audience'].strip() != '미정' and any(
            unknown.startswith(AUDIENCE_INFERENCE_PREFIX) and value['target_audience'] in unknown
            and '근거:' in unknown and bool(unknown.split('근거:', 1)[1].strip())
            for unknown in value['unknowns']), 'script_audience_inference_required')

    beats = value['narrative_beats']
    require(isinstance(beats, list) and 2 <= len(beats) <= 20, 'invalid_script_beats')
    defects = []

    def defect(issue, criterion, evidence, correction):
        defects.append(dict(issue=issue, criterion=criterion, evidence=evidence, severity='major',
                            owner='writer', correction=correction))

    cursor = 0
    seen = set()
    pending = []
    for index, beat in enumerate(beats):
        exact(beat, BEAT_FIELDS)
        for key in BEAT_FIELDS[2:]:
            _nonempty(beat[key])
        start, end = beat['start'], beat['end']
        require(type(start) is int and type(end) is int and 0 <= start < end <= max(120, target_duration), 'invalid_beat_time')
        quote = f'{start}–{end}초: {beat["narration"]}'
        if start != cursor:
            defect('timeline_gap_or_overlap', 'duration', quote, f'장면 시작을 직전 종료 {cursor}초에 맞춘다.')
        cursor = end
        require(beat['shot_type'] in ('demo', 'detail', 'card'), 'invalid_script_shot')
        require(beat['source_status'] in ('pending', 'local_example'), 'invalid_script_source')
        require(beat['fact_status'] in ('illustrative', 'verification_pending'), 'invalid_script_fact')
        normalized = re.sub(r'[^\w]+', '', beat['narration'].casefold())
        if normalized in seen:
            defect('repeated_narration', 'density', quote, '중복 문장을 삭제하고 화면에서 새 정보를 보여준다.')
        seen.add(normalized)
        caption_lines = beat['caption'].splitlines()
        if len(caption_lines) > 2 or any(units(line) > 28 for line in caption_lines):
            defect('caption_width', 'duration', beat['caption'], '자막을 최대 두 줄, 줄당 28 폭 단위로 줄인다.')
        if len(re.sub(r'\s+', '', beat['narration'])) > 6 * (end - start):
            defect('dense_narration', 'duration', quote, '내레이션을 압축하거나 발화 시간을 늘린다.')
        if beat['source_status'] == 'pending' or beat['fact_status'] == 'verification_pending':
            pending.append(dict(beat=index, source=beat['source_ref'], source_status=beat['source_status'],
                                fact_status=beat['fact_status']))
    if beats[0]['end'] != 3 or value['hook_0_3s'] != beats[0]['narration']:
        defect('hook_window', 'hook', beats[0]['narration'], '첫 장면을 0–3초로 두고 후크 문구를 일치시킨다.')
    if cursor != target_duration:
        defect('total_duration', 'duration', f'최종 종료 {cursor}초', f'장면을 {target_duration}초까지 재배치한다.')
    if all(beat['shot_type'] != 'demo' for beat in beats):
        defect('missing_demo', 'demo', '장면 유형: ' + ', '.join(b['shot_type'] for b in beats),
               '가상 예시 입력과 결과 비교를 화면 동작으로 지정한다.')
    if value['topic']['freshness'] == 'current' and not any(
            beat['fact_status'] == 'verification_pending' for beat in beats):
        defect('current_claim_unflagged', 'facts', value['topic']['title'],
               '최신 정보가 필요한 장면에 verification_pending을 표시한다.')
    require(value['transcript'] == '\n'.join(b['narration'] for b in beats)
            and value['close'] == beats[-1]['narration'], 'script_transcript_mismatch')
    return dict(source='deterministic_script_check', artifact_hash=digest(value), defects=defects,
                pending=pending, sensory_quality='unassessed', audience_appeal='unassessed',
                retention='unassessed', previous_artifact_hash=None)


def script_editor_handoff(writer):
    script = parse(writer['content'])
    return dict(contract=SCRIPT_CONTRACT,
        writer_ref=dict(task_id=writer['task_id'], revision=writer['revision'], result_hash=digest(writer)),
        shots=[{k: b[k] for k in BEAT_FIELDS if k != 'fact_status'} for b in script['narrative_beats']])


def validate_script_editor(value, previous):
    writers = [r for r in previous if r['role'] == 'writer']
    require(len(writers) == 1 and value == script_editor_handoff(writers[0]), 'script_editor_handoff_mismatch')
