import sys
sys.path.insert(0, '.')
from server.services.rag_service import rag_service

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

# Test 3: Test statute detection in text
print("\n3. STATUTE DETECTION IN TEXT:")
test_text = "§ 18.2-57.2. Assault and battery against a family or household member; penalty"
found_statutes = rag_service._find_statute_relationships_in_results([{"text": test_text}])
print(f"   Text: {test_text}")
print(f"   Detected primary statutes: {found_statutes}")

print("\n=== TEST COMPLETE ===")















