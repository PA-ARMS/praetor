# "Unable to allocate CPU buffer" – What it means and how to fix it

## What’s going on

The error:

```text
Ollama HTTP error: 500 - {"error":"llama runner process has terminated: error loading model: unable to allocate CPU buffer"}
```

means **Ollama is loading the model into normal (CPU) RAM and running out of memory**. It is **not** using your GPU (or not using it enough), so the model is being put in RAM and your system doesn’t have enough free RAM.

So the problem is: **the model is being loaded on CPU instead of GPU** (or your machine doesn’t have enough RAM for the model even on CPU).

---

## Fix 1: Make sure Ollama uses the GPU (if you have one)

1. **Quit Ollama fully**  
   - Windows: right‑click the Ollama icon in the system tray → Quit.  
   - Or from a terminal: `taskkill /IM ollama.exe /F` (then start it again as below).

2. **Start Ollama with GPU enabled**  
   From a **new** Command Prompt or PowerShell, run **one** of these **before** starting Ollama:

   **Option A – Temporary (this window only)**  
   ```batch
   set OLLAMA_NUM_GPU=99
   ollama serve
   ```

   **Option B – Integrated AMD + discrete NVIDIA (use NVIDIA only)**  
   If GPU 0 is integrated AMD and GPU 1 is NVIDIA, force Ollama to use the NVIDIA card:
   ```batch
   set CUDA_VISIBLE_DEVICES=1
   set OLLAMA_NUM_GPU=99
   ollama serve
   ```

   **Option C – Use the project script**  
   From the `LAWFIRMAI` folder run:
   ```batch
   START_OLLAMA_GPU.bat
   ```
   (That script sets `CUDA_VISIBLE_DEVICES=1` and `OLLAMA_NUM_GPU=99`, then runs `ollama serve`.)

3. **Confirm GPU is used**  
   In another terminal run:
   ```batch
   ollama ps
   ```
   You want to see GPU usage (e.g. “100% GPU” or a mix of GPU/CPU), **not** “100% CPU”.

4. **Restart the backend**  
   Run `START_BACKEND.bat` from the `LAWFIRMAI` folder so chat uses the same small model and GPU settings.

If after this you still get “unable to allocate CPU buffer”, Ollama may not be using the GPU (driver, build, or no GPU). Then use Fix 2.

---

## Fix 2: Use a very small model (works on CPU/RAM only)

If you don’t have a GPU or Ollama still won’t use it, use a **tiny** model so it fits in RAM:

1. **Use the smallest model**  
   In the project root, in `.env`, set:
   ```env
   OLLAMA_MODEL=tinyllama
   ```
   (Or keep `llama3.2:1b` if you prefer.)

2. **Pull and run it**  
   ```batch
   ollama pull tinyllama
   ollama run tinyllama
   ```
   Leave that running or close it; the backend will load the model when you chat.

3. **Restart the backend**  
   From `LAWFIRMAI` run:
   ```batch
   START_BACKEND.bat
   ```

4. **Free RAM**  
   Close other heavy apps so Windows has enough free RAM for the model (~1–2 GB for tinyllama/1B models).

---

## Summary

| Situation | What to do |
|-----------|------------|
| You have an NVIDIA GPU | Quit Ollama, run `set OLLAMA_NUM_GPU=99` then `ollama serve` (or `START_OLLAMA_GPU.bat`), then restart backend. |
| No GPU or Ollama still uses CPU | Set `OLLAMA_MODEL=tinyllama` in `.env`, run `ollama pull tinyllama`, restart backend, free RAM. |
| Still failing | Try closing other programs, or use a smaller/quantized model and ensure `.env` is in the project folder so the backend reads it. |

The app sends `num_gpu=-1` (or 99) to Ollama so it prefers GPU. If Ollama was started without GPU configured, it can still fall back to CPU and hit “unable to allocate CPU buffer” – that’s why starting Ollama with `OLLAMA_NUM_GPU=99` (or using the script) and/or using `tinyllama` fixes it.
