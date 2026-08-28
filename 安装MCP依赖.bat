@echo off
cd /d "%~dp0"
echo ====================================
echo   Install MCP Dependencies
echo ====================================
echo.
set "PYEXE=%~dp0python\python.exe"
if exist "%PYEXE%" (
    echo [OK] Using bundled Python
) else (
    echo [INFO] Bundled Python not found, trying system Python...
    python --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found. Put python folder in the same directory.
        pause
        exit /b 1
    )
    set "PYEXE=python"
    echo [OK] Using system Python
)
echo.
echo [1/2] Installing mcp package...
"%PYEXE%" -m pip install mcp
if errorlevel 1 (
    echo.
    echo [ERROR] Install failed. Check your network connection.
    pause
    exit /b 1
)
echo.
echo [2/2] Verifying installation...
"%PYEXE%" -c "import mcp; print('mcp installed:', 'ok')" 2>nul
if errorlevel 1 (
    echo [WARN] Verify failed, but package may be installed.
) else (
    echo [OK] Installed successfully
)
echo.
echo ====================================
echo   MCP dependencies installed!
echo   Run mcp_server.py after main.py is started.
echo ====================================
pause
