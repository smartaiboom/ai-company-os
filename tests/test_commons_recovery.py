from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from autonomous_company import CompanyError, digest
from commons_discovery import candidates, diagnostic_store
from commons_recovery import (RelevanceWorker, action, offer, prefilter, query_unit, recovery_media,
                             recovery_path, status, store_for_recovery)
from tests.test_commons_discovery import fixture


def setup(manager, plan):
    old=diagnostic_store(manager,plan)
    row={'id':'commons-1','title':'File:Unclear.png','scene_ids':['scene-1'],'reviewable':True,
         'mime':'image/png','url':'https://upload.wikimedia.org/wikipedia/commons/e/e1/Unclear.png',
         'license_url':'https://creativecommons.org/licenses/by/4.0/'}
    old.root.mkdir()
    old.write('candidates.json',{'candidates':[row],'rejected_unsafe':0})
    old.write('done.json',{'fixture':True})


class CommonsRecoveryTests(TestCase):
    def test_scoped_search_and_strict_model_evidence(self):
        with TemporaryDirectory() as folder:
            manager=SimpleNamespace(root=Path(folder),acceptance_project='fixture',
                contract=dict(input=dict(approved_plan_hash='approved',storyboard=[dict(scene_id='scene-1',caption='예시')])))
            plan=dict(scenes=[dict(scene_id='scene-1',request='Use clip showing Example World gameplay in a cave.')])
            setup(manager,plan)
            scope=offer(manager,plan,[])
            self.assertLessEqual(scope['max_searches'],8)
            self.assertEqual(scope['max_downloads'],0)
            q=scope['queries'][0]
            params=parse_qs(urlsplit(recovery_path(q)).query)
            self.assertIn('intitle:"Example World"',params['gsrsearch'][0])
            self.assertIn('categories',params['prop'][0])
            self.assertEqual(query_unit(q)['payload_sha256'],digest(recovery_path(q)))
            w=RelevanceWorker(Path(folder),{'input':{'pairs':[dict(scene_id='scene-1',candidate_id='example',
                metadata=['File:Example World gameplay.webm'],subjects=['Example World'],video=True,
                illustration_allowed=False)]}})
            row=dict(scene_id='scene-1',candidate_id='example',decision='suitable',depiction='gameplay',
                     evidence='Example World gameplay',reason='제목 확인')
            w.validate_plan(dict(assessments=[row]))
            for output in ([{**row,'evidence':'Invented example'}],[{**row,'evidence':'gameplay'}],
                           [{**row,'depiction':'illustrative'}],[row,row]):
                with self.assertRaisesRegex(CompanyError,'commons_relevance_invalid'):
                    w.validate_plan(dict(assessments=output))

    def test_screened_metadata_and_failed_worker_cannot_replay(self):
        key='fixture-relevance-key-123'
        with TemporaryDirectory() as folder, patch.dict('os.environ',GEMINI_API_KEY=key,
                GEMINI_PRODUCTION_PROJECT_API_KEY=key):
            root=Path(folder)
            manager=SimpleNamespace(root=root,acceptance_project='fixture',
                contract=dict(input=dict(approved_plan_hash='approved',storyboard=[dict(scene_id='scene-1',caption='예시')])))
            plan=dict(scenes=[dict(scene_id='scene-1',request='Use clip showing Example World gameplay.')])
            setup(manager,plan)
            old={p:p.read_bytes() for p in (root/'commons_diagnostic').glob('*.json')}
            proof=offer(manager,plan,[])
            args=(manager,plan,[],True)
            action(*args,'production-relevance-approve',dict(confirmed=True,review_hash=digest(proof)))
            good=fixture()
            good['title']='File:Example World gameplay.webm'
            good['categories']=[dict(ns=14,title='Category:Example World'),dict(ns=0,title='excluded')]
            good['imageinfo'][0]['extmetadata']['ImageDescription']={'value':'<b>Example World gameplay</b>'}
            rows,_=candidates({'query':{'pages':[good]}},'scene-1',include_context=True)
            self.assertEqual(rows[0]['categories'],['Category:Example World'])
            self.assertEqual(rows[0]['description'],'Example World gameplay')
            scene={'subjects':['Example World'],'illustration_allowed':False}
            self.assertEqual(prefilter({**rows[0],'title':'File:Cosplay.png'},scene),'unrelated_depiction')
            self.assertEqual(prefilter({**rows[0],'reviewable':False},scene),'rights_ineligible')
            with patch('commons_discovery.search_commons',return_value={'query':{'pages':[good]}}) as search, patch(
                    'commons_recovery.run_worker',side_effect=CompanyError('commons_relevance_invalid')) as worker:
                with self.assertRaisesRegex(CompanyError,'commons_relevance_invalid'):
                    action(*args,'production-relevance-run',{})
                self.assertEqual(search.call_count,1)
                self.assertEqual(worker.call_count,1)
                self.assertEqual(status(manager,plan,[])['status'],'stopped')
                with self.assertRaisesRegex(CompanyError,'owner_policy_exhausted'):
                    action(*args,'production-relevance-run',{})
            self.assertEqual(recovery_media(manager,plan),{})
            self.assertTrue(all(p.read_bytes()==data for p,data in old.items()))
            self.assertIn('relevance',store_for_recovery(manager,plan).attempts())

    def test_empty_search_skips_model_when_every_candidate_is_rights_ineligible(self):
        key='fixture-relevance-key-123'
        with TemporaryDirectory() as folder, patch.dict('os.environ',GEMINI_API_KEY=key,
                GEMINI_PRODUCTION_PROJECT_API_KEY=key):
            manager=SimpleNamespace(root=Path(folder),acceptance_project='fixture',
                contract=dict(input=dict(approved_plan_hash='approved',storyboard=[dict(scene_id='scene-1',caption='예시')])))
            plan=dict(scenes=[dict(scene_id='scene-1',request='Use clip showing Example World gameplay.')])
            old=diagnostic_store(manager,plan)
            old.root.mkdir()
            bad=fixture(missing='Artist')
            found,_=candidates({'query':{'pages':[bad]}},'scene-1')
            old.write('candidates.json',{'candidates':found,'rejected_unsafe':0})
            old.write('done.json',{'fixture':True})
            scope=offer(manager,plan,[])
            args=(manager,plan,[],True)
            action(*args,'production-relevance-approve',dict(confirmed=True,review_hash=digest(scope)))
            with patch('commons_discovery.search_commons',return_value={}) as search, patch('commons_recovery.run_worker') as run:
                action(*args,'production-relevance-run',{})
                run.assert_not_called()
                self.assertEqual(search.call_count,scope['max_searches'])
            self.assertEqual(status(manager,plan,[])['status'],'empty')
