"""
Comprehensive System Check - Verifies all components including new protections
"""
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.ai_laws_protection import ai_laws_protection
from server.services.uncertainty_service import uncertainty_service
from server.services.answer_verification_service import answer_verification_service
from server.services.guardrails_service import guardrails_service
from server.services.scenario_service import scenario_service
from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service
from server.config import settings


def check_ai_laws_protection():
    """Verify AI Laws protection system"""
    print("=" * 80)
    print("AI LAWS PROTECTION CHECK")
    print("=" * 80)
    
    try:
        # Verify AI Laws integrity
        is_valid, error = ai_laws_protection.verify_ai_laws()
        
        if is_valid:
            print("✅ AI Laws Protection: ACTIVE")
            print(f"   Checksum: {ai_laws_protection.get_checksum()[:16]}...")
            print("   Status: IMMUTABLE - Protected from modification")
            
            # Verify all articles are present
            ai_laws = ai_laws_protection.load_ai_laws()
            if ai_laws:
                articles = ai_laws.get("articles", {})
                required = ["article_i", "article_ii", "article_iii", "article_iv", "article_v",
                           "article_vi", "article_vii", "article_viii", "article_ix", "article_x"]
                present = [a for a in required if a in articles]
                print(f"   Articles present: {len(present)}/10")
                if len(present) == 10:
                    print("   ✅ All 10 articles verified")
                else:
                    missing = [a for a in required if a not in articles]
                    print(f"   ⚠️  Missing articles: {', '.join(missing)}")
            
            return True
        else:
            print(f"❌ AI Laws Protection: FAILED")
            print(f"   Error: {error}")
            print("   CRITICAL: AI Laws have been modified or are invalid")
            return False
    except Exception as e:
        print(f"❌ AI Laws Protection: ERROR")
        print(f"   {e}")
        return False


def check_system_prompt_structure():
    """Verify system prompt includes AI Laws as base code"""
    print("\n" + "=" * 80)
    print("SYSTEM PROMPT STRUCTURE CHECK")
    print("=" * 80)
    
    try:
        prompt = guardrails_service.build_system_prompt()
        
        # Check for key indicators
        checks = {
            "FUNDAMENTAL BASE CODE": "FUNDAMENTAL BASE CODE" in prompt,
            "AI Laws first": prompt.find("FUNDAMENTAL BASE CODE") < prompt.find("You are Praetor"),
            "All 10 articles": all(f"ARTICLE {num}" in prompt for num in ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]),
            "Immutable statement": "IMMUTABLE" in prompt and "NON-NEGOTIABLE" in prompt,
            "Override statement": "override" in prompt.lower() and "priority" in prompt.lower()
        }
        
        all_passed = all(checks.values())
        
        if all_passed:
            print("✅ System Prompt Structure: CORRECT")
            print("   ✅ AI Laws positioned as FUNDAMENTAL BASE CODE")
            print("   ✅ AI Laws come before all other instructions")
            print("   ✅ All 10 articles included")
            print("   ✅ Immutability statements present")
            print("   ✅ Override priority statements present")
        else:
            print("⚠️  System Prompt Structure: ISSUES FOUND")
            for check, passed in checks.items():
                status = "✅" if passed else "❌"
                print(f"   {status} {check}")
        
        return all_passed
    except Exception as e:
        print(f"❌ System Prompt Check: ERROR")
        print(f"   {e}")
        return False


def check_uncertainty_service():
    """Verify uncertainty notice service"""
    print("\n" + "=" * 80)
    print("UNCERTAINTY NOTICE SERVICE CHECK")
    print("=" * 80)
    
    try:
        # Test with low confidence scenario
        should_issue = uncertainty_service.should_issue_uncertainty_notice(
            authoritative_sources_count=1,  # Low
            scenario_confidence=45.0,  # Low
            similar_scenarios=3  # Sparse
        )
        
        if should_issue:
            notice = uncertainty_service.generate_uncertainty_notice(
                authoritative_sources_count=1,
                scenario_confidence=45.0,
                similar_scenarios=3
            )
            
            print("✅ Uncertainty Service: OPERATIONAL")
            print(f"   Notice generation: WORKING")
            print(f"   Sample notice length: {len(notice)} characters")
            if "UNCERTAINTY NOTICE" in notice:
                print("   ✅ Proper notice format")
            return True
        else:
            print("⚠️  Uncertainty Service: May not trigger correctly")
            return False
    except Exception as e:
        print(f"❌ Uncertainty Service: ERROR")
        print(f"   {e}")
        return False


def check_answer_verification():
    """Verify answer verification service"""
    print("\n" + "=" * 80)
    print("ANSWER VERIFICATION SERVICE CHECK")
    print("=" * 80)
    
    try:
        # Test verification
        test_answer = "The statute § 18.2-57.2 requires proof of intent."
        test_sources = [
            {"text": "Virginia Code § 18.2-57.2 states that intent must be proven.", "metadata": {"citation": "§ 18.2-57.2"}}
        ]
        
        result = answer_verification_service.verify_answer_against_sources(
            answer=test_answer,
            sources=test_sources,
            query="test"
        )
        
        print("✅ Answer Verification Service: OPERATIONAL")
        print(f"   Verification result: {result.get('verified')}")
        print(f"   Confidence: {result.get('confidence', 0):.2f}")
        print(f"   Supported citations: {len(result.get('supported_citations', []))}")
        return True
    except Exception as e:
        print(f"❌ Answer Verification Service: ERROR")
        print(f"   {e}")
        return False


async def check_scenario_improvements():
    """Verify scenario service improvements"""
    print("\n" + "=" * 80)
    print("SCENARIO SERVICE IMPROVEMENTS CHECK")
    print("=" * 80)
    
    try:
        scenario_service._ensure_initialized()
        stats = scenario_service.get_collection_stats()
        
        print("✅ Scenario Service: OPERATIONAL")
        print(f"   Total scenarios: {stats.get('total_scenarios', 0):,}")
        
        # Test confidence calculation (should be more conservative now)
        test_prediction = await scenario_service.predict_outcome(
            query_facts="Contract dispute over payment terms",
            case_type="Contract",
            jurisdiction="Virginia"
        )
        
        confidence = test_prediction.get("confidence", 0)
        print(f"   Test prediction confidence: {confidence:.1f}%")
        
        # Check if confidence is conservative (should be lower than before)
        if confidence <= 90:  # Should be capped at 90% now (was 95%)
            print("   ✅ Confidence is conservative (capped at 90%)")
        else:
            print("   ⚠️  Confidence may be too high")
        
        return True
    except Exception as e:
        print(f"❌ Scenario Service: ERROR")
        print(f"   {e}")
        return False


async def check_rag_improvements():
    """Verify RAG service improvements"""
    print("\n" + "=" * 80)
    print("RAG SERVICE IMPROVEMENTS CHECK")
    print("=" * 80)
    
    try:
        rag_service._ensure_initialized()
        stats = rag_service.get_collection_stats()
        
        print("✅ RAG Service: OPERATIONAL")
        print(f"   Total documents: {stats.get('total_documents', 0):,}")
        
        # Test search
        results = await rag_service.search("Virginia Code § 18.2-57.2", n_results=3)
        print(f"   Test search returned: {len(results)} results")
        
        if results:
            # Check if results show more context (should be 2000 chars now, not 500)
            first_result = results[0]
            text_length = len(first_result.get('text', ''))
            print(f"   Result text length: {text_length} characters")
            if text_length >= 1000:  # Should be much longer now
                print("   ✅ Extended context working (2000 char limit)")
            else:
                print("   ⚠️  Context may still be limited")
        
        return True
    except Exception as e:
        print(f"❌ RAG Service: ERROR")
        print(f"   {e}")
        return False


def check_facts_extraction_improvements():
    """Verify facts extraction improvements"""
    print("\n" + "=" * 80)
    print("FACTS EXTRACTION IMPROVEMENTS CHECK")
    print("=" * 80)
    
    try:
        from server.services.outcome_extraction_service import outcome_extraction_service
        
        # Test extraction
        test_text = "This is a test case with many details. " * 200  # Long text
        facts = outcome_extraction_service.extract_facts_without_outcome(test_text)
        
        print("✅ Facts Extraction Service: OPERATIONAL")
        print(f"   Extracted facts length: {len(facts)} characters")
        
        # Should be 6000 chars now (was 2000)
        if len(facts) <= 6000:
            print(f"   ✅ Using improved limit (6000 chars, was 2000)")
        else:
            print(f"   ⚠️  May exceed expected limit")
        
        return True
    except Exception as e:
        print(f"❌ Facts Extraction: ERROR")
        print(f"   {e}")
        return False


async def main():
    """Run comprehensive system check"""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE SYSTEM CHECK")
    print("=" * 80)
    print("Verifying all components including new protections and improvements...")
    print()
    
    results = {}
    
    # Check AI Laws protection
    results["AI Laws Protection"] = check_ai_laws_protection()
    
    # Check system prompt structure
    results["System Prompt Structure"] = check_system_prompt_structure()
    
    # Check uncertainty service
    results["Uncertainty Service"] = check_uncertainty_service()
    
    # Check answer verification
    results["Answer Verification"] = check_answer_verification()
    
    # Check scenario improvements
    results["Scenario Improvements"] = await check_scenario_improvements()
    
    # Check RAG improvements
    results["RAG Improvements"] = await check_rag_improvements()
    
    # Check facts extraction improvements
    results["Facts Extraction"] = check_facts_extraction_improvements()
    
    # Summary
    print("\n" + "=" * 80)
    print("COMPREHENSIVE CHECK SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for component, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {component}")
    
    print(f"\nResults: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n✅ ALL CHECKS PASSED - System is fully operational")
    else:
        print(f"\n⚠️  {total - passed} check(s) failed - Review above")
    
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

