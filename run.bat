@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion

set "PYEXE=%~dp0python\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

rem 端口优先级：环境变量 WUCANVAS_PORT > data/port_config.json > 默认 3000
if "%WUCANVAS_PORT%"=="" (
  if exist "%~dp0data\port_config.json" (
    for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "try{((Get-Content '%~dp0data\port_config.json' -Raw | ConvertFrom-Json).port)}catch{''}"`) do set "CUSTOM_PORT=%%i"
    if not "!CUSTOM_PORT!"=="" (
      set "WUCANVAS_PORT=!CUSTOM_PORT!"
    ) else (
      set "WUCANVAS_PORT=3000"
    )
  ) else (
    set "WUCANVAS_PORT=3000"
  )
)

rem ComfyUI render wait limit: default 1200s, raised to 1 hour here
set "COMFYUI_HISTORY_TIMEOUT=3600"

echo Starting Infinite Canvas (main + MCP)...
echo Main  : http://127.0.0.1:%WUCANVAS_PORT%/
echo MCP   : http://127.0.0.1:8765/sse
echo Both services share this window.
echo Press Ctrl+C or close the window to stop both services.
echo.

start /b cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:%WUCANVAS_PORT%/"
start "" /b "%PYEXE%" mcp_server.py
"%PYEXE%" main.py

echo.
echo Server stopped.
pause