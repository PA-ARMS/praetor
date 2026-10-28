@echo off
title Virginia Legal AI - System Startup
color 0A

echo ========================================
echo   Virginia Legal AI System Startup
echo ========================================
echo.

REM Project root = folder where this .bat lives (handles spaces in path)
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

cd /d "%ROOT%"
set PYTHONPATH=%ROOT%

echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)
echo     Python OK

echo [2/4] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found!
    pause
    exit /b 1
)
echo     Node.js OK

echo [3/4] Checking Ollama...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: Ollama not found - some features may not work
) else (
    echo     Ollama OK
)

echo [4/4] Starting services...
echo.

REM Start backend in new window (scripts\run_backend.bat sets cwd and PYTHONPATH from its path)
echo Starting Backend Server (Port 5001)...
start "Virginia Legal AI - Backend Server" /d "%~dp0" cmd /c "call scripts\run_backend.bat & pause"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend in new window
echo Starting Frontend Server (Port 3000)...
start "Virginia Legal AI - Frontend Server" /d "%~dp0" cmd /c "call scripts\run_frontend.bat & pause"

REM Wait a moment for frontend to start
timeout /t 3 /nobreak >nul

REM Open status window
echo Opening Status Monitor...
start "Virginia Legal AI - Status Monitor" /d "%~dp0" cmd /k "call scripts\status_monitor.bat"

REM Wait a moment
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo   System Started Successfully!
echo ========================================
echo.
echo Three windows have been opened:
echo   1. Backend Server - FastAPI on port 5001
echo   2. Frontend Server - React on port 3000
echo   3. Status Monitor - Shows service status
echo.
echo Access the system at: http://localhost:3000
echo.
echo To stop the system, close all three windows.
echo.
pause

