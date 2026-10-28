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
        
        # Keywords that indicate user explicitly lacks information (strict - don't over-trigger)
        self.missing_info_indicators = [
            "vague", "unclear", "unspecified", "unknown", "not sure", "don't know"
        ]
        
        # Critical facts needed for scenario predictions
        self.critical_facts = {
            "case_type": ["contract", "tort", "criminal", "family", "employment", "real estate"],
            "jurisdiction": ["virginia", "federal", "state", "court"],
            "parties": ["plaintiff", "defendant", "party", "claimant"],
            "claims": ["breach", "negligence", "damages", "injury", "violation", "claim"],
            "facts": ["what happened", "facts", "circumstances", "situation"]
        }
    
    def _is_substantive_factual_scenario(self, query: str) -> bool:
        """
        Check if user has given enough factual context that we should answer, not clarify.
        Covers all scenario types: criminal, family, civil, contract, employment, property, etc.
        """
        query_lower = query.lower()
        words = query.split()
        # Need enough content - 10+ words for a substantive scenario
        if len(words) < 10:
            return False
        # Broad factual/legal indicators across all practice areas
        factual_terms = [
            # Criminal / arrest
            "arrest", "arrested", "charged", "charges", "fight", "fought", "officer", "police",
            "witnessed", "seen", "happened", "occurred", "assault", "battery", "theft", "dui",
            # Parties / people
            "brothers", "sisters", "husband", "wife", "spouse", "ex-", "children", "child",
            "employer", "employee", "landlord", "tenant", "neighbor", "contractor", "client",
            # Civil / contract
            "contract", "agreement", "breach", "owed", "owed me", "paid", "payment", "signed",
            "landlord", "tenant", "eviction", "lease", "rent", "property", "deed", "title",
            # Family
            "divorce", "custody", "visitation", "support", "alimony", "marriage", "married",
            # Employment
            "fired", "terminated", "discriminated", "harassment", "wages", "overtime",
            # Injury / tort
            "injured", "injury", "accident", "negligence", "damages", "medical",
            # General factual
            "received", "sent", "told", "said", "agreed", "refused", "denied", "sued",
            "court", "judge", "lawyer", "attorney", "hearing", "trial", "verdict"
        ]
        matches = sum(1 for t in factual_terms if t in query_lower)
        # 1+ factual term with 10+ words = substantive scenario
        if matches >= 1:
            return True
        # Or: asking "what are the options" / "what can I do" with 15+ words (implied context)
        question_phrases = ["what are the options", "what options", "what can i", "what should i",
                           "do i have", "can i", "my rights", "what are my", "how do i"]
        if any(phrase in query_lower for phrase in question_phrases) and len(words) >= 12:
            return True
        return False
    
    def needs_clarification(self, query: str, context: Optional[str] = None, sources: Optional[List[Dict]] = None) -> Tuple[bool, Optional[List[str]]]:
        """
        Determine if clarification is needed and what questions to ask
        
        Returns:
            Tuple of (needs_clarification: bool, questions: Optional[List[str]])
        """
        query_lower = query.lower()
        
        # If user has given a substantive factual scenario (e.g. "two brothers fought, officer arrested both, what are the options"),
        # answer it - don't ask for clarification
        if self._is_substantive_factual_scenario(query):
            return (False, None)
        
        # Check if this is a scenario/prediction question
        is_scenario_question = any(keyword in query_lower for keyword in self.scenario_keywords)
        
        # Check if query is too vague or ambiguous
        is_vague = any(indicator in query_lower for indicator in self.missing_info_indicators)
        
        # Check if sources are insufficient (only trigger when zero - one source is enough to try)
        sources_insufficient = sources is None or len(sources) == 0
        
        questions = []
        
        # Scenario questions: only ask when MULTIPLE critical facts are missing (not just one)
        if is_scenario_question:
            missing_facts = self._check_missing_scenario_facts(query, context)
            if len(missing_facts) >= 2:  # Require 2+ missing before blocking
                questions.extend(missing_facts[:2])
        
        # Non-scenario: only check ambiguous terms if query is very short or explicitly vague
        if not is_scenario_question and (is_vague or len(query.split()) < 4):
            ambiguous_terms = self._detect_ambiguous_terms(query)
            if ambiguous_terms:
                questions.extend(ambiguous_terms)
        
        # Don't trigger on short queries alone - many valid legal questions are brief (e.g. "What is 18.2-57?")
        if is_vague and len(query.split()) < 4:
            questions.append("Could you provide more specific details about what you're looking for?")
        
        # Only ask about limited sources when we have ZERO and query is long/specific
        if sources_insufficient and not is_vague and len(query.split()) > 15:
            questions.append("I found no matching sources. Could you rephrase or specify which aspect you'd like me to focus on?")
        
        # Return True if we have questions to ask
        return (len(questions) > 0, questions if questions else None)
    
    def _check_missing_scenario_facts(self, query: str, context: Optional[str] = None) -> List[str]:
        """Check what critical facts are missing for scenario prediction. Looser thresholds."""
        query_lower = query.lower()
        combined_text = f"{query} {context or ''}".lower()
        missing = []
        
        # Check for case type (Virginia/criminal implied by context often)
        has_case_type = any(term in combined_text for term in self.critical_facts["case_type"])
        if not has_case_type:
            missing.append("What type of case is this? (e.g., contract dispute, personal injury, criminal matter)")
        
        # Jurisdiction: Virginia is default for this system - don't require if query mentions Virginia statutes
        has_jurisdiction = any(term in combined_text for term in self.critical_facts["jurisdiction"])
        has_va_statute = "18.2" in combined_text or "19.2" in combined_text or "virginia" in combined_text or "va " in combined_text
        if not has_jurisdiction and not has_va_statute:
            missing.append("Which jurisdiction applies? (e.g., Virginia state court, federal court)")
        
        # Key facts: 20+ words or explicit facts mention is enough
        word_count = len(query.split())
        has_detailed_facts = word_count > 20 or any(term in combined_text for term in self.critical_facts["facts"])
        if not has_detailed_facts:
            missing.append("Could you provide more details about the key facts and circumstances of this case?")
        
        # Parties: plaintiff/defendant often implied
        has_parties = any(term in combined_text for term in self.critical_facts["parties"])
        if not has_parties:
            missing.append("Who are the parties involved? (plaintiff/claimant and defendant)")
        
        # Claims: breach, negligence, etc.
        has_claims = any(term in combined_text for term in self.critical_facts["claims"])
        if not has_claims:
            missing.append("What are the specific legal claims or issues in dispute?")
        
        return missing[:3]  # Limit to 3 most important questions
    
    def _detect_ambiguous_terms(self, query: str) -> List[str]:
        """Detect ambiguous terms. Only flag when clearly vague (something/anything)."""
        query_lower = query.lower()
        questions = []
        
        # Only flag explicitly vague terms - "it/this/that" are common in legal writing
        if re.search(r'\b(something|anything|everything)\b', query_lower):
            questions.append("Could you be more specific about what you're looking for?")
        
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

