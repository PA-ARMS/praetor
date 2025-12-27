# Citation Extraction and Exact Matching

## Overview

This system now automatically extracts Virginia Code citations from documents during ingestion and stores them in metadata. This enables **exact citation matching** in searches, which is critical for a legal research system.

## What Was Changed

### 1. Citation Extraction Method
- Added `_extract_citation_from_text()` method to `RAGService`
- Extracts citations from document text using multiple patterns:
  - `§ 46.2-391` (explicit section symbol)
  - `Section 46.2-391` (section keyword)
  - `Va. Code Ann. § 46.2-391` (full Virginia Code format)
  - `Code of Virginia § 46.2-391` (alternative format)
- Searches first 2000 characters to find primary citation
- Normalizes all citations to `§ 46.2-391` format

### 2. Automatic Citation Extraction
- Modified `add_document()` to automatically extract citations
- Citations are stored in document metadata
- Chunks inherit citation from parent document

### 3. Ingestion Script Updates
- Updated `scripts/ingest_sources.py` to extract citations during ingestion
- Logs extracted citations for visibility

### 4. Re-indexing Script
- Created `scripts/reindex_with_citations.py` to update existing documents
- Adds citations to documents that don't have them

## How It Works

### During Document Ingestion

1. Document text is analyzed for citation patterns
2. First citation found is extracted and normalized
3. Citation is stored in metadata: `{"citation": "§ 46.2-391"}`
4. Document (and all chunks) include citation in metadata

### During Search

1. If query contains a citation, exact match is attempted:
   ```python
   exact_results = collection.get(where={"citation": "§ 46.2-391"})
   ```
2. If exact match found, it's returned as top result
3. Falls back to semantic search if no exact match

### Citation Verification

The guardrails service now checks citations against:
- Retrieved source documents (as before)
- **NEW**: Exact citation matches from database

This reduces false warnings for statutes that exist in the database but weren't in top search results.

## Usage

### For New Documents

Citations are automatically extracted when you:
- Upload documents via the API
- Run the ingestion script
- Add documents programmatically

No additional steps required!

### For Existing Documents

To add citations to existing documents in your database:

```bash
python scripts/reindex_with_citations.py
```

This will:
- Scan all documents in the vector database
- Extract citations from document text
- Update metadata with citations
- Show progress and statistics

**Note**: This may take a while for large databases. The script processes documents in batches and logs progress.

## Benefits

1. **Exact Matching**: Queries with citations now find exact statute matches
2. **Fewer False Warnings**: Citations that exist in DB but weren't in top results are verified
3. **Better Accuracy**: AI responses can cite statutes that are actually in your database
4. **Faster Searches**: Exact matches bypass semantic search when citation is known

## Example

**Before:**
- Query: "What is § 46.2-391?"
- Search: Semantic search returns top 50 results
- Result: Statute might not be in top 50 → flagged as "not found"

**After:**
- Query: "What is § 46.2-391?"
- Search: Exact match finds document with `citation: "§ 46.2-391"`
- Result: Exact match returned immediately → verified

## Technical Details

### Citation Patterns Supported

- `§ 46.2-391` - Standard format
- `Section 46.2-391` - Section keyword
- `Va. Code Ann. § 46.2-391` - Full format
- `Code of Virginia § 46.2-391` - Alternative format
- `46.2-391` - Bare number (fallback, less reliable)

### Normalization

All citations are normalized to: `§ 46.2-391` format
- Adds `§` symbol if missing
- Preserves original number format
- Handles subsections (e.g., `46.2-391.1`)

### Chunking

When documents are chunked:
- Parent document's citation is inherited by all chunks
- Each chunk has `citation` in metadata
- Exact matching works for both full documents and chunks

## Troubleshooting

### Citations Not Being Extracted

1. Check document text contains citation in supported format
2. Verify citation appears in first 2000 characters
3. Check logs for extraction messages

### Re-indexing Not Working

1. Ensure you have write access to ChromaDB
2. Check database isn't locked by another process
3. Review error logs for specific issues

### Exact Match Still Not Working

1. Verify citation format matches exactly (including `§` symbol)
2. Check metadata actually contains citation field
3. Ensure re-indexing completed successfully

## Future Enhancements

Potential improvements:
- Extract multiple citations from documents (not just primary)
- Support for case citations (e.g., `Smith v. Jones, 123 Va. 456`)
- Citation relationships (related statutes)
- Citation validation against official Virginia Code









