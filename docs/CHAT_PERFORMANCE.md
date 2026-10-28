# Chat Response Time — Performance Guide

If legal chat feels slow, these are the main factors and fixes.

## What takes time

| Step | Typical impact |
|------|----------------|
| **LLM generation** (`OLLAMA_MODEL`) | Largest — 7B+ models (e.g. `mistral:latest`) are much slower than `llama3.2:1b` or `qwen2.5:3b` |
| **Context size** (`OLLAMA_NUM_CTX`) | 32768 context is slow; **8192** is the new default |
| **RAG search** | Each synonym variant = one embed + vector search (now capped at **4**, run **in parallel**) |
| **Attachments** | Upload OCR + optional BART summary before chat even starts |
| **No streaming** | UI waits for the full answer (streaming endpoint planned; use smaller model meanwhile) |

## Recommended `.env` for speed (still accurate for VA law)

```env
OLLAMA_MODEL=llama3.2:3b
OLLAMA_NUM_CTX=8192
BGE_EMBEDDINGS_ENABLED=true
CHAT_RAG_MAX_VARIATIONS=4
CHAT_SIMPLE_N_RESULTS=8
CHAT_SIMPLE_MAX_OUTPUT_TOKENS=768
```

Pull the model once: `ollama pull llama3.2:3b`

For maximum quality (slower): `initium/law_model` or `mistral:latest` with `OLLAMA_NUM_CTX=16384`.

## After changing `.env`

Restart the backend (and Ollama if you changed GPU/model settings).

## Check timing in logs

Look for lines like:

```
[Chat/simple] RAG search_fast: 8 hits in 1.23s
[Chat/simple] LLM generate: 12.45s (max_tokens=768)
[Chat/simple] total request: 14.10s
```

## Code changes (already applied)

- `/api/chat/simple` uses `search_fast` (no scenario case DB round-trip).
- Synonym searches run in parallel (max 4 at a time).
- Fewer sources and shorter snippets in the LLM prompt.
- Default `OLLAMA_NUM_CTX` reduced from 32768 → 8192.
