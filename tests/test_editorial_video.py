"""Meaningful offline safety tests and one opt-in real editorial render, no provider calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autonomous_company import CompanyError,Store,digest
from editorial_video import EditorialJob,inspect_edit,verify_speech,allocate,AUTHOR
from ai_clip_pipeline import probe
from local_artifacts import run_command
from tests.test_ai_clip_pipeline import TestSpeech


def plan():
    return dict(message='한 메시지',intro_kind='specific_problem',hook_seconds=3,author=AUTHOR,
        scenes=[dict(id=f'scene-{i}',seconds=6,source_id=f'source-{i}',source_seconds=6,
          layout='question',title='질문 예시',label='예시',body=['원하는 모양을 적어요'],narration='짧게 적어요.') for i in range(10)])


class EditorialSafetyTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('socket.socket.connect',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')))

    def test_real_editing_constraints_report_evidence_and_owner(self):
        bad=plan();bad.update(message='',intro_kind='greeting',hook_seconds=12)
        bad['scenes'][0]['source_seconds']=1
        bad['scenes'][1]['source_id']=bad['scenes'][0]['source_id']
        bad['scenes'][2]['title']='가'*50
        report=inspect_edit(bad);issues={d['issue'] for d in report['defects']}
        self.assertTrue({'repeated_clip','reused_source','missing_core_message','opening_needs_revision',
                         'caption_or_card_overflow'}.issubset(issues))
        self.assertTrue(all(d['owner'] and d['evidence'] and d['correction'] for d in report['defects']))
        self.assertFalse(inspect_edit(plan())['defects'])
        self.assertEqual(report['semantic_quality'],'unassessed')

    def test_speech_text_hash_and_duration_mismatch_blocks_wrong_voice(self):
        p=plan();folder=self.root/'speech';folder.mkdir()
        r=TestSpeech().synthesize([s['narration'] for s in p['scenes']],folder)
        verify_speech(p,r,folder)
        for mutation in ('text','duration','hash','path'):
            broken=deepcopy(r)
            if mutation=='text':broken['utterances'][0]['text']='다른 대본'
            elif mutation=='duration':broken['utterances'][0]['duration']=float('nan')
            elif mutation=='hash':broken['utterances'][0]['sha256']='0'*64
            else:broken['utterances'][0]['file']='../voice.wav'
            with self.subTest(mutation=mutation):
                with self.assertRaises(CompanyError):verify_speech(p,broken,folder)

    def test_measured_timeline_preserves_hook_and_rejects_overlong_speech(self):
        p=plan();items=[dict(duration=2) for _ in p['scenes']]
        duration=allocate(p,items)
        self.assertEqual(duration[0],3);self.assertAlmostEqual(sum(duration),60)
        self.assertTrue(all(length>=item['duration'] for length,item in zip(duration,items)))
        items[0]['duration']=3
        with self.assertRaises(CompanyError):allocate(p,items)
        items=[dict(duration=8) for _ in p['scenes']];items[0]['duration']=2
        with self.assertRaises(CompanyError):allocate(p,items)

    def test_invalid_plan_and_interrupted_render_do_not_replay(self):
        bad=plan();bad['message']='';job=EditorialJob(self.root/'bad');job.create(bad)
        with self.assertRaises(CompanyError):job.render()
        self.assertFalse(job.load()['attempts'])
        job=EditorialJob(self.root/'interrupted');job.create(plan())
        class Interrupted:
            def synthesize(self,*args):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):job.render(Interrupted())
        self.assertEqual(job.load()['attempts'][0]['status'],'reserved')
        with self.assertRaisesRegex(CompanyError,'render_not_replayable'):job.render(Interrupted())
        self.assertFalse((job.root/'preview.mp4').exists())


@unittest.skipUnless(os.getenv('VIDEO_EDITORIAL_ACCEPTANCE_ROOT'),'Set VIDEO_EDITORIAL_ACCEPTANCE_ROOT for one real local render')
class RealEditorialAcceptance(unittest.TestCase):
    def test_one_real_melo_editorial_video_and_old_media_contract(self):
        root=Path(os.environ['VIDEO_EDITORIAL_ACCEPTANCE_ROOT']).resolve()
        self.assertTrue(root.is_relative_to(Path('data/video_quality_iteration').resolve()))
        self.enterContext(patch('socket.socket.connect',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')))
        job=EditorialJob(root);receipt=job.render()
        self.assertEqual(receipt['voice_engine'],'MeloTTS');self.assertTrue(receipt['decoded'])
        self.assertEqual(receipt['external_api_calls'],0);self.assertFalse(receipt['publish_ready'])
        self.assertEqual(receipt['external_ai_clip_count'],0);self.assertEqual(receipt['external_clip_repeats'],0)
        self.assertAlmostEqual(receipt['duration'],60,places=2)
        timeline=json.loads((root/'timeline.json').read_text())
        self.assertEqual(len(timeline['scenes']),10);self.assertEqual(timeline['scenes'][0]['end'],3)
        self.assertTrue(all(t['start']<t['end']<=60.001 for t in timeline['captions']))
        self.assertTrue((root/'captions.srt').stat().st_size>0)
        with self.assertRaisesRegex(CompanyError,'render_not_replayable'):job.render()
        old=Path('data/video_ai_clip_review/20261109T161931_KST/shorts/preview.mp4')
        before=probe(old)
        run_command(['ffmpeg','-nostdin','-v','error','-i',str(old),'-f','null','-'],stage='ffmpeg_decode')
        Store.atomic(root/'baseline_media_check.json',dict(exists=True,decoded=True,media=before))
