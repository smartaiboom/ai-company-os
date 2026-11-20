"""Local HTTP adapter for the representative video workflow."""
import argparse
from copy import deepcopy
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit

from autonomous_company import CompanyError, Store, exact, require, digest, now
from representative_workflow import RepresentativeVideoWorkflow, _file_hash

ASSETS = Path(__file__).with_name('studio')
ROOT = Path('data/video_representative_workflow')
PROJECT = r'company-[0-9a-f]{32}'
STATIC = {'/': ('index.html', 'text/html'), '/studio.css': ('studio.css', 'text/css'),
          '/studio.js': ('studio.js', 'text/javascript')}
MISSION_ACTIONS = ('mission-connect-web', 'mission-prepare', 'mission-consent', 'mission-run', 'mission-report')
RESEARCH_ACTIONS = ('research-approve', 'research-run', 'research-revoke',
                    'research-recovery-approve', 'research-recovery-run', 'research-recovery-revoke')

PRODUCTION_ACTIONS = ('production-plan-prepare','production-plan-consent','production-plan-run',
                      'production-publisher-approve','production-publisher-run','production-publisher-rights','production-publisher-revoke',
                      'production-relevance-approve','production-relevance-run','production-relevance-rights','production-relevance-revoke',
                      'production-diagnostic-approve','production-diagnostic-run','production-diagnostic-rights',
                      'production-diagnostic-revoke',
                      'production-adaptive-approve','production-adaptive-run','production-adaptive-rights',
                      'production-adaptive-revoke',
                      'production-discovery-approve','production-discovery-run','production-discovery-rights',
                      'production-discovery-revoke',
                      'production-assets-approve','production-assets-revoke',
                      'production-policy-approve','production-policy-run','production-policy-revoke',
                      'production-listen','production-timeline-prepare','production-timeline-consent',
                      'production-timeline-run','production-timeline-approve',
                      'production-batch-prepare','production-batch-consent','production-batch-run',
                      'production-source-prepare','production-source-consent','production-source-run','production-source-import',
                      'production-voice-prepare','production-voice-consent','production-voice-run',
                      'production-clip-import','production-render')
RESEARCH_ERRORS = {
    'decision_recovery_blocked': '응답과 승인 범위를 연결할 수 없어 복구가 차단됐습니다. 관리자·대표 검토가 필요합니다.',
    'decision_internal_error': '판단 검증 코드에서 오류가 발생해 조사를 중단했습니다.',
    'owner_policy_exhausted': '이미 사용한 조사 범위입니다. 기존 기록을 보존하고 복구 범위를 검토하세요.',
    'research_step_invalid': 'Gemini 응답이 허용된 조사 도구 또는 종료 규칙에 맞지 않습니다.',
    'invalid_manager_plan_schema': 'Gemini 응답 형식이 필요한 구조와 일치하지 않습니다.',
    'transport_or_response_failed': 'Gemini 호출 또는 응답 확인 중 중단됐습니다.',
}
ERRORS = {
    'research_scope_invalid': '현재 업무와 조사 범위가 일치하지 않습니다.',
    'research_search_disabled': '무료 전용 Tavily 계정과 서버 설정을 확인하세요.',
    'research_search_failed': '검색 응답을 확인하지 못했습니다. 이 범위에서 후속 호출을 중단했습니다.',
    'research_evidence_invalid': '인용 원문 또는 독립 출처 요건을 확인하지 못했습니다.',
    'publisher_rights_unverified': '후보에 적용되는 공식 무료 다운로드 및 로컬 편집 허가 문구를 확인해야 합니다.',
    'publisher_url_blocked': '승인된 공식 제공처 또는 경로가 아닙니다.',
    'publisher_http_failure': '제작사 응답을 검증하는 중 중단했습니다.',
    'publisher_response_limit': '제작사 응답이 허용 한도를 초과했습니다.',
    'publisher_plan_invalid': '장면 경로 또는 후보 근거가 유효하지 않습니다.',
    'commons_relevance_invalid': '장면 적합성 응답의 후보 ID, 실제 인용 근거 또는 화면 유형을 확인하지 못했습니다.',
    'still_image_pixels_invalid': '이미지 해상도 또는 총 픽셀 수가 로컬 검증 한도를 벗어났습니다.',
    'still_image_format_invalid': '지원되는 단일 PNG/JPEG 원본이 아닙니다.',
    'commons_rights_review_changed': '확인한 후보, 검색 결과 해시 또는 권리 검토 범위가 달라졌습니다.',
    'commons_response_failed': 'Commons 검색 응답을 확인하지 못했습니다. 자동 재시도하지 않습니다.',
    'commons_response_shape': 'Commons 응답의 페이지 배열 구조를 확인할 수 없습니다.',
    'commons_response_limit': 'Commons 응답이 허용된 크기 또는 시간 범위를 초과했습니다.',
    'asset_extension_not_ready': '장면별 길이와 사용권을 확인한 등록 소스 또는 무료 Gemini 설정이 필요합니다.',
    'official_rights_unverified': '공식 출처의 다운로드 허가와 로컬 편집·검토 사용권을 확인하세요.',
    'official_destination_blocked': '공식 제공 호스트가 안전한 공개 주소로 확인되지 않았습니다.',
    'official_media_response_invalid': '직접 MP4 응답 검증에 실패했습니다. 리다이렉트는 허용되지 않습니다.',
    'official_download_failed_or_uncertain': '직접 다운로드가 실패했거나 결과를 확인할 수 없습니다. 자동 재시도는 없습니다.',
    'invalid_source_edit': '편집안의 장면, 구간 또는 배치가 승인된 소스·시간 범위를 벗어났습니다.',
    'owner_policy_required': '이 프로젝트에 적용할 개인 운영 정책을 검토하고 승인하세요.',
    'owner_policy_expired': '개인 운영 정책의 유효 시간이 지났습니다.',
    'owner_policy_revoked': '대표가 운영 정책을 철회했습니다.',
    'owner_policy_key_changed': '현재 제작 키가 승인한 운영 정책의 키와 일치하지 않습니다.',
    'owner_policy_scope_changed': '검토한 프로젝트·요청 범위와 현재 준비 상태가 일치하지 않습니다.',
    'owner_policy_unresolved_attempt': '실패했거나 미확정인 요청이 있습니다. 후속 외부 호출과 자동 재시도를 중단했습니다.',
    'owner_policy_manages_execution': '이 제작의 외부 요청은 개인 운영 정책에 연결되어 있습니다.',
    'timeline_proposal_mismatch': '검토한 시간 조정안 버전과 해시를 확인하세요.',
    'invalid_measured_timeline': '제안된 장면·자막 시간이 실측 음성 또는 소스 범위와 일치하지 않습니다.',
    'voice_batch_scene_reserved': '이 장면은 일괄 승인 범위에 속합니다.',
    'production_source_asset_changed': '등록 당시의 권리 기록 또는 파일 해시와 일치하지 않습니다.',
    'source_library_selection_invalid': '승인된 자산 확보 결과의 장면과 자산 ID를 확인하세요.',
    'technical_preview_not_approvable': '무음 카드 기술 시안은 영상 승인 대상이 아닙니다. 영상 수정 요청으로 제작을 이어가세요.',
    'production_project_key_unverified': '서버의 기존 API 키와 별도 확인한 제작 프로젝트 키가 일치해야 합니다.',
    'portrait_korean_font_missing': '로컬 세로 시안에 사용할 한글 글꼴을 찾을 수 없습니다.',
    'melo_runtime_missing': '로컬 MeloTTS 실행 환경 또는 모델이 준비되지 않았습니다.',
    'narration_exceeds_scene': '음성이 승인된 장면 시간을 초과했습니다. 장면을 자동으로 늘리거나 음성을 자르지 않았습니다.',
    'mission_free_account_unverified': '고정 Google 프로젝트의 키 소속, 결제 미연결 및 무료 사용 조건을 확인해 주세요.',
    'mission_key_missing': '서버 환경에 Gemini 및 YouTube 키가 설정되어 있는지 확인해 주세요.',
    'mission_key_binding_mismatch': '현재 서버 키가 검토한 동의 범위에 결합된 키와 다릅니다.',
    'employee_web_key_mismatch': '서버의 YouTube 키가 서명된 동의 범위에 결합된 키와 다릅니다.',
    'gemini_provider_binding': '서버의 고정 Gemini 모델 및 엔드포인트 설정을 확인해 주세요.',
    'gemini_execution_disabled': '서버에서 Gemini 실행이 비활성화되어 있습니다.',
    'operating_consent_required': '이 미션의 서명된 외부 전송 동의가 필요합니다.',
    'consent_review_changed': '동의 제안이 달라졌습니다. 상태를 새로고침하고 현재 제안을 확인해 주세요.',
    'consent_expired': '동의 범위의 유효 시간이 지났습니다.',
    'mission_restart_forbidden': '이미 시작했거나 실행할 수 없는 미션입니다. 상태를 확인해 주세요.',
    'explicit_owner_confirmation_required': '외부 데이터 전송 및 무료 사용 정책에 명시적으로 동의해 주세요.',
    'mission_game_goal_required': '현재 컷룸 실행은 미션 01의 게임 쇼츠 목표에 연결되어 있습니다.',
    'mission_scope_mismatch': '현재 프로젝트의 미션이 달라졌습니다. 상태를 새로고침해 주세요.',
    'employee_web_policy_confirmation_required': 'YouTube Data API의 공개 검색·메타데이터 사용 정책을 확인해 주세요.',
    'consent_replay': '이미 저장된 동의가 있습니다. 현재 상태를 확인해 주세요.',
    'budget_local_account_required': '서버의 계정 프로젝트 ID·무료 조건 확인 설정이 필요합니다. 키를 화면에 입력하지 마세요.',
    'budget_new_project_only': '미운영 새 프로젝트만 등록할 수 있습니다. 기존 프로젝트를 변환하지 않습니다.',
    'budget_sixty_second_path_only': '현재 예산 모드는 길이를 60초로 지정한 새 대본 프로젝트에만 연결됩니다.',
    'budget_setup_already_decided': '이미 준비·결정된 등록입니다. 최신 상태를 확인해 주세요.',
    'budget_approval_required': 'AI 사용 예산이 부족합니다. 예산 요청을 검토해 주세요.',
    'budget_continue_forbidden': '실패·미확정 작업은 자동 재개할 수 없습니다.',
    'budget_review_changed': '검토한 예산 요청이 변경됐습니다. 새로고침 후 확인해 주세요.',
    'budget_or_consent_expired': '예산 요청 또는 외부 전송 동의가 만료됐습니다.',
    'budget_decision_replay': '이미 처리했거나 유효하지 않은 예산 요청입니다.',
    'representative_stage_mismatch': '현재 단계에서는 실행할 수 없습니다. 최신 상태를 확인해 주세요.',
    'stale_representative_report': '검토한 버전이 최신 보고서와 다릅니다. 새로고침 후 확인해 주세요.',
    'representative_artifact_changed': '파일 또는 검증 기록의 해시가 달라 작업이 차단됐습니다.',
    'representative_artifact_missing': '영상이나 검증 파일이 없습니다.',
    'representative_render_uncertain': '이전 로컬 렌더의 결과가 미확정입니다.',
    'representative_plan_approval_required': '기획·대본에 대한 대표 승인이 필요합니다.',
    'project_busy': '이 프로젝트에서 작업 중입니다. 잠시 후 최신 상태를 확인해 주세요.',
    'rework_fixed_model_required': '고정 무료 Gemini 모델 설정이 일치하지 않습니다. 기존 환경변수 값을 확인해 주세요.',
    'rework_key_changed': '저장된 이전 작업과 현재 Gemini 키가 일치하지 않습니다. 기존 키를 임의 변경하지 마세요.',
    'quality_revision_uncertain_transport': '과거 요청에 확정되지 않은 실행 기록이 있어 새 작업 준비가 차단됐습니다. 기록 확인이 필요합니다.',
    'quality_revision_history_invalid': '이전 작업의 동의·서명·입력 무결성 검증이 일치하지 않습니다. 기존 기록을 변경하지 마세요.',
    'rework_orphan_exists': '동일한 대표 지시에 대한 미연결 작업 파일이 있어 중복 생성을 차단했습니다.',
    'quality_revision_report_changed': '대표 지시의 기준이 된 이전 검토 보고서가 변경되어 새 작업 준비를 차단했습니다.',
    'rework_source_changed': '기존 작업과 원본 프로젝트의 연결 정보가 달라 새 작업을 준비할 수 없습니다.',
    'rework_parent_changed': '기존 실패 작업의 보존 기록이 달라져 새 작업을 준비할 수 없습니다.',
    'rework_script_reuse_not_proven': '이전 기획·대본·검토 기록이 안전한 재사용 기준을 충족하지 않습니다. 기존 작업을 다시 실행하지 마세요.',
    'rework_script_reuse_changed': '원래 대본의 검사 결과가 바뀌어 복구 준비를 중단했습니다. 과거 파일을 변경하지 마세요.',
    'rework_recovery_seed_mismatch': '대본 수정 전용 신규 작업의 자료 출처·시작 상태가 일치하지 않아 실행을 차단했습니다.',
    'rework_recovery_source_changed': '대표 보고 전에 재사용한 원본의 검증·출처 기록이 달라져 결과 제출을 차단했습니다.',
    'rework_pending_cap_required': '동의 전 작업만 호출 상한을 갱신할 수 있습니다. 최신 상태를 확인해 주세요.',
    'rework_pending_proposal_changed': '기존 동의 제안과 작업 상태가 달라져 호출 상한 갱신을 차단했습니다.',

    'invalid_text': '필수 입력과 글자 수를 확인해 주세요.',
    'invalid_fields': '입력 형식을 확인해 주세요.',
    'readonly_project': '기존 검증 사례는 읽기 전용입니다.',
    'invalid_request': '요청 형식이 올바르지 않습니다.',
    'invalid_creation_key': '프로젝트 생성 요청을 확인해 주세요.',
    'mission_game_duration_is_manager_decision': '게임 쇼츠 미션은 관리자가 길이를 정합니다. 프로젝트에서 길이 입력을 비워 주세요.',
    'mission_duration_requires_60': '미션 01은 60초 대본 범위입니다. 새 목표에서 길이를 60초로 설정해 주세요.',
    'mission_provider_result_required': '실행 권한을 받은 미션의 내부 검토 결과가 필요합니다.',
    'representative_render_spec_pending': '이 기획의 제작 사양은 아직 등록되지 않았습니다.',
    'local_tool_failed': '로컬 렌더 도구 실행에 실패했습니다. 제작 시도 기록을 확인해 주세요.',
}


def byte_range(header, size):
    if header is None:
        return 0, size - 1
    match = re.fullmatch(r'bytes=(\d{0,18})-(\d{0,18})', header)
    if not match or not any(match.groups()):
        raise ValueError
    first, last = match.groups()
    if not first and int(last) == 0:
        raise ValueError
    start = int(first) if first else max(0, size - int(last))
    end = min(size - 1, int(last)) if first and last else size - 1
    if start > end:
        raise ValueError
    return start, end


class Studio:
    def __init__(self, writable, references=()):
        self.stores = {'workspace': Store(writable),
                       **{f'reference-{index}': Store(root) for index, root in enumerate(references)}}
        require(len({store.root for store in self.stores.values()}) == len(self.stores), 'studio_store_overlap')
        self.workflow = RepresentativeVideoWorkflow(self.stores['workspace'])
        self.token = secrets.token_urlsafe(32)
        self.creation_lock = threading.Lock()
        self.mission_lock = threading.Lock()
        self.mission_proposals = {}
        self.mission_workers = set()
        self.mission_errors = {}
        self.budget_company_factory = None

    def projects(self, key):
        store = self.stores[key]
        for path in store.root.glob('company-*.json'):
            if re.fullmatch(PROJECT, path.stem):
                yield store.load(path.stem)

    def project(self, key, pid):
        if key not in self.stores or not re.fullmatch(PROJECT, pid):
            raise FileNotFoundError
        project = self.stores[key].load(pid)
        if 'representative' not in project:
            raise FileNotFoundError
        return project

    def card(self, key, p):
        flow = p['representative']
        video = flow['video_versions'][-1] if flow['video_versions'] else None
        prefix = f'/media/{key}/{p["id"]}'
        return dict(id=p['id'], store=key, goal=p['goal'], updated_at=p['updated_at'], stage=flow['stage'],
                    readonly=key != 'workspace', simulation=p['simulation'], audience=flow['audience'],
                    thumbnail=f'{prefix}/{video["version"]}/thumbnail' if video else None,
                    budget_pending=sum(r['status']=='pending' for r in self.budget_ledger().view(flow['budget_job'])['requests']) if key=='workspace' and flow.get('budget_job') else 0,
                    plans=len(flow['plan_versions']), videos=len(flow['video_versions']),
                    render_status=flow['render_attempts'][-1]['status'] if flow['render_attempts'] else None)

    def dashboard(self):
        cards, deferred = [], []
        for key in self.stores:
            for p in self.projects(key):
                if 'representative' in p:
                    cards.append(self.card(key, p))
                if 'topic_reference_disposition' in p:
                    deferred.append(p['topic_reference_disposition'])
        return dict(projects=sorted(cards, key=lambda p: p['updated_at'], reverse=True),
                    deferred=deferred, token=self.token)

    def detail(self, key, pid):
        p = self.project(key, pid)
        flow = deepcopy(p['representative'])
        flow.pop('scoped_experiences', None)
        flow.pop('creation_key', None)
        flow.pop('budget_setup', None)
        for video in flow['video_versions']:
            prefix = f'/media/{key}/{pid}/{video["version"]}'
            video.update(url=prefix+'/video', thumbnail=prefix+'/thumbnail')
            video.pop('artifact', None)
        flow.pop('final_video', None)
        store = self.stores[key]
        jobs = [store.load(job_id) for job_id in flow['planning_jobs']]
        mission = None
        if flow.get('mission_one_job'):
            from video_mission_one import MissionOneStore, provider_view
            provider_store = MissionOneStore(store.root/'mission_one_provider')
            job = provider_store.load(flow['mission_one_job'])
            mission = provider_view(job)
            if key == 'workspace' and flow['stage'] == 'research_planning':
                mission.update(self.mission_controls(p, provider_store, job))
        from cutroom_review import revision_draft
        draft = revision_draft(store.root, p) if key == 'workspace' else None
        production = self.mission_production(p) if key=='workspace' and mission else None
        from mission_production import production_status
        autonomous_production = production_status(self.workflow,p) if production else None
        from research_workflow import status as research_status
        research=research_status(self.workflow,p) if key=='workspace' and mission else None
        return {**self.card(key, p), 'research':research, 'flow': flow, 'mission': mission, 'budget': self.budget_detail(key,p), 'budget_setup': self.budget_setup_view(key,p), 'rework': self.rework_view(key,p), 'revision_draft': draft, 'production': production,
                'autonomous_production': autonomous_production,
                'jobs': [dict(id=j['id'], status=j['status'], reason=j.get('reason_code'),
                              assignments=[dict(role=t['role'], state=t['state'], versions=len(t['versions']))
                                           for t in j['assignments']]) for j in jobs]}

    def mission_production(self, project):
        from shutil import which
        from local_melo_tts import MeloLocal
        from production_video import portrait_font
        from video_production_company import approved_portrait_direction
        flow=project['representative']
        if flow['stage'] not in ('production','video_revision') or not flow['plan_versions']:
            return None
        plan=flow['plan_versions'][-1]
        if plan['render_spec'] is not None:
            return None
        try:
            self.workflow.mission_production_spec(flow,plan['version'],plan['sha256'],'none')
        except CompanyError as exc:
            return dict(ready=False,reason=exc.code)
        board=next(json.loads(t['versions'][-1]['content']) for t in plan['task_history'] if t['role']=='editor')
        ready=bool(which('ffmpeg') and which('ffprobe') and portrait_font())
        uncertain=any(a['status']=='reserved' for a in flow['render_attempts'])
        return dict(ready=ready and not uncertain,local_speech=ready and MeloLocal().available(),
                    reason='representative_render_uncertain' if uncertain else
                    None if ready else 'portrait_preview_tools_missing',
                    direction=approved_portrait_direction(project,plan,board))

    def rework_view(self,key,p):
        if key!='workspace':return None
        flow=p['representative'];state=flow.get('rework')
        if not state:
            return dict(status='available',feedback=flow['decisions'][-1]['feedback']) if flow['stage']=='plan_revision' and flow['plan_versions'] else None
        from representative_rework import (ReworkStore, check_finalization_recovery, execution_settings,
                                            progress_view, failed_plan_reference)
        provider=ReworkStore(self.stores[key].root/'representative_rework')
        job=provider.load(state['job'])
        settings=execution_settings();recovery=dict(eligible=False,error=None)
        if state['status']=='stopped' and state.get('error')=='gemini_execution_disabled':
            try:
                ReworkStore(self.stores[key].root/'representative_rework').verify_disabled_recovery(job,state,os.getenv('GEMINI_API_KEY',''))
                recovery['eligible']=True
            except CompanyError as exc:recovery['error']=exc.code
        new_attempt=None
        if state['status']=='stopped' and p['representative']['stage']=='plan_revision':
            try:new_attempt=failed_plan_reference(ReworkStore(self.stores[key].root/'representative_rework'),p,os.getenv('GEMINI_API_KEY',''))
            except CompanyError:pass
        progress=progress_view(job,state)
        final_recovery=None
        if state.get('status')=='stopped' and state.get('error')=='invalid_checks' and job.get('phase')=='finalize':
            try:
                check_finalization_recovery(p,provider,job)
                final_recovery=dict(eligible=True,job=job['id'],state_hash=job['storage_hash'])
            except CompanyError as exc:
                final_recovery=dict(eligible=False,error=exc.code)
        from representative_rework import legacy_quality_report,review_recovery_audit
        audit=review_recovery_audit(job,state)
        if audit and audit['kind']=='editor_handoff_after_mismatch':
            progress['title']='편집 인계 중단 · 스토리보드 재검토 준비'
            progress['message']='수락된 대본과 관리자 검토를 보존했습니다. 새 작업은 시스템 스토리보드 검토부터 시작합니다.'
            progress['next_action']='스토리보드 관리자 검토 준비에서 새 동의 범위를 확인하세요.'
        elif audit and audit['kind']=='manager_review_after_repeat':
            progress['title']='중복 응답 중단 · 관리자 재검토 준비'
            progress['message']='검증된 첫 대본을 보존했습니다. 이전의 인용 오류는 대본 결함으로 확정되지 않았습니다.'
            progress['next_action']='기존 대본 관리자 재검토 준비에서 새 동의 범위를 검토하세요.'
        elif audit:
            progress['title']='기존 대본·관리자 검토 보존 확인'
            progress['message']='대본 검토는 내부 검증에서 중단됐습니다. 이전 호출을 반복하지 않고 저장된 자료의 재사용 가능성을 확인합니다.'
            progress['next_action']='실패 작업은 자동 재실행하지 않습니다. 저장된 대본과 검토 근거를 확인하고 별도 복구 경로를 검토합니다.'
        legacy=legacy_quality_report(job,state)
        if legacy:
            progress['quality_report']=legacy
            progress['title']='대표 판단 필요 · 과거 검토 실패 보고'
            progress['message']='마지막 관리자 검토는 HTTP 200이지만 검증되지 않았습니다. 저장된 대본은 승인된 결과가 아닙니다.'
            progress['next_action']='저장된 대본을 읽고 대표가 새 수정 지시 또는 보류를 기록하세요. 과거 검토를 수락 처리하지 않습니다.'
        if new_attempt:
            progress['next_action']='새 AI 재작업 준비를 눌러 새 전송 범위를 검토·동의한 뒤 시작하세요. 기존 실패 업무는 다시 실행하지 않습니다.'
        from cutroom_review import quality_draft
        return dict(status=state['status'],job=state['job'],error=state.get('error'),settings=settings,recovery=recovery,
            new_attempt=new_attempt,history=[dict(job=x['job'],status=x['status'],error=x.get('error')) for x in flow.get('rework_history',[])],
            feedback=job['quality_inputs']['feedback_text'],proposal=state.get('proposal'),
            review_hash=digest(state['proposal']) if state.get('proposal') else None,
            job_status=job['status'],attempts=len(job['real_ai']['attempts']),final_recovery=final_recovery,
            replan=job.get('rework_plan'),reviews=job.get('goal_reviews',[]),progress=progress,
            quality_decision=state.get('quality_decision'),
            recovery_audit=audit,
            quality_report_hash=digest(progress['quality_report']) if progress.get('quality_report') else None,
            quality_draft=quality_draft(self.stores[key].root, p, job['id'], progress.get('quality_report')),
            quality_script=next((json.loads(t['versions'][-1]['content']).get('transcript','')
                 for t in job.get('assignments',[]) if t['role']=='writer' and t.get('versions')),None))

    def rework_quality_decide(self,pid,body):
        """Record an owner decision; never resume or reuse a failed transport."""
        exact(body,('job','report_hash','action','feedback'))
        require(body['action'] in ('request_revision','hold'),'invalid_quality_decision')
        require(isinstance(body['feedback'],str) and len(body['feedback'])<=2000
                and (body['action']=='hold' or bool(body['feedback'].strip())),
                'invalid_quality_feedback')
        from representative_rework import ReworkStore,progress_view,legacy_quality_report
        with self.stores['workspace'].lock(pid):
            project=self.stores['workspace'].load(pid)
            flow=project['representative'];state=flow.get('rework')
            require(flow['stage']=='plan_revision' and state is not None
                    and state['status']=='stopped' and state['job']==body['job'],
                    'quality_decision_not_pending')
            job=ReworkStore(self.stores['workspace'].root/'representative_rework').load(body['job'])
            progress=progress_view(job,state)
            report=legacy_quality_report(job,state) or progress.get('quality_report')
            require(report is not None and report.get('decision')=='stop'
                    and body['report_hash']==digest(report),'quality_report_changed')
            prior=state.get('quality_decision')
            require(prior is None,'quality_decision_already_recorded')
            state['quality_decision']=dict(action=body['action'],feedback=body['feedback'],
                report_hash=digest(report),job=body['job'],at=now(),
                requires_new_consent=body['action']=='request_revision')
            self.stores['workspace'].save(project)

    @staticmethod
    def mission_unstarted(job):
        return (job['status'] == 'ready' and not job['sessions']
                and not job['real_ai']['attempts'] and not job['active_operation'])

    def mission_controls(self, project, store, job):
        from video_mission_one import GAME_GOAL, MISSION_ACCOUNT, WEB_TOOL
        jid = job['id']
        with self.mission_lock:
            proposal = self.mission_proposals.get(jid)
            running = jid in self.mission_workers
            error = self.mission_errors.get(jid)
        eligible = self.mission_unstarted(job) and not running and not error
        consent_file = store._grant_path(jid).exists()
        unsigned = eligible and not consent_file and not job['real_ai']['consent']
        connected = job['quality_inputs']['capabilities'].get('employee_web_research') == WEB_TOOL
        supported = project['goal'] == GAME_GOAL
        review = None
        if (unsigned and proposal and proposal['initial_state_hash'] == job['storage_hash']
                and proposal['expires_at'] > now()):
            account, web = proposal['mission_account'], proposal['mission_web']
            review = dict(review_hash=digest(proposal), expires_at=proposal['expires_at'],
                          model=proposal['model'], endpoint=proposal['endpoint'],
                          limits=proposal['limits'], max_cost=proposal['max_cost'],
                          account_project=account['account_project'], youtube_project=web['account_project'],
                          remaining_requests=account['remaining_requests'], search_remaining=web['search_remaining'],
                          units_remaining=web['general_units_remaining'], searches=web['approved_max_searches'],
                          videos=web['approved_max_videos'],
                          metadata_retention_days=web['policy']['api_metadata_retention_days'],
                          constraints=proposal['quality_contract']['inputs']['constraints'],
                          cross_research=proposal.get('mission_cross_research'))
        return dict(account_project=MISSION_ACCOUNT, supported=supported, proposal=review, running=running,
                    execution_error=error or ('mission_consent_incomplete' if eligible and consent_file
                                              and not job['real_ai']['consent'] else None),
                    can_connect=supported and unsigned and not connected,
                    can_prepare=supported and unsigned and connected,
                    can_run=supported and connected and eligible and consent_file
                    and job['real_ai']['consent'].get('approved') is True,
                    can_report=supported and not running and job['status'] == 'needs_user_review')

    def mission_action(self, pid, name, body):
        from autonomous_gemini35 import ENDPOINT, MODEL, Gemini35Config
        from autonomous_live import LiveEmployeeProvider, LiveManagerProvider
        from video_mission_one import GAME_GOAL, MISSION_ACCOUNT, MissionOneCompany, MissionOneStore, WEB_TOOL, _binding
        fields = {
            'mission-prepare': ('account_project', 'confirm_free_account', 'confirm_youtube_policy'),
            'mission-consent': ('review_hash', 'confirm_free_data_policy'),
        }
        exact(body, ('job', *fields.get(name, ())))
        require(isinstance(body['job'], str), 'mission_scope_mismatch')
        store = MissionOneStore(self.workflow.store.root/'mission_one_provider')
        if name == 'mission-connect-web':
            self.workflow.connect_employee_web(pid, expected_job=body['job'])
            return
        if name == 'mission-report':
            self.workflow.report_plan(pid, provider_store=store, expected_mission_job=body['job'])
            return

        with self.mission_lock, self.workflow.store.lock(pid):
            project = self.workflow.store.load(pid)
            flow = project['representative']
            jid = flow.get('mission_one_job')
            require(jid and jid == body['job'] and flow['stage'] == 'research_planning', 'mission_scope_mismatch')
            require(project['goal'] == GAME_GOAL, 'mission_game_goal_required')
            job = store.load(jid)
            require(job['quality_inputs']['capabilities'].get('employee_web_research') == WEB_TOOL,
                    'mission_independent_web_research_unavailable')
            require(self.mission_unstarted(job) and jid not in self.mission_workers and jid not in self.mission_errors,
                    'mission_restart_forbidden')
            config = Gemini35Config.from_env()
            require(config.model == MODEL and config.endpoint == ENDPOINT, 'gemini_provider_binding')
            youtube_key = os.getenv('YOUTUBE_DATA_API_KEY', '')
            if name != 'mission-run':
                require(not job['real_ai']['consent'] and not store._grant_path(jid).exists(), 'consent_replay')
                if name == 'mission-prepare':
                    require(body['account_project'] == MISSION_ACCOUNT and body['confirm_free_account'] is True,
                            'mission_free_account_unverified')
                    self.mission_proposals[jid] = store.prepare_mission(jid, key=config.api_key,
                        account_project=MISSION_ACCOUNT, quota_note='Provider quota unknown; owner attestation only.',
                        youtube_key=youtube_key, youtube_project=MISSION_ACCOUNT,
                        confirm_youtube_policy=body['confirm_youtube_policy'])
                    return
                proposal = self.mission_proposals.get(jid)
                require(body['confirm_free_data_policy'] is True, 'explicit_owner_confirmation_required')
                require(proposal and body['review_hash'] == digest(proposal), 'consent_review_changed')
                require(hmac.compare_digest(proposal['mission_account']['credential_binding'], _binding(jid, config.api_key))
                        and hmac.compare_digest(proposal['mission_web']['credential_binding'], _binding(jid+':youtube', youtube_key)),
                        'mission_key_binding_mismatch')
                store.approve(jid, proposal, review_hash=body['review_hash'], owner_confirmed=True)
                del self.mission_proposals[jid]
                return

            company = MissionOneCompany(store, LiveManagerProvider('gemini-manager'),
                                        LiveEmployeeProvider('gemini-staff'), config)
            grant = company._preflight(job)['body']
            require(grant['mission_account']['account_project'] == grant['mission_web']['account_project'] == MISSION_ACCOUNT,
                    'mission_free_account_unverified')
            self.mission_workers.add(jid)

        def worker():
            error = None
            try:
                result = company.run(jid, expected_state_hash=job['storage_hash'])
                if result['status'] == 'needs_user_review':
                    self.workflow.report_plan(pid, provider_store=store, expected_mission_job=jid)
                else:
                    error = result.get('reason_code') or 'mission_internal_review_incomplete'
            except CompanyError as exc:
                error = exc.code
            except Exception:
                error = 'mission_internal_error'
            finally:
                with self.mission_lock:
                    if error:
                        self.mission_errors[jid] = error
                    self.mission_workers.remove(jid)
        try:
            threading.Thread(target=worker, daemon=True).start()
        except RuntimeError:
            with self.mission_lock:
                self.mission_workers.discard(jid)
            raise CompanyError('mission_worker_unavailable') from None

    def rework_action(self,pid,name,body):
        from representative_rework import prepare,ReworkStore,ReworkCompany,handoff,execution_settings,rework_call_cap
        from autonomous_gemini35 import Gemini35Config,MODEL,ENDPOINT
        from video_mission_one import MISSION_ACCOUNT,_binding
        config=Gemini35Config.from_env()
        preparing=name in ('rework-prepare','rework-new-prepare','rework-quality-prepare',
                           'rework-script-recover-prepare','rework-cap-prepare','rework-consent')
        if preparing:
            # Preparing a proposal does not execute Gemini. Missing runtime
            # model/endpoint env must not block drafting a fixed free-model scope.
            # Explicitly configured mismatches remain forbidden.
            require(os.getenv('GEMINI35_MODEL') in (None,'',MODEL)
                    and os.getenv('GEMINI35_ENDPOINT') in (None,'',ENDPOINT),
                    'rework_fixed_model_required')
        else:
            require(config.model==MODEL and config.endpoint==ENDPOINT,
                    'rework_fixed_model_required')
        _binding('rework-local',config.api_key)
        if name=='rework-cap-prepare':
            exact(body,())
            from representative_rework import cap_pending_proposal
            cap_pending_proposal(self.workflow,pid,config.api_key)
            return
        if preparing and name!='rework-consent':
            followup=name=='rework-quality-prepare'
            script_recovery=name=='rework-script-recover-prepare'
            exact(body,('account_project','confirm_free_account','previous_job')
                  if name in ('rework-new-prepare','rework-quality-prepare','rework-script-recover-prepare')
                  else ('account_project','confirm_free_account'))
            require(body['confirm_free_account'] is True and body['account_project']==MISSION_ACCOUNT,'rework_free_project_required')
            prepare(self.workflow,pid,config.api_key,body['account_project'],
                previous_job=body['previous_job'] if name!='rework-prepare' else None,
                quality_decision=followup,script_recovery=script_recovery)
            return
        provider=ReworkStore(self.stores['workspace'].root/'representative_rework')
        with self.stores['workspace'].lock(pid):
            project=self.project('workspace',pid);state=project['representative'].get('rework')
            require(state is not None,'rework_prepare_required')
            if name=='rework-consent':
                cap=rework_call_cap(provider.load(state['job']))
                require(state.get('proposal',{}).get('limits',{}).get('max_calls')==cap,
                        'rework_pending_cap_required')
                exact(body,('review_hash','confirm_free_account','confirm_data_policy'))
                require(state['status']=='pending' and body['confirm_free_account'] is True and body['confirm_data_policy'] is True
                        and body['review_hash']==digest(state['proposal']),'rework_consent_required')
                require(state['proposal']['rework_scope']['credential_binding']==_binding(state['job'],config.api_key),'rework_key_changed')
                provider.approve(state['job'],state['proposal'],review_hash=body['review_hash'],owner_confirmed=True)
                state['status']='approved';self.stores['workspace'].save(project);return
            exact(body,())
            recovery=name=='rework-recover'
            require(recovery or name=='rework-run' and state['status']=='approved','rework_duplicate_or_unapproved')
            require(execution_settings()['ready'],'rework_execution_settings_required')
            job=provider.load(state['job'])
            if recovery:
                grant=provider.verify_disabled_recovery(job,state,config.api_key)
                state.setdefault('recovery_events',[]).append(dict(at=now(),reason='gemini_execution_disabled_zero_send',
                    previous_status=state['status'],previous_error=state['error'],job_hash=job['storage_hash'],
                    grant_id=grant['id'],scope_hash=digest(grant['body'])))
            else:
                provider.grant(job);provider.require_unstarted(job)
            require(state['proposal']['rework_scope']['credential_binding']==_binding(job['id'],config.api_key),'rework_key_changed')
            cap=rework_call_cap(job)
            require(job['limits'].get('max_calls')==cap
                    and state['proposal']['limits'].get('max_calls')==cap,
                    'rework_pending_cap_required')
            state['status']='running';self.stores['workspace'].save(project)
        def worker():
            try:
                from autonomous_live import LiveManagerProvider,LiveEmployeeProvider
                company=ReworkCompany(provider,LiveManagerProvider('gemini-manager'),LiveEmployeeProvider('gemini-staff'),config)
                result=company.run(job['id'],expected_state_hash=job['storage_hash'])
                if result['status']=='needs_user_review':handoff(self.workflow,pid,provider);return
                error=result.get('reason_code','rework_incomplete')
            except Exception as exc:
                error=exc.code if isinstance(exc,CompanyError) else 'rework_internal_error'
            with self.stores['workspace'].lock(pid):
                project=self.stores['workspace'].load(pid)
                project['representative']['rework'].update(status='stopped',error=error)
                self.stores['workspace'].save(project)
        from threading import Thread
        Thread(target=worker,daemon=True).start()

    def budget_store(self):
        from budget_video_provider import BudgetVideoStore
        return BudgetVideoStore(self.stores['workspace'].root/'budget_provider')

    def budget_ledger(self):
        from project_budget_ledger import ProjectBudgetLedger
        return ProjectBudgetLedger(self.stores['workspace'].root/'project_budgets')

    def enable_budget(self, pid, provider_job):
        """Trusted explicit provisioning after separate provider approval, new projects only."""
        store = self.stores['workspace']
        with store.lock(pid):
            p = self.project('workspace',pid)
            self._enable_budget_locked(p,provider_job)

    @staticmethod
    def _new_budget_project(p):
        flow=p['representative']
        require(flow['stage']=='goal_submitted' and not flow.get('mission_one_job')
                and not flow['planning_jobs'] and not flow['plan_versions'] and not flow['video_versions']
                and not flow['render_attempts'] and not flow.get('budget_job')
                and not p['attempts'] and not p['assignments'] and not p['artifacts'], 'budget_new_project_only')
        require(flow['constraints'].get('duration_seconds')==60,'budget_sixty_second_path_only')

    def _enable_budget_locked(self,p,provider_job):
        self._new_budget_project(p)
        provider=self.budget_store()
        job=provider.load(provider_job)
        require(job['goal']==p['goal'] and job['quality_inputs']['answers']['representative_project']==p['id']
                and job['status']=='ready' and not job['real_ai']['attempts'],'budget_project_mismatch')
        ledger=self.budget_ledger()
        scope=provider.budget_scope(job)
        if ledger._path(provider_job).exists():
            existing=ledger._load(provider_job)
            require(digest(existing['scope'])==digest(scope) and not existing['approvals'] and not existing['attempts'],'budget_project_mismatch')
        else:
            ledger.create(provider_job,scope=scope)
        p['representative']['budget_job']=provider_job
        self.workflow._transition(p,'research_planning')

    @staticmethod
    def _budget_project_binding(p):
        return digest(dict(goal=p['goal'],audience=p['representative']['audience'],
                           constraints=p['representative']['constraints']))

    @staticmethod
    def _budget_environment(account):
        from autonomous_gemini35 import MODEL,ENDPOINT
        require(bool(os.getenv('BUDGET_GEMINI_ACCOUNT_PROJECT'))
                and account==os.getenv('BUDGET_GEMINI_ACCOUNT_PROJECT')
                and os.getenv('BUDGET_GEMINI_FREE_ACCOUNT_CONFIRMED')=='1','budget_local_account_required')
        require(os.getenv('GEMINI35_MODEL')==MODEL and os.getenv('GEMINI35_ENDPOINT')==ENDPOINT,
                'budget_provider_scope_invalid')
        from budget_video_provider import _binding
        key=os.getenv('GEMINI_API_KEY','')
        _binding('local-configuration-check',key)  # Validate before creating any pending provider job.
        return key

    def budget_setup_view(self,key,p):
        if key!='workspace':
            return None
        setup=p['representative'].get('budget_setup')
        if not setup:
            try:
                self._new_budget_project(p)
            except CompanyError:
                return None
            return dict(status='available',local_setup='서버 로컬 환경의 기존 GEMINI_API_KEY와 고정 모델/엔드포인트를 사용합니다. 키를 화면에 입력하지 마세요. 소유자가 계정 ID를 BUDGET_GEMINI_ACCOUNT_PROJECT에, 결제 미연결·무료 확인을 BUDGET_GEMINI_FREE_ACCOUNT_CONFIRMED=1로 설정한 뒤 다시 준비하세요. 이 설정은 독립 공급자 검증이 아닙니다.')
        body=setup['proposal']
        status=self._budget_setup_state(setup)
        return dict(status=status,previous_status=setup['status'],history_count=len(p['representative'].get('budget_setup_history',[])),provider_job=setup['job'],review_hash=digest(body),
            model=body['model'],endpoint=body['endpoint'],goal=p['goal'],
            account_project=body['budget_binding']['account_project'],free_only=body['free_only'],
            data_policy=body['budget_binding']['data_policy'],data_scopes=body['scopes'],
            inputs=body['quality_contract']['inputs'],expires_at=body['expires_at'],
            responsibility='사용자가 키 소속 프로젝트와 결제 미연결·무료 조건을 확인합니다. 예산 승인은 별도이며 모델·계정·데이터 변경에는 새 동의가 필요합니다.')

    @staticmethod
    def _budget_setup_state(setup):
        if setup['status']=='pending':
            from project_budget_ledger import ProjectBudgetLedger
            try:
                ProjectBudgetLedger._future(setup['proposal']['expires_at'])
            except CompanyError:
                return 'expired'
        return setup['status']

    def budget_prepare(self,pid,body,*,renew=False):
        exact(body,('account_project','confirm_free_account','review_hash') if renew else ('account_project','confirm_free_account'))
        require(body['confirm_free_account'] is True,'explicit_provider_confirmation_required')
        key=self._budget_environment(body['account_project'])
        from script_quality import SCRIPT_CONTRACT
        with self.stores['workspace'].lock(pid):
            p=self.project('workspace',pid)
            self._new_budget_project(p)
            previous=p['representative'].get('budget_setup')
            if renew:
                require(previous is not None and self._budget_setup_state(previous) in ('expired','rejected'),
                        'budget_reprepare_forbidden')
                require(body['review_hash']==digest(previous['proposal']) and
                        previous['project_binding']==self._budget_project_binding(p), 'budget_review_changed')
                require(not self.budget_store()._grant_path(previous['job']).exists(), 'budget_reprepare_forbidden')
            elif previous:
                require(previous['status']=='pending' and previous['proposal']['budget_binding']['account_project']==body['account_project'],
                        'budget_setup_already_decided')
                return  # Identical preparation is persistently idempotent, never refreshes expiry.
            flow=p['representative']
            provider=self.budget_store()
            job=provider.create(p['goal'],inputs=dict(domain='video',target_segment=flow['audience'],
                answers=dict(audience=flow['audience'],representative_project=pid),constraints=deepcopy(flow['constraints']),
                capabilities=dict(script_contract=SCRIPT_CONTRACT),experiences=[],feedback_text=''))
            proposal=provider.prepare_budget(job['id'],key=key,account_project=body['account_project'])
            if renew:
                archived=deepcopy(previous)
                archived.update(closed_state=self._budget_setup_state(previous),superseded_at=now())
                flow.setdefault('budget_setup_history',[]).append(archived)
            flow['budget_setup']=dict(status='pending',job=job['id'],proposal=proposal,
                                     project_binding=self._budget_project_binding(p))
            self.stores['workspace'].save(p)

    def budget_consent(self,pid,body):
        exact(body,('review_hash','action'))
        require(body['action'] in ('approve','reject'),'invalid_request')
        with self.stores['workspace'].lock(pid):
            p=self.project('workspace',pid)
            self._new_budget_project(p)
            setup=p['representative'].get('budget_setup')
            require(setup is not None and setup['status']=='pending','budget_setup_already_decided')
            require(body['review_hash']==digest(setup['proposal']) and setup['project_binding']==self._budget_project_binding(p),
                    'budget_review_changed')
            provider=self.budget_store()
            if body['action']=='reject':
                setup.update(status='rejected',decided_at=now())
                self.stores['workspace'].save(p)
                return
            from budget_video_provider import _binding
            proof=setup['proposal']['budget_binding']
            key=self._budget_environment(proof['account_project'])
            require(secrets.compare_digest(proof['credential_binding'],_binding(setup['job'],key)),
                    'budget_provider_key_mismatch')
            job=provider.load(setup['job'])
            provider._check_contract(job,setup['proposal'])  # Includes existing KST expiry and exact inputs.
            if provider._grant_path(setup['job']).exists():
                require(digest(provider.grant(job)['body'])==body['review_hash'],'budget_review_changed')
            else:
                provider.approve(setup['job'],setup['proposal'],review_hash=body['review_hash'],owner_confirmed=True)
            setup.update(status='approved',decided_at=now())
            self._enable_budget_locked(p,setup['job'])

    def propose_budget(self, pid, amounts, **estimate):
        """Internal manager estimate input, never a public representative approval endpoint."""
        p = self.project('workspace',pid)
        require(bool(p['representative'].get('budget_job')), 'budget_not_enabled')
        return self.budget_ledger().request(p['representative']['budget_job'],amounts,**estimate)

    def budget_detail(self, key, p):
        job_id = p['representative'].get('budget_job')
        if not job_id or key!='workspace':
            return None
        provider = self.budget_store()
        job = provider.load(job_id)
        ledger = self.budget_ledger()
        from project_budget import digest
        result = ledger.view(job_id)
        try:
            provider.grant(job)
            consent_state='valid'
        except CompanyError as exc:
            consent_state=exc.code
        result.update(scope=ledger._load(job_id)['scope'], provider_status=job['status'], reason=job.get('reason_code'), consent_state=consent_state)
        for request in result['requests']:
            request['review_hash']=digest(request)
        return result

    def create(self, body):
        exact(body, ('goal', 'audience', 'language', 'platform', 'duration', 'notes', 'key'))
        require(isinstance(body['key'], str) and re.fullmatch(r'[a-f0-9-]{36}', body['key']),
                'invalid_creation_key')
        for field in ('goal', 'audience', 'language', 'platform', 'notes'):
            require(isinstance(body[field], str), 'invalid_request')
        require(all(len(body[k]) <= 300 for k in ('audience', 'language', 'platform')) and
                len(body['notes']) <= 2000 and
                (body['duration'] is None or type(body['duration']) is int and 1 <= body['duration'] <= 120),
                'invalid_request')
        constraints = {k: body[k].strip() for k in ('language', 'platform', 'notes') if body[k].strip()}
        if body['duration'] is not None:
            constraints['duration_seconds'] = body['duration']
        with self.creation_lock:
            for p in self.projects('workspace'):
                if p.get('representative', {}).get('creation_key') == body['key']:
                    return {'id': p['id']}
            pid = self.workflow.create(body['goal'].strip(), audience=body['audience'].strip() or '미정',
                                       constraints=constraints, creation_key=body['key'])
        return {'id': pid}

    def action(self, key, pid, name, body):
        self.project(key, pid)
        require(key == 'workspace', 'readonly_project')
        if name=='rework-quality-decide':
            self.rework_quality_decide(pid,body)
        elif name=='rework-finalize-recover':
            from representative_rework import recover_finalization
            recover_finalization(self.workflow,pid,body)
        elif name in RESEARCH_ACTIONS:
            from research_workflow import action as research_action
            research_action(self.workflow,pid,name,body)
        elif name in MISSION_ACTIONS:
            self.mission_action(pid, name, body)
        elif name in ('rework-prepare','rework-new-prepare','rework-quality-prepare','rework-script-recover-prepare',
                      'rework-cap-prepare','rework-consent','rework-run','rework-recover'):
            self.rework_action(pid,name,body)
        elif name=='budget-prepare':
            self.budget_prepare(pid,body)
        elif name=='budget-reprepare':
            self.budget_prepare(pid,body,renew=True)
        elif name=='budget-consent':
            self.budget_consent(pid,body)
        elif name=='budget-revoke':
            exact(body,())
            job=self.project(key,pid)['representative'].get('budget_job')
            require(bool(job),'budget_not_enabled')
            self.budget_store().revoke(job,owner_confirmed=True)
        elif name in ('budget-decide','budget-run'):
            job_id = self.project(key,pid)['representative'].get('budget_job')
            require(bool(job_id), 'budget_not_enabled')
            if name=='budget-decide':
                exact(body,('request_id','review_hash','action'))
                self.budget_ledger().decide(job_id,**body,owner_confirmed=True)
            else:
                exact(body,())
                from budget_video_provider import BudgetVideoCompany
                from autonomous_live import LiveManagerProvider, LiveEmployeeProvider
                from autonomous_gemini35 import Gemini35Config
                provider = self.budget_store()
                company = (self.budget_company_factory(provider) if self.budget_company_factory else
                    BudgetVideoCompany(provider,LiveManagerProvider('budget-manager'),LiveEmployeeProvider('budget-staff'),Gemini35Config.from_env()))
                job = provider.load(job_id)
                company.run(job_id,expected_state_hash=job['storage_hash'],
                            resume=job['status']=='stopped' and job.get('reason_code')=='budget_approval_required')
        elif name == 'planning':
            exact(body, ())
            self.workflow.start_planning(pid)
        elif name == 'mission':
            exact(body, ())
            self.workflow.stage_mission_one(pid)
        elif name == 'decide':
            exact(body, ('stage', 'version', 'sha256', 'action', 'feedback', 'changes_plan'))
            self.workflow.decide(pid, **body)
        elif name == 'production-render':
            exact(body,('version','sha256'))
            self.workflow.produce(pid,version=body['version'],sha256=body['sha256'],
                changes='관리자 제작 계획·승인 대본과 로컬 인수 소스 결합',imported=True)
        elif name in PRODUCTION_ACTIONS:
            from mission_production import production_action
            ready=production_action(self.workflow,pid,name,body)
            if name=='production-policy-run' and ready is True:
                p=self.project(key,pid)
                plan=p['representative']['plan_versions'][-1]
                self.workflow.produce(pid,version=plan['version'],sha256=plan['sha256'],
                    changes='개인 운영 정책에 따른 기존 승인 소스·대본·음성 로컬 합성',imported=True)
        elif name == 'mission-preview':
            exact(body, ('version', 'sha256', 'audio_mode'))
            require(body['audio_mode'] in ('none','local_speech'),'invalid_request')
            self.workflow.produce(pid,version=body['version'],sha256=body['sha256'],
                changes='승인된 9:16 대본·자막의 로컬 기술 시안',preview_audio=body['audio_mode'])
        elif name == 'produce':
            exact(body, ('version', 'sha256', 'changes', 'camera'))
            require(body['camera'] in (None, 'hold', 'push_in', 'pan_right'), 'invalid_request')
            p = self.project(key, pid)
            current = p['representative']['plan_versions']
            cameras = [body['camera']] * len(current[-1]['render_spec']['scenes']) if body['camera'] and current and current[-1]['render_spec'] else None
            self.workflow.produce(pid, version=body['version'], sha256=body['sha256'],
                                  changes=body['changes'], cameras=cameras)
        else:
            raise FileNotFoundError
        return self.detail(key, pid)

    def media(self, key, pid, version, kind):
        p = self.project(key, pid)
        video = next((v for v in p['representative']['video_versions'] if v['version'] == version), None)
        if not video:
            raise FileNotFoundError
        root = self.stores[key].root
        path = root/video['artifact']
        base = root/'artifacts'/pid
        require(path.name == 'video.mp4' and path.parent.parent == base and
                re.fullmatch(r'render-[1-9]\d*', path.parent.name) and
                not any(item.is_symlink() for item in (base.parent, base, path.parent, path)),
                'representative_artifact_path')
        if kind == 'video':
            expected, mime = video['artifact_sha256'], 'video/mp4'
        else:
            frames = video['render_receipt']['review_material']
            if not frames:
                raise FileNotFoundError
            frame = frames[len(frames)//2]
            require(re.fullmatch(r'keyframe-\d{2}\.png', frame['keyframe']), 'representative_artifact_path')
            path = path.with_name(frame['keyframe'])
            expected, mime = frame['keyframe_sha256'], 'image/png'
        require(_file_hash(path) == expected, 'representative_artifact_changed')
        return path, mime


def make_server(host, port, studio):
    class Handler(BaseHTTPRequestHandler):
        def end_headers(self):
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self'; media-src 'self'; object-src 'none'; frame-ancestors 'self'; base-uri 'none'")
            super().end_headers()

        def send_bytes(self, status, payload, mime):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(payload)

        def send_json(self, status, value):
            self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

        def file(self, path, mime):
            size = path.stat().st_size
            requested = self.headers.get('Range')
            try:
                start, end = byte_range(requested, size)
            except ValueError:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            self.send_response(206 if requested else 200)
            if requested:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(end-start+1))
            self.send_header('Cache-Control', 'private, no-cache')
            self.end_headers()
            if self.command == 'HEAD':
                return
            with path.open('rb') as stream:
                stream.seek(start)
                left = end-start+1
                while left:
                    chunk = stream.read(min(left, 65536))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        def dispatch(self):
            path = urlsplit(self.path).path
            if self.command in ('GET', 'HEAD'):
                if path in STATIC:
                    name, mime = STATIC[path]
                    return self.send_bytes(200, (ASSETS/name).read_bytes(), mime+'; charset=utf-8')
                if path == '/api/studio':
                    return self.send_json(200, studio.dashboard())
                if match := re.fullmatch(rf'/api/project/([\w-]+)/({PROJECT})', path):
                    return self.send_json(200, studio.detail(*match.groups()))
                if match := re.fullmatch(rf'/media/workspace/({PROJECT})/production-voice/(scene-[1-9][0-9]{{0,2}})', path):
                    from mission_production import SceneSpeechReceipts, approved_manager_result, production_manager
                    pid, scene = match.groups()
                    manager = production_manager(studio.workflow, studio.workflow.store.load(pid))
                    audio,_ = SceneSpeechReceipts(manager, approved_manager_result(manager)).validated(scene)
                    return self.file(audio, 'audio/wav')
                if match := re.fullmatch(rf'/media/([\w-]+)/({PROJECT})/([1-9][0-9]{{0,5}})/(video|thumbnail)', path):
                    key, pid, version, kind = match.groups()
                    return self.file(*studio.media(key, pid, int(version), kind))
            elif self.command == 'POST':
                if self.headers.get('Sec-Fetch-Site') == 'cross-site' or not secrets.compare_digest(
                    self.headers.get('X-Studio-Token', '').encode('latin-1'), studio.token.encode('ascii')
                ):
                    return self.send_json(403, dict(error='이 화면에서 새로고침 후 다시 시도해 주세요.'))
                length = self.headers.get('Content-Length', '')
                require(length.isdecimal() and 0 < int(length) <= 20000 and
                        self.headers.get_content_type() == 'application/json', 'invalid_request')
                body = json.loads(self.rfile.read(int(length)))
                if path == '/api/project':
                    return self.send_json(201, studio.create(body))
                if match := re.fullmatch(rf'/api/project/workspace/({PROJECT})/plan-markdown', path):
                    from cutroom_review import matching_plan, plan_markdown
                    exact(body, ('version', 'sha256'))
                    project = studio.project('workspace', match[1])
                    plan = matching_plan(project, body['version'], body['sha256'])
                    return self.send_json(200, dict(markdown=plan_markdown(project, plan)))
                if match := re.fullmatch(rf'/api/project/([\w-]+)/({PROJECT})/(planning|mission|{"|".join(MISSION_ACTIONS+PRODUCTION_ACTIONS+RESEARCH_ACTIONS)}|decide|produce|mission-preview|budget-decide|budget-run|budget-prepare|budget-reprepare|budget-consent|budget-revoke|rework-prepare|rework-consent|rework-run|rework-recover|rework-new-prepare|rework-quality-decide|rework-quality-prepare|rework-script-recover-prepare|rework-finalize-recover|rework-cap-prepare)', path):
                    try:
                        result=studio.action(*match.groups(), body)
                    except CompanyError as exc:
                        if match[3] not in RESEARCH_ACTIONS or exc.code=='readonly_project':
                            raise
                        from research_workflow import status as research_status, RESEARCH_ERROR_STAGES
                        error=dict(code=exc.code if exc.code in ERRORS or exc.code in RESEARCH_ERRORS or exc.code in RESEARCH_ERROR_STAGES
                                   else 'research_error',
                                   error=RESEARCH_ERRORS.get(exc.code,ERRORS.get(exc.code,'조사 작업을 완료하지 못했습니다.')))
                        try:
                            project=studio.project(match[1],match[2])
                            state=research_status(studio.workflow,project)
                        except (CompanyError,OSError,ValueError,KeyError,TypeError):
                            state=None
                        recovery = (state or {}).get('recovery') if match[3] == 'research-recovery-run' else None
                        diagnostics = (recovery or {}).get('diagnostics') or (state or {}).get('diagnostics')
                        error['research']=dict(stage=RESEARCH_ERROR_STAGES.get(exc.code,'preflight'),
                            diagnostics=diagnostics)
                        return self.send_json(409,error)
                    return self.send_json(200,result)
            raise FileNotFoundError

        def handle_request(self):
            try:
                self.dispatch()
            except FileNotFoundError:
                self.send_json(404, dict(error='프로젝트 또는 파일을 찾을 수 없습니다.'))
            except CompanyError as exc:
                status = 403 if exc.code == 'readonly_project' else 409
                self.send_json(status, dict(code=exc.code, error=ERRORS.get(exc.code, '요청을 완료할 수 없습니다. 현재 상태와 입력을 확인해 주세요.')))
            except (ValueError, UnicodeError):
                self.send_json(400, dict(error='요청 형식이 올바르지 않습니다.'))
            except (BrokenPipeError, ConnectionResetError):
                pass
            except OSError:
                self.send_json(500, dict(error='로컬 파일 처리에 실패했습니다.'))

        do_GET = do_HEAD = do_POST = handle_request

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--root', type=Path, default=ROOT/'studio')
    parser.add_argument('--reference', type=Path, action='append')
    args = parser.parse_args()
    references = args.reference if args.reference is not None else [ROOT/'20261111_validation', ROOT/'20261111_reference']
    with make_server(args.host, args.port, Studio(args.root, references)) as server:
        print(f'Studio · http://{args.host}:{server.server_port}', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
