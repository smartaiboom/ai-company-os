'use strict';
const icons = {
  clapper:'<path d="m3 10 17-4-1-4L2 6zM3 10v10h18V10zM7 5l4 4m2-5 4 3"/><path d="m10 13 5 2.5-5 2.5z"/>',
  studio:'<path d="M3 6h14v12H3zM17 10l4-3v10l-4-3M7 10h6m-6 4h4"/>',
  grid:'<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"/>',
  folder:'<path d="M3 6h7l2 2h9v11H3z"/>', bookmark:'<path d="M6 3h12v18l-6-4-6 4z"/>',
  shield:'<path d="M12 22s7-4 7-11V5l-7-3-7 3v6c0 7 7 11 7 11z"/><path d="m9 11 2 2 4-4"/>',
  check:'<path d="m5 12 4 4L19 6"/>', plus:'<path d="M12 5v14M5 12h14"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
  film:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16m10-16v16M3 9h4m-4 6h4m10-6h4m-4 6h4"/>',
  revision:'<path d="M5 8a8 8 0 1 1-1 7m1-7V3m0 5h5"/>',
  arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>', back:'<path d="M19 12H5m6-6-6 6 6 6"/>',
  search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
  script:'<path d="M5 3h9l5 5v13H5zM14 3v6h5M8 13h8m-8 4h8"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
  mic:'<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 11a7 7 0 0 0 14 0m-7 7v4m-4 0h8"/>',
  alert:'<path d="m12 3 10 17H2zM12 9v4m0 3v.1"/>',
};
const icon = (key) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[key] || icons.folder}</svg>`;
document.querySelectorAll('[data-icon]').forEach((item) => { item.innerHTML = icon(item.dataset.icon); });
const main = document.querySelector('#main');
const dialog = document.querySelector('#dialog');
const crumb = document.querySelector('#crumb');
const h = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const time = (value) => value ? value.slice(0, 16).replace('T', ' ') + ' KST' : '—';
const statuses = {
  goal_submitted:['목표 접수','AI 관리자','기획 작업 열기',0,'clock',''],
  research_planning:['조사·기획','조사·대본 직원','내부 검토 보고 대기',1,'search',''],
  awaiting_plan_approval:['기획 승인 대기','대표','기획·대본 검토',2,'shield','amber'],
  plan_revision:['기획 수정 요청','AI 관리자·대본 직원','재작업 대기',1,'revision','rose'],
  production:['제작 중','영상·음성 직원','로컬 제작 확인',3,'film',''],
  awaiting_video_approval:['영상 승인 대기','대표','영상 재생·검토',4,'shield','amber'],
  video_revision:['영상 수정 요청','영상·음성 직원','재작업 대기',3,'revision','rose'],
  completed:['완료','QA','최종 영상 보기',5,'check','green'],
};
const metrics = [
  ['review','대표 승인 대기','shield','amber',p=>p.stage.startsWith('awaiting_')||p.budget_pending>0],
  ['production','진행 중 제작','film','',p=>p.stage==='production'],
  ['revision','수정 요청','revision','rose',p=>p.stage.endsWith('_revision')],
  ['completed','완료','check','green',p=>p.stage==='completed'],
];
const reportOrigin = (plan) => plan?.provenance==='provider_model_claim' ? '실제 AI 결과' :
  plan?.provenance==='offline_http_fixture' ? '오프라인 HTTP 검증' : '오프라인 모의 검증';
const eventRoles = {writer:'대본 직원', editor:'편집 직원', voice:'음성 직원', qa:'QA 직원', research:'조사 직원'};
let studio = {projects:[], deferred:[]};
let filter = null;
let detail;
let routeVersion = 0;
let noticeTimer;

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method:'POST', headers:{'Content-Type':'application/json','X-Studio-Token':studio.token},
    body:JSON.stringify(body)
  });
  const value = await response.json();
  if (!response.ok) {
    const error=new Error(value.error);
    if (value.research) Object.assign(error,{code:value.code,research:value.research});
    throw error;
  }
  return value;
}
function notice(message, error=false) {
  const node = document.querySelector('#notice');
  node.textContent = message;
  node.className = error ? 'notice error' : 'notice';
  node.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { node.hidden = true; }, 4500);
}
function badge(label, symbol, tone='') {
  return `<span class="badge ${tone}">${icon(symbol)}${h(label)}</span>`;
}
const stateBadge = (stage) => {const s = statuses[stage]; return badge(s[0], s[4], s[5]);};
const projectHref = (p) => `#project/${encodeURIComponent(p.store)}/${encodeURIComponent(p.id)}`;
const detailApi = (p) => `/api/project/${encodeURIComponent(p.store)}/${encodeURIComponent(p.id)}`;
const blank = (text) => `<div class="empty">${icon('folder')} <p>${h(text)}</p></div>`;

function references() {
  const candidates = {'source-check':'AI 답변 출처·날짜 확인','csv-total':'가상 지출 CSV 검산',
    'same-prompt':'ChatGPT·Gemini 동일 요청 비교'};
  return `<section class="references" aria-labelledby="reference-heading">
    <div class="section-heading"><h2 id="reference-heading">참고자료</h2></div>
    ${studio.deferred.length ? `<div class="reference">
      ${badge('대표 선택 보류 · 승인 없음', 'bookmark', 'amber')}
      <ol>${studio.deferred[0].candidate_ids.map(id=>`<li>${h(candidates[id] || id)}</li>`).join('')}</ol>
      <p class="muted">대본·제작 권한 미부여 · ${h(time(studio.deferred[0].recorded_at))}</p>
      <details><summary>원본 결정 SHA-256</summary><p class="mono">${h(studio.deferred[0].source_decision_sha256)}</p></details>
    </div>` : blank('저장된 참고자료가 없습니다.')}
  </section>`;
}
function card(p) {
  const s = statuses[p.stage];
  return `<a class="project-card" href="${projectHref(p)}">
    <div class="thumbnail"><span class="placeholder">${icon('film')}영상 미리보기 없음</span>
    ${p.thumbnail ? `<img src="${h(p.thumbnail)}" alt="저장된 영상 키프레임">` : ''}</div>
    <div class="card-body"><div class="inline">${stateBadge(p.stage)}
      ${p.readonly ? badge('검증 사례','shield') : ''}${p.budget_pending ? badge('대표 예산 검토 대기','shield','amber') : ''}</div><h3>${h(p.goal)}</h3>
      <p class="muted">${icon('user')} ${h(s[1])} · ${h(time(p.updated_at))}</p>
      <div class="card-footer"><span>기획 ${p.plans} · 영상 ${p.videos}</span><span class="next">${h(s[2])} ${icon('arrow')}</span></div>
    </div></a>`;
}
function dashboard(route) {
  const group = metrics.find(([key]) => key === filter);
  const list = group ? studio.projects.filter(group[4]) : studio.projects;
  if (route === 'references') return references();
  return `${route === 'dashboard' ? `<section class="hero"><div><div class="eyebrow">${icon('clapper')} 대표 워크스페이스</div>
    <h1>영상 제작 스튜디오</h1><p>기획·대본부터 최종 영상까지, 프로젝트의 진행 상태와 대표 결정을 한곳에서 확인하세요.</p></div>
    <button class="button light" data-action="create">${icon('plus')} 새 프로젝트</button></section>
    <section class="metrics" aria-label="업무 상태 필터">${metrics.map(([key, name, symbol, tone, predicate]) =>
      `<button class="metric" data-filter="${key}" aria-pressed="${filter === key}"><span class="chip-icon ${tone}">${icon(symbol)}</span>
      <span><strong>${studio.projects.filter(predicate).length}</strong><small>${name}</small></span></button>`).join('')}</section>` : ''}
    <section aria-labelledby="projects-heading"><div class="section-heading"><div><h2 id="projects-heading">${group ? h(group[1]) : '프로젝트'}</h2>
    <p>${list.length}개 프로젝트</p></div>
    ${group ? '<button class="button ghost" data-action="clear">전체 보기</button>' : ''}
    ${route === 'projects' ? `<button class="button" data-action="create">${icon('plus')} 새 프로젝트</button>` : ''}</div>
    ${list.length ? `<div class="cards">${list.map(card).join('')}</div>` : blank('이 상태에 해당하는 프로젝트가 없습니다.')}</section>
    ${route === 'dashboard' ? references() : ''}`;
}
const steps = [['조사·주제','search'],['기획·대본','script'],['대표 1차 검토','shield'],
  ['제작·음성','mic'],['대표 2차 검토','film'],['완료·QA','check']];
function facts(rows) {
  return `<dl class="facts">${rows.map(([label, value]) => `<dt>${h(label)}</dt><dd>${h(value)}</dd>`).join('')}</dl>`;
}
function sourceLink(url) {
  return /^https:\/\//i.test(url) ? `<a href="${h(url)}" target="_blank" rel="noopener noreferrer">출처 열기 ↗</a>` : '';
}
function planPanel(p, plan, previous) {
  if (!plan) return `<section class="panel"><h2>기획·대본</h2><p class="muted">검토할 보고서가 없습니다. 조사·기획 작업에서 보고서를 제출하면 여기에 표시됩니다.</p></section>`;
  const script = plan.script;
  return `<section class="panel" id="plan-panel">
    <div class="panel-heading"><h2>${icon('script')} 기획·대본</h2>${versionSelect('plan',p.flow.plan_versions,plan)}</div>
    <h3>${h(plan.topic)}</h3><p>${h(plan.summary)}</p>${facts([['목표 길이',script.target_duration+'초'],['첫 3초 후크',script.hook_0_3s],['시청자 문제',script.viewer_problem],['전달할 효용',script.payoff],['작성 출처',reportOrigin(plan)],['비용 한도',`$${plan.cost_limit_usd}`],['보고 시각',time(plan.reported_at)]])}
    ${plan.research ? `<details class="subpanel" open><summary>조사 후보·선정 근거</summary>
      <p>${h(plan.research.selection_reason)}</p>
      ${plan.research.candidates.map(c=>`<p><strong>${h(c.topic)}</strong> · ${h(c.game ? c.game+' · ' : '')}${h(c.rationale)} · 쇼츠 성과 미검증${c.rights_plan ? ' · '+h(c.rights_plan) : ''}</p>`).join('')}
      <p class="muted">${h(plan.research.uncertainty)}</p></details>` : ''}
    ${plan.task_history ? `<details class="subpanel"><summary>AI 업무·내부 검토 이력</summary>
      <p>${h(plan.manager_plan?.rationale || plan.changes)}</p>
      ${plan.task_history.map(t=>`<div><h3>${h(t.versions.at(-1)?.source==='deterministic_system'?'시스템 스토리보드':eventRoles[t.role] || t.role)} · 버전 ${t.versions.length}</h3>
      ${t.reviews.map((r,i)=>`<p>v${i+1} · ${r.action==='accept'?'수락':'수정 요청'} · ${h(r.rationale)} ${h(r.feedback)}</p>`).join('')}</div>`).join('')}</details>` : ''}
    <details class="subpanel" open><summary>대본 전문</summary><p class="script">${h(script.transcript)}</p></details>
    <details class="subpanel" open><summary>장면 스토리보드</summary><div class="beats">${script.narrative_beats.map(beat => `<article class="beat">
      ${badge(`${beat.start}–${beat.end}초`,beat.shot_type==='demo'?'film':'script')}<h3>${h(beat.caption)}</h3>
      <p>${h(beat.screen)}</p><p class="muted">${h(beat.source_ref)} · ${beat.source_status==='pending'?'소스 미확보':'로컬 예시'}</p></article>`).join('')}</div></details>
    <details class="subpanel" open><summary>조사 출처·권리·미확인 항목</summary>
      ${plan.sources.length ? plan.sources.map(s=>`<p>${h(s.claim)} · ${h(s.observed_at)} · ${h(s.rights)} ${sourceLink(s.url)}</p>`).join('') : '<p class="muted">이 보고서에 등록된 외부 조사 출처가 없습니다.</p>'}
      <p>${h(plan.risks)}</p>${script.unknowns.map(u=>`<p class="muted">${h(u)}</p>`).join('')}</details>
    ${plan.representative_feedback?`<details class="subpanel" open><summary>대표 피드백 반영·관리자 재기획</summary><p>${h(plan.representative_feedback)}</p><p>${h(plan.changes)}</p><pre>${h(JSON.stringify(plan.goal_reviews,null,2))}</pre></details>`:''}
    <details class="subpanel"><summary>스토리보드 · 이전 버전 비교</summary>${[plan,previous].filter(Boolean).map(v=>`<h3>기획 v${v.version}</h3>${(v.task_history||[]).filter(t=>t.role==='editor').map(t=>`<p>${t.versions.at(-1)?.source==='deterministic_system'?'시스템 투영':'편집 직원'}</p><pre>${h(t.versions.at(-1)?.content||'')}</pre>`).join('')}`).join('')}</details>
    <details class="subpanel"><summary>변경사항·보고서 해시</summary><p>${h(plan.changes)}</p><p class="mono">${h(plan.sha256)}</p>
      ${previous ? `<p class="muted">이전 기획 v${previous.version} 대본</p><p class="script">${h(previous.script.transcript)}</p>` : ''}
      <p class="muted">내부 검토 ${plan.internal_reviews.length}건 · ${h(plan.internal_reviews.map(r=>r.action==='accept'?'수락':r.action==='revise'?'수정':'보류').join(' → '))}</p></details>
    ${p.readonly ? '' : '<button class="button ghost" data-action="plan-markdown">대표 검토 Markdown 내려받기</button>'}

  </section>`;
}
function versionSelect(kind, versions, chosen) {
  const label = kind === 'plan' ? '기획 버전' : '영상 버전';
  return `<label>${label}<select aria-label="${label}" data-version="${kind}">${[...versions].reverse().map(item =>
    `<option value="${item.version}" ${item.version===chosen.version?'selected':''}>v${item.version}</option>`).join('')}</select></label>`;
}
function reviewActions(p, kind, report) {
  if (p.readonly || p.stage !== `awaiting_${kind}_approval` || p.flow[`${kind}_versions`].at(-1)?.version !== report.version) return '';
  if(kind==='video' && report.render_receipt.visual_scope==='local_procedural_cards_no_game_footage') {
    return '<div class="actions subpanel"><button class="button secondary" data-review="video:request_revision">영상 수정 · 실제 제작 준비</button></div>';
  }
  const label = kind==='plan' ? '기획·대본 승인' : '최종 영상 승인';
  return `<div class="actions subpanel"><button class="button" data-review="${kind}:approve">${icon('check')}${label}</button>
    <button class="button secondary" data-review="${kind}:request_revision">${icon('revision')} 수정 요청</button></div>`;
}
function videoPanel(p, video) {
  if (!video) return '';
  const r=video.render_receipt;
  return `<section class="panel" id="video-panel"><div class="panel-heading"><h2>${icon('film')} 영상 검토</h2>${versionSelect('video',p.flow.video_versions,video)}</div>
    <video class="player" controls playsinline preload="metadata" poster="${h(video.thumbnail)}" src="${h(video.url)}" aria-label="영상 버전 ${video.version}"></video>
    <div class="inline">${badge('전체 디코딩 통과','check','green')}${r.visual_scope==='local_procedural_cards_no_game_footage'?badge('기술 시안 · 자체 카드','film','amber'):''}</div>
    ${facts([['제작 입력',`승인 기획 v${video.plan_version}`],['영상',`${r.width}×${r.height} · ${Number(r.duration_seconds).toFixed(3)}초`],
    ['음성',r.audio_mode==='espeak_reference'?'eSpeak 로컬 참조 음성':r.voice_engine==='synthetic_test_tone_not_tts'?'합성 테스트 신호':r.voice_engine|| (r.audio?'로컬 음성':'없음')],['자막',r.subtitle_sync==='measured_scene_audio'?'장면별 실측 발화 길이':'장면 단위'],
    ['QA','기술 검사 완료 · 시청·청취 품질 미평가'],['비용',`$${video.cost_usd}`]])}
    <details class="subpanel"><summary>변경사항·파일 및 기획 SHA-256</summary><p>${h(video.changes)}</p>
    <p class="muted">영상 파일</p><p class="mono">${h(video.artifact_sha256)}</p>
    <p class="muted">승인 기획</p><p class="mono">${h(video.plan_sha256)}</p></details>
    <details class="subpanel"><summary>시각 소스·사용 권리</summary>
    ${r.source_licenses.map(item=>`<p>${h(item.file)} · ${h(item.creator)} · ${h(item.license)}</p>`).join('')}
    <p class="muted">글꼴 · ${h(r.font_license)}</p></details>
    ${r.illustrative_scenes?.length?`<p class="warning">설명·참고 이미지 연출 · ${h(r.illustrative_scenes.join(', '))} · 실제 플레이 영상 아님</p>`:''}
    ${r.attribution?.length?`<details class="subpanel"><summary>Commons 표시 근거 · 게시 미승인</summary>
      ${r.attribution.map(item=>`<p>${h(item.scene_id)} · ${h(item.creator)} · ${h(item.text)} ·
      ${h(item.credit)} · ${sourceLink(item.original_page)} · ${sourceLink(item.license)}${item.share_alike?' · 동일조건변경허락':''}</p>`).join('')}</details>`:''}
    ${r.technical_quality?`<details class="subpanel"><summary>움직임·자막 기술 검토</summary>
      <p>고유 클립 ${h(r.technical_quality.unique_clip_hashes)}개 · 반복 ${h(r.technical_quality.repeats)}회 · 장면별 샘플 프레임 차이 ${h(r.review_material.map(x=>x.distinct_sampled_frames).join(', '))} / 3</p>
      <p>초당 자막 문자 수 ${h(r.technical_quality.caption_chars_per_second.join(', '))} · 읽기 편의·실제 청취는 대표 검토 필요</p>
      ${r.editing_sha256?`<p>편집 직원의 검토 기준 · ${h(r.editing_review_criteria)}</p>
        ${r.review_material.map((shot,i)=>`<p>장면 ${i+1} · 소스 시작 ${h(shot.source_start_frames)} 프레임 ·
          ${h(shot.framing)} · ${h(shot.caption_position)} · ${h(shot.editing_note)}</p>`).join('')}`:''}</details>`:''}
    </section>`;
}
function missionProposal(proposal) {
  return `${facts([
    ['Gemini 모델', proposal.model], ['고정 엔드포인트', proposal.endpoint],
    ['Gemini 프로젝트', proposal.account_project], ['YouTube 프로젝트', proposal.youtube_project],
    ['Gemini 호출 상한', proposal.limits.max_calls],
    ['YouTube 요청 상한', `검색 ${proposal.searches}회 · 영상 조회 ${proposal.videos}회`],
    ['수정 상한', `작업당 ${proposal.limits.max_revisions_per_task}회 · 전체 ${proposal.limits.max_total_revisions}회`],
    ['허용 비용', `미화 ${proposal.max_cost}달러 · 무료 조건만`],
    ['제공자 잔여량', `Gemini ${proposal.remaining_requests} · YouTube 검색 ${proposal.search_remaining} · 일반 단위 ${proposal.units_remaining}`],
    ['동의 유효 기한', time(proposal.expires_at)]
  ])}
    <p>Gemini에 목표, 입력 조건, 직원 지시와 산출물, 선행 결과 및 검토 피드백을 보냅니다. 조사 직원이 작성한 검색어와 발견한 공개 영상 ID는 YouTube Data API로 보냅니다. 조회한 공개 메타데이터는 내부 조사·검토에 사용하며 동의 정책의 보존 기준은 ${h(proposal.metadata_retention_days)}일입니다.</p>
    <p>Google 무료 서비스의 입력과 출력은 서비스 개선에 사용되거나 사람이 검토할 수 있습니다. 키 소속과 무료 조건은 소유자 확인에 근거합니다. 실패한 시도도 차감되며 자동 재호출이나 유료 전환은 없습니다.</p>
    ${proposal.cross_research?`<details><summary>Gemini에 함께 보내는 교차 조사 자료</summary><pre>${h(JSON.stringify(proposal.cross_research,null,2))}</pre></details>`:''}
    <p class="mono">동의 해시 ${h(proposal.review_hash)}</p>`;
}
function missionStatus(mission) {
  if (!mission) return '';
  const reasons = {mission_independent_web_research_unavailable:'조사 직원의 웹 접근 도구 미연결 · 게임·길이 근거 조사 불가',
    employee_web_authorization_required:'YouTube 공개 검색·메타데이터 접근의 별도 승인과 키 확인 필요',
    employee_web_failed_no_retry:'직원 웹 조사 실패 또는 미확정 · 자동 재호출 차단',
    mission_old_scope_superseded:'이전 조사 범위로 준비된 미션입니다.',
    mission_consent_incomplete:'서명 파일과 작업의 동의 상태가 일치하지 않습니다.',
    mission_internal_error:'실행 결과를 확정하지 못했습니다. 기록을 확인해 주세요.',
    mission_provider_evidence_incomplete:'대표 제출에 필요한 제공자 증거가 부족합니다.',
    consent_expired:'동의 유효 시간이 지났습니다.',
    provider_rate_limit:'요청 한도에 도달했습니다.', free_request_failed:'요청이 실패했거나 시간 초과되었습니다.',
    known_script_defects:'대본의 검증 결함이 남아 있습니다.', manager_stopped:'관리자가 내부 작업을 중단했습니다.',
    manager_plan_stopped:'관리자가 계획 단계에서 중단했습니다.', optional_technical_cap_reached:'승인된 호출 한도에 도달했습니다.'};
  const terminal = ['stopped','paused','needs_operational_permission'].includes(mission.status);
  const blocked = ['mission_independent_web_research_unavailable','mission_old_scope_superseded'].includes(mission.reason);
  const reason = mission.execution_error || mission.reason;
  const status = mission.supported === false ? '현재 컷룸 실행은 미션 01 게임 쇼츠 목표에 연결되어 있습니다.' :
    mission.running ? '기획 작업 진행 중 · 상태 새로고침으로 확인' :
    mission.status==='needs_user_review' ? '내부 검토 완료 · 대표 제출 확인' :
    terminal || mission.execution_error ? '실행 중단 · 자동 재호출 없음' :
    mission.status==='running' ? '실행 결과 미확정 · 중복 실행 차단' :
    blocked ? '독립 조사 연결 대기 · 실제 호출 0회' :
    mission.authorized ? '외부 전송 동의 완료 · 명시적 실행 대기' : '외부 AI 실행 권한 필요';
  return `<div class="subpanel"><h3>미션 01 · 기획과 대본</h3><p class="warning">${h(status)}</p>
    ${facts([['모델',mission.model],['기록된 시도',mission.attempts.length]])}
    ${reason ? `<p class="muted">${h(reasons[reason] || reason)}</p>` : ''}
    ${mission.assignments.map(t=>`<p class="muted">${h(eventRoles[t.role] || t.role)} · ${t.state==='accepted_by_ai_manager'?'내부 수락':'작업·검토 대기'} · v${t.versions}</p>`).join('')}
    ${mission.attempts.length ? `<details><summary>요청·응답 기록</summary>${mission.attempts.map(a=>`
      <div class="subpanel"><p>${h(a.phase)} · ${h(a.task_id || a.role_kind)} · ${h(a.status)} · HTTP ${h(a.http_status ?? '미수신')}</p>
      <p class="muted">${h(time(a.response_received_at || a.reserved_at))} · ${h(a.usage.total_tokens ?? '미확인')} 토큰 · ${a.cost_basis?'소유자 무료 조건 확인 기준':'청구 미확인'}</p>
      <p class="mono">요청 ${h(a.request_hash)}</p><p class="mono">응답 ${h(a.response_hash || '미수신')}</p></div>`).join('')}</details>` : ''}
    ${mission.web_attempts?.length ? `<details><summary>YouTube 조회 기록 (${mission.web_attempts.length}회)</summary>${mission.web_attempts.map(a=>
      `<p>${a.bucket==='search'?'검색':'영상 조회'} · ${h(a.status)} · HTTP ${h(a.http_status ?? '미수신')}</p>`).join('')}</details>` : ''}
    ${mission.can_connect ? '<button class="button secondary" data-action="mission-connect-web">독립 웹 조사 연결</button>' : ''}
    ${mission.can_prepare && !mission.proposal ? '<button class="button secondary" data-action="mission-prepare">외부 전송 동의 제안 준비</button>' : ''}
    ${mission.proposal ? `<div class="subpanel"><h4>외부 전송 동의 제안</h4>${missionProposal(mission.proposal)}
      <button class="button secondary" data-action="mission-consent">외부 전송 동의 검토</button></div>` : ''}
    ${mission.can_run ? '<button class="button secondary" data-action="mission-run">미션 01 실행</button>' : ''}
    ${mission.can_report ? '<button class="button secondary" data-action="mission-report">내부 검토 결과 대표 제출</button>' : ''}
    <button class="button ghost" data-action="refresh">${icon('revision')} 상태 새로고침</button></div>`;
}
function visualDiscovery(a) {
  return a.adaptive_discovery?.status && a.adaptive_discovery.status!=='unavailable'
    ? a.adaptive_discovery : a.media_discovery;
}

const commonsReason={
  page_structure:'페이지 구조 오류',file_namespace:'파일 이름공간 불일치',page_id:'페이지 ID 오류',file_title:'파일 제목 오류',
  duplicate_page_id:'응답 내 페이지 ID 중복',
  imageinfo_missing:'원본 메타데이터 누락',imageinfo_shape:'원본 메타데이터 구조 오류',mime:'MIME 불일치·미지원',
  media_type:'미디어 유형 불일치',original_url_missing:'원본 URL 누락',original_url_invalid:'원본 URL 안전 검증 실패',
  size_invalid:'파일 크기 값 오류',size_limit:'파일 크기 상한 초과',pages_shape:'응답 페이지 배열 구조 오류',pages_limit:'응답 개수 상한 초과',
  missing_author_or_source:'저작자·출처 미확인',original_checksum_unverified:'원본 체크섬 미확인',
  unsupported_or_missing_license:'라이선스 미확인·미지원',attribution_requirement_unverified:'표시 의무 미확인',
  additional_restrictions:'추가 권리 제한'
};
function commonsTrace(label,rows) {
  if (!rows?.length) return '';
  const counts=data=>Object.entries(data||{}).map(([code,count])=>`${commonsReason[code]||code} ${count}건`).join(' · ');
  return `<details class="subpanel"><summary>${h(label)} (${rows.length}회)</summary>${rows.map(row=>{
    const diag=row.diagnostics;
    return `<article><p>${h(row.scene_ids.join(', '))} · ${row.media==='image'?'이미지':'영상'} · ${h(row.query)}</p>
      <p>${h(({completed:'완료',reserved:'결과 미확정',failed_or_uncertain:'실패 또는 결과 미확정'})[row.status]||row.status)} ·
      후보 ${h(row.candidate_count??'미확인')}건 · 기술 제외 ${h(row.rejected??'미확인')}건</p>
      ${!diag?'<p>개별 판정과 원본 응답 보존 기록 없음</p>':`
        ${diag.response_issue?`<p>${h(commonsReason[diag.response_issue])} · 반환 ${h(diag.returned??'미확인')}</p>`:''}
        <p>기술 사유 집계 · ${h(counts(diag.technical_counts)||'없음')} · 권리 사유 집계 · ${h(counts(diag.rights_counts)||'없음')}</p>
        ${diag.pages.map(page=>`<p>${h(page.page_id??'ID 미확인')} · ${h(page.title??'제목 비공개 또는 미확인')} ·
          ${h(page.mime??'MIME 미확인')} · ${h(page.media_type??'유형 미확인')} · ${h(page.size_bytes??'크기 미확인')}바이트 ·
          ${page.url_allowed?'원본 경로 통과':'원본 경로 미통과'}${page.provenance_removed?' · 출처 추적 값 제거':''} ·
          ${h(page.technical_reasons.map(code=>commonsReason[code]).join(', ')||'기술 통과')} ·
          ${h(page.rights_reasons?.map(code=>commonsReason[code]).join(', ')||'')} ${page.scene_suitability?' · 장면 적합성 미평가':''}</p>`).join('')}`}
      </article>`;
  }).join('')}</details>`;
}

function productionPanel(p) {
  const a=p.autonomous_production;
  if (!a) return '';
  const source=a.source_assessment;
  const timing=a.timeline, operating=a.owner_policy, assets=a.asset_execution, discovery=visualDiscovery(a);
  const alternatives=discovery?.fallback||a.media_discovery?.fallback;
  const policyStates={available:'승인 대기',active:'승인 범위 활성',expired:'만료',revoked:'철회',stopped:'실패 또는 미확정으로 중단',blocked:'현재 키 또는 계정 설정 확인 필요'};
  const routeLabels={local_library:'로컬 자산 보관함', official_direct_media:'공식 직접 제공 자료',
    public_metadata_search:'공개 메타데이터 검색 제안', own_capture:'권리 확인 자체 캡처', hold:'자산 대기'};
  return `<section class="panel" id="production-detail"><h2>제작 상세</h2>
    <p>관리자 계획 Gemini 텍스트 최대 1회 · 현재 시도 ${h(a.attempts)}회.</p>
    <p>기존 Puck 7/10 평가는 이전 안내 영상 표본입니다. 이 영상의 보이스는 관리자 계획에서 선택합니다.</p>
    ${a.plan?`<h3>관리자 제작 계획 원문</h3><p>기존 설명은 작성 언어로 보존합니다.</p>
      <p>${h(a.plan.voice.tool)} · ${h(a.plan.voice.model)} · ${h(a.plan.voice.voice)} · ${h(a.plan.voice.rationale)}</p>
      <p>${h(a.plan.timeline)}</p><ul>${a.plan.work_order.map(item=>`<li>${h(item)}</li>`).join('')}</ul>
      <p>검토 기준 · ${h(a.plan.review_criteria.join(' · '))}</p>
      <p>로컬 인수 폴더 <span class="mono">${h(a.inbox)}</span></p>
      ${a.plan.scenes.map(s=>{
        const voice=a.voices[s.scene_id];
        return `<article><p><strong>${h(s.scene_id)}</strong> · ${h(s.request)} · ${h(s.direction)}</p><p>승인 장면 · ${h(a.scope.storyboard.find(shot=>shot.scene_id===s.scene_id)?.caption)}</p><p>${h(s.speech_style)}</p>
          <p>영상 · ${a.clips.includes(s.scene_id)?'인수 완료':'소스 확인 대기'}
          ${voice?.attempted?` · 음성 시도 · ${h(({audio_validated:'파일 검사 완료',failed_or_uncertain:'실패 또는 미확정',
            receipt_invalid:'음성 기록 검증 실패'})[voice.status]||'결과 미확정')} · 재시도 없음`:''}</p>
          ${voice?.listening?`<p>대표 청취 의견 · ${h(voice.listening.opinion)} · 이 장면에 한함</p>`:''}
          ${voice?.audio_url?`<p>${h(voice.duration_seconds)}초 / 승인 ${h(voice.approved_seconds)}초 · ${voice.fits_timeline?'길이 조건 충족 · 청취 평가 필요':'승인 길이 초과 · 합성 차단'}</p>
            <audio controls preload="none" src="${h(voice.audio_url)}" aria-label="${h(s.scene_id)} 음성 검토"></audio>`:''}</article>`;
      }).join('')}`:''}
    ${a.publisher_discovery?`<details class="subpanel"><summary>공식 제작사 자료</summary>
      <p>정적 페이지에서 확인한 메타데이터입니다. 로컬 편집 권리는 별도 검토합니다.</p>
      ${(a.publisher_discovery.result?.pages||[]).map(row=>`<p>${sourceLink(row.url)} · ${h(({robots_read:'robots 확인',robots_unavailable:'robots 확인 불가',robots_permission_unconfirmed:'robots 접근 허용 미확인',publisher_access_unconfirmed:'제작사 접근 허용 미확인',restricted_or_unavailable:'접근 제한 또는 응답 없음',restricted:'접근 제한',read:'페이지 확인'})[row.status])}</p>`).join('')}
      ${(a.publisher_discovery.result?.media||[]).map(row=>`<p>${h(row.title)} · ${h(row.mime)} · ${sourceLink(row.page)} · ${row.asset_access?'권리 검토 필요':'파일 서버 접근 허용 미확인'}</p>`).join('')}
      ${(a.publisher_discovery.result?.decisions||[]).map(row=>`<p>${h(row.scene_id)} · ${h(({publisher_candidate:'공식 후보',publisher_permission:'추가 허가 필요',manual_capture:'허가된 자체 캡처 검토',hold:'보류'})[row.route])} · ${h(row.evidence)} · ${h(row.reason)}</p>`).join('')}
      ${a.publisher_discovery.status==='active'?'<button class="button secondary" data-action="production-publisher-revoke">공식 자료 탐색 승인 철회</button>':''}
    </details>`:''}
    ${discovery?`<section class="subpanel"><h3>Commons 영상·이미지 탐색</h3>
      <p>검색 메타데이터만으로 게임 IP, 음원 또는 타인의 영상 사용권은 확인되지 않습니다.</p>
      ${a.media_discovery?.status==='empty' && a.adaptive_discovery?.status!=='unavailable'?
        '<p>기존 영상 검색은 후보 0건으로 종료했습니다. 새 검색은 짧은 제목과 영상·이미지 유형을 사용합니다.</p>':''}
      ${discovery.result?`<p>후보 ${h(discovery.result.candidates.length)}개 · 안전 또는 형식 검증에서 제외 ${h(discovery.result.rejected_unsafe)}개</p>
        ${discovery.result.candidates.map(c=>`<p>${h(c.scene_ids.join(', '))} · ${h(c.title)} · ${h(c.license_name||'라이선스 미확인')} ·
          ${c.reviewable?'대표 권리 검토 대상':'권리·표시 근거 부족'} · ${sourceLink(c.original_page)}</p>`).join('')}`:''}
      ${commonsTrace('최초 검색 기록',a.media_discovery?.search_trace)}
      ${commonsTrace('개선 검색 기록',a.adaptive_discovery?.search_trace)}
      ${commonsTrace('제외 원인 진단 기록',a.commons_diagnostic?.search_trace)}
      ${commonsTrace('관련성 복구 검색 기록',a.commons_relevance?.trace)}
      ${a.commons_relevance?`<details class="subpanel"><summary>장면 적합성 판단</summary>
        <p>제목·설명·카테고리 근거만 사용합니다. 실제 화면·권리는 확인되지 않았습니다.</p>
        ${(a.commons_relevance.result?.candidates||[]).map(c=>`<p>${h(c.title)} · ${h(c.id)}
          ${c.relevance.map(r=>`<span> · ${h(r.scene_id)} ${h(({suitable:'적합 후보',unclear:'불명확',unrelated:'무관'})[r.decision])}
            ${h(({gameplay:'플레이 후보',illustrative:'설명 이미지',unknown:'유형 미확인'})[r.depiction])} · ${h(r.evidence)} · ${h(r.reason)}</span>`).join('')||' · 모델 검토 제외'}</p>`).join('')}
        ${(a.commons_relevance.screening?.screened||[]).map(row=>`<p>${h(row.scene_id)} · ${h(row.candidate_id)} ·
          ${h(({rights_ineligible:'권리 근거 부족',unrelated_depiction:'장면 목적과 무관',review_capacity:'검토 상한'})[row.reason])}</p>`).join('')}
        ${a.commons_relevance.status==='active'?'<button class="button secondary" data-action="production-relevance-revoke">관련성 복구 승인 철회</button>':''}
      </details>`:''}
      ${a.commons_diagnostic?.status==='active'?'<button class="button secondary" data-action="production-diagnostic-revoke">진단 승인 철회</button>':''}
      ${alternatives?`<h4>기존 편집 직원의 대안 제안</h4>${alternatives.options.map(item=>
        `<p>${h(item.scene_id)} · ${h(item.suggestion)} · 필요 권리 ${h(item.rights_needed)}
        ${item.route==='authorized_capture'?' · 담당자 권리 확인·캡처 필요':item.route==='verify_generation'?' · 무료·출력 권리 확인된 생성 실행기 미지원':''}</p>`).join('')}`:''}
      ${discovery.status==='active'?'<button class="button secondary" data-action="production-discovery-revoke">영상 탐색 승인 철회</button>':''}
    </section>`:''}
    ${assets?`<section class="subpanel"><h3>권리 확인 소스 인수·편집</h3>
      <p>권리 근거를 등록한 공식 직접 MP4, 권리 확인 Commons 영상 또는 로컬 보관함을 사용합니다. 공개 영상·검색 메타데이터는 단서이며, 확인된 무료 생성 도구는 없습니다.</p>
      <p>지원 편집 · 24fps 구간, 레터박스, 컷, 자막, 권리 확인 이미지의 팬·줌·컷. 시청 품질은 대표 검토가 필요합니다.</p>
      ${assets.decision?`<p>${h(assets.decision.review_criteria)}</p>${assets.decision.scenes.map(s=>`<p>${h(s.scene_id)} · ${h(s.asset_id)} · ${h(s.suitability)}</p>`).join('')}`:''}
      ${assets.expires_at && assets.status!=='revoked'?'<button class="button secondary" data-action="production-assets-revoke">자산 범위 승인 철회</button>':''}
    </section>`:''}
    ${operating && operating.status!=='unavailable'?`<section class="subpanel"><h3>개인 운영 설정</h3>
      <p>${h(policyStates[operating.status])} · 무료 전용 · 요청 사용 ${h(operating.used??0)}/${h(operating.proposal.units.length)} · 공급자 잔량·청구 미확인</p>
      ${operating.expires_at?`<p>유효 기한 ${h(time(operating.expires_at))}</p>`:''}
      ${operating.expires_at && operating.status!=='revoked'?'<button class="button secondary" data-action="production-policy-revoke">운영 정책 철회</button>':''}
    </section>`:''}
    ${timing?.proposal?`<section class="subpanel"><h3>실측 시간 조정안 v${h(timing.proposal.version)}</h3>
      <p>${timing.status==='approved'?'대표 승인 완료':timing.status==='hold'?'관리자 보류':'대표 승인 대기'}</p>
      <p>${h(timing.proposal.decision.rationale)}</p><p>${h(timing.proposal.decision.quality_checks)}</p>
      <p class="mono">${h(timing.proposal.sha256)}</p></section>`:''}
    ${source?`<section class="subpanel"><h3>자산 확보 업무</h3>
      <p>권리 정보가 등록된 로컬 자산 ${h(source.available_count??0)}개 · 신규 검색, 다운로드 및 생성은 승인 범위에 포함되지 않습니다.</p>
      ${source.result?`<p>직원 확보 제안 · 직접 시청 및 사용권 확인 필요</p>
        ${source.result.scenes.map(s=>`<article><p><strong>${h(s.scene_id)}</strong> · ${h(routeLabels[s.route])}
          ${s.asset_id!=='none'?` · ${h(s.asset_id)}`:''}</p><p>${h(s.rationale)} · ${h(s.next_step)}</p><p>확인 기준 · ${h(s.suitability_check)}</p></article>`).join('')}
        <p>검토 기준 · ${h(source.result.review_criteria.join(' · '))}</p>`:''}
    </section>`:''}
  </section>`;
}
function operations(p) {
  if (p.readonly) return '<p class="warning">기존 검증 사례 · 읽기 전용</p>';
  if (p.stage === 'completed') return '<p class="warning">최종 대표 승인이 기록되었습니다. 게시 작업은 별도입니다.</p>';
  const attempt = p.flow.render_attempts.at(-1);
  const failed = attempt?.status === 'failed' ? `<p class="warning">최근 렌더 실패 · ${h(attempt.reason)}</p>` : '';
  if (attempt?.status === 'reserved') return '<p class="warning">로컬 렌더 실행 중 또는 결과 미확정 · 중복 렌더 차단</p>';
  if (p.stage==='goal_submitted') return `<button class="button secondary" data-action="mission">${icon('folder')} 미션 01 준비</button><p class="muted">기획 작업만 준비합니다. 외부 전송은 별도 승인 후 실행합니다.</p>`;
  if (p.rework && p.stage==='plan_revision') return reworkPanel(p);
  if (p.autonomous_production) return failed;
  if (p.production) {
    const prep=p.production;
    const direction=prep.direction;
    if (!direction) return `<p class="warning">승인 제작 입력 검증 실패 · ${h(prep.reason)}</p>`;
    return `${failed}<section class="subpanel"><h3>세로 9:16 테스트 제작</h3>
      <p>승인된 장면과 자막을 자체 생성 카드에 표시합니다. 게임 화면은 확보되지 않았으며 자막은 장면 단위로 맞춥니다.</p>
      ${prep.ready?'<button class="button secondary" data-action="mission-preview">세로 기술 시안 제작</button>':`<p class="warning">제작 준비 확인 필요 · ${h(prep.reason)}</p>`}
      <details><summary>제작 준비 · 음성 및 외부 전송 범위</summary>
      <p>${h(direction.direction)}</p><p>이전 Gemini/Puck 청취 표본의 자연스러움은 대표 평가 7/10입니다. 이번 게임 대본의 음성 품질은 미평가입니다.</p>
      <p>${prep.local_speech?'기존 MeloTTS 로컬 실행 가능 · 청취 미검증':'로컬 음성 런타임 또는 모델 미확보 · 무음 시안 가능'}</p>
      ${direction.external.map(call=>`<p>${h(call.kind)} · ${h(call.model)} · 후보 상한 ${h(call.proposed_max_calls)}회<br>전송 후보 자료 · ${h(call.data)}</p>`).join('')}
      <p>${h(direction.pricing)}. 현재 승인된 외부 요청 0회입니다. 지정 표본의 기존 TTS 승인으로는 이 대본을 보낼 수 없습니다.</p>
      <button type="button" class="button ghost" disabled>새 외부 전송 동의</button>
      <button type="button" class="button ghost" disabled>외부 AI 제작 실행</button></details></section>`;
  }
  if (p.mission && ['production','video_revision'].includes(p.stage) && !p.flow.plan_versions.at(-1)?.render_spec) {
    return '<p class="warning">기획 승인 기록 완료 · 제작 사양 등록 대기</p>';
  }
  if (p.mission && p.stage==='research_planning') return '';
  if (p.stage==='plan_revision') return `<button class="button secondary" data-action="planning">${icon('folder')} 기획 작업 열기</button><p class="muted">내부 작업을 열고 보고서 제출을 기다립니다.</p>`;
  if (['production','video_revision'].includes(p.stage)) return `${failed}<button class="button secondary" data-action="produce">${icon('film')} 로컬 기술 시안 제작</button><p class="muted">승인된 대본으로 로컬 렌더러를 실행합니다. 외부 API 비용은 발생하지 않습니다.</p>`;
  return '<p class="muted">기획·대본이나 영상 보고서를 확인해 주세요.</p>';
}
function reworkPanel(p) {
  const r=p.rework;
  if (!r) return '';
  const labels={available:'실행 동의 준비',pending:'새 외부 전송 동의 대기',approved:'동의 완료 · 실행 대기',running:'AI 재기획·재작업 실행 중',stopped:'재작업 중단 · 자동 재호출 없음',completed:'새 기획 대표 재승인 대기'};
  const progress=r.progress;
  return `<section class="panel"><h3>대표 피드백 AI 재작업</h3><h3>${h(progress?.title||labels[r.status]||'상태 확인 필요')}</h3>
    <p class="muted">프로젝트는 대표의 기획 수정 요청을 유지합니다. 아래는 그 요청에 대한 최신 AI 재작업 현황입니다. 이전 수락 기획과는 별도입니다.</p>
    ${progress?`${facts([['현재 단계',progress.current],['담당',progress.actor],['최종 갱신',progress.updated_at?time(progress.updated_at):'기록 없음']])}
      <ol class="beats" aria-label="AI 재작업 단계">${progress.cards.map(c=>`<li class="beat"><strong>${h(c.label)}</strong><p>${h(c.actor)} · ${h(c.state)}</p></li>`).join('')}</ol>
      <p class="${r.status==='stopped'?'warning':'muted'}">${h(progress.message)}</p><p><strong>다음 행동:</strong> ${h(progress.next_action)}</p>
      ${facts([['기록된 요청 시도',progress.counts.attempts],['전송 시작 기록',progress.counts.transport_started],['정상 HTTP 응답',progress.counts.http_ok],['서버 검증 완료',progress.counts.server_validated],['전송 실패 기록',progress.counts.failed],['무료 quota / 청구','미확인 / 독립 검증 안 됨']])}
      <p class="muted">HTTP 응답 완료와 결과물 수락은 다릅니다. 시도에는 실패·수신 불명 요청도 포함됩니다.</p>
      <details><summary>기술 진단·호출 기록</summary><p>${h(r.error||r.recovery?.error||'현재 오류 코드 없음')}</p><pre>${h(JSON.stringify(progress.ledger,null,2))}</pre></details>`:''}
    ${r.final_recovery?`<section class="subpanel"><h3>최종 기준 집계 · 대표 제출</h3>${r.final_recovery.eligible
      ?'<p>이미 수락된 대본과 스토리보드의 검토를 집계합니다. 외부 요청 0회.</p><button class="button secondary" data-action="rework-finalize-recover">기존 검토로 대표 제출 복구</button>'
      :`<p class="warning">${r.final_recovery.error==='consent_expired'?'기존 동의가 만료되어 제출을 복구할 수 없습니다.':h(r.final_recovery.error)}</p>`}</section>`:''}
    ${r.recovery_audit?.kind==='editor_handoff_after_mismatch'?`<section class="subpanel"><h3>편집 인계 중단 · 스토리보드 검토</h3><p>수락된 대본에서 스토리보드를 그대로 만들고 AI 관리자가 검토합니다.</p>${r.recovery_audit.safe_for_recovery_proposal?'<button class="button secondary" data-action="rework-script-recover-prepare">스토리보드 관리자 검토 준비</button>':''}</section>`
    :r.recovery_audit?.kind==='manager_review_after_repeat'?`<section class="subpanel"><h3>중복 응답 중단 · 기존 대본 재검토</h3>
      <p>보존된 첫 대본을 AI 관리자가 다시 검토합니다. 재기획과 첫 대본 작성은 반복하지 않습니다.</p>
      ${r.recovery_audit.safe_for_recovery_proposal?'<button class="button secondary" data-action="rework-script-recover-prepare">기존 대본 관리자 재검토 준비</button>':''}</section>`
    :r.recovery_audit?`<section class="subpanel"><h3>중단된 대본 검토 · 기존 자료 분석</h3>
      <p class="warning">이전 AI 관리자 검토는 최종 검증을 통과하지 못했습니다. 기존 작업과 API 호출 3회를 변경하지 않습니다.</p>
      ${facts([['이전 기획 호출과 결과',r.recovery_audit.reusable_plan?'검증 완료 · 재사용 후보':'재사용 조건 미충족'],['이전 대본 호출과 결과',r.recovery_audit.reusable_writer?'검증 완료 · 재사용 후보':'재사용 조건 미충족'],['저장된 관리자 수정 의견',r.recovery_audit.review_available?'있음 (최종 미검증)':'검증 필요'],['대본 결함 재검사',r.recovery_audit.checks_available?'완료':'추가 확인 필요'],['발견된 결함',r.recovery_audit.defect_count??'미확인'],['수정 의견에 빠진 식별자',r.recovery_audit.missing_issue_ids?.join(', ')||'없음 또는 미확인'],['복구 후보 판정',r.recovery_audit.safe_for_recovery_proposal?'기존 결과 재사용 가능한 신규 작업 후보':'재사용 근거 추가 확인 필요'],['기존 작업 재실행','차단 · 원본 보존']])}
      ${r.recovery_audit.review_available?`<p><strong>저장된 AI 관리자 수정 의견</strong></p><p class="script">${h(r.recovery_audit.manager_feedback)}</p>`:''}
      ${r.recovery_audit.missing_defects?.length?`<details><summary>시스템 검출 항목과 수정 방법</summary><pre>${h(JSON.stringify(r.recovery_audit.missing_defects,null,2))}</pre></details>`:''}
      <p class="muted">저장된 기획과 대본은 재사용 후보입니다. 이 점검만으로 AI 관리자가 승인했거나 기존 중단 작업을 계속 실행할 수 있다는 뜻은 아닙니다.</p>
      ${r.recovery_audit.safe_for_recovery_proposal?'<p>기획·대본 원본을 보존하고, 새 작업은 대본 수정부터 시작합니다. 새 외부 전송은 별도 동의가 필요합니다.</p><button class="button secondary" data-action="rework-script-recover-prepare">기존 대본으로 수정 작업 준비</button>':''}
    </section>`:''}
    ${progress?.quality_report?`<section class="panel"><h3>${progress.quality_report.source==='legacy_failure_diagnostic_not_manager_review'?'과거 검토 실패 진단 · 대표 지시 필요':'AI 관리자 품질 보고 · 대표 지시 필요'}</h3>
      <p class="warning">${progress.quality_report.source==='legacy_failure_diagnostic_not_manager_review'
        ?'이전 AI 관리자 응답은 HTTP 200이지만 검증에 실패했습니다. 아래 내용은 관리자 승인이나 확정 평가가 아니며, 대표가 저장된 대본을 직접 판단해야 합니다.'
        :'수정 한도에 도달했거나 AI 관리자가 대표 판단을 요청했습니다. 자동 재호출은 없습니다.'}</p>
      <p><strong>대본 직원 산출물</strong></p><pre>${h(r.quality_script||'저장된 대본 없음')}</pre>
      <p><strong>관리자 선택 / 시스템 처리</strong> · ${h(progress.quality_report.original_action)} / ${h(progress.quality_report.decision)} · ${h(progress.quality_report.reason)}</p>
      ${progress.quality_report.manager_review ? `<p><strong>관리자 판단 원문</strong> · ${h(progress.quality_report.manager_review.rationale)}</p>` : ''}
      <p><strong>시스템 검증 사유</strong> · 인용 불일치(evidence_not_found), 관리자 미충족 판단(not_met), 현재 수치 미검증 등</p><pre>${h(JSON.stringify(progress.quality_report.failed_checks,null,2))}</pre>
      <p><strong>${progress.quality_report.source==='legacy_failure_diagnostic_not_manager_review'?'과거 검토 상태(미검증)':'AI 관리자 검토 근거'}</strong></p><pre>${h(JSON.stringify(progress.quality_report.evidence||{},null,2))}</pre>
      <p><strong>${progress.quality_report.source==='legacy_failure_diagnostic_not_manager_review'?'안내 및 대표 직접 검토 요청':'수정 제안'}</strong></p><p>${h(progress.quality_report.feedback||'구체적인 수정 지시가 기록되지 않았습니다.')}</p>
      ${r.quality_decision?`<p><strong>대표 결정:</strong> ${h(r.quality_decision.action==='request_revision'?'수정 지시 기록됨':'보류')} · ${h(r.quality_decision.feedback||'추가 의견 없음')}</p>
      <p class="muted">수정 지시를 저장했지만 새 AI 작업을 시작하지는 않았습니다. 새 전송은 별도 실행 범위와 동의가 필요합니다.</p>
      ${r.quality_decision.action==='request_revision'?'<button class="button secondary" data-action="rework-quality-prepare">수정 지시 기반 새 AI 작업 준비</button>':''}`
      :`<button class="button secondary" data-action="rework-quality-revise">수정 지시 남기기</button>
       <button class="button ghost" data-action="rework-quality-hold">판단 보류</button>`}
      </section>`:''}
    <details><summary>저장된 대표 수정 요청</summary><p>${h(r.feedback)}</p></details>
    <p class="muted">이전 버전은 보존됩니다. 관리자 재기획 → 대본/스토리보드 → 의미·형식 검토 후 같은 컷룸에 새 버전을 제출합니다. 웹 조회·음성·렌더·게시 없음.</p>
    ${r.settings&&!r.settings.ready?`<p class="warning">Gemini 실행 설정 확인 필요: ${h(r.settings.missing.join(', '))}. 서버 환경에 설정 후 서버를 재시작하세요. 키 값은 입력하거나 공유하지 마세요.</p>`:''}
    ${r.recovery?.error?`<p class="warning">재개 차단: 동의·서명·전송 이력 확인이 필요합니다. 만료 동의는 새 동의 검토가 필요하며 반복 클릭하지 마세요.</p>`:''}
    ${r.recovery?.eligible&&r.attempts===0?`<p>과거 중단 기록과 시도 0은 보존됩니다. 현재 승인 범위로 명시적으로 한 번 재개할 수 있습니다.</p>${r.settings?.ready?'<button class="button" data-action="rework-recover">설정 확인 후 AI 재작업 재개</button>':''}`:''}
    ${r.proposal?facts([['모델',r.proposal.model],['프로젝트',r.proposal.rework_scope.account_project],['무료 quota / 청구','unknown / unverified'],['시도',r.attempts],['호출 상한',r.proposal.limits.max_calls===null?'미설정 (동의 차단)':r.proposal.limits.max_calls+'회'],['수정 한도',r.proposal.limits.max_total_revisions+'회']]):''}
    ${r.status==='pending'&&r.proposal?.limits?.max_calls===null?'<p class="muted">동의 화면을 열 때 기존 미설정 호출 상한을 최대 7회로 자동 제한합니다. Gemini는 호출하지 않습니다.</p>':''}
    ${r.proposal?`<details><summary>전송 범위·재기획·검토 기록</summary><p>${h(r.proposal.rework_scope.data_policy)}</p><p>원 목표·저장된 대표 피드백·이전 대본/스토리보드·공개 관측을 Google에 전송합니다. 입출력 개선 활용·인적 검토 가능. 무료 여부는 소유자 확인이며 독립 검증되지 않았습니다.</p><pre>${h(JSON.stringify({inputs:r.proposal.quality_contract.inputs,replan:r.replan,reviews:r.reviews},null,2))}</pre></details>`:''}
    ${r.new_attempt?'<p>이전 실패·피드백은 보존합니다. 새 작업 1회와 표시된 호출·수정 한도를 별도로 검토하고 동의하세요. 기존 동의는 새 전송을 승인하지 않습니다. Gemini 503이 다시 발생할 수 있으며 자동 재시도하지 않습니다.</p><button class="button secondary" data-action="rework-new-prepare">새 AI 재작업 준비</button>':''}
    ${r.history?.length?`<details><summary>이전 재작업 시도 · 보존 기록</summary>${r.history.map(x=>`<p>이전 작업 ${h(x.job)} · 중단/완료 기록 보존</p>`).join('')}<p>현재 작업 ${h(r.job)} · 이전 동의와 별개</p></details>`:''}
    ${r.status==='available'?'<button class="button secondary" data-action="rework-prepare">AI 재작업 동의 준비</button>':''}
    ${r.status==='pending'?'<button class="button secondary" data-action="rework-consent">새 외부 전송 동의</button>':''}
    ${r.status==='approved'&&r.settings?.ready?'<button class="button" data-action="rework-run">AI 재작업 시작</button>':''}
    ${r.status==='running'?'<p class="muted">중복 시작은 차단됩니다. 서버 종료로 상태가 불명확하면 자동 재시작하지 않습니다.</p>':''}<button class="button ghost" data-action="refresh">상태 새로고침 · 조회만</button></section>`;
}

function budgetSetupPanel(p) {
  const setup=p.budget_setup;
  if (!setup||p.readonly) return '';
  if (setup.status==='available') return `<section class="panel" id="budget-setup"><h2>프로젝트별 예산 모드</h2>
    <p>60초 대본 경로 · 초기 예산 0 · 외부 데이터 전송 동의와 예산 승인을 따로 검토합니다.</p>
    <p class="muted">${h(setup.local_setup)}</p><button class="button secondary" data-action="budget-prepare">예산 모드 등록 준비</button></section>`;
  return `<section class="panel" id="budget-setup"><h2>공급자 데이터 전송 동의 · ${h(setup.status)}</h2>
    ${facts([['프로젝트',p.id],['목표',setup.goal],['모델/API',setup.model+' / '+setup.endpoint],['계정 프로젝트',setup.account_project],['무료 전용',setup.free_only?'예':'아니요'],['동의 만료',time(setup.expires_at)]])}
    <p>${h(setup.data_policy)}</p><p>전송 범위: ${h(setup.data_scopes.join(', '))}</p>
    <p>입력 대상: ${h(setup.inputs.target_segment)} · ${h(JSON.stringify(setup.inputs.constraints))}</p>
    <p class="muted">${h(setup.responsibility)} · 예산 승인은 별도이며 등록만으로 전송하지 않습니다.</p>
    <details><summary>검토할 제안 해시</summary><p class="mono">${h(setup.review_hash)}</p></details>
    ${['expired','rejected'].includes(setup.status)?'<button class="button secondary" data-action="budget-reprepare">이전 제안을 보존하고 새 제안 준비</button>':''}
    <p>이전 기록 ${h(setup.history_count)}건 · 저장된 상태 ${h(setup.previous_status)} · 현재 상태 ${h(setup.status)}</p>
    ${setup.status==='pending'?'<button class="button" data-consent="approve">데이터 전송 동의·등록</button><button class="button ghost" data-consent="reject">동의 거절·미등록</button>':''}</section>`;
}
function budgetPanel(p) {
  const b=p.budget;
  if (!b) return '';
  return `<section class="panel" id="budget-panel"><h2>AI 사용 예산</h2>
    <p class="muted">무료 서비스 · 예산 승인과 외부 전송 동의는 별개입니다. 승인 후 실행은 아래 버튼으로 시작합니다.</p>
    ${facts(Object.entries(b.resources).map(([key,v])=>[key,`승인 ${v.approved} · 소모 ${v.consumed} · 잔여 ${v.remaining} · 불명 ${v.unresolved} (${v.unit})`]))}
    <p>${h(b.scope.purpose)}</p><p>${h(b.scope.data_policy)}</p><p>공급자 동의: ${h(b.consent_state)}</p>
    ${facts([['프로젝트',p.id],['모델/계정',Object.values(b.scope.services).map(v=>v.model+' / '+v.account_project).join(', ')],['동의 만료',time(b.scope.consent_expires_at)],['실제 비용','미확인']])}
    ${b.requests.map(r=>`<article class="subpanel"><h3>${r.status==='pending'?'대표 예산 검토 대기':h(r.status)}</h3>
      <p>추가 수량: ${h(JSON.stringify(r.amounts))}</p><p>${h(r.reason)}</p><p>완료한 일: ${h(r.progress)}</p>
      <p>${h(r.cost_impact)} · ${h(r.failure_risk)}</p><p class="mono">작업계획 ${h(r.plan_hash)}</p>
      <details><summary>검토 해시·만료</summary><p class="mono">${h(r.review_hash)}</p><p>${h(time(r.expires_at))}</p></details>
      ${r.status==='pending'&&!p.readonly?`<button class="button" data-budget-decision="approve" data-request="${h(r.id)}">예산 승인</button>
      <button class="button ghost" data-budget-decision="reject" data-request="${h(r.id)}">예산 거절</button>`:''}</article>`).join('')}
    ${!p.readonly&&b.consent_state==='valid'?'<button class="button secondary" data-action="budget-run">승인된 예산으로 작업 시작·계속</button><button class="button ghost" data-action="budget-revoke">공급자 동의 철회</button>':''}
    <p class="muted">${h(b.provider_status)} · ${h(b.reason||'')}</p></section>`;
}
function researchErrorText(code,stage,diagnostics) {
  const labels={step_validation:'조사 도구 선택 검증',evidence_validation:'조사 근거 검증',
    model_response:'Gemini 호출·응답',search_response:'Tavily 호출·응답',preflight:'승인·실행 조건 확인'};
  const info=diagnostics?.providers;
  const failure=diagnostics?.failure;
  const categories={decision_invalid:'판단 규칙 위반',policy_blocked:'정책·권한 차단',internal_error:'검증 코드 오류',
    provider_failure:'공급자 오류 응답',provider_response_invalid:'공급자 응답 형식 오류',outcome_uncertain:'결과 미확정'};
  const parts=[code,labels[stage],categories[failure?.category],failure?.rule].filter(Boolean);
  if (info) {
    parts.push(`Gemini 예약 ${info.gemini.reserved}회·완료 ${info.gemini.completed}회, Tavily 예약 ${info.tavily.reserved}회·완료 ${info.tavily.completed}회`);
    if (failure?.response_received) {
      parts.push('Gemini 응답 수신 확인');
      if (Number.isInteger(failure.total_tokens)) parts.push(`기록 ${failure.total_tokens}토큰`);
    }
    else if (failure?.category==='provider_failure') parts.push('공급자의 실패 응답이 기록됐습니다.');
    else if (failure?.category==='outcome_uncertain' || (failure && !failure.category))
      parts.push('실패한 요청의 전송·응답은 기록만으로 확정할 수 없습니다.');
  }
  parts.push(failure?'현재 조사 상태에서 복구 가능 여부를 확인하세요.':'현재 조사 상태와 서버 설정을 확인하세요.');
  return parts.join(' · ');
}
function researchRecoveryPanel(recovery, readonly) {
  if (!recovery) return '';
  const labels={available:'복구 범위를 검토할 수 있습니다. 별도 승인 후 시작할 수 있습니다.',
    active:'복구 범위가 승인됐습니다. 시작을 선택하면 직원의 수정 판단부터 진행합니다.',
    stopped:'복구를 중단했습니다. 추가 호출은 관리자·대표 검토가 필요합니다.',
    blocked:'복구가 차단됐습니다. 관리자·대표 검토가 필요합니다.',
    review:'복구 조사 결과를 관리자가 검토했습니다.',
    expired:'복구 승인 유효 시간이 지났습니다.',revoked:'복구 실행 권한이 철회됐습니다.'};
  const reasons={research_search_disabled:'공급자 무료 전용 설정을 확인하세요.',
    owner_policy_scope_changed:'기존에 승인한 입력 또는 도구 범위가 변경됐습니다.',
    decision_recovery_blocked:'수정할 수 있는 직원 판단을 기존 응답·예약 기록과 연결하지 못했습니다.'};
  const failure=recovery.diagnostics?.failure;
  return `<div class="subpanel"><h3>조사 판단 복구</h3><p>${h(labels[recovery.status])}</p>
    ${recovery.reason?`<p>${h(reasons[recovery.reason] || recovery.reason)}</p>`:''}
    ${recovery.status==='blocked' && recovery.proposal?`<p>추가 제안 한도 · Gemini ${h(recovery.proposal.max_model_calls)}회 · Tavily ${h(recovery.proposal.max_search_credits)}회 · 비용 $0</p>`:''}
    ${recovery.expires_at?`<p>유효 기한 ${h(time(recovery.expires_at))}</p>`:''}
    ${failure?`<p>${h(researchErrorText(failure.code,failure.stage,recovery.diagnostics))}</p>`:''}
    ${!readonly && recovery.status==='available'?'<button class="button secondary" data-action="research-recovery-approve">복구 범위 검토·승인</button>':''}
    ${!readonly && recovery.status==='active'?'<button class="button secondary" data-action="research-recovery-run">승인된 복구 시작</button><button class="button ghost" data-action="research-recovery-revoke">복구 승인 철회</button>':''}
    </div>`;
}
const replanTitles={
  'research-replan-approve':'관리자 재계획 범위 검토·승인', 'research-replan-run':'승인된 관리자 판단 요청',
  'research-replan-revoke':'관리자 재계획 승인 철회', 'research-reinvestigate-approve':'신규 조사 범위 검토·승인',
  'research-reinvestigate-run':'승인된 신규 조사 시작', 'research-reinvestigate-revoke':'신규 조사 승인 철회'
};
function replanBudget(limits) {
  return `관리자 재계획 Gemini 최대 ${h(limits.manager_replan)}회 · 신규 조사 직원 최대 ${h(limits.staff)}회 · 독립 관리자 검토 ${h(limits.independent_review)}회 · 추가 합계 최대 ${h(limits.combined_gemini)}회 · Tavily 기본 검색 최대 ${h(limits.tavily_credits)}회 · 다운로드 0회 · 비용 $0`;
}
function researchReplanPanel(replan, readonly) {
  if (!replan) return '';
  const labels={setup_required:'무료 전용 공급자 설정 확인이 필요합니다.',
    manager_available:'관리자 재계획 승인이 필요합니다. 실제 관리자 판단을 기다리고 있습니다.',
    manager_active:'관리자 재계획 승인 완료 · 판단 요청 대기', manager_expired:'관리자 재계획 승인 만료',
    manager_stopped:'관리자 재계획 중단 · 관리자·대표 검토 필요', manager_decided:'관리자 판단 수신',
    research_available:'관리자가 재조사를 제안했습니다. 신규 조사 승인 대기',
    research_active:'신규 조사 승인 완료 · 실행 대기', research_expired:'신규 조사 승인 만료',
    research_stopped:'신규 조사 중단 · 관리자·대표 검토 필요', review:'신규 조사 독립 관리자 검토 완료',
    blocked:'재계획 차단 · 승인, 원장 연결 또는 현재 범위를 확인하세요.', revoked:'재계획 또는 신규 조사 승인 철회'};
  const actions={manager_available:['research-replan-approve'],
    manager_active:['research-replan-run','research-replan-revoke'],
    research_available:['research-reinvestigate-approve'],
    research_active:['research-reinvestigate-run','research-reinvestigate-revoke']};
  const choices={reinvestigate:'재조사 제안',alternative:'다른 방법 제안',hold:'보류',ask_owner:'대표 질문'};
  const history=replan.failures || [];
  const gemini=history.reduce((n,f)=>n+f.usage.gemini.reserved,0);
  const tavily=history.reduce((n,f)=>n+f.usage.tavily.reserved,0);
  const tokens=history.reduce((n,f)=>n+f.total_tokens,0);
  const failure=replan.diagnostics?.failure;
  return `<div class="subpanel"><h3>실패 업무 재계획</h3><p>${h(labels[replan.status])}</p>
    ${replan.task_id?`<p>새 업무 ${h(replan.task_id)}</p>`:''}
    ${history.length?`<p>기존 누적 예약 · Gemini ${gemini}회 · Tavily ${tavily}회 · 응답 기록 ${tokens.toLocaleString('ko-KR')}토큰</p>
      ${history.map((f,i)=>`<p>${i===0?'첫 조사':'이전 복구'} · ${h(f.code)} · ${h(f.rule || '세부 규칙 미확인')} · ${h(f.total_tokens)}토큰</p>`).join('')}`:''}
    <p>${replanBudget(replan.limits)}</p>
    ${replan.expires_at?`<p>유효 기한 ${h(time(replan.expires_at))}</p>`:''}
    ${replan.decision?`<p><strong>실제 관리자 판단 · ${h(choices[replan.decision.action])}</strong> ${h(replan.decision.reason)}</p>
      <p>다음 행동 · ${h(replan.decision.next_step)}</p><p>성공 기준 · ${h(replan.decision.success_criteria)}</p>`:''}
    ${failure?`<p>${h(researchErrorText(failure.code,failure.stage,replan.diagnostics))}</p>`:''}
    ${readonly?'':(actions[replan.status] || []).map(action=>`<button class="button secondary" data-action="${action}">${replanTitles[action]}</button>`).join('')}
    </div>`;
}

function researchReplanCommand(action, project) {
  const replan=project.research.replan;
  const authorize=action.endsWith('-approve');
  const manager=action==='research-replan-approve';
  const proposal=replan.proposal;
  const fields=authorize?`<p>${replanBudget(replan.limits)}</p>
    <p>${manager?'이 동의는 Gemini 관리자 판단 1회에 적용됩니다. 목표·실패 진단·보존된 관측·도구와 대표 의사를 전송합니다.':
      '이 동의는 새 조사와 독립 관리자 검토에 적용됩니다. 승인된 검색어, 조사 입력과 관측 자료가 범위에 포함됩니다.'}</p>
    <p>승인 후 ${h(proposal.valid_hours)}시간 · 현재 키에 서명 결합 · 공급자 잔량과 청구는 별도 확인</p>
    <details><summary>업무·계약·이력 연결 정보</summary><p>${h(replan.task_id)}</p>
      <pre>${h(JSON.stringify(proposal.binding,null,2))}</pre>
      <p>조사 계약 ${h(proposal.decision_contract)}</p>
      ${manager?'':`<p>첫 요청 해시 ${h(proposal.units[0].payload_sha256)}</p>`}</details>
    <ul>${proposal.tool_options.map(tool=>`<li>${h(tool.name)} · ${h(Object.values(tool.options).join(' / '))}</li>`).join('')}</ul>
    ${manager?`<label>대표 의사 <select name="owner_intent"><option value="review_options">관리자에게 방법 검토 요청</option>
      <option value="prefer_reinvestigation">재조사를 우선 검토해 달라고 요청</option></select></label>`:''}
    <label class="check"><input type="checkbox" name="confirmed" required>전송 범위와 무료 계정, 결제 비활성 및 잔여 한도를 확인했습니다.</label>`:
    '<p>현재 업무의 서명 범위에 적용됩니다.</p>';
  modal(replanTitles[action],fields,replanTitles[action],async data=>{
    const intent=data.get('owner_intent');
    const body=authorize?{confirmed:data.has('confirmed'),review_hash:manager?replan.review_hashes[intent]:replan.review_hash}:{};
    if (manager) body.owner_intent=intent;
    try {
      await api(detailApi(project)+'/'+action,body);
    } catch (error) {
      if (action.endsWith('-run')) await route();
      if (error.research) error.message+=' '+researchErrorText(error.code,error.research.stage,error.research.diagnostics);
      throw error;
    }
    return {message:'재계획 상태를 갱신했습니다.'};
  });
}

const supervisionTitles={
  'research-supervision-approve':'새 보완 업무 범위 검토·승인',
  'research-supervision-run':'승인된 보완 업무 시작',
  'research-supervision-revoke':'보완 업무 승인 철회'
};
function researchSupervisionPanel(state, readonly) {
  if (!state) return '';
  const proposal=state.proposal;
  const limits=proposal?.limits;
  const labels={available:'기존 보류 유지 · 새 보완 업무 승인 대기',setup_required:'무료 공급자 설정 확인 대기',
    active:'새 승인 완료 · 실행 대기',achieved:'관리자가 목표 달성을 확인했습니다. 조사 참고 범위에 적용됩니다.',
    incomplete:'응답 검증 완료 · 실제 업무 목표 미달성',stopped:'보완 업무 중단 · 관리자·대표 검토 필요',
    expired:'보완 승인 만료',revoked:'보완 승인 철회',blocked:'기존 서명, 보류 또는 현재 범위를 확인할 수 없어 차단됐습니다.'};
  const tools={observed:'관측 확보',empty:'호출 결과 0건',failed:'호출 중단',unconfirmed:'수행 결과 미확정',policy_blocked:'접근 정책으로 차단',unavailable:'공식 페이지 접근 불가'};
  const decisions={revise:'보완 지시',hold:'보류',alternative:'대안 제안',ask_owner:'대표 질문',accept:'목표 달성 확인'};
  const checks={met:'충족',unmet:'미충족',unknown:'미확인'};
  const configReasons={gemini_free_execution_disabled:'Gemini 무료 실행 설정 꺼짐',
    independent_production_key_missing:'독립 제작 프로젝트 키 미설정',production_project_key_mismatch:'제작 프로젝트 키 불일치',
    gemini_model_or_endpoint_mismatch:'Gemini 모델·주소 불일치',gemini_key_missing:'Gemini 키 누락',
    tavily_key_missing_or_invalid:'Tavily 키 누락 또는 형식 불일치',tavily_free_only_disabled:'Tavily 무료 전용 설정 꺼짐'};
  const failures={provider_failure:'공급자 실패 응답',outcome_uncertain:'전송·결과 미확정',
    decision_invalid:'판단 규칙 위반',provider_response_invalid:'응답 계약 오류'};
  const actions={available:['research-supervision-approve'],
    active:['research-supervision-run','research-supervision-revoke']};
  return `<div class="subpanel"><h3>목표 기반 보완 업무</h3><p>${h(labels[state.status])}</p>
    ${(state.readiness?.configuration_blockers || []).map(code=>`<p>${h(configReasons[code] || code)}</p>`).join('')}
    ${proposal?`<p>이전 누적 · Gemini 예약 ${h(proposal.historical_usage.gemini)}회 · Tavily 예약 ${h(proposal.historical_usage.tavily)}회</p>
      <p>추가 · 직원 ${h(limits.staff)}회 · 관리자 ${h(limits.manager)}회(최종 독립 검토 1회 포함) · Gemini 합계 ${h(limits.gemini)}회 · Tavily ${h(limits.tavily)}회 · 공식 HTML·robots GET ${h(limits.official_gets || 0)}회 · 보완 최대 ${h(limits.revisions)}회 · 다운로드 0회 · 비용 $0</p>
      ${limits.final_staff_report_reserved?`<p>최종 직원 보고 1회와 독립 검토 1회 확보 · 도구 선택은 판단당 최대 ${h(proposal.max_batch_tools)}개</p>`:''}
      ${proposal.resume_checkpoint?`<p>수집 체크포인트 인수 · 검증된 자료 ${h(proposal.resume_checkpoint.sources)}건 ·
        이전 오류 ${h(proposal.resume_checkpoint.prior_error)} 이후 직원 보고부터 재개 · 새 수집 호출 없음</p>`:''}
      ${proposal.reused_search_leads?`<p>재사용 검색 단서 ${h(proposal.reused_search_leads)}건 · 공식 원문과 구분</p>`:''}
      ${(proposal.preserved_sources || []).map(source=>`<p>보존 자료 · ${h(source.tool)} · 사용 가능 ${h(source.preserved)}건 · 기간 경과 ${h(source.stale)}건 · 제외 ${h(source.excluded)}건</p>`).join('')}
      ${!proposal.direct_page_available?`<p>직접 확인한 공식 페이지 도구가 현재 목록에 없습니다. 공개 검색은 단서를 수집할 수 있습니다.</p>`:''}`:''}
    ${state.assignment?`<p>관리자 수행 목표 · ${h(state.assignment.manager_direction)}</p><p>성공 기준 · ${h(state.assignment.manager_success_criteria)}</p>`:''}
    ${state.remaining?`<p>잔여 승인 횟수 · 직원 ${h(state.remaining.staff)}회 · 관리자 ${h(state.remaining.manager)}회 · Tavily ${h(state.remaining.tavily)}회 · 공식 GET ${h(state.remaining.official_gets || 0)}회</p>`:''}
    ${state.expires_at?`<p>유효 기한 ${h(time(state.expires_at))}</p>`:''}
    ${state.failure?`<p>${h(failures[state.failure] || state.failure)}${state.failure_rule?' · '+h(state.failure_rule):''}
      ${state.provider_response?` · HTTP ${h(state.provider_response.http_status)} ${h(state.provider_response.status || '')}
         ${state.provider_response.response_schema_rejected?' · 응답 스키마 거절':''}`:''}</p>`:''}
    <p>도구 수행 · 근거 ${h(state.evidence_count || 0)}건</p>
    ${(state.choices || []).map(item=>`<p>${h(item.tool)} · ${h(item.option)} · ${h(tools[item.state])}</p>
      ${(item.requests || []).map(request=>`<p>${h(request.kind==='robots'?'robots 확인':'공식 페이지 조회')} · HTTP ${h(request.http_status)} · ${sourceLink(request.url)}</p>`).join('')}`).join('')}
    ${(proposal?.tool_options || []).filter(tool=>!(state.choices || []).some(item=>item.tool===tool.name))
         .map(tool=>`<p>${h(tool.name)} · ${state.status==='active'?'대기':'미사용'}</p>`).join('')}
    ${state.decision_shape?`<p>응답 단계 ${h(state.decision_shape.phase)} · 행동 ${h(state.decision_shape.action)}
      · 누락 필드 ${h(state.decision_shape.missing.join(', ') || '없음')} · 허용 도구 ${h(state.decision_shape.eligible_tools)}개
      · 근거 ${h(state.decision_shape.evidence_count)}건</p>`:''}
    ${(state.reports || []).map(item=>`<p>직원 보고 검증 완료 · ${h(item.report.feasibility)}</p>
      ${item.collection_direction?.action==='hold'?`<p>수집 보류 · ${h(item.collection_direction.reason)}</p>`:''}
      ${item.unavailable.map(reason=>`<p>${h(reason.tool)} · ${h(reason.reason)}</p>`).join('')}`).join('')}
    ${(state.reviews || []).map(review=>`<p>관리자 ${h(decisions[review.action])} · ${h(review.rationale)}</p>
      <p>${h(review.feedback)} · 확인 기준 ${h(review.confirmation)}</p>
      ${review.checks.map(check=>`<p>${h(check.criterion_id)} · ${h(checks[check.status])} · ${h(check.evidence)}</p>`).join('')}`).join('')}
    ${state.outcome?.next_proposal?`<p>추가 작업은 대표 승인 필요 · ${h(state.outcome.next_proposal.feedback)}</p>`:''}
    ${readonly?'':(actions[state.status] || []).map(name=>`<button class="button secondary" data-action="${name}">${supervisionTitles[name]}</button>`).join('')}
  </div>`;
}

function researchSupervisionCommand(action, project) {
  const state=project.research.supervision;
  const approve=action.endsWith('-approve');
  const proposal=state.proposal;
  const fields=approve?`<p>무료 Gemini 최대 ${h(proposal.limits.gemini)}회 · Tavily 기본 검색 최대 ${h(proposal.limits.tavily)}회 · 공식 HTML·robots GET 최대 ${h(proposal.limits.official_gets)}회 · 비용 $0</p>
    <p>Gemini 프로젝트 ${h(proposal.gemini_project)} · 모델 ${h(proposal.gemini_model)} · Tavily ${h(proposal.tavily_account)}</p>
    <p>이전 보류, 업무 목표, 확인 기준, 보존 관측, 실행 기록 및 보완 지시를 Gemini에 보냅니다. Tavily에는 승인된 공개 검색어만 보냅니다.</p>
    <p>승인 후 ${h(proposal.valid_hours)}시간 · 현재 공급자 키에 서명 결합 · 실제 잔량과 청구는 별도 확인</p>
    <p>승인 대상 공식 경로</p><ul>${proposal.official_get_urls.map(url=>`<li>${h(url)}</li>`).join('')}</ul>
    <ul>${proposal.tool_options.map(tool=>`<li>${h(tool.name)} · ${h(Object.values(tool.options).join(' / '))}</li>`).join('')}</ul>
    <details><summary>계약·이력 및 첫 요청 해시</summary><pre>${h(JSON.stringify({binding:proposal.binding,
      contract:proposal.contract, research_contract:proposal.research_contract, first:proposal.units[0].payload_sha256},null,2))}</pre></details>
    <label class="check"><input type="checkbox" name="confirmed" required>무료 계정과 결제·종량제 비활성 설정 및 전송 범위를 확인했습니다. 실시간 잔량과 실제 청구는 미확인입니다.</label>`:
    '<p id="supervision-progress" role="status">현재 서명 범위에 적용됩니다.</p>';
  modal(supervisionTitles[action],fields,supervisionTitles[action],async data=>{
    const progress=dialog.querySelector('#supervision-progress');
    if (progress && action.endsWith('-run')) progress.textContent='직원 업무 및 독립 관리자 검토 실행 중';
    try {
      await api(detailApi(project)+'/'+action,approve?{confirmed:data.has('confirmed'),review_hash:state.review_hash}:{});
    } catch (error) {
      if (action.endsWith('-run')) await route();
      throw error;
    }
    return {message:'보완 업무 상태를 갱신했습니다.'};
  });
}

function researchPanel(p) {
  const r=p.research;
  if (!r) return '';
  const actions={available:['research-approve','조사 범위 검토·승인'],active:['research-run','웹·전문 자료 조사 실행']};
  const action=actions[r.status];
  const labels={setup_required:'무료 Tavily Researcher 계정과 서버 설정이 필요합니다.',
    available:'업무에 필요한 검색 또는 보존된 전문 자료를 직원이 선택합니다.',active:'승인한 범위 내에서 조사와 관리자 검토를 진행합니다.',
    review:'관리자가 조사 결과와 미확인 항목을 검토했습니다.',revoked:'조사 승인이 철회됐습니다.',
    expired:'조사 승인 유효 시간이 지났습니다.',contract_changed:'조사 계약이 바뀌었습니다. 기존 승인으로 실행할 수 없습니다.',stopped:'실패 또는 미확정 요청에서 조사를 중단했습니다.'};
  return `<section class="panel" id="cross-research"><h2>웹·전문 자료 교차 조사</h2><p>${h(labels[r.status])}</p>
    ${r.diagnostics?.failure?`<p>${h(researchErrorText(r.diagnostics.failure.code,r.diagnostics.failure.stage,r.diagnostics))}</p>`:''}
    ${action?`<button class="button secondary" data-action="${action[0]}">${action[1]}</button>`:''}
    ${r.status==='active'?'<button class="button ghost" data-action="research-revoke">조사 범위 철회</button>':''}
    ${researchRecoveryPanel(r.recovery,p.readonly)}
    ${researchReplanPanel(r.replan,p.readonly)}
    ${researchSupervisionPanel(r.supervision,p.readonly)}
    ${r.review?`<p><strong>관리자 ${r.review.decision.action==='hold'?'보류':'제한적 활용 의견'}</strong> ${h(r.review.decision.note)}</p>`:''}
    ${r.result?`<p><strong>제작 가능성</strong> ${h(r.result.feasibility)}</p>
      ${r.result.claims.map(c=>`<p><strong>직원 해석 · ${h(({supported:'근거 일치',conflicting:'근거 상충',unverified:'미확인'})[c.assessment])}</strong> ${h(c.statement)}</p>
        ${c.citations.map(ref=>`<blockquote><strong>관측 발췌</strong> · ${h(ref.source)} · “${h(ref.quote)}”</blockquote>`).join('')}`).join('')}
      `:''}
    ${r.observations?.length?`<details><summary>실제 관측과 출처</summary>${r.observations.map(o=>`<p>${h(o.tool)} · ${h(o.at)} · ${o.status==='empty'?'결과 없음':o.status==='preserved'?'보존 자료 · 이번 업무 조회 없음':''}</p>
        ${o.sources.map(ref=>`<p>${h(ref.id)} · ${h(({search_lead:'검색 단서',public_page:'직접 확인한 페이지',api_metric:'API 관측',media_metadata:'미디어 메타데이터'})[ref.scope] || ref.scope)}
          · ${h(ref.origin || '원출처 미확인')} · ${h(ref.title)} · ${h(ref.excerpt)} · ${sourceLink(ref.url)}</p>`).join('')}`).join('')}</details>`:''}
    </section>`;
}
function researchCommand(action) {
  const p=detail, r=p.research;
  if (Object.hasOwn(supervisionTitles,action)) return researchSupervisionCommand(action,p);
  if (Object.hasOwn(replanTitles,action)) return researchReplanCommand(action,p);
  const titles={'research-approve':'조사 범위 검토·승인','research-run':'웹·전문 자료 조사 실행','research-revoke':'조사 범위 철회',
    'research-recovery-approve':'복구 범위 검토·승인','research-recovery-run':'승인된 복구 시작',
    'research-recovery-revoke':'복구 승인 철회'};
  const recovery=action.startsWith('research-recovery-');
  const approve=action.endsWith('-approve');
  const offer=recovery?r.recovery:r;
  const proposal=offer.proposal;
  const feedback=proposal?.feedback;
  const fields=approve?`<p>Tavily 기본 검색 최대 ${h(proposal.max_search_credits)}회 · 무료 Gemini 최대 ${h(proposal.max_model_calls)}회 · 다운로드 0회 · 비용 $0</p>
    ${recovery?`<p>기존 Gemini 예약 ${h(proposal.source_usage.gemini.reserved)}회 · Tavily 예약 ${h(proposal.source_usage.tavily.reserved)}회</p>
      <p>추가 범위 중 수정 판단 최대 ${h(proposal.max_corrections)}회 · 독립 관리자 검토 ${h(proposal.manager_review_calls)}회 · 승인 후 ${h(proposal.valid_hours)}시간 · 현재 공급자 키에 서명 결합</p>
      <p>단계 ${h(feedback.step)} · 규칙 ${h(feedback.rule)} · 계약 ${h(proposal.decision_contract)}</p>
      <details><summary>기존 시도와 새 입력의 검토 정보</summary><pre>${h(JSON.stringify({
        original_attempt:feedback.original_attempt, original_reservation_sha256:feedback.original_reservation_sha256,
        source_policy_sha256:proposal.binding.source_policy_sha256, correction_payload_sha256:proposal.units[0].payload_sha256,
        review_hash:offer.review_hash
      },null,2))}</pre></details>`:''}
    <ul>${proposal.tool_options.map(t=>`<li>${h(t.name)} · ${h(Object.values(t.options).join(' / '))}</li>`).join('')}</ul>
    <p>Tavily에 선택한 공개 검색어만, Google에 업무 범위·출처 발췌·조사 결과${recovery?'·규칙 코드와 이전 시도 참조':''}를 보냅니다.</p>
    <label class="check"><input type="checkbox" name="confirmed" required>Tavily Researcher 및 결제·종량제 비활성, Google 무료 프로젝트와 잔여 한도 및 두 제공처의 데이터 처리를 확인했습니다.</label>`:
    action==='research-recovery-run'?'<p id="research-recovery-progress" role="status">승인한 범위에서 실행합니다.</p>':
      '<p>현재 서명 범위에 적용됩니다.</p>';
  modal(titles[action],fields,titles[action],async data=>{
    const body=approve?{review_hash:offer.review_hash,confirmed:data.has('confirmed')}:{};
    const progress=dialog.querySelector('#research-recovery-progress');
    if (progress) progress.textContent='복구를 시작했습니다. 수정 판단과 후속 조사 상태를 확인 중입니다.';
    try {
      await api(detailApi(p)+'/'+action,body);
    } catch (error) {
      if (progress) progress.textContent='현재 요청이 중단됐습니다.';
      if (action.endsWith('-run')) await route();
      if (error.research) error.message+=' '+researchErrorText(error.code,error.research.stage,error.research.diagnostics);
      throw error;
    }
    return {message:'조사 상태를 갱신했습니다.'};
  });
}
function projectPage(p, chosen={}) {
  const f=p.flow;
  const plan=f.plan_versions.find(item=>item.version===chosen.plan) || f.plan_versions.at(-1);
  const video=f.video_versions.find(item=>item.version===chosen.video) || f.video_versions.at(-1);
  const s=statuses[p.stage];
  const stepIndex = p.stage==='research_planning' && !p.jobs.at(-1)?.assignments.length ? 0 : s[3];
  const prior=f.plan_versions.find(item=>item.version===plan?.version-1);
  return `<a class="back" href="#dashboard">${icon('back')} 대시보드</a>
  <section class="detail-title"><div class="inline">${stateBadge(p.stage)} ${plan?.provenance==='provider_model_claim' ? badge('실제 AI 결과','check','green') :
      plan?.provenance==='offline_http_fixture' ? badge('오프라인 HTTP 검증','alert','amber') :
      badge(p.mission?.attempts.length?'모델 작업 결과 확인 중':'실제 모델 미실행','alert','amber')}</div>
  <h1>${h(p.goal)}</h1><p class="muted">${h(s[1])} · ${h(time(p.updated_at))}</p></section>
  <section class="panel next-work" id="next-work" aria-labelledby="next-heading"></section>
  <nav class="stepper" aria-label="업무 단계">${steps.map(([label,symbol],i)=>`<div class="step ${i===stepIndex?'current':i<stepIndex?'done':''}" ${i===stepIndex?'aria-current="step"':''}>${icon(i<stepIndex?'check':symbol)}${label}</div>`).join('')}</nav>
  <div class="detail-grid"><div class="stack">${budgetSetupPanel(p)}${budgetPanel(p)}${researchPanel(p)}${productionPanel(p)}${videoPanel(p,video)}${planPanel(p,plan,prior)}</div>
  <aside class="stack"><section class="panel" id="work-detail"><h2>${icon('user')} 현재 업무</h2>${facts([['담당',s[1]],['대상',p.audience],['언어',f.constraints.language||'미정'],['플랫폼',f.constraints.platform||'미정'],['길이',f.constraints.duration_seconds?f.constraints.duration_seconds+'초':'미정'],['제약',f.constraints.notes||'미정']])}
  ${operations(p)}${p.stage!=='plan_revision'?reworkPanel(p):''}${p.rework&&p.mission?`<details class="subpanel"><summary>이전 미션 기획 보존 · 참고용 (최신 재작업 아님)</summary><p>아래 내부 수락은 이전 버전의 기록입니다. 최신 진행 상황은 위 AI 재작업 현황을 확인하세요.</p>${missionStatus(p.mission)}</details>`:missionStatus(p.mission)}${p.jobs.at(-1)?.assignments.length ? `<div class="subpanel"><h3>직원 인수 상태</h3>${p.jobs.at(-1).assignments.map(t=>`<p class="muted">${icon(t.role==='writer'?'script':t.role==='qa'?'shield':'film')} ${h(eventRoles[t.role] || t.role)} · ${t.state==='accepted_by_ai_manager'?'내부 검토 수락':'작업 또는 검토 대기'} · v${t.versions}</p>`).join('')}</div>` : ''}</section>
  <section class="panel"><h2>${icon('revision')} 대표 결정 이력</h2><ol class="timeline">${[...f.decisions].reverse().map(d=>`<li><strong>${d.stage==='plan'?'기획':'영상'} v${d.version} · ${d.action==='approve'?'승인':'수정 요청'}</strong><p class="muted">${h(time(d.at))}${d.changes_plan?' · 기획 재승인 필요':''}</p><p>${h(d.feedback)}</p></li>`).join('') || '<li>등록된 대표 결정이 없습니다.</li>'}</ol></section>
  <section class="panel"><h2>${icon('clock')} 진행 타임라인</h2><ol class="timeline">${[...f.events].reverse().map(e=>`<li><strong>${h(statuses[e.stage]?.[0] || e.stage)}</strong><p class="muted">${h(time(e.at))}</p></li>`).join('')}</ol></section></aside></div>`;
}
let selectedVersions = {};
const actionButton = (action,label,reason='',scene='') =>
  `<button class="button" data-action="${action}" data-scene="${h(scene)}"${reason?' disabled aria-describedby="next-reason"':''}>${h(label)}</button>`;
const expired = at => Boolean(at && Date.parse(at)<=Date.now());

function productionNext(a,selected) {
  const keyReasons={
    missing_runtime_key:'서버에 GEMINI_API_KEY가 설정되어 있지 않습니다.',
    missing_comparison_key:'서버에 GEMINI_PRODUCTION_PROJECT_API_KEY가 없습니다. 기존 무료 프로젝트의 키를 대조용으로 설정하세요.',
    mismatch:'서버의 GEMINI_API_KEY와 GEMINI_PRODUCTION_PROJECT_API_KEY가 일치하지 않습니다.'
  };
  const key = a.key_ready ? '' : (keyReasons[a.key_setup] ||
    '서버에서 GEMINI_API_KEY와 GEMINI_PRODUCTION_PROJECT_API_KEY가 일치해야 합니다.')+' 키 값은 컷룸에 입력하지 마세요.';
  const choose=(action,label,message,reason='',scene='')=>({message,reason,scene,buttons:actionButton(action,label,reason,scene)});
  const refresh=actionButton('refresh','상태 새로고침');
  if (a.status==='stopped') return {message:a.manager_attempt==='reserved'?
    '관리자 요청 실행 중 또는 결과 미확정 · 중복 실행 차단':
    '관리자 요청 실패 또는 결과 미확정 · 자동 재시도 없음',buttons:refresh};
  if (a.status==='approved') {
    const reason=key || (expired(a.expires_at)?'서명 동의가 만료되었습니다.':!a.manager_enabled?'서버의 Gemini 무료 실행 플래그와 고정 모델·엔드포인트 설정을 확인하세요.':'');
    return choose('production-plan-run','관리자 제작 계획 실행','동의 범위는 서명된 관리자 Gemini 텍스트 요청 최대 1회입니다.',reason);
  }
  if (a.status==='prepared' && a.review_hash && !expired(a.expires_at)) {
    return choose('production-plan-consent','제작 계획 외부 전송 동의','전송 범위와 Google 무료 서비스 정책을 검토합니다. 실행은 별도입니다.',key);
  }
  if (!a.plan) return choose('production-plan-prepare','관리자 제작 계획 준비',
    '승인 대본을 유지합니다. 소유자가 무료 조건, 잔여 쿼터, 현행 문서를 확인합니다. 준비 단계의 외부 호출은 0회입니다.',key);
  const operating=a.owner_policy, assets=a.asset_execution;
  if (a.render_ready && !assets?.expires_at && !operating?.expires_at) return choose('production-render','인수한 클립과 음성으로 제작','로컬 합성 후 대표 영상 검토로 제출합니다. 외부 호출은 0회입니다.');
  if (a.render_attempt) return {message:({
    reserved:'로컬 합성 실행 중 또는 결과 미확정 · 중복 실행 차단',
    completed:'합성 기록 완료 · 대표 영상 검토 제출 상태 확인',
    failed:'로컬 합성 실패 · 자동 재실행 없음'
  })[a.render_attempt]||'로컬 합성 결과 미확정 · 중복 실행 차단',buttons:refresh};
  const clips=[], voices=[];
  for (const scene of a.plan.scenes) {
    if (scene.source==='operator_clip' && !a.clips.includes(scene.scene_id)) {
      clips.push(choose('production-clip-import','로컬 클립 인수',`${scene.scene_id} · 인수 폴더에 권리를 확인한 MP4가 있을 때 진행하세요.`,'',scene.scene_id));
    }
    if (a.plan.voice.tool!=='gemini_scene') continue;
    const voice=a.voices[scene.scene_id];
    if (voice?.attempted || a.voice_batch?.review?.requests?.some(item=>item.scene_id===scene.scene_id)) continue;
    if (!voice) voices.push(choose('production-voice-prepare','장면 음성 준비',`${scene.scene_id} · 승인 원문과 관리자 발화 지시로 요청을 준비합니다.`,key,scene.scene_id));
    else if (!voice.review_hash || expired(voice.expires_at)) voices.push(choose('production-voice-consent','장면 음성 동의',
      `${scene.scene_id} · 장면별 별도 승인`,'유효한 서명 제안이 필요합니다. 현재 요청은 실행할 수 없습니다.',scene.scene_id));
    else if (!voice.consent) voices.push(choose('production-voice-consent','장면 음성 동의',
      `${scene.scene_id} · 이 장면의 요청 내용과 전송 조건만 승인합니다.`,key,scene.scene_id));
    else voices.push(choose('production-voice-run','장면 음성 실행',
      `${scene.scene_id} · 동의한 음성 요청 1회입니다.`,key || (!a.tts_enabled?'Gemini 장면 음성 실행에 GEMINI_PRODUCTION_TTS_ENABLED=1 설정이 필요합니다.':''),scene.scene_id));
  }
  const sources=a.source_assessment;
  let sourceWork;
  if (sources?.status==='unprepared' || (sources?.status==='prepared' && (!sources.review_hash || expired(sources.expires_at)))) {
    sourceWork=choose('production-source-prepare','자산 확보 업무 준비',`등록 자산 ${sources.available_count}개 · 기존 계획을 보존하고 자산 후보와 권리 확인 절차를 검토합니다.`,key);
  } else if (sources?.status==='prepared') {
    sourceWork=choose('production-source-consent','자산 확보 업무 외부 전송 동의','기존 계획·장면과 등록 자료 요약을 Gemini에 보낼 범위를 검토합니다.',key);
  } else if (sources?.status==='approved') {
    sourceWork=choose('production-source-run','자산 확보 직원 실행','별도 서명한 Gemini 텍스트 요청 최대 1회입니다.',
      key || (expired(sources.expires_at)?'자산 확보 업무 동의가 만료되었습니다.':!a.manager_enabled?'Gemini 무료 실행 설정을 확인하세요.':''));
  } else if (sources?.ready?.length) {
    sourceWork=choose('production-source-import','선택된 로컬 자산 인수',`${sources.ready[0]} · 권리 기록과 파일 해시를 확인합니다. 외부 요청 0회.`,'',sources.ready[0]);
  } else if (sources?.status==='completed') {
    sourceWork={message:'자산 확보 업무 완료 · 상세의 확보 방법과 권리 확인 조건을 검토하세요.'};
  } else if (sources?.status==='stopped' || sources?.status==='blocked') {
    sourceWork={message:sources.reason || '자산 확보 요청이 실패했거나 결과가 미확정입니다. 자동 재시도는 없습니다.',buttons:refresh};
  }
  const batch=a.voice_batch, timing=a.timeline;
  let batchWork, timelineWork;
  if (batch?.status==='prepared') batchWork=choose('production-batch-consent','남은 장면 음성 일괄 동의',
    '장면별 정확한 요청의 묶음을 한 번 검토합니다.',key || (expired(batch.review.expires_at)?'일괄 검토 유효 시간이 지났습니다.':''));
  if (batch?.status==='approved') batchWork=choose('production-batch-run','남은 장면 음성 일괄 실행',
    `승인된 최대 ${batch.review.max_requests}회 · 실패 또는 미확정 시 중단`,key ||
      (expired(batch.review.expires_at)?'일괄 동의가 만료되었습니다.':!a.tts_enabled?'Gemini 장면 음성 실행 설정이 필요합니다.':''));
  if (batch?.status==='stopped') batchWork={message:'일괄 음성 작업이 중단됐거나 결과가 미확정입니다. 자동 재시도는 없습니다.',buttons:refresh};
  if (timing?.status==='unprepared') timelineWork=choose('production-timeline-prepare','실측 시간 조정안 준비','실측 발화와 기존 승인 길이, 소스 길이와 자막 노출 조건을 묶어 보완 판단을 준비합니다.',key);
  if (timing?.status==='prepared') timelineWork=choose('production-timeline-consent','시간 조정안 전송 동의','Gemini 텍스트 1회에 보낼 대본·실측 자료를 확인합니다.',key);
  if (timing?.status==='authorized') timelineWork=choose('production-timeline-run','관리자 시간 조정 판단 실행','서명한 텍스트 요청 1회 · 음성 재합성 없음',key ||
      (expired(timing.expires_at)?'전송 동의가 만료되었습니다.':!a.manager_enabled?'Gemini 무료 실행 설정이 필요합니다.':''));
  if (timing?.status==='review') timelineWork=choose('production-timeline-approve','대표 시간 조정안 검토·승인','시간 조정만 별도 승인합니다. 기존 대본과 관리자 계획은 유지됩니다.');
  if (timing?.status==='hold' || timing?.status==='stopped') timelineWork={message:'시간 조정 관리자가 보류했거나 요청 결과가 미확정입니다. 상세에서 결과를 확인하세요.',buttons:refresh};
  const operatingWork=operating?.status==='available'
    ?choose('production-policy-approve','개인 운영 정책 검토·승인',
      `이 제작의 범위를 한 번 검토합니다. 무료 전용 · 외부 요청 최대 ${operating.proposal.units.length}회`,key)
    :operating?.status==='active'
      ?choose('production-policy-run','제작 실행','승인한 범위에서 가능한 단계까지 진행합니다.',
        operating.run_blocker==='tts_execution_disabled'?'서버의 장면 TTS 실행 설정이 필요합니다.':
        operating.run_blocker?'서버의 무료 Gemini 실행 설정이 필요합니다.':
        !operating.can_run?'시간 조정안 승인 또는 권리가 확인된 영상 자산을 기다립니다.':'')
      :operating?.expires_at?{message:'운영 정책이 만료·철회·중단됐거나 키를 확인할 수 없습니다. 제작 상세에서 상태를 확인하세요.'}:null;
  const discovery=visualDiscovery(a);
  let discoverWork;
  if (discovery?.status==='available') discoverWork=choose('production-discovery-approve',
    discovery===a.adaptive_discovery?'대안 영상·이미지 탐색 범위 검토·승인':'영상 자동 탐색 범위 검토·승인',
    `Commons 검색·메타데이터 최대 ${discovery.proposal.max_searches}회 · 기존 판단 재사용 · 추가 대안 판단 상한 ${discovery.proposal.fallback_max_calls}회`,key);
  if (discovery?.status==='active') discoverWork=choose('production-discovery-run','영상 자동 탐색 실행',
    '승인한 검색어로 영상·이미지 후보와 권리 메타데이터를 확인합니다.',key);
  if (discovery?.status==='review') discoverWork=choose('production-discovery-rights','영상 후보 권리 검토',
    '장면 적합성, 창작자·출처·편집 허용과 표시 의무를 확인한 후보만 선택하세요.');
  if (discovery?.status==='empty') discoverWork={message:'권리 검토 가능한 영상 후보가 없습니다. 상세의 대안과 추가 권리 조건을 확인하세요.'};
  if (['stopped','expired','revoked'].includes(discovery?.status)) discoverWork={message:'영상 탐색이 중단·만료 또는 철회됐습니다. 자동 재시도하지 않습니다.',buttons:refresh};
  const diagnostic=a.commons_diagnostic;
  let diagnosticWork;
  if (diagnostic?.status==='available') diagnosticWork=choose('production-diagnostic-approve','Commons 제외 원인 진단 검토·승인',
    '기존 원본 응답이 남아 있지 않습니다. 확인이 필요하면 같은 검색어·유형을 독립 진단 범위로 한 번 조회할 수 있습니다.',key);
  if (diagnostic?.status==='active') diagnosticWork=choose('production-diagnostic-run','Commons 제외 원인 진단 실행',
    '동일 API GET 최대 1회 · 다운로드·Gemini 0회',key);
  if (diagnostic?.status==='review') diagnosticWork=choose('production-diagnostic-rights','진단 후보 권리 검토',
    '기술 검증을 통과한 후보 중 권리 및 장면 적합성을 확인한 항목을 선택하세요.');
  if (['empty','reviewed','revoked','stopped','expired'].includes(diagnostic?.status)) diagnosticWork={
    message:diagnostic.status==='empty'?'진단에서 권리 검토 후보를 확보하지 못했습니다. 관련 상세 보기에서 제외 사유를 확인하세요.':
      '진단 범위가 종료되었습니다. 기존 검색 기록과 별도의 진단 결과를 관련 상세 보기에서 확인하세요.'};
  const relevance=a.commons_relevance;
  let relevanceWork;
  if (relevance?.status==='available') relevanceWork=choose('production-relevance-approve','관련 영상·이미지 복구 검토·승인',
    '기존 진단 후보와 새 검색 후보를 장면별로 검토합니다. 영상 다운로드는 포함되지 않습니다.',key||
       (!a.manager_enabled?'서버의 무료 Gemini 실행 설정이 필요합니다.':''));
  if (relevance?.status==='active') relevanceWork=choose('production-relevance-run','관련 자료 검색·적합성 검토 실행',
    '승인한 검색 범위와 후보 메타데이터 판단을 한 번 실행합니다.',key||
       (!a.manager_enabled?'서버의 무료 Gemini 실행 설정이 필요합니다.':''));
  if (relevance?.status==='review') relevanceWork=choose('production-relevance-rights','적합 후보 권리·장면 검토',
    '실제 원본에서 장면 적합성·다운로드 및 편집 권리를 확인한 후보를 선택하세요.');
  if (['empty','reviewed','stopped','revoked','expired'].includes(relevance?.status))
    relevanceWork={message:'적합한 Commons 자료가 부족하거나 범위가 종료됐습니다. 공식 직접 자료의 허가 또는 권리가 확인된 자체 캡처가 필요합니다. 무료 생성 실행기는 미연결입니다.'};
  const publisher=a.publisher_discovery;
  let publisherWork;
  if (publisher?.status==='available') publisherWork=choose('production-publisher-approve','공식 제작사 자료 탐색 검토·승인',
    '공식 페이지와 개별 자료의 메타데이터를 확인합니다.',key||(!a.manager_enabled?'서버의 무료 Gemini 실행 설정이 필요합니다.':''));
  if (publisher?.status==='active') publisherWork=choose('production-publisher-run','공식 제작사 자료 탐색 실행',
    '승인한 URL에서만 접근 정책과 후보를 확인합니다.',key||(!a.manager_enabled?'서버의 무료 Gemini 실행 설정이 필요합니다.':''));
  if (publisher?.status==='review') publisherWork=choose('production-publisher-rights','공식 자료 로컬 편집 권리 검토',
    '공식 문구가 선택한 각 파일의 무료 다운로드와 로컬 편집을 허용하는지 확인하세요.');
  if (['rights_wait','reviewed','empty','stopped','expired','revoked'].includes(publisher?.status))
    publisherWork={message:publisher.status==='reviewed'?'검토한 자료가 자산·편집 범위에 반영됐습니다. 모든 장면에 사용 가능한 자료가 있어야 제작할 수 있습니다.':
      publisher.status==='rights_wait'?'후보가 있으나 로컬 편집 허가 문서를 확인하지 못했습니다.':
        '이 탐색 범위가 종료됐습니다. 제작 상세에서 접근 차단과 후보 결과를 확인하세요.'};
  let assetWork;
  if (assets?.status==='available') assetWork=choose('production-assets-approve','자산·편집 범위 검토·승인',
    `편집 판단 최대 1회 · 공식 영상·이미지 다운로드 최대 ${assets.proposal.max_downloads}회 · 비용 $0`,key);
  if (assets?.status==='active') assetWork=choose('production-policy-run','제작 실행',
    '등록 권리 범위에서 AI 편집·직접 인수·로컬 합성을 진행합니다.');
  if (assets?.status==='waiting_rights') assetWork=choose('production-assets-approve','자산·편집 범위 검토·승인',
    `미인수 장면 ${assets.missing}개 · 등록 로컬 ${assets.local}개 · 허용 공식 영상 ${assets.official}개`,
    '등록된 소스가 부족합니다. 제작 상세의 장면 요구와 공식 직접 다운로드·로컬 편집 허가 조건을 확인하세요.');
  if (assets?.status==='registry_blocked') assetWork=choose('production-assets-approve','자산·편집 범위 검토·승인',
    '등록 소스 검증이 필요합니다.','공식 제공처, 권리 증빙 또는 로컬 목록을 확인하세요.');
  if (['hold','stopped','expired','revoked'].includes(assets?.status)) assetWork={
    message:assets.status==='hold'?'편집 직원이 확보·편집 가능한 소스 부족으로 보류했습니다.':
      '자산 확보 범위가 중단·만료 또는 철회됐습니다. 기존 결과를 보존하고 후속 호출을 차단합니다.',buttons:refresh};
  const legacy=!operating?.expires_at && operating?.status!=='available';
  const options=[
    ...(publisherWork?[{...publisherWork,choice:'publisher',label:'공식 제작사 자료'}]:[]),
    ...(relevanceWork?[{...relevanceWork,choice:'commons-relevance',label:'장면 적합성 복구'}]:[]),
    ...(diagnosticWork?[{...diagnosticWork,choice:'commons-diagnostic',label:'Commons 제외 원인 진단'}]:[]),
    ...(discoverWork?[{...discoverWork,choice:'discovery',label:'Commons 영상 자동 탐색'}]:[]),
    ...(assetWork?[{...assetWork,choice:'assets',label:'영상 자산 확보·편집'}]:[]),
    ...(operatingWork && !assets?.expires_at?[{...operatingWork,choice:'operating',label:'개인 운영 정책 · 제작 실행'}]:[]),
    ...(legacy && batchWork?[{...batchWork,choice:'batch',label:'남은 장면 음성 일괄'}]:[]),
    ...(timelineWork && (legacy || ['review','hold','stopped'].includes(timing?.status))?[{...timelineWork,choice:'timeline',label:'실측 시간 조정'}]:[]),
    ...(legacy?voices:[]).map(voice=>({...voice,choice:`voice-${voice.scene}`,label:`장면 음성 · ${voice.scene}`})),
    ...(sourceWork && (legacy || ['completed','blocked','stopped'].includes(sources?.status))?[{...sourceWork,choice:'sources',label:'자산 확보 업무'}]:[]),
    ...Object.entries(a.voices).filter(([,voice])=>voice.audio_sha256 && !voice.listening)
      .map(([scene])=>({...choose('production-listen','청취 의견 저장',`${scene} 음성에 대한 대표 의견을 기록합니다.`,'',scene),
        choice:`listen-${scene}`,label:`청취 의견 · ${scene}`})),
    ...(!assets?.expires_at?clips:[]).map(clip=>({...clip,choice:`clip-${clip.scene}`,label:`로컬 클립 인수 · ${clip.scene}`}))
  ];
  if (options.length) {
    const assetDefault=assetWork && operating?.used>=operating?.proposal?.units.length;
    const discoveryDefault=discoverWork && (assets?.status==='waiting_rights' || discovery?.status==='review');
    const diagnosticDefault=diagnosticWork && ['available','active','review','empty','stopped'].includes(diagnostic?.status)
      && assets?.status==='waiting_rights';
    const relevanceDefault=relevanceWork && (relevance?.status==='review' || assets?.status==='waiting_rights');
    const defaultWork=(assets?.status==='waiting_rights' && options.find(item=>item.choice==='publisher' && item.buttons)) ||
      (assets?.status==='waiting_rights' && publisherWork && options.find(item=>item.choice==='publisher')) ||
      (relevanceDefault && options.find(item=>item.choice==='commons-relevance')) ||
      (diagnosticDefault && options.find(item=>item.choice==='commons-diagnostic')) ||
      (discoveryDefault && options.find(item=>item.choice==='discovery')) ||
      (assetDefault && options.find(item=>item.choice==='assets')) || options.find(item=>item.buttons && !item.reason) || options[0];
    return {...(options.find(item=>item.choice===selected)||defaultWork),options};
  }
  const blockers={pending_external_clip:'사용권을 확인한 장면 클립이 필요합니다.',
    production_voice_unavailable:'선택된 음성 도구를 로컬에서 사용할 수 없습니다. 관리자 계획의 음성 조건을 확인하세요.',
    production_voice_receipt_changed:'장면 음성의 검증 기록과 파일이 일치해야 합니다.',
    narration_exceeds_scene:'보존한 음성이 승인 장면 길이를 초과했습니다. 장면 길이 또는 대본을 바꾸려면 별도 대표 승인이 필요합니다.'};
  return choose('production-render','인수한 클립과 음성으로 제작',
    '장면별 소스, 음성 및 타이밍 검증이 필요합니다. 아래 제작 계획과 장면 원장을 확인하세요.',
    blockers[a.render_blocker] || (a.render_blocker ? `제작 검증 대기 · ${a.render_blocker}` : '관리자 계획에 따라 사용 가능한 자산과 음성을 확보하세요.'));
}

function nextWork(p,controlSource,selected) {
  const f=p.flow, stage=p.stage, m=p.mission, r=p.rework;
  const select=(...actions)=>actions.map(name=>controlSource.querySelector(`[data-action="${name}"]`)?.outerHTML||'').join('');
  const refresh=actionButton('refresh','상태 새로고침');
  if (p.readonly) return {message:'기존 검증 사례 · 읽기 전용'};
  if (stage==='completed') return {message:'최종 대표 승인이 기록되었습니다. 게시 승인은 별도입니다.'};
  const kind=stage==='awaiting_plan_approval'?'plan':stage==='awaiting_video_approval'?'video':null;
  if (kind && f[`${kind}_versions`].length) {
    const version=f[`${kind}_versions`].at(-1);
    const preview=version.render_receipt?.visual_scope==='local_procedural_cards_no_game_footage';
    return {message:`${kind==='plan'?'기획':'영상'} v${version.version} · ${preview?'무음 카드 시안은 영상 수정으로 진행합니다.':'최신 버전을 검토하고 승인 또는 수정 요청을 선택하세요.'}`,
      buttons:reviewActions(p,kind,version),target:`${kind}-panel`};
  }
  const attempt=f.render_attempts.at(-1);
  if (attempt?.status==='reserved') return {message:'로컬 렌더 실행 중 또는 결과 미확정 · 중복 렌더 차단',buttons:refresh};
  if (p.autonomous_production) return {...productionNext(p.autonomous_production,selected),target:'production-detail'};
  const budget=p.budget?.requests.find(request=>request.status==='pending');
  if (budget) return {message:'추가 예산의 사용 범위와 한도를 검토하세요.',target:'budget-panel',buttons:[...controlSource.querySelectorAll('[data-budget-decision]')].filter(button=>button.dataset.request===budget.id).map(button=>button.outerHTML).join('')};
  if (stage==='plan_revision' && r) {
    const action=['rework-finalize-recover','rework-script-recover-prepare','rework-quality-revise','rework-quality-prepare','rework-recover','rework-new-prepare','rework-prepare','rework-consent','rework-run'].find(name=>select(name));
    const reason=r.status==='approved'&&!r.settings?.ready?`서버 실행 설정 확인 필요 · ${r.settings?.missing.join(', ')||'Gemini 설정'}`:'';
    return {message:r.progress?.next_action||'같은 수정 요청의 진행 기록과 새 전송 범위를 확인하세요.',reason,target:'work-detail',
      buttons:action?select(action,...(action==='rework-quality-revise'?['rework-quality-hold']:[])):
        reason?actionButton('rework-run','AI 재작업 시작',reason)+refresh:refresh};
  }
  if (stage==='goal_submitted' || stage==='research_planning') {
    const action=(stage==='goal_submitted'?['budget-prepare','mission']:['budget-reprepare','mission-report','mission-connect-web','mission-consent','mission-run','mission-prepare']).find(name=>select(name));
    const scope=action==='mission-run'?'서명한 Gemini·YouTube 전송 범위에서 실행합니다.':action==='mission-consent'?'서명할 전송 범위와 호출 상한을 검토합니다.':'조사·기획의 실행 권한과 보고 상태를 확인하세요.';
    const consent=controlSource.querySelector('[data-consent="approve"]');
    if (p.budget_setup?.status==='pending' && consent) return {message:'공급자 데이터 전송 동의를 검토하세요. 예산 승인은 별도입니다.',target:'budget-setup',buttons:[...controlSource.querySelectorAll('[data-consent]')].map(button=>button.outerHTML).join('')};
    if (m?.running || (m?.status==='running' && !m?.can_run)) return {message:m.running?'기획 요청 실행 중입니다.':'기획 요청 상태가 미확정입니다. 중복 실행이 차단됩니다.',buttons:refresh,target:'work-detail'};
    if (action) return {message:scope,buttons:select(action),target:'work-detail'};
    if (p.budget?.consent_state==='valid') return {message:'승인된 예산과 유효한 외부 전송 동의 범위에서 작업합니다.',buttons:select('budget-run'),target:'budget-panel'};
    return {message:m?.reason?`기획 실행 상태 · ${m.reason}`:'내부 기획·대본 보고 또는 실행 선행조건 확인 대기',buttons:refresh,target:'work-detail'};
  }
  const action=['mission-preview','produce','planning'].find(name=>select(name));
  if (action) return {message:attempt?.status==='failed'?`최근 렌더 실패 · ${attempt.reason}`:
    action==='planning'?'기획 내부 작업을 엽니다.':'승인 대본으로 로컬 기술 시안을 제작합니다. 외부 호출은 0회입니다.',buttons:select(action),target:'work-detail'};
  if (p.production) {
    const reason=`승인 제작 입력 확인 필요 · ${p.production.reason||'준비 미완료'}`;
    return {message:'기술 시안 제작 대기',reason,buttons:actionButton('mission-preview','세로 기술 시안 제작',reason),target:'work-detail'};
  }
  return {message:'작업 보고 또는 제작 사양 등록 대기',buttons:refresh,target:'work-detail'};
}

let selectedWork;
function showDetail() {
  main.innerHTML = projectPage(detail, selectedVersions);
  const next=main.querySelector('#next-work');
  const work=nextWork(detail,main,selectedWork);
  const overrun=Object.entries(detail.autonomous_production?.timeline?.status==='approved'?{}:detail.autonomous_production?.voices||{}).filter(([,voice])=>voice.fits_timeline===false);
  next.innerHTML=`<h2 id="next-heading">현재 상태 / 다음 작업</h2><p><strong>${h(statuses[detail.stage][0])}</strong> · ${h(work.message)}</p>
    ${work.options?.length>1?`<label>제작 작업 선택 <select data-work-choice>${work.options.map(option=>
      `<option value="${h(option.choice)}" ${option.choice===work.choice?'selected':''}>${h(option.label)}</option>`).join('')}</select></label>`:''}
    ${work.reason?`<p class="warning" id="next-reason">${h(work.reason)}</p>`:''}
    ${overrun.length?`<p class="warning">${h(overrun.map(([scene])=>scene).join(', '))} · 승인 길이 초과로 합성 차단. 제작 상세에서 음성을 검토하세요.</p>`:''}
    <div class="actions">${work.buttons||''}${work.target?`<button class="button ghost" data-jump="${work.target}">관련 상세 보기</button>`:''}</div>`;
  const signature=button=>JSON.stringify([button.dataset.action,button.dataset.consent,button.dataset.budgetDecision,button.dataset.request]);
  const promoted=new Set([...next.querySelectorAll('[data-action], [data-consent], [data-budget-decision]')].map(signature));
  main.querySelectorAll('[data-action], [data-consent], [data-budget-decision]').forEach(control=>{
    if (!next.contains(control) && promoted.has(signature(control))) control.remove();
  });
}
async function route({focus=false}={}) {
  const current = ++routeVersion;
  const [name, store, pid] = location.hash.slice(1).split('/');
  const view = ['projects','references','project'].includes(name) ? name : 'dashboard';
  crumb.textContent = {dashboard:'대시보드',projects:'프로젝트',references:'참고자료',project:'프로젝트 상세'}[view];
  document.querySelectorAll('[data-nav]').forEach(a => {
    if (a.dataset.nav === (view==='project'?'projects':view)) a.setAttribute('aria-current','page');
    else a.removeAttribute('aria-current');
  });
  main.setAttribute('aria-busy','true');
  try {
    const dashboardData = await api('/api/studio');
    const projectData = view==='project' ? await api(detailApi({store,id:pid})) : null;
    if (current!==routeVersion) return;
    if (detail?.id!==projectData?.id) selectedWork=undefined;
    studio=dashboardData; detail=projectData; selectedVersions={};
    if (detail) showDetail(); else main.innerHTML=dashboard(view);
    if (focus) { main.focus({preventScroll:true}); window.scrollTo(0,0); }
  } catch (error) {
    if (current===routeVersion) main.innerHTML=blank(error.message || '화면을 불러오지 못했습니다.');
  } finally {
    if (current===routeVersion) main.setAttribute('aria-busy','false');
  }
}

function modal(title, fields, submit, handler) {
  dialog.innerHTML=`<form><h2 id="dialog-title">${h(title)}</h2>${fields}<p class="form-error" role="alert" hidden></p>
    <div class="actions dialog-actions"><button class="button ghost" type="button" data-cancel>취소</button><button class="button" type="submit">${h(submit)}</button></div></form>`;
  const form=dialog.querySelector('form');
  const cancel=form.querySelector('[data-cancel]');
  const button=form.querySelector('[type=submit]');
  cancel.onclick=()=>dialog.close();
  form.onsubmit=async event=>{
    event.preventDefault();
    if (button.disabled) return;
    const data=new FormData(form);
    button.disabled=true; cancel.disabled=true;
    const errorNode=form.querySelector('.form-error');
    errorNode.hidden=true;
    try {
      const result=await handler(data);
      dialog.close();
      if (result?.navigate) location.hash=result.navigate;
      else await route();
      notice(result?.message || '저장했습니다.');
    } catch(error) {
      errorNode.textContent=error.message || '요청을 완료할 수 없습니다.';
      errorNode.hidden=false;
    } finally { button.disabled=false; cancel.disabled=false; }
  };
  dialog.showModal();
}
dialog.addEventListener('cancel', event => {
  if (dialog.querySelector('[type=submit]')?.disabled) event.preventDefault();
});

function createProject() {
  const key=crypto.randomUUID();
  modal('새 프로젝트',`<label>영상 제작 목표<textarea name="goal" required maxlength="4000" rows="3" placeholder="예: 이번 주 스포츠 뉴스를 한 편으로 정리해 줘"></textarea></label>
    <div class="form-grid"><label>시청자 <small>선택</small><input name="audience" maxlength="300"></label>
    <label>언어 <small>선택</small><input name="language" maxlength="300" placeholder="예: 한국어"></label>
    <label>플랫폼 <small>선택</small><input name="platform" maxlength="300" placeholder="예: YouTube"></label>
    <label>길이(초) <small>선택</small><input name="duration" type="number" min="1" max="120"></label></div>
    <label>제작 제약 <small>선택</small><textarea name="notes" maxlength="2000" rows="2"></textarea></label>`,
    '프로젝트 만들기',async data=>{
      const body=Object.fromEntries(data);
      body.duration=body.duration ? Number(body.duration) : null;
      const result=await api('/api/project',{...body,key});
      return {navigate:projectHref({store:'workspace',id:result.id}),message:'프로젝트를 만들었습니다.'};
    });
}
function review(kind, action) {
  const project=detail;
  const report=project.flow[`${kind}_versions`].at(-1);
  const revise=action==='request_revision';
  const draft=revise && kind==='plan' && project.revision_draft?.version===report.version
    && project.revision_draft.report_hash===report.sha256 ? project.revision_draft : null;
  const title=revise?'수정 요청':kind==='plan'?'기획·대본 승인':'최종 영상 승인';
  const technical=kind==='video' && report.render_receipt.visual_scope==='local_procedural_cards_no_game_footage';
  modal(title,`<p class="muted">${kind==='plan'?'기획':'영상'} v${report.version} · SHA-256</p><p class="mono">${h(report.sha256)}</p>
    ${draft ? '<p>이 기획 버전의 로컬 검토 초안입니다. 내용을 확인하거나 편집한 뒤 수정 요청을 확정해 주세요.</p>' : ''}
    ${revise ? `<label>수정 피드백<textarea required name="feedback" maxlength="2000" rows="${draft ? 9 : 4}">${h(draft?.feedback || (technical?'기술 시안의 품질이 이상합니다. 승인된 대본으로 이전보다 나은 실제 영상과 음성을 제작해 주세요.':''))}</textarea></label>` :
      '<label>승인 메모 (선택)<textarea name="feedback" maxlength="2000" rows="2"></textarea></label>'}
    ${revise && kind==='video' ? '<label class="check"><input type="checkbox" name="changes_plan"> 대본·기획 변경이 필요합니다. 새 기획의 대표 승인 후 제작합니다.</label>' : ''}
    <p class="muted">이 결정은 외부 API 사용·결제·게시 권한을 부여하지 않습니다.</p>`,title,async data=>{
      await api(detailApi(project)+'/decide',{stage:kind,version:report.version,sha256:report.sha256,
        action,feedback:data.get('feedback'),changes_plan:data.has('changes_plan')});
      return {message:revise?'수정 요청을 저장했습니다.':'승인을 기록했습니다.'};
    });
}

function productionCommand(action,scene) {
  const project=detail;
  const a=project.autonomous_production;
  const check=(name,label)=>`<label class="check"><input type="checkbox" name="${name}" required>${label}</label>`;
  const free=check('free','해당 계정에서 현재 무료 제공 및 결제 비활성화를 확인했습니다.');
  const quota=check('quota','이 모델·지역의 요청 및 입출력 잔량을 확인했습니다.');
  const policy=check('policy','표시된 요청과 Google 무료 데이터 제공·인적 검토 정책에 동의합니다.');
  const plan=project.flow.plan_versions.at(-1);
  const source=a.source_assessment;
  const seconds=a.scope.storyboard.find(s=>s.scene_id===scene);
  const window=seconds?seconds.end-seconds.start:null;
  const batch=a.voice_batch, timing=a.timeline;
  const proposal=timing?.proposal;
  const adjustments=proposal?.decision.scenes.map((item,index)=>{
    const before=timing.measurements[index];
    return `<li>${h(item.scene_id)} · ${h(before.original_frames/24)}초 → ${h((item.frames/24).toFixed(3))}초 · 자막 ${h((item.caption_frames/24).toFixed(3))}초</li>`;
  }).join('');
  const total=proposal?.decision.scenes.reduce((sum,item)=>sum+item.frames,0)/24;
  const diagnostic=a.commons_diagnostic, relevance=a.commons_relevance;
  const operating=a.owner_policy, discovery=action==='production-relevance-rights'?relevance:
    action==='production-diagnostic-rights'?diagnostic:visualDiscovery(a);
  const publisher=a.publisher_discovery;
  const diagnosticQuery=diagnostic?.proposal?.queries[0];
  const commands={
    'production-listen':['청취 의견 저장',`<p>${h(scene)}의 검증된 음성에 연결합니다.</p><label>대표 청취 의견<textarea name="opinion" required maxlength="500"></textarea></label>`,
      data=>({scene,audio_sha256:a.voices[scene].audio_sha256,opinion:data.get('opinion')})],
    'production-publisher-approve':['공식 제작사 자료 탐색 검토·승인',
      `<p>무료 GET 최대 ${h(publisher?.proposal.max_gets)}회 · 무료 Gemini 최대 1회 · 파일 다운로드 0회</p>
      <ul>${(publisher?.proposal.entries||[]).map(row=>`<li>${h(row.url)}</li>`).join('')}</ul>
      <p>Gemini에는 승인 장면 요구, 제작사 후보 제목과 파일 유형 및 이전 탐색 실패 요약을 보냅니다.</p>`+
      check('confirmed','표시된 범위 및 Google 무료 서비스 데이터 처리를 승인하고 무료 적용·결제 미연결·충분한 한도를 확인했습니다.'),
      data=>({review_hash:publisher.review_hash,confirmed:data.has('confirmed')})],
    'production-publisher-run':['공식 제작사 자료 탐색 실행','<p>승인한 범위에서 한 번 탐색합니다. 접근 허용이 미확인된 페이지와 제한된 파일은 차단합니다.</p>',()=>({})],
    'production-publisher-revoke':['공식 자료 탐색 승인 철회','<p>이 범위에서 이후 요청을 시작하지 않습니다.</p>',()=>({})],
    'production-publisher-rights':['공식 자료 로컬 편집 권리 검토',
      `<p>선택한 각 파일과 해당 게임 IP에 적용되는 문구만 기록하세요. 게시 권한은 부여되지 않습니다.</p>
      ${(publisher?.result?.media||[]).filter(row=>publisher.result.eligible[row.id]).map(row=>`<label class="check"><input type="checkbox" name="asset" value="${h(row.id)}">${h(row.title)} · ${h(publisher.result.eligible[row.id].join(', '))}</label><p>${sourceLink(row.page)}</p>`).join('')}
      <label>권리 근거 문서<select name="terms_url" required>${(publisher?.result?.policies||[]).map(row=>`<option value="${h(row.url)}">${h(row.url)}</option>`).join('')}</select></label>
      ${(publisher?.result?.policies||[]).map(row=>`<details><summary>공식 문서 확인</summary><p>${sourceLink(row.url)}</p><p>${h(row.text)}</p></details>`).join('')}
      <label>무료 다운로드 및 로컬 편집 허가 원문<textarea name="evidence" required minlength="20" maxlength="600"></textarea></label>`+
      check('confirmed','선택한 모든 자료의 장면 적합성과 출처, 제3자 권리, 무료 다운로드 및 로컬 편집 허가를 확인했습니다.'),
      data=>({result_sha256:publisher.result_sha256,accepted:data.getAll('asset'),terms_url:data.get('terms_url'),evidence:data.get('evidence'),confirmed:data.has('confirmed')})],
    'production-relevance-approve':['관련 영상·이미지 복구 검토·승인',
      `<p>Commons GET 최대 ${h(relevance?.proposal?.max_searches)}회 · 후보 제목·설명·카테고리로 Gemini 적합성 판단 최대 1회 · 비용 $0 · 다운로드 0회</p>
        <ul>${(relevance?.proposal?.queries||[]).map(row=>`<li>${h(row.scene_ids.join(', '))} · ${row.media==='image'?'이미지':'영상'} · ${h(row.query)}</li>`).join('')}</ul>
        <p>Gemini에는 승인 장면, 후보 ID와 관련 메타데이터 및 도구 한계를 보냅니다. 실제 영상·음성 파일은 전송하지 않습니다.</p>`+
      check('confirmed','표시된 전송 범위와 Google 무료 서비스 데이터 처리를 승인하고 무료 적용·결제 미연결·충분한 한도를 확인했습니다.'),
      data=>({review_hash:relevance.review_hash,confirmed:data.has('confirmed')})],
    'production-relevance-run':['관련 자료 검색·적합성 검토 실행','<p>승인한 최대 한도에서 검색과 메타데이터 적합성 검토를 실행합니다. 자동 반복은 없습니다.</p>',()=>({})],
    'production-relevance-revoke':['관련성 복구 승인 철회','<p>현재 범위의 신규 요청을 차단합니다. 기존 결과는 보존합니다.</p>',()=>({})],
    'production-diagnostic-approve':['Commons 제외 원인 진단 검토·승인',
      `<p>${h(diagnosticQuery?.query)} · ${diagnosticQuery?.media==='image'?'이미지':'영상'} · 기존 기술 제외 ${h(diagnostic?.proposal.previous_rejected)}건</p>
      <p>동일한 Commons 메타데이터 GET 최대 1회 · 비용 $0 · 다운로드·Gemini 0회 · 자동 재시도 없음</p>`+
      check('confirmed','이 검색어와 파일 유형의 단일 진단 조회를 승인합니다.'),
      data=>({review_hash:diagnostic.review_hash,confirmed:data.has('confirmed')})],
    'production-diagnostic-run':['Commons 제외 원인 진단 실행','<p>승인한 진단 GET을 한 번 실행합니다. 기존 기록은 보존됩니다.</p>',()=>({})],
    'production-diagnostic-revoke':['진단 승인 철회','<p>이 진단 범위의 외부 조회를 차단합니다.</p>',()=>({})],
    'production-discovery-approve':['영상 자동 탐색 범위 검토·승인',
      `<p>Commons 검색·메타데이터 최대 ${h(discovery?.proposal.max_searches)}회 · 최대 비용 $0 · 파일 다운로드 없음</p>
        <ul>${(discovery?.proposal.queries||[]).map(row=>`<li>${h(row.scene_ids.join(', '))} · ${row.media==='image'?'정지 이미지':'영상'} · ${h(row.query)}</li>`).join('')}</ul>
        <p>후보가 부족하면 승인 장면 요구와 후보 통계로 무료 Gemini 대안을 최대 ${h(discovery?.proposal.fallback_max_calls)}회 제안합니다. Google 무료 서비스 데이터 처리 범위도 포함합니다.</p>`+
      check('confirmed','표시된 검색어와 대안 판단의 전송 범위를 승인합니다. Gemini 대안을 포함하는 경우 무료 적용, 결제 미연결 및 충분한 한도를 확인했습니다.'),
      data=>({review_hash:discovery.review_hash,confirmed:data.has('confirmed')})],
    'production-discovery-run':['영상 자동 탐색 실행','<p>정확히 승인한 검색어만 전송합니다. 결과는 내부에 저장합니다. 실제 영상은 다운로드하지 않습니다.</p>',()=>({})],
    'production-discovery-revoke':['영상 탐색 승인 철회','<p>이후 새 검색 요청을 시작하지 않습니다. 기존 기록은 보존합니다.</p>',()=>({})],
    'production-discovery-rights':['영상 후보 권리 검토',
      `<p>원본 파일 페이지에서 출처와 편집·표시 의무를 확인하세요. 게임 IP, 음원 및 제3자 영상 권리를 확인한 후보만 선택합니다.</p>
        ${(discovery?.result?.candidates||[]).filter(c=>c.reviewable).map(c=>`<div class="subpanel">
          <label class="check"><input type="checkbox" name="asset" value="${h(c.id)}">${h(c.title)} · ${h(c.scene_ids.join(', '))}</label>
          <p>${h(c.creator)} · ${h(c.credit)} · ${h(c.attribution)} · ${h(c.license_name)}
          ${c.share_alike?' · 동일조건변경허락':''} · ${sourceLink(c.original_page)} · ${sourceLink(c.license_url)}</p></div>`).join('')}`+
      check('confirmed','선택한 후보의 장면 적합성·저작자·출처·편집·표시 의무와 제3자 권리를 확인했고 로컬 편집·검토에 사용할 수 있음을 확인합니다.'),
      data=>({result_sha256:discovery.result_sha256,accepted:data.getAll('asset'),confirmed:data.has('confirmed')})],
    'production-assets-approve':['자산·편집 범위 검토·승인',
      `<p>Gemini 편집 판단 1회와 권리 확인 HTTPS 영상·이미지 최대 ${h(a.asset_execution?.proposal?.max_downloads)}회. 24시간 유효 · 비용 $0 · 검색·영상 생성·게시 권한 없음.</p>
       <p>Gemini에는 승인 장면과 실측 요약, 등록 자료 설명·해시를 보냅니다. 공개 무료 서비스의 데이터 개선 활용과 사람에 의한 검토가 가능할 수 있습니다.</p>
       <details open><summary>검토할 제공처·공식 권리 근거·다운로드 및 모델 범위</summary><pre>${h(JSON.stringify(a.asset_execution?.proposal,null,2))}</pre></details>`+
      check('confirmed','공식 제공처와 명시된 로컬 편집·다운로드 허가, 무료 조건 및 범위를 확인하고 표시된 정책을 승인합니다.'),
      data=>({review_hash:a.asset_execution.review_hash,confirmed:data.has('confirmed')})],
    'production-assets-revoke':['자산 범위 승인 철회','<p>이 범위에서 새 외부 요청을 시작하지 않습니다. 확보한 파일과 기록은 보존됩니다.</p>',()=>({})],
    'production-policy-approve':['개인 운영 정책 검토·승인',
      `<p>현재 프로젝트의 승인 대본과 제작 계획에만 적용합니다. 24시간 유효하며 제작 상세에서 철회할 수 있습니다.</p>
        <p>Google Gemini 무료 전용 · 비용 상한 $0 · 최대 ${h(operating?.proposal.units.length)}회 · 공급자 잔량·청구는 독립 확인되지 않았습니다. Google의 무료 서비스 개선 활용 및 사람의 검토가 가능할 수 있습니다.</p>
        <details open><summary>프로젝트·모델·전송 범위와 내부 상한</summary><pre>${h(JSON.stringify(operating?.proposal,null,2))}</pre></details>`+
      check('confirmed','무료 적용·결제 미연결 및 이 작업에 충분한 현재 사용 한도를 확인했으며 표시된 데이터 전송 정책과 제작 범위를 승인합니다.'),
      data=>({review_hash:operating.review_hash,confirmed:data.has('confirmed')})],
    'production-policy-run':['제작 실행','<p>서명된 운영 범위에서 가능한 다음 단계로 진행합니다. 실패·미확정이면 후속 외부 요청을 중단합니다.</p>',()=>({})],
    'production-policy-revoke':['운영 정책 철회','<p>이 정책의 이후 외부 요청을 차단합니다. 기존 승인과 시도 기록은 보존합니다.</p>',()=>({})],
    'production-batch-consent':['남은 장면 음성 일괄 동의',
      `<p>최대 ${h(batch?.review?.max_requests)}회 · 무료 전용 · 실패·미확정 시 중단 · 재시도 없음</p><details open><summary>장면별 정확한 요청과 해시</summary><pre>${h(JSON.stringify(batch?.review?.requests,null,2))}</pre></details>`+policy,
      data=>({review_hash:batch.review_hash,policy:data.has('policy')})],
    'production-batch-run':['남은 장면 음성 일괄 실행',
      `<p>서명된 장면 요청 최대 ${h(batch?.review?.max_requests)}회를 순서대로 실행합니다.</p>`,()=>({})],
    'production-timeline-prepare':['실측 시간 조정안 준비',free+quota+check('docs','현재 공급자 문서와 적용 조건을 확인했습니다.'),
      data=>({free:data.has('free'),quota:data.has('quota'),docs:data.has('docs')})],
    'production-timeline-consent':['시간 조정안 전송 동의',
      `<p>Gemini 텍스트 최대 1회 · 무료 전용 · WAV 파일 전송 없음</p><details><summary>전송 입력</summary><pre>${h(JSON.stringify(timing?.scope,null,2))}</pre></details>`+free+policy,
      data=>({review_hash:timing.review_hash,free:data.has('free'),policy:data.has('policy')})],
    'production-timeline-run':['관리자 시간 조정 판단 실행','<p>서명된 관리자 보완 요청 한 번을 실행합니다. 원본 음성과 장면 순서를 유지합니다.</p>',()=>({})],
    'production-timeline-approve':['대표 시간 조정안 검토·승인',
      `<p>기존 ${h((timing?.scope?.approved_total_frames||0)/24)}초 → 제안 ${h(total.toFixed(3))}초</p><ul>${adjustments||''}</ul>
        <p>${h(proposal?.decision.rationale)}</p><p>${h(proposal?.decision.quality_checks)}</p>
        <p class="mono">v${h(proposal?.version)} · ${h(proposal?.sha256)}</p>`+
      check('confirmed','이 시간 조정안을 승인합니다. 대본·음성은 그대로 유지합니다.'),
      data=>({version:proposal.version,sha256:proposal.sha256,confirmed:data.has('confirmed')})],
    'production-plan-prepare':['제작 계획 준비',free+quota+check('docs','현재 공급자 문서와 적용 조건을 확인했습니다.'),
      data=>({free:data.has('free'),quota:data.has('quota'),docs:data.has('docs')})],
    'production-plan-consent':['제작 계획 외부 전송 동의',
      `<p>Gemini 텍스트 요청 1회 · 무료 전용 · 실제 요금 독립 검증 없음</p><details><summary>전송 입력</summary><pre>${h(JSON.stringify(a.scope,null,2))}</pre></details>`+free+policy,
      data=>({review_hash:a.review_hash,free:data.has('free'),policy:data.has('policy')})],
    'production-plan-run':['관리자 제작 계획 실행','<p>서명된 텍스트 요청 한 번을 실행합니다. 직원·음성·영상 생성 요청은 포함하지 않습니다.</p>',()=>({})],
    'production-source-prepare':['자산 확보 업무 준비',free+quota+check('docs','현재 공급자 문서와 적용 조건을 확인했습니다.'),
      data=>({free:data.has('free'),quota:data.has('quota'),docs:data.has('docs')})],
    'production-source-consent':['자산 확보 업무 외부 전송 동의',
      `<p>별도 Gemini 텍스트 1회 · 무료만 · 검색·다운로드·생성 요청 0회</p><details><summary>전송 입력</summary><pre>${h(JSON.stringify(source?.scope,null,2))}</pre></details>`+free+policy,
      data=>({review_hash:source.review_hash,free:data.has('free'),policy:data.has('policy')})],
    'production-source-run':['자산 확보 직원 실행','<p>서명된 별도 텍스트 요청 1회를 실행합니다. 후보와 확보 절차만 반환합니다.</p>',()=>({})],
    'production-source-import':['선택된 로컬 자산 인수',
      `<p>${h(scene)}의 직원 선택 자산 · ${h(source?.result?.scenes.find(s=>s.scene_id===scene)?.asset_id)} · 외부 요청 0회</p>`+
      check('rights_ok','이 장면에 적합하고 등록 권리 기록에 따라 로컬 검토에 사용할 수 있음을 확인했습니다.'),
      data=>({scene,confirmed:data.has('rights_ok')})],
    'production-voice-prepare':['장면 음성 준비',
      `<p>승인 장면 ${h(window)}초. 발화가 초과하면 합성을 막고 원본 음성·시도 기록을 보존합니다. 잘라내기·가속·자동 재시도는 없습니다.</p>`+free+quota+
      '<label>모델·지역·결제·잔량 확인 내용<textarea name="evidence" required minlength="20" maxlength="300"></textarea></label>',
      data=>({scene,free:data.has('free'),quota:data.has('quota'),evidence:data.get('evidence')})],
    'production-voice-consent':['장면 음성 동의',
      `<p>이 장면만 1회. 미확정 결과도 차감합니다. 자동 재시도 없음.</p><pre>${h(JSON.stringify(a.voices[scene]?.payload,null,2))}</pre><p>승인 장면 ${h(a.voices[scene]?.approved_seconds)}초 · 응답 파일 수락 상한 ${h(a.voices[scene]?.diagnostic_max_seconds)}초</p>`+policy,
      data=>({scene,review_hash:a.voices[scene].review_hash,policy:data.has('policy')})],
    'production-voice-run':['장면 음성 실행','<p>이 장면에 서명한 요청 한 번을 실행합니다.</p>',()=>({scene})],
    'production-clip-import':['로컬 클립 인수','<label>인수 폴더의 MP4 파일명<input name="filename" required></label>'+
      '<label>현 장면 적합성 및 사용권 근거<textarea name="rights" required maxlength="600"></textarea></label>'+
      check('rights_ok','이 장면에 맞는 파일이며 로컬 제작·검토에 사용할 권리가 있습니다.'),
      data=>({scene,filename:data.get('filename'),rights:data.get('rights'),confirmed:data.has('rights_ok')})],
    'production-render':['로컬 영상 제작','<p>인수한 클립과 검증된 음성으로 로컬 제작을 시작합니다. 외부 요청은 없습니다.</p>',
      ()=>({version:plan.version,sha256:plan.sha256})],
  };
  const [title,fields,body]=commands[['production-diagnostic-rights','production-relevance-rights'].includes(action)?'production-discovery-rights':action];
  modal(title,fields,title,async data=>{
    const endpoint=discovery===a.adaptive_discovery && action.startsWith('production-discovery-')
      ? action.replace('production-discovery-','production-adaptive-') : action;
    try {
      await api(detailApi(project)+'/'+endpoint,body(data));
    } catch (error) {
      if (['production-policy-run','production-discovery-run','production-diagnostic-run','production-relevance-run','production-publisher-run'].includes(action)) await route();
      throw error;
    }
    return {message:'제작 상태를 갱신했습니다.'};
  });
}
function produce() {
  const project=detail;
  const plan=project.flow.plan_versions.at(-1);
  modal('로컬 기술 시안 제작',`<p>승인 기획 v${plan.version}으로 16:9 로컬 기술 시안을 렌더링합니다.</p>
    <label>작업 메모<textarea name="changes" rows="2" required maxlength="2000"></textarea></label>
    ${project.stage==='video_revision'?'<label>카메라<select name="camera"><option value="">기획안 유지</option><option value="push_in">천천히 확대</option><option value="pan_right">오른쪽 이동</option><option value="hold">고정</option></select></label>':''}`,
    '로컬 렌더 시작',async data=>{
      await api(detailApi(project)+'/produce',{version:plan.version,sha256:plan.sha256,changes:data.get('changes'),camera:data.get('camera')||null});
      return {message:'로컬 영상이 보고되었습니다.'};
    });
}
function missionCommand(action) {
  const project = detail;
  const mission = project.mission;
  const submit = (fields={}) => api(detailApi(project)+'/'+action, {job:mission.id, ...fields});
  if (action === 'mission-prepare') {
    modal('외부 전송 동의 제안 준비',`<p>Google 프로젝트 <strong>${h(mission.account_project)}</strong></p>
      <label class="check"><input type="checkbox" name="free" required>서버의 Gemini·YouTube 키가 이 프로젝트에 속하며, 결제 미연결 및 무료 사용 조건을 확인했습니다.</label>
      <label class="check"><input type="checkbox" name="youtube" required>YouTube Data API의 공개 검색·영상 메타데이터 사용 정책을 확인했습니다.</label>`,
    '제안 준비', async data => {
      await submit({account_project:mission.account_project, confirm_free_account:data.has('free'), confirm_youtube_policy:data.has('youtube')});
      return {message:'동의 제안을 준비했습니다.'};
    });
  } else if (action === 'mission-consent') {
    const proposal = mission.proposal;
    modal('외부 전송 동의 검토',`<p><strong>목표</strong> ${h(project.goal)}</p>
      <p><strong>시청자</strong> ${h(project.audience)} · <strong>길이</strong> 관리자 판단</p>
      ${facts([['언어', proposal.constraints.language], ['플랫폼', proposal.constraints.platform],
        ['화면 비율', proposal.constraints.aspect], ['제작 제약', proposal.constraints.notes || '미지정']])}
      ${missionProposal(proposal)}
      <label class="check"><input type="checkbox" name="accept" required>이 범위의 외부 데이터 전송과 Google 무료 서비스 데이터 제공 정책에 동의합니다.</label>`,
    '동의 저장', async data => {
      await submit({review_hash:proposal.review_hash, confirm_free_data_policy:data.has('accept')});
      return {message:'서명 동의를 저장했습니다. 실행은 별도입니다.'};
    });
  } else if (action === 'mission-run') {
    modal('미션 01 실행','<p>서명한 범위로 Gemini와 YouTube 요청을 시작합니다. 진행 상태는 상태 새로고침에서 확인할 수 있습니다.</p>',
    '외부 요청 시작', async () => {
      await submit();
      return {message:'미션 실행을 요청했습니다.'};
    });
  }
}
main.addEventListener('click',async event=>{
  const button=event.target.closest('button');
  if (!button || button.disabled) return;
  if (button.dataset.jump) {
    const target=document.getElementById(button.dataset.jump);
    if (target) {
      const header=main.querySelector('#next-work');
      window.scrollTo(0,window.scrollY+target.getBoundingClientRect().top-header.offsetHeight-12);
    }
    return;
  }
  if (button.dataset.filter || button.dataset.action==='clear') {
    filter=filter===button.dataset.filter ? null : (button.dataset.filter||null);
    main.innerHTML=dashboard(location.hash==='#projects'?'projects':'dashboard');
    if (filter) main.querySelector(`[data-filter="${filter}"]`)?.focus();
  } else if (button.dataset.action==='create') createProject();
  else if (button.dataset.action?.startsWith('research-')) researchCommand(button.dataset.action);
  else if (button.dataset.action?.startsWith('production-')) productionCommand(button.dataset.action,button.dataset.scene);
  else if (button.dataset.action==='mission-preview') {
    const project=detail;
    const plan=project.flow.plan_versions.at(-1);
    modal('세로 기술 시안 제작','<p>승인 자막과 장면을 자체 생성 카드로 제작합니다. 외부 전송과 비용은 0입니다.</p>'+
      (project.production.local_speech?'<label class="check"><input name="speech" type="checkbox">로컬 MeloTTS 음성 사용</label>':'<p>이번 시안은 무음입니다.</p>'),
      '로컬 제작 시작',async data=>{
        await api(detailApi(project)+'/mission-preview',{version:plan.version,sha256:plan.sha256,
          audio_mode:data.has('speech')?'local_speech':'none'});
        return {message:'세로 시안을 영상 검토에 제출했습니다.'};
      });
  }
  else if (button.dataset.action==='rework-finalize-recover') {
    const project=detail;
    const recovery=project.rework.final_recovery;
    modal('기존 검토로 대표 제출 복구','<p>수락된 검토를 로컬에서 집계하고 기획 승인 대기로 제출합니다. 외부 요청과 대표 승인 없이 처리합니다.</p>',
      '대표 승인 대기로 제출',async ()=>{
        await api(detailApi(project)+'/rework-finalize-recover',{job:recovery.job,state_hash:recovery.state_hash});
        return {message:'기획 승인 대기로 제출했습니다.'};
      });
  }
  else if (button.dataset.action==='plan-markdown') {
    const project=detail;
    const reports=project.flow.plan_versions;
    const report=reports.find(item=>item.version===selectedVersions.plan) || reports.at(-1);
    button.disabled=true;
    try {
      const result=await api(detailApi(project)+'/plan-markdown', {version:report.version, sha256:report.sha256});
      const url=URL.createObjectURL(new Blob([result.markdown], {type:'text/markdown;charset=utf-8'}));
      const link=document.createElement('a');
      link.href=url;
      link.download=`plan-review-v${report.version}.md`;
      link.click();
      setTimeout(()=>URL.revokeObjectURL(url), 1000);
    } catch(error) { notice(error.message,true); }
    finally { button.disabled=false; }
  }
  else if (['mission-prepare','mission-consent','mission-run'].includes(button.dataset.action)) missionCommand(button.dataset.action);
  else if (['mission-connect-web','mission-report'].includes(button.dataset.action)) {
    button.disabled=true;
    try {
      await api(detailApi(detail)+'/'+button.dataset.action, {job:detail.mission.id});
      await route();
      notice(button.dataset.action==='mission-connect-web'?'독립 웹 조사를 연결했습니다.':'내부 검토 결과를 제출했습니다.');
    } catch(error) { notice(error.message,true); button.disabled=false; }
  }
  else if (['rework-prepare','rework-new-prepare','rework-quality-prepare','rework-script-recover-prepare'].includes(button.dataset.action)) {
    const managerRecovery=detail.rework?.recovery_audit?.kind==='manager_review_after_repeat';
    const editorRecovery=detail.rework?.recovery_audit?.kind==='editor_handoff_after_mismatch';
    modal(editorRecovery?'스토리보드 관리자 검토 준비':managerRecovery?'기존 대본 관리자 재검토 준비':button.dataset.action==='rework-script-recover-prepare'?'기존 대본 재사용 · 외부 전송 동의 준비':'AI 재작업 동의 준비',`<p>${editorRecovery?'수락된 대본을 그대로 투영한 시스템 스토리보드의 관리자 검토를 준비합니다. ':managerRecovery?'기존 대본의 관리자 재검토부터 시작하는 별도 작업을 준비합니다. ':button.dataset.action==='rework-script-recover-prepare'?'이전 기획과 대본을 복사한 새 작업을 준비하고 대본 수정부터 진행합니다. 기존 관리자의 실패한 검토는 승인으로 바꾸지 않습니다. ':'저장된 피드백을 사용합니다. '}지금은 제안만 준비하며 Gemini API 호출은 없습니다.</p><label>Google 프로젝트<input name="account_project" value="gen-lang-client-0938732315" required></label><label class="check"><input type="checkbox" name="free" required>키 소속 프로젝트와 결제 미연결·무료 조건 확인</label>`,
      '제안 준비',async data=>{await api(detailApi(detail)+'/'+button.dataset.action,{account_project:data.get('account_project'),confirm_free_account:data.has('free'),...(['rework-new-prepare','rework-quality-prepare','rework-script-recover-prepare'].includes(button.dataset.action)?{previous_job:detail.rework.job}:{})});return {message:'새 동의 제안을 확인하세요.'};});
  }
  else if (['rework-quality-revise','rework-quality-hold'].includes(button.dataset.action)) {
    const revision=button.dataset.action==='rework-quality-revise';
    const report=detail.rework;
    const draft=report.quality_draft;
    const matchedDraft=draft?.job===report.job && draft.report_hash===report.quality_report_hash;
    const defaults=matchedDraft ? draft.feedback : report.progress?.quality_report?.feedback||'';
    modal(revision?'AI 관리자 품질 보고 · 수정 지시':'AI 관리자 품질 보고 · 보류',
      `<p>현재 대본과 관리자 검토 근거를 확인한 뒤 지시를 기록합니다. 이 동작은 AI를 호출하지 않습니다.</p>
      ${revision && matchedDraft ? '<p>이 중단 작업의 로컬 초안입니다. 검토하거나 편집한 뒤 저장해 주세요.</p>' : ''}
      <label>대표 의견<textarea name="feedback" maxlength="2000" rows="5" ${revision?'required':''}>${h(revision?defaults:'')}</textarea></label>`,
      '지시 저장',async data=>{
        await api(detailApi(detail)+'/rework-quality-decide',{
          job:report.job,report_hash:report.quality_report_hash,
          action:revision?'request_revision':'hold',
          feedback:(data.get('feedback')||'').toString()
        });
        return {message:'대표 지시 저장 완료. 별도 동의 없이 AI를 다시 호출하지 않습니다.'};
      });
  }
  else if (button.dataset.action==='rework-consent') {
    if (detail.rework.proposal?.limits?.max_calls===null) {
      button.disabled=true;
      try {
        // A previously drafted unlimited proposal is not consentable.
        // Fix its technical ceiling before showing the scope to the owner.
        await api(detailApi(detail)+'/rework-cap-prepare',{});
        await route();
      } catch(error) {
        notice(error.message,true);button.disabled=false;return;
      }
    }
    const editorRecovery=detail.rework.proposal?.rework_scope?.reference?.previous_failed_attempt?.recovery_scope==='accepted_writer_system_storyboard_new_job';
    if (detail.rework.status!=='pending' || detail.rework.proposal?.limits?.max_calls!==(editorRecovery?1:7)) {
      notice('작업 범위와 호출 상한을 확인할 수 없습니다. 동의하지 않았습니다.',true);
      return;
    }
    modal('새 외부 전송 동의',`<p>이 작업에서 최대 <strong>${h(detail.rework.proposal?.limits?.max_calls??'미설정')}회</strong>의 Gemini 요청을 허용하는 별도 동의입니다. ${detail.rework.proposal?.rework_scope?.reference?.previous_failed_attempt?.recovery_scope==='accepted_writer_system_storyboard_new_job'?'이 경로는 시스템 스토리보드의 관리자 검토 요청 한 번으로 종료합니다. ':detail.rework.proposal?.rework_scope?.reference?.previous_failed_attempt?.recovery_scope==='validated_writer_manager_review_new_job'?'첫 호출은 기존 대본을 대상으로 한 관리자 재검토입니다. 인용 오류만으로 작가를 다시 호출하지 않습니다. ':detail.rework.proposal?.rework_scope?.reference?.previous_failed_attempt?.recovery_scope==='validated_plan_writer_reuse_new_job'?'이전 검증된 기획과 대본을 재사용하고 새 작업은 대본 수정부터 진행합니다. 과거 요청 3회는 재전송하지 않으며 새 요청은 별도 기록됩니다. ':''} AI 관리자·대본 직원·편집 직원의 하위 작업에는 반복 동의하지 않습니다. 원 목표·대표 피드백·이전 대본/스토리보드·공개 관측을 고정 무료 Gemini에 전송합니다. Google 개선 활용·인적 검토 가능. 청구/쿼터 독립 확인 불가. 새 실행이며 과거 동의를 재사용하지 않습니다.</p><label class="check"><input type="checkbox" name="free" required>프로젝트·키·무료 조건을 확인했습니다.</label><label class="check"><input type="checkbox" name="policy" required>표시된 전송 범위와 무료 데이터 정책에 동의합니다.</label>`,
      '이 범위에 동의',async data=>{await api(detailApi(detail)+'/rework-consent',{review_hash:detail.rework.review_hash,confirm_free_account:data.has('free'),confirm_data_policy:data.has('policy')});return {message:'동의 저장. AI 재작업 시작을 눌러 실행하세요.'};});
  }
  else if (['rework-run','rework-recover'].includes(button.dataset.action)) {
    button.disabled=true;
    try {await api(detailApi(detail)+'/'+button.dataset.action,{});await route();notice('AI 재작업을 시작했습니다. 상태 새로고침으로 진행을 확인하세요.');}
    catch(error){notice(error.message,true);button.disabled=false;}
  }
  else if (['budget-prepare','budget-reprepare'].includes(button.dataset.action)) {
    const project=detail;
    const renew=button.dataset.action==='budget-reprepare';
    modal('예산 모드 등록 준비',`<p>서버 로컬에 연결된 키를 사용합니다. 키를 입력하지 마세요. 초기 예산은 0이며 실행은 별도입니다.</p>
      <label>확인한 Google 계정 프로젝트 ID<input name="account_project" required maxlength="200"></label>
      <label class="check"><input name="confirm_free_account" type="checkbox" required>해당 키의 소속 프로젝트와 결제 미연결·무료 조건을 확인했습니다.</label>`,
      '동의 제안 준비',async data=>{
        await api(detailApi(project)+(renew?'/budget-reprepare':'/budget-prepare'),{account_project:data.get('account_project'),confirm_free_account:data.has('confirm_free_account'),...(renew?{review_hash:project.budget_setup.review_hash}:{})});
        return {message:'제안을 준비했습니다. 별도 데이터 전송 동의를 검토해 주세요.'};
      });
  }
  else if (button.dataset.consent||button.dataset.action==='budget-revoke') {
    button.disabled=true;
    try {
      if (button.dataset.consent) await api(detailApi(detail)+'/budget-consent',{review_hash:detail.budget_setup.review_hash,action:button.dataset.consent});
      else await api(detailApi(detail)+'/budget-revoke',{});
      await route();notice('공급자 동의 상태를 저장했습니다. 예산 승인은 별도입니다.');
    } catch(error) { notice(error.message,true);button.disabled=false; }
  }
  else if (button.dataset.budgetDecision || button.dataset.action==='budget-run') {
    button.disabled=true;
    try {
      if (button.dataset.budgetDecision) {
        const request=detail.budget.requests.find(r=>r.id===button.dataset.request);
        await api(detailApi(detail)+'/budget-decide',{request_id:request.id,review_hash:request.review_hash,action:button.dataset.budgetDecision});
      } else await api(detailApi(detail)+'/budget-run',{});
      await route();
      notice('예산·실행 상태를 확인했습니다.');
    } catch(error) { notice(error.message,true); button.disabled=false; }
  }
  else if (button.dataset.review) review(...button.dataset.review.split(':'));
  else if (button.dataset.action==='produce') produce();
  else if (button.dataset.action==='refresh') await route();
  else if (['planning','mission'].includes(button.dataset.action)) {
    button.disabled=true;
    try {
      await api(detailApi(detail)+'/'+button.dataset.action,{});
      await route();
      notice(button.dataset.action==='mission'?'기획 미션을 준비했습니다. 외부 AI 실행 권한을 기다립니다.':'기획 작업을 열었습니다.');
    } catch(error) {
      notice(error.message,true);
      button.disabled=false;
    }
  }
});
main.addEventListener('change',event=>{
  if (event.target.hasAttribute('data-work-choice')) {
    selectedWork=event.target.value;
    showDetail();
    main.querySelector('[data-work-choice]')?.focus({preventScroll:true});
    return;
  }
  if (!event.target.dataset.version) return;
  const kind=event.target.dataset.version;
  selectedVersions[kind]=Number(event.target.value);
  showDetail();
  main.querySelector(`[data-version="${kind}"]`)?.focus({preventScroll:true});
});
main.addEventListener('error',event=>{
  if (event.target.matches('.thumbnail img')) event.target.hidden=true;
  if (event.target.matches('video')) notice('브라우저에서 이 영상 파일을 재생할 수 없습니다.',true);
},true);
window.addEventListener('hashchange',()=>{filter=null;route({focus:true});});
route();
