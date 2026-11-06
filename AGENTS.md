# AGENTS.md — Character Forge Studio Instructions for Antigravity CLI & Codex CLI

This repository is **Character Forge Studio**, a modular Python-first monorepo for creating, inspecting, editing, rigging, and exporting 2D/Pixel Art characters for **Godot 4** and **Unity**.

These instructions apply equally to **Google Antigravity CLI** and **OpenAI Codex CLI**. Do **not** assume Claude Code hooks (`.claude/hooks/`) or proprietary subagent macros run natively.

---

## 1. Non-Negotiable Architectural Rules

1. **Never Modify Source Assets Destructively**:
   - Uploaded assets in `workspace/projects/<project_id>/original/` are strictly read-only after creation.
   - Always verify `original_sha256` before and after any frame edit, version commit, or rollback.
2. **Never Modify Upstream Vendor Files**:
   - `vendor/agent-sprite-forge`, `vendor/sprite-gen`, and `vendor/Claude-Code-Game-Studios` are pinned read-only in `vendor/VENDOR_LOCK.json`.
   - All calls into upstream engines must go through `packages/forge_adapter/` or `packages/sprite_gen_adapter/`.
3. **Single Canonical Pipeline per Operation**:
   - See `docs/architecture/INTEGRATION_MATRIX.md`.
   - Use `agent-sprite-forge` for RGBA core math, anchors, edit locality checks, cutout rigging, and Godot 4 / Aseprite export.
   - Use `sprite-gen` for strip segmentation, uniform background cutout, curation sidecars, and secondary motion/scoring utilities.
4. **No Unapproved Paid AI API Calls**:
   - Never invoke external paid image/video APIs (`OpenAI`, `xAI/Grok`, `Anthropic`, `Fal`, `Gemini`, `BytePlus`) unless `packages/agent_bridge/budget_gate.py` has an explicitly configured budget (`enabled=True`, `max_usd_per_job > 0`) and an explicit user approval token.
5. **Strict Pixel-Preservation for Selection Edits**:
   - When executing an edit job (`character-forge.edit_job.v1`) with `selection_box = {x, y, w, h}`, zero pixels outside `[x, x+w) x [y, y+h)` may change (`outside_changed_pixels == 0`).
6. **Windows CMD Compatibility**:
   - All CLI commands and launch scripts (`run-studio.bat`) must work in standard Windows `cmd.exe` without requiring PowerShell-only modules, npm, or React build pipelines.

---

## 2. Shared Agent Skills (`.agents/skills/`)

Both Antigravity CLI and Codex CLI can read the portable skills in `.agents/skills/`:
- [`.agents/skills/character-asset-spec/SKILL.md`](.agents/skills/character-asset-spec/SKILL.md): Define character visual profiles, anatomy archetypes, dimensions, and engine budgets.
- [`.agents/skills/pixel-region-edit/SKILL.md`](.agents/skills/pixel-region-edit/SKILL.md): Inspect and execute structured JSON selection-edit jobs with strict outside-box pixel preservation and version history commits.
- [`.agents/skills/godot-unity-export-qa/SKILL.md`](.agents/skills/godot-unity-export-qa/SKILL.md): Export character animations to Engine-Independent Manifest and Godot 4 (`SpriteFrames` `.tres` + `.tscn`) and run evidence-based headless QA smoke checks.

---

## 3. Common Commands

- **Launch Studio (Windows CMD)**:
  ```cmd
  run-studio.bat
  ```
- **Launch Studio (Linux / macOS / Direct Python)**:
  ```bash
  python -m uvicorn apps.studio_api.main:app --host 127.0.0.1 --port 8000
  ```
- **Run Full Automated Test Suite**:
  ```bash
  python -m pytest -v
  ```
