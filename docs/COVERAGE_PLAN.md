# Legal Database Coverage Plan

This document outlines the plan for achieving comprehensive legal coverage across criminal, civil, and administrative law in the LAWFIRMAI system.

## Implemented Changes (Completed)

### 1. Ingestion Limits Raised
- **`scripts/ingest_sources.py`**: Default limits raised from 200/2000 to 5000/50000
- **`scripts/verify_and_complete_database.py`**: Per-source HTML limit raised from 500 to 5000
- Override via env: `MAX_INGEST_PER_SOURCE`, `MAX_INGEST_TOTAL`

### 2. Virginia Administrative Code (VAC) Citation Support
- **`server/services/rag_service.py`**:
  - `_extract_citation()`: Now extracts VAC format (e.g., `18 VAC 120-10-10`)
  - `_extract_citation_from_text()`: Extracts VAC citations during ingestion
- **`server/routes/chat.py`**: Citation whitelist now includes VAC regulations

### 3. Administrative Law Synonyms
- **`config/legal_synonyms.json`**: Added mappings for:
  - license suspension, professional license, administrative hearing
  - agency decision, DMV suspension, occupational license
  - administrative procedure, Virginia Administrative Code
  - driver's license, contract, divorce, custody, child support
  - workers compensation, unemployment

### 4. Administrative Law Guidance in Prompts
- **`server/services/guardrails_service.py`**: Added:
  - VAC citation format (e.g., 18 VAC 120-10-10)
  - Chevron/Auer deference, VAPA, exhaustion of remedies

### 5. Statute Relationships Expanded
- **`config/statute_relationships.json`**: Added civil/administrative entries:
  - 46.2-391 (DMV License Suspension)
  - 54.1 (Professions and Occupations)
  - 2.2-4000 (VAPA)
  - 8.01-243 (Statute of Limitations)
  - 20-91 (Divorce Grounds)

---

## Progress GUI

For an on-screen progress display, run:

```bash
python scripts/ingest_progress_gui.py
# Or double-click: RUN_INGEST_GUI.bat
```

Shows live output, step progress, and a progress bar.

---

## Annual Virginia Law Update (Automated)

After each General Assembly session, refresh statutes from LIS:

```bat
UPDATE_VA_LAWS.bat
```

Schedule yearly (July 15, 2:00 AM):

```bat
SETUP_VA_LAW_UPDATE.bat
```

See **[VA_LAW_ANNUAL_UPDATE.md](VA_LAW_ANNUAL_UPDATE.md)** for full details, options, and troubleshooting.

---

## Data Build Steps (To Run)

### Step 1: Download Virginia Code CSV
```bash
python scripts/download_va_csv.py
```

### Step 2: Download Other Sources
```bash
python scripts/download_all_sources.py
# Or: python scripts/complete_legal_database.py  (downloads + ingests)
```

### Step 3: Ingest with Raised Limits
```bash
# Full build (uses new defaults: 5000 per source, 50000 total)
python scripts/verify_and_complete_database.py

# Or for manifest-based ingestion:
MAX_INGEST_PER_SOURCE=5000 MAX_INGEST_TOTAL=50000 python scripts/ingest_sources.py
```

### Step 4: Ingest SCOTUS (if not already done)
```bash
python scripts/ingest_scotus_opinions.py
```

### Step 5: Verify Coverage
```bash
python scripts/check_source_completeness.py
```

---

## Coverage Targets

| Source | Target | Priority |
|--------|--------|----------|
| VA Code | 10,000+ sections | High |
| VA Admin Code | 1,000+ regulations | High |
| VA Register | 500+ | Medium |
| SCOTUS | 1,000+ opinions | High |
| US Code | 5,000+ sections | Medium |
| CFR | 500+ sections | Medium |
| VA/4th Cir cases | 5,000+ | Medium |

---

## File Reference

| File | Purpose |
|------|---------|
| `scripts/ingest_sources.py` | Manifest-based ingestion |
| `scripts/verify_and_complete_database.py` | Full VA + HTML source ingestion |
| `scripts/update_va_legal_corpus.py` | Annual VA Code download + RAG refresh |
| `scripts/complete_legal_database.py` | Download + ingest all |
| `scripts/check_source_completeness.py` | Verify coverage |
| `config/legal_synonyms.json` | Vernacular → legal term mapping |
| `config/statute_relationships.json` | Statute/regulation relationships |
| `server/.env.example` | Ingestion env vars documented |
