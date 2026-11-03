"""Model-only JSON boundary: fictional fixtures and blocked external network."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

import app
import manager_decision as md
from tests import test_real_manager_decision as fixture
from tests.test_real_ai_safety_budget import Response

MODEL_FIELDS = {'action', 'rationale', 'evidence', 'next_step', 'uncertainty', 'payload'}


class ModelOutputContractTests(unittest.TestCase):
    setUp = fixture.RealManagerDecisionTests.setUp
    seed = fixture.RealManagerDecisionTests.seed
    seed_result = fixture.RealManagerDecisionTests.seed_result
    post = fixture.RealManagerDecisionTests.post
    approve = fixture.RealManagerDecisionTests.approve
    saved = fixture.RealManagerDecisionTests.saved
    prepare = fixture.RealManagerDecisionTests.prepare
    run_real = fixture.RealManagerDecisionTests.run_real
    decision = fixture.RealManagerDecisionTests.decision

    def model_value(self, context, action='proceed'):
        return {k: v for k, v in self.decision(context, action).items() if k in MODEL_FIELDS}

    def test_minimal_model_json_four_actions_and_owned_binding(self):
        self.prepare()
        p = self.saved()
        context = md.decision_input(p, 'TASK-001')
        for action in sorted(md.ACTIONS):
            with self.subTest(action=action):
                value = self.model_value(context, action)
                original = deepcopy(value)
                result = md.validate_provider_response({'choices': [{'finish_reason': 'stop',
                    'message': {'content': json.dumps(value, ensure_ascii=False)}}]}, context)
                self.assertEqual(value, original)
                self.assertEqual(result['binding'], context['binding'])
                self.assertEqual(result['schema_version'], 1)
                self.assertEqual(result['source'], 'model_claim')
                self.assertEqual({k: result[k] for k in MODEL_FIELDS}, value)
                self.assertEqual(md.parse_and_validate(json.dumps(result, ensure_ascii=False), context), result)
                result['binding']['project_id'] = 'tampered'
                self.assertEqual(context['binding']['project_id'], p['id'])

    def test_invalid_model_json_stops_once_without_leaking(self):
        self.prepare(); original = self.saved()
        cases = {
            'unknown_action': ('invalid_action', lambda d: d.update(action='PRIVATE')),
            'numeric_action': ('invalid_action', lambda d: d.update(action=1)),
            'missing': ('missing_field', lambda d: d.pop('evidence')),
            'binding': ('unexpected_field', lambda d: d.update(binding={'project_id': 'PRIVATE'})),
            'matching_binding': ('unexpected_field', lambda d: d.update(binding=md.decision_input(self.saved(), 'TASK-001')['binding'])),
            'full_stored': ('unexpected_field', lambda d: d.update(schema_version=1, source='model_claim', binding=md.decision_input(self.saved(), 'TASK-001')['binding'])),
            'project': ('unexpected_field', lambda d: d.update(project_id='PRIVATE')),
            'schema': ('unexpected_field', lambda d: d.update(schema_version=1)),
            'source': ('unexpected_field', lambda d: d.update(source='model_claim')),
            'approved': ('unexpected_field', lambda d: d.update(approved=True)),
            'text': ('invalid_text', lambda d: d.update(rationale='PRIVATE')),
            'empty': ('invalid_text', lambda d: d.update(uncertainty='')),
            'numeric_text': ('invalid_text', lambda d: d.update(evidence=1)),
            'long_text': ('invalid_text', lambda d: d.update(next_step='가'*1501)),
            'payload': ('invalid_payload', lambda d: d.update(payload=[])),
            'payload_extra': ('invalid_payload', lambda d: d['payload'].update(PRIVATE=True)),
            'target': ('invalid_target', lambda d: d['payload'].update(next_task_ids=['TASK-999'])),
        }
        for mode, (code, mutate) in cases.items():
            with self.subTest(mode=mode):
                app.save_project(deepcopy(original))
                def fake(request, **kwargs):
                    data = json.loads(json.loads(request.data)['messages'][1]['content'])
                    self.assertNotIn('binding', data)
                    value = self.model_value(md.decision_input(self.saved(), 'TASK-001'))
                    mutate(value)
                    return Response({'choices': [{'finish_reason': 'stop', 'message': {
                        'content': json.dumps(value, ensure_ascii=False)}}]})
                with patch('manager_decision.urlopen', side_effect=fake) as transport:
                    with self.assertRaises(RuntimeError) as error: self.run_real()
                    with self.assertRaises(ValueError): self.run_real()
                    transport.assert_called_once()
                p = self.saved()
                self.assertEqual(p['history'][-1]['stage'], 'decision_contract')
                self.assertEqual(p['history'][-1]['error_code'], code)
                self.assertEqual(p['manager_decisions']['proposals'], [])
                self.assertEqual(len(p['real_ai']['attempts']), len(original['real_ai']['attempts'])+1)
                self.assertEqual(p['real_ai']['attempts'][-1]['status'], 'completed')
                self.assertEqual(p['tasks'], original['tasks'])
                self.assertNotIn('PRIVATE', json.dumps(p)+str(error.exception))

    def test_action_specific_invalid_targets_and_text(self):
        self.prepare(); context = md.decision_input(self.saved(), 'TASK-001')
        cases = [
            ('ask_user', {'question': 'PRIVATE', 'why_needed': '필요합니다', 'options': []}, 'invalid_text'),
            ('ask_user', {'question': '질문입니다', 'why_needed': '필요합니다', 'options': [1]}, 'invalid_text'),
            ('request_revision', {'task_id': 'TASK-002', 'reason': '이유입니다', 'scope': '범위입니다'}, 'invalid_target'),
            ('proceed', {'next_task_ids': ['TASK-001'], 'guidance': '지침입니다'}, 'invalid_target'),
            ('proceed', {'next_task_ids': ['TASK-002', 'TASK-002'], 'guidance': '지침입니다'}, 'invalid_target'),
            ('propose_plan_change', {'changes': [{'operation': 'modify', 'task_id': 'TASK-999', 'description': '제안입니다'}]}, 'invalid_target'),
            ('propose_plan_change', {'changes': [{'operation': 'add', 'task_id': 'TASK-001', 'description': '제안입니다'}]}, 'invalid_target'),
            ('propose_plan_change', {'changes': [{'operation': 'delete', 'task_id': 'TASK-001', 'description': '제안입니다'}]}, 'invalid_target'),
        ]
        for action, payload, code in cases:
            with self.subTest(action=action, payload=payload):
                value = self.model_value(context, action); value['payload'] = payload
                with self.assertRaises(md.DecisionDiagnosticError) as error:
                    md.validate_provider_response({'choices': [{'finish_reason': 'stop',
                        'message': {'content': json.dumps(value, ensure_ascii=False)}}]}, context)
                self.assertEqual(error.exception.code, code)

    def test_non_object_and_non_json_output_consumed_once(self):
        self.prepare(); original = self.saved()
        for raw, stage, code in (
            ('[]', 'decision_contract', 'invalid_object'),
            ('null', 'decision_contract', 'invalid_object'),
            ('설명 {"action":"proceed"}', 'decision_json', 'invalid_json'),
            ('{"action":NaN}', 'decision_json', 'invalid_json'),
            ('{"action":"proceed","action":"ask_user"}', 'decision_json', 'invalid_json'),
        ):
            with self.subTest(code=code, raw=raw):
                app.save_project(deepcopy(original))
                response = Response({'choices': [{'finish_reason': 'stop', 'message': {'content': raw}}]})
                with patch('manager_decision.urlopen', return_value=response) as transport:
                    with self.assertRaises(RuntimeError): self.run_real()
                    with self.assertRaises(ValueError): self.run_real()
                    transport.assert_called_once()
                p = self.saved()
                self.assertEqual((p['history'][-1]['stage'], p['history'][-1]['error_code']), (stage, code))
                self.assertEqual(p['manager_decisions']['proposals'], [])
                self.assertEqual(p['real_ai']['attempts'][-1]['status'], 'completed')
