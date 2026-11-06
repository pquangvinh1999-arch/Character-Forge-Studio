"""Phase 1 Verification: Engine-Independent Character Manifest and Real Godot 4 Export + Headless Smoke Test."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from packages.qa_gate.godot_smoke import run_godot_import_smoke_test
from tests.conftest import make_synthetic_gif_bytes


def test_character_manifest_and_real_godot4_export_and_headless_smoke_test(client: TestClient) -> None:
    """Acceptance Criterion #7:
    - Produce an engine-independent character manifest.
    - Add a working Godot 4 frame-animation export prototype (.tres + .tscn + atlas PNG).
    - A real Godot import smoke test passes (or is explicitly marked blocked if Godot is unavailable).
    """
    gif_bytes, expected_durations = make_synthetic_gif_bytes(width=32, height=32, frame_count=4)
    up_res = client.post(
        "/api/projects/upload",
        files={"file": ("paladin_walk.gif", gif_bytes, "image/gif")},
        data={"name": "paladin_walk", "clip_name": "walk"},
    )
    assert up_res.status_code == 200
    proj = up_res.json()
    pid = proj["project_id"]

    # 1. Test Engine-Independent Character Manifest
    man_res = client.post(f"/api/projects/{pid}/export/manifest")
    assert man_res.status_code == 200
    man_payload = man_res.json()
    manifest = man_payload["manifest"]
    assert manifest["schema"] == "character-forge.manifest.v1"
    assert manifest["project_id"] == pid
    assert manifest["version_id"] == "v0001"
    assert manifest["geometry"]["frame_size"] == [32, 32]
    assert manifest["source_provenance"]["original_unchanged_verified"] is True
    assert len(manifest["frames"]) == 4
    assert "walk" in manifest["clips"]
    assert manifest["clips"]["walk"]["duration_ms"] == expected_durations

    # 2. Test Godot 4 Export + Real Headless Smoke Test
    godot_res = client.post(
        f"/api/projects/{pid}/export/godot4",
        json={"run_smoke_test": True},
    )
    assert godot_res.status_code == 200
    export_data = godot_res.json()
    assert export_data["schema"] == "character-forge.godot_export_result.v1"
    assert export_data["forge_export_summary"]["status"] == "pass"

    store = client.app.state.store
    pdir = store.project_dir(pid)
    tres_file = pdir / export_data["files"]["sprite_frames_tres"]
    tscn_file = pdir / export_data["files"]["animated_sprite_2d_tscn"]
    export_json_file = pdir / export_data["files"]["engine_export_json"]
    assert tres_file.is_file()
    assert tscn_file.is_file()
    assert export_json_file.is_file()
    assert len(export_data["files"]["atlas_pngs"]) >= 1

    tres_text = tres_file.read_text(encoding="utf-8")
    assert '[gd_resource type="SpriteFrames"' in tres_text
    assert 'SubResource("AtlasTexture_' in tres_text

    tscn_text = tscn_file.read_text(encoding="utf-8")
    assert 'type="AnimatedSprite2D"' in tscn_text

    # Verify real Godot 4 headless smoke test passed
    smoke = export_data["godot_smoke_test"]
    assert smoke is not None
    assert smoke["godot_binary_available"] is True
    assert smoke["status"] == "passed", f"Godot smoke test failed: {smoke}"
    assert smoke["verdict"] == "COMPLIANT"
    assert smoke["verify_exit_code"] == 0
    engine_ver = smoke["engine_verification"]
    assert engine_ver is not None
    assert "walk" in engine_ver["animations"]
    assert engine_ver["frame_count"] == 4
    assert engine_ver["frame_0_size"] == [32, 32]


def test_godot_smoke_test_explicit_blocked_status_when_binary_unavailable(tmp_path: Path) -> None:
    """Verify that if Godot is unavailable, the smoke test explicitly reports 'blocked' / 'NOT ASSESSED'."""
    dummy_dir = tmp_path / "godot_export"
    report = run_godot_import_smoke_test(
        dummy_dir,
        "test_hero",
        force_godot_bin="/nonexistent/godot4_binary",
    )
    assert report["status"] == "blocked"
    assert report["verdict"] == "NOT ASSESSED"
    assert report["godot_binary_available"] is False
    assert (dummy_dir / "project.godot").is_file()
    assert (dummy_dir / "verify_import.gd").is_file()
