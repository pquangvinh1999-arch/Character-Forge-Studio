#!/usr/bin/env python3
"""Ensure pinned upstream repositories in vendor/ are present and checked out at exact commits.

Reads vendor/VENDOR_LOCK.json. If a vendor checkout is missing on a fresh machine,
clones the upstream URL and checks out the exact pinned SHA-1 commit.
Never modifies existing vendor files.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_LOCK = REPO_ROOT / "vendor" / "VENDOR_LOCK.json"


def ensure_vendors(verify_only: bool = False) -> list[dict[str, str]]:
    if not VENDOR_LOCK.is_file():
        raise FileNotFoundError(f"Missing lockfile: {VENDOR_LOCK}")
    lock = json.loads(VENDOR_LOCK.read_text(encoding="utf-8"))
    results: list[dict[str, str]] = []

    for repo in lock.get("repositories", []):
        name = repo["name"]
        local_dir = REPO_ROOT / repo["local_path"]
        target_commit = repo["commit"]
        upstream_url = repo["upstream_url"]

        if not (local_dir / ".git").exists():
            if verify_only:
                raise RuntimeError(f"Vendor repository missing: {local_dir}")
            local_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", upstream_url, str(local_dir)], check=True)
            subprocess.run(["git", "-C", str(local_dir), "checkout", target_commit], check=True)

        head = subprocess.run(
            ["git", "-C", str(local_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        if head != target_commit:
            if verify_only:
                raise RuntimeError(f"Vendor {name} HEAD {head} != pinned {target_commit}")
            subprocess.run(["git", "-C", str(local_dir), "checkout", target_commit], check=True)
            head = target_commit

        results.append({"name": name, "commit": head, "license": repo["license"], "status": "verified"})
    return results


def main() -> int:
    verify_only = "--verify" in sys.argv
    res = ensure_vendors(verify_only=verify_only)
    print(json.dumps({"vendors": res}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
