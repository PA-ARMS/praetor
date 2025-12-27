"""
Check completeness of all legal data sources against the catalog.
Identifies missing, incomplete, and fully downloaded sources.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

CATALOG_PATH = Path("config/source_catalog.json")
MANIFEST_ROOT = Path("data/manifests")
SOURCES_ROOT = Path("data/sources")

# Expected minimum counts for key sources (based on actual content)
EXPECTED_COUNTS = {
    # Federal - US Code has 54 titles with thousands of sections
    "US_CODE_OLRC": 5000,
    "US_CODE_GOVINFO": 100,
    "US_CODE_LII": 1000,
    
    # Federal Regulations - CFR has 50 titles
    "CFR_GOVINFO": 500,
    "ECFR": 500,
    "ECFR_XML": 50,
    
    # Federal Register
    "FED_REGISTER_GOVINFO": 100,
    "FED_REGISTER_BULK": 1,  # Just needs the bulk ZIP
    "FEDERALREGISTER_PORTAL": 100,
    
    # Federal Courts
    "US_COURTS_RULES": 500,
    "SCOTUS_PORTAL": 500,
    "SCOTUS_OPINIONS": 1000,
    "PACER": 0,  # Requires auth - skip
    
    # Case Law Aggregators
    "COURTLISTENER": 1000,
    "CAP_CASELAW": 1000,
    "JUSTIA_FED": 500,
    "GOOGLE_SCHOLAR_CASELAW": 0,  # Google blocks scraping
    
    # Virginia Statutes - Code of Virginia has 67 titles
    "VA_CODE": 2000,
    "VA_ADMIN_CODE": 1000,
    "VA_REGISTER": 500,
    "VA_LIS_BILL_TRACKING": 100,
    
    # Virginia Courts
    "VA_COURTS": 500,
    "VA_OPINIONS": 1000,
    "VA_ACMS": 50,
    
    # Virginia Case Law (Justia)
    "JUSTIA_VA_SCV": 500,
    "JUSTIA_VA_COA": 500,
    
    # Bulk Data
    "GOVINFO_BULK": 1,
    "USLM_SCHEMAS": 10,
    
    # Commercial - Skip (require auth/license)
    "WESTLAW": 0,
    "LEXIS_PLUS": 0,
    "BLOOMBERG_LAW": 0,
    "VLEX_FASTCASE": 0,
    "HEINONLINE": 0,
}


def load_catalog():
    """Load source catalog"""
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_manifest_count(source_id: str) -> int:
    """Get count of items in manifest for a source"""
    manifest_path = MANIFEST_ROOT / f"{source_id}.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return len(data.get("items", []))
        except Exception:
            pass
    return 0


def get_file_count(source_id: str) -> int:
    """Get actual file count in source directory"""
    source_dir = SOURCES_ROOT / source_id
    if source_dir.exists():
        return len(list(source_dir.rglob("*.*")))
    return 0


def check_all_sources():
    """Check completeness of all sources"""
    catalog = load_catalog()
    
    results = {
        "complete": [],
        "incomplete": [],
        "missing": [],
        "skipped": [],
        "unknown": []
    }
    
    print("=" * 80)
    print("LEGAL DATABASE SOURCE COMPLETENESS CHECK")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    for source in catalog["sources"]:
        sid = source["id"]
        name = source["name"]
        priority = source.get("priority", 5)
        auth_required = source.get("auth_required", False)
        authority_type = source.get("authority_type", "")
        jurisdiction = source.get("jurisdiction", "")
        
        # Skip commercial/auth-required sources
        if auth_required or authority_type == "commercial":
            results["skipped"].append({
                "id": sid,
                "name": name,
                "reason": "Requires authentication or commercial license"
            })
            continue
        
        manifest_count = get_manifest_count(sid)
        file_count = get_file_count(sid)
        expected = EXPECTED_COUNTS.get(sid, 100)
        
        actual = max(manifest_count, file_count)
        
        status = {
            "id": sid,
            "name": name,
            "priority": priority,
            "jurisdiction": jurisdiction,
            "manifest_count": manifest_count,
            "file_count": file_count,
            "expected": expected,
            "percentage": round((actual / expected * 100), 1) if expected > 0 else 0
        }
        
        if expected == 0:
            results["skipped"].append({**status, "reason": "Not applicable or blocked"})
        elif actual == 0:
            results["missing"].append(status)
        elif actual >= expected * 0.8:  # 80% threshold for "complete"
            results["complete"].append(status)
        else:
            results["incomplete"].append(status)
    
    # Print results by category
    print("\n" + "=" * 80)
    print("COMPLETE SOURCES (80%+ of expected)")
    print("=" * 80)
    for s in sorted(results["complete"], key=lambda x: x["priority"]):
        print(f"  ✅ [{s['priority']}] {s['id']}: {s['file_count']} files ({s['percentage']}%)")
    
    print("\n" + "=" * 80)
    print("INCOMPLETE SOURCES (need more data)")
    print("=" * 80)
    for s in sorted(results["incomplete"], key=lambda x: x["priority"]):
        print(f"  ⚠️  [{s['priority']}] {s['id']}: {s['file_count']}/{s['expected']} files ({s['percentage']}%)")
    
    print("\n" + "=" * 80)
    print("MISSING SOURCES (not downloaded)")
    print("=" * 80)
    for s in sorted(results["missing"], key=lambda x: x["priority"]):
        print(f"  ❌ [{s['priority']}] {s['id']}: 0 files (expected {s['expected']})")
    
    print("\n" + "=" * 80)
    print("SKIPPED SOURCES (auth required or not applicable)")
    print("=" * 80)
    for s in results["skipped"]:
        print(f"  ⏭️  {s.get('id', s.get('name', 'Unknown'))}: {s.get('reason', 'Skipped')}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Complete:   {len(results['complete'])}")
    print(f"  Incomplete: {len(results['incomplete'])}")
    print(f"  Missing:    {len(results['missing'])}")
    print(f"  Skipped:    {len(results['skipped'])}")
    
    # Save report
    report_path = Path("data/source_completeness_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to: {report_path}")
    
    return results


if __name__ == "__main__":
    check_all_sources()


