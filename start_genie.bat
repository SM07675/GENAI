@echo off
:: ============================================================
::  Genie — One-click launcher
::  Double-click to start backend + Electron desktop app.
:: ============================================================

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

echo.
echo  ============================================================
echo   Genie -- Starting up
echo  ============================================================
echo.

:: 1. Kill anything on ports 8765 or 5173 (ignore errors)
echo  [1/4] Clearing ports 8765 and 5173...
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /R ":8765 :5173 "') do (
    taskkill /PID %%P /F >nul 2>nul
)
ping -n 2 127.0.0.1 >nul

:: 2. Verify venv exists
if not exist "%BACKEND%\.venv\Scripts\python.exe" (
    echo.
    echo  [ERROR] Venv not found. Run once from backend\ :
    echo    py -3.11 -m venv .venv
    echo    .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

:: 2b. Check for GEMINI_API_KEY
findstr /C:"GEMINI_API_KEY=" "%BACKEND%\.env" | findstr /V "GEMINI_API_KEY=$" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [WARN] GEMINI_API_KEY looks empty in backend\.env
    echo  Genie will start but chat/tools won't work until you add your key.
    echo.
)

:: 3. Start backend in its own window (stays open after Ctrl+C)
echo  [2/4] Starting backend...
start "Genie Backend" /D "%BACKEND%" cmd /k ".venv\Scripts\python run.py"

:: 4. Poll /health (PowerShell, up to ~30 s)
echo  [3/4] Waiting for backend...
call :wait_for_backend
echo  Backend is ready!

:: 5. npm install if node_modules missing
if not exist "%FRONTEND%\node_modules" (
    echo  [4/4] Installing npm packages ^(first run^)...
    cd /d "%FRONTEND%"
    call npm install
)

:: 6. Launch Electron
echo  [4/4] Launching Genie desktop app...
start "Genie Frontend" /D "%FRONTEND%" cmd /k "npm run electron:dev"

echo.
echo  ============================================================
echo   Genie is running!
echo     Backend  ^>  "Genie Backend" window  (PIN shown there)
echo     Desktop  ^>  Electron window opens shortly
echo     Stop     ^>  close both cmd windows
echo  ============================================================
echo.
goto :eof

:wait_for_backend
    set /a _t=0
    :_loop
    ping -n 2 127.0.0.1 >nul
    powershell -NoProfile -Command "try{Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 1|Out-Null;exit 0}catch{exit 1}" >nul 2>nul
    if not errorlevel 1 goto :eof
    set /a _t=_t+1
    if %_t% lss 15 goto _loop
    echo  [WARN] Backend took too long -- continuing anyway.
    goto :eof
