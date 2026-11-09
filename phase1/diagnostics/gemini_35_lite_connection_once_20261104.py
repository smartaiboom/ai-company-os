"""Single consented Gemini 3.5 Flash-Lite connection probe; not a company run.
Only one POST, no retry/fallback and no mutation of previous projects/ledgers.
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

MODEL = "gemini-3.5-flash-lite"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent"
LEDGER = Path(__file__).resolve().parents[1] / "data" / "gemini-35-lite-connection-once-20261104.json"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def timestamp():
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def main():
    if os.environ.get("GEMINI_DIAG_FREE_TIER_CONFIRMED") != "YES":
        raise SystemExit("먼저 API 키가 속한 프로젝트의 Gemini Free Tier를 확인하세요.")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit("GEMINI_API_KEY가 없습니다.")
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "안녕하세요. 한국어로 한 문장만 답변해 주세요."}]}],
        "generationConfig": {"maxOutputTokens": 100, "temperature": 0.2},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "model": MODEL, "started_kst": timestamp(), "attempts": 1,
        "status": "reserved", "http_status": None, "error_status_enum": None,
        "request_bytes": len(body), "elapsed_seconds": None,
        "response_received": False, "candidate_stop": False,
        "error_kind": None, "prompt_tokens": None, "output_tokens": None,
    }
    # Consume the single attempt before network I/O. Never retry a used marker.
    fd = os.open(LEDGER, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    opened = time.monotonic()
    try:
        request = Request(ENDPOINT, data=body, method="POST", headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        })
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=40) as res:
            record["http_status"] = res.status
            raw = res.read(16385)
            record["response_received"] = True
        if len(raw) > 16384:
            record["error_kind"] = "response_too_large"
        else:
            try:
                result = json.loads(raw)
                candidates = result.get("candidates", []) if isinstance(result, dict) else []
                record["candidate_stop"] = bool(candidates and isinstance(candidates[0], dict)
                                                and candidates[0].get("finishReason") == "STOP")
                usage = result.get("usageMetadata", {}) if isinstance(result, dict) else {}
                if isinstance(usage, dict):
                    for old, new in (("promptTokenCount", "prompt_tokens"),
                                     ("candidatesTokenCount", "output_tokens")):
                        n = usage.get(old)
                        if type(n) is int and 0 <= n <= 1000000:
                            record[new] = n
            except (ValueError, UnicodeDecodeError, TypeError):
                record["error_kind"] = "response_json_invalid"
    except HTTPError as exc:
        record["http_status"] = exc.code
        record["error_kind"] = "http_error"
        try:
            payload = json.loads(exc.read(8192))
            status = payload.get("error", {}).get("status") if isinstance(payload, dict) else None
            if status in {"UNAVAILABLE", "RESOURCE_EXHAUSTED", "INVALID_ARGUMENT",
                          "PERMISSION_DENIED", "UNAUTHENTICATED", "NOT_FOUND",
                          "INTERNAL", "DEADLINE_EXCEEDED"}:
                record["error_status_enum"] = status
        except (ValueError, UnicodeDecodeError, TypeError, AttributeError):
            pass
        exc.close()
    except (URLError, OSError, TimeoutError) as exc:
        record["error_kind"] = "timeout" if isinstance(exc, TimeoutError) else "transport_error"
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - opened, 2)
        record["finished_kst"] = timestamp()
        record["status"] = "finished"
        LEDGER.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
