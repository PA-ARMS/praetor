"""Fetch Heller and Bruen cases specifically if missing."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import requests
from pathlib import Path
import asyncio
from server.services.rag_service import rag_service
from server.services.scotus_service import scotus_service

# Known citations
HELLER_CITATION = "554 U.S. 570"
BRUEN_CITATION_1 = "597 U.S. 1"
BRUEN_CITATION_2 = "142 S. Ct. 2111"

async def check_and_fetch():
    print("=" * 80)
    print("CHECKING AND FETCHING HELLER AND BRUEN")
    print("=" * 80)
    print()
    
    rag_service._ensure_initialized()
    
    # Check for Heller
    print("Checking for Heller (554 U.S. 570)...")
    heller = await scotus_service.search_scotus_by_citation(HELLER_CITATION)
    if heller:
        print(f"  ✓ Heller found: {heller['metadata'].get('case_name', 'N/A')}")
    else:
        print(f"  ✗ Heller NOT found - needs to be fetched")
        print(f"    URL: https://www.supremecourt.gov/opinions/boundvolumes/554bv.pdf")
        print(f"    Or: https://www.supremecourt.gov/opinions/07pdf/07-290.pdf")
    
    print()
    
    # Check for Bruen
    print("Checking for Bruen (597 U.S. 1 / 142 S. Ct. 2111)...")
    bruen1 = await scotus_service.search_scotus_by_citation(BRUEN_CITATION_1)
    bruen2 = await scotus_service.search_scotus_by_citation(BRUEN_CITATION_2)
    
    if bruen1 or bruen2:
        bruen = bruen1 or bruen2
        print(f"  ✓ Bruen found: {bruen['metadata'].get('case_name', 'N/A')}")
    else:
        print(f"  ✗ Bruen NOT found - needs to be fetched")
        print(f"    URL: https://www.supremecourt.gov/opinions/21pdf/20-843_7j80.pdf")
    
    print()
    
    # Also check by case name
    print("Checking by case name...")
    heller_by_name = await scotus_service.search_scotus_by_case_name("Heller")
    bruen_by_name = await scotus_service.search_scotus_by_case_name("Bruen")
    
    print(f"  Heller matches by name: {len(heller_by_name)}")
    for h in heller_by_name[:2]:
        print(f"    - {h['metadata'].get('case_name', 'N/A')} ({h['metadata'].get('citation', 'N/A')})")
    
    print(f"  Bruen matches by name: {len(bruen_by_name)}")
    for b in bruen_by_name[:2]:
        print(f"    - {b['metadata'].get('case_name', 'N/A')} ({b['metadata'].get('citation', 'N/A')})")
    
    print()
    print("=" * 80)
    print("RECOMMENDATION:")
    print("=" * 80)
    if not heller or not (bruen1 or bruen2):
        print("These landmark cases should be in the database.")
        print("Run: python scripts/fetch_scotus_opinions.py")
        print("Then: python scripts/ingest_scotus_opinions.py")
    else:
        print("✓ Both Heller and Bruen are in the database!")

if __name__ == "__main__":
    asyncio.run(check_and_fetch())







