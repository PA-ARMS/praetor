"""
Uncertainty Service - Automatically generates Uncertainty Notices per AI Laws Article VIII
Ensures system indicates when confidence is limited or sources are weak
"""
from typing import Dict, List, Optional
from server.utils.logger import setup_logger


class UncertaintyService:
    def __init__(self):
        self.logger = setup_logger("uncertainty")
    
    def should_issue_uncertainty_notice(
        self,
        authoritative_sources_count: Optional[int] = None,
        secondary_sources_count: Optional[int] = None,
        verification_status: Optional[str] = None,
        scenario_confidence: Optional[float] = None,
        similar_scenarios: Optional[int] = None,
        conflict_messages: Optional[List[str]] = None,
        total_sources: Optional[int] = None
    ) -> bool:
        """
        Determine if an Uncertainty Notice should be issued per AI Laws Article VIII
        
        Conditions that trigger uncertainty:
        - Fewer than 2 authoritative sources found
        - Confidence below 60%
        - Conflicting authority exists
        - Sparse precedent (few similar cases)
        - Verification status is not 'verified'
        """
        # Check 1: Insufficient authoritative sources
        if authoritative_sources_count is not None and authoritative_sources_count < 2:
            return True
        
        # Check 2: Low confidence in scenario prediction
        if scenario_confidence is not None and scenario_confidence < 60:
            return True
        
        # Check 3: Sparse precedent (few similar cases)
        if similar_scenarios is not None and similar_scenarios < 5:
            return True
        
        # Check 4: Conflicting authority
        if conflict_messages and len(conflict_messages) > 0:
            return True
        
        # Check 5: Verification status indicates weak support
        if verification_status and verification_status != 'verified':
            return True
        
        # Check 6: Very few total sources
        if total_sources is not None and total_sources < 3:
            return True
        
        return False
    
    def generate_uncertainty_notice(
        self,
        authoritative_sources_count: Optional[int] = None,
        secondary_sources_count: Optional[int] = None,
        verification_status: Optional[str] = None,
        scenario_confidence: Optional[float] = None,
        similar_scenarios: Optional[int] = None,
        conflict_messages: Optional[List[str]] = None,
        total_sources: Optional[int] = None
    ) -> str:
        """
        Generate an Uncertainty Notice per AI Laws Article VIII
        
        Format:
        [UNCERTAINTY NOTICE: [reason]. Confidence in this answer is limited. [recommendations]]
        """
        reasons = []
        recommendations = []
        
        # Build reasons
        if authoritative_sources_count is not None and authoritative_sources_count < 2:
            reasons.append(f"only {authoritative_sources_count} authoritative source(s) found")
            recommendations.append("cross-reference with official sources (Code of Virginia, Virginia Administrative Code)")
        
        if scenario_confidence is not None and scenario_confidence < 60:
            reasons.append(f"low confidence ({scenario_confidence:.1f}%) in outcome prediction")
            recommendations.append("consider additional fact-finding before relying on this prediction")
        
        if similar_scenarios is not None and similar_scenarios < 5:
            reasons.append(f"sparse precedent ({similar_scenarios} similar case(s) found)")
            recommendations.append("Shepardize/KeyCite cases to confirm they remain good law")
        
        if conflict_messages and len(conflict_messages) > 0:
            reasons.append("conflicting authority exists")
            recommendations.append("review conflicting sources and determine which authority is controlling")
        
        if verification_status and verification_status != 'verified':
            reasons.append("sources not fully verified")
            recommendations.append("verify all citations against official sources")
        
        if total_sources is not None and total_sources < 3:
            reasons.append(f"limited sources found ({total_sources} source(s))")
            recommendations.append("conduct additional research to ensure comprehensive coverage")
        
        # Build notice
        if not reasons:
            return ""  # No uncertainty notice needed
        
        notice_parts = ["[UNCERTAINTY NOTICE:"]
        
        # Add reasons
        if len(reasons) == 1:
            notice_parts.append(f" {reasons[0]}")
        else:
            notice_parts.append(f" {', '.join(reasons[:-1])}, and {reasons[-1]}")
        
        notice_parts.append(". Confidence in this answer is limited.")
        
        # Add recommendations
        if recommendations:
            notice_parts.append(" Recommended actions:")
            for i, rec in enumerate(recommendations, 1):
                notice_parts.append(f" ({i}) {rec}")
            notice_parts.append(".")
        
        notice_parts.append(" This analysis should be independently verified before relying on it for legal decisions.]")
        
        return "".join(notice_parts)
    
    def add_uncertainty_notice_to_response(
        self,
        response: str,
        authoritative_sources_count: Optional[int] = None,
        secondary_sources_count: Optional[int] = None,
        verification_status: Optional[str] = None,
        scenario_confidence: Optional[float] = None,
        similar_scenarios: Optional[int] = None,
        conflict_messages: Optional[List[str]] = None,
        total_sources: Optional[int] = None
    ) -> str:
        """
        Add Uncertainty Notice to response if conditions are met
        """
        # Don't append uncertainty notices as separate sections - keep response cohesive
        # Uncertainty information is tracked but not forced into response format
        return response


# Singleton instance
uncertainty_service = UncertaintyService()

