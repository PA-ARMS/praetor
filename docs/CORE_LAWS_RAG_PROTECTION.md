# Core Laws RAG Protection

The system keeps a **custom RAG** that contains the **core laws** (Virginia Code, SCOTUS, federal and state statutes/case law ingested by scripts). This data is **read-only** from the app: it cannot be deleted or overwritten by users.

## What is protected

- **By doc_id prefix:** Any document whose `doc_id` starts with `va_code_` (Virginia Code sections ingested from CSV).
- **By source metadata:** Documents whose `source` metadata matches system-ingested sources, including:
  - Code of Virginia / VA Code / Virginia Code
  - SCOTUS Opinions, SCOTUS Portal, Supreme Court of the United States
  - Virginia Administrative Code, VA Register, Virginia Courts, VA Opinions
  - United States Code, CFR, Federal Register, US Courts Rules, etc.

User uploads use the **filename** as `source` and do not use the `va_code_` prefix, so they are not treated as core laws.

## How it is enforced

1. **Backend (`server/services/rag_service.py`)**
   - `_is_core_laws_document(doc_id, metadata)` returns True for the above.
   - `delete_document(doc_id)` checks before deleting; if the document is core laws, it raises `PermissionError` and **no delete** is performed.
   - `list_documents()` includes an `is_core` flag on each document so the UI can show "System" and hide the Remove button.

2. **API (`server/routes/rag.py`)**
   - `DELETE /api/rag/documents/{doc_id}` catches `PermissionError` and returns **403** with the message:  
     `"Cannot delete: this document is part of the system's core laws. Only user-uploaded documents can be removed."`

3. **Frontend (`client/src/components/UploadDocument.jsx`)**
   - Indexed documents list shows a **"System"** badge for documents with `is_core === true`.
   - The **Remove** button is not shown for core documents.

## Adding more core sources

To protect additional system-ingested sources, add their **source name** (lowercase, as it appears in metadata) to `CORE_LAW_SOURCE_NAMES` in `server/services/rag_service.py`, or use a dedicated `doc_id` prefix and check it in `_is_core_laws_document`.

## What is not touched

- **Search and retrieval:** Core laws remain in the same `legal_corpus` collection and are used for chat and RAG search exactly as before.
- **Ingestion scripts:** Scripts like `verify_and_complete_database.py` and `ingest_sources.py` can still add/update core content when you run them intentionally (they are not part of the normal app UI).
- **AI Laws:** The immutable AI Laws in `config/ai_laws.json` are separate and enforced by the guardrails/checksum system; they are not stored in ChromaDB.
