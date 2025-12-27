"""
Pattern Detection Service - Detects and learns from error patterns
Identifies common error patterns and creates learning patterns for improvement
"""
import json
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from server.models import ErrorAnalysis, LearningPattern, PredictionValidation


class PatternDetectionService:
    def __init__(self):
        self.pattern_cache = {}
    
    def detect_patterns_from_errors(self, db: Session, min_occurrences: int = 3) -> List[Dict]:
        """
        Analyze error analyses to detect common patterns
        Returns list of detected patterns
        """
        # Get all error analyses
        error_analyses = db.query(ErrorAnalysis).all()
        
        # Group by error type
        error_type_groups = {}
        for analysis in error_analyses:
            error_type = analysis.error_type
            if error_type not in error_type_groups:
                error_type_groups[error_type] = []
            error_type_groups[error_type].append(analysis)
        
        detected_patterns = []
        
        # Analyze each error type group
        for error_type, analyses in error_type_groups.items():
            if len(analyses) >= min_occurrences:
                pattern = self._analyze_error_type_pattern(error_type, analyses, db)
                if pattern:
                    detected_patterns.append(pattern)
        
        return detected_patterns
    
    def _analyze_error_type_pattern(
        self, error_type: str, analyses: List[ErrorAnalysis], db: Session
    ) -> Optional[Dict]:
        """Analyze a specific error type to extract patterns"""
        
        # Extract common conditions
        common_conditions = {}
        case_types = set()
        recommendations_list = []
        
        for analysis in analyses:
            # Get validation to access case metadata
            validation = db.query(PredictionValidation).filter(
                PredictionValidation.id == analysis.validation_id
            ).first()
            
            if validation:
                if validation.case_type:
                    case_types.add(validation.case_type)
            
            # Extract recommendations
            try:
                recs = json.loads(analysis.recommendations) if analysis.recommendations else []
                recommendations_list.extend(recs)
            except:
                pass
        
        # Count recommendation frequency
        rec_counts = {}
        for rec in recommendations_list:
            rec_counts[rec] = rec_counts.get(rec, 0) + 1
        
        # Get top recommendations
        top_recommendations = sorted(
            rec_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]
        
        # Calculate accuracy impact
        # Get validations for these errors
        validation_ids = [a.validation_id for a in analyses]
        total_with_error = len(validation_ids)
        
        # This is a simplified impact calculation
        # In a real system, you'd track accuracy before/after applying pattern
        accuracy_impact = -5.0  # Default: assume 5% negative impact
        
        pattern_description = f"Error pattern: {error_type}. Occurs in {total_with_error} cases. "
        if case_types:
            pattern_description += f"Affects case types: {', '.join(case_types)}. "
        
        pattern = {
            "pattern_type": error_type,
            "pattern_description": pattern_description,
            "conditions": common_conditions,
            "recommendations": [rec for rec, count in top_recommendations],
            "affected_case_types": list(case_types),
            "occurrence_count": total_with_error,
            "accuracy_impact": accuracy_impact
        }
        
        return pattern
    
    def save_pattern(self, db: Session, pattern: Dict) -> LearningPattern:
        """Save or update a learning pattern"""
        
        # Check if pattern already exists
        existing = db.query(LearningPattern).filter(
            LearningPattern.pattern_type == pattern["pattern_type"],
            LearningPattern.is_active == True
        ).first()
        
        if existing:
            # Update existing pattern
            existing.pattern_description = pattern["pattern_description"]
            existing.conditions = json.dumps(pattern.get("conditions", {}))
            existing.recommendations = json.dumps(pattern.get("recommendations", []))
            existing.affected_case_types = ",".join(pattern.get("affected_case_types", []))
            existing.occurrence_count += pattern.get("occurrence_count", 1)
            existing.accuracy_impact = pattern.get("accuracy_impact")
            existing.last_seen = datetime.utcnow()
            db.commit()
            return existing
        else:
            # Create new pattern
            new_pattern = LearningPattern(
                pattern_type=pattern["pattern_type"],
                pattern_description=pattern["pattern_description"],
                conditions=json.dumps(pattern.get("conditions", {})),
                recommendations=json.dumps(pattern.get("recommendations", [])),
                affected_case_types=",".join(pattern.get("affected_case_types", [])),
                occurrence_count=pattern.get("occurrence_count", 1),
                accuracy_impact=pattern.get("accuracy_impact")
            )
            db.add(new_pattern)
            db.commit()
            db.refresh(new_pattern)
            return new_pattern
    
    def apply_pattern_recommendations(
        self, case_facts: str, case_type: Optional[str], db: Session
    ) -> List[str]:
        """
        Get recommendations from active patterns that match current case
        This can be used to improve predictions before they're made
        """
        active_patterns = db.query(LearningPattern).filter(
            LearningPattern.is_active == True
        ).all()
        
        recommendations = []
        
        for pattern in active_patterns:
            # Check if pattern applies to this case
            applies = False
            
            # Check case type match
            if case_type and pattern.affected_case_types:
                case_types = pattern.affected_case_types.split(",")
                if case_type in case_types:
                    applies = True
            
            # Could add more sophisticated matching here
            
            if applies:
                try:
                    recs = json.loads(pattern.recommendations) if pattern.recommendations else []
                    recommendations.extend(recs)
                except:
                    pass
        
        return list(set(recommendations))  # Remove duplicates


# Singleton instance
pattern_detection_service = PatternDetectionService()

