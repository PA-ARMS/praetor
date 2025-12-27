"""
Check case sources - Show statistics for cases from different sources
"""
from pathlib import Path
from collections import defaultdict

CASE_DIRS = {
    "CourtListener": Path("data/scenarios/courtlistener"),
    "CAP": Path("data/scenarios/cap"),
}

def count_cases():
    """Count cases from each source"""
    stats = defaultdict(int)
    
    for source_name, case_dir in CASE_DIRS.items():
        if case_dir.exists():
            case_files = list(case_dir.glob("case_*.json"))
            stats[source_name] = len(case_files)
        else:
            stats[source_name] = 0
    
    return stats

def show_stats():
    """Display statistics"""
    stats = count_cases()
    total = sum(stats.values())
    
    print("=" * 60)
    print("Case Source Statistics")
    print("=" * 60)
    print()
    
    for source_name, count in sorted(stats.items()):
        percentage = (count / total * 100) if total > 0 else 0
        print(f"{source_name:20} {count:>8,} cases ({percentage:>5.1f}%)")
    
    print()
    print(f"{'Total':20} {total:>8,} cases")
    print("=" * 60)

if __name__ == "__main__":
    show_stats()

