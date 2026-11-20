from datetime import datetime, timedelta
import socket
from time import monotonic
from unittest import TestCase
from unittest.mock import patch

from autonomous_company import CompanyError, now
from official_sources import candidate_plans, exact_page
from publisher_discovery import BLIZZARD_HTML, discovery_research_tools
from research_https import _global_addresses, robots_access
from web_research import collect_observation, evidence, independent_sources, observation_checkpoint


class OfficialSourcesTest(TestCase):
    def test_generic_candidate_registry_and_tamper(self):
        url = 'https://council.example/reports/meeting'
        outside = 'https://mirror.example/reports/meeting'
        rows = [evidence(link, 'Council meeting', 'Search fragment', 'search_lead') for link in (url, outside)]
        observations = [dict(tool='search', option='council', status='observed', at=now(), sources=rows)]
        plans = candidate_plans(observations, {url:dict(channel='publisher_site', subject='Council')})
        self.assertEqual(plans[0]['robots']['url'], 'https://council.example/robots.txt')
        self.assertEqual(plans[0]['access'], 'robots_pending')
        self.assertEqual(plans[1]['access'], 'not_approved')
        self.assertNotIn('page', plans[1])
        self.assertEqual(observation_checkpoint(observations, now())['sources'], 2)
        future = (datetime.fromisoformat(now()) + timedelta(days=2)).isoformat()
        with self.assertRaises(CompanyError):
            observation_checkpoint(observations, future)
        rows[0]['excerpt'] = 'Modified fragment'
        with self.assertRaises(CompanyError):
            candidate_plans(observations, {})

    def test_exact_urls(self):
        for path in ('http://example.org/page', 'https://127.0.0.1/page',
                     'https://example.org:443/page', 'https://user@example.org/page',
                     'https://example.org/../page', 'https://example.org/%2fpage',
                     'https://example.org/page?token=secret', 'https://example.org/page#top'):
            with self.subTest(path=path), self.assertRaises(CompanyError):
                exact_page(path)

    def test_dns_is_rejected_if_any_answer_is_private(self):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 443))
                   for ip in ('93.184.216.34', '127.0.0.1')]
        with patch('research_https.socket.getaddrinfo', return_value=answers), self.assertRaises(CompanyError):
            _global_addresses('council.example', monotonic()+1)

    def test_shared_robots_and_rights_separation(self):
        tools, _ = discovery_research_tools([])
        press = [tool for tool in tools.values() if 'gamespress' in tool.options['approved']]
        requests = []

        def invoke(operation, digest, collect):
            requests.append(operation['endpoint'])
            collect(lambda: None)

        def fetch(parsed, kind, **kwargs):
            if kind == 'robots':
                return dict(status=200, text='User-agent: *\nDisallow: /admin')
            return dict(status=200, text='<title>Blizzard Entertainment</title>'
                                        '<p>World of Warcraft press kit</p>')

        with patch('publisher_discovery.fetch_public_text', side_effect=fetch):
            rows = [collect_observation(tool, 'approved', invoke) for tool in press]
        self.assertEqual(len(set(requests)), len(requests))
        self.assertEqual(len(requests), 3)
        self.assertEqual(rows[0]['document']['rights'], 'unconfirmed')
        self.assertEqual(rows[1]['document']['scene_ids'], ['scene-3'])
        self.assertFalse(independent_sources([row['sources'][0] for row in rows]))
        self.assertTrue(all(plan['access']=='previously_attempted'
                            for plan in candidate_plans(rows, BLIZZARD_HTML)
                            if 'gamespress' in plan['url']))

    def test_denial_and_redirect_stop(self):
        self.assertEqual(robots_access(dict(status=404), '/page'), 'robots_absent_policy_unconfirmed')
        self.assertEqual(robots_access(dict(status=403), '/page'), 'robots_auth_denied')
        tools, _ = discovery_research_tools([])
        tool = next(iter(tools.values()))
        with patch('publisher_discovery.fetch_public_text', side_effect=[
            dict(status=200, text='User-agent: *\nDisallow: /admin'), dict(status=302, text=None)
        ]) as fetch:
            result = collect_observation(tool, 'approved', lambda op, sha, collect:collect(lambda: None))
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['requests'][-1]['http_status'], 302)
        self.assertEqual(fetch.call_count, 2)
