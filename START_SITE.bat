@echo off
title Virginia Legal AI - Start Site
cd /d "%~dp0"

echo Freeing ports 5001, 3000, 3001...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5001" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3001" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
timeout /t 3 /nobreak >nul

echo Starting Backend (port 5001)...
start "Backend" cmd /k "cd /d %~dp0 && set PYTHONPATH=%~dp0 && set SCENARIO_DB_ENABLED=True && python -m uvicorn server.main:app --host 0.0.0.0 --port 5001 --timeout-keep-alive 600"

echo Waiting 10 seconds for backend...
timeout /t 10 /nobreak >nul

echo Starting Frontend...
start "Frontend" cmd /k "cd /d %~dp0client && npm run dev"

echo.
echo ========================================
echo   Open in your browser:
echo   http://localhost:3000
echo   or if 3000 was in use: http://localhost:3001
echo ========================================
echo.
pause
