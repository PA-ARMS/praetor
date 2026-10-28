# Reinstall Ollama on Windows

## Step 1: Stop Ollama

Close Ollama completely:

- Right-click the **Ollama icon** in the system tray (near the clock) → **Quit**
- Or run: **STOP_OLLAMA.bat** (in this folder) to force-stop the process

## Step 2: Uninstall Ollama

1. Press **Win + I** to open **Settings**
2. Go to **Apps** → **Installed apps** (or **Apps & features**)
3. Search for **Ollama**
4. Click the **⋮** next to Ollama → **Uninstall**
5. When asked, choose whether to **delete model files**:
   - **Keep models** if you want to reuse them after reinstall (saves download time)
   - **Delete** if you want a clean slate

## Step 3: Download and install Ollama again

1. Open: **https://ollama.com/download**
2. Download **Ollama for Windows** (OllamaSetup.exe)
3. Run **OllamaSetup.exe** and follow the prompts
4. Allow it to start in the system tray when installation finishes

## Step 4: Set GPU 1 only (for this project)

After reinstalling, set Ollama to use **GPU 1 only** (NVIDIA):

1. Run **SET_OLLAMA_GPU_ENV.bat** once (in the LAWFIRMAI folder)
2. **Quit Ollama** from the tray again
3. Start Ollama (from Start menu or run `ollama serve`)

Or always start Ollama with **START_OLLAMA_GPU.bat** so it uses GPU 1.

## Step 5: Pull the model

In a Command Prompt or PowerShell:

```batch
ollama pull tinyllama
```

(Or whatever model is in your `.env`: `ollama pull llama3.2:1b`, etc.)

## Step 6: Start the system

Run **RESTART_EVERYTHING.bat** to start Ollama (GPU 1) and the backend, then open http://localhost:3000

---

**Quick link:** [Download Ollama](https://ollama.com/download)
