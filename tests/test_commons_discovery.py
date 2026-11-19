from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from autonomous_company import CompanyError, digest
from commons_discovery import (accepted_media, action, candidates, original_url, proposal,
                               queries, request_path, status, unmatched_scenes)


def fixture(number=42, *, missing=None, url=None):
    meta=dict(LicenseShortName='CC BY-SA 4.0',LicenseUrl='https://creativecommons.org/licenses/by-sa/4.0/',
              Artist='<a>Example Artist</a><script>ignored</script>', Credit='Original uploader work',
              AttributionRequired='true')
    if missing:
        meta.pop(missing)
    return dict(pageid=number,ns=6,title=f'File:Example_{number}.webm',imageinfo=[
        dict(mime='video/webm',mediatype='VIDEO',sha1='a'*40,url=url or
             f'https://upload.wikimedia.org/wikipedia/commons/a/ab/Example_{number}.webm',
             extmetadata={key:{'value':value} for key,value in meta.items()})])


class CommonsDiscoveryTests(TestCase):
    def test_metadata_rights_paths_and_untrusted_fields(self):
        info=dict(query=dict(pages=[fixture(),fixture(43,missing='Artist'),
            fixture(44,missing='AttributionRequired'),fixture(45,url='https://127.0.0.1/trap.webm')]))
        rows,rejected=candidates(info,'scene-1')
        self.assertEqual(rejected,1)
        self.assertEqual(rows[0]['creator'],'Example Artist')
        self.assertTrue(rows[0]['share_alike'] and rows[0]['reviewable'])
        self.assertFalse(rows[1]['reviewable'] or rows[2]['reviewable'])
        self.assertTrue(rows[0]['original_page'].startswith('https://commons.wikimedia.org/wiki/File:'))
        for path in ('https://upload.wikimedia.org/wikipedia/commons/a/ab/%2e%2e%2Fa.webm',
                     'https://upload.wikimedia.org/wikipedia/commons/a/ab/a.webm?key=x',
                     'https://upload.wikimedia.org.evil.example/wikipedia/commons/a/ab/a.webm',
                     'https://upload.wikimedia.org/wikipedia/commons/a/ab/a.mp4'):
            with self.assertRaisesRegex(CompanyError,'commons_unsafe_file_url'):
                original_url(path,'video/webm')
        self.assertEqual(unmatched_scenes(['scene-1','scene-2'],lambda _: ['same']),['scene-2'])

    def test_policy_keeps_empty_duplicates_and_failures_distinct(self):
        key='fixture-project-credential-123'
        with patch.dict('os.environ',GEMINI_API_KEY=key,GEMINI_PRODUCTION_PROJECT_API_KEY=key):
            for mode in ('found','empty','failed'):
                with TemporaryDirectory() as folder:
                    manager=SimpleNamespace(root=Path(folder),acceptance_project='fixture',
                                            contract=dict(input=dict(approved_plan_hash='approved')))
                    plan=dict(scenes=[dict(scene_id='scene-1',request='Use operator clip q0:oldid showing grassland motion.'),
                                      dict(scene_id='scene-2',request='Use operator clip showing forest motion.')])
                    args=(manager,plan,[],False)
                    run='production-discovery-run'
                    offer=proposal(*args)
                    self.assertEqual(len(queries(plan,[])),2)
                    self.assertNotIn('oldid',request_path(offer['queries'][0]['query']))
                    action(*args,'production-discovery-approve',dict(confirmed=True,review_hash=digest(offer)))
                    response=dict(query=dict(pages=[fixture()])) if mode=='found' else {}
                    with patch('commons_discovery.search_commons') as transport:
                        if mode=='failed':
                            transport.side_effect=CompanyError('commons_response_failed')
                            with self.assertRaisesRegex(CompanyError,'commons_response_failed'):
                                action(*args,run,{})
                            self.assertEqual(transport.call_count,1)
                            self.assertEqual(status(*args)['status'],'stopped')
                        else:
                            transport.return_value=response
                            action(*args,run,{})
                            self.assertEqual(transport.call_count,2)
                            state=status(*args)
                            self.assertEqual(state['status'],'review' if mode=='found' else 'empty')
                            if mode=='found':
                                self.assertEqual(len(state['result']['candidates']),1)
                                review=dict(result_sha256=state['result_sha256'],accepted=['commons-42'],confirmed=True)
                                with self.assertRaisesRegex(CompanyError,'commons_rights_review_changed'):
                                    action(*args,'production-discovery-rights',{**review,'result_sha256':'bad'})
                                self.assertFalse(accepted_media(manager,plan))
                                action(*args,'production-discovery-rights',review)
                                self.assertEqual(accepted_media(manager,plan)['commons-42']['scene_ids'],['scene-1','scene-2'])
                        with self.assertRaisesRegex(CompanyError,'owner_policy_exhausted'):
                            action(*args,run,{})

    def test_search_transport_bounds_and_rejects_redirect(self):
        import socket
        from commons_discovery import HOST, MAX_BYTES, search_commons
        from tests.test_official_media import Response
        with patch('commons_discovery._global_addresses',return_value=(socket.AF_INET,('8.8.8.8',443))), \
                patch('commons_discovery._PinnedHTTPS') as connection:
            page=connection.return_value
            path=request_path('example search')
            page.getresponse.return_value=Response(302,'application/json',b'{}')
            with self.assertRaisesRegex(CompanyError,'commons_response_failed'):
                search_commons(path)
            page.request.assert_called_once()
            self.assertEqual(connection.call_args.args[0],HOST)
            page.getresponse.return_value=Response(200,'application/json',b' '* (MAX_BYTES+1))
            with self.assertRaisesRegex(CompanyError,'commons_response_limit'):
                search_commons(path)
