"""
CRITICAL DATA VERIFICATION FOR DEFENSE ATTORNEY SYSTEM
=======================================================
This script verifies that ALL critical legal data is present and accurate.
This is a mission-critical system - no room for errors.

Checks:
1. All Virginia Code sections are present in CSV
2. Critical criminal statutes are complete
3. RAG database contains searchable versions
4. Search returns correct results for known queries
"""
import csv
import json
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

# Critical statutes that MUST be present and searchable
CRITICAL_CRIMINAL_STATUTES = [
    # Assault/Battery
    ("18.2-57", "Assault and battery"),
    ("18.2-57.2", "Assault and battery against family member"),
    ("18.2-51", "Malicious wounding"),
    ("18.2-51.2", "Aggravated malicious wounding"),
    ("18.2-51.4", "Maiming of another resulting from DUI"),
    
    # Theft/Property
    ("18.2-95", "Grand larceny"),
    ("18.2-96", "Petit larceny"),
    ("18.2-103", "Concealing merchandise (shoplifting)"),
    ("18.2-111", "Embezzlement"),
    
    # Drug Offenses
    ("18.2-248", "Manufacturing/distributing drugs"),
    ("18.2-250", "Possession of controlled substances"),
    ("18.2-250.1", "Possession of marijuana"),
    
    # DUI
    ("18.2-266", "Driving under influence"),
    ("18.2-270", "DUI penalties"),
    ("18.2-271", "License revocation for DUI"),
    
    # Weapons
    ("18.2-308", "Carrying concealed weapons"),
    ("18.2-308.1", "Possession of firearm by felon"),
    ("18.2-308.2", "Possession by persons adjudicated legally incompetent"),
    
    # Sex Offenses
    ("18.2-61", "Rape"),
    ("18.2-67.1", "Forcible sodomy"),
    ("18.2-67.2", "Object sexual penetration"),
    
    # Murder/Homicide
    ("18.2-31", "Capital murder"),
    ("18.2-32", "First and second degree murder"),
    ("18.2-33", "Felony homicide"),
    ("18.2-35", "Voluntary manslaughter"),
    ("18.2-36", "Involuntary manslaughter"),
    
    # Fraud
    ("18.2-178", "Obtaining money by false pretenses"),
    ("18.2-181", "Issuing bad checks"),
    ("18.2-186.3", "Identity theft"),
    
    # Procedural (Critical for defense)
    ("19.2-81", "Arrest without warrant"),
    ("19.2-82", "Arrest on warrant"),
    ("19.2-120", "Bail"),
    ("19.2-152.4", "Protective orders"),
    ("19.2-163.01", "Right to counsel"),
    ("19.2-187", "Certificates of analysis"),
    ("19.2-188", "Confrontation of witnesses"),
    ("19.2-270", "Competency to stand trial"),
    
    # Evidence
    ("19.2-271", "Testimony of husband and wife"),
    ("8.01-399", "Physician-patient privilege"),
    ("8.01-400", "Attorney-client privilege"),
    
    # Limitations
    ("19.2-8", "Statute of limitations - felonies"),
    ("8.01-243", "Statute of limitations - civil"),
]

CRITICAL_CIVIL_STATUTES = [
    ("8.01-195.3", "Sovereign immunity"),
    ("8.01-229", "Personal injury limitations"),
    ("8.01-243", "General limitations"),
    ("8.01-249", "Tolling of limitations"),
    ("8.01-401", "Burden of proof"),
    ("8.01-581.1", "Medical malpractice"),
]


def log(msg, level="INFO"):
    symbols = {"INFO": "ℹ️", "OK": "✅", "WARN": "⚠️", "FAIL": "❌", "CRITICAL": "🚨"}
    print(f"[{symbols.get(level, '')}] {msg}")


def verify_csv_data():
    """Verify all critical statutes exist in CSV files"""
    print("\n" + "=" * 70)
    print("STEP 1: VERIFYING CSV SOURCE DATA")
    print("=" * 70)
    
    csv_dir = Path("data/va_csv")
    all_sections = {}
    
    # Load all sections
    for csv_file in sorted(csv_dir.glob("CoVTitle*.csv")):
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    section = row.get('Section', '').strip()
                    if section:
                        body = row.get('Body', '')
                        # Clean HTML
                        if body:
                            soup = BeautifulSoup(body, 'html.parser')
                            body = soup.get_text(' ', strip=True)
                        
                        all_sections[section] = {
                            'title': row.get('Title', '').strip(),
                            'body': body,
                            'body_length': len(body),
                            'file': csv_file.name
                        }
        except Exception as e:
            log(f"Error reading {csv_file.name}: {e}", "FAIL")
    
    log(f"Loaded {len(all_sections):,} total sections from CSV files", "OK")
    
    # Check critical statutes
    print("\n--- Criminal Statutes ---")
    criminal_found = 0
    criminal_missing = []
    
    for section, description in CRITICAL_CRIMINAL_STATUTES:
        if section in all_sections:
            info = all_sections[section]
            if info['body_length'] > 100:
                log(f"{section}: {description} ({info['body_length']:,} chars)", "OK")
                criminal_found += 1
            else:
                log(f"{section}: {description} - BODY TOO SHORT ({info['body_length']} chars)", "WARN")
                criminal_missing.append((section, description, "short"))
        else:
            log(f"{section}: {description} - NOT FOUND", "FAIL")
            criminal_missing.append((section, description, "missing"))
    
    print(f"\nCriminal statutes: {criminal_found}/{len(CRITICAL_CRIMINAL_STATUTES)}")
    
    print("\n--- Civil Statutes ---")
    civil_found = 0
    civil_missing = []
    
    for section, description in CRITICAL_CIVIL_STATUTES:
        if section in all_sections:
            info = all_sections[section]
            if info['body_length'] > 100:
                log(f"{section}: {description} ({info['body_length']:,} chars)", "OK")
                civil_found += 1
            else:
                log(f"{section}: {description} - BODY TOO SHORT", "WARN")
                civil_missing.append((section, description, "short"))
        else:
            log(f"{section}: {description} - NOT FOUND", "FAIL")
            civil_missing.append((section, description, "missing"))
    
    print(f"\nCivil statutes: {civil_found}/{len(CRITICAL_CIVIL_STATUTES)}")
    
    # Summary
    total_critical = len(CRITICAL_CRIMINAL_STATUTES) + len(CRITICAL_CIVIL_STATUTES)
    total_found = criminal_found + civil_found
    all_missing = criminal_missing + civil_missing
    
    print("\n" + "-" * 50)
    print(f"TOTAL: {total_found}/{total_critical} critical statutes verified")
    
    if all_missing:
        print(f"\n⚠️  MISSING OR INCOMPLETE ({len(all_missing)}):")
        for section, desc, reason in all_missing:
            print(f"   - {section}: {desc} [{reason}]")
    
    return {
        "total_sections": len(all_sections),
        "critical_found": total_found,
        "critical_total": total_critical,
        "missing": all_missing,
        "sections": all_sections
    }


async def verify_rag_database():
    """Verify RAG database is properly populated"""
    print("\n" + "=" * 70)
    print("STEP 2: VERIFYING RAG DATABASE")
    print("=" * 70)
    
    from server.services.rag_service import rag_service
    
    try:
        rag_service._ensure_initialized()
        collection = rag_service.collection
        all_docs = collection.get()
        
        total = len(all_docs['ids'])
        log(f"Total documents in RAG: {total:,}", "OK" if total > 10000 else "WARN")
        
        # Count Virginia statutes
        va_statutes = 0
        va_cases = 0
        federal = 0
        
        for meta in all_docs['metadatas']:
            jur = meta.get('jurisdiction', '')
            doc_type = meta.get('document_type', '').lower()
            
            if jur == 'Virginia':
                if 'statute' in doc_type:
                    va_statutes += 1
                elif 'case' in doc_type:
                    va_cases += 1
            elif jur == 'Federal':
                federal += 1
        
        log(f"Virginia statutes: {va_statutes:,}", "OK" if va_statutes > 5000 else "WARN")
        log(f"Virginia case law: {va_cases:,}", "OK" if va_cases > 1000 else "WARN")
        log(f"Federal documents: {federal:,}", "OK" if federal > 100 else "WARN")
        
        return {
            "total": total,
            "va_statutes": va_statutes,
            "va_cases": va_cases,
            "federal": federal
        }
        
    except Exception as e:
        log(f"Error accessing RAG: {e}", "FAIL")
        return {"error": str(e)}


async def verify_search_accuracy():
    """Test search returns correct results"""
    print("\n" + "=" * 70)
    print("STEP 3: VERIFYING SEARCH ACCURACY")
    print("=" * 70)
    
    from server.services.rag_service import rag_service
    
    # Test cases: (query, expected_section, expected_topic)
    TEST_CASES = [
        ("18.2-57.2 assault family member", "18.2-57.2", "family"),
        ("grand larceny Virginia", "18.2-95", "larceny"),
        ("DUI Virginia Code", "18.2-266", "influence"),
        ("possession controlled substance", "18.2-250", "controlled"),
        ("arrest without warrant Virginia", "19.2-81", "arrest"),
        ("right to counsel Virginia", "19.2-163", "counsel"),
        ("statute of limitations felony", "19.2-8", "limitation"),
    ]
    
    results = []
    
    for query, expected_section, expected_keyword in TEST_CASES:
        try:
            search_results = await rag_service.search(query, n_results=5)
            
            if not search_results:
                log(f"'{query}' - NO RESULTS", "FAIL")
                results.append({"query": query, "status": "FAIL", "reason": "no results"})
                continue
            
            # Check if expected section is in top results
            found_expected = False
            found_keyword = False
            top_citations = []
            
            for r in search_results[:5]:
                meta = r.get('metadata', {})
                text = r.get('text', '').lower()
                citation = meta.get('citation', '')
                section = meta.get('section', '')
                
                top_citations.append(citation or section or "unknown")
                
                if expected_section in (citation + section):
                    found_expected = True
                if expected_keyword.lower() in text:
                    found_keyword = True
            
            if found_expected:
                log(f"'{query}' - EXACT MATCH found ({expected_section})", "OK")
                results.append({"query": query, "status": "OK", "found": expected_section})
            elif found_keyword:
                log(f"'{query}' - RELEVANT (keyword found, top: {top_citations[0]})", "WARN")
                results.append({"query": query, "status": "PARTIAL", "top": top_citations[:3]})
            else:
                log(f"'{query}' - NOT FOUND (top: {top_citations[:3]})", "FAIL")
                results.append({"query": query, "status": "FAIL", "top": top_citations[:3]})
                
        except Exception as e:
            log(f"'{query}' - ERROR: {e}", "FAIL")
            results.append({"query": query, "status": "ERROR", "error": str(e)})
    
    # Summary
    ok = sum(1 for r in results if r['status'] == 'OK')
    partial = sum(1 for r in results if r['status'] == 'PARTIAL')
    fail = sum(1 for r in results if r['status'] in ('FAIL', 'ERROR'))
    
    print(f"\nSearch accuracy: {ok} exact, {partial} partial, {fail} failed out of {len(results)}")
    
    return results


def generate_integrity_report(csv_result, rag_result, search_result):
    """Generate final integrity report"""
    print("\n" + "=" * 70)
    print("DATA INTEGRITY REPORT")
    print("=" * 70)
    
    issues = []
    
    # CSV Data
    if csv_result['critical_found'] < csv_result['critical_total']:
        missing_count = csv_result['critical_total'] - csv_result['critical_found']
        issues.append(f"CSV: {missing_count} critical statutes missing or incomplete")
    
    # RAG Database
    if isinstance(rag_result, dict) and 'error' not in rag_result:
        if rag_result.get('va_statutes', 0) < 5000:
            issues.append(f"RAG: Only {rag_result.get('va_statutes', 0)} VA statutes (need 5000+)")
        if rag_result.get('total', 0) < 10000:
            issues.append(f"RAG: Only {rag_result.get('total', 0)} total docs (need 10000+)")
    else:
        issues.append("RAG: Database access error")
    
    # Search
    search_failures = sum(1 for r in search_result if r['status'] in ('FAIL', 'ERROR'))
    if search_failures > 0:
        issues.append(f"Search: {search_failures} test queries failed")
    
    # Verdict
    print("\n" + "-" * 50)
    if not issues:
        print("✅ SYSTEM INTEGRITY: VERIFIED")
        print("   All critical data present and searchable")
        status = "VERIFIED"
    elif len(issues) <= 2:
        print("⚠️  SYSTEM INTEGRITY: NEEDS ATTENTION")
        for issue in issues:
            print(f"   - {issue}")
        status = "NEEDS_ATTENTION"
    else:
        print("❌ SYSTEM INTEGRITY: CRITICAL ISSUES")
        for issue in issues:
            print(f"   - {issue}")
        status = "CRITICAL"
    
    print("-" * 50)
    
    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "csv_data": {
            "total_sections": csv_result['total_sections'],
            "critical_found": csv_result['critical_found'],
            "critical_total": csv_result['critical_total'],
            "missing": [(s, d, r) for s, d, r in csv_result.get('missing', [])]
        },
        "rag_database": rag_result if isinstance(rag_result, dict) else {"error": str(rag_result)},
        "search_tests": search_result,
        "issues": issues
    }
    
    report_path = Path("data/integrity_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\nReport saved to: {report_path}")
    
    return status


async def main():
    print("=" * 70)
    print("CRITICAL DATA VERIFICATION")
    print("Defense Attorney Legal AI System")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Step 1: Verify CSV source data
    csv_result = verify_csv_data()
    
    # Step 2: Verify RAG database
    rag_result = await verify_rag_database()
    
    # Step 3: Verify search accuracy
    search_result = await verify_search_accuracy()
    
    # Generate report
    status = generate_integrity_report(csv_result, rag_result, search_result)
    
    return status == "VERIFIED"


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

