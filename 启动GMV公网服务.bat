@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set APP_PORT=8100
set APP_PY=%~dp0.venv\Scripts\python.exe
set FRPC_EXE=%~dp0deploy\frp-runtime\frpc.exe
set FRPC_CONFIG=%~dp0deploy\frp\frpc.toml

echo ============================================================
echo  GMV-LiveLens 一键公网服务
echo  Local:  http://127.0.0.1:%APP_PORT%/dashboard
echo  Public: http://124.223.70.233/dashboard
echo ============================================================
echo.

if not exist "%APP_PY%" (
    echo [ERROR] Python not found: %APP_PY%
    pause
    exit /b 1
)

if not exist "%FRPC_EXE%" (
    echo [ERROR] frpc.exe not found: %FRPC_EXE%
    echo [INFO] Run this first:
    echo        powershell -ExecutionPolicy Bypass -File deploy\scripts\install-frpc-windows.ps1 -Token ^<same-frp-token^>
    pause
    exit /b 1
)

if not exist "%FRPC_CONFIG%" (
    echo [ERROR] FRP config not found: %FRPC_CONFIG%
    echo [INFO] Run install-frpc-windows.ps1 or copy deploy\frp\frpc.gmv-livelens.toml.example to deploy\frp\frpc.toml.
    pause
    exit /b 1
)

echo [1/3] Starting local GMV backend...
start "GMV 后端服务 - 127.0.0.1:%APP_PORT%" cmd /k call "%~dp0第1步_启动GMV服务.bat"

echo [2/3] Waiting for port %APP_PORT%...
set /a WAIT_LEFT=60

:wait_backend
set "PORT_READY="
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":%APP_PORT% " ^| findstr LISTENING') do (
    set "PORT_READY=1"
    goto :backend_ready
)
if %WAIT_LEFT% LEQ 0 goto :backend_timeout
timeout /t 1 /nobreak >nul
set /a WAIT_LEFT-=1
goto :wait_backend

:backend_ready
echo [OK] Local backend is listening on %APP_PORT%.
echo [3/3] Starting public tunnel...
start "GMV 公网隧道 - 124.223.70.233" cmd /k call "%~dp0第2步_启动公网隧道.bat"
echo.
echo Done. Keep both opened windows running.
echo Public dashboard: http://124.223.70.233/dashboard
pause
exit /b 0

:backend_timeout
echo [ERROR] Local backend did not listen on %APP_PORT% within 60 seconds.
echo [INFO] Check the "GMV 后端服务" window for the real error.
pause
exit /b 1
