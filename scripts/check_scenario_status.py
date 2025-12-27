"""Check scenario database status"""
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from server.services.scenario_service import scenario_service

async def check_status():
    """Check scenario database status"""
    print("=" * 60)
    print("SCENARIO DATABASE STATUS")
    print("=" * 60)
    
    # Initialize service
    scenario_service._ensure_initialized()
    
    # Get stats
    stats = scenario_service.get_collection_stats()
    
    print(f"\nTotal scenarios in database: {stats.get('total_scenarios', 0):,}")
    print(f"Collection: {stats.get('collection_name', 'N/A')}")
    
    # Check learned cases
    import json
    learned_file = Path("data/scenarios/.learned_cases.json")
    if learned_file.exists():
        with open(learned_file, 'r', encoding='utf-8') as f:
            learned = json.load(f)
        learned_count = len(learned.get("learned_case_ids", []))
        print(f"\nLearned cases: {learned_count:,}")
        
        # Check case files
        cap_files = len(list(Path("data/scenarios/cap").glob("case_*.json")))
        cl_files = len(list(Path("data/scenarios/courtlistener").glob("case_*.json")))
        total_files = cap_files + cl_files
        
        print(f"Total case files: {total_files:,}")
        print(f"  - CAP: {cap_files:,}")
        print(f"  - CourtListener: {cl_files:,}")
        
        print(f"\nProcessing status:")
        print(f"  - Cases learned: {learned_count:,}")
        print(f"  - Scenarios in DB: {stats.get('total_scenarios', 0):,}")
        print(f"  - Remaining to process: {total_files - learned_count:,}")
        
        if stats.get('total_scenarios', 0) < learned_count:
            print(f"\n⚠ WARNING: Only {stats.get('total_scenarios', 0)} scenarios in DB but {learned_count} cases learned!")
            print("  This suggests scenarios are not being added to the database.")
        elif stats.get('total_scenarios', 0) == learned_count:
            print(f"\n✓ All learned cases are in the scenario database!")
        else:
            print(f"\n✓ More scenarios than learned cases (may include manually added scenarios)")
    else:
        print("\nNo learned cases file found")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(check_status())

