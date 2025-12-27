"""Test if SCOTUS cases are being found and cited properly."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.rag_service import rag_service
import asyncio

async def test():
    print("=" * 80)
    print("TESTING SCOTUS CITATION SYSTEM")
    print("=" * 80)
    print()
    
    # Test 1: Check if SCOTUS opinions are in the database
    print("TEST 1: Checking if SCOTUS opinions are in RAG system...")
    rag_service._ensure_initialized()
    
    scotus_results = rag_service.collection.get(
        where={"source": "SCOTUS Opinions"},
        limit=5
    )
    
    scotus_count = len(scotus_results.get('ids', []))
    print(f"  ✅ Found {scotus_count} SCOTUS opinions in database")
    
    if scotus_count > 0:
        print(f"  Sample: {scotus_results['metadatas'][0].get('case_name', 'N/A')}")
        print(f"  Citation: {scotus_results['metadatas'][0].get('citation', 'N/A')}")
    print()
    
    # Test 2: Search for a well-known SCOTUS case
    print("TEST 2: Searching for 'Miranda v Arizona' (famous SCOTUS case)...")
    search_results = await rag_service.search("Miranda v Arizona", n_results=10)
    
    scotus_found = False
    scotus_in_top_5 = False
    
    print(f"  Found {len(search_results)} total results")
    print()
    
    for i, r in enumerate(search_results[:10], 1):
        source = r['metadata'].get('source', 'Unknown')
        jurisdiction = r['metadata'].get('jurisdiction', 'Unknown')
        citation = r['metadata'].get('citation', '')
        case_name = r['metadata'].get('case_name', '')
        
        is_scotus = 'SCOTUS' in source.upper() or jurisdiction == 'Federal'
        
        marker = "⭐ SCOTUS" if is_scotus else "  "
        print(f"{marker} {i}. {source} ({jurisdiction})")
        if citation:
            print(f"      Citation: {citation}")
        if case_name:
            print(f"      Case: {case_name[:60]}")
        
        if is_scotus:
            scotus_found = True
            if i <= 5:
                scotus_in_top_5 = True
        print()
    
    # Test 3: Search for constitutional issue (should find SCOTUS)
    print("TEST 3: Searching for 'Fourth Amendment search and seizure'...")
    search_results2 = await rag_service.search("Fourth Amendment search and seizure", n_results=10)
    
    scotus_found2 = False
    for r in search_results2[:5]:
        if 'SCOTUS' in r['metadata'].get('source', '').upper() or r['metadata'].get('jurisdiction') == 'Federal':
            scotus_found2 = True
            break
    
    print()
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()
    
    if scotus_count > 0:
        print("✅ SCOTUS opinions ARE in the RAG database")
    else:
        print("❌ SCOTUS opinions NOT in database - need to run ingestion")
    
    if scotus_found:
        print("✅ SCOTUS cases ARE being found in search results")
        if scotus_in_top_5:
            print("✅ SCOTUS cases ARE in top 5 results (properly prioritized)")
        else:
            print("⚠️  SCOTUS cases found but not in top 5 (may need more boost)")
    else:
        print("❌ SCOTUS cases NOT appearing in search results")
        print("   This could mean:")
        print("   - Semantic similarity is low")
        print("   - Need to test with more specific SCOTUS queries")
    
    if scotus_found2:
        print("✅ SCOTUS cases found for constitutional issues")
    else:
        print("⚠️  SCOTUS cases not found for constitutional search")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test())






