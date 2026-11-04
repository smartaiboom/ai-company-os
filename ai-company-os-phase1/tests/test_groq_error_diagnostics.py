"""Offline HTTP rejection diagnostics; shared fixture blocks sockets and DNS."""
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError,URLError

from groq_provider import ENDPOINT,provider_error_diagnostics
from tests import test_autonomous_groq as groq


class GroqErrorTests(unittest.TestCase):
    setUp=groq.GroqTests.setUp
    engine=groq.GroqTests.engine
    approve=groq.GroqTests.approve
    reset=groq.GroqTests.reset
    run_once=groq.GroqTests.run_once

    def assert_private_failure(self):
        self.assertEqual(1,len(self.p['real_ai']['attempts']))
        attempt=self.p['real_ai']['attempts'][0]
        self.assertEqual('failed',attempt['status'])
        self.assertEqual(attempt['id'],self.p['active_operation'])
        for path in self.store.root.rglob('*'):
            if path.is_file():
                self.assertNotIn(groq.KEY.encode(),path.read_bytes())
                self.assertNotIn(b'PRIVATE_PROMPT_SENTINEL',path.read_bytes())
        return attempt

    def test_http_status_code_category_private_body_and_no_replay(self):
        cases=[(400,'invalid_json_schema','invalid_json_schema'),
               (400,'unsupported_parameter','unsupported_parameter'),
               (401,'invalid_api_key','authentication'),
               (403,'model_permission_blocked','permission'),
               (404,'model_not_found','model_or_resource_not_found'),
               (413,'other','request_too_large'),(422,'json_validate_failed','json_schema_validation'),
               (429,'rate_limit_exceeded','rate_limit'),(500,'other','server_error'),
               (502,'other','server_error'),(503,'other','server_error')]
        for status,code,category in cases:
            with self.subTest(status=status,code=code):
                self.reset();self.approve()
                body=json.dumps({'error':{'code':code,'message':groq.KEY,
                                         'failed_generation':'PRIVATE_PROMPT_SENTINEL'}}).encode()
                error=HTTPError(ENDPOINT+'?private='+groq.KEY,status,groq.KEY,
                                {'x-ratelimit-remaining-tokens':'7','Authorization':groq.KEY},BytesIO(body))
                with patch('autonomous_live.urlopen',side_effect=error) as transport:
                    self.run_once()
                    a=self.assert_private_failure()
                    self.assertEqual({'http_status':status,'category':category,'provider_code':code},a['provider_error_diagnostics'])
                    self.assertEqual({'x-ratelimit-remaining-tokens':7},a['rate_limits'])
                    self.assertEqual('provider_rejected' if status not in (429,502,503) else
                                     'provider_rate_limit' if status==429 else 'provider_unavailable',a['error_code'])
                    saved=self.store.path(self.p['id']).read_bytes()
                    # Neither a fresh start nor continue can retransmit this failure.
                    for resume in (False,True):
                        try:self.run_once(resume=resume)
                        except groq.CompanyError:pass
                    self.assertEqual(1,transport.call_count)
                    self.assertEqual(saved,self.store.path(self.p['id']).read_bytes())
                self.assertTrue(error.closed)

    def test_untrusted_and_bounded_error_body(self):
        bodies=[b'not json '+groq.KEY.encode(),
                json.dumps({'error':{'code':groq.KEY,'type':groq.KEY}}).encode(),
                b'{"error":{"code":"invalid_json_schema","code":"unsupported_parameter"}}',
                json.dumps({'error':{'code':['invalid_json_schema']}}).encode(),
                json.dumps({'error':{'code':'unsupported_parameter'},'pad':'x'*8193}).encode()]
        for body in bodies:
            with self.subTest(size=len(body)):
                self.reset();self.approve();stream=BytesIO(body)
                error=HTTPError(ENDPOINT,400,groq.KEY,{},stream)
                with patch('autonomous_live.urlopen',side_effect=error):self.run_once()
                self.assertEqual({'http_status':400,'category':'invalid_request','provider_code':'other'},
                                 self.assert_private_failure()['provider_error_diagnostics'])

    def test_timeout_connection_and_wrapped_timeout_without_message(self):
        for error,category in [(TimeoutError(groq.KEY),'timeout'),
                               (URLError(TimeoutError(groq.KEY)),'timeout'),
                               (ConnectionError(groq.KEY),'connection_error'),
                               (URLError(groq.KEY),'connection_error')]:
            self.reset();self.approve()
            with patch('autonomous_live.urlopen',side_effect=error):self.run_once()
            a=self.assert_private_failure()
            self.assertEqual('free_request_failed',a['error_code'])
            self.assertEqual({'http_status':None,'category':category,'provider_code':'other'},a['provider_error_diagnostics'])

    def test_200_error_envelope_is_not_success_or_zero_cost(self):
        self.reset();self.approve()
        def alter(response):
            response.clear()
            response['error']={'code':'context_length_exceeded','message':groq.KEY}
            return response
        self.fake.alter=alter
        def response(request,timeout):
            value=self.fake(request,timeout);value.status=200
            return value
        with patch('autonomous_live.urlopen',side_effect=response):self.run_once()
        a=self.assert_private_failure()
        self.assertEqual({'http_status':200,'category':'token_limit','provider_code':'context_length_exceeded'},a['provider_error_diagnostics'])
        self.assertNotIn('free_account_policy_verified',a)
        self.assertEqual('provider_rejected',a['error_code'])

    def test_status_validation_read_failure_and_conflicting_code(self):
        class BrokenBody(BytesIO):
            def read(self,size):raise TimeoutError(groq.KEY)
        for status in (99,600,True,'401',None):
            error=HTTPError(ENDPOINT,status,groq.KEY,{},BrokenBody())
            d=provider_error_diagnostics(exception=error)
            self.assertEqual({'http_status':None,'category':'http_error','provider_code':'other'},d)
            error.close()
        for status in (100,599):
            error=HTTPError(ENDPOINT,status,groq.KEY,{},BytesIO(b''))
            self.assertEqual(status,provider_error_diagnostics(exception=error)['http_status']);error.close()
        error=HTTPError(ENDPOINT,503,groq.KEY,{},BytesIO(b'{"error":{"code":"invalid_api_key"}}'))
        self.assertEqual('server_error',provider_error_diagnostics(exception=error)['category']);error.close()
        self.assertIsNone(provider_error_diagnostics(exception=ValueError(groq.KEY)))
