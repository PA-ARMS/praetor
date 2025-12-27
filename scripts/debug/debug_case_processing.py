"""
Debug script to check why cases are failing to process
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.outcome_extraction_service import outcome_extraction_service

CASE_DIR = Path("data/scenarios/courtlistener")

def check_case(case_file: Path):
    """Check a single case file"""
    print(f"\n{'='*60}")
    print(f"Checking: {case_file.name}")
    print(f"{'='*60}")
    
    try:
        with open(case_file, 'r', encoding='utf-8') as f:
            case_data = json.load(f)
    except Exception as e:
        print(f"ERROR: Could not load JSON: {e}")
        return
    
    # Check for text content
    plain_text = case_data.get("plain_text", "")
    html_citations = case_data.get("html_with_citations", "")
    html = case_data.get("html", "")
    html_lawbox = case_data.get("html_lawbox", "")
    
    print(f"plain_text: {len(plain_text) if plain_text else 0} chars")
    print(f"html_with_citations: {len(html_citations) if html_citations else 0} chars")
    print(f"html: {len(html) if html else 0} chars")
    print(f"html_lawbox: {len(html_lawbox) if html_lawbox else 0} chars")
    
    # Get facts
    facts = plain_text or html_citations or html or html_lawbox
    
    if not facts or len(facts.strip()) < 100:
        print(f"[FAIL] Insufficient text ({len(facts) if facts else 0} chars)")
        return
    
    print(f"[OK] Has sufficient text: {len(facts)} chars")
    
    # Try outcome extraction
    outcome = outcome_extraction_service.extract_outcome(facts, case_data)
    print(f"Outcome: {outcome}")
    
    if outcome == "Unknown":
        print(f"[FAIL] Could not determine outcome")
        # Show first 500 chars to help debug
        print(f"\nFirst 500 chars of text:")
        print(facts[:500])
        return
    
    print(f"[OK] Outcome determined: {outcome}")
    
    # Try facts extraction
    facts_clean = outcome_extraction_service.extract_facts_without_outcome(facts)
    print(f"Cleaned facts: {len(facts_clean) if facts_clean else 0} chars")
    
    if not facts_clean or len(facts_clean.strip()) < 100:
        print(f"[FAIL] Facts extraction removed too much ({len(facts_clean) if facts_clean else 0} chars)")
        return
    
    print(f"[OK] Facts extraction successful")
    print(f"\n[SUCCESS] Case should process successfully!")


# Check a few failed cases
case_files = sorted(CASE_DIR.glob("case_*.json"))
print(f"Total case files: {len(case_files)}")

# Check first few that haven't been processed
for case_file in case_files[:5]:
    check_case(case_file)

