import asyncio
import sys
sys.path.insert(0, '.')
from server.services.rag_service import rag_service

async def test_statute_relationships():
    print("=== TESTING STATUTE RELATIONSHIPS SYSTEM ===")

    # Test 1: Check if relationships registry is loaded
    print("\n1. STATUTE RELATIONSHIPS REGISTRY:")
    print(f"   Registry contains {len(rag_service.STATUTE_RELATIONSHIPS)} primary statutes")

    # Test 2: Check domestic violence relationships
    print("\n2. DOMESTIC VIOLENCE RELATIONSHIPS:")
    dv_relationships = rag_service._get_related_statutes("18.2-57.2")
    if dv_relationships:
        print(f"   Title: {dv_relationships.get('title', 'N/A')}")
        print(f"   Categories: {', '.join([k for k in dv_relationships.keys() if k != 'title'])}")

        print("\n   CRIMINAL PROCEDURE:")
        for citation, desc in dv_relationships.get('criminal_procedure', {}).items():
            print(f"     § {citation}: {desc}")

        print("\n   COLLATERAL CONSEQUENCES:")
        for citation, desc in dv_relationships.get('collateral_consequences', {}).items():
            print(f"     § {citation}: {desc}")
    else:
        print("   No relationships found for 18.2-57.2")

    # Test 3: Test search with relationships
    print("\n3. SEARCH WITH RELATIONSHIPS:")
    query = "What happens after a domestic violence conviction?"
    print(f"Query: {query}")

    result = await rag_service.search_with_case_context(query, n_results=3)
    related_statutes = result.get('related_statutes', {})

    print(f"Found related statutes for: {list(related_statutes.keys())}")

    for primary_citation, statute_info in related_statutes.items():
        print(f"\nPRIMARY: § {primary_citation} - {statute_info.get('title', 'Unknown')}")
        total_related = sum(len(statutes) for category, statutes in statute_info.items() if category != 'title' and isinstance(statutes, dict))
        print(f"Total related statutes: {total_related}")

    print("\n=== TEST COMPLETE ===")

asyncio.run(test_statute_relationships())















