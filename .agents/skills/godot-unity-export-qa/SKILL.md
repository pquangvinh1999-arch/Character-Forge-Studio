---
name: godot-unity-export-qa
description: Export character animations to the engine-independent Character Manifest and Godot 4 SpriteFrames (.tres/.tscn), and produce an evidence-based QA report (COMPLIANT / WARNINGS / NOT ASSESSED / NON-COMPLIANT) with headless Godot 4 smoke verification.
---

# Godot 4 & Unity Export QA Skill (`godot-unity-export-qa`)

Ported from `Claude-Code-Game-Studios` (`asset-audit` + `smoke-check`) and `agent-sprite-forge` (`export_engine.py`).

## Core Rules (No Fabricated Verdicts)

1. **Evidence-Only Reporting**:
   - Every check in the QA report must be backed by a real measurement (SHA-256 digest, pixel diff count, parsed `.tres`/`.tscn` section count, or `godot --headless` exit code).
   - If the `godot` binary is unavailable on the host machine, the Godot headless import check MUST be marked `BLOCKED` (`godot_binary_available: false`), never faked as passed.
2. **Verification Steps**:
   - Verify original asset SHA-256 matches `project.json` (`original_sha256`).
   - Generate `manifest.json` (`character-forge.manifest.v1`).
   - Run `packages/exporters/godot4.py` (`export_godot4_bundle`), which delegates to `agent-sprite-forge`'s `export_engine.py --target godot-spriteframes` and runs round-trip `.tres`/`.tscn` + RGBA pixel verification.
   - Run `packages/qa_gate/godot_smoke.py` (`run_godot_import_smoke_test`) which executes `godot --headless --path <export_dir> --quit` and a GDScript resource validation script to confirm Godot 4 loads the exported `SpriteFrames` and `AnimatedSprite2D` scene cleanly.
