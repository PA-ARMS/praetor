"""
Answer Verification Service - Verifies that sources actually support the answer
Ensures answers are "right" by checking source alignment
"""
import re
from typing import Dict, List, Optional
from server.utils.logger import setup_logger


class AnswerVerificationService:
    def __init__(self):
        self.logger = setup_logger("answer_verification")
    
    def verify_answer_against_sources(
        self,
        answer: str,
        sources: List[Dict],
        query: str
    ) -> Dict:
        """
        Verify that the answer is actually supported by the sources
        
        Returns:
            {
                "verified": bool,
                "confidence": float (0-1),
                "issues": List[str],
                "supported_citations": List[str],
                "unsupported_citations": List[str]
            }
        """
        if not sources:
            return {
                "verified": False,
                "confidence": 0.0,
                "issues": ["No sources provided to verify against"],
                "supported_citations": [],
                "unsupported_citations": []
            }
        
        # Extract citations from answer (Virginia Code + VAC)
        answer_citations = self._extract_citations(answer)
        answer_citations.extend(self._extract_vac_citations(answer))
        
        # Extract citations from sources (Virginia Code + VAC regulations)
        source_citations = set()
        source_texts = []
        for source in sources:
            source_text = source.get('text', '')
            source_texts.append(source_text)
            # Extract Virginia Code citations from source text
            source_cits = self._extract_citations(source_text)
            source_citations.update(source_cits)
            # Extract VAC (Virginia Administrative Code) citations
            vac_cits = self._extract_vac_citations(source_text)
            source_citations.update(vac_cits)
            # Also check metadata
            meta_cit = source.get('metadata', {}).get('citation')
            if meta_cit:
                meta_str = str(meta_cit).replace('§', '').strip()
                source_citations.add(meta_str)
                # Check for VAC in metadata
                vac_meta = self._extract_vac_citations(meta_str)
                source_citations.update(vac_meta)
        
        # Check which citations are supported
        supported = []
        unsupported = []
        for cit in answer_citations:
            # Normalize citation for comparison
            cit_normalized = cit.replace('§', '').strip()
            # VAC citations stay as-is (e.g., "18 VAC 120-10-10")
            if ' VAC ' in cit or ' vac ' in cit.lower():
                cit_normalized = cit.strip()
            if cit_normalized in source_citations or any(cit_normalized in sc for sc in source_citations):
                supported.append(cit)
            else:
                unsupported.append(cit)
        
        # Check if key claims are supported
        issues = []
        confidence = 1.0
        
        # Issue 1: Unsupported citations
        if unsupported:
            issues.append(f"Answer cites {len(unsupported)} citation(s) not found in sources: {', '.join(unsupported[:3])}")
            confidence -= 0.3
        
        # Issue 2: Check if answer makes claims not in sources
        answer_key_claims = self._extract_key_claims(answer)
        source_content = " ".join(source_texts).lower()
        
        unsupported_claims = []
        for claim in answer_key_claims:
            # Check if claim appears in sources (simple keyword matching)
            claim_keywords = set(claim.lower().split())
            source_keywords = set(source_content.split())
            # If less than 30% of claim keywords appear in sources, it's unsupported
            overlap = len(claim_keywords & source_keywords) / len(claim_keywords) if claim_keywords else 0
            if overlap < 0.3:
                unsupported_claims.append(claim)
        
        if unsupported_claims:
            issues.append(f"Answer makes {len(unsupported_claims)} claim(s) not clearly supported by sources")
            confidence -= 0.2
        
        # Issue 3: Check if answer contradicts sources
        contradictions = self._check_contradictions(answer, source_texts)
        if contradictions:
            issues.append(f"Answer may contradict sources: {contradictions[0]}")
            confidence -= 0.4
        
        confidence = max(0.0, confidence)
        
        return {
            "verified": confidence >= 0.7 and len(unsupported) == 0,
            "confidence": confidence,
            "issues": issues,
            "supported_citations": supported,
            "unsupported_citations": unsupported
        }
    
    def _extract_citations(self, text: str) -> List[str]:
        """Extract Virginia Code citations from text"""
        # Pattern: § 18.2-57.2 or 18.2-57.2
        pattern = r'§?\s*(\d+\.\d+-\d+(?:\.\d+)?)'
        matches = re.findall(pattern, text)
        return [f"§ {m}" if not m.startswith("§") else m for m in matches]
    
    def _extract_vac_citations(self, text: str) -> List[str]:
        """Extract Virginia Administrative Code (VAC) citations from text"""
        # Pattern: 18 VAC 120-10-10 or 18 VAC 120-10
        pattern = r'(\d+)\s*VAC\s*(\d+)[-.](\d+)(?:[-.](\d+))?'
        matches = re.findall(pattern, text, re.IGNORECASE)
        result = []
        for m in matches:
            if len(m) == 4 and m[3]:
                result.append(f"{m[0]} VAC {m[1]}-{m[2]}-{m[3]}")
            else:
                result.append(f"{m[0]} VAC {m[1]}-{m[2]}")
        return result
    
    def _extract_key_claims(self, text: str) -> List[str]:
        """Extract key legal claims from answer"""
        # Look for sentences that make legal statements
        sentences = re.split(r'[.!?]+', text)
        claims = []
        
        legal_indicators = [
            "must", "shall", "required", "prohibited", "illegal", "legal",
            "violates", "violation", "elements", "statute", "code section"
        ]
        
        for sentence in sentences:
            sentence_lower = sentence.lower().strip()
            if any(indicator in sentence_lower for indicator in legal_indicators):
                if len(sentence.strip()) > 20:  # Filter out very short fragments
                    claims.append(sentence.strip())
        
        return claims[:10]  # Limit to top 10 claims
    
    def _check_contradictions(self, answer: str, sources: List[str]) -> List[str]:
        """Check if answer contradicts sources"""
        contradictions = []
        
        # Simple contradiction detection: look for negations
        answer_lower = answer.lower()
        source_text = " ".join(sources).lower()
        
        # Check for common contradiction patterns
        if "prohibited" in answer_lower and "permitted" in source_text:
            contradictions.append("Answer says 'prohibited' but source says 'permitted'")
        if "required" in answer_lower and "not required" in source_text:
            contradictions.append("Answer says 'required' but source says 'not required'")
        
        return contradictions


# Singleton instance
answer_verification_service = AnswerVerificationService()

