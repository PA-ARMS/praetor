"""
Download and process cases in 100-case chunks
"""
import subprocess
import sys
import os
from pathlib import Path

# Load API key from .env if available
env_file = Path("server/.env")
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            if line.startswith("COURTLISTENER_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["COURTLISTENER_API_KEY"] = api_key
                break

def download_chunk(chunk_num, cases_per_chunk=100):
    """Download a chunk of cases"""
    print(f"\n{'='*60}")
    print(f"DOWNLOADING CHUNK {chunk_num} ({cases_per_chunk} cases)")
    print(f"{'='*60}\n")
    
    result = subprocess.run(
        [sys.executable, "scripts/download_cases.py", str(cases_per_chunk)],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    
    return result.returncode == 0


def process_chunk():
    """Process downloaded cases"""
    print(f"\n{'='*60}")
    print(f"PROCESSING CASES")
    print(f"{'='*60}\n")
    
    # Set environment variable
    env = os.environ.copy()
    env["SCENARIO_DB_ENABLED"] = "True"
    
    result = subprocess.run(
        [sys.executable, "scripts/process_scenarios_batch.py", "--max-cases", "200"],
        capture_output=True,
        text=True,
        env=env
    )
    
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    
    return result.returncode == 0


def get_stats():
    """Get current statistics"""
    try:
        env = os.environ.copy()
        env["SCENARIO_DB_ENABLED"] = "True"
        
        result = subprocess.run(
            [sys.executable, "scripts/monitor_download.py"],
            capture_output=True,
            text=True,
            env=env
        )
        print(result.stdout)
    except Exception as e:
        print(f"Error getting stats: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download and process cases in chunks")
    parser.add_argument("--chunks", type=int, default=1, help="Number of 100-case chunks to download")
    parser.add_argument("--cases-per-chunk", type=int, default=100, help="Cases per chunk")
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"CHUNKED DOWNLOAD AND PROCESS")
    print(f"{'='*60}")
    print(f"Chunks to download: {args.chunks}")
    print(f"Cases per chunk: {args.cases_per_chunk}")
    print(f"Total cases: {args.chunks * args.cases_per_chunk}")
    print(f"{'='*60}\n")
    
    for chunk_num in range(1, args.chunks + 1):
        print(f"\n\n{'#'*60}")
        print(f"CHUNK {chunk_num} of {args.chunks}")
        print(f"{'#'*60}\n")
        
        # Download chunk
        if not download_chunk(chunk_num, args.cases_per_chunk):
            print(f"ERROR: Download of chunk {chunk_num} failed!")
            continue
        
        # Process chunk
        if not process_chunk():
            print(f"WARNING: Processing of chunk {chunk_num} had issues")
        
        # Show stats
        print(f"\n{'='*60}")
        print(f"CHUNK {chunk_num} COMPLETE - STATISTICS")
        print(f"{'='*60}")
        get_stats()
        
        if chunk_num < args.chunks:
            print(f"\nWaiting 5 seconds before next chunk...")
            import time
            time.sleep(5)
    
    print(f"\n\n{'='*60}")
    print(f"ALL CHUNKS COMPLETE!")
    print(f"{'='*60}")
    get_stats()

