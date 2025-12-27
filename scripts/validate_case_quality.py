"""
Validate Case Quality - Check if downloaded cases have enough data for learning
"""
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.outcome_extraction_service import outcome_extraction_service

CASE_DIR = Path("data/scenarios/courtlistener")


def validate_case(case_file: Path) -> Dict:
    """Validate a single case file for learning readiness"""
    result = {
        "case_id": case_file.stem.replace("case_", ""),
        "has_text": False,
        "text_length": 0,
        "has_outcome": False,
        "outcome": None,
        "has_facts": False,
        "facts_length": 0,
        "usable": False,
        "issues": []
    }
    
    try:
        with open(case_file, 'r', encoding='utf-8') as f:
            case_data = json.load(f)
    except Exception as e:
        result["issues"].append(f"JSON error: {e}")
        return result
    
    # Check for text content
    plain_text = case_data.get("plain_text", "")
    html_citations = case_data.get("html_with_citations", "")
    html = case_data.get("html", "")
    html_lawbox = case_data.get("html_lawbox", "")
    
    facts = plain_text or html_citations or html or html_lawbox
    
    if not facts or len(facts.strip()) < 100:
        result["issues"].append("Insufficient text (< 100 chars)")
        return result
    
    result["has_text"] = True
    result["text_length"] = len(facts)
    
    # Check if outcome can be extracted
    outcome = outcome_extraction_service.extract_outcome(facts, case_data)
    if outcome == "Unknown":
        result["issues"].append("Cannot determine outcome")
        return result
    
    result["has_outcome"] = True
    result["outcome"] = outcome
    
    # Check if facts can be extracted (without outcome)
    facts_clean = outcome_extraction_service.extract_facts_without_outcome(facts)
    if not facts_clean or len(facts_clean.strip()) < 100:
        result["issues"].append("Facts extraction removed too much text")
        return result
    
    result["has_facts"] = True
    result["facts_length"] = len(facts_clean)
    
    # Case is usable if it has all requirements
    result["usable"] = True
    
    return result


def validate_all_cases(sample_size: int = None) -> Dict:
    """Validate all or a sample of cases"""
    case_files = sorted(CASE_DIR.glob("case_*.json"))
    
    if sample_size:
        import random
        case_files = random.sample(case_files, min(sample_size, len(case_files)))
        print(f"Validating sample of {len(case_files)} cases...")
    else:
        print(f"Validating all {len(case_files)} cases...")
    
    results = []
    usable_count = 0
    outcome_distribution = {}
    text_lengths = []
    facts_lengths = []
    
    for i, case_file in enumerate(case_files, 1):
        if i % 100 == 0:
            print(f"  Validated {i}/{len(case_files)} cases...")
        
        result = validate_case(case_file)
        results.append(result)
        
        if result["usable"]:
            usable_count += 1
            outcome = result["outcome"]
            outcome_distribution[outcome] = outcome_distribution.get(outcome, 0) + 1
            text_lengths.append(result["text_length"])
            facts_lengths.append(result["facts_length"])
    
    # Analyze issues
    issue_counts = {}
    for result in results:
        for issue in result["issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    
    return {
        "total_cases": len(results),
        "usable_cases": usable_count,
        "unusable_cases": len(results) - usable_count,
        "usability_rate": (usable_count / len(results) * 100) if results else 0,
        "outcome_distribution": outcome_distribution,
        "average_text_length": sum(text_lengths) / len(text_lengths) if text_lengths else 0,
        "average_facts_length": sum(facts_lengths) / len(facts_lengths) if facts_lengths else 0,
        "min_text_length": min(text_lengths) if text_lengths else 0,
        "max_text_length": max(text_lengths) if text_lengths else 0,
        "min_facts_length": min(facts_lengths) if facts_lengths else 0,
        "max_facts_length": max(facts_lengths) if facts_lengths else 0,
        "common_issues": issue_counts,
        "sample_results": results[:10] if sample_size else []
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate case quality for learning")
    parser.add_argument("--sample", type=int, help="Validate only a sample of N cases")
    parser.add_argument("--detailed", action="store_true", help="Show detailed results for each case")
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"CASE QUALITY VALIDATION")
    print(f"{'='*60}\n")
    
    stats = validate_all_cases(sample_size=args.sample)
    
    print(f"\n{'='*60}")
    print(f"VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"Total cases checked: {stats['total_cases']:,}")
    print(f"Usable cases: {stats['usable_cases']:,} ({stats['usability_rate']:.1f}%)")
    print(f"Unusable cases: {stats['unusable_cases']:,} ({100 - stats['usability_rate']:.1f}%)")
    print(f"\nText Content Statistics:")
    print(f"  Average text length: {stats['average_text_length']:,.0f} chars")
    print(f"  Text length range: {stats['min_text_length']:,} - {stats['max_text_length']:,} chars")
    print(f"  Average facts length: {stats['average_facts_length']:,.0f} chars")
    print(f"  Facts length range: {stats['min_facts_length']:,} - {stats['max_facts_length']:,} chars")
    print(f"\nOutcome Distribution (usable cases):")
    for outcome, count in sorted(stats['outcome_distribution'].items(), key=lambda x: x[1], reverse=True):
        percentage = (count / stats['usable_cases'] * 100) if stats['usable_cases'] > 0 else 0
        print(f"  {outcome}: {count:,} ({percentage:.1f}%)")
    
    if stats['common_issues']:
        print(f"\nCommon Issues (unusable cases):")
        for issue, count in sorted(stats['common_issues'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / stats['unusable_cases'] * 100) if stats['unusable_cases'] > 0 else 0
            print(f"  {issue}: {count:,} ({percentage:.1f}%)")
    
    print(f"\n{'='*60}")
    
    # Assessment
    print(f"\nASSESSMENT:")
    if stats['usability_rate'] >= 70:
        print(f"[EXCELLENT] {stats['usability_rate']:.1f}% of cases are usable for learning")
    elif stats['usability_rate'] >= 50:
        print(f"[GOOD] {stats['usability_rate']:.1f}% of cases are usable for learning")
    elif stats['usability_rate'] >= 30:
        print(f"[MODERATE] {stats['usability_rate']:.1f}% of cases are usable - may need more cases")
    else:
        print(f"[LOW] Only {stats['usability_rate']:.1f}% of cases are usable - may need better extraction")
    
    if stats['usable_cases'] >= 1000:
        print(f"[SUFFICIENT DATA] {stats['usable_cases']:,} usable cases is good for learning")
    elif stats['usable_cases'] >= 500:
        print(f"[MODERATE DATA] {stats['usable_cases']:,} usable cases - more would be better")
    else:
        print(f"[LIMITED DATA] Only {stats['usable_cases']:,} usable cases - need more")
    
    print(f"\n{'='*60}\n")
    
    if args.detailed and stats['sample_results']:
        print("Sample Case Details:")
        for result in stats['sample_results'][:5]:
            print(f"\n  Case {result['case_id']}:")
            print(f"    Usable: {result['usable']}")
            if result['usable']:
                print(f"    Outcome: {result['outcome']}")
                print(f"    Text: {result['text_length']:,} chars")
                print(f"    Facts: {result['facts_length']:,} chars")
            else:
                print(f"    Issues: {', '.join(result['issues'])}")

