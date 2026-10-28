@echo off
title Virginia Legal AI - Full Restart (Ollama + Backend + Frontend)
color 0B
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
set SCENARIO_DB_ENABLED=False

echo ========================================
echo   FULL RESTART
echo   Ollama (NVIDIA CUDA device 0) + Backend 5001 + Vite
echo ========================================
echo.

echo [1] Stopping Ollama...
taskkill /F /IM ollama.exe 2>nul
if errorlevel 1 (echo       Ollama was not running.) else (echo       Ollama stopped.)
timeout /t 2 /nobreak >nul

echo [2] Freeing ports 5001, 3000, 3001...
echo     (If backend runs as SYSTEM, accept the UAC prompt to clear ports.)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\restart_free_ports.ps1"
if errorlevel 1 (
    echo     WARNING: Port cleanup may be incomplete. Accept the UAC prompt when asked, or run STOP_BACKEND_ADMIN.bat as Administrator, then run this script again.
)
timeout /t 3 /nobreak >nul

echo [3] Starting Ollama - NVIDIA CUDA device 0 only (new window - keep it open)...
start "Ollama - NVIDIA GPU" cmd /k "set CUDA_DEVICE_ORDER=PCI_BUS_ID & set CUDA_VISIBLE_DEVICES=0 & set OLLAMA_NUM_GPU=99 & echo NVIDIA CUDA device 0 only. Keep this window open. & echo. & ollama serve"

echo [4] Waiting for Ollama on 11434 (15s)...
timeout /t 15 /nobreak >nul

echo [5] Starting backend on port 5001 (new window)...
start "Legal AI - Backend 5001" cmd /k "cd /d %~dp0 & set PYTHONPATH=%CD% & set SCENARIO_DB_ENABLED=False & python -m uvicorn server.main:app --host 0.0.0.0 --port 5001 --timeout-keep-alive 600 --timeout-graceful-shutdown 30"

timeout /t 3 /nobreak >nul

echo [6] Starting frontend - Vite (new window)...
start "Legal AI - Frontend" cmd /k "cd /d %~dp0client & npm run dev"

echo.
echo ========================================
echo   Done. Three windows should be open:
echo   - Ollama (NVIDIA CUDA device 0)
echo   - Backend (5001)
echo   - Frontend (Vite - note the URL, often 3000 or 3001)
echo.
echo   Backend:  http://127.0.0.1:5001/health
echo   Ollama:   http://127.0.0.1:11434/api/tags
echo ========================================
echo.
pause
