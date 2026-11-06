"""Strict pixel-preservation and edit-locality QA gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from packages.character_core.coords import validate_selection_box


def enforce_region_mask(
    before_rgba: np.ndarray,
    candidate_rgba: np.ndarray,
    selection_box: dict[str, int],
) -> np.ndarray:
    """Composite candidate_rgba strictly inside selection_box over before_rgba."""
    before = np.asarray(before_rgba, dtype=np.uint8)
    candidate = np.asarray(candidate_rgba, dtype=np.uint8)
    if before.shape != candidate.shape:
        raise ValueError(f"Frame shape mismatch: before {before.shape} vs candidate {candidate.shape}")
    h, w = before.shape[:2]
    box = validate_selection_box(selection_box, w, h)
    x0, y0, bw, bh = box["x"], box["y"], box["w"], box["h"]
    result = before.copy()
    result[y0 : y0 + bh, x0 : x0 + bw] = candidate[y0 : y0 + bh, x0 : x0 + bw]
    result[result[..., 3] == 0] = 0
    return result


def verify_edit_locality(
    before_rgba: np.ndarray,
    after_rgba: np.ndarray,
    selection_box: dict[str, int],
    *,
    diff_image_path: Path | None = None,
) -> dict[str, Any]:
    """Verify that zero pixels outside selection_box changed between before_rgba and after_rgba."""
    before = np.asarray(before_rgba, dtype=np.uint8)
    after = np.asarray(after_rgba, dtype=np.uint8)
    if before.shape != after.shape:
        return {
            "schema": "character-forge.locality_qa.v1",
            "status": "fail",
            "reason": f"Dimensions changed from {before.shape} to {after.shape}",
        }

    h, w = before.shape[:2]
    box = validate_selection_box(selection_box, w, h)
    x0, y0, bw, bh = box["x"], box["y"], box["w"], box["h"]

    mask = np.zeros((h, w), dtype=bool)
    mask[y0 : y0 + bh, x0 : x0 + bw] = True

    abs_diff = np.abs(after.astype(np.int16) - before.astype(np.int16))
    pixel_changed = np.any(abs_diff > 0, axis=-1)

    outside_changed_mask = pixel_changed & (~mask)
    inside_changed_mask = pixel_changed & mask

    outside_changed_pixels = int(np.count_nonzero(outside_changed_mask))
    inside_changed_pixels = int(np.count_nonzero(inside_changed_mask))
    inside_total_pixels = int(bw * bh)
    outside_total_pixels = int(h * w - inside_total_pixels)

    outside_max_diff = int(abs_diff[~mask].max()) if outside_total_pixels > 0 else 0
    inside_mae = round(float(abs_diff[mask].mean()), 4) if inside_total_pixels > 0 else 0.0

    passed = outside_changed_pixels == 0 and outside_max_diff == 0

    if diff_image_path is not None:
        diff_image_path.parent.mkdir(parents=True, exist_ok=True)
        vis = (after.astype(np.float32) * 0.45).astype(np.uint8)
        vis[..., 3] = np.maximum(after[..., 3], 128)
        vis[inside_changed_mask] = [46, 204, 113, 255]  # green for valid inside edits
        vis[outside_changed_mask] = [231, 76, 60, 255]  # red for illegal outside mutations
        img = Image.fromarray(vis, mode="RGBA")
        draw = ImageDraw.Draw(img)
        draw.rectangle([x0, y0, x0 + bw - 1, y0 + bh - 1], outline=(52, 152, 219, 255), width=1)
        img.save(diff_image_path, format="PNG")

    return {
        "schema": "character-forge.locality_qa.v1",
        "status": "pass" if passed else "fail",
        "selection_box": box,
        "image_size": [w, h],
        "outside_changed_pixels": outside_changed_pixels,
        "outside_total_pixels": outside_total_pixels,
        "outside_max_channel_diff": outside_max_diff,
        "inside_changed_pixels": inside_changed_pixels,
        "inside_total_pixels": inside_total_pixels,
        "inside_changed_fraction": round(inside_changed_pixels / max(1, inside_total_pixels), 4),
        "inside_mae": inside_mae,
        "diff_image": str(diff_image_path) if diff_image_path else None,
    }
