"""Phase 1 Verification: Selection edit jobs, strict pixel preservation, version history, rollback, SSE/WS streaming, and original asset immutability."""

from __future__ import annotations

import hashlib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from packages.agent_bridge.budget_gate import BudgetApprovalError, BudgetGate
from tests.conftest import make_synthetic_gif_bytes


def test_selection_edit_job_version_history_rollback_and_original_immutability(client: TestClient) -> None:
    """Acceptance Criteria #4, #5, #6:
    - Original asset remains unchanged.
    - Edit job can be saved and inspected with frame index, selection coordinates, and instruction.
    - Zero pixels outside selection_box change.
    - Version history and rollback work and restore exact frame pixels.
    - SSE and WebSocket deliver incremental job status events.
    """
    gif_bytes, _ = make_synthetic_gif_bytes(width=32, height=32, frame_count=4)
    original_sha256 = hashlib.sha256(gif_bytes).hexdigest()

    up_res = client.post(
        "/api/projects/upload",
        files={"file": ("hero_anim.gif", gif_bytes, "image/gif")},
        data={"name": "HeroCharacter"},
    )
    assert up_res.status_code == 200
    proj_v1 = up_res.json()
    pid = proj_v1["project_id"]
    assert proj_v1["current_version_id"] == "v0001"
    v1_frame1_sha = proj_v1["versions"][0]["frames"][1]["rgba_pixel_sha256"]
    v1_frame0_sha = proj_v1["versions"][0]["frames"][0]["rgba_pixel_sha256"]

    # Record initial RGBA of frame 1 before edit
    store = client.app.state.store
    frame1_before = store.load_frame_rgba(pid, 1, "v0001")

    # Submit a selection edit job on Frame 1, box (x=10, y=8, w=10, h=6)
    selection_box = {"x": 10, "y": 8, "w": 10, "h": 6}
    job_res = client.post(
        f"/api/projects/{pid}/jobs",
        json={
            "frame_index": 1,
            "selection_box": selection_box,
            "instruction": "Recolor the selected head visor to gold #f1c40f while preserving all outside pixels",
            "operation": "recolor",
            "color_hex": "#f1c40f",
            "apply_immediately": True,
        },
    )
    assert job_res.status_code == 200
    payload = job_res.json()
    job = payload["job"]
    proj_v2 = payload["project"]

    # Verify structured JSON job fields
    assert job["schema"] == "character-forge.edit_job.v1"
    assert job["status"] == "completed"
    assert job["frame_index"] == 1
    assert job["selection_box"] == selection_box
    assert job["base_version_id"] == "v0001"
    assert job["produced_version_id"] == "v0002"
    assert "gold #f1c40f" in job["instruction"]
    assert len(job["events"]) >= 4

    # Verify strict locality QA: zero pixels outside selection_box changed, pixels inside changed
    locality = job["locality_qa"]
    assert locality["status"] == "pass"
    assert locality["outside_changed_pixels"] == 0
    assert locality["outside_max_channel_diff"] == 0
    assert locality["inside_changed_pixels"] > 0

    # Verify direct NumPy comparison between v0001 and v0002 on Frame 1
    frame1_after = store.load_frame_rgba(pid, 1, "v0002")
    mask = np.zeros((32, 32), dtype=bool)
    mask[8 : 8 + 6, 10 : 10 + 10] = True
    assert np.array_equal(frame1_before[~mask], frame1_after[~mask]), "Pixels outside selection box must be identical!"
    assert not np.array_equal(frame1_before[mask], frame1_after[mask]), "Pixels inside selection box must be updated!"

    # Verify untouched frames (e.g. Frame 0) are byte-for-byte identical in v0002
    v2_doc = proj_v2["versions"][1]
    assert v2_doc["version_id"] == "v0002"
    assert v2_doc["frames"][0]["rgba_pixel_sha256"] == v1_frame0_sha
    assert v2_doc["frames"][1]["rgba_pixel_sha256"] != v1_frame1_sha

    # Verify job can be fetched and inspected via GET /api/projects/{pid}/jobs/{job_id}
    job_get = client.get(f"/api/projects/{pid}/jobs/{job['job_id']}")
    assert job_get.status_code == 200
    assert job_get.json()["job_id"] == job["job_id"]

    # Verify job artifacts (patch_before, patch_after, locality_diff) are served
    for kind in ("patch_before", "patch_after", "locality_diff"):
        art_res = client.get(f"/api/projects/{pid}/jobs/{job['job_id']}/artifact/{kind}")
        assert art_res.status_code == 200
        assert art_res.headers["content-type"] == "image/png"

    # Verify original uploaded GIF file is 100% unchanged after edit
    orig_res = client.get(f"/api/projects/{pid}/original")
    assert orig_res.status_code == 200
    assert orig_res.content == gif_bytes
    assert hashlib.sha256(orig_res.content).hexdigest() == original_sha256

    # Rollback to v0001
    rb_res = client.post(
        f"/api/projects/{pid}/rollback",
        json={"target_version_id": "v0001", "reason": "Automated test rollback verification"},
    )
    assert rb_res.status_code == 200
    rb_data = rb_res.json()
    assert rb_data["rollback"]["previous_version_id"] == "v0002"
    assert rb_data["rollback"]["current_version_id"] == "v0001"
    assert rb_data["project"]["current_version_id"] == "v0001"

    # Verify active Frame 1 after rollback matches v0001 byte-for-byte
    frame1_rolled_back = store.load_frame_rgba(pid, 1)
    assert np.array_equal(frame1_rolled_back, frame1_before)

    # Verify original uploaded GIF file is still 100% unchanged after rollback
    orig_after_rb = client.get(f"/api/projects/{pid}/original")
    assert hashlib.sha256(orig_after_rb.content).hexdigest() == original_sha256

    # Verify SSE event stream contains all real job & rollback events
    sse_res = client.get(f"/api/projects/{pid}/events", params={"once": "true"})
    assert sse_res.status_code == 200
    sse_text = sse_res.text
    for expected_event in ("project.created", "job.created", "job.progress", "job.locality_qa", "job.completed", "project.rolled_back"):
        assert f"event: {expected_event}" in sse_text

    # Verify WebSocket stream also replays project events
    with client.websocket_connect(f"/ws/projects/{pid}") as ws:
        first_msg = ws.receive_json()
        assert first_msg["type"] == "project.created"


def test_paid_ai_budget_gate_blocks_unapproved_calls() -> None:
    """Architectural Principle: Do not call paid AI APIs without an explicitly configured budget and user approval."""
    gate = BudgetGate()
    assert gate.status()["paid_apis_enabled"] is False
    with pytest.raises(BudgetApprovalError):
        gate.require_approval("openai", estimated_cost_usd=0.05)
