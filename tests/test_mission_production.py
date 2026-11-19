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
