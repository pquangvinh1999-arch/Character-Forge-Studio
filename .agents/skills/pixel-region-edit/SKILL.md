---
name: pixel-region-edit
description: Execute structured JSON region-selection edit jobs on a character frame while guaranteeing zero pixel changes outside the selected source-image bounding box and recording an undoable version snapshot.
---

# Pixel Region Edit Skill (`pixel-region-edit`)

Use this skill when processing a saved selection edit job (`workspace/projects/<project_id>/jobs/<job_id>.json`) created from the Character Forge Studio canvas.

## Contract & Invariants

1. **Read the Structured Edit Job (`character-forge.edit_job.v1`)**:
   - `project_id`: Target project identifier.
   - `base_version_id`: Version snapshot (`vXXXX`) the selection was made against.
   - `frame_index`: 0-based index of the target frame.
   - `selection_box`: `{"x": int, "y": int, "w": int, "h": int}` in **source-image pixel coordinates** (already mapped from canvas zoom/pan).
   - `instruction`: Natural-language edit instruction from the user.
2. **Non-Destructive Execution**:
   - Never modify `workspace/projects/<project_id>/original/*`.
   - Never overwrite frames inside `versions/<base_version_id>/`.
   - Apply pixel edits strictly within `[x, x + w) x [y, y + h)` of the target frame.
3. **Mandatory Locality Verification**:
   - Run `packages/qa_gate/locality.py` (`verify_edit_locality`) comparing the base frame and edited frame.
   - Verify `outside_changed_pixels == 0` and `outside_max_abs_diff == 0`.
   - Commit the result as a new version snapshot (`vYYYY`) via `packages/project_store/store.py`.
