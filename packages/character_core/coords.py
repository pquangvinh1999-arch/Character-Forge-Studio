"""Zoom-invariant canvas-to-source pixel coordinate mapping and pixel inspection."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def client_to_canvas_coords(
    client_x: float,
    client_y: float,
    rect_left: float,
    rect_top: float,
    rect_width: float,
    rect_height: float,
    canvas_width: int,
    canvas_height: int,
) -> tuple[float, float]:
    """Convert browser MouseEvent clientX/clientY into internal canvas buffer coordinates."""
    if rect_width <= 0 or rect_height <= 0:
        raise ValueError("Canvas bounding rect width and height must be positive.")
    scale_x = float(canvas_width) / float(rect_width)
    scale_y = float(canvas_height) / float(rect_height)
    cx = (float(client_x) - float(rect_left)) * scale_x
    cy = (float(client_y) - float(rect_top)) * scale_y
    return cx, cy


def canvas_point_to_source_pixel(
    canvas_x: float,
    canvas_y: float,
    pan_x: float,
    pan_y: float,
    zoom: float,
    image_width: int,
    image_height: int,
    *,
    clamp: bool = True,
) -> dict[str, Any]:
    """Map a canvas buffer point (canvas_x, canvas_y) to integer source-image pixel (x, y).

    Regardless of zoom level (e.g. 0.5x, 1x, 4x, 16x, 32x) or pan offset (pan_x, pan_y),
    a canvas point inside pixel (i, j) rendered at [pan_x + i*zoom, pan_x + (i+1)*zoom)
    maps deterministically to source pixel (i, j).
    """
    if zoom <= 0 or not math.isfinite(zoom):
        raise ValueError(f"zoom must be a positive finite number, got {zoom!r}")
    if image_width <= 0 or image_height <= 0:
        raise ValueError(f"Invalid image dimensions: {image_width}x{image_height}")

    raw_x = (float(canvas_x) - float(pan_x)) / float(zoom)
    raw_y = (float(canvas_y) - float(pan_y)) / float(zoom)
    px = math.floor(raw_x + 1e-9)
    py = math.floor(raw_y + 1e-9)
    in_bounds = (0 <= px < image_width) and (0 <= py < image_height)

    if clamp:
        clamped_x = max(0, min(image_width - 1, px))
        clamped_y = max(0, min(image_height - 1, py))
    else:
        clamped_x, clamped_y = px, py

    return {
        "x": int(clamped_x),
        "y": int(clamped_y),
        "unclamped_x": int(px),
        "unclamped_y": int(py),
        "raw_x": round(raw_x, 4),
        "raw_y": round(raw_y, 4),
        "in_bounds": bool(in_bounds),
    }


def canvas_rect_to_source_box(
    canvas_x1: float,
    canvas_y1: float,
    canvas_x2: float,
    canvas_y2: float,
    pan_x: float,
    pan_y: float,
    zoom: float,
    image_width: int,
    image_height: int,
) -> dict[str, Any]:
    """Map a dragged canvas rectangle to a source-image integer pixel box {x, y, w, h}.

    Uses half-open pixel intervals [x, x+w) and [y, y+h) clamped to [0, image_width]
    and [0, image_height], guaranteeing accurate source coordinates at any zoom level.
    """
    if zoom <= 0 or not math.isfinite(zoom):
        raise ValueError(f"zoom must be a positive finite number, got {zoom!r}")
    if image_width <= 0 or image_height <= 0:
        raise ValueError(f"Invalid image dimensions: {image_width}x{image_height}")

    left_c = min(float(canvas_x1), float(canvas_x2))
    right_c = max(float(canvas_x1), float(canvas_x2))
    top_c = min(float(canvas_y1), float(canvas_y2))
    bottom_c = max(float(canvas_y1), float(canvas_y2))

    raw_x0 = (left_c - float(pan_x)) / float(zoom)
    raw_y0 = (top_c - float(pan_y)) / float(zoom)
    raw_x1 = (right_c - float(pan_x)) / float(zoom)
    raw_y1 = (bottom_c - float(pan_y)) / float(zoom)

    x0 = max(0, min(image_width - 1, math.floor(raw_x0 + 1e-9)))
    y0 = max(0, min(image_height - 1, math.floor(raw_y0 + 1e-9)))

    # If the user clicked a single pixel or dragged across pixels, include the end pixel
    x1 = max(x0 + 1, min(image_width, math.floor(raw_x1 - 1e-9) + 1))
    y1 = max(y0 + 1, min(image_height, math.floor(raw_y1 - 1e-9) + 1))

    w = int(x1 - x0)
    h = int(y1 - y0)

    return {
        "x": int(x0),
        "y": int(y0),
        "w": w,
        "h": h,
        "x1": int(x1),
        "y1": int(y1),
        "uv": [
            round(x0 / image_width, 6),
            round(y0 / image_height, 6),
            round(x1 / image_width, 6),
            round(y1 / image_height, 6),
        ],
    }


def source_box_to_canvas_rect(
    box: dict[str, int],
    pan_x: float,
    pan_y: float,
    zoom: float,
) -> dict[str, float]:
    """Convert a source-image pixel box {x, y, w, h} back to canvas viewport rectangle."""
    return {
        "canvas_x": float(pan_x) + float(box["x"]) * float(zoom),
        "canvas_y": float(pan_y) + float(box["y"]) * float(zoom),
        "canvas_w": float(box["w"]) * float(zoom),
        "canvas_h": float(box["h"]) * float(zoom),
    }


def validate_selection_box(
    box: dict[str, Any],
    image_width: int,
    image_height: int,
) -> dict[str, int]:
    """Validate that a selection box {x, y, w, h} lies strictly inside the source image."""
    try:
        x = int(box["x"])
        y = int(box["y"])
        w = int(box["w"])
        h = int(box["h"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"selection_box must contain integer x, y, w, h: {exc}") from exc

    if w <= 0 or h <= 0:
        raise ValueError(f"selection_box width and height must be positive, got w={w}, h={h}")
    if x < 0 or y < 0 or (x + w) > image_width or (y + h) > image_height:
        raise ValueError(
            f"selection_box ({x}, {y}, {w}, {h}) exceeds image bounds {image_width}x{image_height}"
        )
    return {"x": x, "y": y, "w": w, "h": h}


def inspect_pixel_at(rgba_array: np.ndarray, x: int, y: int) -> dict[str, Any]:
    """Return RGBA and hex colour values at source pixel (x, y)."""
    arr = np.asarray(rgba_array, dtype=np.uint8)
    h, w = arr.shape[:2]
    if not (0 <= x < w and 0 <= y < h):
        raise ValueError(f"Pixel coordinate ({x}, {y}) out of bounds for {w}x{h} image.")
    r, g, b, a = (int(v) for v in arr[y, x])
    return {
        "x": int(x),
        "y": int(y),
        "r": r,
        "g": g,
        "b": b,
        "a": a,
        "rgba": [r, g, b, a],
        "hex": f"#{r:02x}{g:02x}{b:02x}",
        "hexa": f"#{r:02x}{g:02x}{b:02x}{a:02x}",
    }
