"""
Smart Default Service - Analyzes query complexity and recommends detail level
"""
import re
from typing import Dict, List
from server.utils.logger import setup_logger


class SmartDefaultService:
    def __init__(self):
        self.logger = setup_logger("smart_default")
        
        # Keywords that indicate different detail levels
        self.trial_prep_keywords = [
            "appeal", "trial", "brief", "motion", "all cases", "every case", 
            "comprehensive list", "complete list", "exhaustive", "trial preparation",
            "appellate", "litigation"
        ]
        
        self.complex_indicators = [
            "compare", "distinguish", "analyze", "relationship between",
            "multiple jurisdictions", "conflicts", "circuit split", "versus"
        ]
        
        self.simple_indicators = [
            "what is", "define", "explain", "meaning of", "quick question"
        ]
        
    def detect_detail_level(self, query: str, conversation_history: List[Dict] = None) -> Dict:
        """
        Analyze query complexity and recommend appropriate detail level
        
        Returns:
            {
                "recommended_level": str,  # "summary", "standard", "comprehensive", "complete", "unlimited"
                "confidence": float,        # 0.0 to 1.0
                "reasons": List[str]        # Why this level was chosen
            }
        """
        query_lower = query.lower()
        reasons = []
        score = 0  # Base score starts at 0, will determine level
        
        # Check for trial prep keywords (highest priority)
        trial_keywords_found = [kw for kw in self.trial_prep_keywords if kw in query_lower]
        if trial_keywords_found:
            score += 40
            reasons.append(f"Trial prep keywords found: {', '.join(trial_keywords_found[:3])}")
        
        # Check for complexity indicators
        complex_found = [ind for ind in self.complex_indicators if ind in query_lower]
        if complex_found:
            score += 20
            reasons.append(f"Complex analysis required: {', '.join(complex_found[:2])}")
        
        # Check for simple indicators (reduces score)
        simple_found = [ind for ind in self.simple_indicators if ind in query_lower]
        if simple_found:
            score -= 10
            reasons.append(f"Simple query detected: {simple_found[0]}")
        
        # Count legal terms (indicates complexity)
        legal_terms = ["statute", "code", "regulation", "precedent", "doctrine", 
                       "jurisdiction", "plaintiff", "defendant", "tort", "contract",
                       "constitutional", "criminal", "civil", "procedure"]
        legal_term_count = sum(1 for term in legal_terms if term in query_lower)
        if legal_term_count >= 3:
            score += 15
            reasons.append(f"Multiple legal terms found ({legal_term_count})")
        elif legal_term_count >= 1:
            score += 5
        
        # Count question marks (multiple questions = more detail needed)
        question_count = query.count("?")
        if question_count > 2:
            score += 15
            reasons.append(f"Multiple questions ({question_count})")
        elif question_count > 1:
            score += 5
        
        # Check for code section references (indicates specific research)
        code_patterns = [
            r'\d+\.\d+\.\d+',  # 18.2.51
            r'\d+-\d+-\d+',    # 18-2-51
            r'§\s*\d+',        # § 18
            r'U\.S\.C\.',      # USC
            r'Va\.\s*Code'     # Va. Code
        ]
        has_code_ref = any(re.search(pattern, query) for pattern in code_patterns)
        if has_code_ref:
            score += 10
            reasons.append("Specific code section referenced")
        
        # Check query length (longer queries often need more detail)
        word_count = len(query.split())
        if word_count > 50:
            score += 15
            reasons.append(f"Long query ({word_count} words)")
        elif word_count > 30:
            score += 10
        elif word_count < 10:
            score -= 5
            reasons.append("Short query")
        
        # Check for jurisdiction complexity
        jurisdiction_count = 0
        jurisdictions = ["federal", "virginia", "state", "circuit", "district", "supreme"]
        jurisdiction_count = sum(1 for j in jurisdictions if j in query_lower)
        if jurisdiction_count > 1:
            score += 10
            reasons.append(f"Multiple jurisdictions mentioned ({jurisdiction_count})")
        
        # Check conversation history for escalating complexity
        if conversation_history and len(conversation_history) > 2:
            score += 5
            reasons.append("Continuing complex conversation")
        
        # Determine detail level based on score
        if score >= 40:
            level = "unlimited"
            confidence = min(0.95, 0.7 + (score - 40) * 0.01)
        elif score >= 25:
            level = "complete"
            confidence = min(0.90, 0.7 + (score - 25) * 0.02)
        elif score >= 15:
            level = "comprehensive"
            confidence = min(0.85, 0.6 + (score - 15) * 0.02)
        elif score >= 5:
            level = "standard"
            confidence = min(0.80, 0.6 + (score - 5) * 0.02)
        else:
            level = "summary" if score < 0 else "standard"
            confidence = 0.75
        
        # Ensure we have at least one reason
        if not reasons:
            reasons.append("Standard analysis based on query structure")
        
        self.logger.debug(f"Query analysis: score={score}, level={level}, confidence={confidence:.2f}")
        
        return {
            "recommended_level": level,
            "confidence": confidence,
            "reasons": reasons,
            "score": score  # Include for debugging
        }


smart_default_service = SmartDefaultService()

