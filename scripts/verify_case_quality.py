"""
Verify case data quality and extraction accuracy
"""
import json
import sys
from pathlib import Path
from typing import Dict, List
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.outcome_extraction_service import outcome_extraction_service
from server.services.scenario_service import scenario_service

CASE_DIRS = [
    Path("data/scenarios/courtlistener"),
    Path("data/scenarios/cap"),
]


def verify_extraction_quality(case_file: Path) -> Dict:
    """Verify extraction quality for a case"""
    try:
        with open(case_file, 'r', encoding='utf-8', errors='ignore') as f:
            case_data = json.load(f)
    except Exception as e:
        return {"error": str(e), "file": case_file.name}
    
    # Get text
    facts = case_data.get("plain_text", "")
    if not facts or len(facts.strip()) < 100:
        facts = case_data.get("html_with_citations", "") or \
               case_data.get("html", "") or \
               case_data.get("html_lawbox", "")
    
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
            "quality": "poor",
            "issue": "insufficient_text",
            "text_length": len(facts) if facts else 0
        }
    
    # Extract
    facts_clean = outcome_extraction_service.extract_facts_without_outcome(facts)
    outcome = outcome_extraction_service.extract_outcome(facts, case_data)
    
    # Quality checks
    issues = []
    
    if not facts_clean or len(facts_clean.strip()) < 100:
        issues.append("facts_too_short")
    
    if outcome == "Unknown":
        issues.append("outcome_unknown")
    
    # Check if facts contain outcome (shouldn't)
    facts_lower = facts_clean.lower()
    outcome_keywords = ["motion granted", "motion denied", "dismissed", "judgment for"]
    if any(kw in facts_lower for kw in outcome_keywords):
        issues.append("outcome_in_facts")
    
    # Check if we have good metadata
    has_name = bool(case_data.get("case_name") or case_data.get("name"))
    has_citation = bool(case_data.get("citation"))
    has_date = bool(case_data.get("date_filed") or case_data.get("date_created"))
    
    quality = "good"
    if issues:
        quality = "poor"
    elif not has_name or not has_citation:
        quality = "fair"
    
    return {
        "file": case_file.name,
        "quality": quality,
        "issues": issues,
        "text_length": len(facts),
        "facts_length": len(facts_clean) if facts_clean else 0,
        "outcome": outcome,
        "has_name": has_name,
        "has_citation": has_citation,
        "has_date": has_date
    }


def analyze_quality(n_samples: int = 200):
    """Analyze extraction quality across sample cases"""
    print("=" * 60)
    print("CASE EXTRACTION QUALITY ANALYSIS")
    print("=" * 60)
    
    # Get case files
    case_files = []
    for case_dir in CASE_DIRS:
        if case_dir.exists():
            case_files.extend(list(case_dir.glob("case_*.json"))[:n_samples//2])
    
    if len(case_files) > n_samples:
        case_files = case_files[:n_samples]
    
    print(f"\nAnalyzing {len(case_files)} cases...\n")
    
    results = []
    for i, case_file in enumerate(case_files, 1):
        if i % 20 == 0:
            print(f"  Processing {i}/{len(case_files)}...")
        result = verify_extraction_quality(case_file)
        results.append(result)
    
    # Analyze
    quality_dist = Counter([r.get("quality", "unknown") for r in results])
    issues_dist = Counter()
    for r in results:
        for issue in r.get("issues", []):
            issues_dist[issue] += 1
    
    outcomes = Counter([r.get("outcome", "Unknown") for r in results])
    
    avg_text = sum(r.get("text_length", 0) for r in results) / len(results)
    avg_facts = sum(r.get("facts_length", 0) for r in results) / len(results)
    
    print("\n" + "=" * 60)
    print("QUALITY ANALYSIS RESULTS")
    print("=" * 60)
    
    print(f"\nQuality Distribution:")
    for quality, count in quality_dist.most_common():
        pct = count / len(results) * 100
        print(f"  {quality}: {count} cases ({pct:.1f}%)")
    
    print(f"\nOutcome Extraction:")
    for outcome, count in outcomes.most_common():
        pct = count / len(results) * 100
        print(f"  {outcome}: {count} cases ({pct:.1f}%)")
    
    if issues_dist:
        print(f"\nIssues Found:")
        for issue, count in issues_dist.most_common():
            pct = count / len(results) * 100
            print(f"  {issue}: {count} cases ({pct:.1f}%)")
    
    print(f"\nData Completeness:")
    has_name = sum(1 for r in results if r.get("has_name"))
    has_citation = sum(1 for r in results if r.get("has_citation"))
    has_date = sum(1 for r in results if r.get("has_date"))
    print(f"  Has case name: {has_name}/{len(results)} ({has_name/len(results)*100:.1f}%)")
    print(f"  Has citation: {has_citation}/{len(results)} ({has_citation/len(results)*100:.1f}%)")
    print(f"  Has date: {has_date}/{len(results)} ({has_date/len(results)*100:.1f}%)")
    
    print(f"\nText Statistics:")
    print(f"  Average text length: {avg_text:,.0f} characters")
    print(f"  Average facts length: {avg_facts:,.0f} characters")
    print(f"  Facts extraction ratio: {avg_facts/avg_text*100:.1f}%")
    
    # Check scenario database
    print(f"\n" + "=" * 60)
    print("SCENARIO DATABASE VERIFICATION")
    print("=" * 60)
    
    try:
        scenario_service._ensure_initialized()
        db_stats = scenario_service.get_collection_stats()
        print(f"\nScenarios in database: {db_stats.get('total_scenarios', 0):,}")
        
        # Check if we can find similar scenarios
        test_query = "Contract dispute over payment terms"
        similar = scenario_service.find_similar_scenarios(test_query, n_results=5)
        print(f"Test query returned {len(similar)} similar scenarios")
        
    except Exception as e:
        print(f"Error checking database: {e}")
    
    print("=" * 60)
    
    return {
        "quality_distribution": dict(quality_dist),
        "issues": dict(issues_dist),
        "outcomes": dict(outcomes),
        "avg_text_length": avg_text,
        "avg_facts_length": avg_facts
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify case extraction quality")
    parser.add_argument("--samples", type=int, default=200, help="Number of cases to analyze")
    
    args = parser.parse_args()
    
    analyze_quality(n_samples=args.samples)

