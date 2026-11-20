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

    def test_official_observation_shared_robots_and_signed_http_budget(self):
        from autonomous_company import digest
        from decision_recovery import delegated_call, ProviderFailure
        from owner_operating_policy import OwnerOperatingPolicy
        from web_research import collect_observation

        for scenario in ('success','denied','redirect','empty','503'):
            with self.subTest(scenario=scenario), TemporaryDirectory() as temp:
                original = OwnerOperatingPolicy(Path(temp)/'original', {'task':'fixture'})
                new = OwnerOperatingPolicy(Path(temp)/'new', {'task':'official'})
                robots = 'https://www.klei.com/robots.txt'
                rights = 'https://www.klei.com/creation-guidelines'
                entries = [dict(id='robots-pages',kind='robots',url=robots),
                           dict(id='scene-1',kind='page',url=PAGE),
                           dict(id='rights',kind='page',url=rights)]
                approved = {**original.proposal([publisher.get_unit(row) for row in entries]),
                            'profile':'klei','profile_rules':PROFILE,'entries':entries}
                original.approve(approved,digest(approved),'historical-key')
                with patch('publisher_discovery.store_for',return_value=original):
                    tools, provenance = publisher.official_research_tools(object(), {})
                self.assertEqual(provenance,digest(original.read('policy.json')))
                units = {row['id']:row for tool in tools.values() for row in tool.requests}
                proposal = new.proposal(list(units.values()))
                self.assertEqual(len(proposal['units']),3)
                new.approve(proposal,digest(proposal),'separate-key')

                def invoke(unit, wire, work):
                    delegated_call(new,'separate-key',unit,wire,lambda proof,check: work(check))

                robots_text = 'User-agent: *\nDisallow: /' if scenario=='denied' else 'User-agent: *\nDisallow: /private/'
                first = dict(status=200,text='<title>Official</title><p>Policy text.</p>')
                if scenario == 'redirect':
                    first = dict(status=302,text=None)
                elif scenario == 'empty':
                    first = dict(status=200,text='<script>hidden only</script>')
                elif scenario == '503':
                    first = ProviderFailure('publisher_http_failure')
                with patch('publisher_discovery.fetch_public', side_effect=[
                    dict(status=200,text=robots_text), first, dict(status=200,text='<p>Rights detail.</p>')]) as get:
                    tool = tools['official-page-scene-1']
                    with self.assertRaisesRegex(CompanyError,'publisher_url_blocked'):
                        collect_observation(tool,'https://127.0.0.1/private',invoke)
                    get.assert_not_called()
                    if scenario=='503':
                        with self.assertRaisesRegex(CompanyError,'publisher_http_failure'):
                            collect_observation(tool,'approved',invoke)
                        with self.assertRaisesRegex(CompanyError,'owner_policy_unresolved_attempt'):
                            collect_observation(tools['official-page-rights'],'approved',invoke)
                    else:
                        result = collect_observation(tool,'approved',invoke)
                        self.assertEqual(result['status'],{'success':'observed','denied':'policy_blocked',
                                                          'redirect':'unavailable','empty':'empty'}[scenario])
                        if scenario=='success':
                            self.assertEqual(result['sources'][0]['scope'],'public_page')
                            self.assertEqual(result['sources'][0]['origin'],'Klei Entertainment')
                            collect_observation(tools['official-page-rights'],'approved',invoke)
                            with self.assertRaisesRegex(CompanyError,'owner_policy_exhausted'):
                                collect_observation(tool,'approved',invoke)
                    self.assertEqual(get.call_count,{'success':3,'denied':1,'redirect':2,'empty':2,'503':2}[scenario])
                self.assertEqual(original.attempts(),{})

    def test_common_page_observer_and_private_dns_rejection(self):
        from autonomous_company import digest
        from research_https import _global_addresses, observe_approved_page
        from time import monotonic
        import socket

        host = 'archive.example'
        with patch('socket.getaddrinfo',return_value=[
            (socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]):
            with self.assertRaisesRegex(CompanyError,'official_destination_blocked'):
                _global_addresses(host,monotonic()+5)

        def entry(kind, path):
            url = f'https://{host}{path}'
            return dict(kind=kind,path=path,host=host,url=url,
                        operation=dict(id=kind,payload_sha256=digest(dict(method='GET',url=url))))

        charged = []
        def invoke(operation, wire, work):
            self.assertEqual(wire,operation['payload_sha256'])
            charged.append(operation['id'])
            work(lambda:None)

        def fetch(url, kind):
            self.assertIn(url,(f'https://{host}/robots.txt',f'https://{host}/reports/inventory'))
            return dict(status=200,text='User-agent: *\nDisallow: /internal/' if kind=='robots' else 'Public inventory')

        result = observe_approved_page(entry('page','/reports/inventory'),entry('robots','/robots.txt'),
            invoke,fetch,lambda url, text:dict(status='observed',sources=[text]),{})
        self.assertEqual(result['sources'],['Public inventory'])
        self.assertEqual(charged,['robots','page'])

    def test_robots_absence_requires_separate_path_policy_and_known_host_block_removes_choice(self):
        from research_https import robots_access, observe_approved_page
        from web_research import Tool, step_context

        host = 'archive.example'
        page = dict(kind='page',path='/public',host=host,url=f'https://{host}/public',
                    operation=dict(id='page',payload_sha256='page-fixture'))
        robots = dict(kind='robots',url=f'https://{host}/robots.txt',
                      operation=dict(id='robots',payload_sha256='robots-fixture'))
        for code in (404,410):
            missing = dict(status=code,text=None)
            self.assertEqual(robots_access(missing,'/public'),'robots_absent_policy_unconfirmed')
            self.assertEqual(robots_access(missing,'/public',absence_policy_confirmed=True),
                             'robots_absent_policy_confirmed')
        for code in (401,403,429,500,503,302):
            self.assertNotIn(robots_access(dict(status=code),'/public',absence_policy_confirmed=True),
                             ('robots_allowed','robots_absent_policy_confirmed'))
        self.assertEqual(robots_access(dict(status=200,text='User-agent: *\nDisallow: /public'),'/public',
                                      absence_policy_confirmed=True),'robots_rule_blocked')
        for authorized in (False, True):
            with self.subTest(authorized=authorized):
                get = Mock(side_effect=[dict(status=404,text=None),dict(status=200,text='Public source')])
                result = observe_approved_page(page,robots,lambda _op,_hash,execute:execute(lambda:None),get,
                    lambda url,body:dict(status='observed',sources=[]),{},absence_policy_confirmed=authorized)
                self.assertEqual(get.call_count,2 if authorized else 1)
                self.assertEqual(result['status'],'observed' if authorized else 'policy_blocked')
                if not authorized:
                    other = Tool('new_page','Same publisher',{'id':'exact'},None,
                                 requests=(dict(endpoint=f'https://{host}/other'),))
                    alternate = Tool('cached','Alternate',{'saved':'records'},None)
                    context, _ = step_context({tool.name:tool for tool in (other,alternate)},
                        [{**result,'tool':'initial','option':'id'}],False)
                    self.assertEqual([item['name'] for item in context['tools']],['cached'])
