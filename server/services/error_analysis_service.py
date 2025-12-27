"""
Error Analysis Service - Analyzes why predictions were wrong
Provides learning insights to improve future predictions
"""
import json
from typing import Dict, List, Optional
from datetime import datetime
from server.services.scenario_service import scenario_service
from server.services.ollama_service import ollama_service
from server.utils.logger import setup_logger


class ErrorAnalysisService:
    def __init__(self):
        self.logger = setup_logger("error_analysis")
        self.analysis_cache = {}
    
    async def analyze_prediction_error(
        self,
        case_facts: str,
        predicted_outcome: str,
        actual_outcome: str,
        prediction_confidence: float,
        similar_scenarios: List[Dict],
        case_metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze why a prediction was incorrect
        
        Returns comprehensive analysis with:
        - Error type classification
        - Outcome mismatch details
        - Misleading scenarios identification
        - Missing factors analysis
        - Confidence analysis
        - Learning insights
        - Improvement recommendations
        """
        
        # 1. Compare predicted vs actual outcome
        outcome_mismatch = self._analyze_outcome_mismatch(
            predicted_outcome, actual_outcome
        )
        
        # 2. Analyze similar scenarios that led to wrong prediction
        misleading_scenarios = self._identify_misleading_scenarios(
            similar_scenarios, actual_outcome
        )
        
        # 3. Extract key factors from actual case that weren't considered
        missing_factors = await self._identify_missing_factors(
            case_facts, similar_scenarios, actual_outcome, case_metadata
        )
        
        # 4. Analyze confidence vs accuracy
        confidence_analysis = self._analyze_confidence_error(
            prediction_confidence, outcome_mismatch
        )
        
        # 5. Determine error type
        error_type = self._classify_error_type(
            outcome_mismatch,
            misleading_scenarios,
            missing_factors,
            confidence_analysis
        )
        
        # 6. Generate learning insights using LLM
        insights = await self._generate_learning_insights(
            error_type,
            case_facts,
            predicted_outcome,
            actual_outcome,
            missing_factors,
            misleading_scenarios,
            confidence_analysis
        )
        
        return {
            "error_type": error_type,
            "outcome_mismatch": outcome_mismatch,
            "misleading_scenarios": misleading_scenarios,
            "missing_factors": missing_factors,
            "confidence_analysis": confidence_analysis,
            "insights": insights,
            "recommendations": self._generate_recommendations(error_type, insights, missing_factors),
            "analyzed_at": datetime.now().isoformat()
        }
    
    def _analyze_outcome_mismatch(
        self, predicted: str, actual: str
    ) -> Dict:
        """Analyze how far off the prediction was"""
        # Map outcomes to categories
        outcome_categories = {
            "Plaintiff Win": "win",
            "Defendant Win": "win",
            "Dismissed": "dismissal",
            "Settlement": "settlement",
            "Reversed": "reversal",
            "Remanded": "remand",
            "Unknown": "unknown"
        }
        
        pred_cat = outcome_categories.get(predicted, "unknown")
        actual_cat = outcome_categories.get(actual, "unknown")
        
        severity = "major" if pred_cat != actual_cat else "minor"
        
        return {
            "predicted": predicted,
            "actual": actual,
            "predicted_category": pred_cat,
            "actual_category": actual_cat,
            "severity": severity,
            "is_complete_mismatch": pred_cat != actual_cat,
            "is_same_category": pred_cat == actual_cat
        }
    
    def _identify_misleading_scenarios(
        self, similar_scenarios: List[Dict], actual_outcome: str
    ) -> List[Dict]:
        """Find scenarios that led to wrong prediction"""
        misleading = []
        
        for scenario in similar_scenarios:
            scenario_outcome = scenario.get('outcome') or scenario.get('metadata', {}).get('outcome', 'Unknown')
            if scenario_outcome != actual_outcome:
                misleading.append({
                    "scenario_id": scenario.get('id'),
                    "scenario_outcome": scenario_outcome,
                    "actual_outcome": actual_outcome,
                    "similarity_score": scenario.get('similarity_score'),
                    "case_type": scenario.get('case_type') or scenario.get('metadata', {}).get('case_type'),
                    "reason": f"Similar case had {scenario_outcome} but actual was {actual_outcome}"
                })
        
        return sorted(misleading, key=lambda x: x.get('similarity_score', 0), reverse=True)
    
    async def _identify_missing_factors(
        self,
        case_facts: str,
        similar_scenarios: List[Dict],
        actual_outcome: str,
        case_metadata: Optional[Dict] = None
    ) -> Dict:
        """Identify key factors that were missing or not considered"""
        
        # Build enhanced prompt with more context
        similar_outcomes = []
        if similar_scenarios:
            similar_outcomes = [s.get('outcome') or s.get('metadata', {}).get('outcome', 'Unknown') 
                               for s in similar_scenarios[:3]]
        
        predicted_outcome = similar_scenarios[0].get('outcome', 'Unknown') if similar_scenarios else 'Unknown'
        outcome_mismatch_type = 'Major' if predicted_outcome != actual_outcome else 'Minor'
        
        # Use LLM to analyze what factors might have been missed
        analysis_prompt = f"""Analyze this legal case prediction error in detail:

Case Facts (first 1500 chars):
{case_facts[:1500]}

Predicted Outcome: {predicted_outcome}
Actual Outcome: {actual_outcome}
Outcome Mismatch: {outcome_mismatch_type}

Similar Cases Used: {len(similar_scenarios)} cases
Similar Case Outcomes: {', '.join(similar_outcomes) if similar_outcomes else 'None'}

Analyze systematically:
1. PROCEDURAL FACTORS: What procedural elements (statute of limitations, jurisdiction, venue, filing deadlines, service requirements) might have been missed?
2. LEGAL FACTORS: What key legal elements (elements of cause of action, defenses, burdens of proof, standards of review) were overlooked?
3. FACTUAL DISTINCTIONS: What specific factual differences between this case and similar cases should have changed the prediction?
4. EVIDENCE FACTORS: What evidence-related factors (burden of proof, admissibility, sufficiency) were not considered?
5. JURISDICTIONAL FACTORS: Were there jurisdiction-specific rules or procedures that were missed?

For each category, be specific and actionable. Focus on factors that, if considered, would have led to the correct prediction.

Provide a structured analysis with clear categories."""

        try:
            analysis = await ollama_service.generate(
                prompt=analysis_prompt,
                system_prompt="You are a legal analyst identifying why a case outcome prediction was incorrect. Be specific and focus on actionable insights."
            )
            
            # Extract structured factors from analysis
            factors = {
                "legal_factors": [],
                "factual_distinctions": [],
                "procedural_elements": [],
                "missing_elements": [],
                "analysis_text": analysis
            }
            
            # Simple extraction (could be enhanced with more sophisticated parsing)
            if "statute of limitations" in analysis.lower() or "SOL" in analysis.upper():
                factors["procedural_elements"].append("Statute of Limitations")
            if "jurisdiction" in analysis.lower():
                factors["procedural_elements"].append("Jurisdiction")
            if "evidence" in analysis.lower():
                factors["legal_factors"].append("Evidence")
            if "burden of proof" in analysis.lower():
                factors["legal_factors"].append("Burden of Proof")
            
            return factors
        except Exception as e:
            self.logger.warning(f"Error in LLM analysis: {e}")
            return {
                "legal_factors": [],
                "factual_distinctions": [],
                "procedural_elements": [],
                "missing_elements": [],
                "analysis_text": f"Error generating analysis: {str(e)}"
            }
    
    def _analyze_confidence_error(
        self, confidence: float, outcome_mismatch: Dict
    ) -> Dict:
        """Analyze if confidence was appropriate given the error"""
        is_wrong = outcome_mismatch.get("is_complete_mismatch", True)
        
        # High confidence on wrong answer = overconfidence
        # Low confidence on wrong answer = appropriate uncertainty
        if is_wrong:
            if confidence >= 70:
                confidence_issue = "overconfident"
            elif confidence >= 50:
                confidence_issue = "moderately_overconfident"
            else:
                confidence_issue = "appropriate_uncertainty"
        else:
            confidence_issue = "correct_prediction"
        
        return {
            "confidence": confidence,
            "was_wrong": is_wrong,
            "confidence_issue": confidence_issue,
            "should_have_been_lower": is_wrong and confidence >= 50,
            "calibration_needed": is_wrong and confidence >= 70
        }
    
    def _classify_error_type(
        self,
        outcome_mismatch: Dict,
        misleading_scenarios: List[Dict],
        missing_factors: Dict,
        confidence_analysis: Dict
    ) -> str:
        """Classify the type of error"""
        
        if confidence_analysis.get("calibration_needed"):
            return "overconfidence"
        
        if len(missing_factors.get("procedural_elements", [])) > 0:
            return "procedural_miss"
        
        if len(missing_factors.get("legal_factors", [])) > 0:
            return "legal_factor_miss"
        
        if len(misleading_scenarios) > len(misleading_scenarios) * 0.7:  # Most scenarios were misleading
            return "insufficient_data"
        
        if outcome_mismatch.get("severity") == "major":
            return "factual_distinction"
        
        return "unknown_error"
    
    async def _generate_learning_insights(
        self,
        error_type: str,
        case_facts: str,
        predicted_outcome: str,
        actual_outcome: str,
        missing_factors: Dict,
        misleading_scenarios: List[Dict],
        confidence_analysis: Dict
    ) -> Dict:
        """Generate actionable learning insights"""
        
        insights_prompt = f"""Generate learning insights from this prediction error:

Error Type: {error_type}
Predicted: {predicted_outcome}
Actual: {actual_outcome}
Confidence: {confidence_analysis.get('confidence')}%

Missing Factors Identified:
{json.dumps(missing_factors.get('analysis_text', ''), indent=2)}

Misleading Scenarios: {len(misleading_scenarios)} cases had different outcomes

Provide:
1. What should the system learn from this error?
2. What patterns should be flagged in future similar cases?
3. What questions should be asked before making predictions?
4. How can confidence be better calibrated?

Format as structured insights."""

        try:
            insights_text = await ollama_service.generate(
                prompt=insights_prompt,
                system_prompt="You are a machine learning analyst generating actionable insights for improving prediction accuracy."
            )
            
            return {
                "insights_text": insights_text,
                "error_type": error_type,
                "key_lessons": self._extract_key_lessons(insights_text),
                "actionable_items": self._extract_actionable_items(insights_text)
            }
        except Exception as e:
            return {
                "insights_text": f"Error generating insights: {str(e)}",
                "error_type": error_type,
                "key_lessons": [],
                "actionable_items": []
            }
    
    def _extract_key_lessons(self, insights_text: str) -> List[str]:
        """Extract key lessons from insights text"""
        lessons = []
        lines = insights_text.split('\n')
        for line in lines:
            if any(marker in line.lower() for marker in ['learn', 'should', 'must', 'need']):
                lessons.append(line.strip())
        return lessons[:5]  # Top 5 lessons
    
    def _extract_actionable_items(self, insights_text: str) -> List[str]:
        """Extract actionable items from insights"""
        actions = []
        lines = insights_text.split('\n')
        for line in lines:
            if any(marker in line.lower() for marker in ['check', 'verify', 'ask', 'confirm', 'validate']):
                actions.append(line.strip())
        return actions[:5]  # Top 5 actions
    
    def _generate_recommendations(
        self, error_type: str, insights: Dict, missing_factors: Dict
    ) -> List[str]:
        """Generate specific recommendations based on error type"""
        recommendations = []
        
        if error_type == "overconfidence":
            recommendations.append("Lower confidence threshold when key facts are ambiguous")
            recommendations.append("Request clarification on missing procedural elements")
        
        if error_type == "procedural_miss":
            recommendations.append("Always verify statute of limitations and jurisdiction")
            recommendations.append("Check procedural requirements before outcome prediction")
        
        if error_type == "legal_factor_miss":
            recommendations.append("Expand factor extraction to include identified missing factors")
            recommendations.append("Increase weight of legal elements in similarity matching")
        
        if error_type == "insufficient_data":
            recommendations.append("Increase minimum number of similar cases required")
            recommendations.append("Lower confidence when few similar cases found")
        
        if error_type == "factual_distinction":
            recommendations.append("Improve factual distinction detection in similar cases")
            recommendations.append("Weight factual similarities more heavily")
        
        # Add recommendations from insights
        for action in insights.get("actionable_items", []):
            if action and len(action) > 10:  # Filter out very short items
                recommendations.append(action)
        
        return recommendations[:10]  # Top 10 recommendations


# Singleton instance
error_analysis_service = ErrorAnalysisService()

