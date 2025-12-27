"""Check if SCOTUS opinions are in the RAG system."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.rag_service import rag_service
import asyncio

async def check():
    # Search for a well-known SCOTUS case
    query = "Miranda v Arizona"
    results = await rag_service.search(query, n_results=10)
    
    print(f"Searching for: {query}")
    print(f"Found {len(results)} results\n")
    
    scotus_found = False
    for i, r in enumerate(results, 1):
        source = r['metadata'].get('source', 'Unknown')
        jurisdiction = r['metadata'].get('jurisdiction', 'Unknown')
        citation = r['metadata'].get('citation', '')
        
        print(f"{i}. Source: {source}")
        print(f"   Jurisdiction: {jurisdiction}")
        print(f"   Citation: {citation}")
        print(f"   Text preview: {r['text'][:100]}...")
        print()
        
        if 'SCOTUS' in source or jurisdiction == 'Federal':
            scotus_found = True
    
    if not scotus_found:
        print("❌ NO SCOTUS OPINIONS FOUND IN RESULTS!")
        print("\nPossible reasons:")
        print("1. SCOTUS opinions not yet ingested into RAG system")
        print("2. Search is filtering by jurisdiction")
        print("3. SCOTUS opinions not properly indexed")
    else:
        print("✅ SCOTUS opinions found in RAG system")

if __name__ == "__main__":
    asyncio.run(check())






