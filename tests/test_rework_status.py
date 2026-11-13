"""Read-only status projection and Korean cutroom rendering; no provider calls."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from representative_rework import progress_view


class ReworkStatusTests(unittest.TestCase):
    def test_legacy_review_is_labeled_unvalidated_in_cutroom(self):
        source=Path('companies/video/studio/studio.js').read_text()
        script=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(0,'utf8');
const ctx={h:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
           facts:rows=>JSON.stringify(rows),time:v=>v};
vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('function reworkPanel('),source.indexOf('function budgetSetupPanel')),ctx);
const quality_report={decision:'stop',reason:'legacy_unvalidated_review',
  source:'legacy_failure_diagnostic_not_manager_review',
  evidence:{review_status:'unvalidated',http_status:200},
  failed_checks:{goal_fit:'historical_goal_review_failed'},
  feedback:'대표가 저장된 대본을 직접 검토하세요'};
const p={rework:{status:'stopped',job:'legacy-job',attempts:3,feedback:'기존 요청',error:'rework_goal_not_met',
  progress:{title:'대표 판단 필요 · 과거 검토 실패 보고',current:'대본 검토',actor:'AI 관리자',
   cards:[],message:'검증되지 않은 응답',next_action:'대표 확인',
   counts:{attempts:3,transport_started:3,http_ok:3,server_validated:2,failed:0},
   ledger:[],quality_report},quality_script:'저장된 가상 대본',quality_report_hash:'test-hash',
  settings:{ready:false,missing:['disabled']},recovery:null,history:[]}};
const html=ctx.reworkPanel(p);
assert(html.includes('과거 검토 실패 진단 · 대표 지시 필요'));
assert(html.includes('검증에 실패'));
assert(html.includes('data-action="rework-quality-revise"'));
assert(html.includes('data-action="rework-quality-hold"'));
assert(!html.includes('data-action="rework-run"'));
assert(!html.includes('data-action="rework-quality-prepare"'));
"""
        result=subprocess.run(['node','-e',script],input=source,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_ceo_quality_report_cutroom_render_offline(self):
        """Execute the actual panel renderer against a synthetic report, no files altered."""
        source=Path('companies/video/studio/studio.js').read_text()
        script=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(0,'utf8');
const ctx={
  h:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  time:v=>v,facts:rows=>JSON.stringify(rows)
};
vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('function reworkPanel('),source.indexOf('function budgetSetupPanel')),ctx);
const report={decision:'stop',reason:'revision_limit_reached',
  failed_checks:{goal_fit:'not_met',subject_story:'not_met'},
  evidence:{goal_fit:'대본의 예시'},feedback:'이야기 중심으로 고치세요'};
const progress={title:'대표 판단 필요 · AI 품질 검토 보고',current:'대본 검토',actor:'AI 관리자',
  cards:[],message:'목표 불일치',next_action:'대표에게 보고',counts:{
    attempts:3,transport_started:3,http_ok:3,server_validated:2,failed:0},
  ledger:[],quality_report:report};
const base={rework:{status:'stopped',progress,job:'fixture-job',
  quality_report_hash:'fixture-hash',quality_script:'<img src=x onerror=alert(1)>',
  feedback:'대표 피드백',attempts:3,history:[],settings:{ready:true},proposal:null}};
const html=ctx.reworkPanel(base);
for(const label of ['AI 관리자 품질 보고','수정 지시 남기기','판단 보류','goal_fit','subject_story'])
  assert(html.includes(label),'missing '+label);
assert(html.includes('data-action="rework-quality-revise"'));
assert(html.includes('data-action="rework-quality-hold"'));
assert(!html.includes('<img src=x onerror=alert(1)>'),'unescaped writer source');
assert(html.includes('&lt;img src=x onerror=alert(1)&gt;'));
assert(!html.includes('data-action="rework-quality-prepare"'),'prepare before decision');
assert(!html.includes('data-action="rework-run"'),'never automatically run');
const revised=JSON.parse(JSON.stringify(base));
revised.rework.quality_decision={action:'request_revision',feedback:'게임 이야기 수정'};
const ready=ctx.reworkPanel(revised);
assert(ready.includes('data-action="rework-quality-prepare"'),'explicit new job preparation');
assert(!ready.includes('data-action="rework-quality-revise"'),'duplicate write forbidden');
assert(!ready.includes('data-action="rework-run"'),'consent required');
const held=JSON.parse(JSON.stringify(base));
held.rework.quality_decision={action:'hold',feedback:''};
const holdHtml=ctx.reworkPanel(held);
assert(!holdHtml.includes('data-action="rework-quality-prepare"'),'hold never prepares');
assert(!holdHtml.includes('data-action="rework-quality-revise"'));
"""
        result=subprocess.run(['node','-e',script],input=source,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)


    def test_stopped_running_completed_and_korean_ui_without_execution(self):
        with patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')),patch('socket.socket.connect',side_effect=AssertionError('network forbidden')):
            job=dict(status='stopped',reason_code='invalid_dependencies',phase='plan',plan=None,assignments=[],
                real_ai=dict(consent=dict(approved=True),attempts=[dict(phase='plan',task_id=None,status='completed',
                    http_status=200,role_result_status='json_parsed',transport_started_at='2026-11-12T16:06:16+09:00',
                    response_received_at='2026-11-12T16:06:22+09:00',response_hash='fixture-response')]),
                events=[dict(at='2026-11-12T16:06:22+09:00',event='system_safety_stop')])
            state=dict(status='stopped',error='invalid_dependencies')
            original=deepcopy(job);stopped=progress_view(job,state)
            self.assertEqual(stopped['current'],'재기획');self.assertEqual(stopped['actor'],'AI 관리자')
            self.assertIn('새 대본은 아직 생성되지 않았습니다',stopped['message'])
            self.assertEqual(stopped['counts'],dict(attempts=1,transport_started=1,http_ok=1,server_validated=0,failed=0))
            self.assertEqual(stopped['cards'][1]['state'],'중단')
            self.assertEqual(stopped['updated_at'],'2026-11-12T16:06:22+09:00')
            self.assertEqual(job,original)
            job['status']='running';job['reason_code']=None;job['plan']={'tasks':[]}
            job['assignments']=[dict(id='w',role='writer',state='awaiting_ai_review',versions=[{}]),
                                dict(id='e',role='editor',state='pending',versions=[])]
            job['real_ai']['attempts'].append(dict(task_id='w',phase='review',status='reserved'))
            running=progress_view(job,dict(status='running'))
            self.assertEqual(running['current'],'대본 검토');self.assertEqual(running['cards'][3]['state'],'진행 중')
            job['status']='needs_user_review'
            for t in job['assignments']:t.update(state='accepted_by_ai_manager',versions=[{}])
            completed=progress_view(job,dict(status='completed'))
            self.assertEqual(completed['title'],'새 기획 대표 승인 대기')
            self.assertTrue(all(c['state']=='완료' for c in completed['cards']))
            source=Path('companies/video/studio/studio.js').read_text()
            self.assertIn('이전 미션 기획 보존 · 참고용 (최신 재작업 아님)',source)
            script="""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const data=JSON.parse(fs.readFileSync(0,'utf8')),s=data.source;
const ctx={h:v=>String(v??''),time:v=>v,facts:rows=>JSON.stringify(rows)};
vm.createContext(ctx);vm.runInContext(s.slice(s.indexOf('function reworkPanel('),s.indexOf('function budgetSetupPanel')),ctx);
for(const [status,progress] of Object.entries(data.views)){
 const html=ctx.reworkPanel({rework:{status,progress,error:status==='stopped'?'invalid_dependencies':null,attempts:1,feedback:'fixture'}});
 assert(html.includes(progress.title));assert(html.includes('상태 새로고침 · 조회만'));
 assert(!html.includes('data-action="rework-run"'));assert(!html.includes('data-action="rework-recover"'));
 if(status==='stopped'){assert(!html.split('<details>')[0].includes('invalid_dependencies'));assert(html.includes('담당 개발 점검'));}
}
"""
            result=subprocess.run(['node','-e',script],input=json.dumps(dict(source=source,views=dict(stopped=stopped,running=running,completed=completed))),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
