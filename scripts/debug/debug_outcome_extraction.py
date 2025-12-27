"""Debug outcome extraction"""
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.outcome_extraction_service import outcome_extraction_service

case_file = Path("data/scenarios/courtlistener/case_11164306.json")

with open(case_file, 'r', encoding='utf-8', errors='ignore') as f:
    case_data = json.load(f)

facts = case_data.get("plain_text", "") or case_data.get("html_with_citations", "") or case_data.get("html", "")

print("Testing outcome extraction...")
print(f"Text length: {len(facts)}")

# Test the patterns manually
text_lower = facts.lower()[:3000]
print(f"\nFirst 3000 chars (lowercase):")
print(text_lower[:500])
print("...")

# Test specific patterns
test_patterns = [
    (r"motion.*granted", "Defendant Win"),
    (r"motion.*denied", "Plaintiff Win"),
    (r"affirmed", "Affirmed"),
    (r"denied", "Denied"),
]

print("\nPattern matching results:")
for pattern, expected in test_patterns:
    matches = list(re.finditer(pattern, text_lower, re.IGNORECASE | re.MULTILINE))
    if matches:
        print(f"  {pattern}: FOUND {len(matches)} times")
        for m in matches[:3]:
            print(f"    - Position {m.start()}: '{m.group()}'")
    else:
        print(f"  {pattern}: NOT FOUND")

# Try extraction
outcome = outcome_extraction_service.extract_outcome(facts, case_data)
print(f"\nExtracted outcome: {outcome}")

