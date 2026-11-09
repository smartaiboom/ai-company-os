"""Isolated, explicitly authorized greeting check; never imports the company engine."""
import json
import os
import re
import signal
import socket
import ssl
from http.client import RemoteDisconnected, HTTPException
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

STAGES = frozenset(('timer_setup', 'transport_open', 'response_read', 'json_parse',
                    'response_validate', 'timer_cleanup', 'ledger_save'))


def error_category(exc, stage):
    """Only fixed enums from exception types; never stringify an exception/reason."""
    if stage not in STAGES:
        return 'local_unexpected_error'
    if isinstance(exc, HTTPError) and stage in ('transport_open', 'response_read'):
        code = exc.code
        return {400: '400_payload', 401: '401_auth', 403: '403_permission',
                404: '404_model', 429: '429_limit'}.get(code,
                '5xx_server' if type(code) is int and 500 <= code <= 599 else 'http_error')
    if stage == 'json_parse' and isinstance(exc, (ValueError, UnicodeError)):
        return 'parse_error'
    if stage == 'response_validate' and isinstance(exc, (ValueError, KeyError, IndexError, TypeError, AttributeError)):
        return 'invalid_response'
    if stage not in ('transport_open', 'response_read'):
        return 'local_unexpected_error'
    # URLError.reason may be an exception or arbitrary text. Never inspect text.
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, socket.gaierror):
        return 'dns_error'
    if isinstance(reason, ssl.SSLError):
        return 'tls_error'
    if isinstance(reason, TimeoutError):
        return 'connect_timeout' if stage == 'transport_open' else 'read_timeout'
    if isinstance(reason, RemoteDisconnected):
        return 'remote_disconnected'
    if isinstance(reason, ConnectionResetError):
        return 'connection_reset'
    if isinstance(reason, ConnectionError):
        return 'connection_error'
    if isinstance(exc, URLError) or isinstance(reason, (OSError, HTTPException)):
        return 'transport_error'
    return 'local_unexpected_error'


class WallTimeout(TimeoutError):
    pass

MODEL = 'gemini-2.5-flash-lite'
URL = 'https://generativelanguage.googleapis.com/v1beta/models/' + MODEL + ':generateContent'
ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / 'data/gemini-connection-once-20261104.json'
PAYLOAD = {'contents': [{'role': 'user', 'parts': [{'text': '안녕하세요. 한 문장으로 한국어 인사만 해 주세요.'}]}],
           'generationConfig': {'maxOutputTokens': 80, 'temperature': 0.2}}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def now():
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')


def transport(request):
    # Default proxy and TLS policy retained; no retry handler.
    return build_opener(NoRedirect()).open(request, timeout=30)


def run_once():
    key = os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        raise ValueError('missing_key')
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError('timer_in_use')
    request = Request(URL, data=json.dumps(PAYLOAD, ensure_ascii=False).encode(),
                      headers={'x-goog-api-key': key, 'Content-Type': 'application/json'}, method='POST')
    record = {'operation_id': 'gemini-greeting-20261104-secret-restart', 'timestamp_kst': now(),
              'consumed': True, 'attempts': 1, 'success': False, 'http_status': None,
              'error': 'uncertain', 'retries': 0}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(LEDGER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump(record, file); file.flush(); os.fsync(file.fileno())
    directory = os.open(LEDGER.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    def expired(signum, frame):
        raise WallTimeout()
    previous = signal.signal(signal.SIGALRM, expired)
    stage = 'timer_setup'
    try:
        signal.setitimer(signal.ITIMER_REAL, 30)
        stage = 'transport_open'
        with transport(request) as response:
            stage = 'response_read'
            record['http_status'] = int(response.status)
            raw = response.read(8193)
        stage = 'response_validate'
        if len(raw) > 8192 or key.encode() in raw or record['http_status'] != 200:
            raise ValueError('invalid_response')
        stage = 'json_parse'
        value = json.loads(raw)
        stage = 'response_validate'
        text = value['candidates'][0]['content']['parts'][0]['text'].strip()
        # Only a short Korean greeting, never arbitrary returned identifiers.
        if not re.fullmatch(r'[가-힣 .,!?~。！]{1,200}', text) or '안녕' not in text:
            raise ValueError('invalid_greeting')
        record.update(success=True, error=None, greeting=text)
        record['tokens'] = {k: v for k, v in value.get('usageMetadata', {}).items()
                            if k in ('promptTokenCount', 'candidatesTokenCount', 'totalTokenCount')
                            and type(v) is int and v >= 0}
    except Exception as exc:
        record.update(success=False, error='timeout' if isinstance(exc, WallTimeout)
                      else error_category(exc, stage), error_stage=stage)
        record.pop('greeting', None)
        record.pop('tokens', None)
        if isinstance(exc, HTTPError):
            record['http_status'] = exc.code if type(exc.code) is int and 100 <= exc.code <= 599 else None
            exc.close()
    finally:
        try:
            signal.setitimer(signal.ITIMER_REAL, 0)
        finally:
            signal.signal(signal.SIGALRM, previous)
    record['finished_kst'] = now()
    with LEDGER.open('w') as file:
        json.dump(record, file, ensure_ascii=False); file.flush(); os.fsync(file.fileno())
    return record


if __name__ == '__main__':
    try:
        result = run_once()
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if result['success'] else 1)
    except (ValueError, OSError):
        print('실행 차단: 키 또는 기존 선예약 확인 필요. 재송신하지 않습니다.')
        raise SystemExit(1)
