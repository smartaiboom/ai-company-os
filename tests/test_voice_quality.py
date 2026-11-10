from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from autonomous_company import Store, CompanyError, digest
from quality_feedback import ExperienceJournal, bind_context
from quality_workflow import capabilities
from video_production_company import voice_staff_quality_context
from voice_quality import (AUDIENCE, ORIGINAL, record_user_evaluation, next_voice_sample,
                           inspect_voice_stage, run_voice_quality_offline)
from tts_job import sha


class VoiceQualityTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('no external API')))
        self.enterContext(patch('socket.getaddrinfo', side_effect=AssertionError('no DNS')))
        self.paths = {}
        for label, rate in [('A', 44100), ('B', 24000)]:
            path = self.root/(label+'.wav')
            with wave.open(str(path), 'wb') as wav:
                wav.setparams((1, 2, rate, 0, 'NONE', 'not compressed')); wav.writeframes(b'\x10\x00'*rate)
            self.paths[label] = path
        self.paths['transcript'] = self.root/'script.txt'; self.paths['transcript'].write_text('Fixture only')
        self.enterContext(patch('voice_quality.BINDINGS', {key:sha(path.read_bytes()) for key,path in self.paths.items()}))

    def record(self): return record_user_evaluation(self.root/'feedback', **self.paths)

    def test_verified_binding_idempotence_scope_and_no_authority(self):
        first = self.record(); artifact = Path(first['artifact']); before = artifact.read_bytes()
        second = self.record()
        self.assertEqual(first, second); self.assertEqual(before, artifact.read_bytes())
        self.assertEqual(first['entry']['original_text'], ORIGINAL)
        self.assertEqual(first['entry']['verification'], 'verified')
        self.assertEqual(first['entry']['extraction_source'], 'user_structured')
        journal = ExperienceJournal(self.root/'feedback/journal')
        self.assertEqual(len(journal.store.load(first['journal_id'])['experiences']), 1)
        same = voice_staff_quality_context(first['selection'], target_segment=AUDIENCE)
        self.assertEqual(same['voice_policy']['baseline_score'], 7)
        self.assertEqual(same['voice_policy']['target_score'], 8)
        self.assertFalse(same['voice_policy']['permission_to_generate']);self.assertFalse(same['external_calls'])
        self.assertEqual(same['voice_policy']['improvement_status'], 'hypothesis')
        other = journal.select(first['journal_id'], domain='video', target_segment='초등학생')
        self.assertFalse(other['selected'])
        wrong_domain = journal.select(first['journal_id'], domain='product', target_segment=AUDIENCE)
        self.assertFalse(wrong_domain['selected'])
        self.assertIsNone(voice_staff_quality_context(first['selection'],target_segment='다른 한국어 시청자')['voice_policy']['recommended'])
        fake = deepcopy(first['selection']);fake['selected'][0]['extraction_source']='offline_fixture'
        self.assertIsNone(voice_staff_quality_context(fake,target_segment=AUDIENCE)['voice_policy']['recommended'])

    def test_real_engine_handoffs_manager_baseline_and_terminal_no_replay(self):
        evidence = self.record();store=Store(self.root/'company');p=store.create('Voice quality planning only',opt_in=True)
        caps=capabilities();caps['voice_quality_contract_v1']=True
        bind_context(store,p['id'],dict(answers={'audience':AUDIENCE},constraints={'new_audio':False},capabilities=caps,
            experiences=evidence['selection'],permissions={'external_calls':False,'cost_limit':0}))
        result=run_voice_quality_offline(store,p['id'])
        self.assertEqual(result['reason_code'],'manager_final_stopped')
        self.assertTrue(result['simulation']);self.assertFalse(result['artifacts'])
        self.assertEqual([t['role'] for t in result['assignments']],['writer','voice','editor','qa'])
        writer,voice,editor,qa=[t['versions'][-1] for t in result['assignments']]
        value=json.loads(voice['content']);self.assertEqual(value['baseline_score'],7);self.assertEqual(value['target_score'],8)
        self.assertEqual(value['candidate']['voice'],'Puck')
        self.assertEqual(value['upstream_refs'][0]['result_hash'],digest(writer))
        self.assertEqual(json.loads(editor['content'])['scenes'],json.loads(writer['content'])['sample']['scenes'])
        self.assertEqual(json.loads(qa['content'])['new_quality'],'unassessed')
        calls=len(result['attempts']);self.assertEqual(calls,10)
        self.assertEqual(len(run_voice_quality_offline(store,p['id'])['attempts']),calls)
        for task in result['assignments']: self.assertEqual(task['plan_inspections'][0]['defects'],[])
        policy=voice_staff_quality_context(evidence['selection'],target_segment=AUDIENCE)['voice_policy']
        for key,bad in [('baseline_score',9),('generation_authorized',True),('new_audio','fake.wav'),('narration_sha256','0'*64),('upstream_refs',[])]:
            changed=deepcopy(value);changed[key]=bad
            with self.subTest(key=key),self.assertRaises(CompanyError):inspect_voice_stage('voice',changed,[writer],policy)

    def test_media_tamper_and_future_planning_cannot_be_scored_as_observed(self):
        evidence=self.record();self.paths['B'].write_bytes(b'changed')
        with self.assertRaisesRegex(CompanyError,'voice_evidence_changed'):self.record()
        sample=next_voice_sample()
        self.assertEqual(sum(s['seconds'] for s in sample['scenes']),20)
        self.assertEqual(sample['direction']['extra_wire_parameters'],{})
        self.assertIsNone(sample['actual_seconds']);self.assertFalse(sample['publish_ready'])
        writer=dict(contract='voice_quality_v1',role='writer',authorship='codex-authored',publish_ready=False,upstream_refs=[],sample=sample)
        changed=deepcopy(writer);changed['sample']['scenes'][0]['seconds']=4
        with self.assertRaises(CompanyError):inspect_voice_stage('writer',changed,[],{})
        changed=deepcopy(writer);changed['sample']['direction']['extra_wire_parameters']={'speed':1.3}
        with self.assertRaises(CompanyError):inspect_voice_stage('writer',changed,[],{})


    def brief(self, video_id='tip-1'):
        return dict(channel_id='work-ai',series_id='ai-tips',video_id=video_id,target_segment=AUDIENCE,
            language='ko-KR',topic='가상 회의 메모 구분',genre='ai_tips',mood='friendly_explainer',
            brand_consistency=True,representative=None,exception=None,
            constraints=dict(external_calls=False,publish_ready=False,max_cost_usd=0))

    def representative(self):
        return dict(candidate=dict(provider='gemini_developer',model='gemini-3.8-flash-tts',voice='Kore'),
            scope='series',channel_id='work-ai',series_id='ai-tips',target_segment=AUDIENCE,language='ko-KR',
            mood='friendly_explainer',source='user_designated',evidence_refs=['fixture-user-setting-not-listening-proof'])

    def test_per_video_selection_consistency_reassessment_and_no_global_default(self):
        from voice_quality import select_video_voice, record_voice_selection
        evidence=self.record();selection=evidence['selection']
        first=select_video_voice(selection,self.brief());second=select_video_voice(selection,self.brief('tip-2'))
        self.assertEqual(first['candidate']['voice'],'Puck');self.assertEqual(second['candidate']['voice'],'Puck')
        self.assertNotEqual(first['decision_sha256'],second['decision_sha256'])
        self.assertFalse(first['channel_default_created']);self.assertEqual(first['selected_voice_score'],7)
        brief=self.brief();brief['representative']=self.representative()
        rep=select_video_voice(selection,brief)
        self.assertEqual(rep['candidate']['voice'],'Kore');self.assertIsNone(rep['selected_voice_score'])
        self.assertEqual(rep['listening_status'],'unassessed');self.assertEqual(rep['reference_AB_score'],7)
        brief['mood']='news';changed=select_video_voice(selection,brief)
        self.assertIsNone(changed['candidate']);self.assertEqual(changed['status'],'reassessment_required')
        other=self.brief('children-1');other.update(target_segment='초등학생',genre='story',mood='playful_shorts')
        self.assertIsNone(select_video_voice(selection,other)['candidate'])
        journal=ExperienceJournal(self.root/'decisions');jid=journal.create()
        entry=record_voice_selection(journal,jid,rep,selection=selection)
        self.assertEqual(record_voice_selection(journal,jid,rep,selection=selection),entry)
        self.assertEqual(entry['verification'],'hypothesis');self.assertEqual(entry['extraction_source'],'offline_fixture')

    def test_exceptions_require_reason_review_and_never_grant_generation(self):
        from voice_quality import select_video_voice, record_voice_selection
        selection=self.record()['selection'];brief=self.brief();brief['representative']=self.representative()
        override=dict(candidate=dict(provider='gemini_developer',model='gemini-3.8-flash-tts',voice='Puck'),
            scope='video',reason='가상 변경 이유 검토',reviewed_by='manager',review_note='offline authored review fixture',version=1)
        brief['exception']=override
        valid=select_video_voice(selection,brief);self.assertEqual(valid['status'],'reviewed_exception_unassessed')
        for key,bad in [('reason',''),('reviewed_by',''),('review_note',''),('version',True)]:
            invalid=deepcopy(brief);invalid['exception'][key]=bad
            with self.subTest(key=key),self.assertRaises(CompanyError):select_video_voice(selection,invalid)
        invalid=self.brief();invalid['constraints']['external_calls']=True
        with self.assertRaises(CompanyError):select_video_voice(selection,invalid)
        invalid=self.brief();invalid['representative']=self.representative()
        invalid['representative'].update(source='evidence_based',candidate=dict(provider='gemini_developer',model='gemini-3.8-flash-tts',voice='Puck'),
            evidence_refs=[json.loads(selection['selected'][0]['evidence'])['evaluation_sha256']])
        with self.assertRaises(CompanyError):select_video_voice(selection,invalid)
        journal=ExperienceJournal(self.root/'bad-decisions');jid=journal.create()
        tampered=deepcopy(valid);tampered['permission_to_generate']=True
        with self.assertRaises(CompanyError):record_voice_selection(journal,jid,tampered,selection=selection)

    def test_video_selection_reaches_all_engine_handoffs_and_new_sample_is_unmeasured(self):
        from voice_quality import voice_policy_for_brief
        evidence=self.record();brief=self.brief();store=Store(self.root/'video-selection-company')
        p=store.create('Per-video voice contract',opt_in=True);caps=capabilities();caps['voice_quality_contract_v1']=True
        bind_context(store,p['id'],dict(answers={'audience':AUDIENCE,'video_voice_brief':brief},constraints={'new_audio':False},
            capabilities=caps,experiences=evidence['selection'],permissions={'external_calls':False,'cost_limit':0}))
        result=run_voice_quality_offline(store,p['id']);self.assertEqual(result['reason_code'],'manager_final_stopped')
        expected=voice_policy_for_brief(evidence['selection'],AUDIENCE,brief)
        for task in result['assignments']:
            value=json.loads(task['versions'][-1]['content'])
            self.assertEqual(value['video_voice_selection']['decision_sha256'],expected['video_selection']['decision_sha256'])
        writer,voice,editor,qa=[t['versions'][-1] for t in result['assignments']]
        value=json.loads(voice['content']);tampered=deepcopy(value)
        tampered['video_voice_selection']['selected_voice_score']=8
        with self.assertRaises(CompanyError):inspect_voice_stage('voice',tampered,[writer],expected)
        sample=json.loads(writer['content'])['sample']
        self.assertEqual(sample['accepted_actual_seconds_range'],[15,35]);self.assertIsNone(sample['actual_seconds'])
        self.assertEqual(sample['proposed_limits']['max_audio_seconds'],35)
        self.assertIsNone(sample['comparison_rubric']['new_overall_score'])
        self.assertTrue(all(d['before'] is None and d['after'] is None for d in sample['comparison_rubric']['dimensions']))
        self.assertEqual(json.loads(editor['content'])['actual_alignment'],None)
        other=deepcopy(brief);other['target_segment']='초등학생';other['genre']='story'
        other_policy=voice_policy_for_brief(evidence['selection'],'초등학생',other)
        changed=json.loads(writer['content']);changed['video_voice_selection']=other_policy['video_selection']
        with self.assertRaisesRegex(CompanyError,'voice_sample_scope_mismatch'):
            inspect_voice_stage('writer',changed,[],other_policy)
