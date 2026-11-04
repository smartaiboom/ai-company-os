"""Synthetic-only runner tests. Real sockets/DNS are always forbidden."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack,redirect_stdout
from io import BytesIO,StringIO
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError,URLError

import synthetic_groq_compat_once as compat
from autonomous_company import CompanyError,digest
from groq_provider import COST_POLICY,MODEL,ENDPOINT

KEY='synthetic-compat-credential'


class CompatTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.temp=self.stack.enter_context(tempfile.TemporaryDirectory())
        self.root=Path(self.temp)/'fixed-diagnostic'
        doc=Path(self.temp)/'authorization.md';doc.write_text('OFFLINE synthetic authorization only')
        account={'provider':'groq','model':MODEL,'endpoint':ENDPOINT,'cost_policy':COST_POLICY,
                 'account_verification':{'free_plan':True,'billing_disabled':True,'model_allowed':True,
                                         'verified_at':'2026-11-04T11:35:43+09:00',
                                         'credential_binding':compat.key_binding(KEY)}}
        self.account=Path(self.temp)/'account.json';self.account.write_text(json.dumps(account))
        self.stack.enter_context(patch.dict(os.environ,{'GROQ_API_KEY':KEY},clear=True))
        for name,value in [('ROOT',self.root),('AUTH_DOC',doc),
                           ('AUTH_DOC_SHA',hashlib.sha256(doc.read_bytes()).hexdigest()),
                           ('ACCOUNT_PROPOSAL',self.account),('ACCOUNT_SHA',digest(account)),
                           ('now',lambda:'2026-11-04T12:10:00+09:00')]:
            self.stack.enter_context(patch.object(compat,name,value))
        for name in ('socket.socket.connect','socket.socket.connect_ex','socket.socket.sendto',
                     'socket.create_connection','socket.getaddrinfo','socket.gethostbyname'):
            self.stack.enter_context(patch(name,side_effect=AssertionError('external network forbidden')))
        self.calls=0;self.alter=None
        self.stack.enter_context(patch.object(compat,'guarded_urlopen',self.fake))

    def fake(self,request,timeout):
        self.calls+=1
        self.assertEqual(1,self.calls);self.assertEqual(60,timeout)
        self.assertEqual(ENDPOINT+'/chat/completions',request.full_url)
        self.assertEqual('POST',request.get_method())
        self.assertEqual(compat.REQUEST_SHA,hashlib.sha256(request.data).hexdigest())
        self.assertEqual('Bearer '+KEY,request.get_header('Authorization'))
        self.assertNotIn(KEY.encode(),request.data)
        record=json.loads((self.root/'operation.json').read_text())
        self.assertEqual('transport_started',record['state']);self.assertEqual(1,record['post_attempts'])
        self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0],0)
        envelope={'choices':[{'finish_reason':'stop','message':{'role':'assistant',
                  'content':'{"result":{"status":"ready"}}'}}],
                  'usage':{'prompt_tokens':50,'completion_tokens':30,'total_tokens':80}}
        if self.alter:self.alter(envelope)
        response=BytesIO(json.dumps(envelope).encode());response.status=200
        response.headers={'x-ratelimit-remaining-tokens':'123','Authorization':KEY}
        return response

    def assert_private(self):
        for path in self.root.rglob('*'):
            if path.is_file():
                raw=path.read_bytes()
                self.assertNotIn(KEY.encode(),raw)
                self.assertNotIn(b'PRIVATE_SENTINEL',raw)
                self.assertNotIn(compat.key_binding(KEY).encode(),raw)

    def test_200_exact_bytes_schema_tokens_and_second_invocation_blocked(self):
        record=compat.run_once()
        self.assertEqual('succeeded',record['state']);self.assertEqual('ready',record['result_status'])
        self.assertTrue(record['strict_schema_valid']);self.assertFalse(record['response_cost_verified_zero'])
        self.assertEqual(30,record['response_diagnostics']['tokens']['completion_tokens'])
        self.assertEqual({'x-ratelimit-remaining-tokens':123},record['rate_limits'])
        original=(self.root/'operation.json').read_bytes()
        with self.assertRaisesRegex(CompanyError,'operation_already_consumed'):compat.run_once()
        self.assertEqual(1,self.calls);self.assertEqual(original,(self.root/'operation.json').read_bytes())
        self.assertEqual(0,signal.getitimer(signal.ITIMER_REAL)[0]);self.assert_private()

    def test_http_errors_persist_status_no_body_or_retry(self):
        for status in (400,401,403,404,422,429,500,503):
            with self.subTest(status=status),patch.object(compat,'ROOT',Path(self.temp)/str(status)):
                self.root=compat.ROOT
                error=HTTPError(ENDPOINT+'?'+KEY,status,KEY,{'x-ratelimit-remaining-requests':'0'},
                                BytesIO(json.dumps({'error':{'code':'invalid_json_schema',
                                                            'message':KEY,'failed_generation':'PRIVATE_SENTINEL'}}).encode()))
                with patch.object(compat,'guarded_urlopen',side_effect=error) as fake:
                    result=compat.run_once()
                    self.assertEqual('failed',result['state']);self.assertEqual(status,result['http_status'])
                    self.assertEqual(status,result['provider_error_diagnostics']['http_status'])
                    self.assertTrue(error.closed)
                    with self.assertRaises(CompanyError):compat.run_once()
                    self.assertEqual(1,fake.call_count);self.assert_private()

    def test_timeout_connection_and_reserved_crash_are_consumed(self):
        for index,error in enumerate((TimeoutError(KEY),URLError(KEY),KeyboardInterrupt())):
            with patch.object(compat,'ROOT',Path(self.temp)/('failed-'+str(index))):
                self.root=compat.ROOT
                with patch.object(compat,'guarded_urlopen',side_effect=error) as fake:
                    if isinstance(error,KeyboardInterrupt):
                        with self.assertRaises(KeyboardInterrupt):compat.run_once()
                    else:self.assertEqual('uncertain',compat.run_once()['state'])
                    with self.assertRaises(CompanyError):compat.run_once()
                    self.assertEqual(1,fake.call_count);self.assert_private()
        with patch.object(compat,'ROOT',Path(self.temp)/'reserved-crash'):
            self.root=compat.ROOT
            with patch.object(compat,'persist',side_effect=KeyboardInterrupt()),self.assertRaises(KeyboardInterrupt):
                compat.run_once()
            self.assertEqual('reserved',json.loads((self.root/'operation.json').read_text())['state'])
            with self.assertRaises(CompanyError):compat.run_once()
            self.assertEqual(0,self.calls)

    def test_bad_success_responses_never_count_as_compatible(self):
        mutations=[lambda r:r['choices'][0].update(finish_reason='length'),
                   lambda r:r['choices'][0]['message'].update(refusal=KEY),
                   lambda r:r['choices'][0]['message'].update(content='{"result":{"status":"ready","extra":true}}'),
                   lambda r:r['choices'][0]['message'].update(content='not JSON'),
                   lambda r:r['choices'][0]['message'].update(content='{"result":{"status":"stop","reason":"PRIVATE_SENTINEL"}}'),
                   lambda r:r['choices'][0]['message'].update(content=KEY),
                   lambda r:r['usage'].update(cost=1),
                   lambda r:r['usage'].update(completion_tokens=513),
                   lambda r:r.update(error={'code':'unsupported_parameter','message':KEY})]
        for index,alter in enumerate(mutations):
            with patch.object(compat,'ROOT',Path(self.temp)/('invalid-'+str(index))):
                self.root=compat.ROOT;self.calls=0;self.alter=alter
                record=compat.run_once()
                self.assertNotEqual('succeeded',record['state'])
                with self.assertRaises(CompanyError):compat.run_once()
                self.assertEqual(1,self.calls);self.assert_private()

    def test_preflight_blocks_expiry_key_account_payload_and_authorization(self):
        patches=[('now',lambda:compat.EXPIRES),('now',lambda:'2026-11-03T11:35:43+09:00'),
                 ('AUTH_DOC_SHA','changed'),('ACCOUNT_SHA','changed'),('REQUEST_SHA','changed')]
        for name,value in patches:
            with patch.object(compat,name,value),self.assertRaises(CompanyError):compat.run_once()
        with patch.dict(os.environ,{'GROQ_API_KEY':'changed'}),self.assertRaises(CompanyError):compat.run_once()
        with patch.dict(os.environ,{'GROQ_MODEL':'paid-model'}),self.assertRaises(CompanyError):compat.run_once()
        account=json.loads(self.account.read_text());account['account_verification']['billing_disabled']=False
        self.account.write_text(json.dumps(account))
        with patch.object(compat,'ACCOUNT_SHA',digest(account)),self.assertRaises(CompanyError):compat.run_once()
        self.assertEqual(0,self.calls);self.assertFalse(self.root.exists())

    def test_atomic_reservation_race_and_cli_no_store_override(self):
        self.root.mkdir()
        def reserve():
            try:compat.reserve({'state':'reserved'});return True
            except CompanyError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:reserve(),range(2)))
        self.assertEqual([False,True],sorted(results));self.assertEqual(0,self.calls)
        with redirect_stdout(StringIO()) as output:self.assertEqual(1,compat.main())
        self.assertNotIn(KEY,output.getvalue())

    def test_total_wall_timeout_and_timer_restoration(self):
        with patch.object(compat,'TIMEOUT',0.02):
            with self.assertRaises(TimeoutError),compat.wall_timeout():signal.pause()
        self.assertEqual(0,signal.getitimer(signal.ITIMER_REAL)[0])


if __name__=='__main__':unittest.main()
