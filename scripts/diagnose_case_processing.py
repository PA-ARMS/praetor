"""
Diagnose case processing - find why cases fail and show "no data"
"""
import json
import sys
from pathlib import Path
from typing import Dict, List
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.outcome_extraction_service import outcome_extraction_service

PROCESSED_FILE = Path("data/scenarios/.processed_cases.json")
CASE_DIRS = [
    Path("data/scenarios/courtlistener"),
    Path("data/scenarios/cap"),
]


def check_why_case_fails(case_file: Path) -> Dict:
    """Check why a specific case file would fail processing"""
    try:
        with open(case_file, 'r', encoding='utf-8', errors='ignore') as f:
            case_data = json.load(f)
    except Exception as e:
        return {
            "file": case_file.name,
            "error": f"JSON decode error: {str(e)}",
            "reason": "file_corrupt"
        }
    
    # Step 1: Check for text content
    facts = case_data.get("plain_text", "")
    if not facts or len(facts.strip()) < 100:
        facts = case_data.get("html_with_citations", "") or \
               case_data.get("html", "") or \
               case_data.get("html_lawbox", "")
    
    # Step 2: Check CAP format
    if not facts or len(facts.strip()) < 100:
        if case_data.get("casebody"):
            casebody = case_data["casebody"]
            opinion_texts = []
            if casebody.get("opinions"):
                for opinion in casebody["opinions"]:
                    if opinion.get("text"):
                        opinion_texts.append(opinion["text"])
            if casebody.get("head_matter"):
                opinion_texts.insert(0, casebody["head_matter"])
            if opinion_texts:
                facts = "\n\n".join(opinion_texts)
    
    if not facts or len(facts.strip()) < 100:
        return {
            "file": case_file.name,
            "reason": "insufficient_text",
            "text_length": len(facts) if facts else 0,
            "has_plain_text": bool(case_data.get("plain_text")),
            "has_html": bool(case_data.get("html_with_citations") or case_data.get("html")),
            "has_casebody": bool(case_data.get("casebody"))
        }
    
    # Step 3: Check facts extraction
    facts_clean = outcome_extraction_service.extract_facts_without_outcome(facts)
    if not facts_clean or len(facts_clean.strip()) < 100:
        return {
            "file": case_file.name,
            "reason": "facts_extraction_failed",
            "original_text_length": len(facts),
            "facts_clean_length": len(facts_clean) if facts_clean else 0,
            "text_preview": facts[:200] if facts else ""
        }
    
    # Step 4: Check outcome extraction
    outcome = outcome_extraction_service.extract_outcome(facts, case_data)
    if outcome == "Unknown":
        return {
            "file": case_file.name,
            "reason": "outcome_extraction_failed",
            "text_length": len(facts),
            "facts_length": len(facts_clean),
            "text_preview": facts[:500] if facts else "",
            "has_disposition": bool(case_data.get("disposition")),
            "disposition": case_data.get("disposition")
        }
    
    # Success
    return {
        "file": case_file.name,
        "reason": "success",
        "outcome": outcome,
        "text_length": len(facts),
        "facts_length": len(facts_clean)
    }


def analyze_unprocessed_cases(n_samples: int = 100):
    """Analyze unprocessed cases to see why they're failing"""
    print("=" * 60)
    print("DIAGNOSING UNPROCESSED CASES")
    print("=" * 60)
    
    # Load processed IDs
    processed_ids = set()
    if PROCESSED_FILE.exists():
        try:
            with open(PROCESSED_FILE, 'r') as f:
                data = json.load(f)
                processed_ids = set(data.get("processed_ids", []))
        except:
            pass
    
    print(f"\nProcessed cases: {len(processed_ids):,}")
    
    # Get all case files
    all_case_files = []
    for case_dir in CASE_DIRS:
        if case_dir.exists():
            all_case_files.extend(list(case_dir.glob("case_*.json")))
    
    print(f"Total case files: {len(all_case_files):,}")
    
    # Find unprocessed
    unprocessed = []
    for case_file in all_case_files:
        case_id = case_file.stem.replace("case_", "")
        if case_id not in processed_ids:
            unprocessed.append(case_file)
    
    print(f"Unprocessed cases: {len(unprocessed):,}")
    
    # Sample unprocessed cases
    sample = unprocessed[:n_samples] if len(unprocessed) > n_samples else unprocessed
    print(f"\nAnalyzing {len(sample)} unprocessed cases...\n")
    
    results = []
    for i, case_file in enumerate(sample, 1):
        if i % 10 == 0:
            print(f"  Analyzing {i}/{len(sample)}...")
        result = check_why_case_fails(case_file)
        results.append(result)
    
    # Analyze results
    reasons = Counter([r["reason"] for r in results])
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS RESULTS")
    print("=" * 60)
    
    print(f"\nFailure reasons:")
    for reason, count in reasons.most_common():
        pct = count / len(results) * 100
        print(f"  {reason}: {count} cases ({pct:.1f}%)")
    
    # Show examples of each failure type
    print(f"\nExamples by failure type:")
    for reason in reasons.keys():
        examples = [r for r in results if r["reason"] == reason][:3]
        print(f"\n  {reason}:")
        for ex in examples:
            print(f"    - {ex['file']}")
            if "text_length" in ex:
                print(f"      Text length: {ex.get('text_length', 0)}")
            if "text_preview" in ex:
                preview = ex["text_preview"][:100].replace("\n", " ")
                print(f"      Preview: {preview}...")
    
    # Success rate
    successful = sum(1 for r in results if r["reason"] == "success")
    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Cases that WOULD succeed: {successful} ({successful/len(results)*100:.1f}%)")
    print(f"  Cases that WOULD fail: {len(results) - successful} ({(len(results)-successful)/len(results)*100:.1f}%)")
    print(f"{'=' * 60}")
    
    return {
        "total_analyzed": len(results),
        "successful": successful,
        "failed": len(results) - successful,
        "failure_reasons": dict(reasons)
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnose why cases fail processing")
    parser.add_argument("--samples", type=int, default=100, help="Number of unprocessed cases to analyze")
    
    args = parser.parse_args()
    
    analyze_unprocessed_cases(n_samples=args.samples)

