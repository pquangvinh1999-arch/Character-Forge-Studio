#!/usr/bin/env python3
"""Check GitHub authentication scopes and optionally prepare forks of upstream repositories.

Default mode (--check) is strictly read-only and never mutates GitHub or local remotes.
Passing --execute requires explicit user authorization and valid 'repo' / 'public_repo' token scopes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR_LOCK = ROOT / "vendor" / "VENDOR_LOCK.json"


def inspect_github_auth() -> dict:
    """Inspect gh CLI auth status and token scopes without mutating anything."""
    status_proc = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    headers_proc = subprocess.run(
        ["gh", "api", "-i", "/user"],
        capture_output=True,
        text=True,
        check=False,
    )
    scopes = ""
    client_id = ""
    for line in headers_proc.stdout.splitlines():
        lower = line.lower()
        if lower.startswith("x-oauth-scopes:"):
            scopes = line.split(":", 1)[1].strip()
        elif lower.startswith("x-oauth-client-id:"):
            client_id = line.split(":", 1)[1].strip()

    scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
    can_fork = any(s in scope_list for s in ("repo", "public_repo"))
    return {
        "authenticated": status_proc.returncode == 0,
        "oauth_client_id": client_id,
        "oauth_scopes": scope_list,
        "can_create_forks": can_fork,
        "blocker": (
            None
            if can_fork
            else "Active GITHUB_TOKEN has empty X-OAuth-Scopes (Codespaces repository-scoped token) and cannot create forks under the user account without 'repo'/'public_repo' scope and explicit user permission."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify or prepare GitHub forks for Character Forge Studio upstreams.")
    parser.add_argument("--execute", action="store_true", help="Actually create forks on GitHub (requires repo scope and user permission).")
    args = parser.parse_args(argv)

    lock = json.loads(VENDOR_LOCK.read_text(encoding="utf-8"))
    auth_report = inspect_github_auth()
    output = {
        "auth": auth_report,
        "repositories": lock.get("repositories", []),
        "executed": False,
    }

    if not args.execute:
        print(json.dumps(output, indent=2))
        return 0

    if not auth_report["can_create_forks"]:
        print(json.dumps(output, indent=2))
        print(f"BLOCKED: {auth_report['blocker']}", file=sys.stderr)
        return 2

    for repo in lock.get("repositories", []):
        upstream = repo["upstream_url"]
        local_dir = ROOT / repo["local_path"]
        subprocess.run(
            ["gh", "repo", "fork", upstream, "--clone=false"],
            cwd=str(local_dir),
            check=True,
        )
    output["executed"] = True
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
