# Virginia Law Annual Corpus Update

The legal AI keeps Virginia statutes current by **re-downloading official CSV exports** from [law.lis.virginia.gov](https://law.lis.virginia.gov) and **re-indexing** them into ChromaDB. This is separate from server uptime automation (`SETUP_AUTOMATION.bat`).

## When to run

| Timing | Why |
|--------|-----|
| **July 15** (scheduled default) | Most session laws from the Virginia General Assembly are effective by mid-year. |
| **After a major session** | Run manually if you need new statutes immediately. |
| **After system restore** | Rebuild RAG from official sources. |

## Watch rebuild progress (GUI)

While a rebuild is running, open a live progress window:

```bat
SHOW_VA_REBUILD_PROGRESS.bat
```

It reads `data/va_corpus_update_progress.json` (updated every ~500 ingested sections) and shows overall % and current step. You can also start a rebuild from that window.

---

## Quick commands

**One-time manual update (recommended first run):**

```bat
UPDATE_VA_LAWS.bat
```

Or:

```bash
python scripts/update_va_legal_corpus.py --force
```

**Schedule automatic yearly refresh (requires Administrator):**

```bat
SETUP_VA_LAW_UPDATE.bat
```

Optional: run immediately after scheduling:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_va_law_update_task.ps1 -RunNow
```

## What the update does

1. Downloads all Code of Virginia CSV files (`data/va_csv/`)
2. Purges old Virginia Code vectors from ChromaDB
3. Re-ingests every section with stable `va_code_*` document IDs
4. Runs citation spot-check searches (e.g. § 18.2-57.2, § 8.01-195.1)
5. Writes `data/va_law_update_status.json` with results

Scheduled runs log to `logs/va_law_update.log`.

## Options

```bash
python scripts/update_va_legal_corpus.py --force              # re-download CSVs (yearly default)
python scripts/update_va_legal_corpus.py --download-only      # download only
python scripts/update_va_legal_corpus.py --ingest-only        # use existing CSVs
python scripts/update_va_legal_corpus.py --include-regulations  # also VA Admin Code HTML (slower)
```

## AI Laws alignment

Article II requires citing the **most recent** statutes. This pipeline updates the **RAG corpus**; attorneys should still verify effective dates and session acts before filing.

## Troubleshooting

| Issue | Action |
|-------|--------|
| Download failures | Check internet; open https://law.lis.virginia.gov/CSV/ |
| Ingest very slow | Normal for ~30k+ sections; run overnight |
| Search tests fail | Re-run ingest; check Ollama/embedding service is up |
| Task did not run | Task Scheduler → `AKLegalVault_VA_LawUpdate` → History |

## Related files

| File | Purpose |
|------|---------|
| `scripts/update_va_legal_corpus.py` | Main update pipeline |
| `scripts/download_va_csv.py` | LIS CSV download |
| `scripts/verify_and_complete_database.py` | Ingest + search tests |
| `scripts/setup_va_law_update_task.ps1` | Windows scheduled task |
| `data/va_law_update_status.json` | Last run status |
