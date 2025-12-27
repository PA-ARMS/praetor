"""Quick script to check unprocessed cases"""
import json
from pathlib import Path

CASE_DIR = Path("data/scenarios/courtlistener")
PROCESSED_FILE = Path("data/scenarios/courtlistener/.processed_cases.json")

# Get all case files
case_files = list(CASE_DIR.glob("case_*.json"))
print(f"Total case files: {len(case_files)}")

# Get processed IDs
processed_ids = set()
if PROCESSED_FILE.exists():
    with open(PROCESSED_FILE, 'r') as f:
        data = json.load(f)
        processed_ids = set(data.get("processed_ids", []))
    print(f"Processed IDs: {len(processed_ids)}")

# Find unprocessed
unprocessed = [f for f in case_files if f.stem.replace("case_", "") not in processed_ids]
print(f"Unprocessed cases: {len(unprocessed)}")

if len(unprocessed) > 0:
    print(f"\nFirst 10 unprocessed case IDs:")
    for f in unprocessed[:10]:
        print(f"  - {f.stem.replace('case_', '')}")

