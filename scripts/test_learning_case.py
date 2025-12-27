"""Test why learning is returning None"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.continuous_learning_loop import (
    extract_facts_without_outcome, 
    extract_actual_outcome,
    normalize_case_name,
    load_learned_cases,
    load_learned_case_names
)

# Test a case that was in the log
test_file = Path("data/scenarios/courtlistener/case_11164885.json")

if not test_file.exists():
    print(f"Test file not found: {test_file}")
    sys.exit(1)

print(f"Testing case: {test_file.name}")
print("=" * 60)

# Load case
with open(test_file, "r", encoding="utf-8") as f:
    case_data = json.load(f)

case_id = str(case_data.get("id", test_file.stem))
case_name = case_data.get("case_name") or case_data.get("name", "")
normalized_name = normalize_case_name(case_name)

print(f"Case ID: {case_id}")
print(f"Case name: {case_name[:60]}...")
print()

# Check if already learned
learned_ids = load_learned_cases()
learned_names = load_learned_case_names()

print("Duplicate check:")
print(f"  Already learned by ID: {case_id in learned_ids}")
print(f"  Already learned by name: {normalized_name in learned_names if normalized_name else False}")
print()

# Extract facts
print("Facts extraction:")
facts = extract_facts_without_outcome(case_data)
if facts:
    print(f"  ✓ Facts extracted: {len(facts)} chars")
    print(f"  Meets minimum (100 chars): {len(facts.strip()) >= 100}")
else:
    print("  ✗ No facts extracted")
print()

# Extract outcome
print("Outcome extraction:")
outcome = extract_actual_outcome(case_data)
print(f"  Outcome: {outcome}")
print(f"  Is Unknown: {outcome == 'Unknown'}")
print()

# Final verdict
print("=" * 60)
can_process = (
    case_id not in learned_ids and
    (not normalized_name or normalized_name not in learned_names) and
    facts and len(facts.strip()) >= 100 and
    outcome != "Unknown"
)

if can_process:
    print("[OK] Case CAN be processed")
else:
    print("[FAIL] Case CANNOT be processed")
    print("\nReasons:")
    if case_id in learned_ids:
        print("  - Already learned by ID")
    if normalized_name and normalized_name in learned_names:
        print("  - Already learned by name")
    if not facts or len(facts.strip()) < 100:
        print("  - Facts too short or missing")
    if outcome == "Unknown":
        print("  - Outcome is Unknown")

