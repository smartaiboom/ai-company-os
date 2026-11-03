"""Approved-result next decision: fictional state, fake keys, blocked external network."""
import json
import subprocess
import sys
from copy import deepcopy
from unittest.mock import Mock, patch
import app
import manager_decision as md
import real_manager_approved_task002_tool as tool
from tests.test_real_manager_review_once import RealReviewOnceTests as Fixture
from tests.test_real_ai_safety_budget import Response


class ApprovedNextTests(Fixture):
    def setUp(self):
        Fixture.setUp(self)
        self.enterContext(patch('project_budget.KEY_PATH', app.PROJECTS_DIR / '.budget.key'))

    def prepare_next(self):
        self.prepare_real_review()
        self.enterContext(patch.object(tool,'PROJECT_ID',self.p['id']))
        with patch('manager_decision.urlopen',side_effect=self.transport_review('proceed')):
            review = self.run_review()
        app.respond_manager_decision(self.p['id'],review['id'],md.digest(review),'approve')
        with app.project_mutation_lock(self.p['id']):
            app.review_task_result(self.p['id'],'TASK-002','approve')
        self.guard = app.PROJECTS_DIR / 'approved-next.guard'
        return self.saved()

    def next_once(self, confirmed=True, task_id='TASK-002', purpose=tool.PURPOSE):
        return tool.run_once(self.p['id'],task_id,md.digest(self.saved()),authorization_id='f'*32,
            guard_path=self.guard,user_confirmed=confirmed,purpose=purpose)

    def transport_next(self, action='proceed', mutate=None, finish='stop'):
        def fake(request, **kwargs):
            p = self.saved(); ledger = p['real_ai']['attempts']
            self.assertEqual(len(ledger),8); self.assertEqual(ledger[-1]['status'],'reserved')
            body = json.loads(request.data); data = json.loads(body['messages'][1]['content'])
            self.assertIn('approved_result_data',data)
            for field in ('purpose','employee_result_data','success_criteria_draft','binding'): self.assertNotIn(field,data)
            self.assertEqual(data['approved_result_data']['content'],p['tasks'][1]['result'])
            self.assertEqual(json.loads(self.guard.with_suffix('.observation.json').read_text())['transport_calls'],1)
            value = self.value(app._manager_decision_input(p,'TASK-002'),action)
            if mutate: mutate(value)
            return Response({'choices':[{'finish_reason':finish,'message':{'content':json.dumps(value,ensure_ascii=False)}}]})
        return fake

    def test_next_four_actions_once_and_old_review_stale_preserved(self):
        original = self.prepare_next()
        for action in sorted(md.ACTIONS):
            with self.subTest(action=action):
                app.save_project(deepcopy(original));self.guard=app.PROJECTS_DIR/(action+'.next.guard')
                with patch('manager_decision.urlopen',side_effect=self.transport_next(action)) as sender:
                    proposal = self.next_once()
                    with self.assertRaises(ValueError): self.next_once()
                    sender.assert_called_once()
                p = self.saved()
                self.assertEqual(p['tasks'],original['tasks'])
                self.assertEqual(p['real_ai']['attempts'][:7],original['real_ai']['attempts'])
                self.assertEqual(p['manager_decisions']['proposals'][:2],original['manager_decisions']['proposals'])
                self.assertNotIn('purpose',proposal)
                self.assertNotIn('purpose',proposal['decision']['binding'])
                view = app.manager_decision_view(p['id'])
                self.assertTrue(view[1]['stale']); self.assertEqual(view[1]['status'],'accepted_for_review')
                self.assertFalse(view[-1]['stale']);self.assertEqual(view[-1]['status'],'pending_user_decision')
                code='import sys,json,app;from pathlib import Path;app.PROJECTS_DIR=Path(sys.argv[1]);print(json.dumps(app.manager_decision_view(sys.argv[2])))'
                read=subprocess.run([sys.executable,'-B','-c',code,str(app.PROJECTS_DIR),p['id']],capture_output=True,text=True,check=True)
                self.assertEqual(json.loads(read.stdout)[-1]['status'],'pending_user_decision')
                self.assertFalse(json.loads(read.stdout)[-1]['stale'])
                executor=Mock()
                with self.assertRaises(ValueError): app.execute_project_task(p['id'],'TASK-003',executor=executor)
                executor.assert_not_called()
                self.guard.unlink()  # Only fictional guard; ledger/audit must still block.
                with patch('manager_decision.urlopen') as sender:
                    with self.assertRaises(ValueError): self.next_once()
                    sender.assert_not_called()
                self.assertEqual(self.old_guard.read_text(),'기존 guard 보존')
                self.assertEqual(self.other.read_text(),'{"reservation":"보존"}')

    def test_next_preconditions(self):
        original = self.prepare_next()
        for mode in ('confirmation','task','purpose','project','guard','reserved','budget','ledger','pending','audit','stale'):
            with self.subTest(mode=mode):
                p=deepcopy(original);self.guard=app.PROJECTS_DIR/(mode+'.next.guard')
                if mode=='reserved':p['real_ai']['attempts'][-1]['status']='reserved'
                if mode=='budget':p['real_ai']['limit']=7
                if mode=='ledger':p['real_ai']['attempts'][0]['kind']='other'
                if mode=='pending':p['tasks'][1]['review_status']='pending'
                if mode=='audit':p['history'].append({'event':'real_manager_approved_next_once_authorized'})
                if mode=='guard':self.guard.write_text('이미 사용')
                app.save_project(p)
                with patch('manager_decision.urlopen') as sender:
                    with self.assertRaises((ValueError,FileExistsError)):
                        if mode=='project':
                            with patch.object(tool,'PROJECT_ID','other'):self.next_once()
                        elif mode=='stale':tool.run_once(p['id'],'TASK-002','stale',authorization_id='f'*32,guard_path=self.guard,user_confirmed=True)
                        else:self.next_once(mode!='confirmation','TASK-001' if mode=='task' else 'TASK-002','other' if mode=='purpose' else tool.PURPOSE)
                    sender.assert_not_called()

    def test_next_races_response_timeout_no_retry(self):
        original=self.prepare_next()
        for mode in ('result','approval','plan','linked_task','ledger','payload','finish','timeout','failure'):
            with self.subTest(mode=mode):
                app.save_project(deepcopy(original));self.guard=app.PROJECTS_DIR/(mode+'.next.guard')
                def mutate(value):
                    if mode=='payload':value['payload']={'bad':'불허'}
                    if mode in ('result','approval','plan','linked_task','ledger'):
                        p=self.saved()
                        if mode=='result':p['tasks'][1]['result']+='경합'
                        if mode=='approval':p['tasks'][1]['reviewed_at']='변경'
                        if mode=='plan':p['plan']['version']=99
                        if mode=='linked_task':p['tasks'][2]['name']='변경'
                        if mode=='ledger':p['real_ai']['attempts'][-1]['input_bytes']+=1
                        app.save_project(p)
                fake=TimeoutError('PRIVATE') if mode=='timeout' else OSError('PRIVATE') if mode=='failure' else self.transport_next(mutate=mutate,finish='length' if mode=='finish' else 'stop')
                with patch('manager_decision.urlopen',side_effect=fake) as sender:
                    with self.assertRaises(RuntimeError):self.next_once()
                    with self.assertRaises(ValueError):self.next_once()
                    sender.assert_called_once()
                p=self.saved();self.assertEqual(len(p['manager_decisions']['proposals']),2)
                self.assertEqual(p['real_ai']['attempts'][:7],original['real_ai']['attempts'])
                self.assertNotIn('PRIVATE',json.dumps(p))

    def test_next_reservation_and_proposal_save_failure_consumes_approval(self):
        original=self.prepare_next();save=app.save_project
        for mode in ('reservation','proposal'):
            save(deepcopy(original));self.guard=app.PROJECTS_DIR/(mode+'.next.guard');failed=False
            def fail(p):
                nonlocal failed
                if not failed and ((mode=='reservation' and len(p['real_ai']['attempts'])==8 and p['real_ai']['attempts'][-1]['status']=='reserved') or (mode=='proposal' and len(p['manager_decisions']['proposals'])==3)):
                    failed=True;raise OSError('PRIVATE')
                return save(p)
            with patch('app.save_project',side_effect=fail),patch('manager_decision.urlopen',side_effect=self.transport_next()) as sender:
                with self.assertRaises(RuntimeError):self.next_once()
                self.assertEqual(sender.call_count,0 if mode=='reservation' else 1)
            self.guard.unlink()
            with patch('manager_decision.urlopen') as sender:
                with self.assertRaises(ValueError):self.next_once()
                sender.assert_not_called()

    def test_next_lock_blocks_before_guard(self):
        original=self.prepare_next()
        with app.project_mutation_lock(original['id']),patch('manager_decision.urlopen') as sender:
            with self.assertRaises(ValueError):self.next_once()
            sender.assert_not_called()
        self.assertEqual(self.saved(),original)
        self.assertFalse(self.guard.exists())
