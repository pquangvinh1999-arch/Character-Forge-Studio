"""Extract individual RGBA frames, timings, and metadata from uploaded PNG and GIF files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageSequence

from packages.forge_adapter import get_forge_adapter
from packages.sprite_gen_adapter import get_sprite_gen_adapter

DEFAULT_FRAME_DURATION_MS = 100


@dataclass
class ExtractedFrame:
    index: int
    duration_ms: int
    pixels: np.ndarray  # H x W x 4 uint8 canonical straight-alpha RGBA
    sha256: str
    bbox: list[int]
    anchor_px: list[float]
    opaque_pixels: int


@dataclass
class ExtractedAsset:
    source_format: str  # "GIF" or "PNG"
    width: int
    height: int
    frame_count: int
    total_duration_ms: int
    average_fps: float
    anchor_px: list[float]
    pixel_pitch_estimate: int
    dominant_palette: list[dict[str, Any]]
    motion_summary: dict[str, Any]
    frames: list[ExtractedFrame]


def _canonicalize_rgba(image: Image.Image) -> np.ndarray:
    rgba = image.convert("RGBA")
    arr = np.asarray(rgba, dtype=np.uint8).copy()
    arr[arr[..., 3] == 0] = 0
    return arr


def extract_frames_from_file(path: str | Path) -> ExtractedAsset:
    """Read a PNG or GIF file without modifying it and extract all RGBA frames and timings."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Asset file not found: {file_path}")

    forge = get_forge_adapter()
    sprite_gen = get_sprite_gen_adapter()

    frames: list[ExtractedFrame] = []
    raw_arrays: list[np.ndarray] = []

    with Image.open(file_path) as img:
        fmt = (img.format or file_path.suffix.lstrip(".")).upper()
        if fmt not in ("PNG", "GIF"):
            raise ValueError(f"Unsupported image format {fmt!r}; only PNG and GIF are supported.")

        width, height = img.size
        for index, frame_img in enumerate(ImageSequence.Iterator(img)):
            raw_duration = frame_img.info.get("duration", img.info.get("duration", DEFAULT_FRAME_DURATION_MS))
            try:
                duration_ms = int(round(float(raw_duration)))
            except (TypeError, ValueError):
                duration_ms = DEFAULT_FRAME_DURATION_MS
            if duration_ms <= 0:
                duration_ms = DEFAULT_FRAME_DURATION_MS

            pixels = _canonicalize_rgba(frame_img)
            if pixels.shape[1] != width or pixels.shape[0] != height:
                # Normalize frame canvas if a GIF frame had partial bounds
                canvas = np.zeros((height, width, 4), dtype=np.uint8)
                h_f, w_f = pixels.shape[:2]
                canvas[: min(height, h_f), : min(width, w_f)] = pixels[: min(height, h_f), : min(width, w_f)]
                pixels = canvas

            geom = forge.compute_subject_bbox_and_anchor(pixels, anchor_mode="feet")
            frame_sha = forge.sha256_bytes(pixels.tobytes())
            frames.append(
                ExtractedFrame(
                    index=index,
                    duration_ms=duration_ms,
                    pixels=pixels,
                    sha256=frame_sha,
                    bbox=geom["bbox"],
                    anchor_px=geom["anchor_px"],
                    opaque_pixels=geom["opaque_pixels"],
                )
            )
            raw_arrays.append(pixels)

    total_ms = sum(f.duration_ms for f in frames)
    avg_fps = round((len(frames) * 1000.0) / total_ms, 2) if total_ms > 0 else 10.0

    # Shared character anchor across frames: median horizontal anchor, lowest feet y
    if frames:
        shared_ax = round(float(np.median([f.anchor_px[0] for f in frames])), 2)
        shared_ay = round(float(max(f.anchor_px[1] for f in frames)), 2)
        shared_anchor = [shared_ax, shared_ay]
        pitch = sprite_gen.estimate_pixel_pitch(frames[0].pixels)
        palette = sprite_gen.extract_dominant_palette(frames[0].pixels, max_colors=16)
    else:
        shared_anchor = [round(width / 2.0, 2), float(height)]
        pitch = 1
        palette = []

    motion_summary = sprite_gen.compute_motion_summary(raw_arrays)

    return ExtractedAsset(
        source_format=fmt,
        width=width,
        height=height,
        frame_count=len(frames),
        total_duration_ms=total_ms,
        average_fps=avg_fps,
        anchor_px=shared_anchor,
        pixel_pitch_estimate=pitch,
        dominant_palette=palette,
        motion_summary=motion_summary,
        frames=frames,
    )
