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
    core = dict(original_text=ORIGINAL, bindings=deepcopy(BINDINGS), candidate=deepcopy(CANDIDATE),
        domain='video', target_segment=AUDIENCE, provenance='user_structured', preferred='B',
        naturalness_score=7, score_max=10, verified_scope='actual_user_preference_and_score_only',
        future_quality='hypothesis', publish_ready=False)
    return _record_listening(root, dict(A=Path(A), B=Path(B), transcript=Path(transcript)), core,
        dict(project='gemini_tts_single_free_trial_v1', domain='video',
                target_segment=AUDIENCE, issue='실제 B 자연스러움7/10; 게시 여부 미결정. 구체적 결함은 미지정.',
                positive_preference='동일60자 A/B에서 Gemini/Puck B가 Melo A보다 훨씬 자연스럽다는 사용자 평가',
                proposed_correction='같은 대상의 추천 후보 B 우선; 다음20초 샘플8/10 목표는 hypothesis, 새 승인/생성/청취 필요', source='actual_user_listening_ab_20261110', confidence=1, verification='verified'),
        ('A', 'B'))


LISTENING_148_SOURCE = 'actual_user_listening_148_20261111'
LISTENING_148_TEXT = ('새로 생성한 148자 Gemini/Puck 21.52초 음성을 실제 청취했어. 전체 자연스러움 7/10점, '
    '목소리·억양 좋음, 속도·쉼 적절함. 의견: 좋아 음성은 전체적으로 상당히 괜찮아! '
    '이제 대본,영상,음성 중 음성은 충분하고 대본 생성 능력 향상에 힘쓰자.')


def record_148_user_evaluation(root, *, audio, transcript):
    bindings = dict(sample='6ef2673b6f977981a789d27b132c8233090e049e299cda6f11e946936ccb149f',
        transcript='dee1aef757a0c7edac0a6314fef7559591bab1e506ab59066dbb62a5fe3d243b')
    core = dict(original_text=LISTENING_148_TEXT, bindings=bindings, candidate=deepcopy(CANDIDATE),
        domain='video', target_segment=AUDIENCE, provenance='user_structured', source=LISTENING_148_SOURCE,
        overall_naturalness=7, score_max=10, voice_and_intonation='좋음', pace_and_pauses='적절함',
        user_says_voice_sufficient=True, next_priority='script_quality', transcript_characters=148,
        audio_seconds=21.52, listened_at=None, verified_scope='actual_user_sample_opinion_only',
        publish_ready=False)
    return _record_listening(root, dict(sample=Path(audio), transcript=Path(transcript)), core,
        dict(project='gemini_tts_148_20261111', domain='video', target_segment=AUDIENCE,
            issue='148자·21.52초 샘플 자연스러움 7/10. 개별 발음 결함은 미지정.',
            positive_preference='목소리·억양 좋음, 속도·쉼 적절함, 현 단계 음성 충분',
            proposed_correction='대본 품질을 우선 개선. 음성 추가 생성·실험은 보류.',
            source=LISTENING_148_SOURCE, confidence=1, verification='verified'), ('sample',))


def _record_listening(root, paths, core, fields, media_names):
    bindings = core['bindings']
    original = core['original_text']
    root = Path(root).absolute()
    require(not any(p.is_symlink() for p in (root, *root.parents)), 'voice_feedback_symlink')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(root.stat().st_mode & 0o077 == 0, 'voice_feedback_private_root')
    for name, path in paths.items():
        require(not path.is_symlink() and path.is_file() and sha(path.read_bytes()) == bindings[name], 'voice_evidence_changed')
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
            for name in media_names:
                probe = json.loads(run_command(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(paths[name])], stage='ffprobe_audio'))
                run_command(['ffmpeg', '-v', 'error', '-xerror', '-i', str(paths[name]), '-f', 'null', '-'], stage='ffmpeg_decode')
                stream = probe['streams'][0]
                require(len(probe['streams']) == 1 and stream['codec_name'] == 'pcm_s16le' and stream['channels'] == 1, 'voice_evidence_format')
                media[name] = dict(sha256=bindings[name], bytes=paths[name].stat().st_size,
                    seconds=float(probe['format']['duration']), codec=stream['codec_name'],
                    sample_rate=int(stream['sample_rate']), channels=1, decoded=True)
            if 'audio_seconds' in core:
                require(media['sample']['seconds'] == core['audio_seconds'] and
                        len(paths['transcript'].read_text()) == core['transcript_characters'], 'voice_sample_mismatch')
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
            require(entry['original_text'] == original and entry['extraction_source'] == 'user_structured'
                    and entry['verification'] == 'verified' and entry['source'] == fields['source']
                    and entry['target_segment'] == fields['target_segment']
                    and json.loads(entry['evidence'])['artifact_sha256'] == sha(artifact.read_bytes()), 'voice_journal_changed')
        else:
            claims = (dict(preferred=core['preferred'], naturalness_score=core['naturalness_score'])
                      if 'preferred' in core else {key: core[key] for key in
                          ('overall_naturalness', 'voice_and_intonation', 'pace_and_pauses',
                           'user_says_voice_sufficient', 'next_priority', 'audio_seconds', 'listened_at')})
            entry = journal.record(jid, original, dict(**fields,
                evidence=json.dumps(dict(evaluation_sha256=evaluation_sha, artifact_sha256=sha(artifact.read_bytes()),
                    bindings=bindings, **claims, score_max=core['score_max']), ensure_ascii=False)),
                provenance='user_structured')
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



def select_video_voice(selection, brief):
    """A versioned staff decision, never a voice-gender rule or execution grant."""
    from autonomous_company import exact, text
    exact(brief, ('channel_id','series_id','video_id','target_segment','language','topic','genre','mood',
                  'brand_consistency','representative','exception','constraints'))
    for field in ('channel_id','series_id','video_id','target_segment','language','topic','genre','mood'):
        text(brief[field], 300)
    require(type(brief['brand_consistency']) is bool and brief['constraints'] ==
            dict(external_calls=False, publish_ready=False, max_cost_usd=0), 'voice_selection_permissions')
    baseline = scoped_voice_policy(selection, brief['target_segment'])
    fit = (brief['language'] == 'ko-KR' and brief['genre'] == 'ai_tips'
           and brief['mood'] == 'friendly_explainer' and baseline['recommended'] is not None)
    style = {'friendly_explainer':'친근하고 또렷한 한국어 대화체. 질문 뒤 짧게 쉬고 의미 단위로 나눠 말하기. 과장·성우 모사 없음.',
             'news':'차분하고 명료한 정보 전달. 감정 과장·성우 모사 없음.',
             'calm_information':'차분하고 또렷하게, 중요한 뜻을 구분하기. 과장·성우 모사 없음.',
             'playful_shorts':'가볍고 경쾌하게, 정보는 또렷하게. 과장·성우 모사 없음.'}.get(brief['mood'])
    candidate = None; status = 'unassessed'; reason = 'No matching listening evidence or designated representative; audition needed.'
    rep = brief['representative']; exception = brief['exception']; matches = False
    def validate_candidate(value):
        exact(value, ('provider','model','voice'))
        for val in value.values(): text(val, 200)
    if rep is not None:
        exact(rep, ('candidate','scope','channel_id','series_id','target_segment','language','mood','source','evidence_refs'))
        validate_candidate(rep['candidate'])
        require(rep['scope'] in ('channel','series') and rep['source'] in ('user_designated','evidence_based')
                and isinstance(rep['evidence_refs'],list) and bool(rep['evidence_refs'])
                and all(isinstance(ref,str) and bool(ref.strip()) for ref in rep['evidence_refs']), 'voice_representative_basis')
        require(rep['channel_id'] == brief['channel_id'] and
                (rep['scope']=='channel' or rep['series_id']==brief['series_id']), 'voice_representative_scope')
        if rep['source']=='evidence_based':
            require(fit and rep['candidate']==CANDIDATE and len(set(rep['evidence_refs']))>=2 and
                    set(rep['evidence_refs']).issubset({ref['evaluation_sha256'] for ref in baseline['evidence_refs']}), 'voice_representative_unverified')
        matches = all(rep[field] == brief[field] for field in ('target_segment','language','mood'))
        if matches and brief['brand_consistency']:
            candidate=deepcopy(rep['candidate']);status='representative_preferred'
            reason='Matching existing channel/series representative takes precedence; designation is not listening verification.'
        else: status='reassessment_required';reason='Audience/tone/consistency changed; representative needs reviewed reassessment.'
    if exception is not None:
        exact(exception, ('candidate','scope','reason','reviewed_by','review_note','version'))
        validate_candidate(exception['candidate'])
        require(exception['scope'] in ('video','series','channel') and exception['reviewed_by'] in ('user','manager')
                and isinstance(exception['reason'],str) and len(exception['reason'].strip())>=5
                and isinstance(exception['review_note'],str) and len(exception['review_note'].strip())>=5
                and type(exception['version']) is int and exception['version']>=1, 'voice_exception_review_required')
        candidate=deepcopy(exception['candidate']);status='reviewed_exception_unassessed'
        reason=exception['reason']+' / '+exception['review_note']
    elif rep is None and fit:
        candidate=deepcopy(CANDIDATE);status='scoped_listening_candidate'
        reason='Exact audience/language/AI-tip genre/friendly tone match to the actual B preference; no channel default created.'
    tested = candidate == CANDIDATE and fit
    result=dict(contract='video_voice_selection_v1', decision_version=1, decided_by='deterministic_policy_for_voice_staff',
        brief=deepcopy(brief), brief_sha256=digest(brief), candidate=candidate, style=style, status=status,
        reason=reason, listening_status='scoped_user_AB_7_of_10' if tested else 'unassessed',
        selected_voice_score=7 if tested else None, selected_evidence_refs=baseline['evidence_refs'] if tested else [],
        reference_AB_score=baseline['baseline_score'], reference_AB_scope='the_original_B_sample_only',
        target_score=8 if tested else None, improvement_status='hypothesis',
        permission_to_generate=False, publish_ready=False, channel_default_created=False)
    result['decision_sha256']=digest(result)
    return result


def voice_policy_for_brief(selection, audience, brief=None):
    policy=scoped_voice_policy(selection,audience)
    if brief is not None:
        require(brief['target_segment']==audience, 'voice_brief_audience_mismatch')
        decision=select_video_voice(selection,brief)
        policy.update(recommended=decision['candidate'],baseline_score=decision['selected_voice_score'],
            target_score=decision['target_score'],evidence_refs=decision['selected_evidence_refs'],video_selection=decision)
    return policy


def record_voice_selection(journal, journal_id, decision, *, selection):
    """Reuse ExperienceJournal for scoped choices/exceptions; never invent user feedback."""
    require(decision == select_video_voice(selection,decision['brief']), 'voice_decision_changed')
    value=deepcopy(decision);expected=value.pop('decision_sha256',None)
    require(expected==digest(value) and decision['permission_to_generate'] is False
            and decision['publish_ready'] is False, 'voice_decision_changed')
    lock=os.open(journal.store.root/'.voice-selection.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX)
        p=journal.store.load(journal_id)
        matches=[e for e in p['experiences'] if json.loads(e['evidence']).get('decision_sha256')==expected]
        if matches:return matches[0]
        brief=decision['brief']
        return journal.record(journal_id,'Codex-authored offline voice-selection decision; no new user listening evaluation.',dict(
            project=brief['video_id'],domain='video',target_segment=brief['target_segment'],
            issue='Per-video voice/brand selection; new audio unassessed',
            positive_preference=decision['reason'],proposed_correction='Audition and explicit generation approval remain separate',
            evidence=json.dumps(dict(decision_sha256=expected,brief=brief,candidate=decision['candidate']),ensure_ascii=False),
            source='voice_selection_contract_v1_codex_authored',confidence=.5,verification='hypothesis'),provenance='offline_fixture')
    finally:fcntl.flock(lock,fcntl.LOCK_UN);os.close(lock)

def next_voice_sample():
    """One authored fictional proposal; timing is estimated until synthesis. Text/style preparation is not synthesis."""
    scenes = [
        (3, '금요일 세 시. 회의가 확정된 걸까요?', '원문 시각 선택', '세 시: 숫자 읽기 확인'),
        (5, '이건 가상 회의 메모예요. 금요일 세 시는 제안일 뿐, 아직 확정이 아닙니다.', '제안/미정 분리 표시', '미정 뒤 의미 단위 쉼'),
        (7, '반면, 목요일까지 고객에게 확인하고 다시 알려주겠다는 말은 확인 업무의 기한이죠.', '목요일 확인 업무 강조', '목요일/금요일 구분 청취'),
        (5, '회의 시간은 미정, 확인 기한은 목요일. 두 칸으로 나눠 보세요.', '두 칸 문서 대조', '두 칸을 가볍게 강조')]
    parts = [dict(id=f'scene-{i+1}', seconds=seconds, narration=text, visual=visual,
                  subtitle=text, pronunciation_check=check, actual_seconds=None) for i, (seconds, text, visual, check) in enumerate(scenes)]
    narration = ' '.join(p['narration'] for p in parts)
    return dict(authorship='codex-authored', title='금요일 세 시, 확정인가요?', audience=AUDIENCE,
        fictional=True, narration=narration, narration_sha256=sha(narration.encode()), scenes=parts,
        target_seconds=20, actual_seconds=None, accepted_actual_seconds_range=[15,35],
        revision_of_narration_sha256='2cdff7ca3a91bbeaa4249cd3765c65548fdec016a9688dd1d9af13f7e49556ea',
        revision_notes=['질문 전 의미 쉼을 문장부호로 표시','제안/확정과 목요일/금요일 대조 명시'],
        source_text='가상 메모: 민수가 금요일 세 시를 제안. 고객 확인 필요로 회의는 미정. 민수가 목요일까지 확인 후 재공유.',
        fact_checks=[dict(claim='금요일 세 시는 제안/회의는 미정', source='source_text', status='fictional_source_consistent'),
                     dict(claim='목요일은 확인 후 재공유 기한', source='source_text', status='fictional_source_consistent')],
        direction=dict(style='친근하고 또렷한 한국어 대화체. 질문 후 짧게 쉬고 제안과 미정을 자연스럽게 구분. 과장·성우 모사 없음.',
            editorial_only=['쉼표 위치/호흡은 청취 확인', '서두르지 않기; 실제 발화 길이로 검토', '숫자·영어·고유명사 등장 시 발음표 확인'],
            supported_style_field='speech_metadata.style', extra_wire_parameters={}),
        proposed_limits=dict(requests=1, max_cost_usd=0, max_output_tokens=1024, max_response_bytes=2000000, max_audio_seconds=35),
        timing='estimate_only_align_scenes_after_measuring_audio',
        comparison_rubric=dict(reference_audio_sha256=BINDINGS['B'],reference_overall_score=7,
            target_overall_score=8,new_overall_score=None,
            dimensions=[dict(id=i,before=None,after=None,evaluator='user_pending') for i in
                ('voice_tone','listening_ease','pace_pauses','hook_delivery')],
            caveat='기존8초와 새 긴 샘플은 다른 발화이므로 길이·문맥 차이를 고려하며 모델 우열로 일반화하지 않는다'),
        authorization='not_granted_new_exact_payload_approval_required', publish_ready=False)


def inspect_voice_stage(role, value, previous, policy):
    require(value.get('contract') == 'voice_quality_v1' and value.get('role') == role, 'voice_contract_required')
    expected_refs = [dict(task_id=r['task_id'], revision=r['revision'], result_hash=digest(r)) for r in previous]
    require(value.get('upstream_refs') == expected_refs, 'voice_handoff_changed')
    require(value.get('authorship') == 'codex-authored' and value.get('publish_ready') is False, 'voice_authorship_or_publish_claim')
    require(value.get('video_voice_selection') == policy.get('video_selection'), 'voice_selection_handoff_changed')
    if role == 'writer':
        sample = value['sample']; scenes = sample['scenes']
        if policy.get('video_selection') is not None:
            brief=policy['video_selection']['brief']
            require(sample['audience']==brief['target_segment']==AUDIENCE and brief['language']=='ko-KR'
                    and brief['genre']=='ai_tips', 'voice_sample_scope_mismatch')
        require(sample['narration'] == ' '.join(s['narration'] for s in scenes)
                and sample['narration_sha256'] == sha(sample['narration'].encode()), 'voice_narration_changed')
        require(all(type(s['seconds']) in (int, float) and math.isfinite(s['seconds']) and s['seconds'] > 0
                    and s['subtitle'] == s['narration'] for s in scenes)
                and sum(s['seconds'] for s in scenes) == sample['target_seconds'] == 20, 'voice_timeline_changed')
        require(sample['fictional'] is True and sample['actual_seconds'] is None
                and sample['accepted_actual_seconds_range'] == [15,35]
                and sample['timing'] == 'estimate_only_align_scenes_after_measuring_audio'
                and sample['comparison_rubric']['new_overall_score'] is None
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
            require(policy.get('video_selection') is not None or policy['baseline_score'] == 7, 'voice_scoped_feedback_required')
            tasks = [dict(id=role, title=role, role=role, depends_on=deps, criteria_ids=['handoff'],
                instructions='인수 해시/원문/장면 시간/사용자7점 기준과8점 목표를 구분. 추가 생성/게시 불허.')
                for role, deps in [('writer', []), ('voice', ['writer']), ('editor', ['writer', 'voice']), ('qa', ['writer', 'voice', 'editor'])]]
            value = dict(tasks=tasks, criteria=[dict(id='handoff', description='실제 사용자 평가에 근거한 오프라인 음성 인수 계약')],
                rationale='Codex-authored per-video voice contract; original B7/10 only, future quality hypothesis', uncertainty='No new audio or live model decision')
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
        if 'video_selection' in policy: value['video_voice_selection']=deepcopy(policy['video_selection'])
        if role == 'writer':
            value['sample']=next_voice_sample()
            if policy.get('video_selection',{}).get('style'):
                value['sample']['direction']['style']=policy['video_selection']['style']
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
