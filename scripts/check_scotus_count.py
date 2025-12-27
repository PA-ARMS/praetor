"""Quick check of how many SCOTUS opinions are in RAG system."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.rag_service import rag_service
import asyncio

async def check():
    # Check collection directly
    try:
        rag_service._ensure_initialized()
        
        # Get all documents with Federal jurisdiction
        results = rag_service.collection.get(
            where={"jurisdiction": "Federal"},
            limit=1000
        )
        
        federal_count = len(results.get('ids', []))
        
        # Get SCOTUS specifically
        scotus_results = rag_service.collection.get(
            where={"source": "SCOTUS Opinions"},
            limit=1000
        )
        
        scotus_count = len(scotus_results.get('ids', []))
        
        print(f"Federal jurisdiction documents: {federal_count}")
        print(f"SCOTUS Opinions: {scotus_count}")
        
        if scotus_count > 0:
            print(f"\n✅ SCOTUS opinions are being ingested!")
            print(f"   {scotus_count} opinions indexed so far")
            print(f"   Background process is still running...")
        else:
            print(f"\n⏳ SCOTUS opinions not yet indexed")
            print(f"   Background ingestion is still running...")
            print(f"   This will take ~20 minutes for all 467 opinions")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check())

