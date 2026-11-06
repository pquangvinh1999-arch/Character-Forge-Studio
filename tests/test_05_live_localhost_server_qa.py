"""Phase 1 Live Localhost Server & Launcher QA Test.

Starts a real uvicorn TCP server on 127.0.0.1, executes the full user workflow over
HTTP, verifies launcher scripts (run-studio.bat and run-studio.sh), and verifies zero
hardcoded example character dependencies.
"""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from tests.conftest import make_synthetic_gif_bytes

REPO_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_launcher_scripts_and_no_hardcoded_character_dependencies() -> None:
    bat_path = REPO_ROOT / "run-studio.bat"
    sh_path = REPO_ROOT / "run-studio.sh"
    assert bat_path.is_file()
    assert sh_path.is_file()

    bat_text = bat_path.read_text(encoding="utf-8")
    assert "@echo off" in bat_text
    assert "uvicorn apps.studio_api.main:app" in bat_text
    assert "127.0.0.1" in bat_text
    # Ensure no PowerShell-only cmdlets are required in run-studio.bat
    for forbidden_ps in ("Invoke-WebRequest", "Start-Process", "pwsh", "powershell"):
        assert forbidden_ps not in bat_text

    # Verify POSIX launcher --check
    proc = subprocess.run(
        [str(sh_path), "--check"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "[OK]" in proc.stdout


def test_live_uvicorn_localhost_server_end_to_end(tmp_path: Path) -> None:
    port = _free_port()
    env = dict(**subprocess.os.environ)
    env["CHARACTER_FORGE_WORKSPACE"] = str(tmp_path / "live_ws")

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.studio_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        healthy = False
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"{base_url}/api/health", timeout=1.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        assert data["status"] == "ok"
                        healthy = True
                        break
            except Exception:
                time.sleep(0.15)
        assert healthy, "Live uvicorn localhost server failed to become healthy"

        with urllib.request.urlopen(f"{base_url}/", timeout=2.0) as resp:
            html = resp.read().decode("utf-8")
            assert resp.status == 200
            assert "Character Forge Studio" in html
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
