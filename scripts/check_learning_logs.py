"""Check learning system logs and status"""
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check learning session log
log_file = Path("data/scenarios/.learning_session.log")
print("=" * 60)
print("LEARNING SESSION LOG")
print("=" * 60)
if log_file.exists():
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"Log file exists ({len(lines)} lines)")
        print("\nLast 30 lines:")
        print("-" * 60)
        for line in lines[-30:]:
            print(line.rstrip())
else:
    print("Log file not found - no learning session has been run yet")

# Check progress file
progress_file = Path("data/scenarios/courtlistener/.processed_cases.json")
print("\n" + "=" * 60)
print("PROGRESS FILE")
print("=" * 60)
if progress_file.exists():
    with open(progress_file, 'r') as f:
        data = json.load(f)
    
    print(f"Total processed: {data.get('total_processed', 0):,}")
    print(f"Last update: {data.get('last_update', 'N/A')}")
    
    stats = data.get('stats', {})
    print(f"\nStats:")
    print(f"  Processed: {stats.get('processed', 0):,}")
    print(f"  Failed: {stats.get('failed', 0):,}")
    print(f"  Skipped: {stats.get('skipped', 0):,}")
    
    progress = data.get('progress', {})
    if progress:
        print(f"\nProgress Info:")
        print(f"  Total to process: {progress.get('total_to_process', 0):,}")
        print(f"  Total attempted: {progress.get('total_attempted', 0):,}")
        print(f"  Progress: {progress.get('progress_percent', 0):.1f}%")
        print(f"  Current batch: {progress.get('current_batch', 'N/A')}")
        print(f"  Batch processed: {progress.get('batch_processed', 0)}")
        print(f"  Batch failed: {progress.get('batch_failed', 0)}")
    
    # Check if recently updated
    last_update_str = data.get('last_update', '')
    if last_update_str:
        try:
            last_update = datetime.fromisoformat(last_update_str)
            time_diff = datetime.now() - last_update
            print(f"\nTime since last update: {time_diff}")
            if time_diff < timedelta(minutes=2):
                print("  ✓ Processing appears to be active")
            else:
                print("  ⚠ Processing appears to be idle")
        except:
            pass
else:
    print("Progress file not found")

# Check session status
print("\n" + "=" * 60)
print("SESSION STATUS")
print("=" * 60)
try:
    from server.services.learning_session_service import learning_session_service
    status = learning_session_service.get_status()
    print(f"Status: {status.get('status', 'unknown')}")
    session = status.get('session', {})
    print(f"Running: {session.get('is_running', False)}")
    if session.get('started_at'):
        print(f"Started at: {session.get('started_at')}")
    if session.get('max_cases'):
        print(f"Max cases: {session.get('max_cases'):,}")
    if session.get('pid'):
        print(f"PID: {session.get('pid')}")
except Exception as e:
    print(f"Error checking session status: {e}")

# Check database stats
print("\n" + "=" * 60)
print("DATABASE STATS")
print("=" * 60)
try:
    from server.services.scenario_service import scenario_service
    scenario_service._ensure_initialized()
    stats = scenario_service.get_collection_stats()
    print(f"Total scenarios in database: {stats.get('total_scenarios', 0):,}")
except Exception as e:
    print(f"Error checking database stats: {e}")

print("\n" + "=" * 60)

