from copy import deepcopy
from datetime import datetime,timedelta,timezone
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from autonomous_company import CompanyError, Store, digest, now
from employee_web_research import POLICY, TOOL, collect, usable_observations, validate_selection


class EmployeeWebTests(unittest.TestCase):
    def test_failure_consumed_no_duplicate_and_missing_authorization_no_request(self):
        with TemporaryDirectory() as root:
            store=Store(root)
            p=store.create('격리 도구 테스트',opt_in=True)
            request=dict(tool=TOOL,queries=[dict(query='employee query',purpose='shorts_examples',
                                                 lookback_days=7,order='date')])
            def deny():
                raise CompanyError('test_no_permission')
            with patch('employee_web_research.send_once') as http:
                with self.assertRaisesRegex(CompanyError,'test_no_permission'):
                    collect(store,p,'research',request,'fixture-youtube-key',deny)
                self.assertNotIn('employee_web',store.load(p['id']))
                http.assert_not_called()
                http.side_effect=HTTPError('https://www.googleapis.com/youtube/v3/search',429,'test',{},None)
                with self.assertRaisesRegex(CompanyError,'employee_web_failed_no_retry'):
                    collect(store,p,'research',request,'fixture-youtube-key',lambda:None)
                self.assertEqual(p['employee_web']['attempts'][0]['status'],'failed')
                with self.assertRaisesRegex(CompanyError,'employee_web_already_consumed'):
                    collect(store,p,'research',request,'fixture-youtube-key',lambda:None)
                http.assert_called_once()

    def test_unverified_and_expired_data_cannot_support_manager_selection(self):
        state=dict(status='completed',observations=[dict(id='q0:abcdefghijk',status='unverified')])
        state['receipt_hash']=digest(state['observations'])
        with self.assertRaisesRegex(CompanyError,'employee_web_evidence_expired_or_empty'):
            usable_observations(state)
        state['observations'][0].update(status='metadata_verified',
            expires_at=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat())
        state['receipt_hash']=digest(state['observations'])
        with self.assertRaisesRegex(CompanyError,'employee_web_evidence_expired_or_empty'):
            usable_observations(state)

    def test_four_search_and_four_video_cap_and_timeout_no_retry(self):
        from io import BytesIO
        class Response(BytesIO):
            status = 200
        import json
        with TemporaryDirectory() as root:
            store = Store(root)
            p = store.create('isolated caps', opt_in=True)
            request = dict(tool=TOOL, queries=[dict(query='fixture '+str(i),
                purpose='shorts_examples', lookback_days=7, order='date') for i in range(4)])
            published = (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
            def send(req, timeout):
                data = dict(items=[dict(id=dict(videoId='abcdefghijk'))]) if '/search?' in req.full_url else dict(items=[dict(
                    id='abcdefghijk', snippet=dict(title='fixture',categoryId='20',publishedAt=published),
                    contentDetails=dict(duration='PT34S'),statistics=dict(viewCount='10'))])
                return Response(json.dumps(data).encode())
            with patch('employee_web_research.send_once', side_effect=send) as http:
                state = collect(store,p,'research',request,'fixture-youtube-key',lambda:None)
                self.assertEqual(http.call_count,8)
                self.assertEqual(sum(a['quota_bucket']=='search' for a in state['attempts']),4)
                self.assertEqual(sum(a['quota_bucket']=='general' for a in state['attempts']),4)
                with self.assertRaisesRegex(CompanyError,'employee_web_already_consumed'):
                    collect(store,p,'research',request,'fixture-youtube-key',lambda:None)
                self.assertEqual(http.call_count,8)
            p = store.create('isolated timeout', opt_in=True)
            with patch('employee_web_research.send_once',side_effect=TimeoutError()) as http:
                with self.assertRaisesRegex(CompanyError,'employee_web_failed_no_retry'):
                    collect(store,p,'research',request,'fixture-youtube-key',lambda:None)
                self.assertEqual(p['employee_web']['attempts'][0]['status'],'failed')
                http.assert_called_once()
            p = store.create('isolated excess', opt_in=True)
            request['queries'].append(request['queries'][0])
            with patch('employee_web_research.send_once') as http:
                with self.assertRaisesRegex(CompanyError,'invalid_employee_search_request'):
                    collect(store,p,'research',request,'fixture-youtube-key',lambda:None)
                http.assert_not_called()
