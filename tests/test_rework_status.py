"""Read-only status projection and Korean cutroom rendering; no provider calls."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from representative_rework import progress_view


class ReworkStatusTests(unittest.TestCase):
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
