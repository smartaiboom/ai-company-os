"""Short-form script checks and editor handoff for the existing video workflow."""
import re
import unicodedata

from autonomous_company import CompanyError, digest, exact, parse, require
from production_video import units

MAX_SHORTS_SECONDS = 180
SCRIPT_CONTRACT = 'short_script_v1'
SHOT_TYPES = ('demo','detail','card')
SOURCE_STATUSES = ('pending','local_example')
FACT_STATUSES = ('illustrative','verification_pending')
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
    '사용자가 시청자를 정하지 않았습니다. 구체적인 target_audience 하나를 제안하고 unknowns 한 항목에 '
    '사용자 미확정 AI 제안임을 밝히고 그 대상과 실제 추론 이유를 함께 적으세요. '
    '형식 예시(값을 복사하지 말 것): "AI 제안(사용자 미확정): <제안 대상> — 이유: <선정 주제와 관측 자료에 따른 설명>". '
    'Equivalent clear Korean wording and spacing/punctuation are allowed. Do not claim user confirmation. '
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
CAPTION_WIDTH_INSTRUCTIONS = (
    ' caption_width 규칙(생성·수정·검토 공통): 각 beat.caption은 최대 2줄, 각 줄 28폭 이하입니다. '
    '글자 수가 아니라 Python unicodedata.east_asian_width가 W 또는 F인 문자당 2폭, 나머지는 1폭으로 합산합니다. '
    '한글 완성형은 2폭, ASCII 영문·숫자·공백·문장부호는 각각 1폭입니다. '
    '예: "가나다 ABC"는 6+1+3=10폭; 한글 14자는 28폭(허용), 한글 15자는 30폭(초과), ASCII 28자는 28폭입니다. '
    '모든 줄의 폭을 각각 합산해 확인하고, 초과하면 단어를 줄이거나 실제 줄바꿈을 넣어 두 줄 이내로 나누세요. '
    'JSON에서는 줄바꿈을 \\n escape로 인코딩하세요. 슬래시 / 나 자동 화면 줄바꿈은 줄 분리가 아닙니다. '
    '수정 시 caption_width와 문제 자막을 짚고 줄별 28폭 이하가 되도록 구체적으로 지시하세요. '
    '검토 시 남은 caption_width major 결함은 accept하지 말고 수정 피드백에 포함하세요.'
)
SCRIPT_INSTRUCTIONS = (
    'Plan one writer reviewed against all eight criteria ids and one editor depending on the writer. '
    'Criteria ids: ' + ', '.join(CRITERIA) + '. '
    'Select one useful evergreen topic for the target audience, or mark current claims verification_pending. '
    'Writer JSON keys: ' + ', '.join(WRITER_FIELDS) + '. Beat keys: ' + ', '.join(BEAT_FIELDS) + '. '
    'contract=short_script_v1; target_duration=60; topic={title,freshness}, freshness=evergreen|current; '
    'unknowns=list of strings; provenance={author,model,mock}; use actual invocation provenance. '
    'Use contiguous integer seconds, a 0–3s opening, transcript joined with newlines, and close as the last narration. '
    'Give a concrete screen action and caption per beat; shot_type='+'|'.join(SHOT_TYPES)+', source_status='+'|'.join(SOURCE_STATUSES)+', '
    'fact_status='+ '|'.join(FACT_STATUSES)+'. Local examples are demonstrations prepared as text. '
    'Editor must consume the accepted writer version and output {contract,writer_ref,shots}; writer_ref includes '
    'task_id,revision,result_hash; each shot includes start,end,narration,caption,screen,shot_type,source_ref,source_status. '
    'Review criteria: ' + ', '.join(CRITERIA.values()) + '. Cite actual passages and give severity, owner, and a concrete edit. '
    'On revision read previous version and revision_feedback. Keep audience appeal and retention unassessed without evidence.'
    + AUDIENCE_INSTRUCTIONS + CAPTION_WIDTH_INSTRUCTIONS
)


def _nonempty(value):
    require(isinstance(value, str) and bool(value.strip()), 'missing_script_text')


def _audience_text(value):
    return re.sub(r'[\W_]+','',unicodedata.normalize('NFKC',value).casefold())


def audience_inference_issue(value):
    """Conservative declaration checks, not a judgment of audience appeal or reason quality."""
    audience=_audience_text(value['target_audience'])
    if not audience or audience=='미정':
        return 'literal_unspecified_audience'
    entries=value['unknowns']
    marked=[entry for entry in entries if (
        re.search(r'(?<![a-z])ai(?![a-z])',entry.casefold())
        and any(word in _audience_text(entry) for word in ('추론','제안','추천','가정'))
        and any(word in _audience_text(entry) for word in (
            '사용자미확정','사용자미지정','사용자확인전','사용자확정전','사용자확인필요',
            '사용자가지정하지않','사용자가확정하지않','사용자에게확인필요'))
        and not any(word in _audience_text(entry) for word in ('사용자승인완료','사용자확정완료','ai제안아님','ai추론아님')))]
    if not marked:
        return 'inference_marker_missing'
    referenced=[entry for entry in marked if audience in _audience_text(entry)]
    if not referenced:
        return 'audience_reference_mismatch'
    for entry in referenced:
        reason=re.search(r'(?:근거|이유)\s*(?:[:：]|는|가|로는)?\s*([^;\n]+)',entry)
        if reason:
            explanation=_audience_text(reason[1])
            if (bool(explanation) and explanation!=audience and explanation not in (
                    '없음','없다','없습니다','없어요','미제공','근거없음','미정','미확인','추후확인','unknown','해당없음','불명','모름')):
                return None
    return 'reason_missing'


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
        issue=audience_inference_issue(value)
        if issue:
            error=CompanyError('script_audience_inference_required')
            error.detail_code=issue  # Enum only: never attach response text or audience values.
            raise error

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
        require(beat['shot_type'] in SHOT_TYPES, 'invalid_script_shot')
        require(beat['source_status'] in SOURCE_STATUSES, 'invalid_script_source')
        require(beat['fact_status'] in FACT_STATUSES, 'invalid_script_fact')
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


def writer_contract(audience, duration, model, selected_topic, *, version=2):
    """One source for mission writer wire schema and relational acceptance rules."""
    from role_json_schema import obj, arr, enum
    require(type(version) is int and version in (1,2),'invalid_writer_contract_version')
    string={'type':'string','minLength':1}
    beat=obj(**{k:dict(string) for k in BEAT_FIELDS})
    beat['properties'].update(start=dict(type='integer',minimum=0,maximum=duration),
        end=dict(type='integer',minimum=1,maximum=duration),shot_type=enum(*SHOT_TYPES),
        source_status=enum('pending'),fact_status=enum(*FACT_STATUSES))
    schema=obj(**{k:dict(string) for k in WRITER_FIELDS})
    schema['properties'].update(contract=enum(SCRIPT_CONTRACT),
        target_audience=dict(string) if audience=='미정' else enum(audience),
        topic=obj(title=enum(selected_topic),freshness=enum('evergreen','current')),
        narrative_beats={**arr(beat),'minItems':2,'maxItems':20},
        target_duration=dict(type='integer',enum=[duration]),
        unknowns={**arr(dict(string)),'minItems':1 if audience=='미정' else 0},
        provenance=obj(author=dict(string),model=enum(model),mock=dict(type='boolean',enum=[False])))
    contract=dict(version=version,schema=schema,audience=audience,duration=duration,model=model,selected_topic=selected_topic,
        invariants=[
            'All required text must be nonblank. Do not add or omit object keys.',
            'topic.title copies selected_topic exactly; viewer-facing copy belongs in hook_0_3s/promise/viewing_reason.',
            'Integer contiguous beats start at 0; first beat ends at 3; last ends at target_duration; start < end.',
            'hook_0_3s equals first narration; close equals last narration; transcript joins narrations with newline.',
            'For unspecified audience propose one concrete target; one unknowns entry must state AI proposal, user unconfirmed, target and actual reason.',
            'Keep sources pending and facts illustrative or verification_pending; flag current claims verification_pending.',
            'Include a demo; avoid repeated/dense narration; captions at most 2 lines, 28 width units per line.',
            'Audience appeal, retention, Shorts classification and rights remain unverified; no media or publication.'])
    if version==1:
        return contract  # Exact historical representation; never substitute it for a new default contract.
    unspecified=audience=='미정'
    contract['audience_input']=dict(target_segment=audience,user_specified=not unspecified)
    contract['audience_output']=dict(field='result.content.target_audience',
        policy='propose_one_concrete_audience_not_input_status' if unspecified else 'copy_user_specified_audience_exactly')
    if unspecified:
        instruction=('입력 target_segment=미정은 사용자가 시청자를 지정하지 않았다는 상태입니다. '
            '출력 result.content.target_audience는 입력 상태를 복사하는 필드가 아닙니다. '
            '관리자 선정 주제와 관측을 근거로 구체적인 대상 하나를 AI가 제안하세요. '
            '출력에 미정 또는 아래 placeholder를 복사하지 마세요. '
            'unknowns 한 항목에 AI 제안(사용자 미확정), 제안한 대상, 비어 있지 않은 실제 이유를 함께 적으세요.')
        contract['audience_output_instruction']=instruction
        schema['properties']['target_audience']['description']=instruction
        schema['properties']['unknowns']['items']['description']='제안 대상의 사용자 미확정 상태와 AI 제안 이유를 기록. 대상의 타당성/성과는 미검증.'
        contract['audience_output_example']=dict(template_only=True,target_audience='<AI가 제안할 구체적 대상>',
            unknowns=['AI 제안(사용자 미확정): <동일한 제안 대상>. 이유: <선정 주제와 관측에 따른 실제 설명>'])
    else:
        contract['audience_output_instruction']='사용자가 지정한 target_segment를 target_audience에 문자 그대로 복사하세요. AI가 바꾸지 마세요.'
    return contract


def validate_writer_contract(value, contract):
    from role_json_schema import matches
    inspection=inspect_script(value,contract['audience'],mock=False,target_duration=contract['duration'])
    require(value['provenance']['model']==contract['model'],'script_provenance_mismatch')
    require(value['topic']['title']==contract['selected_topic'],'mission_selected_topic_mismatch')
    require(all(b['source_status']=='pending' for b in value['narrative_beats']),'mission_visual_source_unverified')
    require(not any(d['issue'] in ('timeline_gap_or_overlap','total_duration','hook_window') for d in inspection['defects']),
            'invalid_script_timeline')
    require(matches(value,contract['schema']),'invalid_writer_schema')
    return inspection


def script_failure_details(value, error, contract=None):
    """Fixed field paths/indices/types only; never return generated text."""
    code=error.code
    path={'script_audience_mismatch':'target_audience','script_audience_inference_required':'unknowns',
        'script_provenance_mismatch':'provenance','mission_selected_topic_mismatch':'topic.title',
        'invalid_topic_freshness':'topic.freshness','invalid_script_contract':'target_duration',
        'script_transcript_mismatch':'transcript','invalid_script_unknowns':'unknowns',
        'invalid_script_beats':'narrative_beats','invalid_beat_time':'narrative_beats','invalid_script_timeline':'narrative_beats'}.get(code,'$')
    result=dict(stage='writer_script_validation',category=code,error_code=code,field_path=path)
    enums={'invalid_script_shot':('shot_type',SHOT_TYPES),'invalid_script_source':('source_status',SOURCE_STATUSES),
        'mission_visual_source_unverified':('source_status',('pending',)), 'invalid_script_fact':('fact_status',FACT_STATUSES)}
    if isinstance(value,dict) and code=='invalid_fields':
        missing=next((k for k in WRITER_FIELDS if k not in value),None)
        if missing:result['field_path']=missing
        else:
            for field,keys in (('topic',('title','freshness')),('provenance',('author','model','mock'))):
                item=value.get(field)
                if not isinstance(item,dict) or set(item)!=set(keys):
                    result['field_path']=field
                    break
    if isinstance(value,dict) and code=='missing_script_text':
        for field in WRITER_FIELDS:
            if isinstance(value.get(field),str) and not value[field].strip():
                result['field_path']=field
                break
    beats=value.get('narrative_beats',[]) if isinstance(value,dict) else []
    if code in enums and isinstance(beats,list):
        field,allowed=enums[code]
        for index,beat in enumerate(beats):
            item=beat.get(field) if isinstance(beat,dict) else None
            if not isinstance(item,str) or item not in allowed:
                result.update(field_path=f'narrative_beats[{index}].{field}',beat_index=index,
                    allowed_set_match=False,value_type=type(item).__name__)
                if isinstance(item,str):result['value_length']=len(item)
                break
    if code=='script_audience_inference_required':result['detail_code']=getattr(error,'detail_code','inference_marker_missing')
    if code=='mission_selected_topic_mismatch' and contract:
        title=value['topic']['title'];expected=contract['selected_topic']
        result.update(stage='writer_selected_topic_validation',exact_match=False,
            normalized_match=' '.join(unicodedata.normalize('NFKC',title).split()).casefold()==' '.join(unicodedata.normalize('NFKC',expected).split()).casefold(),
            expected_length=len(expected),returned_length=len(title),expected_title_hash=digest(expected),returned_title_hash=digest(title))
    return result


def script_editor_handoff(writer):
    script = parse(writer['content'])
    return dict(contract=SCRIPT_CONTRACT,
        writer_ref=dict(task_id=writer['task_id'], revision=writer['revision'], result_hash=digest(writer)),
        shots=[{k: b[k] for k in BEAT_FIELDS if k != 'fact_status'} for b in script['narrative_beats']])


def validate_script_editor(value, previous):
    writers = [r for r in previous if r['role'] == 'writer']
    require(len(writers) == 1 and value == script_editor_handoff(writers[0]), 'script_editor_handoff_mismatch')
