"""Offline approval and dependency checks with fictional temporary projects."""
import io
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlencode

import app
from manager_plan import STARTER_STAGES, validate_stages
from tests.real_ai_fixtures import approved_project


class PlanApprovalPreparationTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(app, 'PROJECTS_DIR', Path(directory)))
        self.enterContext(patch('ai_safety.build_opener', side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('app.build_manager_plan', side_effect=AssertionError('planning forbidden')))
        stages = deepcopy(STARTER_STAGES)
        stages[0]['input_task_ids'] = []
        stages[2]['input_task_ids'] = ['TASK-002']
        stages[3]['input_task_ids'] = ['TASK-002', 'TASK-003']
        self.p = approved_project({'id': 'approval-preparation', 'goal': '가상 목표',
            'tasks': [], 'history': [], 'plan': {'goal': '가상 목표',
            'status': 'pending_approval', 'stages': validate_stages(stages)},
            'plan_revisions': [{'plan': {'status': 'pending_approval', 'source': 'fixture'}}]})
        self.p['real_ai']['attempts'] = [{'id': 'used', 'status': 'completed', 'input_bytes': 1}]
        app.save_project(self.p)

    def approve(self):
        handler = app.Handler.__new__(app.Handler)
        body = urlencode({'id': self.p['id']}).encode()
        handler.path = '/manager/approve'
        handler.headers = {'Content-Length': str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        with patch.object(app.Handler, 'redirect') as redirect, patch.object(app.Handler, 'send_html') as html:
            handler.do_POST()
        return redirect, html

    def test_approval_creates_four_waiting_tasks_preserving_original_and_budget(self):
        redirect, html = self.approve()
        redirect.assert_called_once(); html.assert_not_called()
        p = app.load_project(self.p['id'])
        self.assertEqual(p['plan']['status'], 'approved')
        self.assertTrue(p['plan']['approved_at'].endswith('+09:00'))
        self.assertEqual(p['plan_revisions'], self.p['plan_revisions'])
        self.assertEqual(p['real_ai'], self.p['real_ai'])
        self.assertEqual(len(p['tasks']), 4)
        self.assertEqual([t['status'] for t in p['tasks']], ['대기'] * 4)
        self.assertEqual([t['role'] for t in p['tasks']], [s['role'] for s in self.p['plan']['stages']])
        self.assertEqual([t['input_task_ids'] for t in p['tasks']],
                         [[], ['TASK-001'], ['TASK-002'], ['TASK-002', 'TASK-003']])
        self.assertEqual(app._validate_task_predecessors(p['tasks'][0], p['tasks'], 0), [])
        self.assertEqual(sum(h['event'] == 'plan_approved' for h in p['history']), 1)
        before = app.project_path(p['id']).read_bytes()
        redirect, html = self.approve()
        redirect.assert_not_called(); self.assertEqual(html.call_args.args[1], 400)
        self.assertEqual(app.project_path(p['id']).read_bytes(), before)

    def test_later_tasks_cannot_run_with_unfinished_predecessors(self):
        self.approve()
        executor = Mock(side_effect=AssertionError('executor forbidden'))
        before = app.project_path(self.p['id']).read_bytes()
        for tid in ['TASK-002', 'TASK-003', 'TASK-004']:
            with self.subTest(task=tid), self.assertRaises(ValueError):
                app.execute_project_task(self.p['id'], tid, executor=executor)
        executor.assert_not_called()
        self.assertEqual(app.project_path(self.p['id']).read_bytes(), before)

    def test_completed_but_unapproved_predecessors_cannot_run(self):
        self.approve()
        p = app.load_project(self.p['id'])
        for t in p['tasks']:
            t.update(status='완료', result='가상 결과', review_status='pending')
        app.save_project(p)
        before = app.project_path(p['id']).read_bytes()
        executor = Mock(side_effect=AssertionError('executor forbidden'))
        for tid in ['TASK-002', 'TASK-003', 'TASK-004']:
            with self.subTest(task=tid), self.assertRaises(ValueError):
                app.execute_project_task(p['id'], tid, executor=executor)
        executor.assert_not_called()
        self.assertEqual(app.project_path(p['id']).read_bytes(), before)
