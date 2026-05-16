@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set APP_PORT=8100
set APP_PY=%~dp0.venv\Scripts\python.exe
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ============================================================
echo  GMV-LiveLens  http://127.0.0.1:%APP_PORT%
echo ============================================================
echo.

if not exist "%APP_PY%" (
    echo [ERROR] Python not found: %APP_PY%
    pause
    exit /b 1
)

for /f "tokens=2" %%P in ('tasklist /fi "imagename eq python.exe" /fo csv 2^>nul ^| findstr "uvicorn"') do (
    for /f "tokens=1 delims=," %%Q in ("%%P") do (
        taskkill /PID %%Q /T /F >nul 2>&1
    )
)

set "PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":%APP_PORT% " ^| findstr LISTENING') do (
    set "PORT_PID=%%P"
    goto :port_found
)

:port_found
if defined PORT_PID (
    echo [WARN] Port %APP_PORT% is already in use by PID %PORT_PID%.
    echo [INFO] Trying to stop the existing process...
    taskkill /PID %PORT_PID% /T /F >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to stop PID %PORT_PID%. Please close it manually.
        pause
        exit /b 1
    )
    echo [INFO] Waiting for port to release...
    timeout /t 3 /nobreak >nul
)

echo Starting... keep this window open.
echo.
"%APP_PY%" -m uvicorn backend.main:app --host 127.0.0.1 --port %APP_PORT%
pause
