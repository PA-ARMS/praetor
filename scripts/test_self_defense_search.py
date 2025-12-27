"""Test SCOTUS search for self-defense/firearm cases."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.scotus_service import scotus_service
from server.services.rag_service import rag_service
import asyncio

async def test():
    print("=" * 80)
    print("TESTING SCOTUS SEARCH FOR SELF-DEFENSE/FIREARM CASES")
    print("=" * 80)
    print()
    
    queries = [
        "self defense using a firearm",
        "self-defense firearm",
        "stand your ground firearm",
        "Second Amendment self defense",
        "right to bear arms self defense"
    ]
    
    for query in queries:
        print(f"Query: '{query}'")
        print("-" * 80)
        
        # Search SCOTUS
        scotus_results = await scotus_service.search_scotus(query, n_results=5)
        print(f"  SCOTUS results: {len(scotus_results)}")
        
        for i, r in enumerate(scotus_results[:3], 1):
            meta = r['metadata']
            print(f"    {i}. {meta.get('case_name', 'Unknown')}")
            print(f"       Citation: {meta.get('citation', 'N/A')}")
            print(f"       Date: {meta.get('date', 'N/A')}")
            print(f"       Text preview: {r['text'][:100]}...")
            print()
        
        # Also search general RAG
        general_results = await rag_service.search(query, n_results=5, use_synonyms=False)
        scotus_in_general = [r for r in general_results if 'SCOTUS' in r['metadata'].get('source', '').upper() or r['metadata'].get('jurisdiction') == 'Federal']
        print(f"  General search SCOTUS results: {len(scotus_in_general)}")
        print()
    
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test())






