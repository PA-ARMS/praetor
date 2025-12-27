import asyncio
import sys
sys.path.insert(0, '.')
from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service

async def test_praetor_format():
    print("=== Testing Praetor C.R.A.C. Format ===")
    query = "What is the law on domestic violence in Virginia?"
    
    # 1. Simulate RAG retrieval to get context
    print("Retrieving context...")
    context = await rag_service.get_context(query, n_results=3)
    
    # 2. Generate response using the new system prompt
    print("Generating response...")
    response = await ollama_service.generate(
        prompt=query,
        context=context,
        max_tokens=1000
    )
    
    print("\n=== AI OUTPUT START ===\n")
    print(response)
    print("\n=== AI OUTPUT END ===\n")
    
    # 3. Verify C.R.A.C. structure
    if "**Rule:**" in response and "18.2-57.2" in response:
        print("✅ SUCCESS: Found C.R.A.C. format and citation 18.2-57.2")
    else:
        print("❌ FAILURE: Missing format or citation")

if __name__ == "__main__":
    asyncio.run(test_praetor_format())















