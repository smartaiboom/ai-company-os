"""Separately approved source research and local asset-library handoff."""
import re

from ai_clip_pipeline import open_input
from autonomous_company import CompanyError, digest, exact, parse, require
from employee_web_research import POLICY
from goal_dialogue import safe_text
from mission_production import ProductionManager, approved_manager_result, canonical_bytes, clip_job, draft_id
from pathlib import Path
from quality_tool_adapters import capabilities
from role_json_schema import S, arr, enum, obj
from tts_job import private_write


ROUTES = ('local_library', 'official_direct_media', 'public_metadata_search', 'own_capture', 'hold')
IDENTIFIER = re.compile(r'[a-z0-9][a-z0-9_-]{0,39}')
SHA256 = re.compile(r'[a-f0-9]{64}')
SCHEMA = obj(scenes=arr(obj(scene_id=S, route=enum(*ROUTES), asset_id=S, rationale=S,
                            next_step=S, suitability_check=S)), review_criteria=arr(S))
SYSTEM = (
    '당신은 동영상 자산 확보 직원입니다. 한국어 설명과 JSON만 반환하며 장면 ID·경로 열거값·자산 ID는 원문 그대로 사용합니다. '
    '승인된 내레이션과 장면 경계, 관리자 계획 원본을 변경하지 않습니다. 각 장면의 목표와 참조는 검색 단서이며 유일한 후보가 아닙니다. '
    '권리 진술이 있는 로컬 목록에서 적합한 파일만 선택합니다. 목록 설명은 제공자 진술이고 직접 시청한 증거가 아닙니다. '
    '그 밖에는 공식 직접 제공 미디어의 권리 확인 절차, 공개 메타데이터 검색어, 자체 캡처의 실행 조건 또는 보류 이유를 쓰세요. '
    '메타데이터만으로 영상 내용·라이선스·다운로드 허가를 주장하지 마세요. 도구 제공 상태 및 승인 범위를 지키세요. '
    '첫 장면 후크, 주제와 행동의 일치, 움직임·화면 다양성·몰입과 음성 자연스러움의 확인 방법을 이 프로젝트에 맞게 정하세요. '
    '라이브러리 선택만 asset_id에 실제 ID를 사용하고 나머지는 none을 사용합니다. 같은 파일을 여러 장면에 배정하지 마세요.'
)


def source_capabilities(entries):
    return dict(
        local_library=dict(availability='registered' if entries else 'empty', candidates=entries,
            permission='representative local import; registered rights attestation; file SHA-256 and decode',
            external_requests=0, cost_usd=0, rights='local review only; independent rights/semantic review pending'),
        public_metadata_search=dict(tool=POLICY['tool'], availability='existing planning tool; no production grant',
            permission='existing observations are references; new searches require separate scoped authorization',
            external_requests=0, rights='metadata is not footage, a license, or download permission'),
        official_direct_media=dict(availability='investigation proposal only', automatic_download=False,
            required='issuer identity, explicit download permission and project use terms; separate transfer approval',
            cost='unknown', external_requests=0),
        own_capture=dict(availability='operator or authorized staff capture; no capture integration',
            required='game policy, permissions for the recording and included audio; register eligible local file',
            external_requests=0, cost='unknown'),
        generation=dict(availability='no verified free production executor',
            transport_enabled=capabilities()['transport_enabled'], cost='current account pricing unverified',
            external_requests=0, rights='verify inputs and output terms before any separate approval'))


def library_entries(root):
    manifest = root/'inventory.json'
    require(not any(p.is_symlink() for p in (manifest, root, *root.parents)), 'invalid_source_library')
    if not manifest.exists():
        return {}
    require(manifest.is_file() and manifest.stat().st_size <= 32768, 'invalid_source_library')
    entries = parse(manifest.read_text())
    require(isinstance(entries, list) and len(entries) <= 24, 'invalid_source_library')
    by_id = {}
    for entry in entries:
        exact(entry, ('id','file','sha256','description','origin','rights','local_review_allowed'))
        name = entry['id']
        require(type(name) is str and IDENTIFIER.fullmatch(name) and name not in by_id
                and type(entry['sha256']) is str and SHA256.fullmatch(entry['sha256'])
                and entry['local_review_allowed'] is True
                and entry['origin'] in ('official_direct_media','own_capture','rights_cleared_local'),
                'invalid_source_library')
        safe_text(entry['description'], 320)
        safe_text(entry['rights'], 600)
        require(type(entry['file']) is str and Path(entry['file']).name == entry['file']
                and '\\' not in entry['file'] and Path(entry['file']).suffix.lower()=='.mp4',
                'invalid_source_library')
        try:
            with open_input(root, entry['file']):
                by_id[name] = entry
        except FileNotFoundError:
            continue
    return by_id


class SourceAssignment(ProductionManager):
    marker_name = '.mission-production-sources-v1'
    acceptance_scope = 'mission_production_sources_once_v1'

    def freeze_contract(self):
        path = self.root/'inventory.json'
        if not path.exists():
            private_write(path, canonical_bytes(self.contract['input']['source_tools']['local_library']['candidates']))

    def validate_plan(self, value):
        inputs = self.contract['input']
        require([s['scene_id'] for s in value['scenes']] ==
                [s['scene_id'] for s in inputs['storyboard']], 'production_scene_mismatch')
        catalog = inputs['source_tools']['local_library']['candidates']
        used = set()
        for scene in value['scenes']:
            for field in ('rationale','next_step','suitability_check'):
                safe_text(scene[field], 600)
            asset = scene['asset_id']
            if scene['route'] == 'local_library':
                require(asset in catalog and catalog[asset]['sha256'] not in used, 'source_library_selection_invalid')
                used.add(catalog[asset]['sha256'])
            else:
                require(asset == 'none', 'source_library_selection_invalid')
        require(1 <= len(value['review_criteria']) <= 8, 'production_plan_incomplete')
        for text in value['review_criteria']:
            safe_text(text, 600)


def source_assignment(manager, plan, library, entries=None):
    inputs = manager.contract['input']
    root = manager.root/'source_assessment'
    frozen = root/'inventory.json'
    require(not root.is_symlink() and not frozen.is_symlink(), 'invalid_acceptance_path')
    if frozen.exists():
        require(frozen.is_file() and frozen.stat().st_size <= 32768, 'invalid_source_library')
        catalog = parse(frozen.read_text())
    else:
        if entries is None:
            entries = library_entries(library)
        # Filenames and full license evidence stay local.
        catalog = {name:{k:entry[k] for k in ('description','origin','sha256')} |
                       {'local_record_sha256':digest(entry)} for name,entry in entries.items()}
    context = {key:inputs[key] for key in ('goal','audience','topic','duration','storyboard','approved_plan_hash',
                                           'preview_hash','revision_feedback','source_observations')}
    context.update(manager_plan=plan, manager_plan_hash=digest(plan), source_tools=source_capabilities(catalog))
    return SourceAssignment(root,dict(input=context,schema=SCHEMA,system=SYSTEM))


def source_status(manager, plan, library, clips):
    try:
        entries = library_entries(library)
        worker = source_assignment(manager,plan,library,entries)
    except (OSError, ValueError, CompanyError):
        return dict(status='blocked', reason='로컬 자산 목록 또는 저장된 인수 범위를 확인하세요.')
    state = dict(status='unprepared', scope=worker.contract['input'], available_count=len(entries), ready=[])
    jid = draft_id(worker)
    if jid is None:
        return state
    draft = worker.load(jid)
    attempts = draft['real_ai']['attempts']
    state.update(status='stopped' if attempts else 'approved' if draft['grants'] else 'prepared',
                 attempts=len(attempts))
    proposal = worker._proposal_path(jid)
    if proposal.is_file():
        body = parse(proposal.read_text())
        state.update(review_hash=digest(body),expires_at=body['expires_at'])
    if draft['status'] == 'needs_user_review':
        result = approved_manager_result(worker)
        state.update(status='completed',result=result)
        catalog = worker.contract['input']['source_tools']['local_library']['candidates']
        state['ready'] = [s['scene_id'] for s in result['scenes']
                          if s['route']=='local_library' and s['scene_id'] not in clips
                          and s['asset_id'] in entries
                          and digest(entries[s['asset_id']])==catalog[s['asset_id']]['local_record_sha256']]
    return state


def run_source_action(manager, plan, library, action, body):
    from mission_production import prepare_manager_request, production_keys
    worker = source_assignment(manager,plan,library)
    jid = draft_id(worker)
    if action == 'production-source-prepare':
        return prepare_manager_request(worker, jid, body)
    require(jid is not None, 'production_source_assessment_missing')
    if action == 'production-source-consent':
        exact(body, ('review_hash','free','policy'))
        key,_ = production_keys()
        return worker.approve_consent(jid,body['review_hash'],api_key=key,owner_confirmed=True,
                    free_project_confirmed=body['free'],google_data_policy_accepted=body['policy'])
    if action == 'production-source-run':
        exact(body, ())
        key,_ = production_keys()
        return worker.ask_ai(jid,api_key=key)

    exact(body, ('scene','confirmed'))
    require(action=='production-source-import' and body['confirmed'] is True, 'production_rights_confirmation_required')
    result = approved_manager_result(worker)
    selection = next((s for s in result['scenes']
                      if s['scene_id']==body['scene'] and s['route']=='local_library'), None)
    require(selection is not None, 'source_library_selection_invalid')
    name = selection['asset_id']
    entry = library_entries(library).get(name)
    catalog = worker.contract['input']['source_tools']['local_library']['candidates']
    require(entry is not None and digest(entry)==catalog[name]['local_record_sha256'], 'production_source_asset_changed')
    job,spec = clip_job(manager,plan)
    if not job.root.exists():
        job.create(spec)
    rights = entry['rights']
    source = dict(provider='local_library', provenance=dict(kind='operator_provided_clip',
        evidence=f'library:{name} · {entry["origin"]} · assessment:{digest(result)}'),
        generated_at=None, license='registered rights for local review', terms_url='local rights declaration',
        usage_rights='local review only', commercial_use='unknown', allowed_to_publish=False, watermark='unknown',
        rights_verified=False, rights_evidence=rights, estimated_cost=None, actual_cost=None)
    return job.import_generated_clip(library, entry['file'], body['scene'], source, expected_sha256=entry['sha256'])
