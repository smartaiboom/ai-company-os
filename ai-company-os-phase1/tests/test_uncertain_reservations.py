"""Explicit fictional judgments only; no external network or real data."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

import ai_safety as safety
import app
from uncertain_reservations import ResolutionLedger, fingerprint, SCOPE
from tests.real_ai_fixtures import approved_project
from tests.test_real_ai_safety_budget import Response


class Observer:
    def __init__(self, finished=True): self.finished = finished
    def requests_finished(self): return self.finished


class UncertainReservationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.projects = self.root / 'projects'
        self.projects.mkdir()
        for context in (
            patch('project_budget.KEY_PATH', self.root / '.budget.key'),
            patch.object(app, 'PROJECTS_DIR', self.projects),
            patch.dict(os.environ, {'AI_REAL_REQUESTS_ENABLED':'1',
                                    'AI_ENGINE':'openai_compatible'}, clear=True),
            patch('socket.socket', side_effect=AssertionError('network forbidden')),
            patch('socket.getaddrinfo', side_effect=AssertionError('network forbidden')),
            patch('ai_safety.build_opener', side_effect=AssertionError('network forbidden')),
        ):
            context.start(); self.addCleanup(context.stop)
        self.project = approved_project({'id':'fictional', 'goal':'local fictional goal'})
        self.old = {'id':'old-unknown', 'status':'reserved', 'kind':'plan',
                    'reserved_at':safety.now(), 'input_bytes':1, 'model':safety.MODEL}
        self.project['real_ai']['attempts'] = [copy.deepcopy(self.old)]
        app.save_project(self.project)
        self.ledger = ResolutionLedger(app.project_path('fictional'))
        self.observer = Observer()
        self.transport = Mock(return_value=Response())

    def saved(self): return app.load_project('fictional')

    def decision(self):
        return {'project_id':'fictional', 'goal_hash':safety.goal_hash(self.project['goal']),
                'reservation_id':self.old['id'], 'reservation_hash':fingerprint(self.old),
                'project_path':str(app.project_path('fictional').resolve()),
                'project_hash':fingerprint(self.saved()),
                'decided_at':safety.now(), 'provider_outcome':'unknown',
                'acknowledge_duplicate_risk':True, 'new_requests':1,
                'decision':'allow_one_new_request', 'data_scope':SCOPE}

    def issue(self, **changes):
        app.record_uncertain_decision('fictional', self.ledger,
                                     {**self.decision(), **changes}, self.observer)

    def send(self, project, **changes):
        args = dict(model=safety.MODEL, base_url=safety.BASE_URL,
                    body=json.dumps({'model':safety.MODEL, 'max_tokens':1}).encode(),
                    api_key='', timeout=1, transport=self.transport, kind='plan')
        return safety.request_json(project, **{**args, **changes})

    def run_new(self, **changes):
        with app.uncertain_request_scope('fictional', self.ledger, self.observer) as project:
            return self.send(project, **changes)

    def test_no_judgment_or_context_keeps_default_block(self):
        before = app.project_path('fictional').read_bytes()
        with safety.request_scope(app.save_project), self.assertRaises(ValueError):
            self.send(self.saved())
        with self.assertRaises(ValueError): self.run_new()
        self.issue()
        with safety.request_scope(app.save_project), self.assertRaises(ValueError):
            self.send(self.saved())
        self.assertEqual(before, app.project_path('fictional').read_bytes())
        self.transport.assert_not_called()

    def test_one_new_id_preserves_old_and_consumes_once_across_restart(self):
        self.issue()
        record = self.ledger.record_path.read_bytes()
        self.run_new()
        attempts = self.saved()['real_ai']['attempts']
        self.assertEqual(attempts[0], self.old)
        self.assertEqual(len(attempts), 2)
        self.assertNotEqual(attempts[1]['id'], self.old['id'])
        self.assertEqual(attempts[1]['status'], 'completed')
        self.assertEqual(record, self.ledger.record_path.read_bytes())
        self.ledger = ResolutionLedger(app.project_path('fictional'))
        with self.assertRaises(ValueError): self.run_new()
        with self.assertRaises(ValueError): self.issue()
        self.transport.assert_called_once()

    def test_pending_new_request_blocks_even_during_same_scope(self):
        self.issue()
        def fake(*args, **kwargs):
            self.assertEqual([a['status'] for a in self.saved()['real_ai']['attempts']],
                             ['reserved', 'reserved'])
            with self.assertRaises(ValueError): self.send(self.saved())
            return Response()
        self.transport.side_effect = fake
        self.run_new()
        self.transport.assert_called_once()

    def test_total_budget_and_scope_limit_remain_enforced(self):
        for count, used in ((7, 0), (6, 2)):
            with self.subTest(count=count, used=used):
                location = self.root / ('projects'+str(count))
                location.mkdir()
                with patch.object(app, 'PROJECTS_DIR', location):
                    p=copy.deepcopy(self.project)
                    p['real_ai']['attempts']=[copy.deepcopy(self.old)]+[
                        {'id':str(i),'status':'completed','input_bytes':1}
                        for i in range(count-1)]
                    app.save_project(p)
                    self.ledger=ResolutionLedger(app.project_path('fictional'))
                    self.issue()
                    with self.ledger.request_scope(self.saved(), self.observer), safety.request_scope(app.save_project):
                        safety._scope.get()['used']=used
                        with self.assertRaises(ValueError): self.send(self.saved())
                    self.assertFalse(self.ledger.used_path.exists())
        self.transport.assert_not_called()

    def test_six_prior_attempts_allow_only_seventh(self):
        p=self.saved();p['real_ai']['attempts'] += [
            {'id':str(i),'status':'completed','input_bytes':1} for i in range(5)]
        app.save_project(p);self.issue();self.run_new()
        self.assertEqual(len(self.saved()['real_ai']['attempts']),7)
        with self.assertRaises(ValueError): self.run_new()

    def test_invalid_explicit_judgments_are_rejected(self):
        for changes in ({'acknowledge_duplicate_risk':False},{'new_requests':2},
                        {'provider_outcome':'failed'},{'decision':'old_approval'},
                        {'data_scope':'all_data'},{'decided_at':'2026-11-02T00:00:00+00:00'},
                        {'reservation_hash':'changed'},{'goal_hash':'changed'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.issue(**changes)
        self.assertFalse(self.ledger.record_path.exists())

    def test_tampered_record_signature_stale_goal_and_reservation(self):
        self.issue()
        original=self.ledger.record_path.read_bytes()
        envelope=json.loads(original);envelope['record']['judgment']['new_requests']=2
        self.ledger.record_path.write_text(json.dumps(envelope))
        with self.assertRaises(ValueError): self.run_new()
        self.ledger.record_path.write_bytes(original)
        baseline=app.project_path('fictional').read_bytes()
        for mutation in ('goal','reservation'):
            p=self.saved()
            if mutation=='goal':
                p['goal']='changed';p['real_ai']['consent']['goal_hash']=safety.goal_hash('changed')
            else:p['real_ai']['attempts'][0]['input_bytes']=2
            app.save_project(p)
            with self.assertRaises(ValueError): self.run_new()
            app.project_path('fictional').write_bytes(baseline)
        self.transport.assert_not_called()

    def test_live_or_missing_worker_evidence_blocks_issue_and_use(self):
        self.observer.finished=False
        with self.assertRaises(ValueError): self.issue()
        self.observer.finished=True;self.issue();self.observer.finished=False
        with self.assertRaises(ValueError): self.run_new()
        self.observer=None
        with self.assertRaises(ValueError): self.run_new()
        self.transport.assert_not_called()

    def test_replica_path_cannot_reuse_signed_authority(self):
        self.issue()
        replica=self.root/'copy.json';replica.write_text(json.dumps(self.saved()))
        ledger=ResolutionLedger(replica)
        ledger.root.mkdir(parents=True)
        ledger.record_path.write_bytes(self.ledger.record_path.read_bytes())
        ledger.key_path.write_bytes(self.ledger.key_path.read_bytes())
        with self.assertRaises(ValueError), ledger.request_scope(self.saved(),self.observer): pass
        with self.assertRaises(ValueError):
            ledger.record_user_decision(self.saved(),self.decision(),self.observer)
        with self.assertRaises(ValueError), app.uncertain_request_scope('fictional',ledger,self.observer): pass
        self.transport.assert_not_called()

    def test_concurrent_ledger_and_application_mutations_are_blocked(self):
        self.issue()
        entered=threading.Event();release=threading.Event();errors=[]
        def fake(*args,**kwargs):
            entered.set()
            if not release.wait(2):raise AssertionError('release missing')
            return Response()
        self.transport.side_effect=fake
        def first():
            try:self.run_new()
            except Exception as exc:errors.append(type(exc).__name__)
        worker=threading.Thread(target=first);worker.start()
        try:
            self.assertTrue(entered.wait(1))
            with self.assertRaises(ValueError):self.run_new()
            # A separately loaded authority object cannot bypass the file lock.
            other=ResolutionLedger(app.project_path('fictional'))
            with self.assertRaises(ValueError), other.request_scope(self.saved(),self.observer):pass
        finally:release.set();worker.join(2)
        self.assertFalse(worker.is_alive());self.assertEqual(errors,[])
        self.transport.assert_called_once()

    def test_failed_transport_or_project_write_never_restores_permission(self):
        self.issue();self.transport.side_effect=TimeoutError('private')
        with self.assertRaises(RuntimeError):self.run_new()
        self.assertEqual(self.saved()['real_ai']['attempts'][0],self.old)
        self.assertEqual(self.saved()['real_ai']['attempts'][1]['status'],'failed')
        with self.assertRaises(ValueError):self.run_new()
        self.transport.assert_called_once()

    def test_storage_failure_after_consumption_is_fail_closed(self):
        self.issue()
        with self.ledger.request_scope(self.saved(),self.observer), \
             safety.request_scope(Mock(side_effect=OSError('fictional storage error'))):
            with self.assertRaises(OSError):self.send(self.saved())
        self.assertTrue(self.ledger.used_path.exists())
        self.assertEqual(self.saved()['real_ai']['attempts'],[self.old])
        with self.assertRaises(ValueError):self.run_new()
        self.transport.assert_not_called()

    def test_new_unknown_added_after_decision_is_not_covered(self):
        self.issue()
        p=self.saved()
        p['real_ai']['attempts'].append({'id':'another-unknown', 'status':'reserved', 'input_bytes':1})
        app.save_project(p)
        with self.assertRaises(ValueError):self.run_new()
        self.assertFalse(self.ledger.used_path.exists())
        self.transport.assert_not_called()

    def test_unconsumed_restart_needs_new_live_observation(self):
        self.issue()
        self.ledger=ResolutionLedger(app.project_path('fictional'))
        self.observer=Observer(False)
        with self.assertRaises(ValueError):self.run_new()
        self.observer=Observer(True)
        self.run_new()
        self.transport.assert_called_once()

    def test_authority_lock_blocks_a_separate_process(self):
        self.issue()
        program = """
import sys
from uncertain_reservations import ResolutionLedger
try:
    with ResolutionLedger(sys.argv[1])._lock():
        sys.exit(1)
except ValueError:
    sys.exit(0)
"""
        with self.ledger._lock():
            result=subprocess.run([sys.executable, '-B', '-c', program,
                                   str(app.project_path('fictional'))],
                                  capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'')

    def test_model_host_and_consent_guards_still_apply(self):
        self.issue()
        for changes in ({'model':'paid'}, {'base_url':'https://invalid.example'}):
            with self.assertRaises(ValueError):self.run_new(**changes)
        p=self.saved();p['real_ai']['consent']['approved']=False;app.save_project(p)
        with self.assertRaises(ValueError):self.run_new()
        self.assertFalse(self.ledger.used_path.exists())
        self.transport.assert_not_called()
