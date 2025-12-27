"""
Clarification Service - Detects when AI needs to ask clarifying questions
"""
import re
from typing import Dict, List, Optional, Tuple
from server.utils.logger import setup_logger

logger = setup_logger("clarification")


class ClarificationService:
    """Service to detect when clarification is needed and generate questions"""
    
    def __init__(self):
        # Keywords that indicate scenario/prediction questions
        self.scenario_keywords = [
            "outcome", "likely", "probability", "chance", "predict", "what will happen",
            "what happens", "result", "win", "lose", "settlement", "dismissal",
            "success", "failure", "risk", "odds", "prospects", "scenario",
            "my case", "this case", "our case", "client", "plaintiff", "defendant"
        ]
        
        # Keywords that indicate missing critical information
        self.missing_info_indicators = [
            "vague", "unclear", "unspecified", "unknown", "not sure", "don't know",
            "maybe", "possibly", "might", "could be"
        ]
        
        # Critical facts needed for scenario predictions
        self.critical_facts = {
            "case_type": ["contract", "tort", "criminal", "family", "employment", "real estate"],
            "jurisdiction": ["virginia", "federal", "state", "court"],
            "parties": ["plaintiff", "defendant", "party", "claimant"],
            "claims": ["breach", "negligence", "damages", "injury", "violation", "claim"],
            "facts": ["what happened", "facts", "circumstances", "situation"]
        }
    
    def needs_clarification(self, query: str, context: Optional[str] = None, sources: Optional[List[Dict]] = None) -> Tuple[bool, Optional[List[str]]]:
        """
        Determine if clarification is needed and what questions to ask
        
        Returns:
            Tuple of (needs_clarification: bool, questions: Optional[List[str]])
        """
        query_lower = query.lower()
        
        # Check if this is a scenario/prediction question
        is_scenario_question = any(keyword in query_lower for keyword in self.scenario_keywords)
        
        # Check if query is too vague or ambiguous
        is_vague = any(indicator in query_lower for indicator in self.missing_info_indicators)
        
        # Check if sources are insufficient or ambiguous
        sources_insufficient = False
        if sources is None or len(sources) == 0:
            sources_insufficient = True
        elif len(sources) < 2:
            # Only one source - might need clarification
            sources_insufficient = True
        
        questions = []
        
        # Scenario questions need specific information
        if is_scenario_question:
            missing_facts = self._check_missing_scenario_facts(query, context)
            if missing_facts:
                questions.extend(missing_facts)
        
        # Check for ambiguous legal queries
        if not is_scenario_question:
            ambiguous_terms = self._detect_ambiguous_terms(query)
            if ambiguous_terms:
                questions.extend(ambiguous_terms)
        
        # Check if query is too vague
        if is_vague or len(query.split()) < 5:
            questions.append("Could you provide more specific details about what you're looking for?")
        
        # If sources are insufficient and query is specific, ask for clarification
        if sources_insufficient and not is_vague and len(query.split()) > 10:
            questions.append("I found limited sources. Could you clarify which specific aspect you'd like me to focus on?")
        
        # Return True if we have questions to ask
        return (len(questions) > 0, questions if questions else None)
    
    def _check_missing_scenario_facts(self, query: str, context: Optional[str] = None) -> List[str]:
        """Check what critical facts are missing for scenario prediction"""
        query_lower = query.lower()
        combined_text = f"{query} {context or ''}".lower()
        missing = []
        
        # Check for case type
        has_case_type = any(term in combined_text for term in self.critical_facts["case_type"])
        if not has_case_type:
            missing.append("What type of case is this? (e.g., contract dispute, personal injury, criminal matter)")
        
        # Check for jurisdiction
        has_jurisdiction = any(term in combined_text for term in self.critical_facts["jurisdiction"])
        if not has_jurisdiction:
            missing.append("Which jurisdiction applies? (e.g., Virginia state court, federal court)")
        
        # Check for key facts/details
        word_count = len(query.split())
        has_detailed_facts = word_count > 30 or any(term in combined_text for term in self.critical_facts["facts"])
        if not has_detailed_facts:
            missing.append("Could you provide more details about the key facts and circumstances of this case?")
        
        # Check for parties
        has_parties = any(term in combined_text for term in self.critical_facts["parties"])
        if not has_parties:
            missing.append("Who are the parties involved? (plaintiff/claimant and defendant)")
        
        # Check for specific claims/legal issues
        has_claims = any(term in combined_text for term in self.critical_facts["claims"])
        if not has_claims:
            missing.append("What are the specific legal claims or issues in dispute?")
        
        return missing[:3]  # Limit to 3 most important questions
    
    def _detect_ambiguous_terms(self, query: str) -> List[str]:
        """Detect ambiguous terms that need clarification"""
        query_lower = query.lower()
        questions = []
        
        # Check for vague references
        vague_patterns = [
            (r'\b(it|this|that|these|those)\b', "Could you clarify what specific statute/case/issue you're referring to?"),
            (r'\b(something|anything|everything)\b', "Could you be more specific about what you're looking for?"),
            (r'\b(related|similar|like this)\b', "Could you provide more details about what you mean by 'related' or 'similar'?"),
        ]
        
        for pattern, question in vague_patterns:
            if re.search(pattern, query_lower):
                questions.append(question)
                break  # Only ask one question about vagueness
        
        # Check for multiple possible interpretations
        if "or" in query_lower and query.count("?") == 0:
            # Has "or" but not a question - might be ambiguous
            questions.append("Are you asking about one specific option, or would you like information about all of them?")
        
        return questions[:1]  # Limit to 1 question
    
    def format_clarification_questions(self, questions: List[str], query: str) -> str:
        """Format clarification questions in a user-friendly way"""
        if not questions:
            return ""
        
        if len(questions) == 1:
            return f"\n\nTo provide the most accurate answer, I need a bit more information:\n\n{questions[0]}"
        else:
            formatted = "\n\nTo provide the most accurate answer, I need some additional information:\n\n"
            for i, question in enumerate(questions, 1):
                formatted += f"{i}. {question}\n"
            return formatted


# Singleton instance
clarification_service = ClarificationService()

