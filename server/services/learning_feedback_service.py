"""
Learning Feedback Service - Applies learned patterns to improve predictions
Uses error analysis and patterns to enhance prediction quality
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
import json

from server.models import LearningPattern, PredictionValidation, ErrorAnalysis
from server.services.pattern_detection_service import pattern_detection_service


class LearningFeedbackService:
    def __init__(self):
        self.pattern_cache = {}
        self.calibration_cache = {}
    
    def get_prediction_enhancements(
        self,
        case_facts: str,
        case_type: Optional[str],
        jurisdiction: Optional[str],
        db: Session
    ) -> Dict:
        """
        Get enhancements for prediction based on learned patterns
        Returns suggestions to improve prediction quality
        """
        enhancements = {
            "warnings": [],
            "suggested_checks": [],
            "confidence_adjustments": [],
            "factor_reminders": []
        }
        
        # Get active patterns
        active_patterns = db.query(LearningPattern).filter(
            LearningPattern.is_active == True
        ).all()
        
        for pattern in active_patterns:
            # Check if pattern applies
            if self._pattern_applies(pattern, case_type, case_facts):
                # Get recommendations
                try:
                    recs = json.loads(pattern.recommendations) if pattern.recommendations else []
                    enhancements["suggested_checks"].extend(recs)
                except:
                    pass
                
                # Add warnings based on pattern
                if pattern.pattern_type == "procedural_miss":
                    enhancements["warnings"].append(
                        "This case type has historically missed procedural elements. "
                        "Verify statute of limitations, jurisdiction, and procedural requirements."
                    )
                elif pattern.pattern_type == "overconfidence":
                    enhancements["warnings"].append(
                        "Similar cases have shown overconfidence issues. "
                        "Consider lowering confidence if key facts are ambiguous."
                    )
                elif pattern.pattern_type == "legal_factor_miss":
                    enhancements["warnings"].append(
                        "Key legal factors may be missing. "
                        "Review case for all relevant legal elements."
                    )
                elif pattern.pattern_type == "reasoning_gap":
                    enhancements["warnings"].append(
                        "Reasoning alignment gaps detected. "
                        "Double-check that the rationale cites the controlling authority."
                    )
                    enhancements["factor_reminders"].append(
                        "Compare your reasoning to the official holding and explain the link."
                    )
        
        # Get confidence calibration based on historical accuracy
        calibration = self._get_confidence_calibration(case_type, db)
        if calibration:
            enhancements["confidence_adjustments"].append(calibration)
        
        return enhancements
    
    def _pattern_applies(
        self, pattern: LearningPattern, case_type: Optional[str], case_facts: str
    ) -> bool:
        """Check if a pattern applies to this case"""
        # Check case type match
        if case_type and pattern.affected_case_types:
            case_types = pattern.affected_case_types.split(",")
            if case_type in case_types:
                return True
        
        # Could add more sophisticated matching based on conditions
        return False
    
    def _get_confidence_calibration(
        self, case_type: Optional[str], db: Session
    ) -> Optional[Dict]:
        """Get confidence calibration based on historical accuracy"""
        # Get validations for this case type
        query = db.query(PredictionValidation)
        if case_type:
            query = query.filter(PredictionValidation.case_type == case_type)
        
        validations = query.all()
        
        if len(validations) < 5:  # Need at least 5 for calibration
            return None
        
        # Calculate accuracy by confidence range
        high_conf_correct = sum(1 for v in validations 
                                if v.predicted_confidence >= 70 and v.is_correct)
        high_conf_total = sum(1 for v in validations if v.predicted_confidence >= 70)
        
        medium_conf_correct = sum(1 for v in validations 
                                 if 50 <= v.predicted_confidence < 70 and v.is_correct)
        medium_conf_total = sum(1 for v in validations 
                                if 50 <= v.predicted_confidence < 70)
        
        # If high confidence has low accuracy, suggest adjustment
        if high_conf_total > 0:
            high_conf_accuracy = high_conf_correct / high_conf_total
            if high_conf_accuracy < 0.6:  # Less than 60% accuracy at high confidence
                return {
                    "type": "lower_confidence",
                    "reason": f"High confidence predictions for {case_type or 'this case type'} have only {high_conf_accuracy*100:.1f}% accuracy",
                    "suggestion": "Consider reducing confidence by 10-15% for similar cases"
                }
        
        return None
    
    def apply_confidence_adjustment(
        self, base_confidence: float, enhancements: Dict, case_type: Optional[str]
    ) -> float:
        """Apply confidence adjustments based on learned patterns"""
        adjusted = base_confidence
        
        # Apply calibration adjustments
        for adj in enhancements.get("confidence_adjustments", []):
            if adj.get("type") == "lower_confidence":
                # Reduce confidence by 10-15%
                reduction = min(15.0, base_confidence * 0.15)
                adjusted = max(0.0, adjusted - reduction)
        
        # Apply pattern-based adjustments
        if any("overconfidence" in w.lower() for w in enhancements.get("warnings", [])):
            # Reduce confidence if overconfidence pattern detected
            adjusted = max(0.0, adjusted - 10.0)
        
        return round(adjusted, 1)
    
    def get_procedural_checks(self, case_facts: str, case_type: Optional[str], db: Session) -> List[str]:
        """Get procedural checks based on learned patterns"""
        checks = []
        
        # Check for procedural_miss patterns
        patterns = db.query(LearningPattern).filter(
            LearningPattern.pattern_type == "procedural_miss",
            LearningPattern.is_active == True
        ).all()
        
        for pattern in patterns:
            if self._pattern_applies(pattern, case_type, case_facts):
                checks.append("Verify statute of limitations")
                checks.append("Confirm jurisdiction")
                checks.append("Check procedural requirements")
                break
        
        # Add case-specific checks
        if case_type == "Contract":
            checks.append("Check contract formation requirements")
            checks.append("Verify consideration")
        elif case_type == "Tort":
            checks.append("Verify duty of care")
            checks.append("Check causation")
        
        return list(set(checks))  # Remove duplicates


# Singleton instance
learning_feedback_service = LearningFeedbackService()

