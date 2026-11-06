"""FastAPI backend for Character Forge Studio."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from apps.studio_api.streaming import EventHub
from packages.agent_bridge import EditJobManager, get_budget_gate
from packages.character_core.coords import (
    canvas_point_to_source_pixel,
    canvas_rect_to_source_box,
)
from packages.exporters import export_godot4_bundle, write_character_manifest
from packages.project_store import ProjectStore
from packages.qa_gate.godot_smoke import find_godot_binary

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "apps" / "studio_web" / "static"
VENDOR_LOCK_PATH = REPO_ROOT / "vendor" / "VENDOR_LOCK.json"


class PointMapRequest(BaseModel):
    canvas_x: float
    canvas_y: float
    pan_x: float = 0.0
    pan_y: float = 0.0
    zoom: float = 1.0
    image_width: int
    image_height: int


class RectMapRequest(BaseModel):
    canvas_x1: float
    canvas_y1: float
    canvas_x2: float
    canvas_y2: float
    pan_x: float = 0.0
    pan_y: float = 0.0
    zoom: float = 1.0
    image_width: int
    image_height: int


class SelectionBoxModel(BaseModel):
    x: int
    y: int
    w: int
    h: int


class CreateEditJobRequest(BaseModel):
    frame_index: int = Field(ge=0)
    selection_box: SelectionBoxModel
    instruction: str = Field(min_length=1)
    operation: str = "auto"
    color_hex: str | None = None
    apply_immediately: bool = True


class RollbackRequest(BaseModel):
    target_version_id: str
    reason: str = "User rollback from Studio UI"


class TimelineUpdateRequest(BaseModel):
    fps: float | None = None
    frame_durations_ms: list[int] | None = None
    loop: bool | None = None
    default_clip: str | None = None


class GodotExportRequest(BaseModel):
    version_id: str | None = None
    run_smoke_test: bool = True


def create_app(workspace_dir: str | Path | None = None) -> FastAPI:
    app = FastAPI(
        title="Character Forge Studio API",
        version="0.1.0",
        description="Localhost visual studio for creating, previewing, editing, rigging, and exporting 2D/Pixel Art characters.",
    )

    store = ProjectStore(workspace_dir=workspace_dir)
    event_hub = EventHub()
    budget_gate = get_budget_gate()

    def _on_job_event(project_id: str, event: dict[str, Any]) -> None:
        event_hub.publish(project_id, event)

    job_manager = EditJobManager(store=store, event_callback=_on_job_event)

    app.state.store = store
    app.state.event_hub = event_hub
    app.state.job_manager = job_manager
    app.state.budget_gate = budget_gate

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def serve_index() -> HTMLResponse:
        index_file = STATIC_DIR / "index.html"
        if not index_file.is_file():
            raise HTTPException(status_code=404, detail="Studio UI index.html not found")
        return HTMLResponse(index_file.read_text(encoding="utf-8"))

    @app.get("/api/health")
    def health_check() -> dict[str, Any]:
        vendor_lock = {}
        if VENDOR_LOCK_PATH.is_file():
            vendor_lock = json.loads(VENDOR_LOCK_PATH.read_text(encoding="utf-8"))
        godot_bin = find_godot_binary()
        return {
            "status": "ok",
            "studio": "Character Forge Studio",
            "version": "0.1.0",
            "workspace_dir": str(store.workspace_dir),
            "godot4_available": godot_bin is not None,
            "godot4_binary": godot_bin,
            "budget_gate": budget_gate.status(),
            "vendor_lock": vendor_lock.get("repositories", []),
        }

    @app.get("/api/projects")
    def list_projects() -> dict[str, Any]:
        return {"projects": store.list_projects()}

    @app.post("/api/projects/upload")
    async def upload_project(
        file: UploadFile = File(...),
        name: str | None = Form(None),
        clip_name: str = Form("idle"),
    ) -> dict[str, Any]:
        raw_bytes = await file.read()
        try:
            project = store.create_project(
                filename=file.filename or "sprite.png",
                raw_bytes=raw_bytes,
                name=name,
                clip_name=clip_name,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        event_hub.publish(
            project["project_id"],
            {
                "timestamp": project["created_at"],
                "type": "project.created",
                "project_id": project["project_id"],
                "version_id": project["current_version_id"],
                "frame_count": project["frame_count"],
                "original_sha256": project["original_file"]["sha256"],
            },
        )
        return project

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        try:
            return store.load_project(project_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/timeline")
    def update_timeline(project_id: str, req: TimelineUpdateRequest) -> dict[str, Any]:
        try:
            updated = store.update_timeline_settings(
                project_id,
                fps=req.fps,
                frame_durations_ms=req.frame_durations_ms,
                loop=req.loop,
                default_clip=req.default_clip,
            )
            event_hub.publish(
                project_id,
                {
                    "timestamp": updated["updated_at"],
                    "type": "timeline.updated",
                    "project_id": project_id,
                    "fps": updated["fps"],
                    "total_duration_ms": updated["total_duration_ms"],
                    "loop": updated["loop"],
                },
            )
            return updated
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/original")
    def download_original_asset(project_id: str) -> FileResponse:
        try:
            proj = store.load_project(project_id)
            orig_path = store.project_dir(project_id) / proj["original_file"]["relative_path"]
            return FileResponse(orig_path, filename=proj["original_file"]["filename"])
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/frames/{frame_index}/image")
    def get_frame_image(
        project_id: str,
        frame_index: int,
        version_id: str | None = Query(None),
    ) -> FileResponse:
        try:
            fpath = store.get_frame_path(project_id, frame_index, version_id=version_id)
            return FileResponse(
                fpath,
                media_type="image/png",
                headers={"Cache-Control": "no-store, max-age=0"},
            )
        except (FileNotFoundError, IndexError, KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/frames/{frame_index}/pixel")
    def inspect_frame_pixel(
        project_id: str,
        frame_index: int,
        x: int = Query(..., ge=0),
        y: int = Query(..., ge=0),
        version_id: str | None = Query(None),
    ) -> dict[str, Any]:
        try:
            return store.inspect_frame_pixel(project_id, frame_index, x, y, version_id=version_id)
        except (FileNotFoundError, IndexError, KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/coords/map-point")
    def api_map_point(req: PointMapRequest) -> dict[str, Any]:
        try:
            return canvas_point_to_source_pixel(
                req.canvas_x,
                req.canvas_y,
                req.pan_x,
                req.pan_y,
                req.zoom,
                req.image_width,
                req.image_height,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/coords/map-rect")
    def api_map_rect(req: RectMapRequest) -> dict[str, Any]:
        try:
            return canvas_rect_to_source_box(
                req.canvas_x1,
                req.canvas_y1,
                req.canvas_x2,
                req.canvas_y2,
                req.pan_x,
                req.pan_y,
                req.zoom,
                req.image_width,
                req.image_height,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/jobs")
    def create_edit_job(project_id: str, req: CreateEditJobRequest) -> dict[str, Any]:
        try:
            job_doc = job_manager.create_and_run_edit_job(
                project_id,
                frame_index=req.frame_index,
                selection_box=req.selection_box.model_dump(),
                instruction=req.instruction,
                operation=req.operation,
                color_hex=req.color_hex,
                apply_immediately=req.apply_immediately,
            )
            project = store.load_project(project_id)
            return {"job": job_doc, "project": project}
        except (FileNotFoundError, IndexError, KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/jobs")
    def list_edit_jobs(project_id: str) -> dict[str, Any]:
        try:
            return {"jobs": job_manager.list_jobs(project_id)}
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/jobs/{job_id}")
    def get_edit_job(project_id: str, job_id: str) -> dict[str, Any]:
        try:
            return job_manager.get_job(project_id, job_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/jobs/{job_id}/artifact/{kind}")
    def get_job_artifact(project_id: str, job_id: str, kind: str) -> FileResponse:
        if kind not in ("patch_before", "patch_after", "locality_diff"):
            raise HTTPException(status_code=400, detail=f"Unknown artifact kind {kind!r}")
        try:
            job = job_manager.get_job(project_id, job_id)
            rel = job.get("artifacts", {}).get(kind)
            if not rel:
                raise HTTPException(status_code=404, detail=f"Artifact {kind} not available for job {job_id}")
            fpath = store.project_dir(project_id) / rel
            if not fpath.is_file():
                raise HTTPException(status_code=404, detail=f"Artifact file missing: {rel}")
            return FileResponse(fpath, media_type="image/png")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/versions")
    def list_versions(project_id: str) -> dict[str, Any]:
        try:
            proj = store.load_project(project_id)
            return {
                "project_id": project_id,
                "current_version_id": proj["current_version_id"],
                "original_integrity": proj["original_integrity"],
                "versions": proj["versions"],
                "rollback_history": proj.get("rollback_history", []),
            }
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/rollback")
    def rollback_version(project_id: str, req: RollbackRequest) -> dict[str, Any]:
        try:
            result = store.rollback_to_version(
                project_id,
                req.target_version_id,
                reason=req.reason,
            )
            event_hub.publish(
                project_id,
                {
                    "timestamp": result["rollback_entry"]["timestamp"],
                    "type": "project.rolled_back",
                    "project_id": project_id,
                    "from_version_id": result["previous_version_id"],
                    "to_version_id": result["current_version_id"],
                    "reason": req.reason,
                },
            )
            project = store.load_project(project_id)
            return {"rollback": result, "project": project}
        except (FileNotFoundError, KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/export/manifest")
    def export_manifest_endpoint(project_id: str, version_id: str | None = Query(None)) -> dict[str, Any]:
        try:
            res = write_character_manifest(store, project_id, version_id=version_id)
            event_hub.publish(
                project_id,
                {
                    "timestamp": res["manifest"]["generated_at"],
                    "type": "export.manifest.completed",
                    "project_id": project_id,
                    "version_id": res["manifest"]["version_id"],
                    "relative_path": res["relative_path"],
                },
            )
            return res
        except (FileNotFoundError, KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/export/godot4")
    def export_godot4_endpoint(project_id: str, req: GodotExportRequest | None = None) -> dict[str, Any]:
        opts = req or GodotExportRequest()
        try:
            res = export_godot4_bundle(
                store,
                project_id,
                version_id=opts.version_id,
                run_smoke_test=opts.run_smoke_test,
            )
            smoke_status = (res.get("godot_smoke_test") or {}).get("status", "not_run")
            event_hub.publish(
                project_id,
                {
                    "timestamp": res["character_manifest"]["generated_at"],
                    "type": "export.godot4.completed",
                    "project_id": project_id,
                    "version_id": res["version_id"],
                    "export_id": res["export_id"],
                    "godot_bundle_dir": res["godot_bundle_dir"],
                    "smoke_test_status": smoke_status,
                },
            )
            return res
        except (FileNotFoundError, KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/events")
    async def project_events_sse(
        project_id: str,
        once: bool = Query(False, description="If true, replay current event log once and close (for tests/CLI)."),
    ) -> StreamingResponse:
        return StreamingResponse(
            event_hub.sse_stream(project_id, replay_history=True, once=once),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.websocket("/ws/projects/{project_id}")
    async def project_events_ws(websocket: WebSocket, project_id: str) -> None:
        await websocket.accept()
        q = event_hub.subscribe(project_id)
        try:
            for past_event in event_hub.get_history(project_id):
                await websocket.send_json(past_event)
            while True:
                event = await q.get()
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            event_hub.unsubscribe(project_id, q)

    return app


app = create_app()
