"""Check if Heller and Bruen cases are in the database."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.scotus_service import scotus_service
from server.services.rag_service import rag_service
import asyncio

async def check():
    print("=" * 80)
    print("CHECKING FOR HELLER AND BRUEN CASES")
    print("=" * 80)
    print()
    
    rag_service._ensure_initialized()
    
    # Get all SCOTUS documents
    all_docs = rag_service.collection.get(
        where={"source": "SCOTUS Opinions"},
        limit=10000
    )
    
    ids = all_docs.get('ids', [])
    metas = all_docs.get('metadatas', [])
    docs = all_docs.get('documents', [])
    
    print(f"Total SCOTUS documents in database: {len(ids)}")
    print()
    
    # Search for Heller
    print("Searching for District of Columbia v. Heller (554 U.S. 570)...")
    heller_found = []
    for i, meta in enumerate(metas):
        text = docs[i].upper() if i < len(docs) else ""
        meta_str = str(meta).upper()
        combined = f"{text} {meta_str}"
        
        if any(term in combined for term in ['HELLER', '554 U.S. 570', '554 U. S. 570', 'DISTRICT OF COLUMBIA']):
            heller_found.append((i, meta, text[:200]))
    
    print(f"  Found {len(heller_found)} potential Heller matches")
    for idx, meta, preview in heller_found[:5]:
        print(f"    - Case: {meta.get('case_name', 'N/A')}")
        print(f"      Citation: {meta.get('citation', 'N/A')}")
        print(f"      Source: {meta.get('source', 'N/A')}")
        print(f"      Preview: {preview}...")
        print()
    
    # Search for Bruen
    print("Searching for NYSRPA v. Bruen (597 U.S. 1 / 142 S. Ct. 2111)...")
    bruen_found = []
    for i, meta in enumerate(metas):
        text = docs[i].upper() if i < len(docs) else ""
        meta_str = str(meta).upper()
        combined = f"{text} {meta_str}"
        
        if any(term in combined for term in ['BRUEN', '597 U.S. 1', '142 S. CT. 2111', 'NEW YORK STATE RIFLE', 'NYSRPA']):
            bruen_found.append((i, meta, text[:200]))
    
    print(f"  Found {len(bruen_found)} potential Bruen matches")
    for idx, meta, preview in bruen_found[:5]:
        print(f"    - Case: {meta.get('case_name', 'N/A')}")
        print(f"      Citation: {meta.get('citation', 'N/A')}")
        print(f"      Source: {meta.get('source', 'N/A')}")
        print(f"      Preview: {preview}...")
        print()
    
    # Test semantic search
    print("=" * 80)
    print("TESTING SEMANTIC SEARCH")
    print("=" * 80)
    print()
    
    test_queries = [
        "District of Columbia v. Heller",
        "Heller case Second Amendment",
        "NYSRPA v. Bruen",
        "Bruen case concealed carry"
    ]
    
    for query in test_queries:
        print(f"Query: '{query}'")
        results = await scotus_service.search_scotus(query, n_results=3)
        print(f"  Results: {len(results)}")
        for i, r in enumerate(results, 1):
            meta = r['metadata']
            case_name = meta.get('case_name', 'Unknown')
            citation = meta.get('citation', 'N/A')
            print(f"    {i}. {case_name} ({citation})")
        print()

if __name__ == "__main__":
    asyncio.run(check())







