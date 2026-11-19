import struct
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from autonomous_company import CompanyError, digest
from commons_discovery import (accepted_media, action, adaptive_queries, candidates, proposal,
                               request_path, status)
from still_motion import image_dimensions
from tests.test_commons_discovery import fixture


class AdaptiveVisualTests(TestCase):
    def test_structured_queries_use_title_and_separate_media_without_old_request(self):
        old=dict(proposal=dict(queries=[dict(query='Example World moon gameplay elaborate description')]),
                 fallback=dict(options=[dict(scene_id='scene-2',route='licensed_still_motion')]))
        plan=dict(scenes=[dict(scene_id='scene-2',request='Use operator clip q0:abc showing Example World moon gameplay elaborate description.')])
        rows=adaptive_queries(plan,[],old)
        self.assertEqual([(r['query'],r['media']) for r in rows],
                         [('Example World','image'),('Example World','video')])
        self.assertIn('filetype%3Abitmap',request_path('Example World','image'))

    def test_separate_policy_skips_satisfied_wave_and_preserves_legacy_records(self):
        key='fixture-adaptive-test-only-key'
        with TemporaryDirectory() as folder, patch.dict('os.environ',GEMINI_API_KEY=key,
                GEMINI_PRODUCTION_PROJECT_API_KEY=key):
            root=Path(folder)
            manager=SimpleNamespace(root=root,acceptance_project='fixture',
                                    contract=dict(input=dict(approved_plan_hash='approved')))
            plan=dict(scenes=[dict(scene_id='scene-1',request='Use operator clip showing Example World short clip.')])
            arguments=(manager,plan,[],False)
            grant=proposal(*arguments)
            action(*arguments,'production-discovery-approve',dict(confirmed=True,review_hash=digest(grant)))
            with patch('commons_discovery.search_commons',return_value={}):
                action(*arguments,'production-discovery-run',{})
            before={p:p.read_bytes() for p in (root/'commons_discovery').glob('*.json')}
            new=proposal(*arguments,adaptive=True)
            self.assertEqual(new['max_searches'],2)
            action(*arguments,'production-discovery-approve',dict(confirmed=True,review_hash=digest(new)),adaptive=True)
            with patch('commons_discovery.search_commons',return_value={'query':{'pages':[fixture()]}}) as sent:
                action(*arguments,'production-discovery-run',{},adaptive=True)
                self.assertEqual(sent.call_count,1)
                with self.assertRaisesRegex(CompanyError,'owner_policy_exhausted'):
                    action(*arguments,'production-discovery-run',{},adaptive=True)
            self.assertEqual(status(*arguments)['status'],'empty')
            result=status(*arguments,adaptive=True)
            self.assertEqual(result['status'],'review')
            action(*arguments,'production-discovery-rights',dict(confirmed=True,accepted=['commons-42'],
                   result_sha256=result['result_sha256']),adaptive=True)
            self.assertIn('commons-42',accepted_media(manager,plan,adaptive=True))
            self.assertTrue(all(p.read_bytes()==data for p,data in before.items()))

    def test_rejects_oversized_raster_animation_and_svg(self):
        signature=b'\x89PNG\r\n\x1a\n'
        def chunk(tag,content):
            return struct.pack('>I',len(content))+tag+content+b'\0'*4
        def png(width,height,extra=b''):
            return signature+chunk(b'IHDR',struct.pack('>II',width,height)+b'\x08\x02\x00\x00\x00')+extra+chunk(b'IEND',b'')
        with TemporaryDirectory() as folder:
            file=Path(folder)/'source.png'
            file.write_bytes(png(4096,4096))
            with self.assertRaisesRegex(CompanyError,'still_image_pixels_invalid'):
                image_dimensions(file,'image/png')
            file.write_bytes(png(128,128,chunk(b'acTL',b'\0'*8)))
            with self.assertRaisesRegex(CompanyError,'still_image_format_invalid'):
                image_dimensions(file,'image/png')
        candidate=fixture()
        data=candidate['imageinfo'][0]
        data.update(mime='image/svg+xml',mediatype='BITMAP',
                    url='https://upload.wikimedia.org/wikipedia/commons/a/ab/a.svg')
        self.assertEqual(candidates(dict(query=dict(pages=[candidate])),'scene-1','image'),([],1))

    def test_editor_rejects_wrong_scene_and_non_image_extra(self):
        from asset_editing import AssetEditor
        with TemporaryDirectory() as folder:
            catalog={'official:still':dict(frames=None,image=True,scene_ids=['scene-1']),
                     'official:other':dict(frames=None,image=True,scene_ids=['scene-2']),
                     'official:clip':dict(frames=300)}
            worker=AssetEditor(Path(folder),dict(input=dict(candidates=catalog,
                scenes=[dict(scene_id='scene-1',frames=100)])))
            row=dict(scene_id='scene-1',asset_id='official:still',in_frame=0,framing='letterbox_center',
                     transition='cut',caption_position='safe_lower',suitability='적합성 확인',
                     extra_images=[],motion='zoom',label='reference')
            result=dict(action='edit',review_criteria='원본과 설명 확인',scenes=[row])
            worker.validate_plan(result)
            for extra in ('official:other','official:clip','official:still'):
                with self.assertRaisesRegex(CompanyError,'invalid_source_edit'):
                    worker.validate_plan({**result,'scenes':[{**row,'extra_images':[extra]}]})

    def test_shared_first_wave_candidate_leaves_one_scene_for_second_wave(self):
        key='fixture-adaptive-test-only-key'
        with TemporaryDirectory() as folder, patch.dict('os.environ',GEMINI_API_KEY=key,
                GEMINI_PRODUCTION_PROJECT_API_KEY=key):
            manager=SimpleNamespace(root=Path(folder),acceptance_project='fixture',
                                    contract=dict(input=dict(approved_plan_hash='approved')))
            plan=dict(scenes=[dict(scene_id='scene-1',request='Use clip showing Example World open play.'),
                              dict(scene_id='scene-2',request='Use clip showing Another World team play.')])
            args=(manager,plan,[],False)
            old=proposal(*args)
            action(*args,'production-discovery-approve',dict(confirmed=True,review_hash=digest(old)))
            with patch('commons_discovery.search_commons',return_value={}):
                action(*args,'production-discovery-run',{})
            new=proposal(*args,adaptive=True)
            action(*args,'production-discovery-approve',dict(confirmed=True,review_hash=digest(new)),adaptive=True)
            result=dict(query=dict(pages=[fixture()]))
            with patch('commons_discovery.search_commons',side_effect=(result,result,{})) as network:
                action(*args,'production-discovery-run',{},adaptive=True)
                self.assertEqual(network.call_count,3)
            self.assertEqual(len(status(*args,adaptive=True)['result']['candidates']),1)
