"""
LIVE SEARCH ACCURACY TEST
=========================
Tests that the RAG system returns accurate, relevant results
for common defense attorney queries.
"""
import asyncio
import sys
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service


async def test_search_accuracy():
    print("=" * 70)
    print("LIVE SEARCH ACCURACY TEST")
    print("Testing that searches return the correct statutes")
    print("=" * 70)
    
    # Test cases: (query, expected_section, description)
    tests = [
        ("What is the penalty for domestic assault in Virginia?", "18.2-57.2", "Domestic assault"),
        ("DUI penalties Virginia first offense", "18.2-266", "DUI"),
        ("grand larceny threshold amount Virginia", "18.2-95", "Grand larceny"),
        ("speedy trial rights Virginia criminal", "19.2-243", "Speedy trial"),
        ("right to counsel Virginia criminal case", "19.2-163", "Right to counsel"),
        ("assault and battery Virginia penalty", "18.2-57", "Simple assault"),
        ("possession of marijuana Virginia", "18.2-250.1", "Marijuana possession"),
        ("carrying concealed weapon Virginia", "18.2-308", "Concealed carry"),
        ("burglary Virginia penalty", "18.2-89", "Burglary"),
        ("first degree murder Virginia", "18.2-32", "Murder"),
    ]
    
    passed = 0
    failed = 0
    
    for query, expected_section, description in tests:
        print(f"\n{'-' * 70}")
        print(f"Test: {description}")
        print(f"Query: {query}")
        print(f"Expected: § {expected_section}")
        
        try:
            results = await rag_service.search(query, n_results=5)
            
            found = False
            found_position = None
            
            for i, r in enumerate(results):
                citation = r.get('metadata', {}).get('citation', '')
                section = r.get('metadata', {}).get('section', '')
                combined = f"{citation} {section}"
                
                if expected_section in combined:
                    found = True
                    found_position = i + 1
                    break
            
            if found:
                print(f"Result: ✓ FOUND at position #{found_position}")
                passed += 1
            else:
                print(f"Result: ✗ NOT FOUND in top 5")
                if results:
                    top_citation = results[0].get('metadata', {}).get('citation', 'N/A')
                    top_section = results[0].get('metadata', {}).get('section', 'N/A')
                    print(f"  Top result was: {top_citation or top_section}")
                failed += 1
                
        except Exception as e:
            print(f"Result: ✗ ERROR - {e}")
            failed += 1
    
    # Summary
    print(f"\n{'=' * 70}")
    print("SEARCH ACCURACY SUMMARY")
    print("=" * 70)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    accuracy = (passed / len(tests)) * 100
    print(f"Accuracy: {accuracy:.1f}%")
    
    if accuracy >= 90:
        print("\n✓ SEARCH ACCURACY: EXCELLENT")
    elif accuracy >= 70:
        print("\n⚠ SEARCH ACCURACY: NEEDS IMPROVEMENT")
    else:
        print("\n✗ SEARCH ACCURACY: CRITICAL ISSUES")
    
    print("=" * 70)
    
    return accuracy >= 80


if __name__ == "__main__":
    success = asyncio.run(test_search_accuracy())
    sys.exit(0 if success else 1)

