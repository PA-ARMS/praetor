# Get the Chat Portion Working

This guide gets the **Chat** tab working so you can send legal research queries and get AI responses.

## What You Need

1. **Backend** (FastAPI) on port **5001**
2. **Frontend** (React/Vite) on port **3000**
3. **Ollama** running with the legal model pulled
4. **One user account** (create the first account via Sign up on the login screen)

## Step 1: Start Ollama and pull the model

Ollama must be running and the configured model must be available.

```bash
# Start Ollama (if not already running). On Windows, Ollama often runs as a service.
ollama serve

# Pull the legal model (config default: initium/law_model)
ollama run initium/law_model
```

If you prefer a smaller/faster model, set `OLLAMA_MODEL` in `.env` (e.g. `OLLAMA_MODEL=llama3.2`) and run that model in Ollama. The **Chat ready** status on the app will show whether the backend can see Ollama and the model.

## Step 2: Start the backend

From the project root (`LAWFIRMAI`):

```batch
START_BACKEND.bat
```

- Backend listens on **http://0.0.0.0:5001**.
- On startup it verifies **AI Laws** (checksum); if that fails, the server will not start.
- Ensure port 5001 is free (the script tries to free it).

If the backend fails to start, check the console for:
- **AI Laws verification failed** → restore `config/ai_laws.json` and do not edit it.
- **Port in use** → close the app using 5001 or run `START_BACKEND.bat` as administrator once.
- **Module not found** → from repo root run: `pip install -r server/requirements.txt`

## Step 3: Start the frontend

From the project root:

```batch
START_FRONTEND.bat
```

- Frontend runs at **http://localhost:3000** (and, if configured, on your LAN).
- In dev, API calls use the Vite proxy to **http://localhost:5001** when `VITE_API_URL` is not set.
- If the frontend runs on another machine, create `client/.env` with:
  ```env
  VITE_API_URL=http://YOUR_BACKEND_IP:5001
  ```
  Then restart the frontend (`npm run dev` in `client`).

## Step 4: Create an account and log in

1. Open **http://localhost:3000** in your browser.
2. If there are **no users yet**, use **Sign up** to create the first account (that user becomes Admin).
3. Otherwise, log in with **username** and **password**.

You must be **logged in** to use Chat; the **Chat** tab uses `/api/chat/simple`, which requires authentication.

## Step 5: Use Chat

1. After login, open the **Chat** tab.
2. Check the status under the welcome message:
   - **✓ Chat ready** – backend and Ollama/model are OK; you can send messages.
   - **⚠ …** – read the message (e.g. “Ollama not reachable”, “Model 'initium/law_model' not in Ollama”).
3. Type a question and send. The backend will:
   - Run RAG search (if the corpus has documents) or use “No relevant documents found.”
   - Build a system prompt from the AI Laws and context.
   - Call Ollama to generate the response.
   - Save the message and return the answer and sources.

## Troubleshooting

| Symptom | What to do |
|--------|------------|
| **Chat not ready – Backend not reachable** | Start backend (`START_BACKEND.bat`). If frontend is on another PC, set `VITE_API_URL` in `client/.env` to `http://BACKEND_IP:5001` and restart frontend. |
| **Chat not ready – Ollama not reachable** | Start Ollama (`ollama serve`). Default backend URL is `http://localhost:11434`; override with `OLLAMA_BASE_URL` in `.env` if needed. |
| **Chat not ready – Model missing** | Run `ollama run initium/law_model` (or whatever `OLLAMA_MODEL` is in `.env`). |
| **"unable to allocate CPU buffer"** | See **docs/OLLAMA_CPU_BUFFER_ERROR.md**: run `START_OLLAMA_GPU.bat` or set `OLLAMA_MODEL=tinyllama` and `ollama pull tinyllama`. |
| **401 or “Session expired” when sending a message** | Log out and log in again. Create an account via Sign up if you have no user yet. |
| **500 error when sending a message** | Check backend console. Typical causes: Ollama timeout, model not loaded, or RAG/Chroma error (RAG failures are caught and chat continues with “No relevant documents found”). |
| **RAG returns no sources** | Normal if the ChromaDB corpus is empty. Ingest sources with `scripts/ingest_sources.py` and manifests under `data/manifests/`, or upload documents via the **Upload Docs** tab so they are indexed. |

## Quick test without RAG data

Chat works even with an **empty** RAG corpus: the context becomes “No relevant documents found.” and the model is instructed to say so when it has no sources. For real legal answers, add data (ingest scripts or uploads) so RAG can retrieve relevant excerpts.

## Summary

1. **Ollama**: `ollama serve` and `ollama run initium/law_model`
2. **Backend**: `START_BACKEND.bat` (port 5001)
3. **Frontend**: `START_FRONTEND.bat` (port 3000)
4. **Browser**: http://localhost:3000 → Sign up (first user) or Log in → Chat tab → ask a question
