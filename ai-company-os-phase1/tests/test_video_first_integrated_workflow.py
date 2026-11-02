"""One video E2E, variable plans, fake provider transport, loopback HTTP only."""
import json
import os
import unittest
from unittest.mock import patch

import ai_safety
import app
from tests.real_ai_fixtures import approved_project
from tests.test_semantic_review_integration import response
from tests import test_mock_workflow_http_integration as http_fixture

GOAL = 'AI 초보자에게 유용한 ChatGPT 활용법을 소개하는 1분 영상 제작'
CRITERION = '60초 대본에 화면 자막과 사실 확인 안내가 포함되어야 한다'
DRAFT = '# 1분 영상 대본\n0~10초: 질문이 막막하신가요?\n10~45초: 목적과 조건을 구체적으로 말해보세요.\n45~60초: 답변은 사실 확인이 필요합니다.'
REVISED = DRAFT + '\n화면 자막: 목적·조건·원하는 형식 / 개인 정보 입력 금지 / 답변 사실 확인'
FINAL = ('# 최종 대본\n' + REVISED + '\n\n## 장면 구성표\n'
         '| 시간 | 화면 |\n|---|---|\n| 0~10초 | 질문 고민 장면 |\n'
         '| 10~45초 | 가상 질문 예시 |\n| 45~60초 | 사실 확인 안내 |\n'
         '\n## 편집 지시서\n큰 자막과 읽기 쉬운 대비를 사용하고 구간별로 전환한다. '
         '음원·화면 소재 권리를 확인한다. 실제 영상 촬영·렌더링·업로드는 미실시.')


class VideoFirstIntegratedWorkflowTests(unittest.TestCase):
    PROJECT_ID = "video-fixture"
    request = http_fixture.MockWorkflowHTTPTests.request
    saved = http_fixture.MockWorkflowHTTPTests.saved
    setUp = http_fixture.MockWorkflowHTTPTests.setUp

    def seed(self, approved=True):
        pass  # Every fictional project is created through HTTP inside the test.

    def ok(self, path, **fields):
        code, _, body = self.request(path, fields)
        self.assertEqual(code, 303, body)

    def approve(self, task):
        self.ok('/task/review', task_id=task, decision='approve')

    def test_video_plan_handoff_revision_and_matching_downloads(self):
        with patch.dict(os.environ, {'AI_ENGINE':'openai_compatible',
                'AI_MODEL':ai_safety.MODEL, 'AI_API_BASE_URL':ai_safety.BASE_URL,
                'AI_REAL_REQUESTS_ENABLED':'1', 'AI_API_KEY':'FICTIONAL_ONLY'}, clear=True), \
             patch('ai_safety.build_opener', side_effect=AssertionError('external network forbidden')):
            for count in (3, 4):
                with self.subTest(stage_count=count):
                    self.complete(count)

    def complete(self, count):
        code, headers, _ = self.request('/create', {'name':'모의 영상 협업', 'goal':GOAL})
        self.assertEqual(code, 303)
        self.PROJECT_ID = headers['Location'].split('/')[-1]
        # Fictional transport permission exists only in temporary test storage.
        app.save_project(approved_project(self.saved()))
        roles = (['영상 구성 기획 담당'] if count == 4 else []) + [
            '초보자 대본 작가', '품질 검토 담당', '편집 연출 담당']
        stages = [{'name':role+' 업무', 'role':role,
                   'inputs':['프로젝트 목표'] if i==0 else ['승인된 선행 결과'],
                   'input_task_ids':[f'TASK-{j:03d}' for j in range(1,i+1)],
                   'output':'최종 대본·장면 구성표·편집 지시서' if i==count-1 else '영상 제작 자료',
                   'risk':'제품 사실과 소재 사용 권리는 별도 확인'} for i,role in enumerate(roles)]
        target=f'TASK-{count-2:03d}'; reviewer=f'TASK-{count-1:03d}'; final=f'TASK-{count:03d}'
        employee_inputs=[]; review_inputs=[]; drafts=[]
        def employee(request, **kwargs):
            text=json.loads(request.data)['messages'][1]['content']
            employee_inputs.append(text)
            self.assertIn(GOAL,text)
            self.assertNotIn('재고',text)
            if '"담당 역할": "영상 구성 기획 담당"' in text:
                return response('영상 구성: 초보자 대상 60초, 민감 정보 사용 금지')
            if '"담당 역할": "초보자 대본 작가"' in text:
                if count==4:self.assertIn('영상 구성: 초보자 대상 60초',text)
                if drafts:
                    self.assertIn('화면 자막을 추가하세요',text)
                    result=REVISED
                else:result=DRAFT
                drafts.append(result)
                return response(result)
            self.assertIn(json.dumps(REVISED,ensure_ascii=False)[1:-1],text)
            self.assertIn('model_claim',text)
            return response(FINAL)
        def review(request, **kwargs):
            data=json.loads(json.loads(request.data)['messages'][1]['content'])
            review_inputs.append(data)
            self.assertEqual(data['criteria'],[CRITERION])
            self.assertIn(GOAL,json.dumps(data,ensure_ascii=False))
            passed='화면 자막' in data['target_result']
            return response(json.dumps({'schema_version':1,'binding':data['binding'],
                'verdict':'pass' if passed else 'changes_needed',
                'checks':[{'criterion':CRITERION,'status':'met' if passed else 'unmet',
                           'evidence':'대본의 자막·사실 확인 안내를 대조함',
                           'risk':'실제 60초 낭독 시간은 미측정',
                           'suggestion':'화면 자막을 추가하세요', 'source':'model_claim'}]},ensure_ascii=False))
        with patch('manager_plan.urlopen',return_value=response(json.dumps({
                'stages':stages,'questions':[],'assumptions':['제품 설명은 별도 사실 확인']},ensure_ascii=False))) as planner, \
             patch('execution_engine.urlopen',side_effect=employee) as executor, \
             patch('semantic_review.urlopen',side_effect=review) as checker:
            self.ok('/manager/plan')
            self.assertIn(GOAL,json.loads(planner.call_args.args[0].data)['messages'][1]['content'])
            self.assertEqual(self.saved()['plan']['status'],'pending_approval')
            self.assertEqual(self.saved()['tasks'],[])
            self.assertEqual(self.request('/task/execute',{'task_id':target})[0],400)
            self.ok('/manager/approve')
            self.assertEqual([t['role'] for t in self.saved()['tasks']],roles)
            self.ok('/semantic/configure',target_task_id=target,reviewer_task_id=reviewer,criteria=CRITERION)
            for i in range(1,count-1):
                task=f'TASK-{i:03d}'
                if i>1:
                    self.assertEqual(self.request('/task/execute',{'task_id':task})[0],400)
                    self.approve(f'TASK-{i-1:03d}')
                self.ok('/task/execute',task_id=task)
            self.assertEqual(self.request('/semantic/review',{})[0],400)
            self.approve(target)
            self.ok('/semantic/review')
            self.assertEqual(self.saved()['semantic']['review']['verdict'],'changes_needed')
            self.assertEqual(self.saved()['tasks'][count-3]['review_status'],'approved')
            self.assertEqual(self.request('/task/execute',{'task_id':target})[0],400)
            self.assertEqual(self.request('/task/execute',{'task_id':final})[0],400)
            self.ok('/semantic/revision-decision',decision='approve',
                    binding_hash=app._digest(app.semantic_binding(self.saved())))
            self.ok('/task/execute',task_id=target)
            self.assertEqual(len(drafts),2)
            self.assertEqual(self.request('/semantic/review',{})[0],400)
            self.approve(target)
            self.ok('/semantic/review')
            self.assertEqual(self.saved()['semantic']['review']['verdict'],'pass')
            self.assertEqual(self.request('/task/execute',{'task_id':final})[0],400)
            self.approve(reviewer)
            self.ok('/task/execute',task_id=final)
            prefix=f'/report/{self.PROJECT_ID}/download/v000001'
            self.assertEqual(self.request(prefix+'.md')[0],409)
            self.assertEqual(self.request(prefix+'.json')[0],409)
            self.approve(final)
            before=app.project_path(self.PROJECT_ID).read_bytes()
            code, headers, markdown=self.request(prefix+'.md')
            self.assertEqual(code,200);self.assertIn('attachment',headers['Content-Disposition'])
            code, headers, serialized=self.request(prefix+'.json')
            self.assertEqual(code,200);self.assertIn('application/json',headers['Content-Type'])
            snapshot=json.loads(serialized)
            self.assertEqual(markdown,app.confirmed_markdown(snapshot))
            self.assertEqual(snapshot,app.load_confirmed_snapshot(self.saved()))
            for task in snapshot['evidence']['tasks']:self.assertIn(task['result'],markdown)
            for heading in ('최종 대본','장면 구성표','편집 지시서'):self.assertIn(heading,markdown)
            self.assertNotIn('FICTIONAL_ONLY',serialized)
            self.assertEqual(before,app.project_path(self.PROJECT_ID).read_bytes())
            self.assertEqual(len(review_inputs),2)
            self.assertEqual(len(self.saved()['real_ai']['attempts']),count+3)
            self.assertEqual(executor.call_count,count)
            self.assertEqual(checker.call_count,2)
