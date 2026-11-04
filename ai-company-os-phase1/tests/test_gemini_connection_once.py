import io
import json
import socket
import ssl
from http.client import RemoteDisconnected
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import gemini_connection_once as g


class GeminiOnceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (patch.object(g, 'LEDGER', Path(self.tmp.name) / 'operation.json'),
                  patch.dict('os.environ', {'GEMINI_API_KEY': 'offline-secret'}),
                  patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')),
                  patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS forbidden')),
                  patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden'))):
            p.start(); self.addCleanup(p.stop)

    def test_success_and_duplicate(self):
        raw = json.dumps({'candidates': [{'content': {'parts': [{'text': '안녕하세요!'}]}}],
                          'usageMetadata': {'totalTokenCount': 12}}).encode()
        response = io.BytesIO(raw); response.status = 200
        def fake(req):
            self.assertTrue(g.LEDGER.exists())
            self.assertTrue(json.loads(g.LEDGER.read_text())['consumed'])
            self.assertEqual(req.full_url, g.URL)
            self.assertEqual(req.get_method(), 'POST')
            self.assertEqual(json.loads(req.data), g.PAYLOAD)
            self.assertEqual(req.get_header('X-goog-api-key'), 'offline-secret')
            return response
        with patch.object(g, 'transport', side_effect=fake) as send:
            self.assertTrue(g.run_once()['success'])
            with self.assertRaises(FileExistsError): g.run_once()
            self.assertEqual(send.call_count, 1)

    def test_http_errors_and_timeout(self):
        for status in (401, 403, 429, 302):
            with self.subTest(status=status), patch.object(g, 'LEDGER', Path(self.tmp.name) / str(status)):
                with patch.object(g, 'transport', side_effect=HTTPError(g.URL, status, 'secret', {}, io.BytesIO())) as send:
                    result = g.run_once()
                    self.assertEqual(result['http_status'], status)
                    self.assertFalse(result['success'])
                    with self.assertRaises(FileExistsError): g.run_once()
                    self.assertEqual(send.call_count, 1)
        with patch.object(g, 'transport', side_effect=TimeoutError()):
            self.assertEqual(g.run_once()['error'], 'connect_timeout')

    def test_exception_categories_no_secret_text(self):
        secret = 'offline-secret https://private.invalid/?key=secret'
        cases = [(URLError(socket.gaierror(-2, secret)), 'dns_error'),
                 (socket.gaierror(-2, secret), 'dns_error'),
                 (URLError(ssl.SSLError(secret)), 'tls_error'),
                 (ssl.SSLCertVerificationError(secret), 'tls_error'),
                 (URLError(TimeoutError(secret)), 'connect_timeout'),
                 (ConnectionResetError(secret), 'connection_reset'),
                 (RemoteDisconnected(secret), 'remote_disconnected'),
                 (ConnectionRefusedError(secret), 'connection_error'),
                 (OSError(secret), 'transport_error'),
                 (URLError(secret), 'transport_error'),
                 (RuntimeError(secret), 'local_unexpected_error'),
                 (AttributeError(secret), 'local_unexpected_error'),
                 (g.WallTimeout(secret), 'timeout')]
        for i, (exc, category) in enumerate(cases):
            with self.subTest(category=category), patch.object(g, 'LEDGER', Path(self.tmp.name) / str(i)):
                with patch.object(g, 'transport', side_effect=exc) as send:
                    result = g.run_once()
                    self.assertEqual(result['error'], category)
                    self.assertEqual(result['error_stage'], 'transport_open')
                    self.assertIsNone(result['http_status'])
                    self.assertNotIn(secret, json.dumps(result))
                    self.assertNotIn(secret, g.LEDGER.read_text())
                    with self.assertRaises(FileExistsError): g.run_once()
                    self.assertEqual(send.call_count, 1)

    def test_parse_validate_read_and_timer_stages(self):
        for i, (raw, category, stage) in enumerate([
            (b'{bad', 'parse_error', 'json_parse'),
            (b'{}', 'invalid_response', 'response_validate'),
            (b'{"candidates":null}', 'invalid_response', 'response_validate')]):
            with patch.object(g, 'LEDGER', Path(self.tmp.name) / str(i)):
                response = io.BytesIO(raw); response.status = 200
                with patch.object(g, 'transport', return_value=response):
                    result = g.run_once()
                    self.assertEqual((result['error'], result['error_stage']), (category, stage))
                    self.assertEqual(result['http_status'], 200)
        class ReadTimeout(io.BytesIO):
            status = 200
            def read(self, size): raise TimeoutError('private')
        with patch.object(g, 'transport', return_value=ReadTimeout()):
            result = g.run_once()
            self.assertEqual((result['error'], result['error_stage']), ('read_timeout', 'response_read'))
        with patch.object(g, 'LEDGER', Path(self.tmp.name) / 'timer'):
            original = g.signal.setitimer
            def timer(which, seconds):
                if seconds: raise OSError('private')
                return original(which, seconds)
            with patch.object(g.signal, 'setitimer', side_effect=timer), patch.object(g, 'transport') as send:
                result = g.run_once()
                self.assertEqual((result['error'], result['error_stage']), ('local_unexpected_error', 'timer_setup'))
                send.assert_not_called()

    def test_redirect_and_transport_configuration(self):
        self.assertIsNone(g.NoRedirect().redirect_request(None, None, 302, '', {}, g.URL))
        with patch.object(g, 'build_opener') as build:
            g.transport('request')
            build.return_value.open.assert_called_once_with('request', timeout=30)

    def test_oversize_and_secret_rejected(self):
        for i, raw in enumerate((b'x' * 8193, b'offline-secret')):
            with patch.object(g, 'LEDGER', Path(self.tmp.name) / ('bad' + str(i))):
                response = io.BytesIO(raw); response.status = 200
                with patch.object(g, 'transport', return_value=response):
                    self.assertFalse(g.run_once()['success'])

    def test_missing_key_no_reservation(self):
        with patch.dict('os.environ', {'GEMINI_API_KEY': ''}):
            with self.assertRaises(ValueError): g.run_once()
        self.assertFalse(g.LEDGER.exists())
