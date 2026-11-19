from pathlib import Path
import json
from shutil import which
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import wave

from autonomous_company import CompanyError, Store, digest
from cutroom_review import DRAFT_NAME, QUALITY_DRAFT_NAME, matching_plan, plan_markdown, quality_draft
from representative_workflow import _report
from studio_server import Studio, byte_range


class StudioTests(unittest.TestCase):
    def test_approved_portrait_production_binds_script_and_local_audio(self):
        from local_melo_tts import MeloLocal, file_hash
        from production_video import portrait_font
        from script_quality import script_editor_handoff
        if not (which('ffmpeg') and which('ffprobe') and portrait_font()):
            self.skipTest('requires FFmpeg, ffprobe and a local Korean font')

        def synthesize(_engine, texts, folder):
            clips=[]
            for i, text in enumerate(texts):
                path=folder/f'voice-{i:02}.wav'
                with wave.open(str(path),'wb') as out:
                    out.setparams((1,2,44100,0,'NONE',''))
                    out.writeframes(b'\x40\x01\xc0\xfe'*4410)
                clips.append(dict(file=path.name,text=text,duration=.2,sha256=file_hash(path)))
            return dict(engine='synthetic_test_tone_not_tts',utterances=clips)

        with TemporaryDirectory() as root:
            studio=Studio(root)
            flow=studio.workflow
            pid=flow.create('가상 게임 테스트',audience='예시 시청자')
            project=flow.store.load(pid)
            beats=[dict(start=i,end=i+1,narration=line,caption=line,screen='자체 카드',
                        shot_type='card',source_ref='미확보',source_status='pending',fact_status='illustrative')
                   for i,line in enumerate(('첫 장면입니다.','두 번째 장면입니다.'))]
            script=dict(target_duration=2,narrative_beats=beats)
            writer=dict(role='writer',task_id='writer',revision=1,content=json.dumps(script,ensure_ascii=False))
            editor=dict(role='editor',task_id='editor',revision=1,content=json.dumps(script_editor_handoff(writer),ensure_ascii=False))
            plan=_report(dict(render_spec=None,script=script,task_history=[
                dict(role='writer',versions=[writer]),dict(role='editor',versions=[editor])]),[])
            project['representative'].update(stage='awaiting_plan_approval',plan_versions=[plan],mission_one_job='fixture')
            flow.store.save(project)
            with self.assertRaisesRegex(CompanyError,'representative_stage_mismatch'):
                flow.produce(pid,version=1,sha256=plan['sha256'],changes='미승인',preview_audio='local_speech')
            flow.decide(pid,'plan',version=1,sha256=plan['sha256'],action='approve')
            with patch.object(MeloLocal,'available',return_value=False):
                with self.assertRaisesRegex(CompanyError,'melo_runtime_missing'):
                    flow.produce(pid,version=1,sha256=plan['sha256'],changes='런타임 없음',preview_audio='local_speech')
            self.assertFalse(flow.store.load(pid)['representative']['render_attempts'])
            with patch.object(MeloLocal,'available',return_value=True),patch.object(MeloLocal,'synthesize',autospec=True,side_effect=synthesize):
                video=flow.produce(pid,version=1,sha256=plan['sha256'],changes='합성 신호 검증',preview_audio='local_speech')
            saved=flow.store.load(pid)['representative']
            self.assertEqual(saved['stage'],'awaiting_video_approval')
            self.assertEqual(saved['plan_versions'],[plan])
            receipt=video['render_receipt']
            self.assertEqual((receipt['width'],receipt['height']),(720,1280))
            self.assertTrue(receipt['audio'] and receipt['decoded'])
            self.assertEqual(receipt['voice_engine'],'synthetic_test_tone_not_tts')
            self.assertEqual([item['subtitle_start_seconds'] for item in receipt['review_material']],[0,1])
            self.assertFalse(video['publish_authorized'])

    def test_quality_draft_matches_only_the_undecided_stop_report(self):
        with TemporaryDirectory() as root:
            report = dict(decision='stop', original_action='revise', reason='revision_limit_reached')
            state = dict(status='stopped', job='fixture-job')
            project = dict(id='fixture-project', representative=dict(stage='plan_revision', rework=state))
            path = Path(root)/QUALITY_DRAFT_NAME
            draft = dict(project=project['id'], job=state['job'], report_hash=digest(report), feedback='검토할 초안')
            for fields in (dict(project='another'), dict(job='another'), dict(report_hash='wrong')):
                bad = {**draft, **fields}
                Store.atomic(path, {**bad, 'checksum':digest(bad)})
                self.assertIsNone(quality_draft(root, project, state['job'], report))
            Store.atomic(path, {**draft, 'feedback':'변조', 'checksum':digest(draft)})
            self.assertIsNone(quality_draft(root, project, state['job'], report))
            Store.atomic(path, {**draft, 'checksum':digest(draft)})
            before = path.read_bytes()
            self.assertEqual(quality_draft(root, project, state['job'], report)['feedback'], draft['feedback'])
            self.assertEqual(path.read_bytes(), before)
            state['quality_decision'] = dict(action='hold')
            self.assertIsNone(quality_draft(root, project, state['job'], report))

    def test_revision_draft_requires_matching_project_version_and_checksum(self):
        with TemporaryDirectory() as root:
            studio = Studio(root)
            store = studio.workflow.store
            pid = studio.workflow.create('가상 기획', audience='예시 시청자')
            project = store.load(pid)
            flow = project['representative']
            plan = _report(dict(topic='예시'), [])
            flow.update(stage='awaiting_plan_approval', plan_versions=[plan])
            store.save(project)
            original = store.path(pid).read_bytes()
            draft = dict(project=pid, version=1, report_hash=plan['sha256'], feedback='게임 사례를 보강해 주세요.')
            path = Path(root)/DRAFT_NAME
            for changed in (dict(project='another-project'), dict(version=2), dict(report_hash='0'*64)):
                candidate = {**draft, **changed}
                Store.atomic(path, {**candidate, 'checksum': digest(candidate)})
                self.assertIsNone(studio.detail('workspace', pid)['revision_draft'])
            Store.atomic(path, {**draft, 'feedback':'변조된 내용', 'checksum':digest(draft)})
            self.assertIsNone(studio.detail('workspace', pid)['revision_draft'])
            Store.atomic(path, {**draft, 'checksum':digest(draft)})
            self.assertEqual(studio.detail('workspace', pid)['revision_draft']['feedback'], draft['feedback'])
            self.assertEqual(store.path(pid).read_bytes(), original)
            self.assertEqual(store.load(pid)['representative']['decisions'], [])
            studio.action('workspace', pid, 'decide', dict(stage='plan', version=1, sha256=plan['sha256'],
                          action='request_revision', feedback=draft['feedback'], changes_plan=False))
            self.assertIsNone(studio.detail('workspace', pid)['revision_draft'])
            self.assertEqual(store.load(pid)['representative']['decisions'][-1]['feedback'], draft['feedback'])

    def test_markdown_uses_the_selected_report_and_excludes_private_fields(self):
        private = 'owner@example.test'
        source = dict(url='https://www.youtube.com/watch?v=abcdefghijk', duration_seconds=20,
                      view_count=123, observed_at='2026-11-18', title=private)
        script = dict(target_duration=20, transcript=f'첫 줄\n둘째 줄 {private}',
                      narrative_beats=[dict(start=0, end=20, shot_type='demo', screen='게임 화면',
                                           caption='게임 시작', source_status='pending')])
        first = _report(dict(topic='첫 기획', script=script, research=dict(observations=[source,
                            {**source, 'url':source['url']+'&token=hidden-secret'}]),
                             provider_run=dict(attempts=[dict(signature='private-signature')], web_attempts=[{}])), [])
        second = _report(dict(topic='새 기획', script=script, rework_plan=dict(duration_reason='새 정보량'),
                              call_counts=dict(gemini=5, youtube=0)), [first])
        project = dict(goal='가상 게임', representative=dict(plan_versions=[first, second]))
        original = plan_markdown(project, matching_plan(project, 1, first['sha256']))
        revision = plan_markdown(project, matching_plan(project, 2, second['sha256']))
        self.assertIn('Gemini 1회 · YouTube 1회', original)
        self.assertIn('비교 기준 v1', revision)
        self.assertIn('새 정보량', revision)
        self.assertIn('Gemini 5회 · YouTube 0회', revision)
        self.assertIn(source['url'], original)
        self.assertIn('첫 줄<br>', original)
        for value in (private, 'hidden-secret', 'private-signature', first['sha256']):
            self.assertNotIn(value, original)
        with self.assertRaisesRegex(CompanyError, 'stale_representative_report'):
            matching_plan(project, 2, first['sha256'])

    def test_creation_is_persistently_idempotent_and_planning_uses_workflow(self):
        with TemporaryDirectory() as root:
            studio = Studio(root)
            body = dict(goal='스포츠 뉴스 제작', audience='', language='한국어', platform='YouTube',
                duration=60, notes='가상 예시', key='00000000-0000-4000-8000-000000000001')
            self.assertFalse(studio.dashboard()['projects'])
            first = studio.create(body)
            reopened = Studio(root)
            self.assertEqual(reopened.create(body), first)
            pid = first['id']
            self.assertEqual(len(reopened.dashboard()['projects']), 1)
            detail = reopened.detail('workspace', pid)
            self.assertEqual(detail['stage'], 'goal_submitted')
            self.assertNotIn('creation_key', detail['flow'])
            planning = reopened.action('workspace', pid, 'planning', {})
            self.assertEqual(planning['stage'], 'research_planning')
            self.assertEqual(planning['jobs'][0]['assignments'], [])
            self.assertEqual(reopened.action('workspace', pid, 'planning', {})['jobs'], planning['jobs'])
            with self.assertRaisesRegex(CompanyError, 'representative_stage_mismatch'):
                reopened.action('workspace', pid, 'produce', dict(version=1, sha256='0'*64, changes='test', camera=None))

    def test_readonly_reference_and_media_scope(self):
        with TemporaryDirectory() as root:
            base = Path(root)
            original = Studio(base/'reference')
            pid = original.create(dict(goal='가상 사례', audience='', language='', platform='', duration=None,
                notes='', key='00000000-0000-4000-8000-000000000001'))['id']
            original_path = Store(base/'reference').path(pid)
            before = original_path.read_bytes()
            studio = Studio(base/'workspace', [base/'reference'])
            self.assertTrue(studio.detail('reference-0', pid)['readonly'])
            with self.assertRaisesRegex(CompanyError, 'readonly_project'):
                studio.action('reference-0', pid, 'planning', {})
            for key, project in [('workspace', '../secret'), ('../reference', pid), ('reference-0', pid)]:
                with self.assertRaises(FileNotFoundError):
                    studio.media(key, project, 1, 'video')
            self.assertEqual(original_path.read_bytes(), before)

    def test_range_validation(self):
        self.assertEqual(byte_range(None, 100), (0, 99))
        self.assertEqual(byte_range('bytes=0-15', 100), (0, 15))
        self.assertEqual(byte_range('bytes=90-', 100), (90, 99))
        self.assertEqual(byte_range('bytes=-10', 100), (90, 99))
        for value in ('bytes=-0', 'bytes=101-', 'bytes=20-12', 'bytes=1-2,4-5', 'bytes=-'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                byte_range(value, 100)
