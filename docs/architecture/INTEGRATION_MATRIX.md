# Integration Matrix (`INTEGRATION_MATRIX.md`)

> **Architectural Rule**: Every operation in Character Forge Studio has exactly **one** canonical pipeline owner. Upstream repositories in `vendor/` are never modified directly and never compete to perform the same operation.

---

## 1. End-to-End Capability Ownership Matrix

| Domain | Operation / Capability | Canonical Owner | Upstream Source / Module | Studio Package / Adapter | Phase |
|---|---|---|---|---|---|
| **Ingest & Non-Destructive Storage** | Upload PNG / multi-frame GIF & preserve byte-identical original asset (`sha256` verified) | **Character Forge Studio (Native)** | Native Python (`Pillow`, `hashlib`) + `forge_core` atomic I/O conventions | `packages/character_core/ingest.py` | **Phase 1 (MVP)** |
| **Frame Extraction (GIF)** | Extract individual RGBA frames, per-frame duration (`ms`), FPS, and dimensions from animated GIF | **Character Forge Studio (Native)** | Native `Pillow` (`ImageSequence`) normalized to `forge_core` straight-alpha RGBA | `packages/character_core/gif_extractor.py` | **Phase 1 (MVP)** |
| **Frame Extraction (Component Strip / Sheet)** | Segment irregular sprite strips, projection-profile cuts, and uniform background cutout | **sprite-gen** | `vendor/sprite-gen/sprite_gen/frames/extract.py`, `segment.py`, `cutout.py` | `packages/sprite_gen_adapter/adapter.py` | **Phase 1 / 2** |
| **Core RGBA Math & Anchors** | Straight-alpha RGBA canonicalization, alpha hygiene, subject bounding box, feet/stance/centroid anchor calculation, seam metrics | **agent-sprite-forge** | `vendor/agent-sprite-forge/shared/forge_core.py` | `packages/forge_adapter/adapter.py` | **Phase 1 (MVP)** |
| **Canvas Viewport & Pixel Coordinate Mapping** | Transparent checkerboard canvas, integer/fractional zoom, pan, pixel inspector (`x, y, RGBA, hex`), and zoom-invariant selection mapping to source image pixels | **Character Forge Studio (Native)** | Native HTML5 Canvas + pure math module verified both in Python (`packages/character_core/coords.py`) and JS (`apps/studio_web/static/app.js`) | `packages/character_core/coords.py` & `apps/studio_web/` | **Phase 1 (MVP)** |
| **Selection-to-Agent Edit Job Protocol** | Save source-pixel selection `(x, y, w, h)`, frame index, and natural-language instruction as structured JSON job with strict region-only pixel edit & locality QA | **Character Forge Studio + agent-sprite-forge** | Studio Job Schema (`character-forge.edit_job.v1`) + `edit_locality_check.py` locality invariants | `packages/agent_bridge/edit_jobs.py` | **Phase 1 (MVP)** |
| **Project Save/Load & Undoable Version History** | Immutable snapshot history (`v0001`, `v0002`, ...), version diff metadata, non-destructive rollback, and project state persistence | **Character Forge Studio (Native)** | Native content-addressable / snapshot store in `packages/project_store/` | `packages/project_store/store.py` | **Phase 1 (MVP)** |
| **Real-Time Job Status Streaming** | Stream incremental job progress, step logs, and output artifacts to the browser without fake progress | **Character Forge Studio (Native)** | FastAPI Server-Sent Events (`/api/projects/{id}/events` SSE) & WebSocket (`/ws/projects/{id}`) | `apps/studio_api/streaming.py` | **Phase 1 (MVP)** |
| **Engine-Independent Character Manifest** | Canonical character manifest (`character-forge.manifest.v1`) recording source hash, frame dimensions, anchors, clips, frame timings, and version lineage | **Character Forge Studio (Native)** | Synthesizes `agent-sprite-forge` `animation-clips.json` v2 + Studio metadata | `packages/exporters/manifest.py` | **Phase 1 (MVP)** |
| **Godot 4 Export & Smoke Verification** | Generate Godot 4 `SpriteFrames` (`.tres`), `AnimatedSprite2D` (`.tscn`), and atlas `.png` + round-trip parser verification + real `godot --headless` import smoke test | **agent-sprite-forge** | `vendor/agent-sprite-forge/skills/generate2dsprite/scripts/export_engine.py` | `packages/exporters/godot4.py` | **Phase 1 (MVP)** |
| **Curation Sidecar & Secondary Effects** | Non-destructive frame curation, palette recolor variants, idle breathing (`breathe`), silhouette shadow (`shadow`), and soft-part sway (`video-sway`) | **sprite-gen** | `vendor/sprite-gen/sprite_gen/curate/curation.py`, `effects/breathe.py`, `effects/recolor.py`, `effects/shadow.py` | `packages/sprite_gen_adapter/adapter.py` | **Phase 1 / 2** |
| **Cutout Rigging & Bone/IK Animation** | Portable SVG cutout rig (`rig.v1`), hierarchical bones, slot sprite swapping, 2-bone IK, and pixel-clean route D rendering | **agent-sprite-forge** | `vendor/agent-sprite-forge/skills/codeart2d/scripts/rig_animate.py`, `codeart_core.py` | `packages/forge_adapter/adapter.py` | **Phase 2 (Spec)** |
| **Asset Specs, Art Bible & Evidence-Based QA Gates** | Structured asset specs, naming/budget audits, `COMPLIANT` / `NOT ASSESSED` / `BLOCKED` / `NON-COMPLIANT` QA verdicts | **Claude-Code-Game-Studios (Ported)** | `vendor/Claude-Code-Game-Studios/.claude/skills/asset-spec`, `asset-audit`, `smoke-check` | `.agents/skills/*` & `packages/qa_gate/` | **Phase 1 & 2** |
| **Paid AI Provider Budget Gate** | Prevent unapproved paid API calls; require explicit user budget configuration and per-job approval | **Character Forge Studio + agent-sprite-forge** | Modeled on `media_ledger.py` + `CCGS` external call guard | `packages/agent_bridge/budget_gate.py` | **Phase 1 & 2** |
| **Unity Import/Export Adapter** | Aseprite JSON + TextureImporter `.meta` preset + Unity `AnimatorController` / `AnimationClip` generation | **agent-sprite-forge + Studio Unity Adapter** | `export_engine.py --target aseprite-json` + `unity-specialist.md` rules | `packages/exporters/unity_spec.py` | **Phase 2 (Spec)** |

---

## 2. Explicit Rejections (What We Do Not Import or Duplicate)

1. **No Competing Web Servers**:
   - `sprite-gen` includes `serve_curation.py` and `serve_compose.py` (stdlib `ThreadingHTTPServer` SPAs bound to `sprite-gen`'s internal `run-dir` format).
   - Character Forge Studio does **not** run those competing HTTP servers. Instead, `apps/studio_api/` (FastAPI) and `apps/studio_web/` (Vanilla HTML/CSS/JS) provide the single unified localhost studio, calling `sprite-gen` and `agent-sprite-forge` pure Python functions through their adapters.
2. **No Competing Godot / Aseprite Exporters**:
   - `sprite-gen`'s `export_aseprite.py` is bypassed in favor of `agent-sprite-forge`'s `export_engine.py`, which handles both `aseprite-json` and `godot-spriteframes` / `godot-sprite3d` from a single unified clip contract (`generate2dsprite.animation_clips.v2`) with round-trip verification.
3. **No Unchecked Paid AI Calls**:
   - Neither `sprite_gen/gen/*` nor `agent-sprite-forge/skills/generate2dmedia/*` may be invoked automatically by the studio backend without passing through `packages/agent_bridge/budget_gate.py` (which defaults to `paid_apis_enabled = False`, `max_budget_usd = 0.0`).
4. **No Claude Code Native Hook Assumptions**:
   - `.claude/hooks/*.sh` and `.claude/statusline.sh` from `Claude-Code-Game-Studios` are kept untouched in `vendor/` for reference only and are never executed by the studio runtime or required by Antigravity/Codex agents.
