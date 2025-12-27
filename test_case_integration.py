import asyncio
import sys
sys.path.insert(0, '.')
from server.services.rag_service import rag_service

async def test_case_aware_search():
    query = 'What is the Virginia code section for domestic violence? Please also give me the elements of domestic violence and what the Commonwealth attorney must prove in order to find a defendant guilty of domestic violence.'

    print('=== TESTING ENHANCED CASE-AWARE SEARCH ===')
    print(f'Query: {query[:80]}...')
    print()

    # Test the new enhanced search
    result = await rag_service.search_with_case_context(query, n_results=3)

    print('=== STATUTE RESULTS ===')
    statutes = result.get('statute_results', [])
    for i, statute in enumerate(statutes[:3]):
        text = statute.get('text', '')[:200]
        has_57_2 = '18.2-57.2' in text
        marker = '*** TARGET STATUTE ***' if has_57_2 else ''
        print(f'{i+1}. {marker}')
        print(f'   {text}...')
        print()

    print('=== CASE LAW CONTEXT ===')
    cases = result.get('case_contexts', [])
    print(f'Found {len(cases)} relevant cases:')
    for i, case in enumerate(cases[:2]):
        print(f'{i+1}. {case.get("case_type", "Unknown")} case ({case.get("jurisdiction", "Unknown")})')
        print(f'   Outcome: {case.get("outcome", "Unknown")}')
        print(f'   Legal concepts: {case.get("legal_concepts", [])[:3]}')
        print(f'   Similarity: {case.get("similarity_score", 0):.2f}')
        print()

    print('=== LEGAL CONCEPTS EXTRACTED ===')
    concepts = result.get('legal_concepts', [])
    print(f'Total concepts: {len(concepts)}')
    domestic_concepts = [c for c in concepts if 'domestic' in c.lower() or 'assault' in c.lower() or 'family' in c.lower()]
    print(f'Domestic/family/assault concepts: {domestic_concepts[:5]}')

    print()
    print('=== QUERY ANALYSIS ===')
    analysis = result.get('query_analysis', {})
    print(f'Detected intents: {analysis.get("detected_intents", [])}')
    print(f'Case context available: {analysis.get("case_context_available", False)}')
    print(f'Statute-case connections: {analysis.get("statute_case_connections", 0)}')

asyncio.run(test_case_aware_search())
















