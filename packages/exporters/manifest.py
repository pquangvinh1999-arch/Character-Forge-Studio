"""Engine-independent character manifest generator (character-forge.manifest.v1)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.project_store import ProjectStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def build_character_manifest(
    store: ProjectStore,
    project_id: str,
    *,
    version_id: str | None = None,
) -> dict[str, Any]:
    """Build an engine-independent character manifest for the specified project and version."""
    proj = store.load_project(project_id)
    store.verify_original_unchanged(project_id, project_data=proj)
    vdoc = store.get_version_doc(project_id, version_id)
    active_vid = vdoc["version_id"]

    frames_list = vdoc["frames"]
    durations = [int(f["duration_ms"]) for f in frames_list]
    total_ms = sum(durations)
    fps = round((len(frames_list) * 1000.0) / total_ms, 2) if total_ms > 0 else 10.0
    clip_name = proj.get("default_clip", "idle")
    loop = bool(proj.get("loop", True))

    return {
        "schema": "character-forge.manifest.v1",
        "generated_at": _utc_now(),
        "project_id": proj["project_id"],
        "character_name": proj["name"],
        "version_id": active_vid,
        "parent_version_id": vdoc.get("parent_version_id"),
        "source_provenance": {
            "original_filename": proj["original_file"]["filename"],
            "original_format": proj["original_file"]["format"],
            "original_sha256": proj["original_file"]["sha256"],
            "original_size_bytes": proj["original_file"]["size_bytes"],
            "original_unchanged_verified": True,
        },
        "geometry": {
            "frame_size": [proj["width"], proj["height"]],
            "anchor_px": proj["anchor_px"],
            "pixel_pitch_estimate": proj.get("pixel_pitch_estimate", 1),
            "sampling": "nearest",
            "pixel_art": True,
        },
        "frames": [
            {
                "index": int(f["index"]),
                "file": f["file"],
                "duration_ms": int(f["duration_ms"]),
                "rgba_pixel_sha256": f["rgba_pixel_sha256"],
                "png_file_sha256": f["png_file_sha256"],
                "bbox": f["bbox"],
                "anchor_px": f["anchor_px"],
                "opaque_pixels": f["opaque_pixels"],
            }
            for f in frames_list
        ],
        "clips": {
            clip_name: {
                "name": clip_name,
                "frames": [int(f["index"]) for f in frames_list],
                "duration_ms": durations,
                "total_duration_ms": total_ms,
                "fps": fps,
                "loop": loop,
                "loop_policy": "cycle" if loop else "oneshot",
            }
        },
        "states": {
            "idle": clip_name,
        },
        "target_engines": ["godot4", "unity", "aseprite"],
    }


def write_character_manifest(
    store: ProjectStore,
    project_id: str,
    *,
    version_id: str | None = None,
) -> dict[str, Any]:
    """Write the engine-independent character manifest to disk and return its content and path."""
    manifest = build_character_manifest(store, project_id, version_id=version_id)
    vid = manifest["version_id"]
    out_dir = store.project_dir(project_id) / "exports" / f"manifest_{vid}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "character_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "manifest_path": str(out_path),
        "relative_path": f"exports/manifest_{vid}/character_manifest.json",
        "manifest": manifest,
    }
