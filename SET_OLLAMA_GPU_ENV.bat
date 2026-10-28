@echo off
title Set Ollama: NVIDIA CUDA device 0 (run once)
cd /d "%~dp0"

echo ========================================
echo   NVIDIA CUDA device 0 only - no CPU fallback intended
echo ========================================
echo.
echo Sets Windows user env so Ollama uses NVIDIA CUDA device 0.
echo Then quit Ollama and start it again.
echo.

setx CUDA_DEVICE_ORDER "PCI_BUS_ID"
setx CUDA_VISIBLE_DEVICES "0"
setx OLLAMA_NUM_GPU "99"

echo.
echo Done. Restart Ollama: tray -^> Quit, then start again.
echo.
pause
