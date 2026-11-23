from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from review_export import assemble, generate


class ReviewExportTests(TestCase):
    def sample(self):
        pid='company-062d79eeabeb4e5baab3d60ec462db5f'
        project=dict(id=pid,goal='Private goal never publish',
                     representative=dict(audience='Private audience never publish',
                                         constraints={'notes':'Entire private feedback never publish'}))
        rows=[
            dict(id='internal-good-id',scope='api_metric',origin='youtube_data_api',url='https://youtu.be/abcdefghijk',
                 title='Minecraft | example',excerpt='YouTube Data API views=12; duration_seconds=25. '
                 'A top search sample, Shorts format and rights unverified.',
                 observed_at='2026-11-23T15:34:27+09:00',source_date='2026-11-23T01:00:00Z'),
            dict(id='internal-bad-id',scope='api_metric',origin='youtube_data_api',url='https://youtu.be/abcdefghij2',
                 title='tvly-secret /home/private',excerpt='YouTube Data API views=13; duration_seconds=29. '
                 'A top search sample, Shorts format and rights unverified.',
                 observed_at='2026-11-23T15:34:27+09:00',source_date='2026-11-23T01:00:00Z'),
            dict(id='wrong-host',scope='api_metric',origin='youtube_data_api',url='https://example.invalid/token',
                 title='Unsafe',excerpt='raw external response')
        ]
        report=dict(version=4,at='2026-11-23T15:35:01+09:00',provenance='provider_model_claim',
                    staff=dict(observations=[dict(status='observed',sources=rows)],
                        feasibility='private raw staff text'),
                    manager=dict(action='hold',note='internal cost and key',
                        topics=[dict(game='Minecraft',title='private manager title',length='25초',
                                     rationale='private rationale',source_ids=['internal-good-id'])]))
        history=[dict(report=report,decision=None)]
        store=SimpleNamespace(attempts=lambda:{'research-1':{'result':{'status':'completed','secret':'ignore'}}})
        return project,history,store

    def test_allowlisted_export_omits_private_text(self):
        project,history,store=self.sample()
        text=assemble(project,history,store).decode()
        self.assertIn('Minecraft example',text)
        self.assertIn('2026-11-23 10:00:00 KST',text)
        self.assertIn('제목 비공개',text)
        for value in (project['id'],'private','tvly-','internal','example.invalid','raw external'):
            self.assertNotIn(value,text)
        self.assertIn('보류',text)
        self.assertIn('예약 1회 / 완료 1회',text)

    def test_fixed_local_file_tracks_current_version_and_old_public_ref(self):
        project,history,store=self.sample()
        old=assemble(project,history,store)
        store.read=lambda _name: {'fixture':True}
        with TemporaryDirectory() as temp,patch('review_export.LOCAL_ROOT',Path(temp)),patch(
                'review_export.eligible',return_value=True),patch('review_export.versions',return_value=({},store,history)),patch(
                'review_export.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=old)):
            first=generate(None,project)
            self.assertTrue(first['shared'])
            path=Path(temp)/project['id']/'latest.md'
            first_stat=path.stat().st_mtime_ns
            self.assertEqual(generate(None,project),first)
            self.assertEqual(path.stat().st_mtime_ns,first_stat)
            history[-1]['report']['version']=5
            second=generate(None,project)
            self.assertFalse(second['shared'])
            self.assertIn('보고서 v5',path.read_text())
            self.assertEqual(list(path.parent.iterdir()),[path])
