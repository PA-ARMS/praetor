"""
Motion Analysis Service - Analyzes uploaded motions against scenario database
Compares motion facts to similar cases to predict success probability
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
import json

from server.services.scenario_service import scenario_service
from server.services.outcome_extraction_service import outcome_extraction_service
from server.services.ollama_service import ollama_service


class MotionAnalysisService:
    """Analyzes motions and compares to scenario database"""
    
    async def analyze_motion(
        self,
        motion_text: str,
        motion_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        db_session: Optional[Session] = None
    ) -> Dict:
        """
        Analyze a motion by comparing it to similar cases in the scenario database
        
        Returns:
        - Similar cases found
        - Success probability prediction
        - Key factors identified
        - Recommendations
        - Risk assessment
        """
        
        # Extract facts from motion (remove procedural/formatting text)
        motion_facts = self._extract_motion_facts(motion_text)
        
        if not motion_facts or len(motion_facts.strip()) < 100:
            return {
                "error": "Could not extract sufficient facts from motion",
                "extracted_length": len(motion_facts.strip()) if motion_facts else 0
            }
        
        # Determine motion type if not provided
        if not motion_type:
            motion_type = self._detect_motion_type(motion_text)
        
        # Build filters for similar case search (ChromaDB format)
        filters = None
        if motion_type and jurisdiction:
            filters = {"$and": [{"case_type": motion_type}, {"jurisdiction": jurisdiction or "Virginia"}]}
        elif motion_type:
            filters = {"case_type": motion_type}
        elif jurisdiction:
            filters = {"jurisdiction": jurisdiction or "Virginia"}
        
        # Find similar cases
        similar_cases = await scenario_service.find_similar_scenarios(
            query_facts=motion_facts,
            n_results=20,
            filters=filters
        )
        
        # If no results with filters, try without filters
        if not similar_cases and filters:
            similar_cases = await scenario_service.find_similar_scenarios(
                query_facts=motion_facts,
                n_results=20,
                filters=None
            )
        
        if not similar_cases:
            return {
                "error": "No similar cases found in database",
                "motion_facts": motion_facts[:500],
                "recommendation": "Consider expanding the scenario database with more cases"
            }
        
        # Analyze outcomes of similar cases
        outcome_analysis = self._analyze_outcomes(similar_cases)
        
        # Predict success probability
        prediction = await scenario_service.predict_outcome(
            query_facts=motion_facts,
            case_type=motion_type,
            jurisdiction=jurisdiction or "Virginia",
            db_session=db_session
        )
        
        # Extract key factors from motion
        key_factors = await self._extract_key_factors(motion_facts, similar_cases)
        
        # Generate recommendations
        recommendations = await self._generate_recommendations(
            motion_facts,
            similar_cases,
            outcome_analysis,
            prediction
        )
        
        # Risk assessment
        risk_assessment = self._assess_risks(similar_cases, prediction)
        
        return {
            "motion_facts": motion_facts[:1000],  # First 1000 chars
            "motion_type": motion_type,
            "jurisdiction": jurisdiction or "Virginia",
            "similar_cases_count": len(similar_cases),
            "similar_cases": similar_cases[:5],  # Top 5
            "outcome_analysis": outcome_analysis,
            "prediction": prediction,
            "key_factors": key_factors,
            "recommendations": recommendations,
            "risk_assessment": risk_assessment,
            "success_probability": prediction.get("confidence", 0),
            "predicted_outcome": prediction.get("prediction", "Unknown")
        }
    
    def _extract_motion_facts(self, motion_text: str) -> str:
        """Extract factual content from motion, removing procedural boilerplate"""
        # Remove common motion headers/footers
        lines = motion_text.split('\n')
        facts_lines = []
        
        skip_patterns = [
            "IN THE", "CIRCUIT COURT", "MOTION", "COMES NOW", "WHEREFORE",
            "RESPECTFULLY", "PRAY", "CERTIFICATE", "SERVICE", "FILED",
            "DATED", "ATTORNEY", "BAR NUMBER"
        ]
        
        for line in lines:
            line_upper = line.upper().strip()
            # Skip if it's mostly procedural boilerplate
            if any(pattern in line_upper for pattern in skip_patterns):
                if len(line.strip()) < 50:  # Short procedural lines
                    continue
            
            # Keep substantive content
            if len(line.strip()) > 20:  # Substantive lines
                facts_lines.append(line)
        
        facts = '\n'.join(facts_lines)
        
        # If we removed too much, use original with keyword masking
        if len(facts.strip()) < 200:
            # Use original but mask outcome keywords
            facts = motion_text
            outcome_keywords = ["granted", "denied", "dismissed", "sustained", "overruled"]
            for keyword in outcome_keywords:
                import re
                facts = re.sub(rf"\b{keyword}\b", "[outcome]", facts, flags=re.IGNORECASE)
        
        return facts
    
    def _detect_motion_type(self, text: str) -> Optional[str]:
        """Detect motion type from text"""
        text_lower = text.lower()
        
        if any(term in text_lower for term in ["dismiss", "dismissal", "12(b)(6)", "demurrer"]):
            return "Motion to Dismiss"
        elif any(term in text_lower for term in ["summary judgment", "no genuine issue"]):
            return "Motion for Summary Judgment"
        elif any(term in text_lower for term in ["compel", "discovery", "deposition"]):
            return "Motion to Compel"
        elif any(term in text_lower for term in ["strike", "pleading"]):
            return "Motion to Strike"
        elif any(term in text_lower for term in ["protective order", "seal"]):
            return "Motion for Protective Order"
        elif any(term in text_lower for term in ["default", "judgment"]):
            return "Motion for Default Judgment"
        
        return None
    
    def _analyze_outcomes(self, similar_cases: List[Dict]) -> Dict:
        """Analyze outcomes of similar cases"""
        outcomes = {}
        total = len(similar_cases)
        
        for case in similar_cases:
            outcome = case.get("metadata", {}).get("outcome", "Unknown")
            if outcome and outcome != "Unknown":
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
        
        # Calculate percentages
        outcome_percentages = {}
        for outcome, count in outcomes.items():
            outcome_percentages[outcome] = round((count / total * 100), 1) if total > 0 else 0
        
        # Determine most common outcome
        most_common = max(outcomes.items(), key=lambda x: x[1])[0] if outcomes else "Unknown"
        
        return {
            "outcome_counts": outcomes,
            "outcome_percentages": outcome_percentages,
            "most_common_outcome": most_common,
            "total_cases": total
        }
    
    async def _extract_key_factors(self, motion_facts: str, similar_cases: List[Dict]) -> List[str]:
        """Extract key factors from motion that influenced similar cases"""
        # Use LLM to identify key factors
        try:
            prompt = f"""Analyze this motion and identify the 3-5 most important legal factors that would determine its success:

Motion Facts:
{motion_facts[:1500]}

Based on similar cases, what are the key factors that typically determine success or failure? Return only a JSON array of factor strings, no other text."""
            
            response = await ollama_service.generate(prompt)
            
            # Try to extract JSON array
            import re
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                factors = json.loads(json_match.group())
                return factors if isinstance(factors, list) else []
        except:
            pass
        
        # Fallback: extract from similar cases metadata
        factors = set()
        for case in similar_cases[:5]:
            meta = case.get("metadata", {})
            key_factors = meta.get("key_factors", [])
            if isinstance(key_factors, list):
                factors.update(key_factors)
            elif isinstance(key_factors, str):
                factors.add(key_factors)
        
        return list(factors)[:5]
    
    async def _generate_recommendations(
        self,
        motion_facts: str,
        similar_cases: List[Dict],
        outcome_analysis: Dict,
        prediction: Dict
    ) -> List[str]:
        """Generate recommendations for improving the motion"""
        recommendations = []
        
        # Check success rate
        success_rate = outcome_analysis.get("outcome_percentages", {}).get("Plaintiff Win", 0)
        if success_rate < 50:
            recommendations.append(
                f"Low success rate ({success_rate}%) in similar cases. Consider strengthening arguments."
            )
        
        # Check confidence
        confidence = prediction.get("confidence", 0)
        if confidence < 50:
            recommendations.append(
                f"Low confidence prediction ({confidence}%). Review key factors and strengthen weak points."
            )
        
        # Check for missing factors
        if len(similar_cases) < 5:
            recommendations.append(
                "Limited similar cases found. Consider expanding arguments to cover broader scenarios."
            )
        
        # Use LLM for specific recommendations
        try:
            prompt = f"""Based on this motion and similar cases, provide 2-3 specific recommendations for improving the motion:

Motion Facts:
{motion_facts[:1000]}

Similar Cases Outcomes:
{json.dumps(outcome_analysis.get('outcome_percentages', {}), indent=2)}

Predicted Outcome: {prediction.get('prediction', 'Unknown')} ({prediction.get('confidence', 0)}% confidence)

Provide 2-3 specific, actionable recommendations. Return as a JSON array of strings."""
            
            response = await ollama_service.generate(prompt)
            import re
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                llm_recs = json.loads(json_match.group())
                if isinstance(llm_recs, list):
                    recommendations.extend(llm_recs[:3])
        except:
            pass
        
        return recommendations[:5]  # Limit to 5 recommendations
    
    def _assess_risks(self, similar_cases: List[Dict], prediction: Dict) -> Dict:
        """Assess risks and potential issues"""
        risks = []
        warnings = []
        
        confidence = prediction.get("confidence", 0)
        predicted_outcome = prediction.get("prediction", "Unknown")
        
        # Low confidence risk
        if confidence < 40:
            risks.append("High uncertainty - case outcome is difficult to predict")
            warnings.append("Consider additional research or consultation")
        
        # Check outcome distribution
        outcomes = {}
        for case in similar_cases:
            outcome = case.get("metadata", {}).get("outcome", "Unknown")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        
        # If outcomes are mixed, that's a risk
        if len(outcomes) > 2:
            risks.append("Mixed outcomes in similar cases - motion success is uncertain")
        
        # Check if predicted outcome matches most common
        most_common = max(outcomes.items(), key=lambda x: x[1])[0] if outcomes else None
        if most_common and predicted_outcome != most_common:
            warnings.append(f"Prediction differs from most common outcome ({most_common})")
        
        return {
            "risk_level": "high" if len(risks) > 1 else "medium" if len(risks) == 1 else "low",
            "risks": risks,
            "warnings": warnings,
            "confidence_level": "high" if confidence >= 70 else "medium" if confidence >= 50 else "low"
        }


# Singleton instance
motion_analysis_service = MotionAnalysisService()

