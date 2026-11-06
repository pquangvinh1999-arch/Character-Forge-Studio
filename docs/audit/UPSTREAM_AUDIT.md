# Phase 0 — Upstream Repository Audit (`UPSTREAM_AUDIT.md`)

> **Generated**: 2026-11-06  
> **Lock Manifest**: [`vendor/VENDOR_LOCK.json`](../../vendor/VENDOR_LOCK.json)  
> **Third-Party Attribution**: [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md)

---

## 1. Upstream Summary & Version Pinning

All three upstream repositories were cloned read-only into `vendor/` and inspected at their exact HEAD commits without modifying a single upstream file.

| Repository | Upstream URL | Pinned Commit (`SHA-1`) | Commit Date | Version | License | Notice File | Local Vendor Path |
|---|---|---|---|---|---|---|---|
| **agent-sprite-forge** | `https://github.com/0x0funky/agent-sprite-forge` | `72fa5ad92d79b811acff464da32c8f3b1caa010f` | `2026-11-06 05:01:53 +0800` | `0.4.0` (Core API `1.1`) | **MIT License** (`Copyright (c) 2026 0x0funky`) | None | `vendor/agent-sprite-forge/` |
| **sprite-gen** | `https://github.com/aldegad/sprite-gen` | `4f5ccd55c7cf06685a41f954acc1e476b7772ece` | `2026-11-02 05:32:26 +0900` | `3.15.0` | **Apache-2.0** (`Copyright 2026 Alex Kim`) | `vendor/sprite-gen/NOTICE` (preserved in root [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md)) | `vendor/sprite-gen/` |
| **Claude-Code-Game-Studios** | `https://github.com/Donchitos/Claude-Code-Game-Studios` | `05ad7c8a5b8aa2aa86bbd3439ae7cf7295cac418` | `2026-10-19 13:09:09 +1100` | `1.2.0` | **MIT License** (`Copyright (c) 2026 Donchitos`) | None | `vendor/Claude-Code-Game-Studios/` |

---

## 2. GitHub Fork Preparation & Blocker Report

### Verification Conducted
1. Checked `gh auth status`:
   - Logged in to `github.com` account `pquangvinh1999-arch` via `GITHUB_TOKEN` (`ghu_***`).
2. Checked token headers via read-only `gh api -i /user`:
   - `X-Oauth-Client-Id: Iv1.ad5f73e593b03f40` (GitHub Codespaces fine-grained installation token).
   - `X-Oauth-Scopes:` *(empty — repository-scoped token restricted to `pquangvinh1999-arch/Character-Forge-Studio`)*.
3. Project safety rules explicitly state: *"Do not silently perform destructive operations or publish code to GitHub without permission."*

### Resolution & Blocker Status
- **Status**: **Read-only upstream clones active in `vendor/`** (pinned via `vendor/VENDOR_LOCK.json`).
- **Blocker for Remote Fork Creation**:
  1. The environment's `GITHUB_TOKEN` (`ghu_*`) is a repository-scoped GitHub Codespaces token that lacks user-wide `repo` / `public_repo` scope required to create new forks under `pquangvinh1999-arch/*`.
  2. Remote GitHub mutations require explicit user authorization.
- **Prepared Automation**: [`scripts/prepare_github_forks.py`](../../scripts/prepare_github_forks.py) validates authentication scopes and—when run with `--execute` after authenticating with a full-scope Personal Access Token (`gh auth login --scopes repo`)—forks all three repositories under `pquangvinh1999-arch` and registers the `fork` git remote inside each `vendor/<repo>` checkout.

---

## 3. Detailed Upstream Audit

### 3.1 `0x0funky/agent-sprite-forge` (Primary Animation Production Engine)

- **Commit**: `72fa5ad92d79b811acff464da32c8f3b1caa010f`
- **License**: MIT (`vendor/agent-sprite-forge/LICENSE`)
- **Runtime & Dependencies**:
  - Core (`requirements.txt`): `numpy>=1.26`, `Pillow>=10.1`, `scipy>=1.11` (note: `shared/forge_core.py` includes a pure-NumPy vectorised run-length union-find fallback when `scipy` is absent or `FORGE_CORE_NO_SCIPY=1`).
  - Code-art SVG rasterization (`requirements-codeart.txt`): `resvg-py>=0.5,<0.6`.
  - Dev/QA (`requirements-dev.txt`): `pytest>=8`, `PyYAML>=6`, `jsonschema>=4.18`.
- **Shared Core Libraries (`vendor/agent-sprite-forge/shared/`)**:
  - `forge_core.py` (1,687 lines, API `1.1`): Canonical straight-alpha RGBA loading/saving (`load_rgba`, `save_png`), atomic no-replace file publication, connected components, alpha hygiene (`none`, `floor`, `detached`, `both`), subject anchors (`feet`, `stance`, `bbox`, `centroid`, `center`), premultiplied resampling (`box`, `lanczos`, `nearest`), `edge_seam_report`, `ownership_slice`, UTF-8 BOM-tolerant JSON I/O (`read_json`, `write_json`), `round_half_up`, and `utf8_stdio()`.
  - `forge_matte.py`: Background chroma key removal, border flood fill, spill suppression, and matte reporting.
  - `forge_palette.py`: Palette extraction, quantization, OKLab/LAB colour lock, and pixel grid reduction.
  - `forge_av.py`: FFmpeg/FFprobe video decoding, rational frame-rate conversion, VP9-alpha WebM and packed-alpha MP4 encoding.
  - `forge_nav.py`: 2D navigation and collision mask helpers.
  - `forge_schema.py` & `shared/schemas/*.schema.json`: Contract validation for `common.schema.json`, `sprite.schema.json`, `video.schema.json`, `map.schema.json`, `codeart.schema.json`, and `media.schema.json`.
- **Skill Suites & CLI Entry Points (`vendor/agent-sprite-forge/skills/`)**:
  1. `generate2dsprite/scripts/`:
     - `generate2dsprite.py`: End-to-end sprite sheet processing CLI.
     - `master_still.py`, `plan_guide.py`, `make_layout_guide.py`, `make_anchor_layout.py`: Still preparation and anchor layout guides.
     - `pixel_reduce.py`, `palette_tool.py`, `scale_frames.py`: Pixel snapping, palette quantization, and integer/premultiplied scaling.
     - `assemble_frames.py`, `sheet_qc.py`: Frame assembly and sprite sheet quality control.
     - `build_animation_clips.py`: Compiles frame sequences into `animation-clips.json` (`generate2dsprite.animation_clips.v2`).
     - `export_engine.py`: Exports compiled clips to **Godot 4 `SpriteFrames` (`.tres`) + `AnimatedSprite2D` (`.tscn`) + atlas PNG**, **Godot 4 `AnimatedSprite3D`**, and **Aseprite JSON + PNG**, with built-in round-trip parser verification (`parse_godot_resource`, `verify_godot_spriteframes`, `verify_aseprite`).
  2. `video2dsprite/scripts/`:
     - `video2dsprite.py`, `prepare_i2v_input.py`, `gait_loop.py`, `register_clip.py`, `colour_lock.py`, `finish_frames.py`, `retime.py`, `validate_animation.py`, `animation_review.py`, `sprite_set.py`, `engine_export.py`.
  3. `codeart2d/scripts/`:
     - `codeart_core.py`, `render_pixelspec.py`, `svg_render.py`, `rig_animate.py` (portable SVG cutout rig with hierarchical bones `<g id=NAME data-pivot="X Y">`, slot variants `data-variant`, 2-bone IK, and pixel finishing route D), `fx_build.py`, `pixel_qa.py`, `autotile_build.py`, `parallax_build.py`, `layout_build.py`, `ambient_bake.py`.
  4. `generate2dmap/scripts/`:
     - `edit_locality_check.py`: Verifies that an edited image only modifies pixels inside allowed `--edit-box` regions and preserves protected regions (`generate2dmap.edit_locality.v1`), outputting `locality-qa.json` and `locality-diff.png`.
     - `export_godot.py`, `export_ldtk.py`, `export_tiled.py`, `conform_background.py`, `validate_stage.py`, etc.
  5. `generate2dmedia/scripts/`:
     - `cli_media.py`, `route_media.py`, `media_ledger.py` (cost/budget tracking), `media_providers.py`, `forge_doctor.py`.

---

### 3.2 `aldegad/sprite-gen` (Selected Processing, Curation & Effects Engine)

- **Commit**: `4f5ccd55c7cf06685a41f954acc1e476b7772ece`
- **License**: Apache-2.0 (`vendor/sprite-gen/LICENSE`) + `vendor/sprite-gen/NOTICE`
- **Runtime & Dependencies (`pyproject.toml`)**:
  - `requires-python = ">=3.11"`
  - Core: `pillow>=12.3.0,<13` (compatible at runtime with Pillow >=10.1), `numpy>=2.2.6,<3`.
  - Optional: `torch>=2.13.0,<3` (for `rife_torch.py`), `pytest>=8.0`, `pytest-timeout>=2.3`.
- **Entry Point**:
  - Unified CLI `sprite_gen.cli:main` (`python -m sprite_gen.cli <verb>`) and wrapper scripts in `vendor/sprite-gen/scripts/`.
- **Subpackages (`vendor/sprite-gen/sprite_gen/`)**:
  - `frames/`: `extract.py` (alpha-centroid alignment, YCbCr/RGB chroma matting, run-length pitch estimation `estimate_pixel_grid_runlen`), `segment.py` (projection-profile + DP optimal-cut segmentation), `cutout.py` (uniform background cutout), `slice_sheet.py`, `unpack_atlas.py`, `decontam.py`, `alpha_floor.py`.
  - `curate/`: `curation.py` (non-destructive `curation.json` sidecar model storing frame selection, rejection, per-frame `dx`/`dy`/`scale`/`rotate` transforms without modifying source PNGs), `anchor.py`.
  - `effects/`: `breathe.py` & `breath_beat.py` (non-destructive idle breathing layer), `recolor.py` (deterministic palette-swap variants), `shadow.py` (silhouette shadow projection), `interpolate.py`, `anatomy.py`.
  - `compose/`: `compose_gif.py`, `compose_atlas.py`, `compose_cycle.py`, `export_aseprite.py`, `export_pngs.py`.
  - `qa/`: `inspect.py` (histogram/dHash/motion defect inspection), `score.py` (quantitative run scoring + correction hints), `motion.py` (`inspect-motion` contact/timing evidence), `handed.py` (asymmetric prop/handedness verification across directions), `preview.py`, `correction_loop.py`.
  - `video/`: `frames.py`, `loop.py`, `align.py`, `sway.py`, `sway_inspect.py`, `set_sheet.py` (8-way compass sheet `S SW W NW N NE E SE`), `stop.py`, `face_pack.py`, `face_bake.py`, `restoration.py`, `rife.py`, `rife_torch.py`.
  - `serve/`: `serve_curation.py` and `serve_compose.py` (stdlib `ThreadingHTTPServer` webviews for run curation and row composition).
  - `gen/`: Provider wrappers (`codex_provider.py`, `grok_provider.py`, `openai_provider.py`, `anthropic_api.py`).

---

### 3.3 `Donchitos/Claude-Code-Game-Studios` (Agent Orchestration, Asset Specs & QA Reference)

- **Commit**: `05ad7c8a5b8aa2aa86bbd3439ae7cf7295cac418`
- **License**: MIT (`vendor/Claude-Code-Game-Studios/LICENSE`)
- **Structure**:
  - `.claude/agents/`: 49 role-based markdown agent personas (including `art-director.md`, `technical-artist.md`, `godot-specialist.md`, `godot-gdscript-specialist.md`, `unity-specialist.md`, `qa-lead.md`, `qa-tester.md`, `tools-programmer.md`).
  - `.claude/skills/`: 75 workflow skills (`asset-spec`, `asset-audit`, `art-bible`, `smoke-check`, `qa-plan`, `consistency-check`, `setup-engine`, `test-evidence-review`, etc.).
  - `.claude/hooks/`: Bash/Python lifecycle hooks specific to Claude Code (`yaml-helper.sh`, session/pre-tool hooks).
  - `project.yaml`: Single source of truth for studio rigor/automation modes and naming/performance budgets.
- **Portability Findings**:
  - Claude Code Game Studios skills use Claude-specific frontmatter (`allowed-tools`, `!` bash pre-execution macros calling `.claude/hooks/yaml-helper.sh`, and Claude `Agent` subagent tool invocations).
  - **Architectural Rule Applied**: We do **not** assume Claude Code hooks or agents run natively in Google Antigravity CLI or OpenAI Codex CLI. Instead, we port the core domain workflows (`character-asset-spec`, `sprite-qa-audit`, `godot-unity-export-check`, `pixel-region-edit`) into standard, self-contained Agent Skills under `.agents/skills/<skill-name>/SKILL.md` paired with root `AGENTS.md` instructions.

---

## 4. Inventory of Overlapping Functions & Deduplication Decisions

To uphold the architectural principle **"Do not create multiple competing pipelines that perform the same operation"**, every overlapping capability across the three upstreams has a single designated owner in Character Forge Studio:

| Capability Area | `agent-sprite-forge` | `sprite-gen` | `Claude-Code-Game-Studios` | **Selected Canonical Owner in Character Forge Studio** |
|---|---|---|---|---|
| **Core RGBA I/O, Alpha Hygiene & Anchor Math** | `shared/forge_core.py` (`load_rgba`, `save_png`, `anchor_point`, `clean_alpha`) | `sprite_gen/frames/alpha_floor.py`, `curate/anchor.py` | N/A | **`agent-sprite-forge` (`forge_core.py`)** via `packages/forge_adapter/` |
| **Godot 4 Export (`.tres` / `.tscn` / Atlas PNG)** | `skills/generate2dsprite/scripts/export_engine.py` (`godot-spriteframes`, `godot-sprite3d` + round-trip parser verification) | None (exports Aseprite JSON / generic manifest only) | `.claude/agents/godot-specialist.md` (conventions & smoke test command) | **`agent-sprite-forge` (`export_engine.py`)** wrapped by `packages/exporters/godot4.py` + `godot --headless` smoke test |
| **Aseprite JSON Export** | `export_engine.py` (`--target aseprite-json`) | `sprite_gen/compose/export_aseprite.py` | N/A | **`agent-sprite-forge` (`export_engine.py`)** (single unified engine exporter) |
| **Edit Locality & Pixel Preservation QA** | `skills/generate2dmap/scripts/edit_locality_check.py` | `sprite_gen/video/restoration.py` (cell-level loop repair) | N/A | **`agent-sprite-forge` (`edit_locality_check.py` concepts)** + Studio strict pixel-preservation mask check |
| **Cutout Rigging & Bone Animation** | `skills/codeart2d/scripts/rig_animate.py` | None | N/A | **`agent-sprite-forge` (`rig_animate.py`)** |
| **Frame Extraction & Row Segmentation** | `assemble_frames.py` (grid/guide based) | `sprite_gen/frames/extract.py` + `segment.py` (DP projection profile + YCbCr matting) | N/A | **`sprite-gen` (`extract.py` / `segment.py` / `cutout.py`)** for irregular strip segmentation & uniform background cutout; native Pillow GIF frame extractor in `packages/character_core/` for multi-frame GIF uploads |
| **Non-Destructive Frame Curation & Procedural Secondary Motion** | None | `sprite_gen/curate/curation.py`, `effects/breathe.py`, `effects/recolor.py`, `effects/shadow.py`, `video/sway.py` | N/A | **`sprite-gen`** via `packages/sprite_gen_adapter/` |
| **Quantitative Motion/Defect Scoring & Handedness Check** | `sheet_qc.py`, `validate_animation.py` (gate checks) | `sprite_gen/qa/inspect.py`, `score.py`, `motion.py`, `handed.py` | `.claude/skills/asset-audit`, `smoke-check` (evidence-based `NOT ASSESSED` vs `PASS`/`FAIL` discipline) | **Combined complementary pipeline**: `agent-sprite-forge` for seam/export round-trip gates + `sprite-gen` for motion/handedness scoring + `CCGS` evidence-based QA reporting |
| **Paid AI Provider Routing & Budget Guard** | `skills/generate2dmedia/scripts/media_ledger.py` & `route_media.py` | `sprite_gen/gen/*` (direct provider calls) | `asset-spec` (prompt-only until user approval) | **Studio Budget Gate (`packages/agent_bridge/budget_gate.py`)** modeled on `agent-sprite-forge` `media_ledger.py` + `CCGS` explicit approval gate (`sprite-gen` direct paid API calls are disabled by default) |
| **Localhost Visual Studio UI** | None (CLI only) | `serve_curation.py` / `serve_compose.py` (narrow run-folder tools) | None | **Character Forge Studio (`apps/studio_api` + `apps/studio_web`)** — single unified FastAPI + Vanilla JS visual studio |

---

## 5. Adapter Boundary Design

To guarantee that vendor code in `vendor/` is never overwritten or monkey-patched, Character Forge Studio isolates upstream invocations behind two explicit adapter packages:

1. **`packages/forge_adapter/` (`AgentSpriteForgeAdapter`)**:
   - Resolves `vendor/agent-sprite-forge/shared` and `vendor/agent-sprite-forge/skills/*/scripts` paths from `vendor/VENDOR_LOCK.json`.
   - Exposes clean Python dataclasses and methods for:
     - Canonical RGBA inspection, alpha hygiene, anchor computation, and edge-seam metrics (`forge_core`).
     - Building `generate2dsprite.animation_clips.v2` manifests from project frames and durations.
     - Invoking `export_engine.py` in isolated staging directories to produce verified Godot 4 `.tres` (`SpriteFrames`), `.tscn` (`AnimatedSprite2D`), and atlas PNG bundles.
     - Running edit locality verification (`edit_locality_check`) comparing a source frame against an edited frame outside a selected bounding box `(x, y, w, h)`.
2. **`packages/sprite_gen_adapter/` (`SpriteGenAdapter`)**:
   - Resolves `vendor/sprite-gen` from `vendor/VENDOR_LOCK.json`.
   - Exposes clean, non-networked curation and processing utilities:
     - Uniform background cutout (`sprite_gen.frames.cutout`), pixel pitch estimation (`estimate_pixel_grid_runlen`), palette extraction (`recolor`), and motion/frame inspection (`sprite_gen.qa.motion`).
     - Explicitly blocks `sprite_gen.gen.*` paid network calls unless routed through the Studio Budget Gate with an approved budget.

---

## 6. Claude Code Game Studios Skills Ported to `.agents/skills/`

The following skills and specialist conventions from `vendor/Claude-Code-Game-Studios/.claude/` have been selected and adapted to the shared Antigravity/Codex Agent Skills standard (`.agents/skills/*/SKILL.md`):

1. **`.agents/skills/character-asset-spec/SKILL.md`** *(ported from `.claude/skills/asset-spec/SKILL.md` + `.claude/skills/art-bible/SKILL.md` + `.claude/agents/art-director.md` & `technical-artist.md`)*:
   - Defines character visual profiles, dimensions, palette anchors, anatomy profiles, and engine budgets without Claude-specific bash hooks.
2. **`.agents/skills/pixel-region-edit/SKILL.md`** *(combining `agent-sprite-forge` locality checks + Studio selection job JSON protocol)*:
   - Guides Antigravity and Codex agents in executing structured JSON selection-edit jobs (`selection_box` in source image pixel coordinates, target frame index, natural-language instruction) while enforcing zero pixel mutations outside the selected region and committing a new undoable project version.
3. **`.agents/skills/godot-unity-export-qa/SKILL.md`** *(ported from `.claude/skills/asset-audit/SKILL.md` + `.claude/skills/smoke-check/SKILL.md` + `.claude/agents/godot-specialist.md` & `unity-specialist.md`)*:
   - Enforces evidence-based export verification (`COMPLIANT` / `NOT ASSESSED` / `BLOCKED` / `NON-COMPLIANT`), round-trip `.tres`/`.tscn` verification, and headless Godot 4 import smoke testing.
