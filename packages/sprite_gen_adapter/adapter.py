"""Clean adapter boundary over pinned vendor/sprite-gen.

Provides selected frame-processing, palette analysis, pitch estimation, and curation
capabilities from vendor/sprite-gen without modifying vendor files or enabling
unapproved paid AI API calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_SPRITE_GEN_ROOT = REPO_ROOT / "vendor" / "sprite-gen"


class SpriteGenAdapter:
    """Adapter exposing selected non-networked capabilities from aldegad/sprite-gen."""

    def __init__(self, vendor_root: Path | None = None) -> None:
        self.vendor_root = vendor_root or VENDOR_SPRITE_GEN_ROOT
        if str(self.vendor_root) not in sys.path:
            sys.path.insert(0, str(self.vendor_root))

    def estimate_pixel_pitch(self, rgba_pixels: np.ndarray) -> int:
        """Estimate logical pixel block pitch using sprite-gen's run-length mode estimator."""
        try:
            from sprite_gen.frames.extract import estimate_pixel_grid_runlen

            img = Image.fromarray(np.asarray(rgba_pixels, dtype=np.uint8), mode="RGBA")
            pitch = estimate_pixel_grid_runlen(img)
            return max(1, int(pitch)) if pitch else 1
        except Exception:
            return 1

    def extract_dominant_palette(self, rgba_pixels: np.ndarray, max_colors: int = 16) -> list[dict[str, Any]]:
        """Extract dominant opaque RGBA colours sorted by pixel frequency."""
        arr = np.asarray(rgba_pixels, dtype=np.uint8)
        opaque = arr[arr[..., 3] > 0]
        if opaque.size == 0:
            return []
        rgb = opaque[:, :3]
        unique_colors, counts = np.unique(rgb, axis=0, return_counts=True)
        order = np.argsort(-counts)[:max_colors]
        total = int(opaque.shape[0])
        palette = []
        for idx in order:
            r, g, b = (int(v) for v in unique_colors[idx])
            count = int(counts[idx])
            palette.append(
                {
                    "hex": f"#{r:02x}{g:02x}{b:02x}",
                    "rgb": [r, g, b],
                    "pixels": count,
                    "fraction": round(count / total, 4),
                }
            )
        return palette

    def compute_motion_summary(self, frames_rgba: list[np.ndarray]) -> dict[str, Any]:
        """Compute frame-to-frame pixel delta metrics across an extracted animation sequence."""
        if len(frames_rgba) <= 1:
            return {
                "frame_count": len(frames_rgba),
                "mean_frame_delta_fraction": 0.0,
                "loop_seam_delta_fraction": 0.0,
                "is_animated": False,
            }
        deltas: list[float] = []
        for i in range(len(frames_rgba) - 1):
            a = frames_rgba[i].astype(np.int16)
            b = frames_rgba[i + 1].astype(np.int16)
            changed = np.any(np.abs(a - b) > 0, axis=-1)
            deltas.append(float(np.mean(changed)))
        first = frames_rgba[0].astype(np.int16)
        last = frames_rgba[-1].astype(np.int16)
        seam_changed = float(np.mean(np.any(np.abs(first - last) > 0, axis=-1)))
        mean_delta = float(np.mean(deltas)) if deltas else 0.0
        return {
            "frame_count": len(frames_rgba),
            "mean_frame_delta_fraction": round(mean_delta, 5),
            "loop_seam_delta_fraction": round(seam_changed, 5),
            "step_deltas": [round(d, 5) for d in deltas],
            "is_animated": mean_delta > 0.0,
        }


_DEFAULT_SPRITE_GEN_ADAPTER: SpriteGenAdapter | None = None


def get_sprite_gen_adapter() -> SpriteGenAdapter:
    global _DEFAULT_SPRITE_GEN_ADAPTER
    if _DEFAULT_SPRITE_GEN_ADAPTER is None:
        _DEFAULT_SPRITE_GEN_ADAPTER = SpriteGenAdapter()
    return _DEFAULT_SPRITE_GEN_ADAPTER
