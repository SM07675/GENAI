@echo off
echo ========================================
echo    Genie AI Voice Assistant Launcher
echo ========================================
echo.

REM Ensure Node.js is available in PATH
if exist "C:\Program Files\nodejs" (
    set "PATH=C:\Program Files\nodejs;%PATH%"
)

REM Check if backend dependencies are installed
echo [1/4] Checking backend dependencies...
cd backend
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        python -m venv .venv
    )
    .venv\Scripts\pip.exe install -r requirements.txt
)
echo     Backend dependencies OK

REM Check if .env file exists
if not exist ".env" (
    echo.
    echo ERROR: Backend .env file not found!
    echo Please copy .env.example to .env and add your API keys
    echo.
    pause
    exit /b 1
)
echo     Backend .env file found

cd ..

REM Check if frontend dependencies are installed
echo [2/4] Checking frontend dependencies...
if not exist "frontend\node_modules" (
    echo.
    echo ERROR: Frontend dependencies not installed!
    echo Please run: cd frontend && npm install
    echo.
    pause
    exit /b 1
)
echo     Frontend dependencies OK

echo.
echo [3/4] Starting Backend Server...
echo.
start "Genie Backend" cmd /k "cd backend && .venv\Scripts\python.exe run.py"
echo     Backend starting in new window...
echo     Wait for 'Application startup complete' message

REM Wait a bit for backend to start
timeout /t 3 /nobreak >nul

echo.
echo [4/4] Starting Frontend App...
echo.
start "Genie Frontend" cmd /k "cd frontend && npm run electron:dev"
echo     Frontend starting in new window...

echo.
echo ========================================
echo    Genie is starting!
echo ========================================
echo.
echo Two windows have opened:
echo   1. Backend Server (keep this running)
echo   2. Frontend App (Electron will open)
echo.
echo Close this window if you want.
echo To stop Genie, press Ctrl+C in each window.
echo.
pause
