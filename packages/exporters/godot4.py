"""Godot 4 frame-animation export prototype backed by agent-sprite-forge export_engine.py."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from packages.exporters.manifest import write_character_manifest
from packages.forge_adapter import get_forge_adapter
from packages.project_store import ProjectStore
from packages.qa_gate.godot_smoke import run_godot_import_smoke_test

SAFE_GODOT_NAME = re.compile(r"[^A-Za-z0-9_-]+")


def _sanitize_export_name(raw_name: str) -> str:
    cleaned = SAFE_GODOT_NAME.sub("_", raw_name).strip("_-")
    return cleaned or "character"


def export_godot4_bundle(
    store: ProjectStore,
    project_id: str,
    *,
    version_id: str | None = None,
    run_smoke_test: bool = True,
) -> dict[str, Any]:
    """Export the active project version to Godot 4 SpriteFrames (.tres) + AnimatedSprite2D (.tscn).

    1. Writes the Engine-Independent Character Manifest (character-forge.manifest.v1).
    2. Builds the agent-sprite-forge animation-clips.json (generate2dsprite.animation_clips.v2).
    3. Invokes agent-sprite-forge's export_engine.py (--target all: godot-spriteframes + aseprite-json)
       which performs byte-exact RGBA and .tres/.tscn round-trip parser verification.
    4. Optionally runs a real headless Godot 4 import & GDScript verification smoke test.
    """
    proj = store.load_project(project_id)
    store.verify_original_unchanged(project_id, project_data=proj)
    vdoc = store.get_version_doc(project_id, version_id)
    active_vid = vdoc["version_id"]
    pdir = store.project_dir(project_id)

    char_manifest_res = write_character_manifest(store, project_id, version_id=active_vid)
    char_manifest = char_manifest_res["manifest"]

    export_name = _sanitize_export_name(proj["name"])
    export_id = f"godot4_{active_vid}_{uuid.uuid4().hex[:6]}"
    export_root = pdir / "exports" / export_id
    staging_clips_dir = export_root / "clips_source"
    staging_Frames_dir = staging_clips_dir / "frames"
    staging_Frames_dir.mkdir(parents=True, exist_ok=True)

    # Copy active version frames into staging_clips_dir/frames/ with relative paths for export_engine.py
    forge_frames: list[dict[str, Any]] = []
    for f in vdoc["frames"]:
        idx = int(f["index"])
        src_png = pdir / f["file"]
        rel_png = f"frames/frame_{idx:04d}.png"
        dst_png = staging_clips_dir / rel_png
        shutil.copy2(src_png, dst_png)
        forge_frames.append(
            {
                "index": idx,
                "file": rel_png,
                "rgba_pixel_sha256": f["rgba_pixel_sha256"],
            }
        )

    clip_name = _sanitize_export_name(proj.get("default_clip", "idle")).lower()
    durations = [int(f["duration_ms"]) for f in vdoc["frames"]]
    loop = bool(proj.get("loop", True))

    clips_v2 = {
        "schema": "generate2dsprite.animation_clips.v2",
        "frame_size": [proj["width"], proj["height"]],
        "anchor_px": proj["anchor_px"],
        "sampling": "nearest",
        "pixel_art": True,
        "frames": forge_frames,
        "clips": {
            clip_name: {
                "frames": [int(f["index"]) for f in vdoc["frames"]],
                "duration_ms": durations,
                "loop": loop,
                "loop_policy": "cycle" if loop else "oneshot",
            }
        },
        "states": {
            "idle": clip_name,
        },
    }
    clips_json_path = staging_clips_dir / "animation-clips.json"
    clips_json_path.write_text(json.dumps(clips_v2, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    engine_out_dir = export_root / "bundle"
    forge = get_forge_adapter()
    export_summary = forge.export_clips_to_engine(
        clips_manifest_path=clips_json_path,
        output_dir=engine_out_dir,
        name=export_name,
        target="godot-spriteframes",
        sampling="nearest",
    )

    godot_subdir = engine_out_dir / "godot"
    tres_path = godot_subdir / f"{export_name}.tres"
    tscn_path = godot_subdir / f"{export_name}.tscn"
    atlas_paths = sorted(str(p.relative_to(pdir).as_posix()) for p in godot_subdir.glob("*.png"))

    smoke_report: dict[str, Any] | None = None
    if run_smoke_test:
        smoke_report = run_godot_import_smoke_test(godot_subdir, export_name)

    store.verify_original_unchanged(project_id)

    return {
        "schema": "character-forge.godot_export_result.v1",
        "project_id": project_id,
        "version_id": active_vid,
        "export_id": export_id,
        "export_name": export_name,
        "character_manifest_path": char_manifest_res["relative_path"],
        "character_manifest": char_manifest,
        "godot_bundle_dir": str(godot_subdir.relative_to(pdir).as_posix()),
        "files": {
            "sprite_frames_tres": str(tres_path.relative_to(pdir).as_posix()),
            "animated_sprite_2d_tscn": str(tscn_path.relative_to(pdir).as_posix()),
            "atlas_pngs": atlas_paths,
            "engine_export_json": str((engine_out_dir / "engine-export.json").relative_to(pdir).as_posix()),
        },
        "forge_export_summary": export_summary,
        "godot_smoke_test": smoke_report,
    }
