"""Project persistence, immutable version snapshots, and rollback engine.

Guarantees that the uploaded source asset in original/ is never modified.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from packages.character_core.coords import inspect_pixel_at
from packages.character_core.gif_extractor import extract_frames_from_file
from packages.character_core.ingest import validate_upload_bytes
from packages.forge_adapter import get_forge_adapter

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE_DIR = REPO_ROOT / "workspace"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class ProjectStore:
    """Manage Character Forge Studio projects, versions, and rollbacks on disk."""

    def __init__(self, workspace_dir: str | Path | None = None) -> None:
        env_ws = os.environ.get("CHARACTER_FORGE_WORKSPACE")
        base = Path(workspace_dir) if workspace_dir is not None else (Path(env_ws) if env_ws else DEFAULT_WORKSPACE_DIR)
        self.workspace_dir = base.resolve()
        self.projects_dir = self.workspace_dir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.forge = get_forge_adapter()

    def project_dir(self, project_id: str) -> Path:
        clean_id = "".join(c for c in project_id if c.isalnum() or c in "-_")
        if not clean_id or clean_id != project_id:
            raise ValueError(f"Invalid project_id: {project_id!r}")
        return self.projects_dir / clean_id

    def _project_json_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "project.json"

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / f".{path.name}.{uuid.uuid4().hex[:8]}.tmp"
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    def list_projects(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self.projects_dir.is_dir():
            return results
        for folder in sorted(self.projects_dir.iterdir()):
            pjson = folder / "project.json"
            if pjson.is_file():
                try:
                    data = json.loads(pjson.read_text(encoding="utf-8"))
                    results.append(
                        {
                            "project_id": data["project_id"],
                            "name": data["name"],
                            "created_at": data["created_at"],
                            "updated_at": data["updated_at"],
                            "source_format": data["source_format"],
                            "width": data["width"],
                            "height": data["height"],
                            "frame_count": data["frame_count"],
                            "current_version_id": data["current_version_id"],
                            "version_count": len(data.get("versions", [])),
                        }
                    )
                except Exception:
                    continue
        return sorted(results, key=lambda item: item["updated_at"], reverse=True)

    def load_project(self, project_id: str) -> dict[str, Any]:
        pjson = self._project_json_path(project_id)
        if not pjson.is_file():
            raise FileNotFoundError(f"Project not found: {project_id}")
        project = json.loads(pjson.read_text(encoding="utf-8"))
        integrity = self.verify_original_unchanged(project_id, project_data=project)
        project["original_integrity"] = integrity
        return project

    def save_project(self, project_id: str, project_data: dict[str, Any]) -> dict[str, Any]:
        project_data["updated_at"] = _utc_now()
        self._write_json_atomic(self._project_json_path(project_id), project_data)
        return self.load_project(project_id)

    def verify_original_unchanged(
        self,
        project_id: str,
        *,
        project_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Verify that the uploaded original asset is byte-for-byte unchanged."""
        proj = project_data or json.loads(self._project_json_path(project_id).read_text(encoding="utf-8"))
        orig_meta = proj["original_file"]
        orig_path = self.project_dir(project_id) / orig_meta["relative_path"]
        if not orig_path.is_file():
            raise RuntimeError(f"Original asset file missing: {orig_path}")
        actual_sha = self.forge.sha256_file(orig_path)
        actual_size = orig_path.stat().st_size
        unchanged = (actual_sha == orig_meta["sha256"]) and (actual_size == orig_meta["size_bytes"])
        if not unchanged:
            raise RuntimeError(
                f"Original asset integrity violation for {project_id}: expected {orig_meta['sha256']}, got {actual_sha}"
            )
        return {
            "unchanged": True,
            "path": orig_meta["relative_path"],
            "expected_sha256": orig_meta["sha256"],
            "actual_sha256": actual_sha,
            "size_bytes": actual_size,
        }

    def create_project(
        self,
        filename: str,
        raw_bytes: bytes,
        *,
        name: str | None = None,
        clip_name: str = "idle",
    ) -> dict[str, Any]:
        """Create a new project from uploaded PNG or GIF bytes and extract initial frames into v0001."""
        info = validate_upload_bytes(filename, raw_bytes)
        timestamp = _utc_now()
        short_uid = uuid.uuid4().hex[:8]
        safe_stem = info["safe_stem"]
        project_id = f"{safe_stem}-{short_uid}"
        pdir = self.project_dir(project_id)
        orig_dir = pdir / "original"
        orig_dir.mkdir(parents=True, exist_ok=False)

        orig_rel = f"original/{info['safe_filename']}"
        orig_path = pdir / orig_rel
        # Write original file once and make read-only where supported
        with open(orig_path, "xb") as f:
            f.write(raw_bytes)
        orig_sha256 = self.forge.sha256_bytes(raw_bytes)

        extracted = extract_frames_from_file(orig_path)

        # Write version v0001
        version_id = "v0001"
        vdir = pdir / "versions" / version_id
        frames_dir = vdir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        frame_records: list[dict[str, Any]] = []
        for ef in extracted.frames:
            fname = f"frame_{ef.index:04d}.png"
            fpath = frames_dir / fname
            self.forge.save_png_canonical(ef.pixels, fpath)
            png_sha256 = self.forge.sha256_file(fpath)
            frame_records.append(
                {
                    "index": ef.index,
                    "file": f"versions/{version_id}/frames/{fname}",
                    "duration_ms": ef.duration_ms,
                    "rgba_pixel_sha256": ef.sha256,
                    "png_file_sha256": png_sha256,
                    "bbox": ef.bbox,
                    "anchor_px": ef.anchor_px,
                    "opaque_pixels": ef.opaque_pixels,
                }
            )

        version_doc = {
            "version_id": version_id,
            "parent_version_id": None,
            "created_at": timestamp,
            "kind": "initial_import",
            "summary": f"Imported {info['safe_filename']} ({extracted.frame_count} frame(s), {extracted.width}x{extracted.height})",
            "job_id": None,
            "frames": frame_records,
            "original_sha256": orig_sha256,
        }
        self._write_json_atomic(vdir / "version.json", version_doc)

        project_doc = {
            "schema": "character-forge.project.v1",
            "project_id": project_id,
            "name": name or safe_stem,
            "created_at": timestamp,
            "updated_at": timestamp,
            "source_format": extracted.source_format,
            "width": extracted.width,
            "height": extracted.height,
            "frame_count": extracted.frame_count,
            "total_duration_ms": extracted.total_duration_ms,
            "fps": extracted.average_fps,
            "loop": True,
            "default_clip": clip_name,
            "anchor_px": extracted.anchor_px,
            "pixel_pitch_estimate": extracted.pixel_pitch_estimate,
            "dominant_palette": extracted.dominant_palette,
            "motion_summary": extracted.motion_summary,
            "original_file": {
                "filename": info["safe_filename"],
                "relative_path": orig_rel,
                "sha256": orig_sha256,
                "size_bytes": len(raw_bytes),
                "format": extracted.source_format,
            },
            "current_version_id": version_id,
            "versions": [version_doc],
            "rollback_history": [],
            "jobs": [],
        }
        self._write_json_atomic(self._project_json_path(project_id), project_doc)
        return self.load_project(project_id)

    def get_version_doc(self, project_id: str, version_id: str | None = None) -> dict[str, Any]:
        proj = self.load_project(project_id)
        target_vid = version_id or proj["current_version_id"]
        for v in proj["versions"]:
            if v["version_id"] == target_vid:
                return v
        raise KeyError(f"Version {target_vid!r} not found in project {project_id}")

    def get_frame_path(self, project_id: str, frame_index: int, version_id: str | None = None) -> Path:
        vdoc = self.get_version_doc(project_id, version_id)
        frames = vdoc["frames"]
        if not (0 <= frame_index < len(frames)):
            raise IndexError(f"Frame index {frame_index} out of range (0..{len(frames) - 1})")
        return self.project_dir(project_id) / frames[frame_index]["file"]

    def load_frame_rgba(self, project_id: str, frame_index: int, version_id: str | None = None) -> np.ndarray:
        fpath = self.get_frame_path(project_id, frame_index, version_id)
        return self.forge.load_rgba_canonical(fpath)

    def inspect_frame_pixel(
        self,
        project_id: str,
        frame_index: int,
        x: int,
        y: int,
        version_id: str | None = None,
    ) -> dict[str, Any]:
        rgba = self.load_frame_rgba(project_id, frame_index, version_id)
        info = inspect_pixel_at(rgba, x, y)
        info["frame_index"] = int(frame_index)
        info["version_id"] = version_id or self.load_project(project_id)["current_version_id"]
        return info

    def create_version_from_edited_frame(
        self,
        project_id: str,
        *,
        base_version_id: str,
        frame_index: int,
        edited_rgba: np.ndarray,
        summary: str,
        job_id: str | None = None,
        locality_qa: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new immutable version snapshot with one edited frame."""
        proj = self.load_project(project_id)
        self.verify_original_unchanged(project_id, project_data=proj)
        base_vdoc = self.get_version_doc(project_id, base_version_id)

        next_num = len(proj["versions"]) + 1
        new_version_id = f"v{next_num:04d}"
        pdir = self.project_dir(project_id)
        vdir = pdir / "versions" / new_version_id
        frames_dir = vdir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        new_frame_records: list[dict[str, Any]] = []
        for record in base_vdoc["frames"]:
            idx = int(record["index"])
            fname = f"frame_{idx:04d}.png"
            dst_path = frames_dir / fname
            if idx == frame_index:
                arr = np.asarray(edited_rgba, dtype=np.uint8).copy()
                arr[arr[..., 3] == 0] = 0
                self.forge.save_png_canonical(arr, dst_path)
                geom = self.forge.compute_subject_bbox_and_anchor(arr, anchor_mode="feet")
                rgba_sha = self.forge.sha256_bytes(arr.tobytes())
                png_sha = self.forge.sha256_file(dst_path)
                new_frame_records.append(
                    {
                        "index": idx,
                        "file": f"versions/{new_version_id}/frames/{fname}",
                        "duration_ms": record["duration_ms"],
                        "rgba_pixel_sha256": rgba_sha,
                        "png_file_sha256": png_sha,
                        "bbox": geom["bbox"],
                        "anchor_px": geom["anchor_px"],
                        "opaque_pixels": geom["opaque_pixels"],
                    }
                )
            else:
                src_path = pdir / record["file"]
                shutil.copy2(src_path, dst_path)
                copied_record = dict(record)
                copied_record["file"] = f"versions/{new_version_id}/frames/{fname}"
                new_frame_records.append(copied_record)

        timestamp = _utc_now()
        new_vdoc = {
            "version_id": new_version_id,
            "parent_version_id": base_version_id,
            "created_at": timestamp,
            "kind": "region_edit",
            "summary": summary,
            "edited_frame_index": int(frame_index),
            "job_id": job_id,
            "locality_qa": locality_qa,
            "frames": new_frame_records,
            "original_sha256": proj["original_file"]["sha256"],
        }
        self._write_json_atomic(vdir / "version.json", new_vdoc)

        proj["versions"].append(new_vdoc)
        proj["current_version_id"] = new_version_id
        self.save_project(project_id, proj)
        self.verify_original_unchanged(project_id)
        return new_vdoc

    def rollback_to_version(
        self,
        project_id: str,
        target_version_id: str,
        *,
        reason: str = "User requested rollback",
    ) -> dict[str, Any]:
        """Roll back the active project state to target_version_id non-destructively."""
        proj = self.load_project(project_id)
        self.verify_original_unchanged(project_id, project_data=proj)
        target_vdoc = self.get_version_doc(project_id, target_version_id)
        previous_version_id = proj["current_version_id"]

        rollback_entry = {
            "rollback_id": f"rb-{uuid.uuid4().hex[:8]}",
            "timestamp": _utc_now(),
            "from_version_id": previous_version_id,
            "to_version_id": target_version_id,
            "reason": reason,
            "original_sha256_verified": proj["original_file"]["sha256"],
        }
        proj.setdefault("rollback_history", []).append(rollback_entry)
        proj["current_version_id"] = target_vdoc["version_id"]
        updated = self.save_project(project_id, proj)
        self.verify_original_unchanged(project_id, project_data=updated)
        return {
            "status": "rolled_back",
            "project_id": project_id,
            "previous_version_id": previous_version_id,
            "current_version_id": updated["current_version_id"],
            "rollback_entry": rollback_entry,
            "original_integrity": updated["original_integrity"],
        }

    def update_timeline_settings(
        self,
        project_id: str,
        *,
        fps: float | None = None,
        frame_durations_ms: list[int] | None = None,
        loop: bool | None = None,
        default_clip: str | None = None,
    ) -> dict[str, Any]:
        """Update playback FPS, per-frame durations, or loop settings on the current project."""
        proj = self.load_project(project_id)
        current_vid = proj["current_version_id"]
        vdoc = self.get_version_doc(project_id, current_vid)

        if frame_durations_ms is not None:
            if len(frame_durations_ms) != len(vdoc["frames"]):
                raise ValueError(
                    f"frame_durations_ms length {len(frame_durations_ms)} != frame_count {len(vdoc['frames'])}"
                )
            for rec, dur in zip(vdoc["frames"], frame_durations_ms):
                rec["duration_ms"] = max(10, int(dur))
            total_ms = sum(r["duration_ms"] for r in vdoc["frames"])
            proj["total_duration_ms"] = total_ms
            proj["fps"] = round((len(vdoc["frames"]) * 1000.0) / total_ms, 2)
        elif fps is not None:
            if fps <= 0 or fps > 120:
                raise ValueError("fps must be in (0, 120]")
            dur_ms = max(10, int(round(1000.0 / float(fps))))
            for rec in vdoc["frames"]:
                rec["duration_ms"] = dur_ms
            proj["total_duration_ms"] = dur_ms * len(vdoc["frames"])
            proj["fps"] = round(float(fps), 2)

        if loop is not None:
            proj["loop"] = bool(loop)
        if default_clip is not None and default_clip.strip():
            proj["default_clip"] = default_clip.strip()

        # Persist updated version.json and project.json
        vdir = self.project_dir(project_id) / "versions" / current_vid
        self._write_json_atomic(vdir / "version.json", vdoc)
        return self.save_project(project_id, proj)


_DEFAULT_STORE: ProjectStore | None = None


def get_project_store(workspace_dir: str | Path | None = None) -> ProjectStore:
    global _DEFAULT_STORE
    if workspace_dir is not None:
        return ProjectStore(workspace_dir=workspace_dir)
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = ProjectStore()
    return _DEFAULT_STORE
