"""Simple search test with explicit output"""
import asyncio
import sys
from pathlib import Path

# Output file
OUTPUT = Path("C:/LAWFIRMAI/data/search_test_output.txt")

def log(msg):
    with open(OUTPUT, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")
    print(msg)

# Clear output
OUTPUT.write_text("")

log("Starting search test...")

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from server.services.rag_service import rag_service
    from server.services.ollama_service import ollama_service
    log("Services imported")
    
    async def test_search():
        log("Testing embedding first...")
        emb = await ollama_service.embed("test")
        log(f"Embedding works, dimension: {len(emb)}")
        
        log("\nRunning search: 'domestic assault Virginia'")
        results = await rag_service.search("domestic assault Virginia", n_results=5)
        log(f"Got {len(results)} results")
        
        for i, r in enumerate(results):
            meta = r.get('metadata', {})
            citation = meta.get('citation', '')
            section = meta.get('section', '')
            source = meta.get('source', '')
            log(f"  {i+1}. {citation or section} ({source})")
        
        # Test specific statute search
        log("\nSearching for '18.2-57.2'...")
        results2 = await rag_service.search("Virginia Code 18.2-57.2", n_results=3)
        log(f"Got {len(results2)} results")
        
        for i, r in enumerate(results2):
            meta = r.get('metadata', {})
            citation = meta.get('citation', '')
            log(f"  {i+1}. {citation}")
        
        log("\nSearch test complete!")
    
    asyncio.run(test_search())
    
except Exception as e:
    log(f"ERROR: {e}")
    import traceback
    log(traceback.format_exc())

log("Done.")


















