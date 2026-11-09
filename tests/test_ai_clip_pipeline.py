"""Offline media integration and adversarial import boundaries, no cloud inference."""
from copy import deepcopy
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

from autonomous_company import CompanyError, now, digest
from ai_clip_pipeline import (ClipJob, ManualClipProvider, DisabledAPIProvider, baseline_plan,
    create_fixtures, validate_source, publishable, open_input, write_captions)
from local_melo_tts import file_hash
from video_production_company import create_offline_clip_job, offline_clip_decision_context


class TestSpeech:
    """A test signal validates mixing; never advertised as speech/MeloTTS."""
    def synthesize(self, texts, folder):
        import math
        items=[]
        for i,text in enumerate(texts):
            path=Path(folder)/f'voice-{i:02}.wav'
            with wave.open(str(path),'wb') as stream:
                stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(44100)
                stream.writeframes(b''.join(struct.pack('<h',int(3000*math.sin(2*math.pi*440*n/44100))) for n in range(22050)))
            items.append(dict(file=path.name,text=text,duration=.5,sample_rate=44100,sha256=file_hash(path)))
        return dict(engine='synthetic_test_tone_not_tts',utterances=items)


class ClipPipelineTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('socket.socket.connect',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')))

    def plan(self):
        return dict(goal='초보자 안내',decision_source='test fixture',total_seconds=2,fit='letterbox',allow_repeat=True,
            scenes=[dict(id='scene-1',request=dict(prompt='A calm desk',aspect_ratio='9:16',duration_target=2,reference_image=None),
                         utterances=['원하는 일을 적어 보세요.'])])

    def test_provider_contracts_and_rights_are_not_execution_permission(self):
        request=self.plan()['scenes'][0]['request']
        for name in ('google_flow','pika','kling'):
            provider=ManualClipProvider(name)
            self.assertFalse(provider.capabilities()['automatic_generation_supported'])
            self.assertEqual(provider.generate_scene(request)['status'],'pending_manual_import')
        with self.assertRaisesRegex(CompanyError,'external_video_api_disabled'):
            DisabledAPIProvider().generate_scene(request)
        self.assertFalse(offline_clip_decision_context()['external_api_enabled'])
        source=dict(provider='pika',provenance=dict(kind='external_ai_clip',evidence='Operator supplied download'),
            generated_at=now(),license='unknown',terms_url='unknown',usage_rights='unknown',commercial_use='unknown',
            allowed_to_publish=None,watermark='unknown',rights_verified=False,rights_evidence='unknown',estimated_cost=None,actual_cost=None)
        validate_source(source);self.assertFalse(publishable(source))
        source['allowed_to_publish']=1
        with self.assertRaises(CompanyError): validate_source(source)

    def test_import_traversal_symlink_container_duplicate_checksum_and_crop(self):
        inbox=self.root/'inbox';source=create_fixtures(inbox)
        plan=self.plan();plan['scenes'].append({**deepcopy(plan['scenes'][0]),'id':'scene-2'})
        job=ClipJob(self.root/'job');job.create(plan)
        for name in ('../fixture-1.mp4',str(inbox/'fixture-1.mp4')):
            with self.assertRaises(CompanyError): job.import_generated_clip(inbox,name,'scene-1',source)
        (inbox/'link.mp4').symlink_to(inbox/'fixture-1.mp4')
        (inbox/'linked').symlink_to(inbox,target_is_directory=True)
        for name in ('link.mp4','linked/fixture-1.mp4'):
            with self.assertRaises((OSError,CompanyError)): job.import_generated_clip(inbox,name,'scene-1',source)
        (inbox/'fake.mp4').write_text('not a video')
        with self.assertRaises(CompanyError): job.import_generated_clip(inbox,'fake.mp4','scene-1',source)
        before=file_hash(inbox/'fixture-1.mp4')
        record=job.import_generated_clip(inbox,'fixture-1.mp4','scene-1',source)
        with self.assertRaisesRegex(CompanyError,'duplicate_clip'):
            job.import_generated_clip(inbox,'fixture-1.mp4','scene-2',source)
        self.assertEqual(file_hash(inbox/'fixture-1.mp4'),before)
        job.import_generated_clip(inbox,'fixture-2.mp4','scene-2',source)
        path=job.root/'assets'/record['file'];path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaisesRegex(CompanyError,'clip_changed'): job.render(TestSpeech())
        self.assertFalse(job.load()['attempts'])
        job2=ClipJob(self.root/'crop');p=self.plan();p['fit']='crop';job2.create(p)
        source['watermark']='present';job2.import_generated_clip(inbox,'fixture-2.mp4','scene-1',source)
        with self.assertRaisesRegex(CompanyError,'watermark_crop_forbidden'): job2.render(TestSpeech())

    def test_real_ffmpeg_vertical_audio_captions_timeline_and_no_replay(self):
        inbox=self.root/'inbox';source=create_fixtures(inbox)
        plan=self.plan();job=ClipJob(self.root/'job')
        plan['scenes'].append({**deepcopy(plan['scenes'][0]),'id':'scene-2'})
        create_offline_clip_job(job.root,plan)
        job.import_generated_clip(inbox,'fixture-1.mp4','scene-1',source)
        job.import_generated_clip(inbox,'fixture-2.mp4','scene-2',source)
        result=job.render(TestSpeech())
        self.assertEqual((result['width'],result['height']),(720,1280))
        self.assertTrue(result['audio'] and result['decoded'])
        self.assertEqual(result['media']['raw']['streams'][0]['sample_aspect_ratio'],'1:1')
        self.assertFalse(result['publish_ready'] or result['ai_generated_clip_used'])
        self.assertEqual(job.load()['status'],'pending_external_clip')
        timeline=json.loads((job.root/'timeline.json').read_text())
        self.assertAlmostEqual(timeline['scenes'][-1]['end'],2)
        self.assertTrue(all(0<=c['start']<c['end']<=2 for c in timeline['captions']))
        self.assertIn('원하는 일을',(job.root/'captions.ass').read_text())
        with self.assertRaisesRegex(CompanyError,'render_not_replayable'): job.render(TestSpeech())

    def test_too_long_audio_fails_instead_of_truncation_or_speedup(self):
        inbox=self.root/'inbox';source=create_fixtures(inbox)
        plan=self.plan();plan['total_seconds']=1
        plan['scenes'][0]['utterances']*=3
        job=ClipJob(self.root/'job');job.create(plan)
        job.import_generated_clip(inbox,'fixture-1.mp4','scene-1',source)
        with self.assertRaisesRegex(CompanyError,'narration_exceeds_target_revise_script'): job.render(TestSpeech())
        self.assertFalse((job.root/'preview.mp4').exists())
        self.assertEqual(job.load()['attempts'][0]['status'],'failed')
        with self.assertRaises(CompanyError):job.render(TestSpeech())


@unittest.skipUnless(os.getenv('AI_CLIP_ACCEPTANCE_ROOT'), 'Set AI_CLIP_ACCEPTANCE_ROOT for real local MeloTTS + 60s render')
class RealOfflineClipAcceptance(unittest.TestCase):
    def test_baseline_to_real_melo_vertical_video(self):
        from local_melo_tts import MeloLocal
        roots=[Path('data/gemini_one_call_acceptance'),Path('data/video_baseline_review/20261109T132912_KST'),
               Path('data/tts_korean_review/20261109T140119_KST')]
        before={str(p):file_hash(p) for root in roots for p in root.rglob('*') if p.is_file()}
        state=json.loads(Path('data/gemini_one_call_acceptance/dialogue-f4eb35fc53a3415093e37815964f51d7.json').read_text())
        self.assertEqual(state['status'],'confirmed')
        self.assertEqual(state['storage_hash'],digest({k:v for k,v in state.items() if k!='storage_hash'}))
        self.assertEqual(state['confirmed_hash'],digest(state['spec']))
        self.assertEqual(len(state['real_ai']['attempts']),1)
        output=Path(os.environ['AI_CLIP_ACCEPTANCE_ROOT']).absolute()
        self.assertTrue(output.is_relative_to(Path('data/video_ai_clip_review').absolute()))
        output.mkdir(parents=True,exist_ok=False)
        source=json.loads(Path('data/video_baseline_review/20261109T132912_KST/render_spec.json').read_text())
        plan=baseline_plan(source,state['goal'])
        self.assertEqual(len(plan['scenes']),3)
        with patch('socket.socket.connect',side_effect=AssertionError('network forbidden')), \
             patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')):
            job=ClipJob(output/'shorts');create_offline_clip_job(job.root,plan)
            meta=create_fixtures(output/'inbox')
            for i in range(1,4): job.import_generated_clip(output/'inbox',f'fixture-{i}.mp4',f'scene-{i}',meta)
            result=job.render(MeloLocal())
        self.assertEqual(result['audio_engine'],'MeloTTS')
        self.assertTrue(result['decoded'] and result['audio'])
        self.assertEqual((result['width'],result['height']),(720,1280))
        self.assertAlmostEqual(result['duration'],60,delta=.2)
        self.assertEqual(job.load()['status'],'pending_external_clip')
        self.assertFalse(result['ai_generated_clip_used'] or result['publish_ready'])
        self.assertEqual(result['external_api_calls'],0)
        timeline=json.loads((job.root/'timeline.json').read_text())
        self.assertTrue(all(0<=c['start']<c['end']<=60 for c in timeline['captions']))
        self.assertTrue(all(a['end']<=b['start']+.001 for a,b in zip(timeline['captions'],timeline['captions'][1:])))
        after={str(p):file_hash(p) for root in roots for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        from autonomous_company import Store
        Store.atomic(output/'preservation.json',dict(existing_acceptance_baseline_and_tts_samples_unchanged=before==after,
            checked_files=len(before),existing_gemini_calls='1/1',new_external_ai_calls=0,incurred_cost=0))
        Store.atomic(output/'source_inputs.json',{k:state[k] for k in ('goal','questions','answers','spec','confirmed_hash')})
        print('\nOFFLINE_SHORTS_ARTIFACT='+str(job.root/'preview.mp4'))
