from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from autonomous_company import CompanyError, digest, now
from mission_production import SceneVoice, ProductionManager


class MissionProductionTests(TestCase):
    def test_scene_voice_scope_and_separate_consent_are_exact(self):
        with TemporaryDirectory() as temp:
            folder=Path(temp)/'voice'
            scene=dict(scene_id='scene-1',start=0,end=3,speech_style='짧고 또렷하게')
            voice=SceneVoice(folder,'v2-plan','manager-plan',scene,
                             dict(model='gemini-3.8-flash-lite-tts',voice='Kore'),'승인된 문장입니다.')
            voice.create_scene()
            job,scope,raw=voice._load()
            self.assertEqual((scope['scene_id'],scope['local_max_seconds'],scope['requests']),('scene-1',3,1))
            self.assertIn('짧고 또렷하게'.encode(),raw)
            key='fixture-scene-credential-value'
            stamp=now()
            evidence=dict(project=scope['project'],model=scope['model'],tier='Free',billing='disabled',
                model_access='available',region_supported=True,paid_fallback=False,remaining_requests=1,
                remaining_input_tokens=2048,remaining_output_tokens=1024,checked_at=stamp,
                expires_at=(datetime.fromisoformat(stamp)+timedelta(minutes=30)).isoformat(),
                method='owner_aistudio_review_not_independent_verification',evidence_sha256=digest('fixture'),
                source_url='https://aistudio.google.com/',observation='A fixture attestation only, for the local test.')
            voice.verify_key(key,key,evidence)
            review=voice.review(key)
            with patch.dict('os.environ',GEMINI_PRODUCTION_TTS_ENABLED='1'):
                with self.assertRaises(CompanyError):
                    voice.execute(key)
                with self.assertRaisesRegex(CompanyError,'tts_explicit_consent_required'):
                    voice.approve(review['review_hash'],key,owner_confirmed=True)
                voice.approve(review['review_hash'],key,owner_confirmed=True,accept_google_data_policy=True)
                with self.assertRaisesRegex(CompanyError,'tts_active_key_changed'):
                    voice.execute('another-fixture-credential')
                with patch.object(voice,'_send_authorized',return_value='fixture') as send:
                    self.assertEqual(voice.execute(key),'fixture')
                    self.assertEqual(send.call_args.args[3],raw)
                altered=SceneVoice(folder,'v2-plan','manager-plan',{**scene,'speech_style':'변경된 스타일'},
                                   dict(model=job['model'],voice=job['voice']),'승인된 문장입니다.')
                with self.assertRaisesRegex(CompanyError,'tts_scope_changed'):
                    altered.execute(key)

    def test_manager_requires_approved_scene_order_and_supported_voice(self):
        with TemporaryDirectory() as temp:
            manager=ProductionManager(Path(temp),dict(input={'storyboard':[{'scene_id':'scene-1'}],
                                                             'tools':{'melo_installed':False}}))
            value=dict(voice=dict(tool='gemini_scene',model='gemini-3.8-flash-tts',voice='Kore',
                                  rationale='장면 흐름에 맞춘 한국어 전달'),
                       fit='letterbox',timeline='승인 장면 경계 유지',review_criteria=['음성 확인'],
                       work_order=['소스 확보'],scenes=[dict(scene_id='scene-1',source='operator_clip',
                           request='해당 게임의 승인 사용권이 있는 장면',direction='동작 중심',
                           transition='cut',speech_style='차분하고 정확하게')])
            manager.validate_plan(value)
            with self.assertRaisesRegex(CompanyError,'production_scene_mismatch'):
                manager.validate_plan({**value,'scenes':[{**value['scenes'][0],'scene_id':'scene-2'}]})
            with self.assertRaisesRegex(CompanyError,'melo_runtime_missing'):
                manager.validate_plan({**value,'voice':{**value['voice'],'tool':'melo_local','model':'local','voice':'local'}})

    def test_source_assignment_rejects_unregistered_or_duplicate_assets(self):
        from production_sources import SourceAssignment, source_capabilities

        with TemporaryDirectory() as temp:
            storyboard = [dict(scene_id='scene-1'), dict(scene_id='scene-2')]
            catalog = {'owned': {'sha256': 'a'*64}, 'same-bytes': {'sha256': 'a'*64}}
            worker = SourceAssignment(Path(temp), dict(input=dict(storyboard=storyboard,
                source_tools=source_capabilities(catalog))))
            item = dict(scene_id='scene-1',route='local_library',asset_id='owned',
                        rationale='등록 후보',next_step='권리 기록 확인',suitability_check='실제 장면 확인')
            alternative = {**item,'scene_id':'scene-2','asset_id':'none','route':'official_direct_media'}
            result = dict(scenes=[item,alternative],review_criteria=['동작과 후크의 일치'])
            worker.validate_plan(result)
            for invalid in ({**alternative,'route':'local_library','asset_id':'invented'},
                            {**alternative,'route':'local_library','asset_id':'same-bytes'},
                            {**alternative,'asset_id':'owned'}):
                with self.assertRaisesRegex(CompanyError,'source_library_selection_invalid'):
                    worker.validate_plan({**result,'scenes':[item,invalid]})

    def test_new_scene_receipt_can_record_overrun_without_replacing_legacy_scope(self):
        from mission_production import voice_scene

        with TemporaryDirectory() as temp:
            root = Path(temp)
            scene = dict(scene_id='scene-1',start=0,end=3,narration='승인된 원문')
            manager = ProductionManager(root,dict(input=dict(storyboard=[scene],approved_plan_hash='approved')))
            selected = dict(tool='gemini_scene',model='gemini-3.8-flash-tts',voice='Puck')
            direction = dict(scene_id='scene-1',speech_style='자연스럽게')
            result = dict(voice=selected,scenes=[direction])
            diagnostic = voice_scene(manager,result,'scene-1')
            self.assertEqual(diagnostic.scope['approved_scene_seconds'], 3)
            self.assertEqual(diagnostic.scope['local_max_seconds'], 20)
            legacy = SceneVoice(diagnostic.root,'approved',digest(result),{**scene,**direction},selected,scene['narration'])
            self.assertEqual(legacy.raw, diagnostic.raw)
            legacy.create_scene()
            recovered = voice_scene(manager,result,'scene-1')
            self.assertEqual(recovered._load()[1], legacy.scope)
            self.assertEqual(recovered.scope['local_max_seconds'], 3)

    def test_measured_manager_keeps_frame_bounds_and_requires_a_distinct_total_choice(self):
        from measured_timeline import TimelineManager

        with TemporaryDirectory() as temp:
            worker = TimelineManager(Path(temp),dict(input=dict(approved_total_frames=840,measurements=[
                dict(scene_id='scene-1',min_frames=89,clip_max_frames=100),
                dict(scene_id='scene-2',min_frames=300,clip_max_frames=None)])))
            scenes=[dict(scene_id='scene-1',frames=90,caption_frames=90),
                    dict(scene_id='scene-2',frames=750,caption_frames=400)]
            valid=dict(decision='keep_total',rationale='실측 타임라인',quality_checks='자막 검토',scenes=scenes)
            worker.validate_plan(valid)
            worker.validate_plan({**valid,'decision':'hold','scenes':[]})
            worker.validate_plan({**valid,'decision':'change_total',
                'scenes':[scenes[0],{**scenes[1],'frames':760}]})
            for result in ({**valid,'decision':'change_total'}, {**valid,'decision':'hold'},
                           {**valid,'scenes':list(reversed(scenes))},
                           {**valid,'scenes':[{**scenes[0],'caption_frames':88},scenes[1]]},
                           {**valid,'scenes':[{**scenes[0],'frames':101},{**scenes[1],'frames':739}]}):
                with self.assertRaisesRegex(CompanyError,'invalid_measured_timeline'):
                    worker.validate_plan(result)
