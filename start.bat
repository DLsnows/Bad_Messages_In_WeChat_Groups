@echo off
cd /d "%~dp0"

echo ============================================
echo    WeChat Group Monitor - 一键启�?echo ============================================
echo.

REM --- Check Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo [!!] Not found: Python. Please install Python 3.10+
    pause
    exit /b 1
)
echo [OK] Python found

REM --- Check .env ---
if not exist .env (
    echo [..] Creating .env from .env.example ...
    copy .env.example .env >nul
    echo.
    echo [!!] =======================================================
    echo [!!]  Please edit .env to configure your LLM API:
    echo [!!]    LLM_BASE_URL  - API endpoint
    echo [!!]    LLM_API_KEY   - API key
    echo [!!]    LLM_MODEL     - model name
    echo [!!] =======================================================
    echo.
    echo [..] Opening .env in Notepad. Save and close to continue...
    pause
    notepad .env
    echo.
) else (
    echo [OK] .env exists
)

REM --- Install dependencies ---
echo.
echo [..] Installing dependencies...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [!!] Failed to install dependencies.
    echo       Try: python -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo [OK] Dependencies ready

REM --- Start server ---
echo.
echo [..] Starting server...
echo [..] Browser will open automatically
echo [..] Close this window to stop the server
echo.
python run.py
echo.
echo [!!] Server stopped
