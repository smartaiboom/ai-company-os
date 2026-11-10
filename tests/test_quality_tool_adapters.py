"""Offline tool costs, handoff integrity and existing-engine dependency execution."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from autonomous_company import CompanyError, Store, digest
from quality_feedback import bind_context, select_experiences
from quality_tool_adapters import (capabilities, prepare, inspect_handoff, execute,
                                  PreparedSceneProvider, run_offline_contract)
from video_production_company import quality_tool_decision_context


class QualityToolTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden')))
        self.script = '회의 메모의 미정은 확정 시간이 아닙니다. 원문과 비교하세요.'
        self.spec = dict(audience='한국어 직장인 AI 초보자',
                         acceptance='No loops; meaningful demo; natural Korean judged by listener',
                         human_review_required=True)

    def request(self, video=False):
        value = (dict(prompt='Hands compare original meeting note and tentative schedule; no text',
                      aspect_ratio='9:16', duration_target=5, reference_image=None) if video else
                 dict(text=self.script, language='ko-KR', voice_id=None))
        return dict(input=value, quality_spec=deepcopy(self.spec), cap_usd='0.25',
                    rights='owned_input_pending_output_terms', upstream_hash=digest(self.script))

    def test_published_costs_unicode_units_and_detached_catalog(self):
        for tool, rate in [('eleven_multilingual_v2', '0.00008'), ('google_chirp3_hd', '0.00003')]:
            result = prepare(tool, self.request())
            from decimal import Decimal
            self.assertEqual(Decimal(result['estimated_usd']), len(self.script)*Decimal(rate))
            self.assertNotEqual(len(self.script), len(self.script.encode()))
        result = PreparedSceneProvider().prepare(self.request(True))
        self.assertEqual(result['estimated_usd'], '0.25')
        c = quality_tool_decision_context();c['tools'].clear()
        self.assertEqual(len(capabilities()['tools']), 3)

    def test_caps_limits_and_unknown_fields_are_rejected(self):
        cases = [('cap_usd', True), ('cap_usd', 'NaN'), ('cap_usd', '-1'),
                 ('cap_usd', '0.2499'), ('upstream_hash', 'bad'), ('api_key', 'forbidden')]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                request = self.request(True);request[key] = value
                with self.assertRaises(CompanyError): prepare('runway_gen4_turbo', request)
        for seconds in [True, float('nan'), 6, 60]:
            request = self.request(True);request['input']['duration_target'] = seconds
            with self.assertRaises(CompanyError): prepare('runway_gen4_turbo', request)
        request = self.request();request['input']['text'] = '가'*1667
        with self.assertRaisesRegex(CompanyError, 'tts_byte_limit'): prepare('google_chirp3_hd', request)
        request['input']['text'] = 'x'*10001
        with self.assertRaises(CompanyError): prepare('eleven_multilingual_v2', request)
        with self.assertRaises(CompanyError): prepare('unverified_kling', self.request(True))

    def test_no_permission_upload_or_forged_result_enables_execution(self):
        request = self.request(True);request['input']['reference_image'] = 'ref.png'
        with self.assertRaisesRegex(CompanyError, 'reference_upload_not_authorized'):
            prepare('runway_gen4_turbo', request)
        result = prepare('runway_gen4_turbo', self.request(True))
        self.assertFalse(inspect_handoff(result, upstream_hash=digest(self.script))['publishable'])
        result['output'] = 'fake.mp4'
        with self.assertRaisesRegex(CompanyError, 'quality_preparation_changed'):
            inspect_handoff(result, upstream_hash=digest(self.script))
        for value in [result, {'approved': True}, None]:
            with self.assertRaisesRegex(CompanyError, 'quality_tool_transport_disabled'): execute(value)
        with self.assertRaisesRegex(CompanyError, 'external_video_api_disabled'):
            PreparedSceneProvider().generate_scene(self.request(True)['input'])

    def test_current_input_writer_video_voice_qa_and_terminal_no_replay(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root)/'mock');project = store.create('New meeting-note demo', opt_in=True)
            bind_context(store, project['id'], dict(answers={'audience': self.spec['audience']},
                constraints={'sensory_quality': 'unassessed'}, capabilities=capabilities(),
                experiences=select_experiences([], domain='video', target_segment=self.spec['audience']),
                permissions={'external_calls': False, 'cost_limit': 0}))
            def run():
                return run_offline_contract(store, project['id'], self.script,
                    self.request(True), self.request(), voice_tool='eleven_multilingual_v2')
            result = run()
            self.assertEqual(result['reason_code'], 'manager_final_stopped')
            self.assertEqual([t['id'] for t in result['assignments']], ['writer', 'video', 'voice', 'qa'])
            self.assertTrue(all(len(t['versions']) == 1 for t in result['assignments']))
            qa = json.loads(result['assignments'][-1]['versions'][0]['content'])
            self.assertFalse(qa['publishable']);self.assertEqual(len(qa['inspections']), 2)
            self.assertEqual(len(result['attempts']), 10)
            self.assertFalse(result['artifacts']);self.assertTrue(result['simulation'])
            self.assertEqual(len(run()['attempts']), 10)
            wrong = self.request();wrong['upstream_hash'] = '0'*64
            with self.assertRaisesRegex(CompanyError, 'quality_upstream_changed'):
                run_offline_contract(store, project['id'], self.script, self.request(True), wrong,
                                     voice_tool='eleven_multilingual_v2')


if __name__ == '__main__': unittest.main()
