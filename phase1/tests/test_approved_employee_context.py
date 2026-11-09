"""Offline transport validates the exact allowed employee context."""
import json
import os
import unittest
from copy import deepcopy
from unittest.mock import patch

import ai_safety
from execution_engine import OpenAICompatibleExecutionEngine, approved_task_context
from tests.real_ai_fixtures import approved_project
from tests.test_real_ai_safety_budget import Response


class ApprovedEmployeeContextTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {'AI_ENGINE':'openai_compatible',
            'AI_MODEL':ai_safety.MODEL, 'AI_API_BASE_URL':ai_safety.BASE_URL,
            'AI_REAL_REQUESTS_ENABLED':'1', 'AI_API_KEY':'FICTIONAL'}, clear=True))
        self.enterContext(patch('ai_safety.build_opener',side_effect=AssertionError('network forbidden')))
        self.task={'id':'TASK-001','name':'가상 조사','role':'조사 담당','inputs':['승인 입력'],
                   'input_task_ids':[],'output':'조사 자료','risk':'출처 미검증 표시'}
        self.p=approved_project({'id':'context-fixture','goal':'가상 목표',
            'plan':{'status':'approved','stages':[dict(self.task, private='STAGE_SECRET'),
                   {'name':'UNRELATED_STAGE'}],'feedback':'PLAN_SECRET'},
            'user_preferences':{'focus':'초보자 기본','video_style':'화면 설명','source':'PREFERENCE_SECRET'},
            'success_criteria_draft':{'approved':False,'items':['DRAFT_SECRET']},
            'other_project':'OTHER_PROJECT_SECRET'})

    def test_fake_transport_receives_only_approved_relevant_context(self):
        before=deepcopy(self.p)
        persisted=[]
        def transport(request, **kwargs):
            self.assertEqual(len(persisted),1)
            self.assertEqual(persisted[0]['real_ai']['attempts'][0]['status'],'reserved')
            payload=json.loads(request.data)
            text=payload['messages'][1]['content']
            for value in ['가상 목표','가상 조사','승인 입력','출처 미검증 표시','초보자 기본','화면 설명','해당 업무의 승인 계획','미검증']:
                self.assertIn(value,text)
            for value in ['STAGE_SECRET','UNRELATED_STAGE','PLAN_SECRET','PREFERENCE_SECRET','DRAFT_SECRET','OTHER_PROJECT_SECRET']:
                self.assertNotIn(value,text)
            return Response()
        with patch('execution_engine.urlopen',side_effect=transport) as sender:
            with ai_safety.request_scope(lambda p:persisted.append(deepcopy(p))):
                result=OpenAICompatibleExecutionEngine().execute(self.p,self.task)
        self.assertIn('모의 제공자 결과',result)
        sender.assert_called_once()
        self.assertEqual(len(self.p['real_ai']['attempts']),1)
        self.assertEqual(self.p['real_ai']['attempts'][0]['status'],'completed')
        self.assertEqual(self.p['plan'],before['plan'])
        self.assertEqual(self.p['user_preferences'],before['user_preferences'])

    def test_unapproved_plan_or_unknown_task_has_no_added_context(self):
        self.p['plan']['status']='pending_approval'
        self.assertEqual(approved_task_context(self.p,self.task),{})
        self.p['plan']['status']='approved'
        self.assertEqual(approved_task_context(self.p,dict(self.task,id='TASK-999')),{})
