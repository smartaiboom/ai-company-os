"""User-feedback scope, real-file assets and voice gating; no model downloads or synthesis."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autonomous_company import CompanyError,Store
from audience_visual_review import assess,render_motion_study,tts_candidate_gate,voice_comparison_ready
from local_melo_tts import file_hash
from quality_feedback import ExperienceJournal
from quality_provider import experience_context,validate_inputs
from quality_workflow import capabilities


class AudienceGateTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('socket.socket.connect',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')))

    def plan(self):
        return dict(audience='직장인 초보자',topic='원문 날짜 대조',card_seconds_limit=6,card_continuous_limit=3,
            scenes=[dict(id=f'scene-{i}',seconds=6,kind='document_demo',asset_id=f'asset-{i}',
                narration='원문과 날짜를 대조해요.',role='원문 선택/강조 동작') for i in range(10)])

    def assets(self):
        result={}
        for i in range(10):
            path=self.root/f'{i}.png';path.write_bytes(b'owned-asset-'+str(i).encode())
            result[f'asset-{i}']=dict(available=True,file=path.name,sha256=file_hash(path),duration=6,motion_verified=True,rights_verified=False)
        return result

    def test_missing_fake_or_changed_assets_do_not_pass(self):
        p=self.plan();a=self.assets()
        self.assertFalse(assess(p,a,asset_root=self.root)['render_ready'])
        a['asset-0']['file']='missing.png'
        a['asset-1']['sha256']='0'*64
        a['asset-2']['file']='../escaped.png'
        a['asset-3']['file']=None
        (self.root/'link.png').symlink_to(self.root/'4.png');a['asset-4']['file']='link.png'
        r=assess(p,a,asset_root=self.root)
        self.assertEqual(sum(i['issue']=='asset_unverified' for i in r['issues']),5)
        self.assertFalse(r['publish_ready'])

    def test_card_repetition_duration_and_unsupported_motion_block(self):
        p=self.plan();a=self.assets()
        p['scenes'][0]['kind']=p['scenes'][1]['kind']='text_card'
        p['scenes'][2]['kind']=p['scenes'][3]['kind']='footage'
        p['scenes'][3]['asset_id']=p['scenes'][2]['asset_id']
        a['asset-2']['duration']=2;a['asset-4']['motion_verified']=False
        issues={i['issue'] for i in assess(p,a,asset_root=self.root)['issues']}
        self.assertTrue({'too_much_static_card','footage_reused','source_duration_shortfall','demo_motion_unverified',
                         'replacement_voice_pending'}.issubset(issues))
        p['card_seconds_limit']=60
        with self.assertRaises(CompanyError):assess(p,a,asset_root=self.root)

    def test_actual_user_feedback_uses_scoped_existing_journal_contract(self):
        # Literal from the user's instruction, not a fabricated model judgment.
        original='MeloTTS 음성이 최근 자연스러운 AI 음성 서비스와 비교해 어색함.'
        j=ExperienceJournal(self.root/'new_feedback');key=j.create()
        record=j.record(key,original,dict(project='two_user_viewed_previews',domain='video',target_segment='직장인 초보자',
            issue='음성 어색함',positive_preference='자연스러운 한국어',proposed_correction='동일 대본 음성 A/B 청취',
            evidence='실제 사용자 시청 피드백',source='user_instruction_20261110',confidence=.9,verification='hypothesis'),provenance='user_structured')
        selected=j.select(key,domain='video',target_segment='직장인 초보자')
        self.assertEqual(selected['selected'][0]['original_text'],original)
        self.assertEqual(record['extraction_source'],'user_structured')
        self.assertFalse(j.select(key,domain='video',target_segment='어린이')['selected'])
        inputs=dict(domain='video',target_segment='직장인 초보자',answers={},constraints={},capabilities=capabilities(),
            experiences=experience_context(selected),feedback_text='')
        validate_inputs(inputs)
        j.withdraw(key,record['id'],'사용자 철회')
        self.assertFalse(j.select(key,domain='video',target_segment='직장인 초보자')['selected'])

    def test_download_memory_and_voice_comparison_remain_separate_gates(self):
        r=tts_candidate_gate(download_approved=False,installed=False,available_memory_bytes=3800000000,free_disk_bytes=11000000000)
        self.assertIn('model_download_approval_required',r['blockers'])
        self.assertIn('insufficient_memory_headroom_for_unbenchmarked_cpu_run',r['blockers'])
        self.assertFalse(voice_comparison_ready(dict(state='codec_ok'),self.root))
        self.assertFalse(voice_comparison_ready(dict(state='user_preferred_B',evaluator='model_claim'),self.root))
        self.assertFalse(voice_comparison_ready(dict(state='user_preferred_B',evaluator='user_listening',script_hash='a'*64,A={},B={}),self.root))


@unittest.skipUnless(os.getenv('AUDIENCE_VISUAL_REVIEW_ROOT'),'Set AUDIENCE_VISUAL_REVIEW_ROOT for one real 15s silent study')
class RealVisualStudy(unittest.TestCase):
    def test_existing_footage_and_authored_demo_not_a_finished_sixty_second_short(self):
        root=Path(os.environ['AUDIENCE_VISUAL_REVIEW_ROOT']).resolve()
        self.assertTrue(root.is_relative_to(Path('data/video_quality_iteration').resolve()))
        self.enterContext(patch('socket.socket.connect',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')))
        result=render_motion_study(root/'motion_study','data/video_ai_clip_inbox',
                                  ['Adult_beginner_using_laptop_356cf95b.mp4','scene-2.mp4'])
        self.assertEqual(result['duration'],15);self.assertFalse(result['audio']);self.assertFalse(result['publish_ready'])
        self.assertEqual(result['looped_footage_seconds'],0)
        self.assertEqual(len(set(result['demo_frame_hashes'])),3)
        with self.assertRaises(FileExistsError):render_motion_study(root/'motion_study','data/video_ai_clip_inbox',
                                  ['Adult_beginner_using_laptop_356cf95b.mp4','scene-2.mp4'])
