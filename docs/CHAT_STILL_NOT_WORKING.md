# Chat still not working – "unable to allocate CPU buffer"

If you switched to **tinyllama** and **restarted the backend** but still get the error, do this in order.

---

## Step 1: Use the smallest model

In **`.env`** you should have (and it's already set):

```env
OLLAMA_MODEL=tinyllama
```

Pull it if you haven’t:

```batch
ollama pull tinyllama
```

---

## Step 2: Make Ollama use NVIDIA GPU (Windows, once)

So Ollama stops using CPU and doesn’t run out of RAM:

1. **Run as administrator** (right‑click → Run as administrator):
   ```batch
   SET_OLLAMA_GPU_ENV.bat
   ```
   That sets **CUDA_VISIBLE_DEVICES=1** and **OLLAMA_NUM_GPU=99** for your user.

2. **Quit Ollama**  
   Right‑click Ollama in the system tray → **Quit**.

3. **Start Ollama again**  
   From the Start menu or run:
   ```batch
   ollama serve
   ```
   It will now use GPU 1 (NVIDIA) only.

---

## Step 3: Restart the backend

From the LAWFIRMAI folder:

```batch
START_BACKEND.bat
```

Or use **RESTART_EVERYTHING.bat** (it starts Ollama with GPU env in its own window).

---

## Step 4: Try Chat

Open the app, go to Chat, send a short message. It should use **tinyllama** and no longer hit "unable to allocate CPU buffer".

---

## If it still fails

- **Ollama not using GPU**  
  After Step 2, open a **new** Command Prompt and run:
  ```batch
  ollama run tinyllama
  ```
  If you still get the same error, Ollama may not have GPU support on this machine (e.g. no CUDA, or wrong build). Install the latest Ollama from https://ollama.com and try again.

- **Backend using wrong model**  
  Confirm `.env` has `OLLAMA_MODEL=tinyllama` and no other `OLLAMA_MODEL=` line. Then run **START_BACKEND.bat** again.

- **Very low RAM**  
  Close other apps to free a few GB, then try again. TinyLlama needs about 1–2 GB free.
