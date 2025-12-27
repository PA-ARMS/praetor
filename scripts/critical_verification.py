"""
CRITICAL VERIFICATION FOR LEGAL AI SYSTEM
==========================================
This script performs rigorous verification to ensure the legal database
is accurate and complete for defense attorney use.

NO ROOM FOR ERROR - This system helps defend people's freedom.

Checks:
1. Specific statute lookup accuracy
2. Citation matching precision  
3. Cross-reference verification
4. Coverage completeness
5. Search result relevance
"""
import asyncio
import csv
import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service

VA_CSV_DIR = Path("data/va_csv")


def log(msg: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    symbols = {"INFO": "   ", "PASS": " ✓ ", "FAIL": " ✗ ", "WARN": " ⚠ ", "CRITICAL": "!!!"}
    print(f"[{timestamp}]{symbols.get(level, '   ')} {msg}")


# =============================================================================
# CRITICAL STATUTES FOR DEFENSE ATTORNEYS
# These MUST be present and accurate
# =============================================================================

CRITICAL_STATUTES = [
    # Criminal - Assault/Battery
    ("18.2-57", "Assault and battery"),
    ("18.2-57.2", "Assault and battery against family member"),
    ("18.2-57.3", "Assault and battery against health care provider"),
    
    # Criminal - Weapons
    ("18.2-308", "Carrying concealed weapons"),
    ("18.2-308.1", "Possession of firearm on school property"),
    ("18.2-308.2", "Possession of firearm by convicted felon"),
    
    # Criminal - DUI
    ("18.2-266", "Driving motor vehicle while intoxicated"),
    ("18.2-270", "Penalty for driving while intoxicated"),
    ("18.2-271", "Forfeiture of driver's license"),
    
    # Criminal - Theft/Larceny
    ("18.2-95", "Grand larceny"),
    ("18.2-96", "Petit larceny"),
    ("18.2-103", "Concealing merchandise; shoplifting"),
    
    # Criminal - Drug Offenses
    ("18.2-248", "Manufacturing, selling, distributing controlled substances"),
    ("18.2-250", "Possession of controlled substances"),
    ("18.2-250.1", "Possession of marijuana"),
    
    # Criminal - Homicide
    ("18.2-31", "Capital murder"),
    ("18.2-32", "First and second degree murder"),
    ("18.2-33", "Felony homicide"),
    ("18.2-35", "Voluntary manslaughter"),
    ("18.2-36", "Involuntary manslaughter"),
    
    # Criminal - Sexual Offenses
    ("18.2-61", "Rape"),
    ("18.2-67.1", "Forcible sodomy"),
    ("18.2-67.2", "Object sexual penetration"),
    
    # Criminal - Burglary/Breaking
    ("18.2-89", "Burglary"),
    ("18.2-90", "Breaking and entering with intent to commit felony"),
    ("18.2-91", "Breaking and entering with intent to commit larceny"),
    
    # Criminal - Fraud
    ("18.2-178", "Forgery"),
    ("18.2-181", "Uttering forged documents"),
    ("18.2-186", "False statements to obtain property"),
    
    # Criminal Procedure
    ("19.2-81", "Arrest without warrant"),
    ("19.2-82", "Arrest on capias"),
    ("19.2-120", "Admission to bail"),
    ("19.2-152.4", "Protective orders"),
    ("19.2-163", "Right to counsel"),
    ("19.2-187", "Certificate of analysis as evidence"),
    ("19.2-243", "Speedy trial"),
    ("19.2-264.2", "Sentencing proceedings"),
    
    # Civil Procedure
    ("8.01-195.3", "Sovereign immunity"),
    ("8.01-229", "Statute of limitations - personal injury"),
    ("8.01-243", "Statute of limitations - contracts"),
    ("8.01-249", "Tolling of limitations"),
    ("8.01-401", "Hearsay rule"),
    
    # Evidence
    ("19.2-270.1", "Admissibility of certain certificates"),
    ("19.2-271", "Competency of witnesses"),
    
    # Constitutional Rights (VA)
    ("19.2-59", "Search warrants"),
    ("19.2-60", "Execution of search warrants"),
]


async def verify_statute_exists(section: str, expected_topic: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Verify a specific statute exists in the database and contains expected content.
    Returns: (found, message, result_metadata)
    """
    try:
        # Search for exact section
        results = await rag_service.search(f"Virginia Code {section}", n_results=10)
        
        if not results:
            return False, f"No results found for {section}", None
        
        # Check if any result matches the section number
        for result in results:
            meta = result.get('metadata', {})
            text = result.get('text', '').lower()
            citation = meta.get('citation', '')
            section_meta = meta.get('section', '')
            
            # Check if this result is for the right section
            section_match = (
                section in citation or 
                section in section_meta or
                f"§ {section}" in text or
                f"section {section}" in text.lower()
            )
            
            if section_match:
                # Verify topic relevance
                topic_words = expected_topic.lower().split()
                topic_match = any(word in text for word in topic_words if len(word) > 3)
                
                if topic_match:
                    return True, f"Found and verified: {section}", meta
                else:
                    return True, f"Found {section} but topic mismatch - review needed", meta
        
        # Section not in top results - might be missing
        return False, f"Section {section} not found in search results", None
        
    except Exception as e:
        return False, f"Error searching for {section}: {str(e)}", None


async def verify_csv_coverage():
    """
    Verify that CSV data matches what's in the database.
    Cross-reference section counts.
    """
    log("=" * 60)
    log("VERIFYING CSV DATA COVERAGE")
    log("=" * 60)
    
    csv_sections = {}
    total_csv = 0
    
    # Count sections in each CSV file
    for csv_file in sorted(VA_CSV_DIR.glob("CoVTitle*.csv")):
        title = csv_file.stem.replace("CoVTitle_", "")
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                sections = [row.get('Section', '') for row in reader if row.get('Section')]
                csv_sections[title] = sections
                total_csv += len(sections)
        except Exception as e:
            log(f"Error reading {csv_file.name}: {e}", "FAIL")
    
    log(f"Total sections in CSV files: {total_csv:,}")
    
    # Sample verification - check random sections from each title
    verified = 0
    missing = 0
    
    for title, sections in csv_sections.items():
        if not sections:
            continue
        
        # Check first, middle, and last section of each title
        samples = [sections[0]]
        if len(sections) > 1:
            samples.append(sections[len(sections)//2])
        if len(sections) > 2:
            samples.append(sections[-1])
        
        for section in samples:
            found, msg, _ = await verify_statute_exists(section, title)
            if found:
                verified += 1
            else:
                missing += 1
                log(f"Missing: {section} from Title {title}", "WARN")
    
    coverage_pct = (verified / (verified + missing) * 100) if (verified + missing) > 0 else 0
    log(f"Sample verification: {verified}/{verified+missing} found ({coverage_pct:.1f}%)")
    
    return {
        "total_csv_sections": total_csv,
        "samples_verified": verified,
        "samples_missing": missing,
        "coverage_percent": coverage_pct
    }


async def verify_critical_statutes():
    """
    Verify ALL critical statutes that defense attorneys need.
    This is the most important check.
    """
    log("=" * 60)
    log("VERIFYING CRITICAL DEFENSE STATUTES")
    log("=" * 60)
    
    results = {
        "passed": [],
        "failed": [],
        "warnings": []
    }
    
    for section, topic in CRITICAL_STATUTES:
        found, message, meta = await verify_statute_exists(section, topic)
        
        if found and "verified" in message.lower():
            results["passed"].append((section, topic, message))
            log(f"{section}: {topic}", "PASS")
        elif found:
            results["warnings"].append((section, topic, message))
            log(f"{section}: {topic} - NEEDS REVIEW", "WARN")
        else:
            results["failed"].append((section, topic, message))
            log(f"{section}: {topic} - MISSING!", "FAIL")
    
    total = len(CRITICAL_STATUTES)
    passed = len(results["passed"])
    warnings = len(results["warnings"])
    failed = len(results["failed"])
    
    log("")
    log(f"Results: {passed} passed, {warnings} warnings, {failed} FAILED out of {total}")
    
    if failed > 0:
        log("", "CRITICAL")
        log("CRITICAL STATUTES ARE MISSING!", "CRITICAL")
        log("System is NOT ready for production use.", "CRITICAL")
        for section, topic, msg in results["failed"]:
            log(f"  - {section}: {topic}", "CRITICAL")
    
    return results


async def test_search_accuracy():
    """
    Test that searches return accurate, relevant results.
    """
    log("=" * 60)
    log("TESTING SEARCH ACCURACY")
    log("=" * 60)
    
    test_cases = [
        {
            "query": "What is the penalty for DUI in Virginia?",
            "must_contain": ["18.2-266", "18.2-270"],
            "topic": "DUI penalties"
        },
        {
            "query": "domestic assault Virginia",
            "must_contain": ["18.2-57.2"],
            "topic": "Family assault"
        },
        {
            "query": "grand larceny threshold Virginia",
            "must_contain": ["18.2-95"],
            "topic": "Grand larceny"
        },
        {
            "query": "possession of marijuana Virginia",
            "must_contain": ["18.2-250.1"],
            "topic": "Marijuana possession"
        },
        {
            "query": "speedy trial Virginia",
            "must_contain": ["19.2-243"],
            "topic": "Speedy trial rights"
        },
        {
            "query": "right to counsel Virginia",
            "must_contain": ["19.2-163"],
            "topic": "Right to attorney"
        },
        {
            "query": "search warrant requirements Virginia",
            "must_contain": ["19.2-59", "19.2-60"],
            "topic": "Search warrants"
        },
        {
            "query": "bail bond Virginia",
            "must_contain": ["19.2-120"],
            "topic": "Bail"
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        query = test["query"]
        must_contain = test["must_contain"]
        topic = test["topic"]
        
        try:
            results = await rag_service.search(query, n_results=10)
            
            # Check if required sections appear in results
            found_sections = set()
            for result in results:
                text = result.get('text', '')
                meta = result.get('metadata', {})
                combined = f"{text} {meta.get('citation', '')} {meta.get('section', '')}"
                
                for section in must_contain:
                    if section in combined:
                        found_sections.add(section)
            
            missing = set(must_contain) - found_sections
            
            if not missing:
                log(f"'{topic}': Found all required sections", "PASS")
                passed += 1
            else:
                log(f"'{topic}': Missing {missing}", "FAIL")
                failed += 1
                
        except Exception as e:
            log(f"'{topic}': Error - {e}", "FAIL")
            failed += 1
    
    log("")
    log(f"Search accuracy: {passed}/{passed+failed} tests passed")
    
    return {"passed": passed, "failed": failed}


async def check_for_outdated_law():
    """
    Check for potentially outdated or superseded statutes.
    """
    log("=" * 60)
    log("CHECKING FOR OUTDATED REFERENCES")
    log("=" * 60)
    
    # Known repealed/amended sections to watch for
    known_changes = [
        ("18.2-250.1", "Marijuana decriminalization - verify current penalties"),
        ("18.2-248", "Drug penalties - verify current schedules"),
    ]
    
    warnings = []
    
    for section, note in known_changes:
        results = await rag_service.search(f"Virginia Code {section}", n_results=3)
        if results:
            log(f"{section}: Present - {note}", "WARN")
            warnings.append((section, note))
    
    log("")
    log("NOTE: Always verify current law status before use in court")
    
    return warnings


async def generate_verification_report():
    """
    Generate comprehensive verification report.
    """
    log("=" * 60)
    log("GENERATING VERIFICATION REPORT")
    log("=" * 60)
    
    # Get database stats
    rag_service._ensure_initialized()
    collection = rag_service.collection
    all_docs = collection.get()
    
    total_docs = len(all_docs['ids'])
    
    # Count by source
    sources = {}
    for meta in all_docs['metadatas']:
        src = meta.get('source', 'Unknown')
        sources[src] = sources.get(src, 0) + 1
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "database_stats": {
            "total_documents": total_docs,
            "sources": dict(sorted(sources.items(), key=lambda x: -x[1])[:20])
        }
    }
    
    # Save report
    report_path = Path("data/verification_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    log(f"Report saved to: {report_path}")
    
    return report


async def main():
    """
    Run all critical verifications.
    """
    start = datetime.now()
    
    print("=" * 60)
    print("CRITICAL VERIFICATION FOR LEGAL AI SYSTEM")
    print("Defense Attorney Production Readiness Check")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # 1. Verify critical statutes
    critical_results = await verify_critical_statutes()
    if critical_results["failed"]:
        all_passed = False
    
    print()
    
    # 2. Test search accuracy
    search_results = await test_search_accuracy()
    if search_results["failed"] > 0:
        all_passed = False
    
    print()
    
    # 3. Check CSV coverage
    csv_results = await verify_csv_coverage()
    if csv_results["coverage_percent"] < 90:
        all_passed = False
    
    print()
    
    # 4. Check for outdated law warnings
    outdated = await check_for_outdated_law()
    
    print()
    
    # 5. Generate report
    report = await generate_verification_report()
    
    # Final verdict
    duration = datetime.now() - start
    
    print()
    print("=" * 60)
    print("FINAL VERIFICATION RESULT")
    print("=" * 60)
    print(f"Duration: {duration}")
    print()
    
    if all_passed:
        print("✓ ALL CRITICAL CHECKS PASSED")
        print("✓ System is ready for production use")
        print()
        print("IMPORTANT REMINDERS FOR ATTORNEYS:")
        print("  1. Always verify current law status (Shepardize/KeyCite)")
        print("  2. Cross-reference with official Virginia Code")
        print("  3. Check for recent amendments or case law")
        print("  4. This is a research aid, not legal advice")
    else:
        print("✗ CRITICAL CHECKS FAILED")
        print("✗ System is NOT ready for production use")
        print()
        print("ISSUES TO RESOLVE:")
        if critical_results["failed"]:
            print(f"  - {len(critical_results['failed'])} critical statutes missing")
        if search_results["failed"] > 0:
            print(f"  - {search_results['failed']} search accuracy tests failed")
        if csv_results["coverage_percent"] < 90:
            print(f"  - CSV coverage only {csv_results['coverage_percent']:.1f}%")
    
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

