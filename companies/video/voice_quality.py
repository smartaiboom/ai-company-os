"""Scoped human voice evidence and executable offline staff handoffs. No transport."""
from copy import deepcopy
import fcntl
import json
import math
import os
from pathlib import Path
from autonomous_company import require, digest, now, MockManagerProvider, MockEmployeeProvider
from quality_feedback import ExperienceJournal
from manager_plan_once import canonical_bytes
from tts_job import sha, private_write
from local_artifacts import run_command

AUDIENCE = '한국어 직장인 AI 초보자'
ORIGINAL = '실제 음성 A/B 청취 평가 결과: 더 나은 음성=Gemini TTS(B), 새 Gemini 음성 자연스러움=7/10점, 의견=B가 훨씬 자연스러워.'
BINDINGS = dict(A='a011f8bb6b83e5d3515171bcdf6fc9e9aa09d42844f8e14cfbb8955de18b25a5',
    B='7674f8d8449f5011aff56efd6c4f52ba7d878c43541df6d7043442a4ba831419',
    transcript='ec1e2906fd065530a2bbfc79bfab9d3769a9f72296897887f5b02d4efeeffa59')
CANDIDATE = dict(provider='gemini_developer', model='gemini-3.8-flash-tts', voice='Puck')


def record_user_evaluation(root, *, A, B, transcript):
    """Dedicated journal, immutable artifact, and evaluation-SHA idempotence under lock."""
    root = Path(root).absolute()
    require(not any(p.is_symlink() for p in (root, *root.parents)), 'voice_feedback_symlink')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(root.stat().st_mode & 0o077 == 0, 'voice_feedback_private_root')
    paths = dict(A=Path(A), B=Path(B), transcript=Path(transcript))
    for name, path in paths.items():
        require(not path.is_symlink() and path.is_file() and sha(path.read_bytes()) == BINDINGS[name], 'voice_evidence_changed')
    core = dict(original_text=ORIGINAL, bindings=deepcopy(BINDINGS), candidate=deepcopy(CANDIDATE),
        domain='video', target_segment=AUDIENCE, provenance='user_structured', preferred='B',
        naturalness_score=7, score_max=10, verified_scope='actual_user_preference_and_score_only',
        future_quality='hypothesis', publish_ready=False)
    evaluation_sha = digest(core)
    lock = os.open(root/'.feedback.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        artifact = root/(evaluation_sha+'.json')
        if artifact.exists():
            require(not artifact.is_symlink(), 'voice_feedback_symlink')
            evidence = json.loads(artifact.read_bytes())
            require(evidence['evaluation'] == core and evidence['evaluation_sha256'] == evaluation_sha,
                    'voice_evaluation_changed')
        else:
            media = {}
            for name in ('A', 'B'):
                probe = json.loads(run_command(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(paths[name])], stage='ffprobe_audio'))
                run_command(['ffmpeg', '-v', 'error', '-xerror', '-i', str(paths[name]), '-f', 'null', '-'], stage='ffmpeg_decode')
                stream = probe['streams'][0]
                require(len(probe['streams']) == 1 and stream['codec_name'] == 'pcm_s16le' and stream['channels'] == 1, 'voice_evidence_format')
                media[name] = dict(sha256=BINDINGS[name], bytes=paths[name].stat().st_size,
                    seconds=float(probe['format']['duration']), codec=stream['codec_name'],
                    sample_rate=int(stream['sample_rate']), channels=1, decoded=True)
            evidence = dict(evaluation_sha256=evaluation_sha, recorded_at=now(), evaluation=core, media=media)
            private_write(artifact, canonical_bytes(evidence)); artifact.chmod(0o400)
        journal = ExperienceJournal(root/'journal'); reference = root/'journal_ref.json'
        if reference.exists():
            require(not reference.is_symlink(), 'voice_feedback_symlink')
            jid = json.loads(reference.read_bytes())['journal_id']
        else:
            jid = journal.create(); private_write(reference, canonical_bytes(dict(journal_id=jid)))
        state = journal.store.load(jid)
        matches = [e for e in state['experiences'] if json.loads(e['evidence']).get('evaluation_sha256') == evaluation_sha]
        require(len(matches) <= 1, 'voice_duplicate_evaluation')
        if matches:
            entry = matches[0]
            require(entry['original_text'] == ORIGINAL and entry['extraction_source'] == 'user_structured'
                    and entry['verification'] == 'verified'
                    and json.loads(entry['evidence'])['artifact_sha256'] == sha(artifact.read_bytes()), 'voice_journal_changed')
        else:
            entry = journal.record(jid, ORIGINAL, dict(project='gemini_tts_single_free_trial_v1', domain='video',
                target_segment=AUDIENCE, issue='실제 B 자연스러움7/10; 게시 여부 미결정. 구체적 결함은 미지정.',
                positive_preference='동일60자 A/B에서 Gemini/Puck B가 Melo A보다 훨씬 자연스럽다는 사용자 평가',
                proposed_correction='같은 대상의 추천 후보 B 우선; 다음20초 샘플8/10 목표는 hypothesis, 새 승인/생성/청취 필요',
                evidence=json.dumps(dict(evaluation_sha256=evaluation_sha, artifact_sha256=sha(artifact.read_bytes()),
                    bindings=BINDINGS, preferred='B', naturalness_score=7, score_max=10), ensure_ascii=False),
                source='actual_user_listening_ab_20261110', confidence=1, verification='verified'), provenance='user_structured')
        selection = journal.select(jid, domain='video', target_segment=AUDIENCE)
        return dict(journal_id=jid, entry=entry, evaluation_sha256=evaluation_sha,
            artifact=str(artifact), artifact_sha256=sha(artifact.read_bytes()), selection=selection)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN); os.close(lock)


def scoped_voice_policy(selection, audience):
    selected = []
    if audience == AUDIENCE:
        for entry in selection.get('selected', []):
            if (entry.get('domain') == 'video' and entry.get('target_segment') == AUDIENCE
                and entry.get('active') is True and entry.get('extraction_source') == 'user_structured'
                and entry.get('verification') == 'verified' and entry.get('original_text') == ORIGINAL
                and entry.get('source') == 'actual_user_listening_ab_20261110'):
                value = json.loads(entry['evidence'])
                require(value['bindings'] == BINDINGS and value['naturalness_score'] == 7 and value['preferred'] == 'B', 'voice_feedback_claim_changed')
                selected.append(dict(experience_id=entry['id'], record_hash=entry['record_hash'],
                    evaluation_sha256=value['evaluation_sha256']))
    return dict(recommended=deepcopy(CANDIDATE) if selected else None, evidence_refs=selected,
        journal_hash=selection.get('journal_hash'), baseline_score=7 if selected else None,
        baseline_scope='actual_user_preference_and_score_only', target_score=8 if selected else None,
        improvement_status='hypothesis', permission_to_generate=False, new_audio_quality='unassessed',
        publish_ready=False, comparison='Melo A preserved; no general provider ranking')


def next_voice_sample():
    """One authored fictional20s proposal. Text/style preparation is not synthesis."""
    scenes = [
        (3, '금요일 세 시, 회의가 확정된 걸까요?', '원문 시각 선택', '세 시: 숫자 읽기 확인'),
        (5, '설명을 위한 가상 메모예요. 금요일 세 시는 제안이고, 회의는 아직 미정입니다.', '제안/미정 분리 표시', '미정 뒤 의미 단위 쉼'),
        (7, '목요일까지 고객에게 확인하고 다시 알려주겠다는 말은, 확인 업무의 기한이죠.', '목요일 확인 업무 강조', '목요일/금요일 구분 청취'),
        (5, '회의 시간과 확인 기한, 두 칸으로 나눠 보세요.', '두 칸 문서 대조', '두 칸을 가볍게 강조')]
    parts = [dict(id=f'scene-{i+1}', seconds=seconds, narration=text, visual=visual,
                  subtitle=text, pronunciation_check=check) for i, (seconds, text, visual, check) in enumerate(scenes)]
    narration = ' '.join(p['narration'] for p in parts)
    return dict(authorship='codex-authored', title='금요일 세 시, 확정인가요?', audience=AUDIENCE,
        fictional=True, narration=narration, narration_sha256=sha(narration.encode()), scenes=parts,
        target_seconds=20, actual_seconds=None,
        source_text='가상 메모: 민수가 금요일 세 시를 제안. 고객 확인 필요로 회의는 미정. 민수가 목요일까지 확인 후 재공유.',
        fact_checks=[dict(claim='금요일 세 시는 제안/회의는 미정', source='source_text', status='fictional_source_consistent'),
                     dict(claim='목요일은 확인 후 재공유 기한', source='source_text', status='fictional_source_consistent')],
        direction=dict(style='친근하고 또렷한 한국어 대화체. 질문 후 짧게 쉬고 제안과 미정을 자연스럽게 구분. 과장·성우 모사 없음.',
            editorial_only=['쉼표 위치/호흡은 청취 확인', '서두르지 않기; 실제 발화 길이로 검토', '숫자·영어·고유명사 등장 시 발음표 확인'],
            supported_style_field='speech_metadata.style', extra_wire_parameters={}),
        proposed_limits=dict(requests=1, max_cost_usd=0, max_output_tokens=1024, max_response_bytes=2000000, max_audio_seconds=20),
        timing='target_only_actual_speech_and_subtitle_sync_unmeasured',
        authorization='not_granted_new_exact_payload_approval_required', publish_ready=False)


def inspect_voice_stage(role, value, previous, policy):
    require(value.get('contract') == 'voice_quality_v1' and value.get('role') == role, 'voice_contract_required')
    expected_refs = [dict(task_id=r['task_id'], revision=r['revision'], result_hash=digest(r)) for r in previous]
    require(value.get('upstream_refs') == expected_refs, 'voice_handoff_changed')
    require(value.get('authorship') == 'codex-authored' and value.get('publish_ready') is False, 'voice_authorship_or_publish_claim')
    if role == 'writer':
        sample = value['sample']; scenes = sample['scenes']
        require(sample['narration'] == ' '.join(s['narration'] for s in scenes)
                and sample['narration_sha256'] == sha(sample['narration'].encode()), 'voice_narration_changed')
        require(all(type(s['seconds']) in (int, float) and math.isfinite(s['seconds']) and s['seconds'] > 0
                    and s['subtitle'] == s['narration'] for s in scenes)
                and sum(s['seconds'] for s in scenes) == sample['target_seconds'] == 20, 'voice_timeline_changed')
        require(sample['fictional'] is True and sample['actual_seconds'] is None
                and sample['direction']['extra_wire_parameters'] == {}
                and sample['authorization'] == 'not_granted_new_exact_payload_approval_required'
                and bool(sample['fact_checks']), 'voice_unverified_generation')
    elif role == 'voice':
        sample = json.loads(previous[0]['content'])['sample']
        require(value['narration_sha256'] == sample['narration_sha256'] and value['candidate'] == policy['recommended']
                and value['baseline_score'] == policy['baseline_score'] and value['target_score'] == policy['target_score']
                and value['evidence_refs'] == policy['evidence_refs'] and value['new_audio'] is None
                and value['generation_authorized'] is False, 'voice_preference_or_permission_changed')
        require(value['direction'] == sample['direction'], 'voice_direction_changed')
    elif role == 'editor':
        sample = json.loads(previous[0]['content'])['sample']
        require(value['scenes'] == sample['scenes'] and value['actual_alignment'] is None
                and value['audio_status'] == 'not_generated', 'voice_edit_alignment_changed')
    else:
        require(role == 'qa' and value['new_quality'] == 'unassessed' and value['rights'] == 'unverified'
                and set(value['blockers']) == {'new_audio_pending', 'user_listening_pending', 'rights_unverified'}, 'voice_qa_claim_changed')
    return dict(source='deterministic_voice_handoff_check', artifact_hash=digest(value), defects=[],
        sensory_quality='unassessed', media_technical='new_audio_not_generated')


def run_voice_quality_offline(store, project_id):
    """Authored callback demo on existing company engine, never live AI reasoning."""
    from quality_workflow import VideoQualityCompany
    def manager(phase, context):
        policy = context['voice_policy']
        if phase == 'plan':
            require(policy['baseline_score'] == 7, 'voice_scoped_feedback_required')
            tasks = [dict(id=role, title=role, role=role, depends_on=deps, criteria_ids=['handoff'],
                instructions='인수 해시/원문/장면 시간/사용자7점 기준과8점 목표를 구분. 추가 생성/게시 불허.')
                for role, deps in [('writer', []), ('voice', ['writer']), ('editor', ['writer', 'voice']), ('qa', ['writer', 'voice', 'editor'])]]
            value = dict(tasks=tasks, criteria=[dict(id='handoff', description='실제 사용자 평가에 근거한 오프라인 음성 인수 계약')],
                rationale='Codex-authored contract; B7/10 observed, next8/10 hypothesis', uncertainty='No new audio or live model decision')
        elif phase == 'review':
            value = dict(action='accept', rationale='인수 계약만 확인; 음질 합격 아님', evidence='deterministic_voice_handoff_check',
                uncertainty='새 음성 없음', checks=[dict(criterion_id='handoff', status='met', evidence='hash/timing/score scope checked', source='model_claim')], feedback='', operation=None)
        else:
            value = dict(action='stop', content='다음 음성1샘플 준비; 실제 생성/게시 대기', rationale='새 승인/청취/권리 확인 필요',
                uncertainty='품질 개선 미검증', checks=[dict(criterion_id='handoff', status='unknown', evidence='new sample absent', source='model_claim')],
                task_refs=[dict(task_id=r['task_id'], revision=r['revision'], result_hash=digest(r)) for r in context['results']])
        return json.dumps(value, ensure_ascii=False)
    def employee(phase, context):
        role = context['assignment']['role']; previous = context['previous_results']; policy = context['voice_policy']
        value = dict(contract='voice_quality_v1', role=role, authorship='codex-authored', publish_ready=False,
            upstream_refs=[dict(task_id=r['task_id'], revision=r['revision'], result_hash=digest(r)) for r in previous])
        if role == 'writer': value['sample'] = next_voice_sample()
        elif role == 'voice':
            sample = json.loads(previous[0]['content'])['sample']
            value.update(narration_sha256=sample['narration_sha256'], candidate=policy['recommended'],
                baseline_score=policy['baseline_score'], target_score=policy['target_score'], evidence_refs=policy['evidence_refs'],
                direction=sample['direction'], new_audio=None, generation_authorized=False)
        elif role == 'editor':
            value.update(scenes=json.loads(previous[0]['content'])['sample']['scenes'], actual_alignment=None, audio_status='not_generated')
        else: value.update(new_quality='unassessed', rights='unverified', blockers=['new_audio_pending', 'user_listening_pending', 'rights_unverified'])
        inspect_voice_stage(role, value, previous, policy)
        return json.dumps(dict(content=json.dumps(value, ensure_ascii=False), evidence='authored offline handoff validation', uncertainty='No new model call/media/quality improvement claim'), ensure_ascii=False)
    return VideoQualityCompany(store, MockManagerProvider('codex-authored-voice-manager', manager),
        MockEmployeeProvider('codex-authored-voice-staff', employee)).run(project_id)
