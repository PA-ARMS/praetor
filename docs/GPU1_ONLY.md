# NVIDIA GPU 1 only – no CPU, no APU (GPU 0)

This system is set so **all LLM work runs on the NVIDIA GPU (GPU 1) only**. No CPU fallback, no use of GPU 0 (APU/integrated).

## How it’s enforced

1. **Ollama** must be started with:
   - **CUDA_DEVICE_ORDER=PCI_BUS_ID** – stable GPU ordering
   - **CUDA_VISIBLE_DEVICES=1** – only NVIDIA (GPU 1) is visible; APU/CPU are not used for the model
   - **OLLAMA_NUM_GPU=99** – use as many layers as possible on that GPU (no CPU offload)

2. **Backend** (`server/services/ollama_service.py`): when `OLLAMA_NUM_GPU=-1`, every request sends **num_gpu=99** to Ollama (generate and stream), so the app never asks for CPU.

3. **Config** (`.env` and `server/config.py`): `OLLAMA_NUM_GPU=-1` means “NVIDIA GPU 1 only”.

## Scripts (all set for NVIDIA GPU 1)

| Script | Purpose |
|--------|--------|
| **START_OLLAMA_GPU.bat** | Starts Ollama with GPU 1–only env in this window. Use this to run Ollama. |
| **SET_OLLAMA_GPU_ENV.bat** | Sets Windows user env vars once so any future Ollama start (tray, Start menu) uses NVIDIA GPU 1. Then quit and restart Ollama. |
| **RESTART_EVERYTHING.bat** | Stops Ollama and backend, starts Ollama (NVIDIA GPU 1 only) in a new window, then starts the backend. |

## What you must do

- Start Ollama via **START_OLLAMA_GPU.bat**, or run **SET_OLLAMA_GPU_ENV.bat** once and restart Ollama.
- Use a **model that fits in your NVIDIA VRAM** (e.g. tinyllama, llama3.2:1b). If the model is too large, Ollama may try CPU and fail with "unable to allocate CPU buffer".
