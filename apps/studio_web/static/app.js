/**
 * Character Forge Studio — Vanilla JS Visual Studio Frontend (Phase 1 MVP)
 * Zero frontend build pipeline. Uses exact zoom-invariant source-pixel math.
 */

const state = {
  project: null,
  currentFrameIndex: 0,
  frameImages: {}, // key: `${versionId}:${frameIndex}` -> HTMLImageElement
  isPlaying: false,
  playTimerId: null,
  zoom: 8,
  panX: 40,
  panY: 40,
  toolMode: "select", // "select" | "pan"
  showGrid: true,
  showAnchor: true,
  isDragging: false,
  dragStartCanvas: null,
  selectionBox: null, // {x, y, w, h} in source-image pixel coordinates
  sseSource: null,
  wsSocket: null,
};

const els = {
  uploadInput: document.getElementById("upload-input"),
  projectSelect: document.getElementById("project-select"),
  refreshProjectsBtn: document.getElementById("refresh-projects-btn"),
  healthPill: document.getElementById("health-pill"),
  streamPill: document.getElementById("stream-pill"),
  godotPill: document.getElementById("godot-pill"),
  budgetPill: document.getElementById("budget-pill"),
  modeSelectBtn: document.getElementById("mode-select-btn"),
  modePanBtn: document.getElementById("mode-pan-btn"),
  clearSelectionBtn: document.getElementById("clear-selection-btn"),
  zoomOutBtn: document.getElementById("zoom-out-btn"),
  zoomSelect: document.getElementById("zoom-select"),
  zoomInBtn: document.getElementById("zoom-in-btn"),
  zoomFitBtn: document.getElementById("zoom-fit-btn"),
  gridToggle: document.getElementById("grid-toggle"),
  anchorToggle: document.getElementById("anchor-toggle"),
  canvas: document.getElementById("sprite-canvas"),
  emptyOverlay: document.getElementById("empty-canvas-overlay"),
  hudDimensions: document.getElementById("hud-dimensions"),
  hudCursorXY: document.getElementById("hud-cursor-xy"),
  hudColorSwatch: document.getElementById("hud-color-swatch"),
  hudPixelRGBA: document.getElementById("hud-pixel-rgba"),
  hudSelection: document.getElementById("hud-selection"),
  stepPrevBtn: document.getElementById("step-prev-btn"),
  playPauseBtn: document.getElementById("play-pause-btn"),
  stepNextBtn: document.getElementById("step-next-btn"),
  timelineScrubber: document.getElementById("timeline-scrubber"),
  frameCounterLabel: document.getElementById("frame-counter-label"),
  fpsInput: document.getElementById("fps-input"),
  loopCheckbox: document.getElementById("loop-checkbox"),
  applyFpsBtn: document.getElementById("apply-fps-btn"),
  framesStrip: document.getElementById("frames-strip"),
  activeVersionBadge: document.getElementById("active-version-badge"),
  originalHashBadge: document.getElementById("original-hash-badge"),
  selX: document.getElementById("sel-x"),
  selY: document.getElementById("sel-y"),
  selW: document.getElementById("sel-w"),
  selH: document.getElementById("sel-h"),
  selFrame: document.getElementById("sel-frame"),
  editInstruction: document.getElementById("edit-instruction"),
  editOperation: document.getElementById("edit-operation"),
  editColor: document.getElementById("edit-color"),
  submitJobBtn: document.getElementById("submit-job-btn"),
  jobsList: document.getElementById("jobs-list"),
  versionsList: document.getElementById("versions-list"),
  exportManifestBtn: document.getElementById("export-manifest-btn"),
  exportGodotBtn: document.getElementById("export-godot-btn"),
  inspectorJsonView: document.getElementById("inspector-json-view"),
  eventStreamLog: document.getElementById("event-stream-log"),
};

const ctx = els.canvas.getContext("2d");
const offscreenCanvas = document.createElement("canvas");
const offscreenCtx = offscreenCanvas.getContext("2d", { willReadFrequently: true });

/* -------------------------------------------------------------------------- */
/* Exact Coordinate Mapping (matches packages/character_core/coords.py)       */
/* -------------------------------------------------------------------------- */

function clientToCanvasCoords(clientX, clientY) {
  const rect = els.canvas.getBoundingClientRect();
  const scaleX = els.canvas.width / Math.max(1, rect.width);
  const scaleY = els.canvas.height / Math.max(1, rect.height);
  return {
    x: (clientX - rect.left) * scaleX,
    y: (clientY - rect.top) * scaleY,
  };
}

function canvasPointToSourcePixel(canvasX, canvasY, panX, panY, zoom, imgW, imgH) {
  const rawX = (canvasX - panX) / zoom;
  const rawY = (canvasY - panY) / zoom;
  const px = Math.floor(rawX + 1e-9);
  const py = Math.floor(rawY + 1e-9);
  const inBounds = px >= 0 && px < imgW && py >= 0 && py < imgH;
  const clampedX = Math.max(0, Math.min(imgW - 1, px));
  const clampedY = Math.max(0, Math.min(imgH - 1, py));
  return { x: clampedX, y: clampedY, unclampedX: px, unclampedY: py, inBounds };
}

function canvasRectToSourceBox(cx1, cy1, cx2, cy2, panX, panY, zoom, imgW, imgH) {
  const leftC = Math.min(cx1, cx2);
  const rightC = Math.max(cx1, cx2);
  const topC = Math.min(cy1, cy2);
  const bottomC = Math.max(cy1, cy2);

  const rawX0 = (leftC - panX) / zoom;
  const rawY0 = (topC - panY) / zoom;
  const rawX1 = (rightC - panX) / zoom;
  const rawY1 = (bottomC - panY) / zoom;

  const x0 = Math.max(0, Math.min(imgW - 1, Math.floor(rawX0 + 1e-9)));
  const y0 = Math.max(0, Math.min(imgH - 1, Math.floor(rawY0 + 1e-9)));
  const x1 = Math.max(x0 + 1, Math.min(imgW, Math.floor(rawX1 - 1e-9) + 1));
  const y1 = Math.max(y0 + 1, Math.min(imgH, Math.floor(rawY1 - 1e-9) + 1));

  return {
    x: x0,
    y: y0,
    w: x1 - x0,
    h: y1 - y0,
  };
}

/* -------------------------------------------------------------------------- */
/* Canvas Rendering                                                           */
/* -------------------------------------------------------------------------- */

function drawCheckerboard(x, y, width, height, cellSize = 8) {
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, width, height);
  ctx.clip();

  ctx.fillStyle = "#1c2432";
  ctx.fillRect(x, y, width, height);
  ctx.fillStyle = "#283347";
  for (let row = 0; row * cellSize < height; row++) {
    for (let col = 0; col * cellSize < width; col++) {
      if ((row + col) % 2 === 0) {
        ctx.fillRect(x + col * cellSize, y + row * cellSize, cellSize, cellSize);
      }
    }
  }
  ctx.restore();
}

function getActiveVersionDoc() {
  if (!state.project) return null;
  const vid = state.project.current_version_id;
  return (state.project.versions || []).find((v) => v.version_id === vid) || null;
}

function getCurrentFrameRecord() {
  const vdoc = getActiveVersionDoc();
  if (!vdoc || !vdoc.frames) return null;
  return vdoc.frames[state.currentFrameIndex] || null;
}

function getCurrentFrameImage() {
  if (!state.project) return null;
  const key = `${state.project.current_version_id}:${state.currentFrameIndex}`;
  return state.frameImages[key] || null;
}

function renderCanvas() {
  ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
  if (!state.project) {
    els.emptyOverlay.classList.remove("hidden");
    return;
  }
  els.emptyOverlay.classList.add("hidden");

  const imgW = state.project.width;
  const imgH = state.project.height;
  const drawW = imgW * state.zoom;
  const drawH = imgH * state.zoom;

  drawCheckerboard(state.panX, state.panY, drawW, drawH, Math.max(4, Math.min(16, state.zoom)));

  const frameImg = getCurrentFrameImage();
  if (frameImg && frameImg.complete) {
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(frameImg, state.panX, state.panY, drawW, drawH);
    ctx.restore();
  }

  // Optional 1px source pixel grid when zoomed in >= 4x
  if (state.showGrid && state.zoom >= 4) {
    ctx.save();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = 0; x <= imgW; x++) {
      const cx = Math.round(state.panX + x * state.zoom) + 0.5;
      ctx.moveTo(cx, state.panY);
      ctx.lineTo(cx, state.panY + drawH);
    }
    for (let y = 0; y <= imgH; y++) {
      const cy = Math.round(state.panY + y * state.zoom) + 0.5;
      ctx.moveTo(state.panX, cy);
      ctx.lineTo(state.panX + drawW, cy);
    }
    ctx.stroke();
    ctx.restore();
  }

  // Canvas border around image bounds
  ctx.save();
  ctx.strokeStyle = "#4b6584";
  ctx.lineWidth = 1;
  ctx.strokeRect(state.panX - 0.5, state.panY - 0.5, drawW + 1, drawH + 1);
  ctx.restore();

  // Feet anchor crosshair
  if (state.showAnchor && state.project.anchor_px) {
    const [ax, ay] = state.project.anchor_px;
    const cx = state.panX + ax * state.zoom;
    const cy = state.panY + ay * state.zoom;
    ctx.save();
    ctx.strokeStyle = "#f1c40f";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx - 8, cy);
    ctx.lineTo(cx + 8, cy);
    ctx.moveTo(cx, cy - 8);
    ctx.lineTo(cx, cy + 8);
    ctx.stroke();
    ctx.restore();
  }

  // Active source-pixel selection box
  if (state.selectionBox) {
    const { x, y, w, h } = state.selectionBox;
    const sx = state.panX + x * state.zoom;
    const sy = state.panY + y * state.zoom;
    const sw = w * state.zoom;
    const sh = h * state.zoom;

    ctx.save();
    ctx.fillStyle = "rgba(52, 152, 219, 0.20)";
    ctx.fillRect(sx, sy, sw, sh);
    ctx.strokeStyle = "#3498db";
    ctx.lineWidth = 2;
    ctx.strokeRect(sx, sy, sw, sh);
    ctx.restore();
  }
}

function centerAndFitCanvas() {
  if (!state.project) return;
  const imgW = state.project.width;
  const imgH = state.project.height;
  const maxZoomX = Math.floor((els.canvas.width - 60) / Math.max(1, imgW));
  const maxZoomY = Math.floor((els.canvas.height - 60) / Math.max(1, imgH));
  const ideal = Math.max(1, Math.min(32, Math.min(maxZoomX, maxZoomY)));
  const allowed = [0.5, 1, 2, 4, 8, 12, 16, 24, 32];
  let best = allowed[0];
  for (const z of allowed) {
    if (z <= ideal) best = z;
  }
  state.zoom = best;
  els.zoomSelect.value = String(best);
  state.panX = Math.floor((els.canvas.width - imgW * state.zoom) / 2);
  state.panY = Math.floor((els.canvas.height - imgH * state.zoom) / 2);
  renderCanvas();
}

function setSelectionBox(box) {
  state.selectionBox = box;
  if (!box || !state.project) {
    els.hudSelection.textContent = "None (drag on canvas to select)";
    return;
  }
  els.selX.value = box.x;
  els.selY.value = box.y;
  els.selW.value = box.w;
  els.selH.value = box.h;
  els.selFrame.value = state.currentFrameIndex;
  els.hudSelection.textContent = `x=${box.x}, y=${box.y}, w=${box.w}, h=${box.h} [Frame #${state.currentFrameIndex}]`;
  renderCanvas();
}

/* -------------------------------------------------------------------------- */
/* Frame Loading & Timeline Playback                                          */
/* -------------------------------------------------------------------------- */

function preloadVersionFrames(project) {
  const vid = project.current_version_id;
  const vdoc = getActiveVersionDoc();
  if (!vdoc) return Promise.resolve();

  offscreenCanvas.width = project.width;
  offscreenCanvas.height = project.height;

  const promises = vdoc.frames.map((frameRec) => {
    const key = `${vid}:${frameRec.index}`;
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        state.frameImages[key] = img;
        if (frameRec.index === state.currentFrameIndex) {
          offscreenCtx.clearRect(0, 0, project.width, project.height);
          offscreenCtx.drawImage(img, 0, 0);
          renderCanvas();
        }
        resolve();
      };
      img.onerror = () => resolve();
      img.src = `/api/projects/${encodeURIComponent(project.project_id)}/frames/${frameRec.index}/image?version_id=${encodeURIComponent(vid)}&t=${Date.now()}`;
    });
  });
  return Promise.all(promises);
}

function selectFrame(index) {
  if (!state.project) return;
  const count = state.project.frame_count;
  state.currentFrameIndex = ((index % count) + count) % count;
  els.timelineScrubber.value = String(state.currentFrameIndex);
  els.selFrame.value = String(state.currentFrameIndex);

  const rec = getCurrentFrameRecord();
  const dur = rec ? rec.duration_ms : 100;
  els.frameCounterLabel.textContent = `Frame ${state.currentFrameIndex} / ${count - 1} (${dur} ms)`;

  const frameImg = getCurrentFrameImage();
  if (frameImg && frameImg.complete) {
    offscreenCtx.clearRect(0, 0, state.project.width, state.project.height);
    offscreenCtx.drawImage(frameImg, 0, 0);
  }

  for (const thumb of els.framesStrip.querySelectorAll(".frame-thumb")) {
    thumb.classList.toggle("active", Number(thumb.dataset.index) === state.currentFrameIndex);
  }
  if (state.selectionBox) {
    els.hudSelection.textContent = `x=${state.selectionBox.x}, y=${state.selectionBox.y}, w=${state.selectionBox.w}, h=${state.selectionBox.h} [Frame #${state.currentFrameIndex}]`;
  }
  renderCanvas();
}

function stopPlayback() {
  state.isPlaying = false;
  if (state.playTimerId) {
    clearTimeout(state.playTimerId);
    state.playTimerId = null;
  }
  els.playPauseBtn.textContent = "Play";
}

function scheduleNextFrameTick() {
  if (!state.isPlaying || !state.project) return;
  const rec = getCurrentFrameRecord();
  const delayMs = rec ? Math.max(15, rec.duration_ms) : 100;
  state.playTimerId = setTimeout(() => {
    if (!state.isPlaying || !state.project) return;
    const nextIdx = state.currentFrameIndex + 1;
    if (nextIdx >= state.project.frame_count && !els.loopCheckbox.checked) {
      stopPlayback();
      return;
    }
    selectFrame(nextIdx);
    scheduleNextFrameTick();
  }, delayMs);
}

function togglePlayback() {
  if (!state.project) return;
  if (state.isPlaying) {
    stopPlayback();
  } else {
    state.isPlaying = true;
    els.playPauseBtn.textContent = "Pause";
    scheduleNextFrameTick();
  }
}

/* -------------------------------------------------------------------------- */
/* Real-time Event Stream (SSE + WebSocket)                                   */
/* -------------------------------------------------------------------------- */

function appendStreamEvent(ev) {
  const line = document.createElement("div");
  line.className = "event-line";
  const timeStr = (ev.timestamp || "").split("T")[1] || "";
  const summary = ev.summary || ev.message || ev.status || ev.version_id || "";
  line.innerHTML = `[${timeStr}] <strong>${ev.type}</strong> ${summary}`;
  els.eventStreamLog.prepend(line);
}

function connectProjectStreams(projectId) {
  if (state.sseSource) {
    state.sseSource.close();
    state.sseSource = null;
  }
  if (state.wsSocket) {
    state.wsSocket.close();
    state.wsSocket = null;
  }
  els.eventStreamLog.innerHTML = "";

  // Connect Server-Sent Events (SSE)
  const sse = new EventSource(`/api/projects/${encodeURIComponent(projectId)}/events`);
  state.sseSource = sse;
  sse.onopen = () => {
    els.streamPill.textContent = "SSE: Connected";
    els.streamPill.className = "pill pill-safe";
  };
  const eventTypes = [
    "project.created",
    "timeline.updated",
    "job.created",
    "job.progress",
    "job.locality_qa",
    "job.completed",
    "job.awaiting_agent",
    "project.rolled_back",
    "export.manifest.completed",
    "export.godot4.completed",
  ];
  for (const t of eventTypes) {
    sse.addEventListener(t, (e) => {
      try {
        appendStreamEvent(JSON.parse(e.data));
      } catch (_err) {
        // ignore parse errors
      }
    });
  }
  sse.onerror = () => {
    els.streamPill.textContent = "SSE: Reconnecting...";
    els.streamPill.className = "pill pill-warn";
  };
}

/* -------------------------------------------------------------------------- */
/* UI Hydration                                                               */
/* -------------------------------------------------------------------------- */

function renderFramesStrip(project) {
  els.framesStrip.innerHTML = "";
  const vid = project.current_version_id;
  const vdoc = getActiveVersionDoc();
  if (!vdoc) return;

  for (const frameRec of vdoc.frames) {
    const card = document.createElement("div");
    card.className = `frame-thumb ${frameRec.index === state.currentFrameIndex ? "active" : ""}`;
    card.dataset.index = String(frameRec.index);

    const img = document.createElement("img");
    img.src = `/api/projects/${encodeURIComponent(project.project_id)}/frames/${frameRec.index}/image?version_id=${encodeURIComponent(vid)}&t=${Date.now()}`;
    img.alt = `Frame ${frameRec.index}`;

    const label = document.createElement("span");
    label.textContent = `#${frameRec.index} (${frameRec.duration_ms}ms)`;

    card.appendChild(img);
    card.appendChild(label);
    card.addEventListener("click", () => {
      stopPlayback();
      selectFrame(frameRec.index);
    });
    els.framesStrip.appendChild(card);
  }
}

function renderVersionsList(project) {
  els.versionsList.innerHTML = "";
  const currentVid = project.current_version_id;
  const versions = [...(project.versions || [])].reverse();

  for (const v of versions) {
    const row = document.createElement("div");
    row.className = `list-item ${v.version_id === currentVid ? "active" : ""}`;
    const info = document.createElement("div");
    info.innerHTML = `<strong>${v.version_id}</strong> &mdash; ${v.summary || v.kind}`;
    row.appendChild(info);

    if (v.version_id !== currentVid) {
      const btn = document.createElement("button");
      btn.className = "btn btn-small";
      btn.textContent = "Rollback";
      btn.addEventListener("click", () => handleRollback(v.version_id));
      row.appendChild(btn);
    } else {
      const tag = document.createElement("span");
      tag.className = "badge badge-safe";
      tag.textContent = "Active";
      row.appendChild(tag);
    }
    els.versionsList.appendChild(row);
  }
}

function renderJobsList(project) {
  els.jobsList.innerHTML = "";
  const jobs = [...(project.jobs || [])].reverse();
  if (jobs.length === 0) {
    els.jobsList.innerHTML = `<div class="list-item"><span>No edit jobs yet. Select a region and submit an instruction.</span></div>`;
    return;
  }
  for (const j of jobs) {
    const row = document.createElement("div");
    row.className = "list-item";
    const b = j.selection_box;
    row.innerHTML = `
      <div>
        <strong>${j.job_id}</strong> [F#${j.frame_index} (${b.x},${b.y},${b.w},${b.h})] &rarr; ${j.produced_version_id || j.status}
        <div style="color: var(--text-muted)">${j.instruction}</div>
      </div>
    `;
    const inspectBtn = document.createElement("button");
    inspectBtn.className = "btn btn-small";
    inspectBtn.textContent = "JSON";
    inspectBtn.addEventListener("click", async () => {
      const res = await fetch(`/api/projects/${encodeURIComponent(project.project_id)}/jobs/${encodeURIComponent(j.job_id)}`);
      if (res.ok) {
        const fullJob = await res.json();
        els.inspectorJsonView.textContent = JSON.stringify(fullJob, null, 2);
      }
    });
    row.appendChild(inspectBtn);
    els.jobsList.appendChild(row);
  }
}

async function applyProjectState(project, resetView = false) {
  const prevPid = state.project ? state.project.project_id : null;
  state.project = project;

  els.hudDimensions.textContent = `${project.width} × ${project.height} px (${project.frame_count} frame${project.frame_count > 1 ? "s" : ""}, ${project.source_format})`;
  els.activeVersionBadge.textContent = project.current_version_id;
  els.fpsInput.value = String(project.fps);
  els.loopCheckbox.checked = Boolean(project.loop);
  els.timelineScrubber.max = String(Math.max(0, project.frame_count - 1));

  if (project.original_integrity && project.original_integrity.unchanged) {
    els.originalHashBadge.textContent = `Original SHA256 OK (${project.original_file.sha256.slice(0, 8)}...)`;
    els.originalHashBadge.className = "badge badge-safe";
  }

  if (state.currentFrameIndex >= project.frame_count) {
    state.currentFrameIndex = 0;
  }

  if (!state.selectionBox || resetView) {
    setSelectionBox({
      x: 0,
      y: 0,
      w: Math.max(1, Math.min(project.width, Math.floor(project.width / 2))),
      h: Math.max(1, Math.min(project.height, Math.floor(project.height / 2))),
    });
  }

  renderFramesStrip(project);
  renderVersionsList(project);
  renderJobsList(project);

  await preloadVersionFrames(project);
  if (resetView || prevPid !== project.project_id) {
    centerAndFitCanvas();
    connectProjectStreams(project.project_id);
  }
  selectFrame(state.currentFrameIndex);
}

/* -------------------------------------------------------------------------- */
/* API Actions                                                                */
/* -------------------------------------------------------------------------- */

async function fetchHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    els.healthPill.textContent = "API: Online";
    els.healthPill.className = "pill pill-safe";
    if (data.godot4_available) {
      els.godotPill.textContent = "Godot 4: Ready";
      els.godotPill.className = "pill pill-safe";
    } else {
      els.godotPill.textContent = "Godot 4: Not Installed (Smoke Blocked)";
      els.godotPill.className = "pill pill-warn";
    }
  } catch (_err) {
    els.healthPill.textContent = "API: Offline";
    els.healthPill.className = "pill pill-warn";
  }
}

async function refreshProjectsDropdown(selectedId = null) {
  const res = await fetch("/api/projects");
  if (!res.ok) return;
  const data = await res.json();
  els.projectSelect.innerHTML = `<option value="">-- Select a project (${data.projects.length}) --</option>`;
  for (const p of data.projects) {
    const opt = document.createElement("option");
    opt.value = p.project_id;
    opt.textContent = `${p.name} [${p.source_format}, ${p.frame_count}f, ${p.current_version_id}]`;
    if (selectedId && p.project_id === selectedId) {
      opt.selected = true;
    }
    els.projectSelect.appendChild(opt);
  }
}

async function handleUploadFile(file) {
  if (!file) return;
  stopPlayback();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("name", file.name.replace(/\.[^.]+$/, ""));

  const res = await fetch("/api/projects/upload", {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    alert(`Upload failed: ${data.detail || "Unknown error"}`);
    return;
  }
  state.currentFrameIndex = 0;
  await refreshProjectsDropdown(data.project_id);
  await applyProjectState(data, true);
  els.inspectorJsonView.textContent = JSON.stringify(data.original_integrity, null, 2);
}

async function handleSubmitEditJob() {
  if (!state.project) {
    alert("Please upload or load a project first.");
    return;
  }
  const box = {
    x: Number(els.selX.value),
    y: Number(els.selY.value),
    w: Number(els.selW.value),
    h: Number(els.selH.value),
  };
  const instruction = els.editInstruction.value.trim() || `Edit region (${box.x}, ${box.y}, ${box.w}, ${box.h})`;
  const operation = els.editOperation.value;
  const colorHex = els.editColor.value;

  const payload = {
    frame_index: state.currentFrameIndex,
    selection_box: box,
    instruction,
    operation,
    color_hex: colorHex,
    apply_immediately: operation !== "record_only",
  };

  const res = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(`Edit job failed: ${data.detail || "Invalid selection or parameters"}`);
    return;
  }
  els.inspectorJsonView.textContent = JSON.stringify(data.job, null, 2);
  await applyProjectState(data.project, false);
  await refreshProjectsDropdown(data.project.project_id);
}

async function handleRollback(targetVersionId) {
  if (!state.project) return;
  stopPlayback();
  const res = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/rollback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_version_id: targetVersionId,
      reason: `Rollback to ${targetVersionId} from Studio UI`,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(`Rollback failed: ${data.detail || "Unknown error"}`);
    return;
  }
  els.inspectorJsonView.textContent = JSON.stringify(data.rollback, null, 2);
  await applyProjectState(data.project, false);
  await refreshProjectsDropdown(data.project.project_id);
}

async function handleExportManifest() {
  if (!state.project) return;
  const res = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/export/manifest`, {
    method: "POST",
  });
  const data = await res.json();
  if (res.ok) {
    els.inspectorJsonView.textContent = JSON.stringify(data, null, 2);
  }
}

async function handleExportGodot() {
  if (!state.project) return;
  els.inspectorJsonView.textContent = "Exporting Godot 4 (.tres / .tscn / atlas.png) and running headless smoke test...";
  const res = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/export/godot4`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_smoke_test: true }),
  });
  const data = await res.json();
  els.inspectorJsonView.textContent = JSON.stringify(data, null, 2);
}

/* -------------------------------------------------------------------------- */
/* Event Listeners                                                            */
/* -------------------------------------------------------------------------- */

els.uploadInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) handleUploadFile(file);
});

els.projectSelect.addEventListener("change", async (e) => {
  const pid = e.target.value;
  if (!pid) return;
  stopPlayback();
  const res = await fetch(`/api/projects/${encodeURIComponent(pid)}`);
  if (res.ok) {
    const proj = await res.json();
    state.currentFrameIndex = 0;
    await applyProjectState(proj, true);
  }
});

els.refreshProjectsBtn.addEventListener("click", () => {
  refreshProjectsDropdown(state.project ? state.project.project_id : null);
});

els.modeSelectBtn.addEventListener("click", () => {
  state.toolMode = "select";
  els.modeSelectBtn.classList.add("btn-active");
  els.modePanBtn.classList.remove("btn-active");
  els.canvas.style.cursor = "crosshair";
});

els.modePanBtn.addEventListener("click", () => {
  state.toolMode = "pan";
  els.modePanBtn.classList.add("btn-active");
  els.modeSelectBtn.classList.remove("btn-active");
  els.canvas.style.cursor = "grab";
});

els.clearSelectionBtn.addEventListener("click", () => setSelectionBox(null));

els.zoomSelect.addEventListener("change", () => {
  state.zoom = Number(els.zoomSelect.value);
  renderCanvas();
});

els.zoomInBtn.addEventListener("click", () => {
  const allowed = [0.5, 1, 2, 4, 8, 12, 16, 24, 32];
  const next = allowed.find((z) => z > state.zoom) || 32;
  state.zoom = next;
  els.zoomSelect.value = String(next);
  renderCanvas();
});

els.zoomOutBtn.addEventListener("click", () => {
  const allowed = [0.5, 1, 2, 4, 8, 12, 16, 24, 32];
  const prev = [...allowed].reverse().find((z) => z < state.zoom) || 0.5;
  state.zoom = prev;
  els.zoomSelect.value = String(prev);
  renderCanvas();
});

els.zoomFitBtn.addEventListener("click", centerAndFitCanvas);
els.gridToggle.addEventListener("change", () => {
  state.showGrid = els.gridToggle.checked;
  renderCanvas();
});
els.anchorToggle.addEventListener("change", () => {
  state.showAnchor = els.anchorToggle.checked;
  renderCanvas();
});

els.canvas.addEventListener("mousedown", (e) => {
  if (!state.project) return;
  const pt = clientToCanvasCoords(e.clientX, e.clientY);
  state.isDragging = true;
  state.dragStartCanvas = { x: pt.x, y: pt.y, panX: state.panX, panY: state.panY };

  if (state.toolMode === "select") {
    const box = canvasRectToSourceBox(
      pt.x,
      pt.y,
      pt.x,
      pt.y,
      state.panX,
      state.panY,
      state.zoom,
      state.project.width,
      state.project.height
    );
    setSelectionBox(box);
  }
});

window.addEventListener("mousemove", (e) => {
  if (!state.project) return;
  const pt = clientToCanvasCoords(e.clientX, e.clientY);
  const pixel = canvasPointToSourcePixel(
    pt.x,
    pt.y,
    state.panX,
    state.panY,
    state.zoom,
    state.project.width,
    state.project.height
  );

  if (pixel.inBounds) {
    els.hudCursorXY.textContent = `x: ${pixel.x}, y: ${pixel.y} (zoom ${state.zoom}x)`;
    const data = offscreenCtx.getImageData(pixel.x, pixel.y, 1, 1).data;
    const [r, g, b, a] = data;
    const hex = `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
    els.hudColorSwatch.style.background = `rgba(${r}, ${g}, ${b}, ${a / 255})`;
    els.hudPixelRGBA.textContent = `RGBA(${r}, ${g}, ${b}, ${a}) ${hex}`;
  } else {
    els.hudCursorXY.textContent = `Out of bounds (${pixel.unclampedX}, ${pixel.unclampedY})`;
  }

  if (!state.isDragging || !state.dragStartCanvas) return;
  if (state.toolMode === "pan") {
    state.panX = state.dragStartCanvas.panX + (pt.x - state.dragStartCanvas.x);
    state.panY = state.dragStartCanvas.panY + (pt.y - state.dragStartCanvas.y);
    renderCanvas();
  } else {
    const box = canvasRectToSourceBox(
      state.dragStartCanvas.x,
      state.dragStartCanvas.y,
      pt.x,
      pt.y,
      state.panX,
      state.panY,
      state.zoom,
      state.project.width,
      state.project.height
    );
    setSelectionBox(box);
  }
});

window.addEventListener("mouseup", () => {
  state.isDragging = false;
  state.dragStartCanvas = null;
});

for (const input of [els.selX, els.selY, els.selW, els.selH]) {
  input.addEventListener("change", () => {
    if (!state.project) return;
    setSelectionBox({
      x: Math.max(0, Math.min(state.project.width - 1, Number(els.selX.value) || 0)),
      y: Math.max(0, Math.min(state.project.height - 1, Number(els.selY.value) || 0)),
      w: Math.max(1, Number(els.selW.value) || 1),
      h: Math.max(1, Number(els.selH.value) || 1),
    });
  });
}

els.playPauseBtn.addEventListener("click", togglePlayback);
els.stepPrevBtn.addEventListener("click", () => {
  stopPlayback();
  selectFrame(state.currentFrameIndex - 1);
});
els.stepNextBtn.addEventListener("click", () => {
  stopPlayback();
  selectFrame(state.currentFrameIndex + 1);
});
els.timelineScrubber.addEventListener("input", (e) => {
  stopPlayback();
  selectFrame(Number(e.target.value));
});

els.applyFpsBtn.addEventListener("click", async () => {
  if (!state.project) return;
  const res = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/timeline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      fps: Number(els.fpsInput.value),
      loop: els.loopCheckbox.checked,
    }),
  });
  if (res.ok) {
    const updated = await res.json();
    await applyProjectState(updated, false);
  }
});

els.submitJobBtn.addEventListener("click", handleSubmitEditJob);
els.exportManifestBtn.addEventListener("click", handleExportManifest);
els.exportGodotBtn.addEventListener("click", handleExportGodot);

/* Initialize */
fetchHealth();
refreshProjectsDropdown();
