"""Test if SCOTUS service is working properly."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.scotus_service import scotus_service
from server.services.rag_service import rag_service
import asyncio

async def test():
    print("=" * 80)
    print("TESTING SCOTUS SERVICE - SEPARATE DATABASE QUERY")
    print("=" * 80)
    print()
    
    # Test 1: Check SCOTUS database directly
    print("TEST 1: Checking SCOTUS database...")
    rag_service._ensure_initialized()
    
    scotus_docs = rag_service.collection.get(
        where={"source": "SCOTUS Opinions"},
        limit=3
    )
    
    scotus_count = len(scotus_docs.get('ids', []))
    print(f"  ✅ Found {scotus_count} SCOTUS opinions in database")
    
    if scotus_count > 0:
        sample = scotus_docs['metadatas'][0]
        print(f"  Sample: {sample.get('source', 'N/A')}")
        print(f"  Citation: {sample.get('citation', 'N/A')}")
        print(f"  Case: {sample.get('case_name', 'N/A')[:60]}")
    print()
    
    # Test 2: Query SCOTUS service directly
    print("TEST 2: Querying SCOTUS service for 'Miranda rights'...")
    scotus_results = await scotus_service.search_scotus("Miranda rights", n_results=5)
    
    print(f"  Found {len(scotus_results)} SCOTUS cases")
    print()
    
    if scotus_results:
        print("  SCOTUS cases found:")
        for i, r in enumerate(scotus_results[:3], 1):
            meta = r['metadata']
            print(f"    {i}. {meta.get('case_name', 'Unknown')}")
            print(f"       Citation: {meta.get('citation', 'N/A')}")
            print(f"       Source: {meta.get('source', 'N/A')}")
            print()
    else:
        print("  ⚠️  No SCOTUS cases found for this query")
        print("     (This might be normal if query doesn't match SCOTUS content)")
    print()
    
    # Test 3: Query SCOTUS for constitutional issue
    print("TEST 3: Querying SCOTUS service for 'Fourth Amendment search'...")
    scotus_results2 = await scotus_service.search_scotus("Fourth Amendment search and seizure", n_results=5)
    
    print(f"  Found {len(scotus_results2)} SCOTUS cases")
    if scotus_results2:
        print("  ✅ SCOTUS service is finding cases!")
        for r in scotus_results2[:2]:
            print(f"    - {r['metadata'].get('case_name', 'Unknown')}")
    else:
        print("  ⚠️  No SCOTUS cases found")
    print()
    
    # Test 4: Test combined search (simulating chat route)
    print("TEST 4: Simulating combined search (SCOTUS + State)...")
    scotus_sources = await scotus_service.search_scotus("Miranda", n_results=3)
    state_sources = await rag_service.search("Miranda", n_results=5, use_synonyms=False)
    
    # Filter state sources to exclude SCOTUS (avoid duplicates)
    state_only = [s for s in state_sources if 'SCOTUS' not in s['metadata'].get('source', '').upper()]
    
    print(f"  SCOTUS results: {len(scotus_sources)}")
    print(f"  State results: {len(state_only)}")
    print()
    
    # Combine with SCOTUS first
    combined = scotus_sources + state_only[:5]
    
    print("  Combined results (SCOTUS first, then State):")
    for i, r in enumerate(combined[:5], 1):
        meta = r['metadata']
        source = meta.get('source', 'Unknown')
        is_scotus = 'SCOTUS' in source.upper() or meta.get('jurisdiction') == 'Federal'
        marker = "⭐ SCOTUS" if is_scotus else "  State"
        print(f"    {marker} {i}. {source}")
        if is_scotus:
            print(f"         Case: {meta.get('case_name', 'N/A')[:50]}")
    print()
    
    # Final summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    if scotus_count > 0:
        print("✅ SCOTUS database has opinions")
    else:
        print("❌ SCOTUS database is empty - need to run ingestion")
    
    if len(scotus_results) > 0 or len(scotus_results2) > 0:
        print("✅ SCOTUS service is finding cases")
        print("✅ SCOTUS cases will be cited when relevant")
    else:
        print("⚠️  SCOTUS service not finding cases for test queries")
        print("   This might be normal - SCOTUS cases need to be semantically relevant")
        print("   Try queries about constitutional issues, federal law, etc.")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test())






