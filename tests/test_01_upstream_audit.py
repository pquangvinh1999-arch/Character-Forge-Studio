"""Phase 0 Verification: Upstream repository audit, commits, licenses, NOTICE, and untouched vendor tree."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_LOCK = REPO_ROOT / "vendor" / "VENDOR_LOCK.json"

EXPECTED_UPSTREAMS = {
    "agent-sprite-forge": {
        "commit": "72fa5ad92d79b811acff464da32c8f3b1caa010f",
        "license": "MIT",
    },
    "sprite-gen": {
        "commit": "4f5ccd55c7cf06685a41f954acc1e476b7772ece",
        "license": "Apache-2.0",
    },
    "Claude-Code-Game-Studios": {
        "commit": "05ad7c8a5b8aa2aa86bbd3439ae7cf7295cac418",
        "license": "MIT",
    },
}


def test_vendor_lock_and_upstream_commits_and_licenses() -> None:
    assert VENDOR_LOCK.is_file(), "vendor/VENDOR_LOCK.json must exist"
    lock_data = json.loads(VENDOR_LOCK.read_text(encoding="utf-8"))
    repos = {r["name"]: r for r in lock_data["repositories"]}
    assert set(repos.keys()) == set(EXPECTED_UPSTREAMS.keys())

    for name, expected in EXPECTED_UPSTREAMS.items():
        record = repos[name]
        assert record["commit"] == expected["commit"]
        assert record["license"] == expected["license"]

        local_dir = REPO_ROOT / record["local_path"]
        assert local_dir.is_dir(), f"Missing vendor checkout: {local_dir}"

        # Verify actual git HEAD inside vendor checkout matches pinned commit
        head_proc = subprocess.run(
            ["git", "-C", str(local_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert head_proc.stdout.strip() == expected["commit"]

        # Verify vendor working tree is 100% clean (never overwritten or modified)
        status_proc = subprocess.run(
            ["git", "-C", str(local_dir), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert status_proc.stdout.strip() == "", f"Vendor repo {name} was modified: {status_proc.stdout}"

        # Verify license file exists
        license_file = REPO_ROOT / record["license_file"]
        assert license_file.is_file()
        if record.get("notice_file"):
            notice_file = REPO_ROOT / record["notice_file"]
            assert notice_file.is_file()


def test_required_phase0_and_phase2_docs_exist() -> None:
    required_files = [
        "THIRD_PARTY_NOTICES.md",
        "AGENTS.md",
        "run-studio.bat",
        "docs/audit/UPSTREAM_AUDIT.md",
        "docs/architecture/ARCHITECTURE.md",
        "docs/architecture/INTEGRATION_MATRIX.md",
        "docs/architecture/PHASE2_TECHNICAL_SPECS.md",
        "docs/roadmap/IMPLEMENTATION_PLAN.md",
        ".agents/skills/character-asset-spec/SKILL.md",
        ".agents/skills/pixel-region-edit/SKILL.md",
        ".agents/skills/godot-unity-export-qa/SKILL.md",
    ]
    for rel in required_files:
        path = REPO_ROOT / rel
        assert path.is_file(), f"Missing required deliverable file: {rel}"
        assert path.stat().st_size > 100, f"Deliverable file {rel} is unexpectedly empty"

    audit_text = (REPO_ROOT / "docs/audit/UPSTREAM_AUDIT.md").read_text(encoding="utf-8")
    for info in EXPECTED_UPSTREAMS.values():
        assert info["commit"] in audit_text
