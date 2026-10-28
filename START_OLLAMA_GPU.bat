@echo off
title Ollama - NVIDIA GPU only
cd /d "%~dp0"

REM Use the first visible NVIDIA CUDA device (index 0). Keeps model load off system RAM.
set CUDA_DEVICE_ORDER=PCI_BUS_ID
set CUDA_VISIBLE_DEVICES=0
set OLLAMA_NUM_GPU=99

echo NVIDIA GPU (CUDA index 0) only. No CPU fallback intended.
echo.
ollama serve

pause
