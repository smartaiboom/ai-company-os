from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from autonomous_company import CompanyError, digest
from commons_discovery import (accepted_media, candidates, diagnostic_action, diagnostic_status,
                               original_url, request_path, search_unit, store_for)
from tests.test_commons_discovery import fixture


class CommonsRejectionTests(TestCase):
    def test_documented_imageinfo_provenance_is_removed_without_loosening_download_urls(self):
        base='https://upload.wikimedia.org/wikipedia/commons/e/e1/Forschung_zur_Hohen_Birga_an_der_Universit%C3%A4t_Innsbruck.webm'
        provenance='utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original'
        row=fixture(url=base+'?'+provenance)
        diag={}
        found,rejected=candidates({'query':{'pages':[row]}},'scene-1',diagnostics=diag)
        self.assertEqual(rejected,0)
        self.assertEqual(found[0]['url'],base)
        self.assertTrue(diag['pages'][0]['provenance_removed'])
        self.assertNotIn('utm_source',str(diag))
        with self.assertRaisesRegex(CompanyError,'commons_unsafe_file_url'):
            original_url(row['imageinfo'][0]['url'],'video/webm')
        for url in (base+'?'+provenance+'&token=secret',base+'?'+provenance+'&utm_campaign=imageinfo',
                    base+'?'+provenance+'#x',base.replace('upload.wikimedia.org','127.0.0.1')+'?'+provenance,
                    base.replace('Forschung','%2e%2e%2fX')+'?'+provenance,
                    base.replace('%C3%A4','%GG')+'?'+provenance):
            with self.subTest(url=url):
                self.assertEqual(candidates({'query':{'pages':[fixture(url=url)]}},'scene-1'),([],1))

    def test_individual_and_combined_errors_and_rights_are_separate(self):
        cases=[(None,['page_structure'])]
        for key,value,code in [('ns',0,'file_namespace'),('pageid',False,'page_id'),
                               ('title','Category:Fixture','file_title'),('imageinfo',None,'imageinfo_missing'),
                               ('imageinfo',{},'imageinfo_shape')]:
            page=fixture()
            page[key]=value
            cases.append((page,[code]))
        for key,value,code in [('mime','video/ogg','mime'),('mediatype','MULTIMEDIA','media_type'),
                               ('url','https://localhost/file.webm','original_url_invalid'),
                               ('size','100','size_invalid'),('size',64*1024**2+1,'size_limit')]:
            page=fixture()
            page['imageinfo'][0][key]=value
            cases.append((page,[code]))
        missing=fixture()
        del missing['imageinfo'][0]['url']
        cases.append((missing,['original_url_missing']))
        multiple=fixture()
        multiple['imageinfo'][0].update(mime='not-a-media-type',mediatype='UNKNOWN',url='https://bad.example/',
                                        size=10**10)
        cases.append((multiple,['mime','media_type','original_url_invalid','size_limit']))
        for page,expected in cases:
            snapshot={}
            found,rejected=candidates(dict(query=dict(pages=[page])),'scene-1',diagnostics=snapshot)
            self.assertEqual((found,rejected),([],1))
            self.assertEqual(snapshot['pages'][0]['technical_reasons'],expected)
            self.assertEqual(snapshot['technical_counts'],dict.fromkeys(expected,1))
        image=fixture(missing='AttributionRequired')
        image['title']='File:someone@example.test.jpg'
        image['imageinfo'][0].update(mime='image/jpeg',mediatype='BITMAP',
              url='https://upload.wikimedia.org/wikipedia/commons/e/e1/Example.jpg',size=8*1024**2)
        diag={}
        found,rejected=candidates(dict(query=dict(pages=[image])),'scene-1','image',diag)
        self.assertEqual(rejected,0)
        self.assertFalse(found[0]['reviewable'])
        self.assertEqual(diag['rights_counts'],{'attribution_requirement_unverified':1})
        self.assertNotIn('someone@',str(diag))
        image['imageinfo'][0]['size']+=1
        self.assertEqual(candidates(dict(query=dict(pages=[image])),'scene-1','image'),([],1))
        with self.assertRaisesRegex(CompanyError,'commons_response_shape'):
            candidates({'query':{'pages':{'42':fixture()}}},'scene-1',diagnostics=diag)
        self.assertEqual(diag['response_issue'],'pages_shape')
        diag={}
        self.assertEqual(candidates({'query':{'pages':[fixture(),fixture()]}},'scene-1',diagnostics=diag),([],2))
        self.assertEqual(diag['technical_counts'],{'duplicate_page_id':2})

    def test_single_independent_diagnostic_and_candidate_handoff_preserve_history(self):
        key='fixture-diagnosis-test-only-key'
        with TemporaryDirectory() as folder, patch.dict('os.environ',GEMINI_API_KEY=key,
                GEMINI_PRODUCTION_PROJECT_API_KEY=key):
            root=Path(folder)
            manager=SimpleNamespace(root=root,acceptance_project='fixture',
                                    contract=dict(input=dict(approved_plan_hash='approved')))
            plan=dict(scenes=[])
            old=store_for(manager,plan,adaptive=True)
            row=dict(scene_id='scene-2',scene_ids=['scene-2'],unit_id='scene-2-image',media='image',query='Example World')
            unit=search_unit(row)
            scope={**old.proposal([unit]),'queries':[row]}
            old.approve(scope,digest(scope),key)
            reserve=old.reserve(key,unit,unit['payload_sha256'])
            old.write('metadata-scene-2-image.json',dict(candidates=[],rejected=5))
            old.finish(reserve,'completed')
            old.write('done.json',{'fixture':True})
            hashes={p:p.read_bytes() for p in old.root.glob('*.json')}
            s=diagnostic_status(manager,plan)
            self.assertEqual(s['proposal']['max_searches'],1)
            self.assertEqual(s['proposal']['max_downloads'],0)
            self.assertEqual(s['proposal']['fallback_max_calls'],0)
            self.assertEqual(s['proposal']['previous_request_sha256'],unit['payload_sha256'])
            with patch('commons_discovery.search_commons') as lookup:
                with self.assertRaisesRegex(CompanyError,'owner_policy_required'):
                    diagnostic_action(manager,plan,'production-diagnostic-run',{})
                diagnostic_action(manager,plan,'production-diagnostic-approve',
                                  dict(confirmed=True,review_hash=s['review_hash']))
                lookup.assert_not_called()
                image=fixture()
                image['title']='File:Example.png'
                image['imageinfo'][0].update(mime='image/png',mediatype='BITMAP',
                    url='https://upload.wikimedia.org/wikipedia/commons/e/e1/Example.png'
                        '?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original')
                lookup.return_value={'query':{'pages':[image]}}
                diagnostic_action(manager,plan,'production-diagnostic-run',{})
                lookup.assert_called_once_with(request_path('Example World','image'))
                with self.assertRaisesRegex(CompanyError,'owner_policy_exhausted'):
                    diagnostic_action(manager,plan,'production-diagnostic-run',{})
            s=diagnostic_status(manager,plan)
            self.assertEqual(s['status'],'review')
            self.assertEqual(s['search_trace'][0]['diagnostics']['returned'],1)
            self.assertEqual(accepted_media(manager,plan,diagnostic=True),{})
            diagnostic_action(manager,plan,'production-diagnostic-rights',
                              dict(result_sha256=s['result_sha256'],confirmed=True,accepted=['commons-42']))
            from asset_editing import registries
            self.assertIn('commons-42',registries(root,manager,plan)[2])
            self.assertTrue(all(path.read_bytes()==value for path,value in hashes.items()))
