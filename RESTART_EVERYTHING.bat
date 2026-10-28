@echo off
title Virginia Legal AI - Restart Everything
color 0B
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
set SCENARIO_DB_ENABLED=False

echo ========================================
echo   Restarting: Ollama (NVIDIA CUDA device 0) + Backend
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
timeout /t 2 /nobreak >nul

echo [3] Starting Ollama on NVIDIA CUDA device 0 only (new window)...
start "Ollama - NVIDIA GPU" cmd /k "set CUDA_DEVICE_ORDER=PCI_BUS_ID & set CUDA_VISIBLE_DEVICES=0 & set OLLAMA_NUM_GPU=99 & echo NVIDIA CUDA device 0 only. No CPU fallback intended. & echo. & ollama serve"
timeout /t 5 /nobreak >nul

echo [4] Starting backend...
echo.
python -m uvicorn server.main:app --host 0.0.0.0 --port 5001 --timeout-keep-alive 600 --timeout-graceful-shutdown 30

if errorlevel 1 (
    echo.
    echo Backend exited with an error. Check the output above.
)
pause
