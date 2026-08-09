@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Genie -- One-click launcher
REM  Double-click to start backend + Electron desktop app.
REM ============================================================

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

REM Ensure Node.js is available in PATH
if exist "C:\Program Files\nodejs" (
    set "PATH=C:\Program Files\nodejs;!PATH!"
)

echo.
echo  ============================================================
echo   Genie -- Starting up
echo  ============================================================
echo.

REM 1. Clear ports 8765 and 5173
echo  [1/4] Clearing ports 8765 and 5173...
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /R ":8765 :5173 "') do (
    taskkill /PID %%P /F >nul 2>nul
)
ping -n 2 127.0.0.1 >nul

REM 2. Verify or recreate venv & dependencies
if not exist "%BACKEND%\.venv\Scripts\python.exe" (
    echo  [INFO] Virtual environment not found. Creating fresh .venv...
    cd /d "%BACKEND%"
    py -3 -m venv .venv
    if errorlevel 1 (
        python -m venv .venv
    )
    cd /d "%ROOT%"
)

if not exist "%BACKEND%\.venv\Scripts\uvicorn.exe" (
    echo  [INFO] Installing backend dependencies...
    cd /d "%BACKEND%"
    .venv\Scripts\pip install -r requirements.txt
    cd /d "%ROOT%"
)

REM 3. Check for GEMINI_API_KEY
findstr /C:"GEMINI_API_KEY=" "%BACKEND%\.env" | findstr /V "GEMINI_API_KEY=$" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [WARN] GEMINI_API_KEY looks empty in backend\.env
    echo  Genie will start but chat/tools won't work until you add your key.
    echo.
)

REM 4. Start backend in its own window
echo  [2/4] Starting backend...
start "Genie Backend" /D "%BACKEND%" cmd /k ".venv\Scripts\python.exe run.py"

REM 5. Poll /health (up to ~15 sec)
echo  [3/4] Waiting for backend...
set "_count=0"
:health_loop
ping -n 2 127.0.0.1 >nul
powershell -NoProfile -Command "try{Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 1|Out-Null;exit 0}catch{exit 1}" >nul 2>nul
if not errorlevel 1 goto backend_ready
set /a "_count=_count+1"
if %_count% lss 15 goto health_loop
echo  [WARN] Backend took too long -- continuing anyway.

:backend_ready
echo  Backend is ready!

REM 6. Launch Electron
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
pause
