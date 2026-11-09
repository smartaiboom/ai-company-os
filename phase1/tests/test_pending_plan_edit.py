"""Offline draft edits preserve source plans, approvals and consumed budgets."""
import json
import tempfile
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import app
from manager_plan import STARTER_STAGES
from tests.real_ai_fixtures import approved_project


class PendingPlanEditTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch('ai_safety.build_opener', side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('manager_plan.urlopen', side_effect=AssertionError('network forbidden')))
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(app, 'PROJECTS_DIR', Path(directory)))
        self.p = approved_project({'id': 'draft-test', 'goal': '가상 목표', 'tasks': [], 'history': []})
        self.p['real_ai']['attempts'] = [{'id': 'used', 'status': 'completed', 'input_bytes': 1}]
        self.p['plan'] = {'goal': '가상 목표', 'status': 'pending_approval',
                          'stages': deepcopy(STARTER_STAGES), 'questions': ['확인 질문']}
        app.save_project(self.p)
        self.original = deepcopy(self.p)
        self.stages = deepcopy(STARTER_STAGES)
        self.stages[0]['input_task_ids'] = []
        self.stages[2]['role'] = '품질 검토 담당'
        self.stages[2]['input_task_ids'] = ['TASK-002']
        self.stages[3]['input_task_ids'] = ['TASK-002', 'TASK-003']

    def edit(self, stages=None, expected=None):
        app.edit_pending_plan(self.p['id'], stages if stages is not None else self.stages,
                              '초안 보완', expected or app._digest(self.p['plan']))

    def test_preserves_source_budget_and_reload_with_valid_contract(self):
        self.edit()
        saved = app.load_project(self.p['id'])
        self.assertEqual(saved['plan_revisions'][0]['plan'], self.original['plan'])
        self.assertEqual(saved['real_ai'], self.original['real_ai'])
        self.assertEqual(saved['plan']['status'], 'pending_approval')
        self.assertEqual(saved['tasks'], [])
        self.assertEqual(saved['plan']['questions'], ['확인 질문'])
        tasks = [dict(s, id=f'TASK-{i:03d}') for i, s in enumerate(saved['plan']['stages'], 1)]
        self.assertEqual(app.semantic_tasks({'tasks': tasks, 'semantic': {
            'target_task_id': 'TASK-002', 'reviewer_task_id': 'TASK-003'}}), (1, 2))
        self.assertEqual(json.loads(app.project_path(self.p['id']).read_text()), saved)
        script = ('import json; from pathlib import Path; import app; '
                  'app.PROJECTS_DIR=Path(__import__("sys").argv[1]); '
                  'print(json.dumps(app.load_project("draft-test")))')
        restarted = subprocess.run([sys.executable, '-B', '-c', script,
                                    str(app.PROJECTS_DIR)], check=True,
                                   capture_output=True, text=True)
        self.assertEqual(json.loads(restarted.stdout), saved)
        with self.assertRaises(ValueError):
            app.execute_project_task(self.p['id'], 'TASK-001')
        self.assertEqual(app.load_project(self.p['id']), saved)

    def test_invalid_dependency_preserves_file(self):
        before = app.project_path(self.p['id']).read_bytes()
        self.stages[0]['input_task_ids'] = ['TASK-004']
        with self.assertRaises(ValueError): self.edit()
        self.assertEqual(app.project_path(self.p['id']).read_bytes(), before)

    def test_stale_edit_preserves_source(self):
        self.edit()
        before = app.project_path(self.p['id']).read_bytes()
        with self.assertRaises(ValueError): self.edit()
        self.assertEqual(app.project_path(self.p['id']).read_bytes(), before)

    def test_approved_or_started_plan_rejected(self):
        for field, value in [('status', 'approved'), ('approved_at', '2026-11-03T09:00:00+09:00')]:
            p = deepcopy(self.original); p['plan'][field] = value; app.save_project(p)
            before = app.project_path(p['id']).read_bytes()
            with self.assertRaises(ValueError): self.edit(expected=app._digest(p['plan']))
            self.assertEqual(app.project_path(p['id']).read_bytes(), before)
        p = deepcopy(self.original); p['tasks'] = [{'id': 'TASK-001'}]; app.save_project(p)
        with self.assertRaises(ValueError): self.edit()

    def test_second_edit_keeps_first_original(self):
        self.edit()
        first = app.load_project(self.p['id'])
        self.edit(expected=app._digest(first['plan']))
        saved = app.load_project(self.p['id'])
        self.assertEqual(saved['plan_revisions'][0]['plan'], self.original['plan'])
        self.assertEqual(saved['plan_revisions'][1]['plan'], first['plan'])
