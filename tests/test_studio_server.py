from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from autonomous_company import CompanyError, Store
from studio_server import Studio, byte_range


class StudioTests(unittest.TestCase):
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
