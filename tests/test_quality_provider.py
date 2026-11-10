"""Native-wire integration with mocked HTTP only. No live inference or account verification."""
from copy import deepcopy
from io import BytesIO
from datetime import datetime, timedelta, timezone
from itertools import count
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autonomous_company import CompanyError, Store, digest, parse
from autonomous_live import LiveManagerProvider, LiveEmployeeProvider
from autonomous_gemini35 import Gemini35Config, MODEL, ENDPOINT
from quality_provider import (QualityProviderStore, QualityProviderCompany, experience_context,
                              validate_feedback_claim)
from quality_workflow import VideoProviderQualityCompany, capabilities, validate_qa_claim
from tests.test_quality_feedback import VideoFixtures


class ProviderReadinessTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.store=QualityProviderStore(self.root/'provider')
        self.key='fixture-only-provider-key'
        self.enterContext(patch('socket.socket.connect',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')))
        self.http=self.enterContext(patch('autonomous_live.urlopen'))
        self.enterContext(patch.dict(os.environ, GEMINI_API_KEY=self.key,GEMINI35_MODEL=MODEL,
            GEMINI35_ENDPOINT=ENDPOINT,GEMINI35_AUTONOMOUS_FREE_ENABLED='1'))
        # Keep pacing algorithm/checks, make each recorded interval immediately elapsed in fixtures.
        ticks=count()
        self.enterContext(patch('autonomous_free.pacing_now',side_effect=lambda: (
            datetime(2026,1,1,tzinfo=timezone(timedelta(hours=9)))+timedelta(seconds=3*next(ticks))).isoformat()))
        self.inputs=dict(domain='video',target_segment='30~40대 주부',answers={'audience':'30~40대 주부'},
            constraints={'seconds':60,'aspect':'9:16'},capabilities=capabilities(),experiences=[],
            feedback_text='30~40대 주부용이면 친근한 말투가 좋겠다. 화면이 계속 반복된다.')

    def create(self,**kwargs):
        p=self.store.create('초보자에게 질문 한 가지 방법을 설명하는60초영상',inputs=self.inputs,**kwargs)
        self.pid=p['id']
        self.company=VideoProviderQualityCompany(self.store,LiveManagerProvider(),LiveEmployeeProvider(),Gemini35Config(self.key))
        return p

    def approve(self,**kwargs):
        body=self.store.prepare(self.pid,confirm_free_account=True,**kwargs)
        self.store.approve(self.pid,body,review_hash=digest(body),owner_confirmed=True)
        return body

    def run_company(self):
        p=self.store.load(self.pid)
        return self.company.run(self.pid,expected_state_hash=p['storage_hash'])

    def envelope(self,value):
        return BytesIO(json.dumps(dict(candidates=[dict(finishReason='STOP',content=dict(role='model',
            parts=[dict(text=json.dumps({'result':value},ensure_ascii=False))]))],
            usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=20,totalTokenCount=40))).encode())

    def claim(self):
        return dict(project=self.pid,domain='video',target_segment='30~40대 주부',issue='반복 화면',
            positive_preference='친근한 말투',proposed_correction='다른 장면과 친근한 말투',
            evidence='친근한 말투가 좋겠다',source='model extraction of user text',confidence=.7,verification='hypothesis')

    def fixture_transport(self):
        model=VideoFixtures(); contexts=[]
        def send(request,timeout):
            p=self.store.load(self.pid)
            self.assertEqual(p['real_ai']['attempts'][-1]['status'],'reserved')
            self.assertTrue(p['real_ai']['attempts'][-1]['transport_started_at'])
            self.assertEqual(request.full_url,ENDPOINT);self.assertEqual(timeout,90)
            self.assertEqual(request.get_header('X-goog-api-key'),self.key)
            self.assertNotIn(self.key,request.data.decode())
            self.assertNotIn('operating_grant_id',request.data.decode())
            self.assertNotIn('storage_hash',request.data.decode())
            wire=json.loads(request.data)
            self.assertEqual(wire['generationConfig']['responseMimeType'],'application/json')
            message=parse(wire['contents'][0]['parts'][0]['text']);contexts.append(message)
            phase=message['phase'];c=message['data']
            self.assertNotIn('real_ai',c)
            if phase=='plan':
                value=json.loads(model.manage(phase,c))
                value['tasks'] += [dict(id='quality',title='内容QA',role='qa',depends_on=['script','shots','speech'],
                    criteria_ids=['plan'],instructions='반복 수치와 의미 검토를 분리; 감각 품질 미평가'),
                    dict(id='experience',title='피드백 구조화',role='feedback',depends_on=['quality'],
                    criteria_ids=['plan'],instructions='입력 피드백 원문을 근거로 대상 한정 가설 추출')]
            elif phase=='execute' and c['assignment']['role']=='qa':
                self.assertTrue(c['handoff_refs']);self.assertTrue(c['plan_evidence'])
                value=dict(content=json.dumps(dict(assessments=[dict(criterion_id='hook',status='met',
                    evidence='수정 대본의 질문형 도입; fixture 판단',source='model_claim'),dict(criterion_id='voice',
                    status='unassessed',evidence='음성 미제공',source='model_claim')],defects=[],sensory_quality='unassessed')),
                    evidence='text plan only, mocked HTTP',uncertainty='no watching/listening')
            elif phase=='execute' and c['assignment']['role']=='feedback':
                value=dict(content=json.dumps(self.claim(),ensure_ascii=False),evidence='원문 인용',uncertainty='hypothesis')
            elif phase=='execute':
                adjusted=deepcopy(c);adjusted['quality']['experiences']={'selected':c['quality']['experiences']}
                if c['revision_feedback']:
                    self.assertTrue(c['version_history']);self.assertIn('correction',c['revision_feedback'])
                value=json.loads(model.work(phase,adjusted))
            else:
                value=json.loads(model.manage(phase,c));value.pop('task_refs',None)
            return self.envelope(value)
        self.http.side_effect=send
        return contexts

    def test_native_workflow_handoff_qa_revision_and_feedback_receipt(self):
        self.create(max_calls=20);self.approve();contexts=self.fixture_transport()
        with patch('quality_provider.QUALITY_TRANSPORT_ENABLED',True):result=self.run_company()
        self.assertEqual(result['status'],'external_clip_pending');self.assertFalse(result['simulation'])
        self.assertEqual([len(t['versions']) for t in result['assignments']],[2,2,1,1,1])
        self.assertEqual(len(result['real_ai']['attempts']),16)
        self.assertTrue(all(a['role_result_status']=='validated' for a in result['real_ai']['attempts']))
        self.assertTrue(all(v['source']=='provider_model_claim' for t in result['assignments'] for v in t['versions']))
        self.assertIsNone(result['quality_checklist']['total']);self.assertFalse(result['artifacts'])
        count=self.http.call_count;self.run_company();self.assertEqual(self.http.call_count,count)
        record=self.store.record_feedback(self.pid,'experience')
        selected=self.store.select_feedback(self.pid,domain='video',target_segment='30~40대 주부')
        self.assertEqual(selected['selected'][0]['id'],record['id'])
        wire=experience_context(selected);self.assertNotIn('original_text',wire[0])
        self.assertFalse(self.store.select_feedback(self.pid,domain='video',target_segment='초등학생')['selected'])
        with self.assertRaisesRegex(CompanyError,'duplicate_feedback_receipt'):self.store.record_feedback(self.pid,'experience')
        self.store.withdraw_feedback(self.pid,record['id'],'사용자 철회')
        self.assertFalse(self.store.select_feedback(self.pid,domain='video',target_segment='30~40대 주부')['selected'])
        sample=dict(provenance='mocked HTTP, no real AI inference',requests=contexts,result=result,
                    feedback=record,selection=selected,wire_experiences=wire)
        target=os.getenv('PROVIDER_SAMPLE_OUTPUT')
        if target:
            path=Path(target);self.assertTrue(path.is_absolute() and path.is_relative_to('/tmp'))
            path.write_text(json.dumps(sample,ensure_ascii=False,indent=2))

    def test_default_gate_despite_key_env_and_signed_consent(self):
        self.create();self.approve()
        before=self.store.load(self.pid)
        with self.assertRaisesRegex(CompanyError,'quality_transport_disabled'):self.run_company()
        self.assertEqual(self.store.load(self.pid),before);self.http.assert_not_called()
        with self.assertRaises(CompanyError):QualityProviderCompany(Store(self.root/'mock'),LiveManagerProvider(),
            LiveEmployeeProvider(),Gemini35Config(self.key))
        with self.assertRaises(CompanyError):QualityProviderStore(self.root/'provider').create('목표',inputs=self.inputs,max_calls=None)
        with self.assertRaises(CompanyError):QualityProviderStore(self.root/'provider').create('목표',inputs=self.inputs,max_calls=21)

    def test_missing_consent_free_account_binding_and_revocation(self):
        self.create()
        with patch('quality_provider.QUALITY_TRANSPORT_ENABLED',True):
            with self.assertRaises(CompanyError):self.run_company()
        body=self.store.prepare(self.pid)
        with self.assertRaisesRegex(CompanyError,'gemini_free_account_unverified'):
            self.store.approve(self.pid,body,review_hash=digest(body),owner_confirmed=True)
        body=self.store.prepare(self.pid,confirm_free_account=True)
        body['quality_contract']['inputs']['target_segment']='다른 대상'
        with self.assertRaisesRegex(CompanyError,'quality_consent_binding'):
            self.store.approve(self.pid,body,review_hash=digest(body),owner_confirmed=True)
        self.approve();self.store.revoke(self.pid,owner_confirmed=True)
        with patch('quality_provider.QUALITY_TRANSPORT_ENABLED',True):
            with self.assertRaisesRegex(CompanyError,'consent_revoked'):self.run_company()
        self.http.assert_not_called();self.assertFalse(self.store.load(self.pid)['real_ai']['attempts'])

    def test_timeout_malformed_output_and_nonzero_cost_never_replayed(self):
        for failure in ('timeout','schema','cost','interrupt'):
            with self.subTest(failure=failure):
                self.store=QualityProviderStore(self.root/failure);self.create();self.approve()
                if failure=='timeout':self.http.side_effect=TimeoutError('do not log secret exception')
                elif failure=='interrupt':self.http.side_effect=KeyboardInterrupt()
                elif failure=='schema':self.http.side_effect=lambda *a,**k:self.envelope({'tasks':'invalid'})
                else:
                    def response(*a,**k):
                        env=json.loads(self.envelope({}).getvalue());env['usageMetadata']['cost']=1
                        return BytesIO(json.dumps(env).encode())
                    self.http.side_effect=response
                with patch('quality_provider.QUALITY_TRANSPORT_ENABLED',True):
                    if failure=='interrupt':
                        with self.assertRaises(KeyboardInterrupt):self.run_company()
                    else:
                        result=self.run_company();self.assertEqual(result['status'],'stopped')
                    count=self.http.call_count
                    if failure=='interrupt':
                        with self.assertRaises(CompanyError):self.run_company()
                    else:self.run_company()
                    self.assertEqual(self.http.call_count,count)
                p=self.store.load(self.pid)
                self.assertEqual(len(p['real_ai']['attempts']),1)
                self.assertNotIn('do not log secret exception',json.dumps(p))

    def test_budget_exhaustion_namespace_isolation_and_changed_inputs(self):
        self.create(max_calls=1);self.approve();self.fixture_transport()
        with patch('quality_provider.QUALITY_TRANSPORT_ENABLED',True):result=self.run_company()
        self.assertEqual(result['reason_code'],'optional_technical_cap_reached');self.assertEqual(self.http.call_count,1)
        with self.assertRaises(CompanyError):Store(self.store.root).load(self.pid)
        with self.assertRaises(CompanyError):QualityProviderStore(self.root/'mock').load('company-old')
        self.store=QualityProviderStore(self.root/'changed');self.create();self.approve()
        p=self.store.load(self.pid);p['quality_inputs']['target_segment']='변경';self.store.save(p)
        with patch('quality_provider.QUALITY_TRANSPORT_ENABLED',True):
            with self.assertRaisesRegex(CompanyError,'quality_consent_binding'):self.run_company()
        self.assertFalse(self.store.load(self.pid)['real_ai']['attempts'])

    def test_feedback_scope_privacy_and_fabricated_sensory_evidence_rejected(self):
        self.create()
        for change in ({'target_segment':'전세계'},{'verification':'verified'},{'confidence':True},
                       {'evidence':'원문에 없는 문구'}):
            with self.assertRaises(CompanyError):validate_feedback_claim({**self.claim(),**change},self.inputs)
        wrong=deepcopy(self.inputs);wrong['constraints']['api_key']='should never transmit'
        with self.assertRaises(CompanyError):self.store.create('bad',inputs=wrong)
        with self.assertRaisesRegex(CompanyError,'sensory_evidence_missing'):
            validate_qa_claim(dict(assessments=[dict(criterion_id='voice',status='met',source='model_claim',evidence='heard it')],
                                   defects=[],sensory_quality='unassessed'))
        self.http.assert_not_called()
