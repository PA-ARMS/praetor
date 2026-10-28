@echo off
title Virginia Legal AI - Backend Server
color 0A

REM Run as current user so restart (RESTART.bat) can kill this process without admin.
REM If port 5001 is in use by another user's process, run this batch "Run as administrator" once.

cd /d "%~dp0"
set "PYTHONPATH=%CD%"
REM Chat-only: scenario DB off so only chat LLM runs (no scenario embeddings). Set True to re-enable Scenario Analysis.
set SCENARIO_DB_ENABLED=False

echo ========================================
echo   Virginia Legal AI - Backend Server
echo   Port 5001
echo ========================================
echo.

echo [0] Ollama on port 11434...
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -UseBasicParsing -TimeoutSec 3).StatusCode | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo     Ollama not responding — starting it with NVIDIA CUDA device 0 only ^(new window^).
    echo     If chat still says "CPU buffer", quit Ollama from the tray and run RESTART_EVERYTHING.bat
    start "Ollama - NVIDIA GPU" cmd /k "set CUDA_DEVICE_ORDER=PCI_BUS_ID&& set CUDA_VISIBLE_DEVICES=0&& set OLLAMA_NUM_GPU=99&& echo NVIDIA CUDA device 0 only. Keep this window open.&& echo.&& ollama serve"
    call :wait_for_ollama
) else (
    echo     Ollama is already running.
    echo     If you get "unable to allocate CPU buffer", that Ollama was likely started without GPU: quit Ollama from the tray, then run RESTART_EVERYTHING.bat
)
echo.

echo [1] Freeing port 5001...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5001" ^| findstr "LISTENING"') do (
    echo     Stopping PID %%a...
    taskkill /F /PID %%a 2>nul
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\kill_port.ps1" -Port 5001 2>nul
timeout /t 3 /nobreak >nul

echo [2] Starting backend...
echo.
python -m uvicorn server.main:app --host 0.0.0.0 --port 5001 --timeout-keep-alive 600 --timeout-graceful-shutdown 30

if errorlevel 1 (
    echo.
    echo Backend exited with an error. Check the output above.
)
pause
goto :eof

:wait_for_ollama
echo     Waiting for Ollama on port 11434 ^(up to 45s^)...
for /L %%i in (1,1,15) do (
    timeout /t 3 /nobreak >nul
    powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -UseBasicParsing -TimeoutSec 3).StatusCode | Out-Null; exit 0 } catch { exit 1 }"
    if not errorlevel 1 (
        echo     Ollama is up.
        goto :eof
    )
    echo     ... still waiting ^(%%i/15^)
)
echo     WARNING: Ollama did not respond. Check the "Ollama - GPU1" window for errors.
goto :eof
