from contextlib import nullcontext
from email.message import Message
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from autonomous_company import CompanyError
import publisher_discovery as publisher


PROFILE = publisher.PROFILES['klei']
PAGE = 'https://www.klei.com/games/example/'
ASSET = 'https://assets.klei.com/images/example.png'


class PublisherDiscoveryTests(TestCase):
    def test_only_static_media_from_registered_cdn(self):
        result = publisher.extract_page(PROFILE, PAGE, f'''
            <title>Official game media</title>
            <img src="{ASSET}" alt="Example gameplay">
            <meta property="og:image" content="{ASSET}">
            <source src="https://assets.klei.com/media/game.webm">
            <a href="https://assets.klei.com/press.zip">Archive</a>
            <a href="https://another.example/cover.png">Untrusted</a>
            <script><img src="https://assets.klei.com/hidden.jpg"></script>
        ''')
        self.assertFalse(result['restricted'])
        self.assertEqual([(item['mime'], item['title']) for item in result['assets']],
                         [('image/png', 'Example gameplay'), ('video/webm', 'game.webm')])
        for body in ('<input TYPE="password">', '<title>Verify you are human</title>'):
            result = publisher.extract_page(PROFILE, PAGE, body + f'<img src="{ASSET}">')
            self.assertTrue(result['restricted'])
            self.assertFalse(result['assets'])

    def test_url_scope_and_robots(self):
        for url in (ASSET+'?credential=x', ASSET+'#x', 'http://assets.klei.com/image.png',
                    'https://assets.klei.com@127.0.0.1/a.png', 'https://assets.klei.com:443/a.png',
                    'https://assets.klei.com/a/%2e%2e/b.png', 'https://assets.klei.com//a.png',
                    'https://assets.klei.com/a/../b.png'):
            with self.subTest(url=url), self.assertRaisesRegex(CompanyError, 'publisher_url_blocked'):
                publisher.profile_url(PROFILE,url,'asset')
        publisher.profile_url(PROFILE,'https://assets.klei.com/robots.txt','robots')
        self.assertFalse(publisher.robots_allows(None, '/images/example.png'))
        self.assertFalse(publisher.robots_allows('User-agent: other\nDisallow:', '/images/example.png'))
        self.assertFalse(publisher.robots_allows('User-agent: *\nDisallow: /images/*', '/images/example.png'))
        self.assertFalse(publisher.robots_allows('User-agent: *\nCrawl-delay: 5\nDisallow:', '/images/example.png'))
        self.assertTrue(publisher.robots_allows('User-agent: *\nDisallow: /private/', '/images/example.png'))

    def test_html_response_bounds_and_no_redirect(self):
        headers = Message()
        headers['Content-Type'] = 'text/html'
        response = Mock(status=302, headers=headers)
        with patch('publisher_discovery._PinnedHTTPS') as connection, patch(
                'publisher_discovery._global_addresses', return_value=(2, ('8.8.8.8', 443))):
            transport = connection.return_value
            transport.getresponse.return_value = nullcontext(response)
            self.assertEqual(publisher.fetch_public(PROFILE,PAGE,'page'), {'status':302,'text':None})
            response.read.assert_not_called()
            response.status = 200
            response.getheader.side_effect = lambda key, default=None: default
            response.read.return_value = b'x'*(publisher.MAX_PAGE+1)
            with self.assertRaisesRegex(CompanyError, 'publisher_response_limit'):
                publisher.fetch_public(PROFILE,PAGE,'page')
            self.assertEqual(transport.request.call_count, 2)

    def test_unavailable_robots_stops_without_page_or_model(self):
        from autonomous_company import digest
        from owner_operating_policy import OwnerOperatingPolicy

        with TemporaryDirectory() as temp:
            store = OwnerOperatingPolicy(Path(temp)/'publisher', {'goal':'test'})
            entries = [
                {'id':'robots-pages','kind':'robots','url':'https://www.klei.com/robots.txt'},
                {'id':'robots-assets','kind':'robots','url':'https://assets.klei.com/robots.txt'},
                {'id':'scene-1','kind':'page','url':PAGE},
            ]
            scope = {**store.proposal([publisher.get_unit(entry) for entry in entries]+[publisher.plan_unit()]),
                     'profile':'klei','profile_rules':PROFILE,'entries':entries}
            store.approve(scope,digest(scope),'fixture')
            with patch('publisher_discovery.fetch_public', return_value={'status':403,'text':None}) as fetch, patch(
                    'publisher_discovery.run_worker') as model:
                publisher.acquire(None,None,[],store,'fixture',scope)
            fetch.assert_called_once()
            model.assert_not_called()
            result = store.read('discovery.json')
            self.assertFalse(result['eligible'])
            self.assertEqual([row['status'] for row in result['pages']],
                             ['robots_unavailable','publisher_access_unconfirmed','robots_permission_unconfirmed'])
            self.assertEqual(len(store.attempts()), 1)
