"""One-shot structured manager payload check against Gemini 3.5 Flash-Lite.
No company execute, no original project data, no retries, no raw output persistence.
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from diagnostics.gemini_request_shape_probe_20261104 import manager_plan

MODEL = "gemini-3.5-flash-lite"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent"
LEDGER = Path(__file__).resolve().parents[1] / "data" / "gemini-35-lite-manager-shape-once-20261104.json"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def now():
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def main():
    if os.getenv("GEMINI_DIAG_FREE_TIER_CONFIRMED") != "YES":
        raise SystemExit("프로젝트의 Gemini API 무료 등급을 먼저 확인하세요.")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit("GEMINI_API_KEY가 없습니다.")
    payload = manager_plan()  # uses actual 4096-output-token, structured-json/schema path; synthetic goal
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "model": MODEL, "started_kst": now(), "attempts": 1,
        "request_bytes": len(body), "structured_json_schema": True,
        "max_output_tokens": 4096, "http_status": None,
        "error_status_enum": None, "response_received": False,
        "candidate_stop": False, "manager_plan_structure": False,
        "prompt_tokens": None, "output_tokens": None,
        "elapsed_seconds": None, "error_kind": None, "status": "reserved",
    }
    fd = os.open(LEDGER, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    started = time.monotonic()
    try:
        request = Request(ENDPOINT, body, method="POST", headers={
            "Content-Type": "application/json", "x-goog-api-key": key,
        })
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=40) as response:
            result["http_status"] = response.status
            raw = response.read(131073)
            result["response_received"] = True
        if len(raw) > 131072:
            result["error_kind"] = "response_too_large"
        else:
            try:
                data = json.loads(raw)
                candidates = data.get("candidates", []) if isinstance(data, dict) else []
                if isinstance(candidates, list) and len(candidates) == 1 and isinstance(candidates[0], dict):
                    candidate = candidates[0]
                    result["candidate_stop"] = candidate.get("finishReason") == "STOP"
                    parts = candidate.get("content", {}).get("parts", [])
                    texts = [p["text"] for p in parts if isinstance(p, dict)
                             and isinstance(p.get("text"), str) and not p.get("thought")]
                    if texts and result["candidate_stop"]:
                        output = json.loads("".join(texts))
                        from role_json_schema import response_format, matches
                        result["manager_plan_structure"] = matches(
                            output, response_format("plan")["json_schema"]["schema"])
                usage = data.get("usageMetadata", {}) if isinstance(data, dict) else {}
                if isinstance(usage, dict):
                    for src, dst in (("promptTokenCount", "prompt_tokens"),
                                     ("candidatesTokenCount", "output_tokens")):
                        n = usage.get(src)
                        if type(n) is int and 0 <= n <= 1000000:
                            result[dst] = n
            except (ValueError, TypeError, AttributeError, UnicodeDecodeError):
                result["error_kind"] = "response_format_invalid"
    except HTTPError as err:
        result["http_status"] = err.code
        result["error_kind"] = "http_error"
        try:
            obj = json.loads(err.read(8192))
            s = obj.get("error", {}).get("status") if isinstance(obj, dict) else None
            if s in {"UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED",
                     "INVALID_ARGUMENT", "PERMISSION_DENIED", "UNAUTHENTICATED",
                     "INTERNAL", "NOT_FOUND", "FAILED_PRECONDITION"}:
                result["error_status_enum"] = s
        except (ValueError, TypeError, AttributeError, UnicodeDecodeError):
            pass
        err.close()
    except (URLError, TimeoutError, OSError) as err:
        result["error_kind"] = "timeout" if isinstance(err, TimeoutError) else "transport_error"
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        result["finished_kst"] = now()
        result["status"] = "finished"
        LEDGER.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
