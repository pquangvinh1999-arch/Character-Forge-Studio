"""Structured selection edit jobs and non-destructive region-only pixel transformations."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

from packages.character_core.coords import validate_selection_box
from packages.forge_adapter import get_forge_adapter
from packages.project_store import ProjectStore
from packages.qa_gate.locality import enforce_region_mask, verify_edit_locality

HEX_COLOR_RE = re.compile(r"#?([0-9a-fA-F]{6})\b")

NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "red": (231, 76, 60),
    "đỏ": (231, 76, 60),
    "blue": (52, 152, 219),
    "xanh dương": (52, 152, 219),
    "green": (46, 204, 113),
    "xanh lá": (46, 204, 113),
    "gold": (241, 196, 15),
    "yellow": (241, 196, 15),
    "vàng": (241, 196, 15),
    "purple": (155, 89, 182),
    "tím": (155, 89, 182),
    "cyan": (26, 188, 156),
    "orange": (230, 126, 34),
    "cam": (230, 126, 34),
    "white": (245, 247, 250),
    "trắng": (245, 247, 250),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _parse_color(color_hex: str | None, instruction: str) -> tuple[int, int, int]:
    if color_hex:
        match = HEX_COLOR_RE.search(color_hex)
        if match:
            h = match.group(1)
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    lower = instruction.lower()
    for name, rgb in NAMED_COLORS.items():
        if name in lower:
            return rgb
    match = HEX_COLOR_RE.search(instruction)
    if match:
        h = match.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (52, 152, 219)  # default studio accent blue


def apply_region_pixel_operation(
    before_rgba: np.ndarray,
    selection_box: dict[str, int],
    *,
    operation: str,
    instruction: str,
    color_hex: str | None = None,
) -> tuple[np.ndarray, str]:
    """Apply a deterministic, non-destructive pixel operation strictly inside selection_box.

    Supported operations:
    - 'auto': infers operation from natural-language instruction (tint/recolor/invert/brighten/darken/outline/erase)
    - 'tint': blends opaque pixels inside selection_box toward target RGB colour
    - 'recolor': replaces opaque pixels inside selection_box with shaded target RGB colour
    - 'invert': inverts RGB channels of opaque pixels inside selection_box
    - 'brighten': increases luminance of opaque pixels inside selection_box
    - 'darken': decreases luminance of opaque pixels inside selection_box
    - 'outline_box': draws a 1px pixel-art highlight border inside selection_box
    - 'erase': clears pixels inside selection_box to transparent (0, 0, 0, 0)
    """
    before = np.asarray(before_rgba, dtype=np.uint8)
    h, w = before.shape[:2]
    box = validate_selection_box(selection_box, w, h)
    x0, y0, bw, bh = box["x"], box["y"], box["w"], box["h"]

    op = (operation or "auto").lower().strip()
    lower_inst = instruction.lower()
    if op == "auto":
        if any(k in lower_inst for k in ("erase", "clear", "delete", "xóa", "trong suốt")):
            op = "erase"
        elif any(k in lower_inst for k in ("invert", "negative", "đảo màu")):
            op = "invert"
        elif any(k in lower_inst for k in ("bright", "glow", "sáng")):
            op = "brighten"
        elif any(k in lower_inst for k in ("dark", "shadow", "tối")):
            op = "darken"
        elif any(k in lower_inst for k in ("outline", "border", "viền")):
            op = "outline_box"
        elif any(k in lower_inst for k in ("recolor", "replace", "đổi màu")):
            op = "recolor"
        else:
            op = "tint"

    candidate = before.copy()
    patch = candidate[y0 : y0 + bh, x0 : x0 + bw].copy()
    opaque = patch[..., 3] > 0
    tr, tg, tb = _parse_color(color_hex, instruction)

    if op == "erase":
        patch[:, :] = 0
        op_desc = f"Cleared selection ({x0},{y0},{bw},{bh}) to transparent RGBA(0,0,0,0)"
    elif op == "invert":
        if np.any(opaque):
            patch[opaque, :3] = 255 - patch[opaque, :3]
        else:
            patch[..., :3] = 255 - patch[..., :3]
            patch[..., 3] = 255
        op_desc = f"Inverted RGB pixels inside selection ({x0},{y0},{bw},{bh})"
    elif op == "brighten":
        if np.any(opaque):
            patch[opaque, :3] = np.clip(patch[opaque, :3].astype(np.int16) + 45, 0, 255).astype(np.uint8)
        else:
            patch[..., :3] = np.array([tr, tg, tb], dtype=np.uint8)
            patch[..., 3] = 255
        op_desc = f"Brightened pixels (+45 luminance) inside selection ({x0},{y0},{bw},{bh})"
    elif op == "darken":
        if np.any(opaque):
            patch[opaque, :3] = np.clip(patch[opaque, :3].astype(np.int16) - 45, 0, 255).astype(np.uint8)
        else:
            patch[..., :3] = np.array([tr // 2, tg // 2, tb // 2], dtype=np.uint8)
            patch[..., 3] = 255
        op_desc = f"Darkened pixels (-45 luminance) inside selection ({x0},{y0},{bw},{bh})"
    elif op == "outline_box":
        border = np.zeros((bh, bw), dtype=bool)
        border[0, :] = True
        border[-1, :] = True
        border[:, 0] = True
        border[:, -1] = True
        patch[border] = np.array([tr, tg, tb, 255], dtype=np.uint8)
        op_desc = f"Applied 1px pixel-art border #{tr:02x}{tg:02x}{tb:02x} inside selection ({x0},{y0},{bw},{bh})"
    elif op == "recolor":
        if np.any(opaque):
            lum = (
                0.299 * patch[opaque, 0].astype(np.float32)
                + 0.587 * patch[opaque, 1].astype(np.float32)
                + 0.114 * patch[opaque, 2].astype(np.float32)
            ) / 255.0
            scale = np.clip(0.45 + 0.75 * lum, 0.25, 1.25)[:, None]
            target_rgb = np.array([tr, tg, tb], dtype=np.float32)[None, :]
            patch[opaque, :3] = np.clip(np.round(target_rgb * scale), 0, 255).astype(np.uint8)
        else:
            patch[:, :] = np.array([tr, tg, tb, 255], dtype=np.uint8)
        op_desc = f"Recolored selection ({x0},{y0},{bw},{bh}) to #{tr:02x}{tg:02x}{tb:02x}"
    else:
        # 'tint' (default): 55% blend toward target RGB on opaque pixels, or fill if patch is fully transparent
        if np.any(opaque):
            target = np.array([tr, tg, tb], dtype=np.float32)
            orig_rgb = patch[opaque, :3].astype(np.float32)
            blended = np.clip(np.round(orig_rgb * 0.45 + target * 0.55), 0, 255).astype(np.uint8)
            # Ensure at least 1 level change so locality diff is measurable
            same = np.all(blended == patch[opaque, :3], axis=-1)
            if np.any(same):
                blended[same, 0] = np.where(blended[same, 0] < 255, blended[same, 0] + 1, blended[same, 0] - 1)
            patch[opaque, :3] = blended
        else:
            patch[:, :] = np.array([tr, tg, tb, 255], dtype=np.uint8)
        op_desc = f"Tinted selection ({x0},{y0},{bw},{bh}) toward #{tr:02x}{tg:02x}{tb:02x}"

    candidate[y0 : y0 + bh, x0 : x0 + bw] = patch
    final_rgba = enforce_region_mask(before, candidate, box)
    return final_rgba, op_desc


class EditJobManager:
    """Create, store, inspect, and execute structured selection edit jobs."""

    def __init__(
        self,
        store: ProjectStore,
        event_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.store = store
        self.forge = get_forge_adapter()
        self.event_callback = event_callback

    def _emit(self, project_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "timestamp": _utc_now(),
            "type": event_type,
            **payload,
        }
        if self.event_callback is not None:
            self.event_callback(project_id, entry)
        return entry

    def _jobs_dir(self, project_id: str) -> Path:
        jdir = self.store.project_dir(project_id) / "jobs"
        jdir.mkdir(parents=True, exist_ok=True)
        return jdir

    def create_and_run_edit_job(
        self,
        project_id: str,
        *,
        frame_index: int,
        selection_box: dict[str, int],
        instruction: str,
        operation: str = "auto",
        color_hex: str | None = None,
        apply_immediately: bool = True,
    ) -> dict[str, Any]:
        """Save a structured selection edit job JSON and optionally execute a region-confined edit."""
        if not instruction or not instruction.strip():
            raise ValueError("Edit instruction cannot be empty.")

        proj = self.store.load_project(project_id)
        base_version_id = proj["current_version_id"]
        before_rgba = self.store.load_frame_rgba(project_id, frame_index, base_version_id)
        h, w = before_rgba.shape[:2]
        valid_box = validate_selection_box(selection_box, w, h)
        x0, y0, bw, bh = valid_box["x"], valid_box["y"], valid_box["w"], valid_box["h"]

        job_id = f"job-{uuid.uuid4().hex[:10]}"
        jdir = self._jobs_dir(project_id)
        job_json_path = jdir / f"{job_id}.json"
        patch_before_path = jdir / f"{job_id}_patch_before.png"

        # Save cropped selection patch for agent inspection
        patch_before = before_rgba[y0 : y0 + bh, x0 : x0 + bw].copy()
        self.forge.save_png_canonical(patch_before, patch_before_path)

        events: list[dict[str, Any]] = []
        ev_created = self._emit(
            project_id,
            "job.created",
            {
                "job_id": job_id,
                "status": "queued",
                "frame_index": int(frame_index),
                "selection_box": valid_box,
                "instruction": instruction.strip(),
            },
        )
        events.append(ev_created)

        job_doc: dict[str, Any] = {
            "schema": "character-forge.edit_job.v1",
            "job_id": job_id,
            "project_id": project_id,
            "created_at": ev_created["timestamp"],
            "updated_at": ev_created["timestamp"],
            "base_version_id": base_version_id,
            "produced_version_id": None,
            "frame_index": int(frame_index),
            "image_size": [w, h],
            "selection_box": valid_box,
            "normalized_uv_box": [
                round(x0 / w, 6),
                round(y0 / h, 6),
                round((x0 + bw) / w, 6),
                round((y0 + bh) / h, 6),
            ],
            "instruction": instruction.strip(),
            "operation": operation,
            "color_hex": color_hex,
            "status": "queued",
            "artifacts": {
                "patch_before": f"jobs/{patch_before_path.name}",
                "patch_after": None,
                "locality_diff": None,
            },
            "constraints": {
                "preserve_outside_selection": True,
                "original_asset_read_only": True,
                "paid_api_calls": False,
            },
            "locality_qa": None,
            "events": events,
        }
        job_json_path.write_text(json.dumps(job_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        if not apply_immediately or operation == "record_only":
            job_doc["status"] = "awaiting_agent"
            ev_wait = self._emit(
                project_id,
                "job.awaiting_agent",
                {
                    "job_id": job_id,
                    "status": "awaiting_agent",
                    "message": "Structured selection job saved to disk and ready for agent execution.",
                },
            )
            job_doc["events"].append(ev_wait)
            job_doc["updated_at"] = ev_wait["timestamp"]
            job_json_path.write_text(json.dumps(job_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self._append_job_to_project(project_id, job_doc)
            return job_doc

        # Step 1: Running region edit
        ev_run = self._emit(
            project_id,
            "job.progress",
            {
                "job_id": job_id,
                "status": "running",
                "step": "apply_region_operation",
                "message": f"Applying region edit on frame {frame_index} within box ({x0}, {y0}, {bw}, {bh})",
            },
        )
        job_doc["status"] = "running"
        job_doc["events"].append(ev_run)

        edited_rgba, op_summary = apply_region_pixel_operation(
            before_rgba,
            valid_box,
            operation=operation,
            instruction=instruction,
            color_hex=color_hex,
        )

        patch_after_path = jdir / f"{job_id}_patch_after.png"
        self.forge.save_png_canonical(edited_rgba[y0 : y0 + bh, x0 : x0 + bw], patch_after_path)
        diff_path = jdir / f"{job_id}_locality_diff.png"

        # Step 2: Locality QA check
        locality_qa = verify_edit_locality(
            before_rgba,
            edited_rgba,
            valid_box,
            diff_image_path=diff_path,
        )
        ev_qa = self._emit(
            project_id,
            "job.locality_qa",
            {
                "job_id": job_id,
                "status": locality_qa["status"],
                "outside_changed_pixels": locality_qa["outside_changed_pixels"],
                "inside_changed_pixels": locality_qa["inside_changed_pixels"],
            },
        )
        job_doc["events"].append(ev_qa)

        if locality_qa["status"] != "pass":
            job_doc["status"] = "failed"
            job_doc["locality_qa"] = locality_qa
            job_json_path.write_text(json.dumps(job_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            raise RuntimeError(f"Edit locality check failed for job {job_id}: {locality_qa}")

        # Step 3: Commit new version snapshot in ProjectStore
        new_version = self.store.create_version_from_edited_frame(
            project_id,
            base_version_id=base_version_id,
            frame_index=frame_index,
            edited_rgba=edited_rgba,
            summary=f"{instruction.strip()} [{op_summary}]",
            job_id=job_id,
            locality_qa=locality_qa,
        )

        job_doc["status"] = "completed"
        job_doc["produced_version_id"] = new_version["version_id"]
        job_doc["operation_summary"] = op_summary
        job_doc["artifacts"]["patch_after"] = f"jobs/{patch_after_path.name}"
        job_doc["artifacts"]["locality_diff"] = f"jobs/{diff_path.name}"
        job_doc["locality_qa"] = locality_qa

        ev_done = self._emit(
            project_id,
            "job.completed",
            {
                "job_id": job_id,
                "status": "completed",
                "produced_version_id": new_version["version_id"],
                "summary": new_version["summary"],
                "outside_changed_pixels": locality_qa["outside_changed_pixels"],
                "inside_changed_pixels": locality_qa["inside_changed_pixels"],
            },
        )
        job_doc["events"].append(ev_done)
        job_doc["updated_at"] = ev_done["timestamp"]
        job_json_path.write_text(json.dumps(job_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._append_job_to_project(project_id, job_doc)
        return job_doc

    def _append_job_to_project(self, project_id: str, job_doc: dict[str, Any]) -> None:
        proj = self.store.load_project(project_id)
        jobs = proj.setdefault("jobs", [])
        jobs = [j for j in jobs if j.get("job_id") != job_doc["job_id"]]
        jobs.append(
            {
                "job_id": job_doc["job_id"],
                "created_at": job_doc["created_at"],
                "status": job_doc["status"],
                "frame_index": job_doc["frame_index"],
                "selection_box": job_doc["selection_box"],
                "instruction": job_doc["instruction"],
                "base_version_id": job_doc["base_version_id"],
                "produced_version_id": job_doc["produced_version_id"],
            }
        )
        proj["jobs"] = jobs
        self.store.save_project(project_id, proj)

    def get_job(self, project_id: str, job_id: str) -> dict[str, Any]:
        clean = "".join(c for c in job_id if c.isalnum() or c in "-_")
        jpath = self._jobs_dir(project_id) / f"{clean}.json"
        if not jpath.is_file():
            raise FileNotFoundError(f"Job {job_id!r} not found in project {project_id}")
        return json.loads(jpath.read_text(encoding="utf-8"))

    def list_jobs(self, project_id: str) -> list[dict[str, Any]]:
        jdir = self._jobs_dir(project_id)
        results: list[dict[str, Any]] = []
        for fpath in sorted(jdir.glob("job-*.json")):
            try:
                results.append(json.loads(fpath.read_text(encoding="utf-8")))
            except Exception:
                continue
        return sorted(results, key=lambda item: item.get("created_at", ""), reverse=True)
