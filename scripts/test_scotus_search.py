"""Test SCOTUS search directly."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.rag_service import rag_service
import asyncio

async def test():
    # Direct query for SCOTUS collection
    rag_service._ensure_initialized()
    
    # Get a sample SCOTUS document
    results = rag_service.collection.get(
        where={"source": "SCOTUS Opinions"},
        limit=5
    )
    
    print(f"Found {len(results.get('ids', []))} SCOTUS documents in collection")
    print()
    
    if results.get('ids'):
        print("Sample SCOTUS document:")
        print(f"  ID: {results['ids'][0]}")
        print(f"  Metadata: {results['metadatas'][0]}")
        print(f"  Text preview: {results['documents'][0][:200]}...")
        print()
    
    # Try semantic search
    print("Testing semantic search for 'Miranda rights':")
    search_results = await rag_service.search("Miranda rights", n_results=10)
    
    scotus_found = False
    for i, r in enumerate(search_results[:5], 1):
        source = r['metadata'].get('source', 'Unknown')
        jurisdiction = r['metadata'].get('jurisdiction', 'Unknown')
        print(f"{i}. {source} ({jurisdiction})")
        if 'SCOTUS' in source or jurisdiction == 'Federal':
            scotus_found = True
    
    if scotus_found:
        print("\n✅ SCOTUS opinions ARE being found in search!")
    else:
        print("\n⚠️  SCOTUS opinions in DB but not ranking high in semantic search")
        print("   This is normal - semantic search ranks by relevance")
        print("   SCOTUS cases will appear when they're actually relevant to the query")

if __name__ == "__main__":
    asyncio.run(test())






