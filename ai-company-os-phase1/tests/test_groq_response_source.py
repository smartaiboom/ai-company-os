"""No network: header hints cannot authenticate a response origin."""
from contextlib import ExitStack
from io import BytesIO
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,getproxies_environment

import ai_safety
from groq_provider import ENDPOINT,response_source_hints
from tests import test_autonomous_groq as groq
from tests import test_synthetic_groq_compat_once as compat_tests
import synthetic_groq_compat_once as compat


class GuardTests(unittest.TestCase):
    def test_present_or_absent_proxy_env_never_changes_existing_guard(self):
        for env in ({},{'HTTPS_PROXY':'http://synthetic-upper.invalid',
                       'https_proxy':'http://synthetic-lower.invalid',
                       'HTTP_PROXY':'http://synthetic-http.invalid','ALL_PROXY':'http://synthetic-all.invalid',
                       'NO_PROXY':'synthetic-exclusion.invalid'}):
            with ExitStack() as stack:
                stack.enter_context(patch.dict(os.environ,env,clear=True))
                for name in ('socket.socket.connect','socket.socket.connect_ex','socket.socket.sendto',
                             'socket.create_connection','socket.getaddrinfo'):
                    stack.enter_context(patch(name,side_effect=AssertionError('network forbidden')))
                # Verify stdlib precedence on synthetic values, never actual proxy values.
                if env:self.assertEqual(env['https_proxy'],getproxies_environment()['https'])
                stack.enter_context(patch('urllib.request.getproxies',side_effect=AssertionError('guard must not autodetect proxies')))
                observed=[]
                def fake_open(handler,request):
                    observed.append(request.has_proxy())
                    raise HTTPError(ENDPOINT,403,'synthetic',{},BytesIO(b''))
                stack.enter_context(patch('urllib.request.HTTPSHandler.https_open',new=fake_open))
                with self.assertRaises(HTTPError) as exc:
                    ai_safety.guarded_urlopen(Request(ENDPOINT+'/chat/completions',data=b'{}'),timeout=1)
                exc.exception.close();self.assertEqual([False],observed)
                self.assertIsNone(ai_safety.NoRedirect().redirect_request(None,None,302,'synthetic',{},'https://synthetic.invalid'))

    def test_presence_only_and_redirect_status_never_prove_origin(self):
        headers={k:'PRIVATE_SENTINEL' for k in ('Server','Via','WWW-Authenticate','X-Request-ID','CF-Ray','Location','Content-Type','Authorization')}
        for status in (200,302,304,403,None,True,'403'):
            hints=response_source_hints(headers,status)
            self.assertTrue(all(hints['header_presence'].values()))
            self.assertEqual('unverified',hints['origin_classification'])
            self.assertNotIn('PRIVATE_SENTINEL',json.dumps(hints))
            self.assertNotIn('authorization',hints['header_presence'])
            self.assertEqual(status==302 if type(status) is int else None,hints['redirect_status_observed'])
        self.assertEqual('unverified',response_source_hints({},403)['origin_classification'])


class GroqSourceTests(unittest.TestCase):
    setUp=groq.GroqTests.setUp
    engine=groq.GroqTests.engine
    reset=groq.GroqTests.reset
    approve=groq.GroqTests.approve
    run_once=groq.GroqTests.run_once

    def test_fake_direct_proxy_403_and_timeout_preserve_uncertainty(self):
        # Labels are fixture intent, not a classification made from headers.
        for label,headers in [('direct',{}),('proxy',{'Via':groq.KEY,'Server':groq.KEY,'X-Request-ID':groq.KEY})]:
            self.reset();self.approve()
            error=HTTPError(ENDPOINT,403,groq.KEY,headers,BytesIO(groq.KEY.encode()))
            with patch('autonomous_live.urlopen',side_effect=error):self.run_once()
            a=self.p['real_ai']['attempts'][0];h=a['response_source_hints']
            self.assertEqual(403,a['provider_error_diagnostics']['http_status'])
            self.assertEqual(label=='proxy',h['header_presence']['via'])
            self.assertFalse(h['redirect_status_observed'])
            self.assertEqual('unverified',h['origin_classification'])
            self.assertNotIn(groq.KEY,json.dumps(a))
        self.reset();self.approve()
        with patch('autonomous_live.urlopen',side_effect=TimeoutError(groq.KEY)):self.run_once()
        self.assertNotIn('response_source_hints',self.p['real_ai']['attempts'][0])


class CompatSourceTests(unittest.TestCase):
    setUp=compat_tests.CompatTests.setUp
    fake=compat_tests.CompatTests.fake

    def test_200_json_and_403_source_hints_in_offline_once_runner(self):
        result=compat.run_once()
        self.assertEqual('succeeded',result['state'])
        self.assertEqual('unverified',result['response_source_hints']['origin_classification'])
        self.assertFalse(result['response_source_hints']['redirect_status_observed'])
        with patch.object(compat,'ROOT',self.root.parent/'other-offline-fixture'):
            headers={'Via':compat_tests.KEY,'CF-Ray':compat_tests.KEY,'WWW-Authenticate':compat_tests.KEY}
            error=HTTPError(ENDPOINT,403,compat_tests.KEY,headers,BytesIO(b''))
            with patch.object(compat,'guarded_urlopen',side_effect=error):result=compat.run_once()
            self.assertTrue(result['response_source_hints']['header_presence']['via'])
            self.assertEqual('unverified',result['response_source_hints']['origin_classification'])
            self.assertNotIn(compat_tests.KEY,json.dumps(result))


if __name__=='__main__':unittest.main()
