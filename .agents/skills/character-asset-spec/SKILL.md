---
name: character-asset-spec
description: Create engine-ready 2D/Pixel Art character specifications, anatomy profiles, palette constraints, and animation state budgets for Godot 4 and Unity. Ported from Claude Code Game Studios (asset-spec + art-bible) for Antigravity CLI and Codex CLI.
---

# Character Asset Spec Skill (`character-asset-spec`)

Use this skill when defining a new character profile or validating an uploaded sprite's target specifications before editing or exporting.

## Workflow

1. **Inspect Existing Project or Input Asset**:
   - Read the character project's `project.json` and `manifest.json` (via `packages/exporters/manifest.py`) if a project already exists.
   - Measure actual frame dimensions `(width, height)`, frame count, frame durations (`ms`), and opaque subject bounding box (`forge_core`).
2. **Assign Anatomy & Direction Profile**:
   - `anatomy_profile`: `humanoid_biped` | `quadruped_digitigrade` | `winged_biped_or_avian`.
   - `directions`: `1-way (side/front)` | `4-way (S, W, N, E)` | `8-way (S, SW, W, NW, N, NE, E, SE)`.
   - `anchor_mode`: `feet` (default for grounded characters) | `center` (for flying/floating entities).
3. **Engine Target Standards**:
   - **Godot 4**: `AnimatedSprite2D` + `SpriteFrames` (`.tres`), `texture_filter = 1` (`TEXTURE_FILTER_NEAREST`), `centered = false`, `offset = Vector2(-anchor_x, -anchor_y)`.
   - **Unity**: `TextureImporter` (`spriteMode = 2`, `filterMode = 0` Point, `textureCompression = 0` Uncompressed, custom pivot normalized from `anchor_px`).
4. **Budget Guard**:
   - Never trigger external paid AI image/video generation from a spec unless the user has explicitly enabled `BudgetGate` and approved the call.
