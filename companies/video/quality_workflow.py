"""Video quality planning adapter. Text plans are not rendered or publishable videos."""
from copy import deepcopy
import math
from autonomous_company import Company, require, exact, parse, digest
from quality_feedback import ROLE_CONTRACTS
from video_production_company import offline_clip_decision_context

RUBRIC = (
    ('hook', '대본/기획', '초반 3초 관심 유도'),
    ('message', '대본/기획', '대상 시청자에게 한 가지 분명한 메시지'),
    ('facts', '대본/기획', '사실 정확성과 구체적 유용성'),
    ('alignment', '영상/편집', '화면과 대본 의미 일치'),
    ('variety', '영상/편집', '소스 다양성과 과도한 반복 회피'),
    ('composition', '영상/편집', '9:16 구성과 자막 가독성'),
    ('voice', '음성/자막', '발음·어조·속도'),
    ('sync', '음성/자막', '자막 동기와 읽기 편의'),
    ('flow', '전체 완성도', '이야기 흐름과 밀도'),
    ('publish', '전체 완성도', '시청자 유익성과 게시 수준'))

VIDEO_ROLES = {
    'writer': '한국어 대본: 0~3초 후크, 핵심 사례, 시연/근거, 짧은 마무리. '
              '과밀 목표는 가치 중심으로 줄인 이유를 기록하고 필요하면 관리자에게 재확인. 미확인 사실 구분.',
    'editor': '60초 샷별 내레이션 대응·소스 수·필요 길이·시연·교차편집 계획. '
              '5~8초 클립 반복으로 20초를 채우지 말 것. 소스 없으면 external_clip_pending.',
    'voice': '발음하기 쉬운 한국어, 영어/이름 발음 보정, 대상별 톤·속도 지시. '
             'MeloTTS 자연스러움 한계 명시. 새 TTS/API/다운로드 금지. 청취 전 자연스러움 unassessed.',
    'qa': '기술 미디어 검사와 콘텐츠 평가 분리. 근거 없는 점수/게시 합격 금지. '
          '각 결함의 근거·심각도·담당·수정 요청·기대 지표와 전후 차이를 기록.'}


def capabilities():
    return dict(**offline_clip_decision_context(), roles=deepcopy(VIDEO_ROLES),
                artifact_contract='writer:{segments:[{seconds,text}]}; editor:{shots:[{seconds,source_seconds,'
                                  'source_id,narration,source_status}]}; voice:{instructions,pronunciation}',
                rubric=[dict(id=i, category=c, description=d, max_score=1) for i,c,d in RUBRIC])


def validate_artifact(role, value):
    if role == 'writer':
        exact(value, ('segments',));items=value['segments']
        require(isinstance(items,list) and 1 <= len(items) <= 20, 'invalid_segments')
        for item in items:
            exact(item, ('seconds','text'))
            require(isinstance(item['text'],str) and bool(item['text'].strip()), 'missing_narration')
    elif role == 'editor':
        exact(value, ('shots',));items=value['shots']
        require(isinstance(items,list) and 1 <= len(items) <= 30, 'invalid_shots')
        for item in items:
            exact(item, ('seconds','source_seconds','source_id','narration','source_status'))
            require(type(item['source_seconds']) in (int,float) and math.isfinite(item['source_seconds'])
                    and item['source_seconds'] > 0, 'invalid_source_duration')
            require(item['source_status'] in ('planned','provided_unverified'), 'invalid_source_status')
            require(isinstance(item['source_id'],str) and bool(item['source_id']), 'invalid_source_id')
            require(isinstance(item['narration'],str) and bool(item['narration']), 'missing_narration')
    else:
        require(role == 'voice', 'unsupported_quality_role')
        exact(value, ('instructions','pronunciation'))
        require(all(isinstance(v,str) and bool(v.strip()) for v in value.values()), 'invalid_voice')
        return value
    for item in items:
        require(type(item['seconds']) in (int,float) and math.isfinite(item['seconds'])
                and item['seconds'] > 0, 'invalid_duration')
    require(abs(sum(i['seconds'] for i in items)-60) < .01, 'timeline_must_be_60_seconds')
    return value


def inspect_plan(role, value):
    """Objective plan checks only; no semantic or sensory score inferred."""
    validate_artifact(role, value)
    defects=[]
    if role == 'editor':
        for index, shot in enumerate(value['shots']):
            if shot['seconds'] > shot['source_seconds']:
                defects.append(dict(issue='repeated_clip', severity='major', owner='editor',
                    evidence=f'shots[{index}]: {shot["seconds"]}s / {shot["source_seconds"]}s source',
                    correction='추가 샷/실제 시연을 확보하고 내레이션에 맞게 분할',
                    expected_metric='planned source repeats=0'))
        ids=[s['source_id'] for s in value['shots']]
        if len(set(ids)) < len(ids):
            defects.append(dict(issue='reused_source', severity='major', owner='editor',
                evidence='duplicate source_id in shot plan', correction='다른 소스와 시연으로 교체',
                expected_metric='unique source ids per shot'))
    return dict(source='deterministic_plan_check', artifact_hash=digest(value), defects=defects,
                sensory_quality='unassessed', media_technical='unassessed')


def checklist():
    return dict(items=[dict(id=i, category=c, description=d, max_score=1,
                           status='unassessed', score=None, evidence=None,
                           evaluator='none') for i,c,d in RUBRIC], total=None,
                reason='계획만 검사함. 실제 시청·청취·사실 검증 및 사용자 평가 필요')


class VideoQualityCompany(Company):
    """Opt-in mock adapter over existing orchestration. Live providers remain rejected."""
    def _workflow_context(self, p):
        require('quality_context' in p, 'quality_context_required')
        return dict(quality=deepcopy(p['quality_context']), role_contracts=deepcopy(ROLE_CONTRACTS),
                    video_roles=deepcopy(VIDEO_ROLES))

    def _call(self, p, provider, phase, task_id, context):
        if 'previous_results' in context:
            context=deepcopy(context)
            context['handoff_refs']=[dict(task_id=r['task_id'], revision=r['revision'],
                                         result_hash=digest(r), source=r['source'])
                                     for r in context['previous_results']]
        if phase == 'review':
            role=next(t['role'] for t in p['assignments'] if t['id']==task_id)
            context={**context, 'plan_inspection':inspect_plan(role,parse(context['result']['content']))}
        return super()._call(p,provider,phase,task_id,context)

    def _validate_review_decision(self,p,task,review):
        inspection=inspect_plan(task['role'],parse(task['versions'][-1]['content']))
        require(review['action'] != 'accept' or not inspection['defects'], 'known_plan_defects')
        task.setdefault('plan_inspections',[]).append(inspection)

    def _delivery_blockers(self,p):
        # A source plan never proves files, rights, technical media or perceived quality.
        p['quality_checklist']=checklist()
        return ['external_clip_pending','needs_user_review']
