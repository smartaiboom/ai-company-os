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
