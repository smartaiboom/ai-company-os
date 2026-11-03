"""Offline owner acceptance, original result approval and execution gates."""
import hashlib
from copy import deepcopy
from unittest.mock import Mock, patch
import app
import manager_decision as md
import accept_review_task002_tool as tool
from tests.test_real_manager_review_once import RealReviewOnceTests as Base


class AcceptReviewTask002Tests(Base):
    def setUp(self):
        Base.setUp(self)
        self.enterContext(patch('project_budget.KEY_PATH', app.PROJECTS_DIR / '.budget.key'))

    def prepare_accept(self):
        self.prepare_real_review()
        self.enterContext(patch.object(tool, 'PROJECT_ID', self.p['id']))
        with patch('manager_decision.urlopen', side_effect=self.transport_review('proceed',
            mutate=lambda d: d['payload'].update(next_task_ids=['TASK-003','TASK-004']))):
            proposal = self.run_review()
        return self.saved(), proposal

    def accept(self, p, proposal, user_approval=tool.USER_APPROVAL, result_hash=None):
        return tool.run_once(p['id'], proposal['id'], md.digest(p),
            result_hash or hashlib.sha256(p['tasks'][1]['result'].encode()).hexdigest(), user_approval=user_approval)

    def test_accept_then_approve_preserves_results_and_blocks_execution(self):
        original, proposal = self.prepare_accept()
        with patch('manager_decision.urlopen') as manager, patch('execution_engine.urlopen') as employee:
            p = self.accept(original, proposal)
            manager.assert_not_called(); employee.assert_not_called()
        self.assertEqual(p['tasks'][1]['review_status'],'approved')
        self.assertEqual(p['tasks'][1]['reviewed_by'],'사용자')
        self.assertTrue(p['tasks'][1]['reviewed_at'].endswith('+09:00'))
        for key in ('result','result_revision','status'):
            self.assertEqual(p['tasks'][1][key],original['tasks'][1][key])
        self.assertEqual(p['tasks'][0],original['tasks'][0])
        self.assertEqual(p['tasks'][2:],original['tasks'][2:])
        self.assertEqual(p['real_ai'],original['real_ai'])
        self.assertEqual(p['manager_decisions']['proposals'][0],original['manager_decisions']['proposals'][0])
        self.assertEqual(p['manager_decisions']['proposals'][-1]['status'],'accepted_for_review')
        self.assertTrue(app.manager_decision_view(p['id'])[-1]['stale'])
        self.assertTrue(md.decision_input(p,'TASK-002'))
        self.assertTrue(md.require_proceed(p,'TASK-002',['TASK-001']))
        with self.assertRaises(ValueError): md.require_proceed(p,'TASK-003',['TASK-002'])
        executor = Mock()
        with self.assertRaises(ValueError): app.execute_project_task(p['id'],'TASK-003',executor=executor)
        executor.assert_not_called()
        events = [h['event'] for h in p['history'][len(original['history']):]]
        self.assertEqual(events,['manager_user_decision','task_review_approved','review_proceed_and_result_user_approved'])
        with self.assertRaises(ValueError): self.accept(p,proposal)
        self.assertEqual(self.saved(),p)

    def test_wrong_order_stales_review(self):
        p, proposal = self.prepare_accept()
        with app.project_mutation_lock(p['id']): app.review_task_result(p['id'],'TASK-002','approve')
        self.assertTrue(app.manager_decision_view(p['id'])[-1]['stale'])
        with self.assertRaises(ValueError): app.respond_manager_decision(p['id'],proposal['id'],md.digest(proposal),'approve')
        self.assertEqual(self.saved()['manager_decisions']['proposals'][-1]['status'],'pending_user_decision')

    def test_wrong_approval_hash_and_stale_project_block_before_acceptance(self):
        original, proposal = self.prepare_accept()
        for mode in ('text','result_hash','project'):
            with self.subTest(mode=mode):
                app.save_project(deepcopy(original))
                if mode == 'project':
                    p = self.saved(); p['user_preferences']['focus'] = '경합'; app.save_project(p)
                with self.assertRaises(ValueError):
                    self.accept(original,proposal,user_approval='다른 승인' if mode=='text' else tool.USER_APPROVAL,
                                result_hash='bad' if mode=='result_hash' else None)
                self.assertEqual(self.saved()['manager_decisions']['proposals'][-1]['status'],'pending_user_decision')

    def test_race_during_acceptance_and_after_acceptance_preserved(self):
        original, proposal = self.prepare_accept()
        respond = app.respond_manager_decision
        for mode in ('before','after'):
            with self.subTest(mode=mode):
                app.save_project(deepcopy(original))
                def mutate(*args, **kwargs):
                    if mode == 'after': respond(*args, **kwargs)
                    p = self.saved(); p['user_preferences']['focus'] = '경합 보존'; app.save_project(p)
                    if mode == 'before': respond(*args, **kwargs)
                with patch('app.respond_manager_decision',side_effect=mutate):
                    with self.assertRaises(ValueError): self.accept(original,proposal)
                p = self.saved()
                self.assertEqual(p['tasks'][1]['review_status'],'pending')
                self.assertEqual(p['user_preferences']['focus'],'경합 보존')
                self.assertEqual(p['real_ai'],original['real_ai'])
                self.assertEqual(p['manager_decisions']['proposals'][-1]['status'],
                    'accepted_for_review' if mode=='after' else 'pending_user_decision')
