@echo off
cd /d "%~dp0"

echo ============================================
echo    WeChat Group Monitor - 一键启动（全量复制）
echo ============================================
echo.

set SOURCE_DIR=Bad_Messages_In_WeChat_Groups
set TARGET_DIR=_run

echo [..] Copying fresh project to %TARGET_DIR% ...
if exist "%TARGET_DIR%" (
    rmdir /s /q "%TARGET_DIR%"
)
mkdir "%TARGET_DIR%" >nul 2>&1
xcopy /E /I /Q "%SOURCE_DIR%\*" "%TARGET_DIR%" >nul
if errorlevel 1 (
    echo [!!] Failed to copy project directory
    pause
    exit /b 1
)
echo [OK] Fresh copy ready

REM --- Change to the copy and run ---
cd /d "%TARGET_DIR%"

echo [..] Starting run.py from copied directory...
echo.
python run.py
echo.
echo [!!] Server stopped
pause
