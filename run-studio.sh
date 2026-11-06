#!/usr/bin/env bash
set -euo pipefail

# Character Forge Studio — POSIX Launcher (Linux / macOS / CI)
cd "$(dirname "$0")"

STUDIO_HOST="${STUDIO_HOST:-127.0.0.1}"
STUDIO_PORT="${STUDIO_PORT:-8000}"
STUDIO_URL="http://${STUDIO_HOST}:${STUDIO_PORT}"

if [ -x ".venv/bin/python" ]; then
  PYTHON_EXE=".venv/bin/python"
else
  PYTHON_EXE="python3"
fi

if [ "${1:-}" = "--check" ]; then
  "${PYTHON_EXE}" scripts/bootstrap_vendors.py --verify
  echo "[OK] Character Forge Studio launcher verified with ${PYTHON_EXE} on ${STUDIO_URL}"
  exit 0
fi

"${PYTHON_EXE}" scripts/bootstrap_vendors.py

echo "============================================================================"
echo "  Character Forge Studio - Localhost Visual Studio"
echo "  URL: ${STUDIO_URL}"
echo "  Python: ${PYTHON_EXE}"
echo "============================================================================"

exec "${PYTHON_EXE}" -m uvicorn apps.studio_api.main:app --host "${STUDIO_HOST}" --port "${STUDIO_PORT}"
