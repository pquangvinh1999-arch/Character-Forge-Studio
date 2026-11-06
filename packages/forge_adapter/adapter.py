"""Clean adapter boundary over pinned vendor/agent-sprite-forge.

Never modifies or overwrites vendor files. Dynamically loads canonical modules
from vendor/agent-sprite-forge/shared and skills/generate2dsprite/scripts.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_FORGE_ROOT = REPO_ROOT / "vendor" / "agent-sprite-forge"
FORGE_SHARED_DIR = VENDOR_FORGE_ROOT / "shared"
FORGE_SPRITE_SCRIPTS_DIR = VENDOR_FORGE_ROOT / "skills" / "generate2dsprite" / "scripts"


def _load_vendor_module(module_name: str, file_path: Path) -> Any:
    if not file_path.is_file():
        raise FileNotFoundError(f"Missing pinned vendor module: {file_path}")
    parent = str(file_path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create module spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class AgentSpriteForgeAdapter:
    """Adapter wrapping Agent Sprite Forge core RGBA utilities and engine exporter."""

    def __init__(self, vendor_root: Path | None = None) -> None:
        self.vendor_root = vendor_root or VENDOR_FORGE_ROOT
        self.shared_dir = self.vendor_root / "shared"
        self.sprite_scripts_dir = self.vendor_root / "skills" / "generate2dsprite" / "scripts"
        self._forge_core: Any = None
        self._export_engine: Any = None

    @property
    def forge_core(self) -> Any:
        if self._forge_core is None:
            self._forge_core = _load_vendor_module(
                "_vendor_forge_core",
                self.shared_dir / "forge_core.py",
            )
        return self._forge_core

    @property
    def export_engine(self) -> Any:
        if self._export_engine is None:
            # Ensure forge_core is loaded in sys.modules as 'forge_core' for export_engine.py
            fc = self.forge_core
            sys.modules.setdefault("forge_core", fc)
            self._export_engine = _load_vendor_module(
                "_vendor_forge_export_engine",
                self.sprite_scripts_dir / "export_engine.py",
            )
        return self._export_engine

    def sha256_file(self, path: str | Path) -> str:
        return str(self.forge_core.sha256_file(Path(path)))

    def sha256_bytes(self, data: bytes) -> str:
        return str(self.forge_core.sha256_bytes(data))

    def load_rgba_canonical(self, path: str | Path) -> np.ndarray:
        """Load an image as canonical straight-alpha RGBA (RGB zeroed where alpha == 0)."""
        img, _info = self.forge_core.load_rgba(Path(path))
        arr = np.asarray(img, dtype=np.uint8).copy()
        arr[arr[..., 3] == 0] = 0
        return arr

    def save_png_canonical(self, pixels: np.ndarray, path: str | Path) -> None:
        """Save canonical straight-alpha RGBA array to PNG via forge_core."""
        arr = np.asarray(pixels, dtype=np.uint8).copy()
        arr[arr[..., 3] == 0] = 0
        self.forge_core.save_png(arr, Path(path))

    def compute_subject_bbox_and_anchor(
        self,
        pixels: np.ndarray,
        anchor_mode: str = "feet",
    ) -> dict[str, Any]:
        """Compute opaque subject bounding box [x0, y0, x1, y1] and anchor [ax, ay] in source pixels."""
        arr = np.asarray(pixels, dtype=np.uint8)
        h, w = arr.shape[:2]
        alpha = arr[..., 3]
        mask = alpha > self.forge_core.ALPHA_GEOMETRY_THRESHOLD
        if not np.any(mask):
            mask = alpha > 0
        if not np.any(mask):
            return {
                "has_subject": False,
                "bbox": [0, 0, w, h],
                "anchor_px": [round(w / 2.0, 2), float(h)],
                "opaque_pixels": 0,
            }
        ys, xs = np.nonzero(mask)
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        if anchor_mode == "center":
            ax = (x0 + x1) / 2.0
            ay = (y0 + y1) / 2.0
        elif anchor_mode == "centroid":
            weights = alpha[mask].astype(np.float64)
            ax = float(np.sum(xs * weights) / np.sum(weights)) + 0.5
            ay = float(np.sum(ys * weights) / np.sum(weights)) + 0.5
        else:
            # 'feet' anchor: horizontal center of subject, bottom-most visible row y1
            bottom_band = mask[max(y0, y1 - max(1, (y1 - y0) // 6)) : y1, :]
            if np.any(bottom_band):
                _, bx = np.nonzero(bottom_band)
                ax = float(bx.min() + bx.max() + 1) / 2.0
            else:
                ax = (x0 + x1) / 2.0
            ay = float(y1)
        return {
            "has_subject": True,
            "bbox": [x0, y0, x1, y1],
            "anchor_px": [round(ax, 2), round(ay, 2)],
            "opaque_pixels": int(np.count_nonzero(mask)),
        }

    def export_clips_to_engine(
        self,
        clips_manifest_path: Path,
        output_dir: Path,
        name: str,
        target: str = "godot-spriteframes",
        sampling: str = "nearest",
    ) -> dict[str, Any]:
        """Run agent-sprite-forge export_engine.py with full round-trip verification."""
        parser = self.export_engine.build_parser()
        args = parser.parse_args(
            [
                "--clips",
                str(clips_manifest_path),
                "--target",
                target,
                "--output-dir",
                str(output_dir),
                "--name",
                name,
                "--sampling",
                sampling,
            ]
        )
        return dict(self.export_engine.export(args))


_DEFAULT_ADAPTER: AgentSpriteForgeAdapter | None = None


def get_forge_adapter() -> AgentSpriteForgeAdapter:
    global _DEFAULT_ADAPTER
    if _DEFAULT_ADAPTER is None:
        _DEFAULT_ADAPTER = AgentSpriteForgeAdapter()
    return _DEFAULT_ADAPTER
