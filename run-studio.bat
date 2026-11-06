@echo off
setlocal EnableExtensions

REM Character Forge Studio — Windows CMD Launcher (Phase 1 Local MVP)
REM Starts the FastAPI backend and opens http://127.0.0.1:8000 in the default browser.
REM Pure CMD.exe batch script — no PowerShell-only tooling or npm required.

cd /d "%~dp0"

set "STUDIO_HOST=127.0.0.1"
if "%STUDIO_PORT%"=="" set "STUDIO_PORT=8000"
set "STUDIO_URL=http://%STUDIO_HOST%:%STUDIO_PORT%"

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
    ) else (
        where py >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=py -3"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo [ERROR] Python 3.11+ was not found in PATH or .venv\Scripts\python.exe.
    exit /b 1
)

if "%~1"=="--check" (
    %PYTHON_EXE% scripts\bootstrap_vendors.py --verify
    if errorlevel 1 exit /b 1
    echo [OK] Character Forge Studio launcher verified with %PYTHON_EXE% on %STUDIO_URL%
    exit /b 0
)

%PYTHON_EXE% scripts\bootstrap_vendors.py
if errorlevel 1 (
    echo [ERROR] Failed to verify or bootstrap pinned vendor repositories.
    exit /b 1
)

echo ============================================================================
echo   Character Forge Studio - Localhost Visual Studio
echo   URL: %STUDIO_URL%
echo   Python: %PYTHON_EXE%
echo ============================================================================

if not "%~1"=="--no-browser" (
    start "" "%STUDIO_URL%"
)

%PYTHON_EXE% -m uvicorn apps.studio_api.main:app --host %STUDIO_HOST% --port %STUDIO_PORT%
exit /b %ERRORLEVEL%
