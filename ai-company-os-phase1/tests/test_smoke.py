import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app.py"

def test_health_endpoint():
    with tempfile.TemporaryDirectory() as temp:
        env = os.environ.copy()
        env["AI_COMPANY_OS_HOST"] = "127.0.0.1"
        env["AI_COMPANY_OS_PORT"] = "18765"
        # The app stores data relative to its own folder, so this smoke test only
        # checks startup/health and should be run in a disposable copy if needed.
        proc = subprocess.Popen([sys.executable, str(APP)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for _ in range(30):
                try:
                    with urllib.request.urlopen("http://127.0.0.1:18765/health", timeout=1) as response:
                        assert response.status == 200
                        assert b"Phase 1 app is running" in response.read()
                        break
                except Exception:
                    time.sleep(0.2)
            else:
                raise AssertionError("Health endpoint did not become available")
        finally:
            proc.terminate()
            proc.wait(timeout=5)
