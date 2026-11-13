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
  if (!response.ok) throw new Error(value.error);
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
      ${plan.task_history.map(t=>`<div><h3>${h(eventRoles[t.role] || t.role)} · 버전 ${t.versions.length}</h3>
      ${t.reviews.map((r,i)=>`<p>v${i+1} · ${r.action==='accept'?'수락':'수정 요청'} · ${h(r.rationale)} ${h(r.feedback)}</p>`).join('')}</div>`).join('')}</details>` : ''}
    <details class="subpanel" open><summary>대본 전문</summary><p class="script">${h(script.transcript)}</p></details>
    <details class="subpanel" open><summary>장면 스토리보드</summary><div class="beats">${script.narrative_beats.map(beat => `<article class="beat">
      ${badge(`${beat.start}–${beat.end}초`,beat.shot_type==='demo'?'film':'script')}<h3>${h(beat.caption)}</h3>
      <p>${h(beat.screen)}</p><p class="muted">${h(beat.source_ref)} · ${beat.source_status==='pending'?'소스 미확보':'로컬 예시'}</p></article>`).join('')}</div></details>
    <details class="subpanel" open><summary>조사 출처·권리·미확인 항목</summary>
      ${plan.sources.length ? plan.sources.map(s=>`<p>${h(s.claim)} · ${h(s.observed_at)} · ${h(s.rights)} ${sourceLink(s.url)}</p>`).join('') : '<p class="muted">이 보고서에 등록된 외부 조사 출처가 없습니다.</p>'}
      <p>${h(plan.risks)}</p>${script.unknowns.map(u=>`<p class="muted">${h(u)}</p>`).join('')}</details>
    ${plan.representative_feedback?`<details class="subpanel" open><summary>대표 피드백 반영·관리자 재기획</summary><p>${h(plan.representative_feedback)}</p><p>${h(plan.changes)}</p><pre>${h(JSON.stringify(plan.goal_reviews,null,2))}</pre></details>`:''}
    <details class="subpanel"><summary>편집 직원 스토리보드 · 이전 버전 비교</summary>${[plan,previous].filter(Boolean).map(v=>`<h3>기획 v${v.version}</h3>${(v.task_history||[]).filter(t=>t.role==='editor').map(t=>`<pre>${h(t.versions.at(-1)?.content||'')}</pre>`).join('')}`).join('')}</details>
    <details class="subpanel"><summary>변경사항·보고서 해시</summary><p>${h(plan.changes)}</p><p class="mono">${h(plan.sha256)}</p>
      ${previous ? `<p class="muted">이전 기획 v${previous.version} 대본</p><p class="script">${h(previous.script.transcript)}</p>` : ''}
      <p class="muted">내부 검토 ${plan.internal_reviews.length}건 · ${h(plan.internal_reviews.map(r=>r.action==='accept'?'수락':r.action==='revise'?'수정':'보류').join(' → '))}</p></details>
    ${reviewActions(p,'plan',plan)}
  </section>`;
}
function versionSelect(kind, versions, chosen) {
  const label = kind === 'plan' ? '기획 버전' : '영상 버전';
  return `<label>${label}<select aria-label="${label}" data-version="${kind}">${[...versions].reverse().map(item =>
    `<option value="${item.version}" ${item.version===chosen.version?'selected':''}>v${item.version}</option>`).join('')}</select></label>`;
}
function reviewActions(p, kind, report) {
  if (p.readonly || p.stage !== `awaiting_${kind}_approval` || p.flow[`${kind}_versions`].at(-1)?.version !== report.version) return '';
  const label = kind==='plan' ? '기획·대본 승인' : '최종 영상 승인';
  return `<div class="actions subpanel"><button class="button" data-review="${kind}:approve">${icon('check')}${label}</button>
    <button class="button secondary" data-review="${kind}:request_revision">${icon('revision')} 수정 요청</button></div>`;
}
function videoPanel(p, video) {
  if (!video) return '';
  const r=video.render_receipt;
  return `<section class="panel" id="video-panel"><div class="panel-heading"><h2>${icon('film')} 영상 검토</h2>${versionSelect('video',p.flow.video_versions,video)}</div>
    <video class="player" controls playsinline preload="metadata" poster="${h(video.thumbnail)}" src="${h(video.url)}" aria-label="영상 버전 ${video.version}"></video>
    <div class="inline">${badge('전체 디코딩 통과','check','green')}${badge('기술 검증용','alert','amber')}</div>
    ${facts([['제작 입력',`승인 기획 v${video.plan_version}`],['영상',`${r.width}×${r.height} · ${Number(r.duration_seconds).toFixed(3)}초`],
    ['음성',r.audio_mode==='espeak_reference'?'eSpeak 로컬 참조 음성':r.audio?'로컬 음성':'없음'],['자막','장면 단위'],
    ['QA','기술 검사 완료 · 시청·청취 품질 미평가'],['비용',`$${video.cost_usd}`]])}
    <details class="subpanel"><summary>변경사항·파일 및 기획 SHA-256</summary><p>${h(video.changes)}</p>
    <p class="muted">영상 파일</p><p class="mono">${h(video.artifact_sha256)}</p>
    <p class="muted">승인 기획</p><p class="mono">${h(video.plan_sha256)}</p></details>
    <details class="subpanel"><summary>시각 소스·사용 권리</summary>
    ${r.source_licenses.map(item=>`<p>${h(item.file)} · ${h(item.creator)} · ${h(item.license)}</p>`).join('')}
    <p class="muted">글꼴 · ${h(r.font_license)}</p></details>
    ${reviewActions(p,'video',video)}</section>`;
}
function missionStatus(mission) {
  if (!mission) return '';
  const reasons = {mission_independent_web_research_unavailable:'조사 직원의 웹 접근 도구 미연결 · 게임·길이 근거 조사 불가',
    employee_web_authorization_required:'YouTube 공개 검색·메타데이터 접근의 별도 승인과 키 확인 필요',
    employee_web_failed_no_retry:'직원 웹 조사 실패 또는 미확정 · 자동 재호출 차단',
    mission_old_scope_superseded:'이전 조사 입력이 들어간 준비본 · 최신 미션 프로젝트를 사용해 주세요.',
    provider_rate_limit:'요청 한도에 도달했습니다.', free_request_failed:'요청이 실패했거나 시간 초과되었습니다.',
    known_script_defects:'대본의 검증 결함이 남아 있습니다.', manager_stopped:'관리자가 내부 작업을 중단했습니다.',
    manager_plan_stopped:'관리자가 계획 단계에서 중단했습니다.', optional_technical_cap_reached:'승인된 호출 한도에 도달했습니다.'};
  const terminal = ['stopped','paused','needs_operational_permission'].includes(mission.status);
  const blocked = ['mission_independent_web_research_unavailable','mission_old_scope_superseded'].includes(mission.reason);
  const status = blocked ? '독립 조사 연결 대기 · 실제 호출 0회' : mission.status==='needs_user_review' ? '내부 검토 완료 · 대표 제출 확인' :
    terminal ? '실행 중단 · 자동 재호출 없음' : mission.status==='running' ? '기획 작업 진행 중 · 재호출 금지' :
    mission.authorized ? '외부 전송 승인 기록 있음 · 별도 실행 대기' : '외부 AI 실행 권한 필요';
  return `<div class="subpanel"><h3>미션 01 · 기획과 대본</h3><p class="warning">${h(status)}</p>
    ${facts([['모델',mission.model],['기록된 시도',mission.attempts.length]])}
    ${mission.reason ? `<p class="muted">${h(reasons[mission.reason] || mission.reason)}</p>` : ''}
    ${mission.assignments.map(t=>`<p class="muted">${h(eventRoles[t.role] || t.role)} · ${t.state==='accepted_by_ai_manager'?'내부 수락':'작업·검토 대기'} · v${t.versions}</p>`).join('')}
    ${mission.attempts.length ? `<details><summary>요청·응답 기록</summary>${mission.attempts.map(a=>`
      <div class="subpanel"><p>${h(a.phase)} · ${h(a.task_id || a.role_kind)} · ${h(a.status)} · HTTP ${h(a.http_status ?? '미수신')}</p>
      <p class="muted">${h(time(a.response_received_at || a.reserved_at))} · ${h(a.usage.total_tokens ?? '미확인')} 토큰 · ${a.cost_basis?'무료 계정 확인 기준':'청구 미확인'}</p>
      <p class="mono">요청 ${h(a.request_hash)}</p><p class="mono">응답 ${h(a.response_hash || '미수신')}</p></div>`).join('')}</details>` : ''}
    <button class="button ghost" data-action="refresh">${icon('revision')} 상태 새로고침</button></div>`;
}
function operations(p) {
  if (p.readonly) return '<p class="warning">기존 검증 사례 · 읽기 전용</p>';
  if (p.stage === 'completed') return '<p class="warning">최종 대표 승인이 기록되었습니다. 게시 작업은 별도입니다.</p>';
  const attempt = p.flow.render_attempts.at(-1);
  const failed = attempt?.status === 'failed' ? `<p class="warning">최근 렌더 실패 · ${h(attempt.reason)}</p>` : '';
  if (attempt?.status === 'reserved') return '<p class="warning">로컬 렌더 실행 중 또는 결과 미확정 · 중복 렌더 차단</p>';
  if (p.stage==='goal_submitted') return `<button class="button secondary" data-action="mission">${icon('folder')} 미션 01 준비</button><p class="muted">기획 작업만 준비합니다. 외부 전송은 별도 승인 후 실행합니다.</p>`;
  if (p.rework && p.stage==='plan_revision') return reworkPanel(p);
  if (p.mission && p.stage==='production') return '<p class="warning">기획 승인 기록 완료 · 제작 사양 등록 대기</p>';
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
    ${r.recovery_audit?`<section class="subpanel"><h3>중단된 대본 검토 · 기존 자료 분석</h3>
      <p class="warning">이전 AI 관리자 검토는 최종 검증을 통과하지 못했습니다. 기존 작업과 API 호출 3회를 변경하지 않습니다.</p>
      ${facts([['이전 기획 호출과 결과',r.recovery_audit.reusable_plan?'검증 완료 · 재사용 후보':'재사용 조건 미충족'],['이전 대본 호출과 결과',r.recovery_audit.reusable_writer?'검증 완료 · 재사용 후보':'재사용 조건 미충족'],['저장된 관리자 수정 의견',r.recovery_audit.review_available?'있음 (최종 미검증)':'검증 필요'],['대본 결함 재검사',r.recovery_audit.checks_available?'완료':'추가 확인 필요'],['발견된 결함',r.recovery_audit.defect_count??'미확인'],['수정 의견에 빠진 식별자',r.recovery_audit.missing_issue_ids?.join(', ')||'없음 또는 미확인'],['복구 후보 판정',r.recovery_audit.safe_for_recovery_proposal?'기존 결과 재사용 가능한 신규 작업 후보':'재사용 근거 추가 확인 필요'],['기존 작업 재실행','차단 · 원본 보존']])}
      ${r.recovery_audit.review_available?`<p><strong>저장된 AI 관리자 수정 의견</strong></p><p class="script">${h(r.recovery_audit.manager_feedback)}</p>`:''}
      ${r.recovery_audit.missing_defects?.length?`<details><summary>시스템 검출 항목과 수정 방법</summary><pre>${h(JSON.stringify(r.recovery_audit.missing_defects,null,2))}</pre></details>`:''}
      <p class="muted">저장된 기획과 대본은 재사용 후보입니다. 이 점검만으로 AI 관리자가 승인했거나 기존 중단 작업을 계속 실행할 수 있다는 뜻은 아닙니다.</p>
    </section>`:''}
    ${progress?.quality_report?`<section class="panel"><h3>${progress.quality_report.source==='legacy_failure_diagnostic_not_manager_review'?'과거 검토 실패 진단 · 대표 지시 필요':'AI 관리자 품질 보고 · 대표 지시 필요'}</h3>
      <p class="warning">${progress.quality_report.source==='legacy_failure_diagnostic_not_manager_review'
        ?'이전 AI 관리자 응답은 HTTP 200이지만 검증에 실패했습니다. 아래 내용은 관리자 승인이나 확정 평가가 아니며, 대표가 저장된 대본을 직접 판단해야 합니다.'
        :'수정 한도에 도달했거나 AI 관리자가 대표 판단을 요청했습니다. 자동 재호출은 없습니다.'}</p>
      <p><strong>대본 직원 산출물</strong></p><pre>${h(r.quality_script||'저장된 대본 없음')}</pre>
      <p><strong>부족한 검토 항목</strong></p><pre>${h(JSON.stringify(progress.quality_report.failed_checks,null,2))}</pre>
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
  if (setup.status==='available') return `<section class="panel"><h2>프로젝트별 예산 모드</h2>
    <p>60초 대본 경로 · 초기 예산 0 · 외부 데이터 전송 동의와 예산 승인을 따로 검토합니다.</p>
    <p class="muted">${h(setup.local_setup)}</p><button class="button secondary" data-action="budget-prepare">예산 모드 등록 준비</button></section>`;
  return `<section class="panel"><h2>공급자 데이터 전송 동의 · ${h(setup.status)}</h2>
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
  <nav class="stepper" aria-label="업무 단계">${steps.map(([label,symbol],i)=>`<div class="step ${i===stepIndex?'current':i<stepIndex?'done':''}" ${i===stepIndex?'aria-current="step"':''}>${icon(i<stepIndex?'check':symbol)}${label}</div>`).join('')}</nav>
  <div class="detail-grid"><div class="stack">${budgetSetupPanel(p)}${budgetPanel(p)}${videoPanel(p,video)}${planPanel(p,plan,prior)}</div>
  <aside class="stack"><section class="panel"><h2>${icon('user')} 현재 업무</h2>${facts([['담당',s[1]],['다음 행동',s[2]],['대상',p.audience],['언어',f.constraints.language||'미정'],['플랫폼',f.constraints.platform||'미정'],['길이',f.constraints.duration_seconds?f.constraints.duration_seconds+'초':'미정'],['제약',f.constraints.notes||'미정']])}
  ${operations(p)}${p.stage!=='plan_revision'?reworkPanel(p):''}${p.rework&&p.mission?`<details class="subpanel"><summary>이전 미션 기획 보존 · 참고용 (최신 재작업 아님)</summary><p>아래 내부 수락은 이전 버전의 기록입니다. 최신 진행 상황은 위 AI 재작업 현황을 확인하세요.</p>${missionStatus(p.mission)}</details>`:missionStatus(p.mission)}${p.jobs.at(-1)?.assignments.length ? `<div class="subpanel"><h3>직원 인수 상태</h3>${p.jobs.at(-1).assignments.map(t=>`<p class="muted">${icon(t.role==='writer'?'script':t.role==='qa'?'shield':'film')} ${h(eventRoles[t.role] || t.role)} · ${t.state==='accepted_by_ai_manager'?'내부 검토 수락':'작업 또는 검토 대기'} · v${t.versions}</p>`).join('')}</div>` : ''}</section>
  <section class="panel"><h2>${icon('revision')} 대표 결정 이력</h2><ol class="timeline">${[...f.decisions].reverse().map(d=>`<li><strong>${d.stage==='plan'?'기획':'영상'} v${d.version} · ${d.action==='approve'?'승인':'수정 요청'}</strong><p class="muted">${h(time(d.at))}${d.changes_plan?' · 기획 재승인 필요':''}</p><p>${h(d.feedback)}</p></li>`).join('') || '<li>등록된 대표 결정이 없습니다.</li>'}</ol></section>
  <section class="panel"><h2>${icon('clock')} 진행 타임라인</h2><ol class="timeline">${[...f.events].reverse().map(e=>`<li><strong>${h(statuses[e.stage]?.[0] || e.stage)}</strong><p class="muted">${h(time(e.at))}</p></li>`).join('')}</ol></section></aside></div>`;
}
let selectedVersions = {};
function showDetail() { main.innerHTML = projectPage(detail, selectedVersions); }
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
  const title=revise?'수정 요청':kind==='plan'?'기획·대본 승인':'최종 영상 승인';
  modal(title,`<p class="muted">${kind==='plan'?'기획':'영상'} v${report.version} · SHA-256</p><p class="mono">${h(report.sha256)}</p>
    ${revise ? '<label>수정 피드백<textarea required name="feedback" maxlength="2000" rows="4"></textarea></label>' :
      '<label>승인 메모 (선택)<textarea name="feedback" maxlength="2000" rows="2"></textarea></label>'}
    ${revise && kind==='video' ? '<label class="check"><input type="checkbox" name="changes_plan"> 대본·기획 변경이 필요합니다. 새 기획의 대표 승인 후 제작합니다.</label>' : ''}
    <p class="muted">이 결정은 외부 API 사용·결제·게시 권한을 부여하지 않습니다.</p>`,title,async data=>{
      await api(detailApi(project)+'/decide',{stage:kind,version:report.version,sha256:report.sha256,
        action,feedback:data.get('feedback'),changes_plan:data.has('changes_plan')});
      return {message:revise?'수정 요청을 저장했습니다.':'승인을 기록했습니다.'};
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
main.addEventListener('click',async event=>{
  const button=event.target.closest('button');
  if (!button) return;
  if (button.dataset.filter || button.dataset.action==='clear') {
    filter=filter===button.dataset.filter ? null : (button.dataset.filter||null);
    main.innerHTML=dashboard(location.hash==='#projects'?'projects':'dashboard');
    if (filter) main.querySelector(`[data-filter="${filter}"]`)?.focus();
  } else if (button.dataset.action==='create') createProject();
  else if (['rework-prepare','rework-new-prepare','rework-quality-prepare'].includes(button.dataset.action)) {
    modal('AI 재작업 동의 준비',`<p>저장된 피드백을 사용합니다. 지금은 제안만 준비하며 API 호출은 없습니다.</p><label>Google 프로젝트<input name="account_project" value="gen-lang-client-0938732315" required></label><label class="check"><input type="checkbox" name="free" required>키 소속 프로젝트와 결제 미연결·무료 조건 확인</label>`,
      '제안 준비',async data=>{await api(detailApi(detail)+'/'+button.dataset.action,{account_project:data.get('account_project'),confirm_free_account:data.has('free'),...(['rework-new-prepare','rework-quality-prepare'].includes(button.dataset.action)?{previous_job:detail.rework.job}:{})});return {message:'새 동의 제안을 확인하세요.'};});
  }
  else if (['rework-quality-revise','rework-quality-hold'].includes(button.dataset.action)) {
    const revision=button.dataset.action==='rework-quality-revise';
    const report=detail.rework;
    const defaults=report.progress?.quality_report?.feedback||'';
    modal(revision?'AI 관리자 품질 보고 · 수정 지시':'AI 관리자 품질 보고 · 보류',
      `<p>현재 대본과 관리자 검토 근거를 확인한 뒤 지시를 기록합니다. 이 동작은 AI를 호출하지 않습니다.</p>
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
    if (detail.rework.status!=='pending' || detail.rework.proposal?.limits?.max_calls!==7) {
      notice('작업 범위와 호출 상한을 확인할 수 없습니다. 동의하지 않았습니다.',true);
      return;
    }
    modal('새 외부 전송 동의',`<p>이 작업에서 최대 <strong>${h(detail.rework.proposal?.limits?.max_calls??'미설정')}회</strong>의 Gemini 요청을 허용하는 별도 동의입니다. AI 관리자·대본 직원·편집 직원의 하위 작업에는 반복 동의하지 않습니다. 원 목표·대표 피드백·이전 대본/스토리보드·공개 관측을 고정 무료 Gemini에 전송합니다. Google 개선 활용·인적 검토 가능. 청구/쿼터 독립 확인 불가. 새 실행이며 과거 동의를 재사용하지 않습니다.</p><label class="check"><input type="checkbox" name="free" required>프로젝트·키·무료 조건을 확인했습니다.</label><label class="check"><input type="checkbox" name="policy" required>표시된 전송 범위와 무료 데이터 정책에 동의합니다.</label>`,
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
