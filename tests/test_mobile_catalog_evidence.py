from datetime import datetime, timedelta
import json
from unittest import TestCase

from autonomous_company import now
from mobile_catalog_evidence import listing, listing_id, verified_games
from web_research import evidence


class MobileCatalogEvidenceTests(TestCase):
    def test_title_link_requires_direct_mobile_game_evidence_and_deduplicates_localizations(self):
        url='https://apps.apple.com/us/app/crimson-cloud/id1234567'
        alternate='https://apps.apple.com/kr/app/cloud/id1234567'
        mobile=dict(url=url,name='Crimson Cloud',applicationCategory='GameApplication',
                    operatingSystem='iOS 15 or later',**{'@type':'SoftwareApplication'})

        def document(value):
            return '<script type="application/ld+json">'+json.dumps(value)+'</script>'

        self.assertIsNone(listing_id('https://apps.apple.com.evil.example/us/app/crimson-cloud/id1234567'))
        self.assertIsNone(listing_id(url+'?redirect=yes'))
        self.assertFalse(listing(url,document(dict(mobile,operatingSystem='macOS')))['sources'])
        self.assertFalse(listing(url,document(dict(mobile,url=url.replace('1234567','7654321'))))['sources'])

        observed=now()
        published=(datetime.fromisoformat(observed)-timedelta(days=2)).isoformat()
        first=evidence('https://youtu.be/AXcdefghijk','Crimson Cloud gameplay','Video metadata','api_metric',
                       'youtube_data_api',observed,published)
        second=evidence('https://youtu.be/BXcdefghijk','다른이름 gameplay','Video metadata','api_metric',
                        'youtube_data_api',observed,published)
        lead=evidence(url,'Crimson Cloud','App Store search lead','search_lead')
        observations=[dict(sources=[first,second,lead])]
        self.assertFalse(verified_games(observations,now(),{}))
        observations.extend((listing(url,document(mobile)),
                             listing(alternate,document(dict(mobile,url=alternate,name='다른이름')))))
        result=verified_games(observations,now(),{})
        self.assertEqual(set(result),{first['id'],second['id']})
        self.assertEqual({row['game'] for row in result.values()},{'crimson cloud'})

    def test_extracts_structured_graph_and_rejects_conflicting_metadata(self):
        url='https://apps.apple.com/us/app/example-cloud/id1234567'
        app={'@type':['https://schema.org/SoftwareApplication','VideoGame'],'url':url,
             'name':'Example Cloud','applicationCategory':['Games'],
             'operatingSystem':[{'@type':'OperatingSystem','name':'iPadOS'},'Requires iOS 16.0 or later.']}

        def document(*nodes):
            return '<script type="application/ld+json">'+json.dumps([{'@graph':list(nodes)}])+'</script>'

        verified=listing(url,document(app))
        self.assertEqual(verified['extraction']['platforms'],['iOS','iPadOS'])
        self.assertEqual(verified['sources'][0]['scope'],'public_page')
        for other,reason in (
                ({**app,'name':'Unrelated Cloud'},'listing_metadata_conflict'),
                ({**app,'@id':'7654321'},'listing_identity_conflict'),
                ({**app,'applicationCategory':['Business']},'listing_metadata_conflict'),
                ({**app,'operatingSystem':'macOS does not run the iOS version'},'listing_metadata_conflict')):
            with self.subTest(reason=reason):
                self.assertEqual(listing(url,document(app,other))['reason'],reason)
        mismatch='<link rel="canonical" href="'+url.replace('1234567','7654321')+'">'
        self.assertEqual(listing(url,mismatch+document(app))['reason'],'listing_identity_conflict')
        self.assertEqual(listing(url,'<html>iOS Games Example Cloud</html>')['reason'],'listing_app_node_unverified')
        self.assertEqual(listing(url,document({**app,'operatingSystem':'not iOS'}))['reason'],
                         'listing_mobile_platform_unverified')

    def test_same_app_name_across_different_ids_cannot_link_a_video(self):
        observed=now()
        published=(datetime.fromisoformat(observed)-timedelta(days=2)).isoformat()
        video=evidence('https://youtu.be/CXcdefghijk','Example Cloud gameplay','Video metadata','api_metric',
                       'youtube_data_api',observed,published)
        observations=[dict(sources=[video])]
        for app_id in ('1234567','7654321'):
            url=f'https://apps.apple.com/us/app/example-cloud/id{app_id}'
            app={'@type':'VideoGame','url':url,'name':'Example Cloud','operatingSystem':'iOS'}
            observations.append(listing(url,'<script type="application/ld+json">'+json.dumps(app)+'</script>'))
        self.assertFalse(verified_games(observations,observed,{}))

    def test_progress_distinguishes_relevant_leads_official_records_and_linked_games(self):
        from research_quality_loop import evidence_progress

        observed=now()
        published=(datetime.fromisoformat(observed)-timedelta(days=2)).isoformat()
        url='https://apps.apple.com/us/app/example-cloud/id1234567'
        video=evidence('https://youtu.be/DXcdefghijk','Example Cloud gameplay','Video metadata','api_metric',
                       'youtube_data_api',observed,published)
        lead=evidence(url,'Example Cloud','Search result','search_lead')
        other=evidence(url.replace('example-cloud/id1234567','unrelated/id7654321'),'Unrelated','Lead','search_lead')
        app={'@type':'VideoGame','url':url,'name':'Example Cloud','operatingSystem':'iOS'}
        direct=listing(url,'<script type="application/ld+json">'+json.dumps(app)+'</script>')
        before=[dict(sources=[video,lead,other])]
        self.assertEqual(evidence_progress(before,{}),{('relevant_listing_lead','1234567')})
        self.assertEqual(evidence_progress(before+before,{}),evidence_progress(before,{}))
        final=before+[direct]
        self.assertEqual(evidence_progress(final,verified_games(final,now(),{}))-evidence_progress(before,{}),
                         {('official_mobile','1234567'),('linked_game','example cloud')})

    def test_independent_origins_alone_do_not_link_unrelated_citations(self):
        from decision_recovery import DecisionViolation
        from research_quality_loop import linked_citation_pairs, validate_staff_report
        from web_research import evidence_catalog

        source=evidence('https://apps.apple.com/us/app/falcon/id1234567','Falcon','Mobile support',
                        'public_page','apple_app_store')
        video=evidence('https://youtu.be/EXcdefghijk','An unrelated video','Video metadata',
                       'api_metric','youtube_data_api')
        observations=[dict(sources=[source,video])]
        pairs=linked_citation_pairs(evidence_catalog(observations),{})
        self.assertEqual(pairs,[])
        report=dict(tool='finish',option='',feasibility='검토 필요',claims=[
            dict(statement='독립 모바일 근거 필요',assessment='supported',citations=[source['id'],video['id']])])
        with self.assertRaises(DecisionViolation) as exc:
            validate_staff_report(report,observations,pairs)
        self.assertEqual(exc.exception.rule,'quality_claim_pair_unlinked')
