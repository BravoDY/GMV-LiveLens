@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set FRPC_EXE=%~dp0deploy\frp-runtime\frpc.exe
set FRPC_CONFIG=%~dp0deploy\frp\frpc.toml

echo ============================================================
echo  GMV-LiveLens public tunnel
echo  Local:  http://127.0.0.1:8100
echo  Public: http://124.223.70.233/dashboard
echo ============================================================
echo.

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

echo Starting tunnel... keep this window open.
echo.
"%FRPC_EXE%" -c "%FRPC_CONFIG%"
pause
