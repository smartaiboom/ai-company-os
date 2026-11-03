"""Offline result approval and downstream input preparation, no external calls."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

import app
from execution_engine import OpenAICompatibleExecutionEngine
from tests import test_video_plan_approval_preparation as fixture
from tests import test_concurrent_execution_safety as handlers


class TaskResultApprovalPreparationTests(unittest.TestCase):
    setUp = fixture.PlanApprovalPreparationTests.setUp
    approve = fixture.PlanApprovalPreparationTests.approve
    post = handlers.ConcurrentExecutionSafetyTests.post

    def seed_result(self):
        self.approve()
        with app.project_mutation_lock(self.p['id']), patch.object(app, 'get_execution_engine_name', return_value='mock'):
            app.execute_project_task(self.p['id'], 'TASK-001', executor=lambda *a, **k:'가상 조사 결과: 출처 미확인, 구체적인 요청을 사용한다.')
        return app.load_project(self.p['id'])

    def test_approval_preserves_result_budget_and_blocks_duplicate(self):
        before = self.seed_result()
        task = before['tasks'][1]
        with self.assertRaises(ValueError):
            app._validate_task_predecessors(task, before['tasks'], 1)
        with patch('execution_engine.urlopen') as transport, patch('app.execute_task') as execute:
            status, _ = self.post('/task/review', project_id=self.p['id'], decision='approve')
            self.assertEqual(status,303)
            approved = app.load_project(self.p['id'])
            self.assertEqual(approved['tasks'][0]['review_status'],'approved')
            self.assertEqual(approved['tasks'][0]['result'],before['tasks'][0]['result'])
            self.assertTrue(approved['tasks'][0]['reviewed_at'].endswith('+09:00'))
            for key in ['real_ai','plan','plan_revisions']:
                self.assertEqual(approved[key],before[key])
            self.assertEqual(approved['tasks'][1:],before['tasks'][1:])
            self.assertEqual(app._validate_task_predecessors(approved['tasks'][1],approved['tasks'],1),['TASK-001'])
            raw=app.project_path(self.p['id']).read_bytes()
            self.assertEqual(self.post('/task/review',project_id=self.p['id'],decision='approve')[0],400)
            self.assertEqual(app.project_path(self.p['id']).read_bytes(),raw)
            transport.assert_not_called();execute.assert_not_called()

    def test_approved_result_enters_writer_payload_without_transport_or_budget_change(self):
        self.seed_result()
        self.assertEqual(self.post('/task/review',project_id=self.p['id'],decision='approve')[0],303)
        p=app.load_project(self.p['id']);before=deepcopy(p)
        ids=app._validate_task_predecessors(p['tasks'][1],p['tasks'],1)
        previous=app._build_previous_results(p['tasks'][1],p['tasks'],1,ids)
        self.assertEqual(previous[0]['result'],p['tasks'][0]['result'])
        with patch('execution_engine.urlopen') as transport, patch('execution_engine.request_json',return_value={'choices':[{'message':{'content':'가상 대본'}}]}) as capture:
            engine=OpenAICompatibleExecutionEngine(base_url='https://openrouter.ai/api/v1',api_key='FICTIONAL',model='openrouter/free')
            engine.execute(p,p['tasks'][1],previous_results=previous)
            payload=json.loads(capture.call_args.kwargs['body'])
            text=payload['messages'][1]['content']
            self.assertIn(p['tasks'][0]['result'],json.loads(text[text.index('{'):text.rindex('}')+1])['이전 작업 결과'][0]['result'])
            self.assertIn('미검증',text)
            transport.assert_not_called()
        self.assertEqual(p,before)
        self.assertEqual(app.load_project(p['id']),before)
