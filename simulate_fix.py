import asyncio
from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service
from server.services.guardrails_service import guardrails_service
import json

async def simulate_perfect_response():
    print("🔍 SIMULATING SEARCH & RESPONSE GENERATION...")
    query = "What is the Virginia code section for domestic violence? Please also give me the elements of domestic violence and what the Commonwealth attorney must prove in order to find a defendant guilty of domestic violence."
    
    # 1. Test Search Expansion
    print("\n--- STEP 1: SEARCH EXPANSION ---")
    expanded = await rag_service.expand_query_concepts(query)
    print(f"Expanded Queries ({len(expanded)}):")
    for q in expanded[:5]: # Show top 5
        print(f"  - {q}")
    
    # 2. Test Search Retrieval
    print("\n--- STEP 2: DOCUMENT RETRIEVAL ---")
    search_results = await rag_service.search_comprehensive(query, n_results_per_query=10)
    sources = search_results['results']
    
    print(f"Found {len(sources)} sources.")
    print("Top 3 Sources:")
    top_citations = []
    for i, s in enumerate(sources[:3]):
        citation = s['metadata'].get('citation', 'No citation')
        top_citations.append(citation)
        print(f"  [{i+1}] {citation}: {s['metadata'].get('catchline', 'No catchline')}")
    
    # Check if target statute is in top 3
    if "§ 18.2-57.2" in top_citations:
        print("✅ SUCCESS: § 18.2-57.2 found in top results.")
    else:
        print("❌ FAILURE: § 18.2-57.2 NOT in top 3 results.")
        # Force it for generation simulation
        pass

    # 3. Generate Response
    print("\n--- STEP 3: GENERATING RESPONSE (Qwen 14B) ---")
    context = await rag_service.get_context(query, n_results=5)
    
    system_prompt = guardrails_service.build_system_prompt()
    system_prompt += "\n\nSYSTEMATIC REQUIREMENT - COLLATERAL CONSEQUENCES:\nFor EVERY question involving a criminal offense..."
    
    response = await ollama_service.generate(
        prompt=query,
        context=context,
        system_prompt=system_prompt,
        max_tokens=1000
    )
    
    print("\n--- RAW AI RESPONSE ---")
    print(response[:500] + "...\n[truncated]")
    
    # 4. Validation & Correction
    print("\n--- STEP 4: VALIDATION & CORRECTION ---")
    final_response = await guardrails_service.validate_and_correct(response, query, sources)
    
    print("\n--- FINAL OUTPUT ANALYSIS ---")
    has_statute = "18.2-57.2" in final_response
    has_elements = "prove" in final_response.lower()
    has_collateral = "Collateral Consequences" in final_response or "Firearm Rights" in final_response
    
    print(f"Correct Statute Cited: {'✅' if has_statute else '❌'}")
    print(f"Elements Listed: {'✅' if has_elements else '❌'}")
    print(f"Collateral Consequences: {'✅' if has_collateral else '❌'}")
    
    if has_statute and has_elements and has_collateral:
        print("\n🏆 PERFECT ANSWER ACHIEVED")
    else:
        print("\n⚠️ STILL NEEDS WORK")

if __name__ == "__main__":
    asyncio.run(simulate_perfect_response())














