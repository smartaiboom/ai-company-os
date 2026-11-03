"""Generic offline vertical slice: real decision handlers, fake AI transports."""
import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import app
import ai_safety
import manager_decision as md
import workflow_guidance
from tests import test_manager_decision_loop as fixture
from tests.test_real_ai_safety_budget import Response


class AutonomousWorkflowTests(unittest.TestCase):
    setUp=fixture.ManagerDecisionLoopTests.setUp
    seed=fixture.ManagerDecisionLoopTests.seed
    seed_result=fixture.ManagerDecisionLoopTests.seed_result
    approve=fixture.ManagerDecisionLoopTests.approve
    post=fixture.ManagerDecisionLoopTests.post
    saved=fixture.ManagerDecisionLoopTests.saved

    def prepare_flow(self, alternate=False):
        self.seed(goal='지역 도서관 이용 안내 개선' if alternate else '신입 직원 업무 안내 개선')
        p=self.saved()
        self.ids=['TASK-101','TASK-211','TASK-321','TASK-431'] if alternate else [t['id'] for t in p['tasks']]
        mapping={t['id']:new for t,new in zip(p['tasks'],self.ids)}
        for task in p['tasks']:
            task['id']=mapping[task['id']]
            task['input_task_ids']=[mapping[i] for i in task['input_task_ids']]
        for stage in p['plan']['stages']:stage['input_task_ids']=[mapping[i] for i in stage['input_task_ids']]
        for h in p['history']:
            if 'details' in h:
                for old,new in mapping.items():h['details']=h['details'].replace(old+':',new+':')
        p['real_ai']['limit']=20;p['real_ai']['consent']['goal_hash']=ai_safety.goal_hash(p['goal'])
        p['success_criteria_draft']={'approved':False,'items':['미확인 주장을 구분한다']}
        app.save_project(p)
        self.enterContext(patch('project_budget.KEY_PATH',app.PROJECTS_DIR/'.budget.key'))
        self.enterContext(patch.object(app,'ARTIFACTS_DIR',app.PROJECTS_DIR/'artifacts'))
        self.enterContext(patch.dict(os.environ,{'AI_ENGINE':'openai_compatible','AI_MODEL':'openrouter/free',
            'AI_API_BASE_URL':'https://openrouter.ai/api/v1','AI_API_KEY':'FICTIONAL','AI_REAL_REQUESTS_ENABLED':'1'},clear=True))
        self.employee_inputs=[];self.review_inputs=[];self.verdict='pass';self.fail_review=False
        self.enterContext(patch('execution_engine.urlopen',side_effect=self.employee_transport))
        self.enterContext(patch('semantic_review.urlopen',side_effect=self.review_transport))
        self.enterContext(patch('ai_safety.build_opener',side_effect=AssertionError('no external network')))
        self.criteria=['담당자와 실행 절차가 구체적으로 있다','외부 확인이 불가능한 주장을 미확인으로 구분한다']
        return self.saved()

    def ok(self,path,**fields):
        status,body=self.post(path,project_id=self.p['id'],**fields)
        self.assertEqual(status,303,body)

    def approve_result(self,task_id):self.ok('/task/review',task_id=task_id,decision='approve')

    def proposal(self,task_id,action='proceed'):
        def generate(context):
            payload={
                'proceed':{'next_task_ids':[t['task_id'] for t in context['data']['next_tasks']], 'guidance':'승인된 자료를 연결하고 미확인 사실을 구분해 주세요.'},
                'ask_user':{'question':'기존 자료를 유지하고 품질 검토에서 불확실성을 다룰까요?','why_needed':'사용자 방향을 확인합니다.','options':['자료 유지','수정 검토']},
                'request_revision':{'task_id':task_id,'reason':'내용 보완이 필요합니다.','scope':'대상 자료만 검토해 주세요.'},
                'propose_plan_change':{'changes':[{'operation':'modify','task_id':task_id,'description':'업무 정의 변경을 제안합니다.'}]},
            }[action]
            value={'action':action,'rationale':'목표와 자료를 대조했습니다.','evidence':'승인 결과와 사용자 답변을 확인했습니다.',
                   'next_step':'사용자 결정을 기다립니다.','uncertainty':'출처를 독립 확인하지 않았습니다.','payload':payload}
            response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value,ensure_ascii=False)}}]}
            return json.dumps(md.validate_provider_response(response,context),ensure_ascii=False)
        return app.propose_manager_decision(self.p['id'],task_id,md.MockDecisionProvider(generate))

    def decide(self,proposal,response='approve',answer=''):
        view=next(v for v in app.manager_decision_view(self.p['id']) if v['id']==proposal['id'])
        self.ok('/manager/decision',proposal_id=view['id'],expected_hash=view['expected_hash'],
            expected_project_hash=md.digest(self.saved()),response=response,answer=answer)

    def employee_transport(self,request,**kwargs):
        body=json.loads(request.data);text=body['messages'][1]['content'];data=json.loads(text[text.index('{'):text.rindex('}')+1])
        self.employee_inputs.append(data)
        result='업무 안내 자료\n담당자가 절차를 확인합니다. 외부 출처는 미확인입니다.'
        return Response({'choices':[{'finish_reason':'stop','message':{'content':result}}]})

    def review_transport(self,request,**kwargs):
        data=json.loads(json.loads(request.data)['messages'][1]['content']);self.review_inputs.append(data)
        if self.fail_review:raise TimeoutError('PRIVATE')
        statuses=['unknown','met'] if self.verdict=='inconclusive' else ['unmet','met'] if self.verdict=='changes_needed' else ['met','met']
        review={'schema_version':1,'binding':data['binding'],'verdict':self.verdict,'checks':[
            {'criterion':criterion,'status':status,'evidence':'자료의 절차·불확실성 표기를 대조했습니다.',
             'risk':'외부 출처는 독립 확인하지 못했습니다.','suggestion':'불확실한 사실은 미확인으로 남기세요.','source':'model_claim'}
            for criterion,status in zip(self.criteria,statuses)]}
        return Response({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(review,ensure_ascii=False)}}]})

    def prepare_review(self,alternate=False):
        self.prepare_flow(alternate)
        first=self.proposal(self.ids[0]);self.decide(first)
        self.ok('/task/execute',task_id=self.ids[1]);self.approve_result(self.ids[1])
        self.assertNotIn('approved_quality_criteria',md.decision_input(self.saved(),self.ids[1])['data'])
        question=self.proposal(self.ids[1],'ask_user')
        html=workflow_guidance.render(self.saved());self.assertIn('/manager/decision',html)
        self.decide(question,'answer','기존 자료를 유지하고 검토에서 미확인 사실과 실행 가능성을 확인하세요. 실제 호출 승인은 별도입니다.')
        self.assertEqual(self.saved()['manager_decisions']['proposals'][-1]['status'],'answered')
        before=deepcopy(self.saved());app.semantic_controls(before);self.assertEqual(before,self.saved())
        self.ok('/semantic/configure',target_task_id=self.ids[1],reviewer_task_id=self.ids[2],criteria='\n'.join(self.criteria))
        return self.saved()

    def finish_flow(self):
        self.approve_result(self.ids[2])
        reviewer=self.proposal(self.ids[2]);self.decide(reviewer)
        self.ok('/task/execute',task_id=self.ids[3])
        final=self.saved()['tasks'][-1]
        self.assertEqual(final['review_status'],'pending')
        data=self.employee_inputs[-1]
        previous=data['이전 작업 결과']
        for tid in self.ids[1:3]:self.assertTrue(any(v['task_id']==tid for v in previous))
        self.assertTrue(any('미확인' in v['result'] for v in previous))
        self.approve_result(self.ids[3])
        p=self.saved();snapshot=app.load_confirmed_snapshot(p)
        self.assertEqual(p['final_report']['status'],'confirmed')
        self.assertIn(p['goal'],app.confirmed_markdown(snapshot))
        self.assertNotIn('FICTIONAL',json.dumps(snapshot))
        self.assertTrue(snapshot['evidence']['manager_decisions']['answers'])
        self.assertTrue((app.ARTIFACTS_DIR/p['id']/'final_reports'/'v000001.json').is_file())
        return p

    def test_generic_success_answer_to_review_to_final_human_confirmation(self):
        self.prepare_review(alternate=True)
        before=self.saved()
        status,_=self.post('/semantic/review',project_id=self.p['id'])
        self.assertEqual(status,400)
        self.assertEqual(self.saved(),before)  # Missing manager approval must not reserve a semantic slot.
        proceed=self.proposal(self.ids[1]);self.decide(proceed)
        self.assertIn('기존 자료를 유지',md.decision_input(self.saved(),self.ids[1])['data']['user_answers'][-1]['answer'])
        self.assertEqual(md.decision_input(self.saved(),self.ids[1])['data']['approved_quality_criteria'],self.criteria)
        self.ok('/semantic/review')
        self.assertEqual(self.saved()['semantic']['review']['verdict'],'pass')
        self.assertTrue(any('기존 자료를 유지' in v['result'] for v in self.review_inputs[-1]['approved_predecessors']))
        self.assertTrue(all(c['source']=='model_claim' for c in self.saved()['semantic']['review']['checks']))
        self.assertEqual(self.saved()['tasks'][2]['review_status'],'pending')
        self.finish_flow()

    def test_changes_needed_human_revision_reapproval_reassessment_then_final(self):
        self.prepare_review();self.decide(self.proposal(self.ids[1]))
        self.verdict='changes_needed';self.ok('/semantic/review')
        p=self.saved();original=p['tasks'][1]['result']
        self.assertEqual(self.post('/task/review',project_id=p['id'],task_id=self.ids[2],decision='approve')[0],400)
        self.ok('/semantic/revision-decision',decision='approve',binding_hash=app._digest(app.semantic_binding(p)))
        self.assertEqual(self.saved()['tasks'][1]['result'],original)
        self.ok('/task/execute',task_id=self.ids[1]);self.approve_result(self.ids[1])
        self.assertEqual(self.saved()['tasks'][1]['result_revision'],2)
        self.decide(self.proposal(self.ids[1]));self.verdict='pass';self.ok('/semantic/review')
        self.assertEqual(len(self.saved()['semantic']['reviews']),2)
        self.finish_flow()

    def test_inconclusive_and_timeout_stop_without_downstream_execution(self):
        self.prepare_review();self.decide(self.proposal(self.ids[1]));original=deepcopy(self.saved())
        self.verdict='inconclusive';self.ok('/semantic/review')
        self.assertEqual(self.post('/task/review',project_id=self.p['id'],task_id=self.ids[2],decision='approve')[0],400)
        self.assertEqual(self.post('/task/execute',project_id=self.p['id'],task_id=self.ids[3])[0],400)
        self.assertFalse(self.saved()['tasks'][3].get('result'))
        self.assertEqual(self.saved()['semantic']['review']['checks'][0]['status'],'unknown')
        app.save_project(original);self.fail_review=True
        self.assertEqual(self.post('/semantic/review',project_id=self.p['id'])[0],400)
        used=len(self.saved()['real_ai']['attempts'])
        self.assertEqual(self.post('/semantic/review',project_id=self.p['id'])[0],400)
        self.assertEqual(len(self.saved()['real_ai']['attempts']),used)
        self.assertFalse(self.saved()['tasks'][3].get('result'))
        self.assertNotIn('PRIVATE',json.dumps(self.saved()))

    def test_decision_handler_stale_missing_token_and_nonproceed_are_not_execution(self):
        self.prepare_flow();first=self.proposal(self.ids[0]);before=self.saved()
        self.assertEqual(self.post('/manager/decision',project_id=self.p['id'],proposal_id=first['id'],expected_hash=md.digest(first),response='approve')[0],400)
        self.assertEqual(self.saved(),before)
        self.decide(first);self.ok('/task/execute',task_id=self.ids[1]);self.approve_result(self.ids[1])
        p=self.proposal(self.ids[1],'request_revision');self.decide(p)
        self.assertEqual(self.saved()['manager_decisions']['proposals'][-1]['status'],'accepted_for_review')
        self.assertEqual(self.saved()['tasks'][1]['review_status'],'approved')
        self.assertEqual(self.post('/task/execute',project_id=self.p['id'],task_id=self.ids[2])[0],400)
        p=self.saved();html=workflow_guidance.render(p)
        self.assertIn('자동 수정',html);self.assertEqual(p,self.saved())

    def test_plan_change_rejection_failure_guidance_and_escaping(self):
        self.prepare_flow();self.decide(self.proposal(self.ids[0]))
        self.ok('/task/execute',task_id=self.ids[1]);self.approve_result(self.ids[1])
        original=deepcopy(self.saved()['plan'])
        proposal=self.proposal(self.ids[1],'propose_plan_change');self.decide(proposal)
        self.assertEqual(self.saved()['plan'],original)
        self.assertEqual(self.saved()['manager_decisions']['proposals'][-1]['status'],'accepted_for_review')
        p=self.saved();p['history'].append({'event':'real_manager_stopped','stage':'provider_response','error_code':'finish_reason'})
        p['tasks'][2]['name']='<script>unsafe()</script>';app.save_project(p)
        original=deepcopy(self.saved());html=workflow_guidance.render(original)
        self.assertIn('finish_reason',html);self.assertIn('별도 승인',html)
        self.assertNotIn('<script>unsafe()',html);self.assertIn('&lt;script&gt;',html)
        self.assertEqual(original,self.saved())

    def test_project_page_and_explicit_handler_tokens(self):
        self.prepare_flow();self.decide(self.proposal(self.ids[0]))
        self.ok('/task/execute',task_id=self.ids[1]);self.approve_result(self.ids[1])
        question=self.proposal(self.ids[1],'ask_user')
        body=[];handler=app.Handler.__new__(app.Handler);handler.send_html=lambda content,status=200:body.append(content)
        handler.project_detail(self.p['id'])
        self.assertIn('/manager/decision',body[0]);self.assertIn('expected_project_hash',body[0])
        self.assertIn('미승인 초안',body[0]);self.assertIn('답변만 저장',body[0])
        p=self.saved();q=deepcopy(p);q['user_preferences']['focus']='경합 보존';app.save_project(q)
        status,_=self.post('/manager/decision',project_id=p['id'],proposal_id=question['id'],expected_hash=md.digest(question),
            expected_project_hash=md.digest(p),response='answer',answer='기존 자료 유지')
        self.assertEqual(status,400);self.assertEqual(self.saved(),q)

    def test_user_answer_input_allowlist_and_criteria_preparation_never_authorize(self):
        self.prepare_review(alternate=True);p=self.saved();original=deepcopy(p)
        self.assertIn('품질 검토 담당',json.dumps(p,ensure_ascii=False))
        answers=md.user_answer_inputs(p,[self.ids[1]])
        self.assertEqual(len(answers),1)
        value=json.loads(answers[0]['result']);self.assertFalse(value['execution_authorized']);self.assertFalse(value['criteria_approved'])
        self.assertEqual(md.user_answer_inputs(p,['TASK-999']),[])
        p['manager_decisions']['answers'][0]['private']='PRIVATE'
        self.assertNotIn('PRIVATE',json.dumps(md.user_answer_inputs(p,[self.ids[1]])))
        p['manager_decisions']['proposals'][-1]['decision']['binding']['project_id']='other'
        self.assertEqual(md.user_answer_inputs(p,[self.ids[1]]),[])
        self.assertEqual(self.saved(),original)

    def test_answer_change_invalidates_quality_judgment_and_archive_keeps_decisions(self):
        self.prepare_review();self.decide(self.proposal(self.ids[1]));self.ok('/semantic/review')
        p=self.saved();self.assertIn('user_answers_hash',p['semantic']['review']['binding'])
        p['manager_decisions']['answers'][-1]['answer']='사용자 방향이 바뀌었습니다.';app.save_project(p)
        with self.assertRaises(ValueError):app.validate_semantic_pass(self.saved())
        self.assertEqual(self.post('/task/review',project_id=p['id'],task_id=self.ids[2],decision='approve')[0],400)
        self.assertFalse(self.saved()['tasks'][3].get('result'))
