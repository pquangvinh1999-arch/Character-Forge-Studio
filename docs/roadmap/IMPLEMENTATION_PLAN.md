# Implementation Plan (`IMPLEMENTATION_PLAN.md`)

---

## Phase 0 — Repository Audit & Architecture Foundation (Completed)

- [x] Clone and pin all three upstream repositories read-only under `vendor/` (`vendor/VENDOR_LOCK.json`):
  - `0x0funky/agent-sprite-forge` @ `72fa5ad92d79b811acff464da32c8f3b1caa010f` (MIT)
  - `aldegad/sprite-gen` @ `4f5ccd55c7cf06685a41f954acc1e476b7772ece` (Apache-2.0 + NOTICE)
  - `Donchitos/Claude-Code-Game-Studios` @ `05ad7c8a5b8aa2aa86bbd3439ae7cf7295cac418` (MIT)
- [x] Verify GitHub authentication and token scope (`ghu_*` repository-scoped token blocker documented; `scripts/prepare_github_forks.py` provided).
- [x] Preserve all copyright, licenses, and `sprite-gen` `NOTICE` attribution in [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).
- [x] Produce [`docs/audit/UPSTREAM_AUDIT.md`](../audit/UPSTREAM_AUDIT.md).
- [x] Produce [`docs/architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md) and [`docs/architecture/PHASE2_TECHNICAL_SPECS.md`](../architecture/PHASE2_TECHNICAL_SPECS.md).
- [x] Produce [`docs/architecture/INTEGRATION_MATRIX.md`](../architecture/INTEGRATION_MATRIX.md).
- [x] Create shared `AGENTS.md` and `.agents/skills/` for Google Antigravity CLI and OpenAI Codex CLI.

---

## Phase 1 — Local MVP Bootstrap (Active Implementation)

### Step 1.1: Core Packages (`packages/`)
- `packages/character_core/`:
  - `ingest.py`: Non-destructive PNG/GIF ingest, SHA-256 verification, zero hardcoded character dependencies.
  - `gif_extractor.py`: Extract individual RGBA frames, per-frame durations (`ms`), effective FPS, and pixel dimensions from any uploaded GIF or PNG.
  - `coords.py`: Exact zoom-invariant canvas-to-source pixel coordinate mapping (`canvas_point_to_source_pixel`, `canvas_rect_to_source_box`, `source_box_to_uv`).
- `packages/forge_adapter/`:
  - `adapter.py`: Clean wrapper around `vendor/agent-sprite-forge/shared/forge_core.py` and `skills/generate2dsprite/scripts/export_engine.py` without modifying vendor files.
- `packages/sprite_gen_adapter/`:
  - `adapter.py`: Clean wrapper around selected `vendor/sprite-gen` utilities (palette extraction, pitch estimation, motion metrics) with paid API calls blocked by default.
- `packages/project_store/`:
  - `store.py`: Project creation, save/load, immutable version snapshots (`v0001`, `v0002`, ...), version diff inspection, and non-destructive rollback.
- `packages/agent_bridge/`:
  - `budget_gate.py`: Explicit budget guard preventing unapproved paid AI API calls.
  - `edit_jobs.py`: Structured JSON selection-edit job creation (`character-forge.edit_job.v1`), region-confined deterministic pixel transformations (tint/recolor/outline/clear/brightness or agent patch application), and strict outside-region pixel preservation.
- `packages/exporters/`:
  - `manifest.py`: Engine-independent character manifest (`character-forge.manifest.v1`).
  - `godot4.py`: Working Godot 4 frame-animation export prototype producing `.tres` (`SpriteFrames`), `.tscn` (`AnimatedSprite2D`), atlas `.png`, and `project.godot` via `agent-sprite-forge` `export_engine.py`.
- `packages/qa_gate/`:
  - `locality.py`: Bit-exact outside-selection pixel preservation verification + diff report.
  - `godot_smoke.py`: Real headless Godot 4 (`godot --headless`) import and resource verification smoke test.

### Step 1.2: Localhost Backend & Visual Studio UI (`apps/`)
- `apps/studio_api/`:
  - FastAPI application serving REST endpoints, static UI assets, Server-Sent Events (`/api/projects/{project_id}/events`), and WebSocket (`/ws/projects/{project_id}`).
- `apps/studio_web/`:
  - Zero-build HTML5 + CSS + Vanilla JS single-page studio:
    - Upload PNG or animated GIF (or load saved projects).
    - Transparent checkerboard canvas with zoom ($1\times$ to $32\times$), pan, pixel grid overlay, and live cursor pixel inspector (`(x, y)` in source pixels + `RGBA(r, g, b, a)` + `#HEX`).
    - Timeline strip showing extracted frames, frame index, frame duration (ms), FPS control, Play, Pause, Scrub slider, Step Forward/Back.
    - Interactive rectangular region selection tool showing exact source-image pixel coordinates `(x, y, w, h)` regardless of zoom or pan.
    - Natural-language edit instruction panel + optional local preview operation that saves a structured JSON edit job, streams real-time status via SSE/WebSocket, creates a new version snapshot, and verifies original asset immutability.
    - Version History & Rollback panel with SHA-256 verification badges.
    - Export panel generating the Engine-Independent Character Manifest (`manifest.json`) and Godot 4 (`SpriteFrames` `.tres` + `.tscn`) bundle, plus one-click Godot 4 headless smoke test execution.
- `run-studio.bat` (Windows CMD launcher) & `run-studio.sh` (Linux/macOS launcher).

### Step 1.3: Automated Verification & Acceptance Gate (`tests/`)
- Unit & integration tests covering:
  1. Upstream lock & license/NOTICE presence (`test_upstream_audit.py`).
  2. PNG & multi-frame GIF upload, frame extraction, FPS/duration accuracy, and zero hardcoded character dependencies (`test_ingest_and_frames.py`).
  3. Zoom-invariant canvas-to-source coordinate mapping across zoom levels $0.5\times \dots 32\times$ and pan offsets (`test_coords.py`).
  4. Region selection edit job JSON persistence, strict pixel preservation outside selection box, version history, and rollback (`test_jobs_versions_rollback.py`).
  5. Original asset byte-for-byte immutability before and after edits and rollbacks (`test_original_immutability.py`).
  6. Engine-independent character manifest & real Godot 4 export + `godot --headless` import smoke test (`test_godot_export_smoke.py`).
  7. FastAPI REST + SSE/WebSocket end-to-end workflow (`test_studio_api_e2e.py`).

---

## Phase 2 — Advanced Production & Rigging (Design Only — Gate Locked Until Phase 1 Acceptance)

All 10 Phase 2 technical specifications are complete in [`docs/architecture/PHASE2_TECHNICAL_SPECS.md`](../architecture/PHASE2_TECHNICAL_SPECS.md). Implementation of Phase 2 begins only after Phase 1 acceptance sign-off.
