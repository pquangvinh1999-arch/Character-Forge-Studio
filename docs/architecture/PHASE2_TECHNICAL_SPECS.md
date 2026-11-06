# Phase 2 — Detailed Technical Specifications (`PHASE2_TECHNICAL_SPECS.md`)

> **Status**: **Design Specification Only (Phase 2)** — Per project governance, Phase 2 modules are specified here in full architectural detail and must **not** be implemented prior to Phase 1 MVP acceptance.

---

## 2.1 AI Image-to-Animation Integration Specification

### Objective
Enable opt-in, budget-controlled AI still-to-animation and video-to-sprite generation without destructive asset mutation or unapproved API billing.

### Pipeline Architecture
1. **Budget & Approval Gate (`packages/agent_bridge/budget_gate.py`)**:
   - Reads `workspace/config/budget.json` (`enabled: bool`, `max_usd_per_job: float`, `max_usd_session: float`, `approved_providers: list[str]`).
   - Any paid provider call (`openai`, `xai`/`grok`, `anthropic`, `fal`, `gemini`, `byteplus`) requires an explicit user approval token (`approval_id`) signed per job and logged in `media-ledger.jsonl` (compatible with `agent-sprite-forge/skills/generate2dmedia/scripts/media_ledger.py`).
2. **Stage 1 — Input Preparation (`prepare_i2v_input.py`)**:
   - Pads the approved master character still onto a chroma-safe motion canvas (`magenta #FF00FF`, `green #00FF00`, or `blue #0000FF` selected orthogonal to the character's palette) with state-dependent headroom (tall for `jump`, wide for `attack`, square for `idle`/`walk`).
3. **Stage 2 — Video / Frame Sequence Generation (`route_media.py`)**:
   - Routes the prepared plate + motion prompt to the approved provider or local offline generator.
4. **Stage 3 — Chroma Matting, Loop Extraction & Registration**:
   - `forge_matte.py`: Keys out the background with border flood fill and spill suppression.
   - `gait_loop.py` / `sprite_gen.video.loop`: Finds the true periodic cycle and optimal seam cut.
   - `register_clip.py`: Registers every frame to a stable feet/stance anchor (`anchor_mode="feet"` or `"stance"`).
   - `colour_lock.py` & `finish_frames.py`: Locks frame colours back to the master still's quantized palette and snaps pixel boundaries.

---

## 2.2 4/8 Directional Character Generation Specification

### Compass Convention
Follows `sprite-gen` (`video_set_sheet.py`) and `agent-sprite-forge` (`sprite.schema.json`) compass ordering:
- **4-Direction Set**: `["S", "W", "N", "E"]` (or `["down", "left", "up", "right"]` mapped 1:1).
- **8-Direction Set**: `["S", "SW", "W", "NW", "N", "NE", "E", "SE"]`.

### Cross-Direction Invariants
1. **Master Anchor Lock**: All directions share a single `cell_size: [W, H]` and a single `baseline_y` (ground contact line in source pixels).
2. **Standing Height Parity**: Subject bounding-box height across all 4/8 directions in `idle` frame 0 must remain within $\pm 1\text{ px}$ of `reference_subject_height_px`.
3. **Handedness & Asymmetric Prop Verification**:
   - Ported from `vendor/sprite-gen/sprite_gen/qa/handed.py`.
   - Tracks colour-marked asymmetric features (e.g., shield in left hand, sword in right hand, pauldron on left shoulder) across compass turns to reject naive horizontal-flip errors when asymmetric mode is enabled.

---

## 2.3 Humanoid, Quadruped & Winged-Character Anatomy Profiles

### Schema (`character-forge.anatomy_profile.v1`)
```json
{
  "schema": "character-forge.anatomy_profile.v1",
  "profile_id": "humanoid_biped | quadruped_digitigrade | winged_biped_or_avian",
  "root_bone": "pelvis",
  "ground_line_y": 60,
  "bones": [
    {"id": "pelvis", "parent": null, "pivot": [32, 36]},
    {"id": "torso", "parent": "pelvis", "pivot": [32, 34]},
    {"id": "head", "parent": "torso", "pivot": [32, 22]}
  ],
  "ik_chains": [
    {"id": "leg_l", "upper": "thigh_l", "lower": "shin_l", "effector": "foot_l", "ground_clamp": true},
    {"id": "leg_r", "upper": "thigh_r", "lower": "shin_r", "effector": "foot_r", "ground_clamp": true}
  ],
  "gait_Generator": {
    "contact_groups": [
      {"group": "pair_a", "effectors": ["foot_l"], "phase_offset": 0.0},
      {"group": "pair_b", "effectors": ["foot_r"], "phase_offset": 0.5}
    ]
  }
}
```

### Built-In Archetype Templates
1. **`humanoid_biped`**:
   - 12-bone hierarchy (`pelvis`, `torso`, `head`, `upper_arm_l/r`, `forearm_l/r`, `hand_l/r`, `thigh_l/r`, `shin_l/r`, `foot_l/r`).
   - 2 two-bone ground-clamped IK chains (`leg_l`, `leg_r`) with $\Delta \phi = 0.5$ opposing phase walk/run cycles and counter-swinging arms.
2. **`quadruped_digitigrade`**:
   - 16-bone hierarchy (`pelvis`, `spine_mid`, `chest`, `neck`, `head`, `tail_1..3`, `front_upper_l/r`, `front_lower_l/r`, `front_paw_l/r`, `hind_upper_l/r`, `hind_lower_l/r`, `hind_paw_l/r`).
   - 4 two-bone ground-clamped IK chains supporting walk ($0.0, 0.25, 0.5, 0.75$ phase offsets), trot (diagonal pairs $0.0, 0.5$), and gallop (bound phase offsets with spine flexion).
3. **`winged_biped_or_avian`**:
   - Extends `humanoid_biped` or avian root with `wing_shoulder_l/r`, `wing_mid_l/r`, `wing_tip_l/r` chains.
   - Supports coupled vertical root bob $\Delta y(t) = -A \sin(2\pi t - \phi_{\text{lag}})$ synchronized with downstroke impulse and `sprite-gen` `video-sway` secondary feather follow-through.

---

## 2.4 Cutout Rigging & Pixel-Safe Sprite Swapping

### Foundation
Directly leverages `vendor/agent-sprite-forge/skills/codeart2d/scripts/rig_animate.py` (`rig.v1` SVG + `codeart2d.rig_anim.v1`).

### Technical Contract
- **Rig Structure**:
  - Root `<svg data-codeart="rig.v1" data-anchor="X Y" data-ground="Y" data-outline="#rrggbb">`.
  - Bones `<g id="BONE_NAME" data-pivot="X Y">` nested parent-to-child.
  - Slots inside bones carry `data-z="INT"` (global draw order independent of parent tree) and `data-variant="VARIANT_NAME"` (for sprite swapping such as open/closed eyes, open/fist/weapon hands, or damaged armor states).
- **Pixel-Safe Rendering (Route D)**:
  - Rather than naive bilinear rotation of low-res pixel sprites (which causes Mixels and blurry alpha fringes), Route D (`codeart_core.pixel_finish`) renders each slot at $8\times$ supersampled coverage, resolves Z-order and bone seam inner lines, applies optional palette ramp shading, and draws a deterministic 1px outer silhouette outline last.
  - Enforces strict pixel gates: `0` partial-alpha pixels, `0` off-palette colours, `0` outline gaps, and $\le 10$ L-corners per frame.

---

## 2.5 Bone, Pivot, Mesh & Animation Keyframe Editors

### Interactive Canvas Gizmo Layer
- **Bone & Pivot Mode**:
  - Renders bone hierarchy overlay on the Studio HTML5 canvas (`apps/studio_web`).
  - Dragging a pivot handle updates `data-pivot="X Y"` in source pixel coordinates using `canvas_to_source_pixel()`.
  - Hierarchical world matrix evaluation:
    $$M_{\text{world}} = M_{\text{parent}} \cdot T(d_x, d_y) \cdot T(p_x, p_y) \cdot R(\theta) \cdot S(s_x, s_y) \cdot T(-p_x, -p_y)$$
- **2D Mesh Deformation Layer**:
  - Optional triangulated grid over a slot region with barycentric vertex weights $w_{v,b}$ bound to up to 2 bones, quantized back to the nearest integer pixel grid and locked palette after deformation.
- **Keyframe Dopesheet & Curve Editor**:
  - Normalized timeline $t \in [0, 1)$ for looping clips ($t_i = i / N$) and $t \in [0, 1]$ for one-shot clips ($t_i = i / (N - 1)$).
  - Supports track types `rotate`, `translate`, `scale`, `show`, and `swap`, with easing functions `linear`, `sine`, `in`, `out`, `step`, `cubic-bezier(a,b,c,d)`, and `spring(k,d)`.

---

## 2.6 Separate VFX Timelines & Attachment Anchors

### Motivation
Character body animations (e.g., 6-frame sword swing at 10 FPS) often require higher-frequency or longer-living VFX (e.g., 12-frame slash arc or lingering smoke puff at 24 FPS) that must not bloat the character's core bounding box or distort its feet anchor.

### Schema (`character-forge.vfx_timeline.v1`)
```json
{
  "schema": "character-forge.vfx_timeline.v1",
  "character_clip": "attack_slash",
  "anchors_per_frame": [
    {"frame": 0, "sockets": {"weapon_tip": [48, 20], "hand_r": [38, 30], "feet_dust": [30, 60]}},
    {"frame": 1, "sockets": {"weapon_tip": [56, 34], "hand_r": [42, 32], "feet_dust": [30, 60]}}
  ],
  "vfx_tracks": [
    {
      "track_id": "slash_arc",
      "attach_socket": "weapon_tip",
      "space": "local_attached | world_spawned_at_trigger",
      "trigger_ms": 80,
      "fps": 24,
      "z_layer": "foreground",
      "blend_mode": "add | normal",
      "frames": ["vfx/slash_00.png", "vfx/slash_01.png", "vfx/slash_02.png"]
    }
  ]
}
```

---

## 2.7 Visual Selection to Agent Edit-Command Protocol

### Protocol (`character-forge.edit_job.v1` / `.v2`)
When the user selects a region on the canvas and enters a natural-language instruction:
1. The UI maps the canvas selection to exact source-image pixel coordinates `selection_box = {"x": x, "y": y, "w": w, "h": h}` and normalized UV `[u0, v0, u1, v1]`.
2. The backend persists a structured job JSON in `workspace/projects/<project_id>/jobs/<job_id>.json` containing:
   - `project_id`, `base_version_id`, `frame_index` (or `frame_range`)
   - `selection_box` (`x, y, w, h` in source pixels) and optional `mask_png_relpath`
   - `instruction` (natural-language instruction from the user)
   - `source_frame_path` and `cropped_patch_path` (the exact cropped RGBA patch + 4px context ring)
   - `constraints`: `{"preserve_outside_selection": true, "exact_rgba_outside_mask": true, "lock_palette": false}`
3. **Agent Execution Path**:
   - **Local Deterministic / Agent-Assisted Mode**: An agent (Antigravity CLI or Codex CLI) using `.agents/skills/pixel-region-edit/SKILL.md` or the built-in region processor reads `<job_id>.json`, modifies only the pixels inside `selection_box`, validates the result through the Strict Pixel-Preservation gate, commits a new version `vXXXX`, and emits SSE/WebSocket completion events.

---

## 2.8 Strict Pixel-Preservation Editing

### Mathematical Guarantee
Let $I_{\text{before}}, I_{\text{after}} \in \{0, \dots, 255\}^{H \times W \times 4}$ be the 8-bit straight-alpha RGBA arrays of the target frame before and after an edit, and let $B = [x_0, x_0 + w) \times [y_0, y_0 + h)$ be the selected pixel region (or binary mask $M \in \{0, 1\}^{H \times W}$).

The commit gate (`packages/qa_gate/locality.py`) enforces:
1. **Dimension Invariance**: $\text{shape}(I_{\text{after}}) == \text{shape}(I_{\text{before}})$.
2. **Zero Outside Mutation**:
   $$\max_{(y, x) \notin B} \left| I_{\text{after}}(y, x, c) - I_{\text{before}}(y, x, c) \right| = 0 \quad \forall c \in \{R, G, B, A\}$$
3. **Auto-Compositing Guard**: When applying a patch or agent output, the studio composites $I_{\text{final}}(y, x) = M(y, x) \cdot I_{\text{candidate}}(y, x) + (1 - M(y, x)) \cdot I_{\text{before}}(y, x)$ and then verifies the full frame against `I_before` outside $M$ to produce a signed `locality_qa` certificate (`changed_pixels_outside_box == 0`, `changed_pixels_inside_box >= 0`, `original_asset_unchanged == True`).

---

## 2.9 Unity Import/Export Adapter Specification

### Target Output Layout (`exports/unity/<character_name>/`)
1. `<character_name>.png`: Lossless RGBA sprite atlas generated by `agent-sprite-forge` (`export_engine.py --target aseprite-json`).
2. `<character_name>.aseprite.json`: Aseprite JSON metadata with `frameTags` (clips), per-frame `duration` (ms), `slices` (`anchor` pivot), and `events`.
3. `<character_name>.png.meta`: Deterministic Unity `TextureImporter` YAML (following `Claude-Code-Game-Studios/.claude/agents/unity-specialist.md` pixel-art rules):
   - `textureType: 8` (Sprite 2D and UI)
   - `spriteMode: 2` (Multiple)
   - `spritePixelsToUnits: 32` (configurable per project)
   - `filterMode: 0` (Point / no filter)
   - `textureCompression: 0` (Uncompressed RGBA32)
   - `mipMaps.enableMipMap: 0`
   - `spriteSheet.sprites`: Populated with exact rect `[x, H_atlas - y - h, w, h]` (converting top-left image coordinates to Unity bottom-left UV space) and normalized pivot `[anchor_x / w, 1.0 - (anchor_y / h)]` (`alignment: 9` Custom).
4. `<character_name>_manifest.unity.json`: Companion C# `ScriptableObject` / importer payload for automatic `AnimationClip` (`.anim`) and `AnimatorController` (`.controller`) generation inside Unity 2022 LTS / Unity 6.

---

## 2.10 Automated & Visual Animation QA Specification

### Evidence-Based Verdict Enum (Ported from Claude Code Game Studios)
Every QA report (`character-forge.qa_report.v1`) produces one of four overall verdicts—never fabricating passing metrics when a tool or input is absent:
- `COMPLIANT`: All automated gates ran and passed with measured evidence.
- `WARNINGS`: Core gates passed, advisory findings detected (e.g., minor loop seam ratio warning).
- `BLOCKED` / `NOT ASSESSED`: A required external runtime (e.g., Godot binary) was unavailable; the exact missing dependency is recorded.
- `NON-COMPLIANT`: Any hard gate failed (e.g., original asset mutated, pixels outside selection box changed, broken `.tres`/`.tscn` round-trip, or failed Godot headless import).

### Automated QA Gate Suite
1. **Source Integrity Gate**: `sha256(original_file) == project.original_sha256`.
2. **Edit Locality Gate**: `outside_selection_diff_px == 0` (`packages/qa_gate/locality.py` + `agent-sprite-forge` `edit_locality_check.py`).
3. **Alpha & Matte Hygiene Gate**: `forge_core.py` straight-alpha check (RGB zeroed where $A = 0$, detached island check).
4. **Loop Seam & Motion Gate**: `forge_core.edge_seam_report()` + `sprite-gen` `qa/motion.py` contact/timing evidence.
5. **Engine Round-Trip & Headless Import Gate**:
   - `agent-sprite-forge` `export_engine.py` internal round-trip parser check (`verify_godot_spriteframes`, `verify_aseprite`).
   - Real `godot --headless --path <export_dir> --quit` (and GDScript resource load check) verifying that Godot 4 parses and loads the exported `.tres` (`SpriteFrames`) and `.tscn` (`AnimatedSprite2D`) without errors.
