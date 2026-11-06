"""Shared test fixtures for Character Forge Studio automated QA suite.

Generates synthetic pixel-art PNG and multi-frame GIF assets in memory so the
studio has zero hardcoded example character dependencies.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from apps.studio_api.main import create_app


def make_synthetic_png_bytes(width: int = 24, height: int = 24) -> bytes:
    """Create a deterministic transparent pixel-art PNG in memory."""
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    # Body block (x: 6..18, y: 4..20)
    arr[4:20, 6:18] = [41, 128, 185, 255]
    # Visor region (x: 8..16, y: 6..10)
    arr[6:10, 8:16] = [236, 240, 241, 255]
    # Feet (y: 20..22)
    arr[20:22, 7:11] = [44, 62, 80, 255]
    arr[20:22, 13:17] = [44, 62, 80, 255]
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def make_synthetic_gif_bytes(width: int = 32, height: int = 32, frame_count: int = 4) -> tuple[bytes, list[int]]:
    """Create a real multi-frame transparent animated GIF with distinct frames and timings."""
    frames: list[Image.Image] = []
    durations = [80, 100, 120, 100][:frame_count]
    for idx in range(frame_count):
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        bob = idx % 2
        # Torso
        arr[6 + bob : 24 + bob, 10:22] = [52, 152, 219, 255]
        # Head/visor
        arr[8 + bob : 12 + bob, 12:20] = [231, 76, 60, 255]
        # Frame-specific pixel marker at (4 + idx, 4)
        arr[4:8, 4 + idx * 2 : 6 + idx * 2] = [46, 204, 113, 255]
        # Feet planted at y=28
        arr[24:28, 11:15] = [149, 165, 166, 255]
        arr[24:28, 17:21] = [149, 165, 166, 255]
        frames.append(Image.fromarray(arr, mode="RGBA"))

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
    )
    return buf.getvalue(), durations


@pytest.fixture()
def temp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


@pytest.fixture()
def client(temp_workspace: Path) -> TestClient:
    app = create_app(workspace_dir=temp_workspace)
    return TestClient(app)
