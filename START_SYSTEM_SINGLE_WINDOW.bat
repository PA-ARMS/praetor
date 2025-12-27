@echo off
title Virginia Legal AI - System Console
color 0A
mode con: cols=100 lines=40

REM Set working directory
cd /d "%~dp0"

REM Set Python path
set PYTHONPATH=%CD%

cls
echo ========================================
echo   Virginia Legal AI System Console
echo ========================================
echo.
echo Starting Backend Server (Port 5000)...
echo Starting Frontend Server (Port 3000)...
echo.
echo ========================================
echo.

REM Start backend in background
start /B cmd /c "cd /d %CD% && set PYTHONPATH=%CD% && set SCENARIO_DB_ENABLED=True && python -m uvicorn server.main:app --host 0.0.0.0 --port 5000 > backend.log 2>&1"

REM Wait for backend
timeout /t 3 /nobreak >nul

REM Start frontend in background
start /B cmd /c "cd /d %CD%\client && npm run dev > ..\frontend.log 2>&1"

REM Wait for frontend
timeout /t 3 /nobreak >nul

echo System Status:
echo ========================================
echo.

:status_loop
REM Check backend
curl -s http://localhost:5000/health >nul 2>&1
if errorlevel 1 (
    echo [%time%] Backend:  NOT RUNNING
) else (
    echo [%time%] Backend:  RUNNING ^(http://localhost:5000^)
)

REM Check frontend
set "FRONTEND_PORT=3000"
curl -s http://localhost:3000 >nul 2>&1
if errorlevel 1 (
    REM Try fallback port 3001 (Vite uses this if 3000 is busy)
    set "FRONTEND_PORT=3001"
    curl -s http://localhost:3001 >nul 2>&1
    if errorlevel 1 (
        echo [%time%] Frontend: NOT RUNNING
        set "FRONTEND_PORT="
    ) else (
        echo [%time%] Frontend: RUNNING ^(http://localhost:3001^)
    )
) else (
    echo [%time%] Frontend: RUNNING ^(http://localhost:3000^)
)

echo.
echo ========================================
if defined FRONTEND_PORT (
    echo Access: http://localhost:%FRONTEND_PORT%
) else (
    echo Access: http://localhost:3000 ^(or 3001 if 3000 is busy^)
)
echo Press Ctrl+C to stop all services
echo ========================================
echo.

timeout /t 10 /nobreak >nul
cls
echo ========================================
echo   Virginia Legal AI System Console
echo ========================================
echo.
goto status_loop

