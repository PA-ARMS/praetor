"""Quick check of scenario processing progress"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from server.services.scenario_service import scenario_service
    scenario_service._ensure_initialized()
    db_stats = scenario_service.get_collection_stats()
    scenario_count = db_stats.get('total_scenarios', 0)
except:
    scenario_count = 0

progress_file = Path("data/scenarios/.processed_cases.json")

print("=" * 60)
print("SCENARIO PROCESSING STATUS")
print("=" * 60)
print()

if progress_file.exists():
    with open(progress_file, 'r', encoding='utf-8') as f:
        progress = json.load(f)
    
    print(f"Total Processed: {progress.get('total_processed', 0):,}")
    print(f"Last Update: {progress.get('last_update', 'N/A')}")
    print()
    
    if progress.get('progress'):
        p = progress['progress']
        print(f"Progress: {p.get('progress_percent', 0):.1f}%")
        print(f"  Attempted: {p.get('total_attempted', 0):,} / {p.get('total_to_process', 0):,}")
        print(f"  Successful: {p.get('total_processed', 0):,}")
        print(f"  Failed: {p.get('total_failed', 0):,}")
        print(f"  Current Batch: {p.get('current_batch', 0)}")
        print()
    
    if progress.get('stats'):
        stats = progress['stats']
        print(f"Statistics:")
        print(f"  Processed: {stats.get('processed', 0):,}")
        print(f"  Failed: {stats.get('failed', 0):,}")
        print(f"  Skipped: {stats.get('skipped', 0):,}")
        print()
        
        if stats.get('outcomes'):
            print("Outcome Distribution:")
            outcomes = sorted(stats['outcomes'].items(), key=lambda x: x[1], reverse=True)
            total = stats.get('processed', 1)
            for outcome, count in outcomes:
                pct = (count / total * 100) if total > 0 else 0
                print(f"  {outcome}: {count:,} ({pct:.1f}%)")
            print()
else:
    print("Progress file not found. Processing may not have started yet.")
    print()

print(f"Scenarios in Database: {scenario_count:,}")
print("=" * 60)

