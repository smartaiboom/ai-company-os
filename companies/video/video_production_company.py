"""Video company profile on the existing Gemini35 state machine, offline by default."""
from copy import deepcopy
import json
from autonomous_company import require,digest
from autonomous_gemini35 import Gemini35Store,Gemini35Company
from production_video import CATALOG,TOOL,validate,render

PROFILE={'version':1,'name':'video_production_company',
         'capabilities':['제작 총괄','대본·구성','소스·아트','음성·편집','품질 검토'],
         'decisions':'AI executive selects roles, workflow, concept and quality criteria from user goal',
         'external_tts':False,'external_sources':False,
         'review_limits':'text model receives storyboard, keyframe hashes and timing metadata; no claim of watching/listening'}


class VideoProductionStore(Gemini35Store):
    mode='video_production_gemini35_v1'
    marker_name='.video-production-gemini35-v1-store'
    policy='video_production_gemini35_v1'
    project_prefix='videocompany-'
    def _tool_catalog(self):return CATALOG
    def create(self,goal,**kwargs):
        require(kwargs.get('local_tools',[TOOL])==[TOOL],'production_tool_required')
        kwargs['local_tools']=[TOOL]
        return super().create(goal,**kwargs)
    def prepare(self,project_id,**kwargs):
        body=super().prepare(project_id,**kwargs);body['production_profile']=deepcopy(PROFILE);return body
    def _check_contract(self,p,b):
        require(isinstance(b,dict) and digest(b.get('production_profile'))==digest(PROFILE),'production_profile_consent_required')
        super()._check_contract(p,{k:v for k,v in b.items() if k!='production_profile'})


class VideoProductionCompany(Gemini35Company):
    store_type=VideoProductionStore
    def _validate_tool_input(self,spec):validate(spec)
    def _execute_local_tool(self,spec,folder):return render(spec,folder)
    def _tool_notice(self,p):
        return (' Video production company capability profile: '+json.dumps(PROFILE,ensure_ascii=False)+
                ' You are the production executive. Assign/combine suitable specialist roles and handoffs for the goal; '
                'this is a capability catalog, not a fixed plan. Tool schema: '+json.dumps(CATALOG)+
                ' Employee content is a strict JSON tool request with root tool selector or prose for non-tool work. '
                'Tool failures are retained as tool_status=failed/tool_failure for manager review. '
                'Manager decides revise with concrete feedback, stop or operational permission; never accept failed media. '
                'No external TTS/source permission exists. espeak_reference is robotic, never label it natural Korean. '
                'If natural voice is a goal requirement, these offline audio modes do not fulfill it; '
                'stop or request operational permission instead of claiming that requirement met. '
                'Keyframes/timing/source receipts are review evidence, not proof the text model watched or heard the media. '
                'Actual MP4 plus accepted input/receipt required for delivery. Keep production choices and quality judgment with AI roles.')


def offline_clip_decision_context():
    """Capabilities for a future manager decision, without granting live tool permission."""
    from ai_clip_pipeline import PROVIDERS, DisabledAPIProvider
    return dict(workflow='offline_imported_clip_shorts_v1', providers=deepcopy(PROVIDERS),
                future_api=DisabledAPIProvider().capabilities(), output_size=[720,1280],
                fit_default='letterbox', speech='MeloTTS_local_cpu', incurred_cost_limit=0,
                external_api_enabled=False, manager_must_supply='validated scene plan and source/rights receipts',
                live_company_tool_catalog_unchanged=True)


def create_offline_clip_job(folder, plan):
    """Explicit local job; never creates/approves/resumes a Gemini project."""
    from ai_clip_pipeline import ClipJob
    return ClipJob(folder).create(plan)


def quality_tool_decision_context():
    """Read-only paid-tool preparation; does not enlarge the live tool allowlist."""
    from quality_tool_adapters import capabilities
    return capabilities()


def prepare_staff_tts_job(text, reference, *, fictional, model='gemini-3.8-flash-tts', voice='Puck'):
    """Voice employee handoff; isolated job and independent TTS approval required."""
    from tts_job import prepare_voice_job
    return prepare_voice_job(text, reference, fictional=fictional, model=model, voice=voice)


def voice_staff_quality_context(selection, *, target_segment, video_brief=None):
    """Scoped recommendation for a new voice assignment; never authorizes TTS."""
    from voice_quality import voice_policy_for_brief, next_voice_sample, AUDIENCE
    policy = voice_policy_for_brief(selection, target_segment, video_brief)
    sample=next_voice_sample() if (policy['recommended'] and target_segment==AUDIENCE and
        (video_brief is None or video_brief['language']=='ko-KR' and video_brief['genre']=='ai_tips')) else None
    if sample and policy.get('video_selection',{}).get('style'):
        sample['direction']['style']=policy['video_selection']['style']
    return dict(voice_policy=policy, next_sample=sample, external_calls=False, cost_limit=0)


def approved_portrait_direction(project, plan, storyboard):
    """Review-only inputs for a future, separately scoped production-direction request."""
    from autonomous_gemini35 import MODEL
    from voice_quality import CANDIDATE, scoped_voice_policy
    flow = project['representative']
    audience = plan['script']['target_audience']
    policy = scoped_voice_policy(flow.get('scoped_experiences', {}), audience)
    return dict(goal=project['goal'], audience=audience, topic=plan['topic'],
        language=flow['constraints'].get('language'), duration=plan['script']['target_duration'],
        storyboard=storyboard['shots'], source_observations=[
            {k:item[k] for k in ('id','title','duration_seconds','view_count','rights','shorts_classification') if k in item}
            for item in plan.get('research',{}).get('observations',[])],
        profile=deepcopy(PROFILE),
        direction='승인 내레이션·장면 타이밍을 유지하고 대상에 맞는 한국어 전달 방식과 장면 연출을 제안한다. '
                  '기존 사용권 상태를 보존하고, 확보 전에는 자체 시안만 사용한다. 실제 청취·시청은 별도 확인한다.',
        listening=dict(historical_candidate=deepcopy(CANDIDATE), historical_score=7,
                       scope='이전 한국어 안내 영상 표본의 대표 평가', current_quality='unassessed',
                       matched_experience_count=len(policy['evidence_refs'])),
        external=[
            dict(kind='제작 방향 텍스트',model=MODEL,proposed_max_calls=1,
                 data='목표·대상·승인 장면과 내레이션·출처 관측·경험과 도구 한계',enabled=False),
            dict(kind='장면 음성',model=CANDIDATE['model'],proposed_max_calls=len(storyboard['shots']),
                 data='승인된 장면별 내레이션과 검토한 음성 지시',enabled=False)],
        pricing='현재 계정의 무료 적용·잔량·실제 청구 미확인', authorized_external_calls=0)
