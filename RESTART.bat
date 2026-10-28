@echo off
title Virginia Legal AI - Restart
color 0A

cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo ========================================
echo   Virginia Legal AI - Restart
echo ========================================
echo.

echo [1] Freeing ports 5001, 3000, 3001...
echo     (If backend runs as SYSTEM, accept the UAC prompt to clear ports.)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\restart_free_ports.ps1"
if errorlevel 1 (
    echo     WARNING: Port cleanup may be incomplete. Accept the UAC prompt when asked, or run STOP_BACKEND_ADMIN.bat as Administrator, then run this script again.
)

timeout /t 3 /nobreak >nul

echo [2] Starting Backend (port 5001)...
start "Virginia Legal AI - Backend Server" /d "%ROOT%" cmd /c "call scripts\run_backend.bat & pause"

timeout /t 3 /nobreak >nul

echo [3] Starting Frontend (port 3000)...
start "Virginia Legal AI - Frontend Server" /d "%ROOT%" cmd /c "call scripts\run_frontend.bat & pause"

echo.
echo ========================================
echo   Restart complete
echo ========================================
echo   Backend:  http://localhost:5001
echo   Frontend: http://localhost:3000
echo   If a port is still in use: run STOP_BACKEND_ADMIN.bat as Administrator ^(stops SYSTEM/Session 0 Python^), or close the Backend/Frontend window.
echo.
pause
