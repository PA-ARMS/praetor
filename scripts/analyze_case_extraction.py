"""
Analyze case extraction quality - diagnose why cases fail or show "no data"
"""
import json
import sys
from pathlib import Path
from typing import Dict, Optional, List
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.outcome_extraction_service import outcome_extraction_service

CASE_DIRS = [
    Path("data/scenarios/courtlistener"),
    Path("data/scenarios/cap"),
]


def analyze_case_file(case_file: Path) -> Dict:
    """Analyze a single case file and return diagnostic info"""
    try:
        with open(case_file, 'r', encoding='utf-8', errors='ignore') as f:
            case_data = json.load(f)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "file": case_file.name
        }
    
    # Check available text fields
    text_fields = {}
    for field in ["plain_text", "html_with_citations", "html", "html_lawbox", "snippet"]:
        if case_data.get(field):
            text_fields[field] = len(case_data[field])
    
    # Check CAP format
    casebody_text = ""
    if case_data.get("casebody"):
        casebody = case_data["casebody"]
        if casebody.get("opinions"):
            casebody_text = "\n\n".join([op.get("text", "") for op in casebody["opinions"]])
        if casebody.get("head_matter"):
            casebody_text = casebody["head_matter"] + "\n\n" + casebody_text
    
    # Get all available text
    all_text = ""
    if case_data.get("plain_text"):
        all_text = case_data["plain_text"]
    elif case_data.get("html_with_citations"):
        all_text = case_data["html_with_citations"]
    elif case_data.get("html"):
        all_text = case_data["html"]
    elif casebody_text:
        all_text = casebody_text
    
    # Try extraction
    facts_clean = ""
    outcome = "Unknown"
    
    if all_text and len(all_text.strip()) >= 100:
        facts_clean = outcome_extraction_service.extract_facts_without_outcome(all_text)
        outcome = outcome_extraction_service.extract_outcome(all_text, case_data)
    
    # Determine why it might fail
    failure_reasons = []
    
    if not all_text or len(all_text.strip()) < 100:
        failure_reasons.append("insufficient_text")
    
    if not facts_clean or len(facts_clean.strip()) < 100:
        failure_reasons.append("facts_extraction_failed")
    
    if outcome == "Unknown":
        failure_reasons.append("outcome_extraction_failed")
    
    # Check metadata
    has_case_name = bool(case_data.get("case_name") or case_data.get("name"))
    has_citation = bool(case_data.get("citation"))
    has_date = bool(case_data.get("date_filed") or case_data.get("date_created") or case_data.get("decision_date"))
    
    return {
        "status": "success" if not failure_reasons else "failed",
        "file": case_file.name,
        "text_length": len(all_text) if all_text else 0,
        "text_fields_available": text_fields,
        "has_casebody": bool(case_data.get("casebody")),
        "facts_length": len(facts_clean) if facts_clean else 0,
        "outcome": outcome,
        "failure_reasons": failure_reasons,
        "has_case_name": has_case_name,
        "has_citation": has_citation,
        "has_date": has_date,
        "case_type_inferred": case_data.get("case_type") or "Unknown",
        "jurisdiction": case_data.get("jurisdiction") or "Unknown"
    }


def analyze_sample_cases(n_samples: int = 100) -> Dict:
    """Analyze a sample of cases"""
    print(f"Analyzing {n_samples} sample cases...")
    print("=" * 60)
    
    # Get case files
    case_files = []
    for case_dir in CASE_DIRS:
        if case_dir.exists():
            case_files.extend(list(case_dir.glob("case_*.json"))[:n_samples//2])
    
    if len(case_files) > n_samples:
        case_files = case_files[:n_samples]
    
    print(f"Found {len(case_files)} case files to analyze\n")
    
    results = []
    for i, case_file in enumerate(case_files, 1):
        if i % 10 == 0:
            print(f"  Analyzing case {i}/{len(case_files)}...")
        result = analyze_case_file(case_file)
        results.append(result)
    
    # Analyze results
    total = len(results)
    successful = sum(1 for r in results if r["status"] == "success")
    failed = total - successful
    
    # Failure reasons
    failure_reasons = Counter()
    for r in results:
        for reason in r.get("failure_reasons", []):
            failure_reasons[reason] += 1
    
    # Text length distribution
    text_lengths = [r["text_length"] for r in results if r["text_length"] > 0]
    avg_text_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
    
    # Outcome distribution
    outcomes = Counter([r["outcome"] for r in results])
    
    # Fields available
    fields_available = Counter()
    for r in results:
        for field in r.get("text_fields_available", {}).keys():
            fields_available[field] += 1
    
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    print(f"\nTotal cases analyzed: {total}")
    print(f"Successful extractions: {successful} ({successful/total*100:.1f}%)")
    print(f"Failed extractions: {failed} ({failed/total*100:.1f}%)")
    
    print(f"\nAverage text length: {avg_text_length:,.0f} characters")
    print(f"Cases with text: {len(text_lengths)}/{total}")
    
    print(f"\nText fields available:")
    for field, count in fields_available.most_common():
        print(f"  {field}: {count} cases ({count/total*100:.1f}%)")
    
    print(f"\nOutcome extraction results:")
    for outcome, count in outcomes.most_common():
        print(f"  {outcome}: {count} cases ({count/total*100:.1f}%)")
    
    print(f"\nFailure reasons:")
    if failure_reasons:
        for reason, count in failure_reasons.most_common():
            print(f"  {reason}: {count} cases ({count/total*100:.1f}%)")
    else:
        print("  None - all cases extracted successfully!")
    
    # Sample failed cases
    failed_cases = [r for r in results if r["status"] == "failed"]
    if failed_cases:
        print(f"\nSample failed cases (first 5):")
        for case in failed_cases[:5]:
            print(f"  {case['file']}: {', '.join(case.get('failure_reasons', []))}")
            print(f"    Text length: {case['text_length']}, Outcome: {case['outcome']}")
    
    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "failure_reasons": dict(failure_reasons),
        "outcomes": dict(outcomes),
        "avg_text_length": avg_text_length,
        "fields_available": dict(fields_available)
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze case extraction quality")
    parser.add_argument("--samples", type=int, default=100, help="Number of cases to analyze")
    
    args = parser.parse_args()
    
    analyze_sample_cases(n_samples=args.samples)

