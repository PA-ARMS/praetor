"""
Validation Routes - API endpoints for prediction validation and error analysis
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from server.models import (
    PredictionValidation, ErrorAnalysis, LearningPattern,
    get_db, User
)
from server.middleware.auth_middleware import require_auth
from server.services.error_analysis_service import error_analysis_service
from server.services.pattern_detection_service import pattern_detection_service

router = APIRouter()


class ValidationStatsResponse(BaseModel):
    total_validations: int
    correct_predictions: int
    incorrect_predictions: int
    overall_accuracy: float
    accuracy_by_case_type: dict
    accuracy_by_confidence_range: dict
    error_type_distribution: dict
    recent_accuracy: float  # Last 30 days


class ValidationResponse(BaseModel):
    id: int
    case_id: str
    case_name: Optional[str]
    predicted_outcome: str
    actual_outcome: str
    is_correct: bool
    predicted_confidence: float
    error_type: Optional[str]
    validated_at: str


class ErrorAnalysisResponse(BaseModel):
    id: int
    validation_id: int
    error_type: str
    severity: Optional[str]
    insights: dict
    recommendations: List[str]
    analyzed_at: str


@router.get("/stats", response_model=ValidationStatsResponse)
async def get_validation_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get validation statistics and accuracy metrics"""
    
    # Overall stats
    total = db.query(PredictionValidation).count()
    correct = db.query(PredictionValidation).filter(PredictionValidation.is_correct == True).count()
    incorrect = total - correct
    accuracy = (correct / total * 100) if total > 0 else 0
    
    # By case type
    case_type_stats = {}
    case_types = db.query(PredictionValidation.case_type).distinct().all()
    for (case_type,) in case_types:
        if case_type:
            type_total = db.query(PredictionValidation).filter(
                PredictionValidation.case_type == case_type
            ).count()
            type_correct = db.query(PredictionValidation).filter(
                PredictionValidation.case_type == case_type,
                PredictionValidation.is_correct == True
            ).count()
            case_type_stats[case_type] = {
                "total": type_total,
                "correct": type_correct,
                "accuracy": (type_correct / type_total * 100) if type_total > 0 else 0
            }
    
    # By confidence range
    confidence_ranges = {
        "high_70_plus": (70, 100),
        "medium_50_70": (50, 70),
        "low_below_50": (0, 50)
    }
    confidence_stats = {}
    for range_name, (min_conf, max_conf) in confidence_ranges.items():
        range_total = db.query(PredictionValidation).filter(
            PredictionValidation.predicted_confidence >= min_conf,
            PredictionValidation.predicted_confidence < max_conf
        ).count()
        range_correct = db.query(PredictionValidation).filter(
            PredictionValidation.predicted_confidence >= min_conf,
            PredictionValidation.predicted_confidence < max_conf,
            PredictionValidation.is_correct == True
        ).count()
        confidence_stats[range_name] = {
            "total": range_total,
            "correct": range_correct,
            "accuracy": (range_correct / range_total * 100) if range_total > 0 else 0
        }
    
    # Error type distribution
    error_types = db.query(
        PredictionValidation.error_type,
        func.count(PredictionValidation.id).label('count')
    ).filter(
        PredictionValidation.is_correct == False
    ).group_by(PredictionValidation.error_type).all()
    
    error_distribution = {error_type or "unknown": count for error_type, count in error_types}
    
    # Recent accuracy (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_total = db.query(PredictionValidation).filter(
        PredictionValidation.validated_at >= thirty_days_ago
    ).count()
    recent_correct = db.query(PredictionValidation).filter(
        PredictionValidation.validated_at >= thirty_days_ago,
        PredictionValidation.is_correct == True
    ).count()
    recent_accuracy = (recent_correct / recent_total * 100) if recent_total > 0 else 0
    
    return ValidationStatsResponse(
        total_validations=total,
        correct_predictions=correct,
        incorrect_predictions=incorrect,
        overall_accuracy=round(accuracy, 2),
        accuracy_by_case_type=case_type_stats,
        accuracy_by_confidence_range=confidence_stats,
        error_type_distribution=error_distribution,
        recent_accuracy=round(recent_accuracy, 2)
    )


@router.get("/validations", response_model=List[ValidationResponse])
async def get_validations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    is_correct: Optional[bool] = None,
    case_type: Optional[str] = None,
    error_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get validation results with filtering"""
    
    query = db.query(PredictionValidation)
    
    if is_correct is not None:
        query = query.filter(PredictionValidation.is_correct == is_correct)
    
    if case_type:
        query = query.filter(PredictionValidation.case_type == case_type)
    
    if error_type:
        query = query.filter(PredictionValidation.error_type == error_type)
    
    validations = query.order_by(desc(PredictionValidation.validated_at)).offset(skip).limit(limit).all()
    
    return [
        ValidationResponse(
            id=v.id,
            case_id=v.case_id,
            case_name=v.case_name,
            predicted_outcome=v.predicted_outcome,
            actual_outcome=v.actual_outcome,
            is_correct=v.is_correct,
            predicted_confidence=v.predicted_confidence,
            error_type=v.error_type,
            validated_at=v.validated_at.isoformat()
        )
        for v in validations
    ]


@router.get("/validations/{validation_id}/analysis", response_model=ErrorAnalysisResponse)
async def get_error_analysis(
    validation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get detailed error analysis for a validation"""
    
    validation = db.query(PredictionValidation).filter(
        PredictionValidation.id == validation_id
    ).first()
    
    if not validation:
        raise HTTPException(status_code=404, detail="Validation not found")
    
    if validation.is_correct:
        raise HTTPException(status_code=400, detail="No error analysis for correct predictions")
    
    error_analysis = db.query(ErrorAnalysis).filter(
        ErrorAnalysis.validation_id == validation_id
    ).first()
    
    if not error_analysis:
        raise HTTPException(status_code=404, detail="Error analysis not found")
    
    import json
    insights = json.loads(error_analysis.insights) if error_analysis.insights else {}
    recommendations = json.loads(error_analysis.recommendations) if error_analysis.recommendations else []
    
    return ErrorAnalysisResponse(
        id=error_analysis.id,
        validation_id=error_analysis.validation_id,
        error_type=error_analysis.error_type,
        severity=error_analysis.severity,
        insights=insights,
        recommendations=recommendations,
        analyzed_at=error_analysis.analyzed_at.isoformat()
    )


@router.get("/patterns", response_model=List[dict])
async def get_learning_patterns(
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get learned patterns from error analysis"""
    
    query = db.query(LearningPattern)
    
    if is_active is not None:
        query = query.filter(LearningPattern.is_active == is_active)
    
    patterns = query.order_by(desc(LearningPattern.occurrence_count)).all()
    
    import json
    return [
        {
            "id": p.id,
            "pattern_type": p.pattern_type,
            "pattern_description": p.pattern_description,
            "conditions": json.loads(p.conditions) if p.conditions else {},
            "recommendations": json.loads(p.recommendations) if p.recommendations else [],
            "affected_case_types": p.affected_case_types.split(",") if p.affected_case_types else [],
            "occurrence_count": p.occurrence_count,
            "accuracy_impact": p.accuracy_impact,
            "first_seen": p.first_seen.isoformat(),
            "last_seen": p.last_seen.isoformat()
        }
        for p in patterns
    ]


@router.get("/confusion-matrix")
async def get_confusion_matrix(
    case_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get confusion matrix showing predicted vs actual outcomes"""
    
    query = db.query(PredictionValidation)
    
    if case_type:
        query = query.filter(PredictionValidation.case_type == case_type)
    
    validations = query.all()
    
    # Build confusion matrix
    matrix = {}
    outcomes = set()
    
    for v in validations:
        pred = v.predicted_outcome
        actual = v.actual_outcome
        outcomes.add(pred)
        outcomes.add(actual)
        
        if actual not in matrix:
            matrix[actual] = {}
        if pred not in matrix[actual]:
            matrix[actual][pred] = 0
        matrix[actual][pred] += 1
    
    # Format as table
    outcome_list = sorted(list(outcomes))
    result = {
        "matrix": matrix,
        "outcomes": outcome_list,
        "total": len(validations)
    }
    
    return result


@router.post("/detect-patterns")
async def detect_patterns(
    min_occurrences: int = Query(3, ge=2, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Detect learning patterns from error analyses and save them"""
    
    if current_user.role.value not in ["admin", "attorney_partner"]:
        raise HTTPException(status_code=403, detail="Only admins and partners can detect patterns")
    
    # Detect patterns
    patterns = pattern_detection_service.detect_patterns_from_errors(db, min_occurrences)
    
    # Save patterns
    saved_patterns = []
    for pattern in patterns:
        saved = pattern_detection_service.save_pattern(db, pattern)
        saved_patterns.append({
            "id": saved.id,
            "pattern_type": saved.pattern_type,
            "occurrence_count": saved.occurrence_count
        })
    
    return {
        "patterns_detected": len(patterns),
        "patterns_saved": len(saved_patterns),
        "patterns": saved_patterns
    }

