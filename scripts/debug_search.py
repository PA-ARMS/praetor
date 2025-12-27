"""Debug search issue"""
import asyncio
import sys
from pathlib import Path

OUTPUT = Path("C:/LAWFIRMAI/data/debug_search.txt")

def log(msg):
    with open(OUTPUT, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")
    print(msg)

OUTPUT.write_text("")
log("Debug search starting...")

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    log("Step 1: Import services")
    from server.services.rag_service import rag_service
    from server.services.ollama_service import ollama_service
    
    log("Step 2: Initialize RAG")
    rag_service._ensure_initialized()
    log(f"Collection: {rag_service.collection.name}")
    log(f"Count: {rag_service.collection.count()}")
    
    async def debug():
        log("Step 3: Generate embedding")
        query = "domestic assault"
        emb = await ollama_service.embed(query)
        log(f"Embedding generated, dim: {len(emb)}")
        
        log("Step 4: Direct ChromaDB query")
        results = rag_service.collection.query(
            query_embeddings=[emb],
            n_results=3
        )
        log(f"Query returned: {len(results.get('ids', [[]])[0])} results")
        
        ids = results.get('ids', [[]])[0]
        metas = results.get('metadatas', [[]])[0]
        
        for i, (id, meta) in enumerate(zip(ids, metas)):
            log(f"  {i+1}. {meta.get('citation', 'N/A')} - {meta.get('source', 'N/A')}")
        
        log("Step 5: Done!")
    
    asyncio.run(debug())
    
except Exception as e:
    log(f"ERROR: {e}")
    import traceback
    log(traceback.format_exc())

log("Debug complete.")

















