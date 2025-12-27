"""
Correction Verification Service - Verifies user corrections against RAG system
Uses RAG to check if corrections are supported by authoritative sources
"""
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
import json

from server.models import UserCorrection, User, UserRole
from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service
from server.utils.logger import setup_logger


class CorrectionVerificationService:
    def __init__(self):
        self.logger = setup_logger("correction_verification")
    
    async def verify_correction(
        self,
        correction: UserCorrection,
        db: Session
    ) -> Dict:
        """
        Verify a correction against RAG system and authoritative sources
        Returns verification results with confidence level
        """
        verification_result = {
            "verified": False,
            "confidence": 0.0,
            "rag_support": [],
            "conflicting_sources": [],
            "verification_method": None,
            "recommendation": None
        }
        
        # Extract correction content to verify
        correction_text = correction.corrected_response or correction.correction_details
        if not correction_text:
            verification_result["recommendation"] = "Cannot verify: No correction text provided"
            return verification_result
        
        # Step 1: Search RAG for sources supporting the correction
        try:
            rag_results = await rag_service.search_comprehensive(
                correction_text,
                n_results_per_query=20,
                require_multiple_sources=True,
                min_authoritative_sources=2
            )
            
            # Check if multiple authoritative sources support the correction
            authoritative_sources = rag_results.get('authoritative_sources', [])
            
            if len(authoritative_sources) >= 2:
                # Multiple authoritative sources found - verify they support correction
                verification_result["verified"] = True
                verification_result["confidence"] = 0.85  # High confidence with 2+ authoritative sources
                verification_result["verification_method"] = "rag_multiple_sources"
                verification_result["rag_support"] = [
                    {
                        "source": s['source'],
                        "jurisdiction": s['jurisdiction'],
                        "priority": s['priority']
                    }
                    for s in authoritative_sources
                ]
                verification_result["recommendation"] = "Verified: Multiple authoritative sources support this correction"
            elif len(authoritative_sources) == 1:
                # Single authoritative source - moderate confidence
                verification_result["verified"] = True
                verification_result["confidence"] = 0.65
                verification_result["verification_method"] = "rag_single_source"
                verification_result["rag_support"] = [
                    {
                        "source": authoritative_sources[0]['source'],
                        "jurisdiction": authoritative_sources[0]['jurisdiction'],
                        "priority": authoritative_sources[0]['priority']
                    }
                ]
                verification_result["recommendation"] = "Partially verified: Single authoritative source found. Attorney review recommended."
            else:
                # No authoritative sources found - use LLM to analyze
                verification_result["verification_method"] = "llm_analysis"
                llm_verification = await self._verify_with_llm(correction)
                verification_result.update(llm_verification)
                
        except Exception as e:
            self.logger.error(f"Error verifying correction: {e}", exc_info=True)
            verification_result["recommendation"] = f"Verification error: {str(e)}"
        
        # Step 2: If attorney correction, automatically verify (with RAG check)
        if correction.is_attorney_correction:
            if verification_result["verified"]:
                verification_result["confidence"] = min(0.95, verification_result["confidence"] + 0.1)
                verification_result["recommendation"] = "Attorney correction verified by RAG sources"
            else:
                # Attorney correction but not verified by RAG - still accept but flag
                verification_result["verified"] = True
                verification_result["confidence"] = 0.75
                verification_result["recommendation"] = "Attorney correction accepted but not fully verified by RAG. May need review."
        
        return verification_result
    
    async def _verify_with_llm(
        self,
        correction: UserCorrection
    ) -> Dict:
        """Use LLM to analyze correction when RAG sources are insufficient"""
        prompt = f"""Analyze this legal correction and determine if it appears accurate:

Original AI Response:
{correction.original_response[:500]}

Correction:
{correction.corrected_response or correction.correction_details}

Correction Type: {correction.correction_type}

Determine:
1. Does the correction appear factually accurate?
2. Is it consistent with legal principles?
3. What confidence level (0-1) would you assign?

Respond in JSON format:
{{
    "verified": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "explanation",
    "recommendation": "what to do"
}}"""
        
        try:
            response = await ollama_service.generate(
                prompt=prompt,
                system_prompt="You are a legal verification assistant. Analyze corrections for accuracy."
            )
            
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "verified": result.get("verified", False),
                    "confidence": result.get("confidence", 0.5),
                    "recommendation": result.get("recommendation", "LLM analysis completed")
                }
        except Exception as e:
            self.logger.warning(f"LLM verification error: {e}")
        
        # Fallback
        return {
            "verified": False,
            "confidence": 0.3,
            "recommendation": "Unable to verify: Insufficient RAG sources and LLM analysis failed"
        }
    
    async def incorporate_verified_correction(
        self,
        correction: UserCorrection,
        db: Session
    ) -> bool:
        """
        Incorporate a verified correction into the RAG corpus
        Returns True if successfully incorporated
        """
        if not correction.verified_by_rag and not correction.is_attorney_correction:
            return False
        
        try:
            # Create a document from the correction
            correction_doc = f"""
CORRECTION VERIFIED: {correction.correction_type.upper()}

Original (INCORRECT):
{correction.original_response[:500]}

Corrected (VERIFIED):
{correction.corrected_response or correction.correction_details}

Correction Details:
{correction.correction_details or 'N/A'}

Verified by: {'Attorney' if correction.is_attorney_correction else 'RAG System'}
Verification Date: {correction.verified_at or datetime.utcnow()}
"""
            
            # Add to RAG corpus
            metadata = {
                "source": "user_correction",
                "jurisdiction": "Virginia",  # Default, could be extracted
                "correction_id": str(correction.id),
                "correction_type": correction.correction_type,
                "is_attorney_correction": correction.is_attorney_correction,
                "verified": True,
                "priority": 2 if correction.is_attorney_correction else 3  # Attorney corrections are more authoritative
            }
            
            doc_id = f"correction_{correction.id}"
            await rag_service.add_document(correction_doc, metadata, doc_id=doc_id)
            
            # Mark as incorporated
            correction.incorporated_into_rag = True
            correction.incorporated_at = datetime.utcnow()
            db.commit()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error incorporating correction: {e}", exc_info=True)
            db.rollback()
            return False
    
    async def get_relevant_corrections(
        self,
        query: str,
        db: Session,
        limit: int = 5
    ) -> List[Dict]:
        """
        Get relevant verified corrections for a query
        Used to inform AI responses with past corrections
        """
        # Search for corrections related to the query
        # This is a simple implementation - could be enhanced with vector search
        corrections = db.query(UserCorrection).filter(
            UserCorrection.verification_status == "verified",
            UserCorrection.incorporated_into_rag == True
        ).order_by(
            UserCorrection.created_at.desc()
        ).limit(limit).all()
        
        relevant = []
        query_lower = query.lower()
        
        for correction in corrections:
            # Simple keyword matching - could be enhanced
            correction_text = (correction.corrected_response or correction.correction_details or "").lower()
            original_text = correction.original_response.lower()
            
            # Check if query relates to correction
            if any(word in correction_text or word in original_text 
                   for word in query_lower.split() if len(word) > 3):
                relevant.append({
                    "id": correction.id,
                    "correction_type": correction.correction_type,
                    "original": correction.original_response[:200],
                    "corrected": correction.corrected_response[:200] if correction.corrected_response else None,
                    "details": correction.correction_details[:200] if correction.correction_details else None,
                    "is_attorney": correction.is_attorney_correction
                })
        
        return relevant


# Singleton instance
correction_verification_service = CorrectionVerificationService()

