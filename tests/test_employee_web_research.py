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
