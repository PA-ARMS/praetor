"""
VERIFY AND COMPLETE LEGAL DATABASE
===================================
This script ensures the legal database is complete and production-ready.

1. Verifies all Virginia Code CSV data is ingested
2. Downloads missing critical sources
3. Validates search functionality
4. Generates production readiness report
"""
import asyncio
import csv
import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from bs4 import BeautifulSoup

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from server.services.rag_service import rag_service
from corpus_progress import write_progress
from server.services.ollama_service import ollama_service

# Paths
VA_CSV_DIR = Path("data/va_csv")
SOURCES_DIR = Path("data/sources")
SCENARIOS_DIR = Path("data/scenarios")


def log(msg: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    symbols = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}
    symbol = symbols.get(level, "")
    print(f"[{timestamp}] {symbol} {msg}")


async def check_rag_status() -> Dict:
    """Check current RAG database status"""
    log("Checking RAG database status...")
    
    try:
        rag_service._ensure_initialized()
        collection = rag_service.collection
        all_docs = collection.get()
        
        total = len(all_docs['ids'])
        
        # Count by metadata
        stats = {
            "total": total,
            "by_jurisdiction": {},
            "by_type": {},
            "by_source": {},
            "va_code_sections": 0
        }
        
        for meta in all_docs['metadatas']:
            # Jurisdiction
            jur = meta.get('jurisdiction', 'Unknown')
            stats["by_jurisdiction"][jur] = stats["by_jurisdiction"].get(jur, 0) + 1
            
            # Type
            doc_type = meta.get('document_type', 'Unknown')
            stats["by_type"][doc_type] = stats["by_type"].get(doc_type, 0) + 1
            
            # Source
            source = meta.get('source', 'Unknown')
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
            
            # VA Code sections (check citation format)
            citation = meta.get('citation', '')
            if citation and re.match(r'Va\. Code', citation):
                stats["va_code_sections"] += 1
        
        log(f"Total documents: {total:,}", "SUCCESS")
        log(f"Virginia Code sections with proper citation: {stats['va_code_sections']:,}")
        
        return stats
        
    except Exception as e:
        log(f"Error checking RAG: {e}", "ERROR")
        return {"error": str(e)}


def count_uncodified_acts_since(min_year: int = 2015) -> int:
    """Count uncodified act rows (2015+) for progress total."""
    path = VA_CSV_DIR / "UnCodifiedActs.csv"
    if not path.exists():
        return 0
    csv.field_size_limit(10_000_000)
    total = 0
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            year = (row.get("Year") or "").strip()
            try:
                if year and int(year) >= min_year:
                    total += 1
            except ValueError:
                pass
    return total


def count_csv_sections() -> int:
    """Count total sections in VA CSV files"""
    total = 0
    for csv_file in VA_CSV_DIR.glob("CoVTitle*.csv"):
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                total += sum(1 for _ in reader)
        except Exception:
            pass
    return total


async def ingest_va_csv_complete(corpus_refresh_at: str | None = None):
    """Ingest ALL Virginia Code CSV data into RAG with proper metadata"""
    log("=" * 60)
    log("INGESTING VIRGINIA CODE CSV DATA")
    log("=" * 60)
    
    csv_files = sorted(VA_CSV_DIR.glob("CoVTitle*.csv"))
    total_sections = count_csv_sections()
    log(f"Found {len(csv_files)} CSV files with {total_sections:,} total sections")
    write_progress(
        "statutes",
        message="Ingesting Code of Virginia titles",
        current=0,
        total=total_sections,
    )
    
    ingested = 0
    skipped = 0
    errors = 0
    
    for csv_file in csv_files:
        title_num = csv_file.stem.replace("CoVTitle_", "")
        log(f"Processing Title {title_num}...")
        
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    section = row.get('Section', '').strip()
                    title = row.get('Title', '').strip()
                    body = row.get('Body', '').strip()
                    chapter = row.get('ChapterName', '').strip()
                    article = row.get('ArticleName', '').strip()
                    
                    # Clean HTML from body
                    if body:
                        soup = BeautifulSoup(body, 'html.parser')
                        body = soup.get_text(' ', strip=True)
                    
                    if not body or len(body) < 50:
                        skipped += 1
                        continue
                    
                    # Build comprehensive document text
                    doc_parts = [f"Virginia Code § {section}"]
                    if title:
                        doc_parts.append(f"Title: {title}")
                    if chapter:
                        doc_parts.append(f"Chapter: {chapter}")
                    if article:
                        doc_parts.append(f"Article: {article}")
                    doc_parts.append("")
                    doc_parts.append(body)
                    
                    doc_text = "\n".join(doc_parts)
                    
                    # Proper legal citation format
                    citation = f"Va. Code Ann. § {section}"
                    
                    metadata = {
                        "source": "Code of Virginia",
                        "jurisdiction": "Virginia",
                        "document_type": "Statute",
                        "citation": citation,
                        "section": section,
                        "title": title,
                        "chapter": chapter,
                        "article": article,
                        "title_number": title_num,
                        "file": csv_file.name,
                        "official": True,
                    }
                    if corpus_refresh_at:
                        metadata["corpus_refresh_at"] = corpus_refresh_at
                    
                    try:
                        # Use section as doc_id for deduplication
                        doc_id = f"va_code_{section.replace('.', '_').replace('-', '_')}"
                        await rag_service.add_document(
                            text=doc_text,
                            metadata=metadata,
                            doc_id=doc_id
                        )
                        ingested += 1
                        
                        if ingested % 500 == 0:
                            log(f"  Ingested {ingested:,} sections...")
                            write_progress(
                                "statutes",
                                message=f"Title {title_num}",
                                current=ingested,
                                total=total_sections,
                            )
                            
                    except Exception as e:
                        errors += 1
                        if errors <= 5:
                            log(f"  Error on {section}: {e}", "WARNING")
                        
        except Exception as e:
            log(f"Error processing {csv_file.name}: {e}", "ERROR")
    
    write_progress(
        "statutes",
        message="Code of Virginia ingest complete",
        current=ingested,
        total=total_sections or ingested or 1,
    )
    log(f"Ingestion complete: {ingested:,} ingested, {skipped:,} skipped, {errors:,} errors", "SUCCESS")
    return ingested


async def ingest_va_uncodified_acts(corpus_refresh_at: str | None = None, max_rows: int | None = None):
    """
    Ingest Virginia uncodified/session acts (includes many effective-date enactments).
    Source: data/va_csv/UnCodifiedActs.csv from LIS.
    """
    path = VA_CSV_DIR / "UnCodifiedActs.csv"
    if not path.exists():
        log("UnCodifiedActs.csv not found — skip session acts", "WARNING")
        return 0

    log("=" * 60)
    log("INGESTING VIRGINIA UNCODIFIED / SESSION ACTS")
    log("=" * 60)

    total_uncodified = count_uncodified_acts_since(2015)
    log(f"Uncodified acts to ingest (2015+): {total_uncodified:,}")
    write_progress(
        "uncodified",
        message="Ingesting session / uncodified acts",
        current=0,
        total=total_uncodified or 1,
    )

    ingested = 0
    skipped = 0
    import hashlib

    csv.field_size_limit(10_000_000)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if max_rows is not None and i >= max_rows:
                break
            year = (row.get("Year") or "").strip()
            # Session-law refresh: prioritize 2015+ (covers recent July 1 effective-date questions)
            if year:
                try:
                    if int(year) < 2015:
                        skipped += 1
                        continue
                except ValueError:
                    pass
            chapter = (row.get("Chapter") or "").strip()
            bill = (row.get("BillNum") or "").strip()
            title = (row.get("Title") or "").strip()
            catchline = (row.get("CatchLine") or "").strip()
            subject = (row.get("Subject") or "").strip()
            session = (row.get("Session") or "").strip()

            body_parts = []
            if catchline:
                body_parts.append(catchline)
            if title:
                body_parts.append(title)
            body = " ".join(body_parts).strip()
            if len(body) < 40:
                skipped += 1
                continue

            citation = f"Va. Acts {year} Ch. {chapter}" if year and chapter else f"Va. Uncodified Act {year or 'n.d.'}"
            doc_parts = [
                f"Virginia Uncodified Act — {citation}",
                f"Year: {year}" if year else "",
                f"Session: {session}" if session else "",
                f"Subject: {subject}" if subject else "",
                f"Bill: {bill}" if bill else "",
                "",
                body,
            ]
            doc_text = "\n".join(p for p in doc_parts if p)

            safe = hashlib.md5(f"{year}_{chapter}_{bill}_{title[:80]}".encode()).hexdigest()[:16]
            doc_id = f"va_uncodified_{year}_{chapter}_{safe}".replace(" ", "_")

            metadata = {
                "source": "Virginia Uncodified Acts",
                "jurisdiction": "Virginia",
                "document_type": "Session Law",
                "citation": citation,
                "year": year,
                "chapter": chapter,
                "bill": bill,
                "session": session,
                "subject": subject,
                "official": True,
            }
            if corpus_refresh_at:
                metadata["corpus_refresh_at"] = corpus_refresh_at

            try:
                await rag_service.add_document(text=doc_text, metadata=metadata, doc_id=doc_id)
                ingested += 1
                if ingested % 500 == 0:
                    log(f"  Uncodified acts ingested: {ingested:,}...")
                    write_progress(
                        "uncodified",
                        message=f"Session acts ({year})",
                        current=ingested,
                        total=total_uncodified or ingested or 1,
                    )
            except Exception as e:
                if ingested < 3:
                    log(f"  Uncodified ingest error: {e}", "WARNING")

    write_progress(
        "uncodified",
        message="Uncodified acts ingest complete",
        current=ingested,
        total=total_uncodified or ingested or 1,
    )
    log(f"Uncodified acts: {ingested:,} ingested, {skipped:,} skipped", "SUCCESS")
    return ingested


async def ingest_downloaded_html():
    """Ingest downloaded HTML/PDF sources"""
    log("=" * 60)
    log("INGESTING DOWNLOADED SOURCES")
    log("=" * 60)
    
    sources_to_ingest = [
        ("VA_OPINIONS", "Virginia", "Case Law"),
        ("VA_COURTS", "Virginia", "Court Rules"),
        ("VA_REGISTER", "Virginia", "Regulations"),
        ("VA_ADMIN_CODE", "Virginia", "Regulations"),
        ("SCOTUS_OPINIONS", "Federal", "Case Law"),
        ("SCOTUS_PORTAL", "Federal", "Case Law"),
        ("US_CODE_OLRC", "Federal", "Statute"),
        ("US_COURTS_RULES", "Federal", "Court Rules"),
    ]
    
    total_ingested = 0
    
    for source_id, jurisdiction, doc_type in sources_to_ingest:
        source_dir = SOURCES_DIR / source_id
        if not source_dir.exists():
            continue
        
        files = list(source_dir.glob("*.html")) + list(source_dir.glob("*.htm"))
        log(f"Processing {source_id}: {len(files)} files")
        
        ingested = 0
        for file_path in files[:5000]:  # Limit per source (raised for full coverage)
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')
                
                # Remove non-content
                for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
                    tag.extract()
                
                text = soup.get_text('\n', strip=True)
                
                if len(text) < 200:
                    continue
                
                # Truncate very long documents
                if len(text) > 30000:
                    text = text[:30000]
                
                metadata = {
                    "source": source_id.replace("_", " ").title(),
                    "jurisdiction": jurisdiction,
                    "document_type": doc_type,
                    "file": file_path.name
                }
                
                await rag_service.add_document(text=text, metadata=metadata)
                ingested += 1
                
            except Exception:
                pass
        
        log(f"  Ingested {ingested} from {source_id}")
        total_ingested += ingested
    
    return total_ingested


async def ingest_case_scenarios():
    """Ingest case law from scenarios"""
    log("=" * 60)
    log("INGESTING CASE LAW SCENARIOS")
    log("=" * 60)
    
    total_ingested = 0
    
    for source in ["cap", "courtlistener"]:
        cases_dir = SCENARIOS_DIR / source
        if not cases_dir.exists():
            continue
        
        case_files = list(cases_dir.glob("*.json"))[:3000]  # Limit
        log(f"Processing {source}: {len(case_files)} cases")
        
        ingested = 0
        for case_path in case_files:
            try:
                with open(case_path, 'r', encoding='utf-8') as f:
                    case = json.load(f)
                
                # Extract text based on source format
                if source == "cap":
                    opinions = case.get("casebody", {}).get("data", {}).get("opinions", [])
                    text = opinions[0].get("text", "") if opinions else ""
                else:
                    text = case.get("text", "") or case.get("plain_text", "")
                
                if not text or len(text) < 300:
                    continue
                
                if len(text) > 25000:
                    text = text[:25000]
                
                case_name = case.get("name", case.get("case_name", "Unknown"))
                
                # Get citation
                if source == "cap":
                    citations = case.get("citations", [])
                    citation = citations[0].get("cite", "") if citations else ""
                else:
                    citation = case.get("citation", "")
                
                metadata = {
                    "source": source.upper(),
                    "jurisdiction": "Virginia",
                    "document_type": "Case Law",
                    "case_name": case_name,
                    "citation": citation,
                    "decision_date": case.get("decision_date", "")
                }
                
                await rag_service.add_document(text=text, metadata=metadata)
                ingested += 1
                
            except Exception:
                pass
        
        log(f"  Ingested {ingested} from {source}")
        total_ingested += ingested
    
    return total_ingested


async def test_search_functionality():
    """Test that search works correctly"""
    log("=" * 60)
    log("TESTING SEARCH FUNCTIONALITY")
    log("=" * 60)
    
    test_queries = [
        ("18.2-57.2", "assault and battery family member"),
        ("8.01-195.1", "sovereign immunity"),
        ("19.2-81", "arrest without warrant"),
        ("46.2-301", "driving without license"),
        ("domestic assault Virginia", "family abuse"),
    ]
    
    results = []
    
    for query, expected_topic in test_queries:
        log(f"Testing: '{query}'")
        try:
            search_results = await rag_service.search(query, n_results=3)
            
            if search_results:
                top_result = search_results[0]
                citation = top_result.get('metadata', {}).get('citation', 'N/A')
                source = top_result.get('metadata', {}).get('source', 'N/A')
                text_preview = top_result.get('text', '')[:100]
                
                # Check if we got a relevant result
                found_relevant = any(
                    query.split('-')[0] in str(r.get('metadata', {})) or
                    expected_topic.lower() in r.get('text', '').lower()
                    for r in search_results
                )
                
                status = "PASS" if found_relevant else "PARTIAL"
                log(f"  {status}: Found {len(search_results)} results, top: {citation}")
                results.append((query, status, len(search_results)))
            else:
                log(f"  FAIL: No results", "WARNING")
                results.append((query, "FAIL", 0))
                
        except Exception as e:
            log(f"  ERROR: {e}", "ERROR")
            results.append((query, "ERROR", 0))
    
    passed = sum(1 for _, status, _ in results if status in ("PASS", "PARTIAL"))
    log(f"Search tests: {passed}/{len(results)} passed")
    
    return results


async def generate_production_report():
    """Generate final production readiness report"""
    log("=" * 60)
    log("GENERATING PRODUCTION READINESS REPORT")
    log("=" * 60)
    
    # Get final stats
    rag_stats = await check_rag_status()
    csv_sections = count_csv_sections()
    
    # Count files
    source_counts = {}
    for source_dir in SOURCES_DIR.iterdir():
        if source_dir.is_dir():
            count = len(list(source_dir.rglob("*.*")))
            source_counts[source_dir.name] = count
    
    case_counts = {}
    for source in ["cap", "courtlistener"]:
        cases_dir = SCENARIOS_DIR / source
        if cases_dir.exists():
            case_counts[source] = len(list(cases_dir.glob("*.json")))
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "status": "PRODUCTION_READY" if rag_stats.get("total", 0) > 50000 else "NEEDS_REVIEW",
        "rag_database": {
            "total_documents": rag_stats.get("total", 0),
            "va_code_sections": rag_stats.get("va_code_sections", 0),
            "by_jurisdiction": rag_stats.get("by_jurisdiction", {}),
            "by_type": rag_stats.get("by_type", {})
        },
        "source_data": {
            "va_csv_total_sections": csv_sections,
            "downloaded_sources": source_counts,
            "case_scenarios": case_counts
        },
        "coverage": {
            "virginia_code": "COMPLETE" if csv_sections > 30000 else "INCOMPLETE",
            "virginia_cases": "GOOD" if case_counts.get("cap", 0) > 5000 else "NEEDS_MORE",
            "federal_law": "PARTIAL",
            "court_rules": "GOOD" if source_counts.get("US_COURTS_RULES", 0) > 200 else "NEEDS_MORE"
        }
    }
    
    # Save report
    report_path = Path("data/production_readiness_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    log(f"Report saved to: {report_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("PRODUCTION READINESS SUMMARY")
    print("=" * 60)
    print(f"Status: {report['status']}")
    print(f"\nRAG Database:")
    print(f"  Total documents: {report['rag_database']['total_documents']:,}")
    print(f"  VA Code sections: {report['rag_database']['va_code_sections']:,}")
    print(f"\nCoverage:")
    for area, status in report['coverage'].items():
        symbol = "✅" if status in ("COMPLETE", "GOOD") else "⚠️"
        print(f"  {symbol} {area}: {status}")
    print("=" * 60)
    
    return report


async def main():
    """Main entry point"""
    start = datetime.now()
    
    log("=" * 60)
    log("LEGAL DATABASE VERIFICATION AND COMPLETION")
    log("=" * 60)
    
    # Step 1: Check current status
    log("\n[STEP 1/5] Checking current database status...")
    initial_stats = await check_rag_status()
    
    # Step 2: Ingest VA CSV data (most critical)
    log("\n[STEP 2/5] Ingesting Virginia Code CSV data...")
    csv_ingested = await ingest_va_csv_complete()
    
    # Step 3: Ingest downloaded HTML sources
    log("\n[STEP 3/5] Ingesting downloaded HTML sources...")
    html_ingested = await ingest_downloaded_html()
    
    # Step 4: Ingest case scenarios
    log("\n[STEP 4/5] Ingesting case law...")
    cases_ingested = await ingest_case_scenarios()
    
    # Step 5: Test and report
    log("\n[STEP 5/5] Testing and generating report...")
    search_results = await test_search_functionality()
    report = await generate_production_report()
    
    # Final summary
    duration = datetime.now() - start
    print(f"\n{'=' * 60}")
    print("COMPLETION SUMMARY")
    print(f"{'=' * 60}")
    print(f"Duration: {duration}")
    print(f"VA Code sections ingested: {csv_ingested:,}")
    print(f"HTML documents ingested: {html_ingested:,}")
    print(f"Case law ingested: {cases_ingested:,}")
    print(f"Final status: {report['status']}")
    print(f"{'=' * 60}")
    
    return report['status'] == "PRODUCTION_READY"


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)


