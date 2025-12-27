"""
Monitor Download Progress - Check status of bulk download and processing
"""
import json
from pathlib import Path
from datetime import datetime

DOWNLOAD_PROGRESS = Path("data/scenarios/courtlistener/.download_progress.json")
PROCESSED_PROGRESS = Path("data/scenarios/courtlistener/.processed_cases.json")
CASE_DIR = Path("data/scenarios/courtlistener")


def format_size(size_bytes):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def monitor_status():
    """Monitor and display download/processing status"""
    print(f"\n{'='*60}")
    print(f"DOWNLOAD & PROCESSING STATUS")
    print(f"{'='*60}\n")
    
    # Check downloaded cases
    case_files = list(CASE_DIR.glob("case_*.json"))
    total_size = sum(f.stat().st_size for f in case_files)
    avg_size = total_size / len(case_files) if case_files else 0
    
    print(f"Downloaded Cases:")
    print(f"  Total files: {len(case_files):,}")
    print(f"  Total size: {format_size(total_size)}")
    print(f"  Average size: {format_size(avg_size)}")
    
    # Check download progress
    if DOWNLOAD_PROGRESS.exists():
        with open(DOWNLOAD_PROGRESS, 'r') as f:
            progress = json.load(f)
        
        print(f"\nDownload Progress:")
        print(f"  Last page: {progress.get('last_page', 0):,}")
        print(f"  Total downloaded: {progress.get('total_downloaded', 0):,}")
        print(f"  Last case ID: {progress.get('last_case_id', 'N/A')}")
        if 'start_time' in progress:
            start = datetime.fromisoformat(progress['start_time'])
            elapsed = datetime.now() - start
            print(f"  Running for: {elapsed}")
        if 'last_update' in progress:
            last_update = datetime.fromisoformat(progress['last_update'])
            print(f"  Last update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        if progress.get('errors'):
            print(f"  Errors: {len(progress['errors'])}")
    else:
        print(f"\nDownload Progress: No progress file found (download may not be running)")
    
    # Check processing progress
    if PROCESSED_PROGRESS.exists():
        with open(PROCESSED_PROGRESS, 'r') as f:
            processed = json.load(f)
        
        print(f"\nProcessing Progress:")
        print(f"  Processed cases: {processed.get('total_processed', 0):,}")
        if 'stats' in processed:
            stats = processed['stats']
            print(f"  Successful: {stats.get('processed', 0):,}")
            print(f"  Failed: {stats.get('failed', 0):,}")
            print(f"  Skipped: {stats.get('skipped', 0):,}")
            if 'outcomes' in stats:
                print(f"  Outcome distribution:")
                for outcome, count in sorted(stats['outcomes'].items(), key=lambda x: x[1], reverse=True):
                    print(f"    {outcome}: {count:,}")
        if 'last_update' in processed:
            last_update = datetime.fromisoformat(processed['last_update'])
            print(f"  Last update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"\nProcessing Progress: No processing file found")
    
    # Check scenario database
    try:
        from server.services.scenario_service import scenario_service
        scenario_service._ensure_initialized()
        db_stats = scenario_service.get_collection_stats()
        print(f"\nScenario Database:")
        print(f"  Total scenarios: {db_stats.get('total_scenarios', 0):,}")
    except Exception as e:
        print(f"\nScenario Database: Error checking - {e}")
    
    # Estimate completion
    if DOWNLOAD_PROGRESS.exists() and case_files:
        with open(DOWNLOAD_PROGRESS, 'r') as f:
            progress = json.load(f)
        
        target = 15_000_000  # 15 million cases target
        downloaded = progress.get('total_downloaded', len(case_files))
        
        if downloaded > 0 and 'start_time' in progress:
            start = datetime.fromisoformat(progress['start_time'])
            elapsed = (datetime.now() - start).total_seconds()
            rate = downloaded / elapsed if elapsed > 0 else 0
            remaining = (target - downloaded) / rate if rate > 0 else 0
            
            print(f"\nEstimates:")
            print(f"  Download rate: {rate:.2f} cases/second")
            print(f"  Remaining: {target - downloaded:,} cases")
            if remaining > 0:
                hours = remaining / 3600
                days = hours / 24
                print(f"  Estimated time remaining: {days:.1f} days ({hours:.1f} hours)")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    monitor_status()

