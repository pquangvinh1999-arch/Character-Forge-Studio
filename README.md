# Character Forge Studio

**Character Forge Studio** is a modular Python-first 2D / Pixel Art character production monorepo designed for non-programmers and operated collaboratively with **Google Antigravity CLI** and **OpenAI Codex CLI**.

It combines selected capabilities from three pinned upstream repositories isolated in `vendor/`:
1. **[`0x0funky/agent-sprite-forge`](https://github.com/0x0funky/agent-sprite-forge)** (`72fa5ad92d79b811acff464da32c8f3b1caa010f`, MIT License) — Primary animation production engine, RGBA core math, edit-locality QA, cutout rigging, and Godot 4 / Aseprite export.
2. **[`aldegad/sprite-gen`](https://github.com/aldegad/sprite-gen)** (`4f5ccd55c7cf06685a41f954acc1e476b7772ece`, Apache-2.0 License + NOTICE) — Selected frame extraction, palette analysis, pitch estimation, non-destructive curation sidecars, and motion scoring.
3. **[`Donchitos/Claude-Code-Game-Studios`](https://github.com/Donchitos/Claude-Code-Game-Studios)** (`05ad7c8a5b8aa2aa86bbd3439ae7cf7295cac418`, MIT License) — Reference architecture for agent orchestration, asset specifications, and evidence-based QA gates (`COMPLIANT` / `NOT ASSESSED` / `BLOCKED` / `NON-COMPLIANT`), ported to [`AGENTS.md`](AGENTS.md) and [`.agents/skills/`](.agents/skills/).

---

## Quick Start (Windows CMD & Linux)

### 1. Install Dependencies
```cmd
python -m pip install -r requirements.txt
```

### 2. Launch the Localhost Visual Studio
- **Windows (`cmd.exe`)**:
  ```cmd
  run-studio.bat
  ```
- **Linux / macOS / Direct Python**:
  ```bash
  ./run-studio.sh
  # or:
  python3 -m uvicorn apps.studio_api.main:app --host 127.0.0.1 --port 8000
  ```
Then open **`http://127.0.0.1:8000`** in your browser.

### 3. Run the Automated QA & Acceptance Suite
```cmd
python -m pytest -v
```

---

## Documentation Index

- **Phase 0 Upstream Audit**: [`docs/audit/UPSTREAM_AUDIT.md`](docs/audit/UPSTREAM_AUDIT.md)
- **System Architecture**: [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md)
- **Capability Integration Matrix**: [`docs/architecture/INTEGRATION_MATRIX.md`](docs/architecture/INTEGRATION_MATRIX.md)
- **Phase 2 Technical Specifications**: [`docs/architecture/PHASE2_TECHNICAL_SPECS.md`](docs/architecture/PHASE2_TECHNICAL_SPECS.md)
- **Implementation Roadmap**: [`docs/roadmap/IMPLEMENTATION_PLAN.md`](docs/roadmap/IMPLEMENTATION_PLAN.md)
- **Third-Party Licenses & Notices**: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- **Pinned Upstream Lockfile**: [`vendor/VENDOR_LOCK.json`](vendor/VENDOR_LOCK.json)
- **Shared Agent Instructions**: [`AGENTS.md`](AGENTS.md)
