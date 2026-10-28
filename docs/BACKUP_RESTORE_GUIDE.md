# Backup and Restore Guide

This guide covers backing up and restoring the Virginia Legal AI (AKLAWMS) system data.

## Backup Schedule

- **Frequency:** Daily (recommended). Run via Windows Task Scheduler or cron.
- **Retention:** 30 days default (configurable with `--keep-days`).
- **Location:** `data/backups/` (created automatically).

## Running a Backup

### Basic backup (SQLite only)

```bash
python scripts/backup_database.py
```

Creates `data/backups/legal_ai_YYYYMMDD_HHMMSS.db`. Old backups older than 30 days are removed.

### Backup with ChromaDB (RAG corpus)

```bash
python scripts/backup_database.py --include-chromadb
```

ChromaDB can be large; use for full restores or less frequently.

### Custom retention

```bash
python scripts/backup_database.py --keep-days=60
```

Keeps backups for 60 days.

### Windows Task Scheduler

1. Open Task Scheduler.
2. Create Basic Task → Daily → Set time (e.g. 2:00 AM).
3. Action: Start a program.
4. Program: `python` (or full path to your Python executable).
5. Arguments: `scripts/backup_database.py` (run from project root, or use full path to script).
6. Start in: `C:\LAWFIRMAI` (your project root).

Alternatively use `scripts/schedule_backup.bat` if you have one configured.

## What Gets Backed Up

| Item | Script | Location |
|------|--------|----------|
| SQLite database | `backup_database.py` | `data/legal_ai.db` → `data/backups/legal_ai_*.db` |
| ChromaDB (optional) | `--include-chromadb` | `data/chroma_db` → `data/backups/chroma_db_*` |

**Not included in script:** `data/sources/`, `data/scenarios/`, `data/templates/`, `config/`. Back these up separately if needed (e.g. copy entire `data/` and `config/` periodically).

## Restore Procedure

### Restore SQLite database

1. **Stop the application** (backend server and any processes using the database).
2. **Rename or move** the current database:
   ```bash
   move data\legal_ai.db data\legal_ai.db.old
   ```
3. **Copy** the backup file to the live path:
   ```bash
   copy data\backups\legal_ai_YYYYMMDD_HHMMSS.db data\legal_ai.db
   ```
4. **Start the application** and verify (e.g. login, run a query).

### Restore ChromaDB (if you backed it up)

1. Stop the application.
2. Rename or remove the current ChromaDB folder:
   ```bash
   rename data\chroma_db data\chroma_db.old
   ```
3. Copy the backup folder:
   ```bash
   xcopy /E /I data\backups\chroma_db_YYYYMMDD_HHMMSS data\chroma_db
   ```
4. Start the application.

## Last Backup Time

The backup script writes `data/backups/last_backup.json` with the timestamp of the last successful backup. The Admin dashboard and `/api/system/status` can show "Last backup" from this file.

## Troubleshooting

- **"Database file not found"**: Ensure the server has created `data/legal_ai.db` at least once (run the app once), or that you are running the script from the project root where `data/` exists.
- **Permission errors**: Run with a user that has read/write access to `data/` and `data/backups/`.
- **Disk space**: Ensure enough free space for the copy (SQLite file size ≈ current DB size; ChromaDB can be large).

## Compliance

See [COMPLIANCE.md](COMPLIANCE.md) for retention and backup policy. Audit logs are stored in the SQLite database and are included in the database backup.
