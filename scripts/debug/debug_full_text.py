"""Debug full text search for outcomes"""
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

case_file = Path("data/scenarios/courtlistener/case_11164306.json")

with open(case_file, 'r', encoding='utf-8', errors='ignore') as f:
    case_data = json.load(f)

facts = case_data.get("plain_text", "") or case_data.get("html_with_citations", "") or case_data.get("html", "")
text_lower = facts.lower()

print(f"Full text length: {len(text_lower)}")
print(f"\nLast 2000 chars (where outcomes often are):")
print(text_lower[-2000:])
print("\n" + "="*60)

# Search for outcome keywords in full text
outcome_keywords = {
    "granted": [],
    "denied": [],
    "affirmed": [],
    "reversed": [],
    "remanded": [],
    "dismissed": [],
    "settled": [],
    "judgment": [],
    "motion": []
}

for keyword in outcome_keywords.keys():
    matches = list(re.finditer(rf"\b{keyword}\b", text_lower, re.IGNORECASE))
    outcome_keywords[keyword] = matches
    if matches:
        print(f"\n'{keyword}' found {len(matches)} times:")
        for m in matches[:5]:
            context = text_lower[max(0, m.start()-50):m.end()+50]
            print(f"  Position {m.start()}: ...{context}...")

# Check for common outcome phrases
phrases = [
    "motion granted",
    "motion denied", 
    "it is ordered",
    "the court",
    "we hold",
    "we find",
    "therefore",
    "accordingly"
]

print("\n" + "="*60)
print("OUTCOME PHRASES:")
for phrase in phrases:
    if phrase in text_lower:
        idx = text_lower.find(phrase)
        context = text_lower[max(0, idx-100):idx+200]
        print(f"\n'{phrase}' found at position {idx}:")
        print(f"  ...{context}...")

