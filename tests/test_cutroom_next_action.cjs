const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const node = {addEventListener() {}};
const document = {querySelectorAll: () => [], querySelector: () => node};
const source = fs.readFileSync(path.join(__dirname,'../companies/video/studio/studio.js'),'utf8');
const ui = vm.runInNewContext(source.replace(/\nroute\(\);\s*$/, '') +
  '\n({nextWork, productionNext, projectPage})', {document, window: node});
const clip = {scene_id:'scene-1',source:'operator_clip',request:'test'};
const initial = {status:'unprepared',key_ready:false,clips:[],voices:{}};
const available = {...initial,key_ready:true};
const planned = {...available,status:'waiting_assets',plan:{scenes:[clip],voice:{tool:'gemini_scene'}}};
const flow = {plan_versions:[], video_versions:[], render_attempts:[]};
const controls = new Map();
const controlSource = {querySelector: selector => controls.get(selector)};
const project = {stage:'video_revision',flow,autonomous_production:initial};

function hasAction(work, action, disabled = false) {
  assert.match(work.buttons, new RegExp(`data-action="${action}"`));
  assert.equal(/\bdisabled\b/.test(work.buttons), disabled);
}

hasAction(ui.nextWork(project,controlSource),'production-plan-prepare',true);
assert.match(ui.productionNext(initial).reason,/GEMINI_PRODUCTION_PROJECT_API_KEY/);
assert.doesNotMatch(ui.productionNext(initial).reason,/GEMINI_PRODUCTION_TTS_ENABLED/);
hasAction(ui.productionNext(available),'production-plan-prepare');
hasAction(ui.productionNext({...available,status:'prepared',review_hash:'review'}),'production-plan-consent');
hasAction(ui.productionNext({...available,status:'approved',manager_enabled:false}),'production-plan-run',true);
hasAction(ui.productionNext({...available,status:'approved',manager_enabled:true,expires_at:'2000-01-01T00:00:00Z'}),'production-plan-run',true);
assert.match(ui.productionNext({...available,status:'stopped',manager_attempt:'reserved'}).message,/미확정/);
hasAction(ui.productionNext(planned),'production-voice-prepare');
hasAction(ui.productionNext(planned,'clip-scene-1'),'production-clip-import');
const sourcePending = {...planned,source_assessment:{status:'unprepared',available_count:0,ready:[]}};
hasAction(ui.productionNext(sourcePending,'sources'),'production-source-prepare');
const sourceApproved = {...sourcePending,source_assessment:{status:'approved',ready:[]}};
hasAction(ui.productionNext({...sourceApproved,manager_enabled:true},'sources'),'production-source-run');
hasAction(ui.productionNext({...sourcePending,source_assessment:{status:'completed',ready:['scene-1']}},'sources'),'production-source-import');
assert.match(ui.productionNext({...sourcePending,source_assessment:{status:'blocked',reason:'권리 목록 검증 필요'}},'sources').message,/권리 목록/);

const withClip = {...planned,clips:['scene-1']};
hasAction(ui.productionNext(withClip),'production-voice-prepare');
const voice = {review_hash:'voice'};
hasAction(ui.productionNext({...withClip,voices:{'scene-1':voice}}),'production-voice-consent');
const voiceApproved = {...withClip,voices:{'scene-1':{...voice,consent:true}}};
const blockedVoice = ui.productionNext(voiceApproved);
hasAction(blockedVoice,'production-voice-run',true);
assert.match(blockedVoice.reason,/GEMINI_PRODUCTION_TTS_ENABLED/);
hasAction(ui.productionNext({...voiceApproved,tts_enabled:true}),'production-voice-run');
hasAction(ui.productionNext({...planned,render_ready:true}),'production-render');
assert.match(ui.productionNext({...planned,render_attempt:'failed'}).message,/합성 실패/);

const batchReady = {...planned,key_ready:true,voice_batch:{status:'available',scenes:['scene-2','scene-3']}};
const offer={status:'available',proposal:{units:[{id:'voice:scene-2'}]}};
hasAction(ui.productionNext({...batchReady,owner_policy:offer}),'production-policy-approve');
hasAction(ui.productionNext({...batchReady,owner_policy:{status:'active',expires_at:'future',can_run:true}}),'production-policy-run');
assert.doesNotMatch(source,/name="\$\{name\}" type="number" min="1" max="1000000000"/);
hasAction(ui.productionNext({...batchReady,voice_batch:{status:'prepared',review:{}}}),'production-batch-consent');
hasAction(ui.productionNext({...batchReady,voice_batch:{status:'approved',review:{max_requests:2}}},'batch'),'production-batch-run',true);
const timed = {...planned,timeline:{status:'unprepared'}};
hasAction(ui.productionNext(timed,'timeline'),'production-timeline-prepare');
hasAction(ui.productionNext({...timed,timeline:{status:'review'}},'timeline'),'production-timeline-approve');

const assetsBlocked = {...planned,asset_execution:{status:'waiting_rights',missing:1,local:0,official:0},
  owner_policy:{status:'active',used:1,expires_at:'future',proposal:{units:[{}]}}};
const discover = {...assetsBlocked,media_discovery:{status:'available',proposal:{max_searches:4,fallback_max_calls:1}}};
hasAction(ui.productionNext(discover),'production-discovery-approve');
hasAction(ui.productionNext({...discover,media_discovery:{status:'active'}}),'production-discovery-run');
hasAction(ui.productionNext({...discover,media_discovery:{status:'review'}}),'production-discovery-rights');
assert.match(ui.productionNext({...discover,media_discovery:{status:'empty'}}).message,/후보가 없습니다/);
const adaptive = ui.productionNext({...assetsBlocked, media_discovery:{status:'empty'},
  adaptive_discovery:{status:'available',proposal:{max_searches:8,fallback_max_calls:0}}});
hasAction(adaptive,'production-discovery-approve');
assert.match(adaptive.buttons,/대안 영상·이미지/);
const blockedAssetWork = ui.productionNext(assetsBlocked);
hasAction(blockedAssetWork,'production-assets-approve',true);
assert.match(blockedAssetWork.reason,/공식 직접 다운로드/);
hasAction(ui.productionNext({...assetsBlocked,asset_execution:{status:'available',proposal:{max_downloads:1}}}),
  'production-assets-approve');
hasAction(ui.productionNext({...assetsBlocked,asset_execution:{status:'active',expires_at:'future'}}),
  'production-policy-run');

const review = ui.nextWork({stage:'awaiting_video_approval',flow:{...flow,
  video_versions:[{version:1,render_receipt:{visual_scope:'local_procedural_cards_no_game_footage'}}]}},controlSource);
assert.match(review.buttons,/video:request_revision/);
assert.doesNotMatch(review.buttons,/video:approve/);
const planReview = ui.nextWork({stage:'awaiting_plan_approval',flow:{...flow,plan_versions:[{version:2}]}},controlSource);
assert.match(planReview.buttons,/plan:approve/);
assert.match(planReview.buttons,/plan:request_revision/);
controls.set('[data-action="rework-consent"]', {outerHTML:'<button data-action="rework-consent">동의</button>'});
hasAction(ui.nextWork({stage:'plan_revision',flow,rework:{status:'pending'}},controlSource),'rework-consent');
controls.set('[data-action="mission-run"]', {outerHTML:'<button data-action="mission-run">실행</button>'});
hasAction(ui.nextWork({stage:'research_planning',flow,mission:{can_run:true}},controlSource),'mission-run');
hasAction(ui.nextWork({stage:'research_planning',flow,mission:{running:true}},controlSource),'refresh');
assert.match(ui.nextWork({stage:'completed',flow},controlSource).message,/최종 대표 승인/);

if (process.argv[2]) {
  const live = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const page = ui.projectPage(live);
  assert.ok(page.indexOf('id="next-work"') < page.indexOf('id="production-detail"'));
  assert.ok(page.indexOf('id="production-detail"') < page.indexOf('id="video-panel"'));
  if (live.autonomous_production?.status==='waiting_assets') {
    const work = ui.nextWork(live,controlSource);
    if (live.autonomous_production.voice_batch?.status==='available') {
      if (!live.autonomous_production.voices['scene-1'].listening) {
        hasAction(ui.nextWork(live,controlSource,'listen-scene-1'),'production-listen');
      } else {
        assert.match(page,/대표 청취 의견/);
      }
      assert.equal(live.autonomous_production.voices['scene-1'].duration_seconds,3.68);
    } else if (!live.autonomous_production.asset_execution?.status) {
      hasAction(work,'production-voice-prepare');
    }
    if (live.autonomous_production.asset_execution?.status==='waiting_rights') {
      if ([live.autonomous_production.media_discovery?.status,live.autonomous_production.adaptive_discovery?.status].includes('available')) {
        hasAction(work,'production-discovery-approve');
        assert.match(page,/Commons 영상·이미지 탐색/);
      } else {
        hasAction(work,'production-assets-approve',true);
      }
      assert.match(page,/권리 확인 소스 인수·편집/);
    } else if (live.autonomous_production.owner_policy?.status==='available') {
      hasAction(work,'production-policy-approve');
      assert.match(page,/개인 운영 설정/);
    } else {
      hasAction(ui.nextWork(live,controlSource,'sources'),'production-source-prepare');
    }
    assert.match(page,/관리자 제작 계획 원문/);
  } else {
    hasAction(ui.nextWork(live,controlSource),'production-plan-prepare',true);
  }
}
console.log('Cutroom next-action scenarios passed');
