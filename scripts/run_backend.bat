@echo off
REM Run from project root using this script's location
cd /d "%~dp0.."
set "PYTHONPATH=%CD%"
set SCENARIO_DB_ENABLED=True

echo Backend starting from: %CD%
echo PYTHONPATH=%PYTHONPATH%
echo.

REM Free port 5001 first (Run as Admin if you get "port in use" errors)
echo Freeing port 5001...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5001" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kill_port.ps1" -Port 5001 2>nul
timeout /t 3 /nobreak >nul
echo.

python -m uvicorn server.main:app --host 0.0.0.0 --port 5001 --timeout-keep-alive 600 --timeout-graceful-shutdown 30

if errorlevel 1 (
    echo.
    echo Backend exited with an error. See above.
    echo Tip: Right-click this file -^> Run as administrator to free the port.
)
pause
