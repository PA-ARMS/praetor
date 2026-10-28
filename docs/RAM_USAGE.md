# What Uses RAM in This System (32GB and reducing usage)

This document lists components that consume system RAM so you can turn off or shrink them if you're hitting 32GB.

---

## 1. Ollama (separate process)

- **Chat model** (e.g. `initium/law_model`) – we use **GPU 1** (NVIDIA), so the model lives in VRAM, not system RAM. If Ollama ever falls back to CPU, it can use **several GB** of RAM.
- **Embedding model** (`nomic-embed-text`) – used for RAG search. Ollama keeps it loaded; it can use **~500MB–1GB** RAM (or VRAM if Ollama puts it on GPU). You can't disable it if you use RAG chat; you can avoid RAG by not uploading docs and using chat with no context (not recommended for legal answers).

**To reduce:** Ensure Ollama runs with **GPU only** (`START_OLLAMA_GPU.bat` with `CUDA_VISIBLE_DEVICES=1`) so the chat model stays on the NVIDIA GPU and doesn't use system RAM.

---

## 2. Backend Python process – in‑memory caches

These grow with use and are held in the backend process:

| Component | Config / location | Default | RAM impact |
|-----------|-------------------|--------|------------|
| **RAG query cache** | `rag_service.py` – `_cache_capacity` | 2048 entries | High – each entry stores full search results (many vectors + text). 2048 is a lot. |
| **Ollama embedding cache** | `ollama_service.py` – `_embed_capacity` | 4096 entries | Medium – each entry is one 768‑dim float vector (~3KB). 4096 × 3KB ≈ 12MB+; keys and overhead add more. |

**To reduce:** Set in `.env` (see “Low‑RAM .env” below):

- `RAG_QUERY_CACHE_SIZE=256`
- `OLLAMA_EMBED_CACHE_SIZE=512`

These are now in config; defaults 256 / 512. Set RAG_QUERY_CACHE_SIZE and OLLAMA_EMBED_CACHE_SIZE in .env to tune.

---

## 3. Backend – optional ML models (document pipeline)

When you **upload documents** (Upload Docs or RAG ingest), the document pipeline can load several models into the **same Python process**. All of these use RAM:

| Feature | Config | What loads | Approx. RAM |
|--------|--------|------------|-------------|
| **Document reader** | `DOCUMENT_READER_ENABLED` | Unstructured library (layout/parsing) | Hundreds of MB |
| **Neural OCR** | `NEURAL_OCR_ENABLED` | EasyOCR (neural net) | ~500MB–1GB+ |
| **Summarization** | `SUMMARIZATION_MODEL_ENABLED` | BART (transformers) | ~1–2GB |
| **Entity extraction** | `ENTITY_EXTRACTION_ENABLED` | spaCy NER model | ~100–500MB |
| **Table extraction** | `TABLE_EXTRACTION_ENABLED` | Camelot/Tabula | Lower |
| **BGE embeddings** | `BGE_EMBEDDINGS_ENABLED` | BGE sentence‑transformers | ~1GB+ (if enabled) |

They load **on first use** (first document that needs that step). Once loaded, they stay in RAM until the backend restarts.

**To reduce:** For **chat‑only** (no or minimal document processing), disable these in `.env`:

```env
DOCUMENT_READER_ENABLED=false
NEURAL_OCR_ENABLED=false
SUMMARIZATION_MODEL_ENABLED=false
ENTITY_EXTRACTION_ENABLED=false
TABLE_EXTRACTION_ENABLED=false
BGE_EMBEDDINGS_ENABLED=false
```

RAG **search** still works (Ollama `nomic-embed-text` does embeddings). Only **upload-time** extraction/summary/entities are disabled; existing indexed documents remain searchable.

---

## 4. ChromaDB (RAG vector DB)

- **Location:** `./data/chroma_db` (on disk).
- **RAM:** ChromaDB may cache index/data in process memory. Large corpora (tens of thousands of chunks) can add **hundreds of MB to a few GB** depending on usage and Chroma version.

**To reduce:** Don’t grow the corpus unnecessarily. There’s no simple “run Chroma with less RAM” flag; reducing corpus size or number of queries (and RAG query cache size) is the main lever.

---

## 5. Scenario DB (optional)

- **Config:** `SCENARIO_DB_ENABLED=false` (already off in your setup).
- When enabled: another ChromaDB + embeddings, so extra RAM and CPU for scenario search.

**To reduce:** Keep `SCENARIO_DB_ENABLED=false` for chat‑only.

---

## 6. Summary – “Chat only, minimal RAM” settings

Use these in `.env` if 32GB is getting full:

```env
# Chat only – no heavy document pipeline models
DOCUMENT_READER_ENABLED=false
NEURAL_OCR_ENABLED=false
SUMMARIZATION_MODEL_ENABLED=false
ENTITY_EXTRACTION_ENABLED=false
TABLE_EXTRACTION_ENABLED=false
BGE_EMBEDDINGS_ENABLED=false

# Smaller in‑process caches (optional; defaults are already 256 / 512)
RAG_QUERY_CACHE_SIZE=256
OLLAMA_EMBED_CACHE_SIZE=512
```

And:

- Run Ollama with **GPU only** (`START_OLLAMA_GPU.bat`) so the chat model uses VRAM, not RAM.
- Keep **SCENARIO_DB_ENABLED=false**.

After changing `.env`, **restart the backend** so it reloads config and doesn’t load the disabled models.

---

## 7. Quick checklist

| Item | Action |
|------|--------|
| Ollama using CPU? | Use `START_OLLAMA_GPU.bat` (GPU 1 only). |
| RAG cache too big? | Set `RAG_QUERY_CACHE_SIZE=256` (once supported). |
| Embed cache too big? | Set `OLLAMA_EMBED_CACHE_SIZE=512` (once supported). |
| Document uploads? | Disable DOCUMENT_READER, NEURAL_OCR, SUMMARIZATION, ENTITY_EXTRACTION, TABLE_EXTRACTION, BGE if you don’t need them. |
| Scenario analysis? | Keep SCENARIO_DB_ENABLED=false. |
| ChromaDB huge? | Reduce corpus or avoid ingesting very large sets. |
