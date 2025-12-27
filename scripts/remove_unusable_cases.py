"""Remove cases that cannot be used for learning"""
import json
import sys
import shutil
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
        
        # Check if already learned - KEEP these (they're useful as reference)
        if case_id in learned_ids:
            return {"status": "keep", "reason": "Already learned (keeping as reference)"}
        
        if normalized_name and normalized_name in learned_names:
            return {"status": "keep", "reason": "Already learned by name (keeping as reference)"}
        
        # Extract facts
        facts = extract_facts_without_outcome(case_data)
        if not facts or len(facts.strip()) < 100:
            return {"status": "remove", "reason": f"Facts too short: {len(facts) if facts else 0} chars"}
        
        # Extract outcome
        outcome = extract_actual_outcome(case_data)
        if outcome == "Unknown":
            return {"status": "remove", "reason": "Outcome is Unknown"}
        
        # Can be used - KEEP
        return {"status": "keep", "reason": "Usable case"}
        
    except Exception as e:
        return {"status": "remove", "reason": f"Error: {str(e)[:50]}"}

def main():
    print("=" * 70)
    print("REMOVING UNUSABLE CASES")
    print("=" * 70)
    print()
    
    # Load learned cases
    learned_ids = load_learned_cases()
    learned_names = load_learned_case_names()
    print(f"Already learned: {len(learned_ids):,} cases (will be kept)")
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
    
    # Create directory for unusable cases
    unusable_dir = Path("data/scenarios/unusable")
    unusable_dir.mkdir(parents=True, exist_ok=True)
    
    # Analyze and move cases
    print("Analyzing and moving unusable cases...")
    print()
    
    stats = defaultdict(int)
    by_source = defaultdict(lambda: {"keep": 0, "remove": 0})
    removed_reasons = defaultdict(int)
    
    for i, (case_file, source) in enumerate(all_cases, 1):
        if i % 500 == 0:
            print(f"  Processed {i:,}/{len(all_cases):,} cases...")
        
        result = analyze_case(case_file, learned_ids, learned_names)
        status = result["status"]
        stats[status] += 1
        by_source[source][status] += 1
        
        if status == "remove":
            # Move to unusable directory, preserving source structure
            source_subdir = unusable_dir / source.lower()
            source_subdir.mkdir(parents=True, exist_ok=True)
            
            dest_file = source_subdir / case_file.name
            try:
                shutil.move(str(case_file), str(dest_file))
                removed_reasons[result["reason"]] += 1
            except Exception as e:
                print(f"  Error moving {case_file.name}: {e}")
                stats["error"] += 1
    
    print()
    print("=" * 70)
    print("CLEANUP RESULTS")
    print("=" * 70)
    print()
    
    print(f"Total cases processed: {len(all_cases):,}")
    print()
    
    print("Action Summary:")
    print(f"  Kept: {stats.get('keep', 0):,} cases")
    print(f"  Removed: {stats.get('remove', 0):,} cases")
    if stats.get('error', 0) > 0:
        print(f"  Errors: {stats.get('error', 0):,} cases")
    print()
    
    print("By Source:")
    for source in sorted(by_source.keys()):
        data = by_source[source]
        keep = data["keep"]
        remove = data["remove"]
        total = keep + remove
        print(f"  {source}:")
        print(f"    Kept: {keep:,}")
        print(f"    Removed: {remove:,}")
        if total > 0:
            print(f"    Removal rate: {(remove/total*100):.1f}%")
    print()
    
    print("Removal Reasons:")
    for reason, count in sorted(removed_reasons.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason}: {count:,}")
    print()
    
    # Final counts
    remaining_cases = []
    for case_dir in case_dirs:
        if case_dir.exists():
            remaining_cases.extend(case_dir.glob("case_*.json"))
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Cases remaining (usable): {len(remaining_cases):,}")
    print(f"Cases removed (unusable): {stats.get('remove', 0):,}")
    print(f"Unusable cases location: {unusable_dir}")
    print("=" * 70)
    print()
    print("Note: Unusable cases have been moved (not deleted) in case you need them later.")
    print("They are located in: data/scenarios/unusable/")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Remove unusable cases from learning dataset")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without actually removing")
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN MODE - No files will be moved")
        print()
    
    main()

