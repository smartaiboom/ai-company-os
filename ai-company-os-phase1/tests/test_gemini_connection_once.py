import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import gemini_connection_once as g


class GeminiOnceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (patch.object(g, 'LEDGER', Path(self.tmp.name) / 'operation.json'),
                  patch.dict('os.environ', {'GEMINI_API_KEY': 'offline-secret'}),
                  patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')),
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
            self.assertEqual(g.run_once()['error'], 'timeout')

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
