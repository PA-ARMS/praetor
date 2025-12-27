"""Analyze which cases can be used for learning"""
import json
import sys
from pathlib import Path
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.continuous_learning_loop import (
    extract_facts_without_outcome,
    extract_actual_outcome,
    load_learned_cases,
    load_learned_case_names,
    normalize_case_name
)

def analyze_case(case_file: Path, learned_ids: set, learned_names: set):
    """Analyze a single case to see if it can be used"""
    try:
        with open(case_file, 'r', encoding='utf-8') as f:
            case_data = json.load(f)
        
        case_id = str(case_data.get("id", case_file.stem))
        case_name = case_data.get("case_name") or case_data.get("name", "")
        normalized_name = normalize_case_name(case_name)
        
        # Check if already learned
        if case_id in learned_ids:
            return {"status": "already_learned", "reason": "Already learned by ID"}
        
        if normalized_name and normalized_name in learned_names:
            return {"status": "already_learned", "reason": "Already learned by name"}
        
        # Extract facts
        facts = extract_facts_without_outcome(case_data)
        if not facts or len(facts.strip()) < 100:
            return {"status": "no_facts", "reason": f"Facts too short: {len(facts) if facts else 0} chars"}
        
        # Extract outcome
        outcome = extract_actual_outcome(case_data)
        if outcome == "Unknown":
            return {"status": "unknown_outcome", "reason": "Outcome is Unknown"}
        
        # Can be used!
        return {
            "status": "usable",
            "facts_length": len(facts),
            "outcome": outcome,
            "case_id": case_id,
            "case_name": case_name[:60] if case_name else "Unknown"
        }
        
    except Exception as e:
        return {"status": "error", "reason": str(e)}

def main(analyze_all: bool = False):
    print("=" * 70)
    print("CASE USABILITY ANALYSIS")
    print("=" * 70)
    print()
    
    # Load learned cases
    learned_ids = load_learned_cases()
    learned_names = load_learned_case_names()
    print(f"Already learned: {len(learned_ids):,} cases (by ID)")
    print(f"Already learned: {len(learned_names):,} cases (by name)")
    print()
    
    # Get all case files
    case_dirs = [
        Path("data/scenarios/courtlistener"),
        Path("data/scenarios/cap"),
    ]
    
    all_cases = []
    for case_dir in case_dirs:
        if case_dir.exists():
            source = "CAP" if "cap" in str(case_dir).lower() else "CourtListener"
            cases = list(case_dir.glob("case_*.json"))
            for case_file in cases:
                all_cases.append((case_file, source))
    
    print(f"Total case files: {len(all_cases):,}")
    print()
    
    # Analyze cases
    print("Analyzing cases...")
    print("(This may take a few minutes)")
    print()
    
    stats = defaultdict(int)
    outcomes = defaultdict(int)
    by_source = defaultdict(lambda: {"usable": 0, "total": 0})
    by_status = defaultdict(list)
    
    sample_size = len(all_cases)
    if not analyze_all and sample_size > 1000:
        print(f"Sampling first 1000 cases for quick analysis...")
        print("(Run with --all to analyze all cases)")
        sample_size = 1000
    elif analyze_all:
        print("Analyzing ALL cases (this may take several minutes)...")
    
    for i, (case_file, source) in enumerate(all_cases[:sample_size], 1):
        if i % 100 == 0:
            print(f"  Analyzed {i}/{sample_size} cases...")
        
        result = analyze_case(case_file, learned_ids, learned_names)
        status = result["status"]
        stats[status] += 1
        by_source[source]["total"] += 1
        
        if status == "usable":
            by_source[source]["usable"] += 1
            outcomes[result["outcome"]] += 1
            by_status[status].append({
                "case_id": result["case_id"],
                "outcome": result["outcome"],
                "facts_length": result["facts_length"],
                "source": source
            })
        else:
            by_status[status].append({
                "case_id": case_file.stem.replace("case_", ""),
                "reason": result.get("reason", "Unknown"),
                "source": source
            })
    
    print()
    print("=" * 70)
    print("ANALYSIS RESULTS")
    print("=" * 70)
    print()
    
    print(f"Cases Analyzed: {sample_size:,}")
    print()
    
    print("Status Breakdown:")
    for status, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        pct = (count / sample_size * 100) if sample_size > 0 else 0
        status_name = {
            "usable": "[OK] USABLE",
            "already_learned": "[SKIP] Already Learned",
            "no_facts": "[SKIP] No Facts",
            "unknown_outcome": "[SKIP] Unknown Outcome",
            "error": "[ERROR] Error"
        }.get(status, status)
        print(f"  {status_name}: {count:,} ({pct:.1f}%)")
    print()
    
    print("By Source:")
    for source in sorted(by_source.keys()):
        data = by_source[source]
        usable = data["usable"]
        total = data["total"]
        pct = (usable / total * 100) if total > 0 else 0
        print(f"  {source}:")
        print(f"    Usable: {usable:,} / {total:,} ({pct:.1f}%)")
    print()
    
    if outcomes:
        print("Usable Cases - Outcome Distribution:")
        for outcome, count in sorted(outcomes.items(), key=lambda x: x[1], reverse=True):
            pct = (count / stats["usable"] * 100) if stats["usable"] > 0 else 0
            print(f"  {outcome}: {count:,} ({pct:.1f}%)")
        print()
    
    # Show sample usable cases
    if by_status["usable"]:
        print("Sample Usable Cases (first 10):")
        for case in by_status["usable"][:10]:
            print(f"  {case['case_id']}: {case['outcome']} ({case['facts_length']} chars) - {case['source']}")
        print()
    
    # Show reasons for non-usable cases
    if by_status["no_facts"]:
        print("Sample Cases with No Facts (first 5):")
        for case in by_status["no_facts"][:5]:
            print(f"  {case['case_id']}: {case['reason']} - {case['source']}")
        print()
    
    if by_status["unknown_outcome"]:
        print("Sample Cases with Unknown Outcome (first 5):")
        for case in by_status["unknown_outcome"][:5]:
            print(f"  {case['case_id']}: {case['source']}")
        print()
    
    # Summary
    usable_count = stats.get("usable", 0)
    total_available = len(all_cases)
    if analyze_all:
        estimated_usable = usable_count
    else:
        estimated_usable = int((usable_count / sample_size) * total_available) if sample_size > 0 else 0
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Usable cases (from sample): {usable_count:,}")
    print(f"Estimated total usable: ~{estimated_usable:,} of {total_available:,}")
    print(f"Already learned: {len(learned_ids):,}")
    print(f"Remaining to learn: ~{estimated_usable - len(learned_ids):,}")
    print("=" * 70)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Analyze all cases (slower)")
    args = parser.parse_args()
    
    main(analyze_all=args.all)

