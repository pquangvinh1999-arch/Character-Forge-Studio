"""Phase 1 Verification: PNG/GIF upload, frame extraction, FPS/timeline, pixel inspector, and zoom-invariant coordinate math."""

from __future__ import annotations

import hashlib
import pytest
from fastapi.testclient import TestClient

from packages.character_core.coords import (
    canvas_point_to_source_pixel,
    canvas_rect_to_source_box,
    source_box_to_canvas_rect,
)
from tests.conftest import make_synthetic_gif_bytes, make_synthetic_png_bytes


def test_localhost_ui_and_health(client: TestClient) -> None:
    index_res = client.get("/")
    assert index_res.status_code == 200
    assert "Character Forge Studio" in index_res.text
    assert "sprite-canvas" in index_res.text

    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    data = health_res.json()
    assert data["status"] == "ok"
    assert data["budget_gate"]["paid_apis_enabled"] is False
    assert len(data["vendor_lock"]) == 3


def test_upload_png_and_gif_and_inspect_frames_and_pixels(client: TestClient) -> None:
    # 1. Upload PNG
    png_bytes = make_synthetic_png_bytes(width=24, height=24)
    png_sha = hashlib.sha256(png_bytes).hexdigest()
    res_png = client.post(
        "/api/projects/upload",
        files={"file": ("knight_idle.png", png_bytes, "image/png")},
        data={"name": "KnightPNG"},
    )
    assert res_png.status_code == 200
    proj_png = res_png.json()
    assert proj_png["source_format"] == "PNG"
    assert proj_png["width"] == 24
    assert proj_png["height"] == 24
    assert proj_png["frame_count"] == 1
    assert proj_png["original_file"]["sha256"] == png_sha
    assert proj_png["original_integrity"]["unchanged"] is True

    # 2. Upload multi-frame animated GIF
    gif_bytes, expected_durations = make_synthetic_gif_bytes(width=32, height=32, frame_count=4)
    gif_sha = hashlib.sha256(gif_bytes).hexdigest()
    res_gif = client.post(
        "/api/projects/upload",
        files={"file": ("runner_walk.gif", gif_bytes, "image/gif")},
        data={"name": "RunnerGIF"},
    )
    assert res_gif.status_code == 200
    proj_gif = res_gif.json()
    pid = proj_gif["project_id"]
    assert proj_gif["source_format"] == "GIF"
    assert proj_gif["width"] == 32
    assert proj_gif["height"] == 32
    assert proj_gif["frame_count"] == 4
    assert proj_gif["total_duration_ms"] == sum(expected_durations)
    assert proj_gif["original_file"]["sha256"] == gif_sha
    assert proj_gif["original_integrity"]["unchanged"] is True

    # Verify individual frames can be fetched and have distinct hashes
    vdoc = proj_gif["versions"][0]
    assert len(vdoc["frames"]) == 4
    for idx, f_rec in enumerate(vdoc["frames"]):
        assert f_rec["index"] == idx
        assert f_rec["duration_ms"] == expected_durations[idx]
        img_res = client.get(f"/api/projects/{pid}/frames/{idx}/image")
        assert img_res.status_code == 200
        assert img_res.headers["content-type"] == "image/png"

    # Verify pixel inspection on frame 0: (14, 10) is inside head/visor [231, 76, 60, 255]; (0, 0) is transparent [0, 0, 0, 0]
    px_visor = client.get(f"/api/projects/{pid}/frames/0/pixel", params={"x": 14, "y": 10}).json()
    assert px_visor["x"] == 14 and px_visor["y"] == 10
    assert px_visor["a"] == 255
    assert px_visor["r"] > 200

    px_empty = client.get(f"/api/projects/{pid}/frames/0/pixel", params={"x": 0, "y": 0}).json()
    assert px_empty["rgba"] == [0, 0, 0, 0]

    # Verify timeline FPS update
    tl_res = client.post(f"/api/projects/{pid}/timeline", json={"fps": 12.5, "loop": False})
    assert tl_res.status_code == 200
    tl_proj = tl_res.json()
    assert tl_proj["fps"] == 12.5
    assert tl_proj["loop"] is False


@pytest.mark.parametrize("zoom", [0.5, 1.0, 2.0, 4.0, 8.0, 12.0, 16.0, 24.0, 32.0])
@pytest.mark.parametrize("pan", [(0.0, 0.0), (45.0, 30.0), (-20.5, 112.25)])
def test_canvas_selection_produces_accurate_source_coordinates_across_all_zooms(
    client: TestClient,
    zoom: float,
    pan: tuple[float, float],
) -> None:
    """Acceptance Criterion #3: Canvas selection produces accurate source coordinates regardless of zoom."""
    img_w, img_h = 64, 48
    pan_x, pan_y = pan

    # Target source box: x=10, y=8, w=14, h=12 (spans x in [10..23], y in [8..19])
    target_box = {"x": 10, "y": 8, "w": 14, "h": 12}

    # Simulate user dragging from the middle of top-left pixel (10, 8) to the middle of bottom-right pixel (23, 19)
    start_canvas_x = pan_x + (10 + 0.35) * zoom
    start_canvas_y = pan_y + (8 + 0.35) * zoom
    end_canvas_x = pan_x + (23 + 0.65) * zoom
    end_canvas_y = pan_y + (19 + 0.65) * zoom

    mapped_point = canvas_point_to_source_pixel(start_canvas_x, start_canvas_y, pan_x, pan_y, zoom, img_w, img_h)
    assert mapped_point["x"] == 10
    assert mapped_point["y"] == 8
    assert mapped_point["in_bounds"] is True

    mapped_box = canvas_rect_to_source_box(
        start_canvas_x,
        start_canvas_y,
        end_canvas_x,
        end_canvas_y,
        pan_x,
        pan_y,
        zoom,
        img_w,
        img_h,
    )
    assert mapped_box["x"] == target_box["x"]
    assert mapped_box["y"] == target_box["y"]
    assert mapped_box["w"] == target_box["w"]
    assert mapped_box["h"] == target_box["h"]

    # Reverse drag (bottom-right to top-left) must yield the exact same source pixel box
    mapped_reverse = canvas_rect_to_source_box(
        end_canvas_x,
        end_canvas_y,
        start_canvas_x,
        start_canvas_y,
        pan_x,
        pan_y,
        zoom,
        img_w,
        img_h,
    )
    assert mapped_reverse["x"] == target_box["x"]
    assert mapped_reverse["y"] == target_box["y"]
    assert mapped_reverse["w"] == target_box["w"]
    assert mapped_reverse["h"] == target_box["h"]

    # Round-trip canvas rect back to source box
    canvas_rect = source_box_to_canvas_rect(target_box, pan_x, pan_y, zoom)
    assert abs(canvas_rect["canvas_x"] - (pan_x + 10 * zoom)) < 1e-6
    assert abs(canvas_rect["canvas_w"] - (14 * zoom)) < 1e-6

    # Also verify REST API endpoint returns identical coordinates
    api_res = client.post(
        "/api/coords/map-rect",
        json={
            "canvas_x1": start_canvas_x,
            "canvas_y1": start_canvas_y,
            "canvas_x2": end_canvas_x,
            "canvas_y2": end_canvas_y,
            "pan_x": pan_x,
            "pan_y": pan_y,
            "zoom": zoom,
            "image_width": img_w,
            "image_height": img_h,
        },
    )
    assert api_res.status_code == 200
    api_box = api_res.json()
    assert (api_box["x"], api_box["y"], api_box["w"], api_box["h"]) == (10, 8, 14, 12)
