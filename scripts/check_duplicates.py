"""
Check for duplicate cases between CourtListener and CAP
Compares case IDs, names, and citations to detect duplicates
"""
import json
from pathlib import Path
from collections import defaultdict
import re

COURTLISTENER_DIR = Path("data/scenarios/courtlistener")
CAP_DIR = Path("data/scenarios/cap")

def normalize_case_name(name: str) -> str:
    """Normalize case name for comparison"""
    if not name:
        return ""
    # Remove extra whitespace, convert to lowercase
    name = re.sub(r'\s+', ' ', name.lower().strip())
    # Remove common suffixes
    name = re.sub(r'\s+v\.?\s+', ' v ', name)
    return name

def extract_citation(case_data: dict) -> str:
    """Extract citation from case data"""
    # Try various citation fields
    citation = (
        case_data.get("citation") or
        case_data.get("citations", [{}])[0].get("cite") if case_data.get("citations") else None or
        case_data.get("reporter") or
        ""
    )
    return str(citation).strip()

def load_cases_from_dir(case_dir: Path, source_name: str):
    """Load all cases from a directory"""
    cases = {}
    case_files = list(case_dir.glob("case_*.json"))
    
    print(f"Loading {len(case_files)} cases from {source_name}...")
    
    for case_file in case_files:
        try:
            with open(case_file, 'r', encoding='utf-8') as f:
                case_data = json.load(f)
            
            case_id = str(case_data.get("id", case_file.stem))
            case_name = case_data.get("case_name") or case_data.get("name", "")
            citation = extract_citation(case_data)
            
            cases[case_id] = {
                "id": case_id,
                "name": case_name,
                "normalized_name": normalize_case_name(case_name),
                "citation": citation,
                "file": str(case_file),
                "source": source_name
            }
        except Exception as e:
            print(f"  Error loading {case_file.name}: {e}")
            continue
    
    return cases

def find_duplicates(courtlistener_cases: dict, cap_cases: dict):
    """Find duplicate cases between sources"""
    duplicates = []
    
    # Check by normalized case name
    cl_by_name = defaultdict(list)
    for case_id, case in courtlistener_cases.items():
        if case["normalized_name"]:
            cl_by_name[case["normalized_name"]].append(case)
    
    cap_by_name = defaultdict(list)
    for case_id, case in cap_cases.items():
        if case["normalized_name"]:
            cap_by_name[case["normalized_name"]].append(case)
    
    # Find matches by name
    name_matches = set(cl_by_name.keys()) & set(cap_by_name.keys())
    
    for name in name_matches:
        cl_cases = cl_by_name[name]
        cap_cases_list = cap_by_name[name]
        
        for cl_case in cl_cases:
            for cap_case in cap_cases_list:
                duplicates.append({
                    "courtlistener": cl_case,
                    "cap": cap_case,
                    "match_type": "name",
                    "confidence": "high" if len(name) > 20 else "medium"
                })
    
    return duplicates

def main():
    print("=" * 60)
    print("DUPLICATE CASE DETECTION")
    print("=" * 60)
    print()
    
    # Load cases
    courtlistener_cases = {}
    cap_cases = {}
    
    if COURTLISTENER_DIR.exists():
        courtlistener_cases = load_cases_from_dir(COURTLISTENER_DIR, "CourtListener")
    else:
        print(f"CourtListener directory not found: {COURTLISTENER_DIR}")
    
    if CAP_DIR.exists():
        cap_cases = load_cases_from_dir(CAP_DIR, "CAP")
    else:
        print(f"CAP directory not found: {CAP_DIR}")
    
    print()
    print(f"CourtListener: {len(courtlistener_cases)} cases")
    print(f"CAP: {len(cap_cases)} cases")
    print(f"Total: {len(courtlistener_cases) + len(cap_cases)} cases")
    print()
    
    # Check for duplicate IDs (unlikely but possible)
    cl_ids = set(courtlistener_cases.keys())
    cap_ids = set(cap_cases.keys())
    duplicate_ids = cl_ids & cap_ids
    
    if duplicate_ids:
        print(f"⚠ Found {len(duplicate_ids)} cases with identical IDs:")
        for case_id in list(duplicate_ids)[:10]:
            print(f"  ID {case_id}:")
            print(f"    CourtListener: {courtlistener_cases[case_id]['name']}")
            print(f"    CAP: {cap_cases[case_id]['name']}")
        if len(duplicate_ids) > 10:
            print(f"  ... and {len(duplicate_ids) - 10} more")
        print()
    else:
        print("[OK] No duplicate case IDs found (different ID systems)")
        print()
    
    # Check for duplicate names
    duplicates = find_duplicates(courtlistener_cases, cap_cases)
    
    if duplicates:
        print(f"⚠ Found {len(duplicates)} potential duplicate cases (by name):")
        print()
        for i, dup in enumerate(duplicates[:20], 1):
            cl = dup["courtlistener"]
            cap = dup["cap"]
            print(f"{i}. {cl['name']}")
            print(f"   CourtListener ID: {cl['id']}")
            print(f"   CAP ID: {cap['id']}")
            print(f"   Match confidence: {dup['confidence']}")
            print()
        
        if len(duplicates) > 20:
            print(f"... and {len(duplicates) - 20} more potential duplicates")
        print()
        
        print(f"Total unique cases (estimated): {len(courtlistener_cases) + len(cap_cases) - len(duplicates)}")
    else:
        print("[OK] No duplicate case names found")
        print("  Cases appear to be from different sources/sets")
        print()
    
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"CourtListener cases: {len(courtlistener_cases):,}")
    print(f"CAP cases: {len(cap_cases):,}")
    print(f"Total cases: {len(courtlistener_cases) + len(cap_cases):,}")
    if duplicates:
        print(f"Potential duplicates: {len(duplicates):,}")
        print(f"Estimated unique: {len(courtlistener_cases) + len(cap_cases) - len(duplicates):,}")
    print("=" * 60)

if __name__ == "__main__":
    main()

