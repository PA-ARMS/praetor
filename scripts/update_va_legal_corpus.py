#!/usr/bin/env python3
"""
Annual Virginia legal corpus refresh.

Downloads current Code of Virginia CSV exports from law.lis.virginia.gov,
re-ingests statutes into ChromaDB, runs spot-check searches, and writes
data/va_law_update_status.json.

Designed to run:
  - Manually:  python scripts/update_va_legal_corpus.py
  - Scheduled: SETUP_VA_LAW_UPDATE.bat (July 15 yearly after GA session)

Usage:
  python scripts/update_va_legal_corpus.py              # download + re-ingest
  python scripts/update_va_legal_corpus.py --force      # re-download CSVs
  python scripts/update_va_legal_corpus.py --download-only
  python scripts/update_va_legal_corpus.py --ingest-only  # use existing CSVs
  python scripts/update_va_legal_corpus.py --include-regulations  # also VA Admin HTML
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from corpus_progress import init_progress, write_progress
from download_va_csv import download_all_va_csv
from verify_and_complete_database import (
    count_csv_sections,
    ingest_va_csv_complete,
    ingest_va_uncodified_acts,
    test_search_functionality,
)
from server.services.rag_service import rag_service

STATUS_PATH = PROJECT_ROOT / "data" / "va_law_update_status.json"
LOCK_PATH = PROJECT_ROOT / "data" / ".va_corpus_update.lock"
VA_CSV_DIR = PROJECT_ROOT / "data" / "va_csv"


def write_lock(started_iso: str) -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(
        json.dumps({"started": started_iso, "pid": os.getpid()}, indent=2),
        encoding="utf-8",
    )


def clear_lock() -> None:
    LOCK_PATH.unlink(missing_ok=True)


def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    symbols = {"INFO": "", "SUCCESS": "[OK]", "WARNING": "[WARN]", "ERROR": "[ERR]"}
    print(f"[{ts}] {symbols.get(level, '')} {msg}")


def save_status(payload: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log(f"Status written to {STATUS_PATH}", "SUCCESS")


async def refresh_va_admin_html() -> int:
    """Re-download Virginia Administrative Code HTML (optional, slower)."""
    try:
        from scripts.complete_legal_database import VirginiaAdminCodeDownloader

        out_dir = PROJECT_ROOT / "data" / "sources" / "VA_ADMIN_CODE"
        out_dir.mkdir(parents=True, exist_ok=True)
        downloader = VirginiaAdminCodeDownloader("VA_ADMIN_CODE", out_dir)
        count = downloader.download()
        log(f"VA Administrative Code: {count} pages downloaded", "SUCCESS")
        return count
    except Exception as e:
        log(f"VA Admin Code download failed: {e}", "ERROR")
        return 0


async def ingest_va_admin_html() -> int:
    """Ingest VA_ADMIN_CODE HTML into RAG (limited batch)."""
    from bs4 import BeautifulSoup

    source_dir = PROJECT_ROOT / "data" / "sources" / "VA_ADMIN_CODE"
    if not source_dir.exists():
        return 0

    files = list(source_dir.glob("*.html"))[:2000]
    ingested = 0
    refresh_at = datetime.now().isoformat()

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.extract()
            text = soup.get_text("\n", strip=True)
            if len(text) < 200:
                continue
            if len(text) > 30000:
                text = text[:30000]

            doc_id = f"va_admin_{file_path.stem[:120]}"
            metadata = {
                "source": "Virginia Administrative Code",
                "jurisdiction": "Virginia",
                "document_type": "Regulations",
                "file": file_path.name,
                "corpus_refresh_at": refresh_at,
            }
            await rag_service.upsert_document(text=text, metadata=metadata, doc_id=doc_id)
            ingested += 1
        except Exception:
            continue

    log(f"VA Administrative Code: {ingested} documents ingested", "SUCCESS")
    return ingested


async def run_update(
    force_download: bool = False,
    download_only: bool = False,
    ingest_only: bool = False,
    include_regulations: bool = False,
    skip_purge: bool = False,
) -> int:
    started = datetime.now()
    refresh_at = started.isoformat()
    write_lock(refresh_at)
    run_mode = "ingest-only" if ingest_only else ("download-only" if download_only else "full")
    init_progress(run_mode)
    status: dict = {
        "last_run_started": refresh_at,
        "last_run_completed": None,
        "success": False,
        "steps": {},
        "errors": [],
    }

    try:
        if not ingest_only:
            write_progress("download", message="Downloading CSV from LIS", current=0, total=81)
            log("Downloading Code of Virginia CSV from law.lis.virginia.gov...")
            dl = await download_all_va_csv(force=force_download)
            write_progress(
                "download",
                message="CSV download complete",
                current=dl.get("downloaded", 0) + dl.get("skipped", 0),
                total=81,
            )
            status["steps"]["download"] = dl
            log(
                f"CSV download: {dl['downloaded']} new, {dl['skipped']} cached, {dl['failed']} failed"
            )
            if dl["failed"] > 0 and dl["downloaded"] == 0 and dl["skipped"] == 0:
                raise RuntimeError("All CSV downloads failed; check network and LIS availability")

        if download_only:
            status["success"] = True
            status["last_run_completed"] = datetime.now().isoformat()
            save_status(status)
            write_progress("complete", message="CSV download finished", current=81, total=81)
            clear_lock()
            return 0

        if not VA_CSV_DIR.exists() or not list(VA_CSV_DIR.glob("CoVTitle*.csv")):
            raise FileNotFoundError(
                f"No Virginia Code CSV files in {VA_CSV_DIR}. Run without --ingest-only first."
            )

        csv_sections = count_csv_sections()
        status["steps"]["csv_sections_on_disk"] = csv_sections
        log(f"CSV sections on disk: {csv_sections:,}")

        rag_service._ensure_initialized()

        if not skip_purge:
            write_progress("purge", message="Purging old Virginia Code vectors", current=0, total=1)
            log("Purging previous Virginia Code vectors from RAG...")
            purged = rag_service.purge_va_statutes()
            write_progress("purge", message=f"Purged {purged:,} vectors", current=1, total=1)
            status["steps"]["purged_vectors"] = purged
            log(f"Purged {purged:,} vectors", "SUCCESS")

        log("Ingesting Virginia Code into RAG (this may take a while)...")
        ingested = await ingest_va_csv_complete(corpus_refresh_at=refresh_at)
        status["steps"]["statutes_ingested"] = ingested
        log(f"Ingested {ingested:,} statute sections", "SUCCESS")

        log("Ingesting Virginia uncodified/session acts...")
        uncodified = await ingest_va_uncodified_acts(corpus_refresh_at=refresh_at)
        status["steps"]["uncodified_acts_ingested"] = uncodified
        log(f"Ingested {uncodified:,} uncodified/session act records", "SUCCESS")

        if include_regulations:
            log("Refreshing Virginia Administrative Code...")
            pages = await refresh_va_admin_html()
            status["steps"]["admin_code_pages_downloaded"] = pages
            admin_ingested = await ingest_va_admin_html()
            status["steps"]["admin_code_ingested"] = admin_ingested

        write_progress("search_tests", message="Running citation spot-checks", current=0, total=5)
        log("Running citation spot-check searches...")
        search_results = await test_search_functionality()
        write_progress("search_tests", message="Spot-checks done", current=5, total=5)
        status["steps"]["search_tests"] = [
            {"query": q, "status": s, "count": n} for q, s, n in search_results
        ]
        failed_searches = sum(1 for _, s, _ in search_results if s == "FAIL")
        if failed_searches:
            status["errors"].append(f"{failed_searches} search spot-check(s) failed")

        # Update manifest timestamp for VA_CODE source tracking
        manifest_path = PROJECT_ROOT / "data" / "manifests" / "VA_CODE.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["downloaded_at"] = refresh_at
                manifest["corpus_refresh_at"] = refresh_at
                manifest["corpus_refresh_source"] = "scripts/update_va_legal_corpus.py"
                manifest_path.write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                status["steps"]["manifest_updated"] = str(manifest_path)
            except Exception as e:
                status["errors"].append(f"manifest update: {e}")

        status["success"] = ingested > 0 and failed_searches == 0
        status["last_run_completed"] = datetime.now().isoformat()
        status["duration_seconds"] = (datetime.now() - started).total_seconds()
        save_status(status)
        write_progress(
            "complete" if status["success"] else "failed",
            message="Virginia corpus update finished",
            current=ingested,
            total=csv_sections,
            extra={"success": status["success"]},
        )

        elapsed = datetime.now() - started
        print()
        print("=" * 60)
        print("VIRGINIA LAW CORPUS UPDATE COMPLETE")
        print("=" * 60)
        print(f"Duration: {elapsed}")
        print(f"Statutes ingested: {ingested:,}")
        print(f"Search checks failed: {failed_searches}")
        print(f"Success: {status['success']}")
        print("=" * 60)

        return 0 if status["success"] else 1

    except Exception as e:
        status["success"] = False
        status["last_run_completed"] = datetime.now().isoformat()
        status["errors"].append(str(e))
        save_status(status)
        write_progress("failed", message=str(e)[:200], current=0, total=1)
        log(str(e), "ERROR")
        return 1
    finally:
        clear_lock()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Annual Virginia Code corpus refresh (download + RAG re-ingest)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download all CSV files from LIS (recommended yearly)",
    )
    parser.add_argument("--download-only", action="store_true", help="Download CSVs only")
    parser.add_argument(
        "--ingest-only",
        action="store_true",
        help="Re-ingest from existing CSVs (skip download)",
    )
    parser.add_argument(
        "--include-regulations",
        action="store_true",
        help="Also download/ingest Virginia Administrative Code HTML",
    )
    parser.add_argument(
        "--skip-purge",
        action="store_true",
        help="Do not purge old VA Code vectors before ingest (not recommended)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("VIRGINIA LEGAL CORPUS ANNUAL UPDATE")
    print("=" * 60)
    print()

    return asyncio.run(
        run_update(
            force_download=args.force,
            download_only=args.download_only,
            ingest_only=args.ingest_only,
            include_regulations=args.include_regulations,
            skip_purge=args.skip_purge,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
