from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from autonomous_company import CompanyError
from alternative_production import SCHEMA, StrategyManager
from role_json_schema import S, obj
from task_replanning import strategy_assignment, strategy_schema


class StrategyTests(TestCase):
    def test_common_assignment_works_without_video(self):
        schema=strategy_schema(('local_checks','hold'),obj(target=S))
        inputs=dict(goal='Check journal consistency')
        plan=dict(route='local_checks',reason='Local evidence is available',success_criteria='Check totals',
                  risk='Partial history only',work=[dict(target='journal')])
        assignment=strategy_assignment(plan,schema,inputs,{'local_checks':'accounting'})
        self.assertEqual(assignment['role'],'accounting')
        self.assertEqual(assignment['next_reviewer'],'owner')

    def test_unverified_assets_cannot_create_executable_work(self):
        worker=StrategyManager(Path('/tmp/unused-strategy'),dict(input=dict(scenes=[dict(scene_id='scene-1')],
                                                                             local_ready=True),schema=SCHEMA))
        row=dict(scene_id='scene-1',title='Example',graphic='workflow',labels=['Steps'],camera='hold')
        plan=dict(route='rights_cleared_assets',reason='Potential source',success_criteria='Verify rights',
                  risk='Still unconfirmed',work=[])
        worker.validate_plan(plan)
        with self.assertRaisesRegex(CompanyError,'strategy_invalid'):
            worker.validate_plan({**plan,'work':[row]})
        with self.assertRaisesRegex(CompanyError,'strategy_scene_mismatch'):
            worker.validate_plan({**plan,'route':'local_graphics','work':[{**row,'scene_id':'wrong'}]})

    def test_cutroom_approval_execution_and_playback_without_provider_transport(self):
        import os
        import threading
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen
        from alternative_production import SYSTEM
        from autonomous_gemini35 import ENDPOINT, MODEL
        from studio_server import Studio, make_server

        class Reply(BytesIO):
            status=200

        with TemporaryDirectory() as tmp:
            studio=Studio(Path(tmp)/'studio')
            pid=studio.create(dict(goal='게임 소개',audience='입문자',language='한국어',platform='YouTube Shorts',
                              duration=None,notes='',key='00000000-0000-4000-8000-000000000044'))['id']
            project=studio.workflow.store.load(pid)
            project['representative']['stage']='video_revision'
            studio.workflow.store.save(project)
            worker=StrategyManager(Path(tmp)/'strategy',dict(input=dict(goal='게임 소개',scenes=[
                dict(scene_id='scene-1',narration='내레이션',caption='자막',visual_need='개념 설명',speech_sha256='abc',caption_frames=48)],
                plan_sha256='plan',timeline_sha256='timeline',local_ready=True),schema=SCHEMA,system=SYSTEM))
            spec=dict(tool='portrait_storyboard_v1',width=720,height=1280,series='시범',audio_mode='local_speech',
                      palette=dict(background='#101728',surface='#1A2742',accent='#86C8F1',text='#FFFFFF'),
                      scenes=[dict(title='장면',subtitle='자막',narration='내레이션',seconds=2,transition='cut')])
            from production_video import PORTRAIT_TOOL
            spec['tool']=PORTRAIT_TOOL
            answer=dict(route='local_graphics',reason='설명 자체 그래픽',success_criteria='장면 설명 전달',
                risk='게임 플레이는 미확인',work=[dict(scene_id='scene-1',title='개념',graphic='target',
                                              labels=['설명'],camera='push_in')])
            key='fixture-credential-long-enough'
            env=dict(GEMINI_API_KEY=key,GEMINI_PRODUCTION_PROJECT_API_KEY=key,GEMINI35_MODEL=MODEL,
                     GEMINI35_ENDPOINT=ENDPOINT,GEMINI35_AUTONOMOUS_FREE_ENABLED='1')
            payload=dict(candidates=[dict(finishReason='STOP',content=dict(role='model',
                         parts=[dict(text=json.dumps(answer))]))],usageMetadata=dict(
                         promptTokenCount=10,candidatesTokenCount=10,totalTokenCount=20))
            from copy import deepcopy
            from local_melo_tts import file_hash
            def fixture_render(spec,folder,*,speech,illustrated,caption_frames):
                self.assertTrue(illustrated)
                self.assertEqual(spec['scenes'][0]['narration'],'내레이션')
                path=folder/'video.mp4'
                path.write_bytes(b'fixture-video-bytes')
                return dict(sha256=file_hash(path),decoded=True,duration_seconds=2.0)
            with patch.dict(os.environ,env),patch('goal_dialogue_live.send_once',return_value=Reply(
                    json.dumps(payload).encode())) as provider,patch('alternative_production.setup',
                    side_effect=lambda *_:(worker,deepcopy(spec),None)),patch(
                    'alternative_production.render',side_effect=fixture_render) as renderer,make_server(
                    '127.0.0.1',0,studio) as server:
                thread=threading.Thread(target=server.serve_forever,daemon=True)
                thread.start()
                try:
                    base=f'http://127.0.0.1:{server.server_port}'
                    api=base+'/api/project/workspace/'+pid
                    def call(action=None,body=None):
                        url=api+('/'+action if action else '')
                        req=Request(url,json.dumps(body).encode() if body is not None else None,
                            headers={'Content-Type':'application/json','X-Studio-Token':studio.token})
                        with urlopen(req,timeout=5) as response:
                            return json.load(response)['alternative']
                    call('alternative-prepare',dict(free=True,quota=True,docs=True))
                    pending=call()
                    self.assertEqual(pending,call())
                    call('alternative-consent',dict(confirmed=True,review_hash=pending['review_hash']))
                    proposed=call('alternative-decide',{})
                    self.assertEqual(proposed['status'],'review')
                    with self.assertRaises(HTTPError) as blocked:
                        call('alternative-render',{})
                    with blocked.exception as response:
                        self.assertEqual(response.code,409)
                    assigned=call('alternative-approve',dict(confirmed=True,proposal_sha256=proposed['proposal_sha256']))
                    self.assertEqual(assigned['assignment']['role'],'visual_production')
                    completed=call('alternative-render',{})
                    self.assertEqual(completed['receipt']['quality'],'unassessed')
                    with urlopen(Request(base+completed['url'],headers={'Range':'bytes=0-6'}),timeout=5) as response:
                        self.assertEqual((response.status,response.read()),(206,b'fixture'))
                    evaluated=call('alternative-evaluate',dict(sha256=completed['receipt']['sha256'],feedback='설명이 보입니다.'))
                    self.assertEqual(evaluated['evaluation']['feedback'],'설명이 보입니다.')
                    self.assertEqual(studio.workflow.store.load(pid),project)
                    provider.assert_called_once()
                    renderer.assert_called_once()
                finally:
                    server.shutdown()
                    thread.join()
