"""
Response Review API routes - For senior partners to review AI responses
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
import json

from server.models import get_db, User, ChatMessage, ResponseReview, UserRole
from server.middleware.auth_middleware import require_auth, require_role

router = APIRouter()


class ReviewRequest(BaseModel):
    chat_message_id: int
    review_status: str  # "approved", "needs_correction", "flagged"
    accuracy_rating: Optional[int] = None  # 1-5
    completeness_rating: Optional[int] = None  # 1-5
    clarity_rating: Optional[int] = None  # 1-5
    feedback_notes: Optional[str] = None
    correction_suggestions: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    should_incorporate: bool = True
    learning_priority: Optional[str] = "normal"  # "high", "normal", "low"


class ReviewResponse(BaseModel):
    id: int
    chat_message_id: int
    reviewer_id: int
    reviewer_name: str
    review_status: str
    accuracy_rating: Optional[int]
    completeness_rating: Optional[int]
    clarity_rating: Optional[int]
    feedback_notes: Optional[str]
    correction_suggestions: Optional[str]
    strengths: Optional[str]
    weaknesses: Optional[str]
    should_incorporate: bool
    learning_priority: Optional[str]
    reviewed_at: Optional[str]
    created_at: str


class MessageForReview(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_role: str
    conversation_id: str
    subject: Optional[str]
    message: str
    response: Optional[str]
    sources: Optional[List[dict]]
    warnings: Optional[List[str]]
    timestamp: str
    has_review: bool
    review_status: Optional[str]
    review_count: int


@router.get("/pending", response_model=List[MessageForReview])
async def get_pending_reviews(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_role(UserRole.ATTORNEY_PARTNER)),
    db: Session = Depends(get_db)
):
    """
    Get list of AI responses that need review (for senior partners)
    Returns messages that either have no review or have pending reviews
    """
    # Get all chat messages with responses, ordered by most recent
    messages = db.query(ChatMessage)\
        .filter(ChatMessage.response.isnot(None))\
        .filter(ChatMessage.response != "")\
        .order_by(desc(ChatMessage.timestamp))\
        .offset(offset)\
        .limit(limit)\
        .all()
    
    result = []
    for msg in messages:
        # Check if there are any reviews for this message
        reviews = db.query(ResponseReview)\
            .filter(ResponseReview.chat_message_id == msg.id)\
            .all()
        
        # Get the most recent review status
        latest_review = None
        if reviews:
            latest_review = max(reviews, key=lambda r: r.created_at)
        
        # Parse sources if available
        sources = None
        if msg.sources:
            try:
                sources = json.loads(msg.sources) if isinstance(msg.sources, str) else msg.sources
            except:
                sources = []
        
        # Parse warnings if available
        warnings = None
        if msg.warnings:
            try:
                warnings = json.loads(msg.warnings) if isinstance(msg.warnings, str) else msg.warnings
            except:
                warnings = []
        
        result.append(MessageForReview(
            id=msg.id,
            user_id=msg.user_id,
            user_name=msg.user.full_name,
            user_role=msg.user.role.value,
            conversation_id=msg.conversation_id,
            subject=msg.subject,
            message=msg.message,
            response=msg.response,
            sources=sources,
            warnings=warnings,
            timestamp=msg.timestamp.isoformat(),
            has_review=latest_review is not None,
            review_status=latest_review.review_status if latest_review else None,
            review_count=len(reviews)
        ))
    
    return result


@router.get("/message/{message_id}", response_model=List[ReviewResponse])
async def get_message_reviews(
    message_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get all reviews for a specific message
    """
    # Check if user can view this message
    message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Only allow viewing if user owns the message, is a senior partner, or is admin
    if (current_user.role != UserRole.ATTORNEY_PARTNER and 
        current_user.role != UserRole.ADMIN and 
        current_user.id != message.user_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    reviews = db.query(ResponseReview)\
        .filter(ResponseReview.chat_message_id == message_id)\
        .order_by(desc(ResponseReview.created_at))\
        .all()
    
    return [
        ReviewResponse(
            id=review.id,
            chat_message_id=review.chat_message_id,
            reviewer_id=review.reviewer_id,
            reviewer_name=review.reviewer.full_name,
            review_status=review.review_status,
            accuracy_rating=review.accuracy_rating,
            completeness_rating=review.completeness_rating,
            clarity_rating=review.clarity_rating,
            feedback_notes=review.feedback_notes,
            correction_suggestions=review.correction_suggestions,
            strengths=review.strengths,
            weaknesses=review.weaknesses,
            should_incorporate=review.should_incorporate,
            learning_priority=review.learning_priority,
            reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None,
            created_at=review.created_at.isoformat()
        )
        for review in reviews
    ]


@router.post("/submit", response_model=ReviewResponse)
async def submit_review(
    request: ReviewRequest,
    current_user: User = Depends(require_role(UserRole.ATTORNEY_PARTNER)),
    db: Session = Depends(get_db)
):
    """
    Submit a review for an AI response (senior partners only)
    """
    # Validate chat message exists
    message = db.query(ChatMessage).filter(ChatMessage.id == request.chat_message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Chat message not found")
    
    if not message.response:
        raise HTTPException(status_code=400, detail="Message has no AI response to review")
    
    # Validate ratings if provided
    if request.accuracy_rating and (request.accuracy_rating < 1 or request.accuracy_rating > 5):
        raise HTTPException(status_code=400, detail="Accuracy rating must be between 1 and 5")
    if request.completeness_rating and (request.completeness_rating < 1 or request.completeness_rating > 5):
        raise HTTPException(status_code=400, detail="Completeness rating must be between 1 and 5")
    if request.clarity_rating and (request.clarity_rating < 1 or request.clarity_rating > 5):
        raise HTTPException(status_code=400, detail="Clarity rating must be between 1 and 5")
    
    # Validate review status
    valid_statuses = ["approved", "needs_correction", "flagged"]
    if request.review_status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Review status must be one of: {', '.join(valid_statuses)}"
        )
    
    # Create review
    review = ResponseReview(
        chat_message_id=request.chat_message_id,
        reviewer_id=current_user.id,
        review_status=request.review_status,
        accuracy_rating=request.accuracy_rating,
        completeness_rating=request.completeness_rating,
        clarity_rating=request.clarity_rating,
        feedback_notes=request.feedback_notes,
        correction_suggestions=request.correction_suggestions,
        strengths=request.strengths,
        weaknesses=request.weaknesses,
        should_incorporate=request.should_incorporate,
        learning_priority=request.learning_priority or "normal",
        reviewed_at=datetime.utcnow()
    )
    
    db.add(review)
    db.commit()
    db.refresh(review)
    
    return ReviewResponse(
        id=review.id,
        chat_message_id=review.chat_message_id,
        reviewer_id=review.reviewer_id,
        reviewer_name=review.reviewer.full_name,
        review_status=review.review_status,
        accuracy_rating=review.accuracy_rating,
        completeness_rating=review.completeness_rating,
        clarity_rating=review.clarity_rating,
        feedback_notes=review.feedback_notes,
        correction_suggestions=review.correction_suggestions,
        strengths=review.strengths,
        weaknesses=review.weaknesses,
        should_incorporate=review.should_incorporate,
        learning_priority=review.learning_priority,
        reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None,
        created_at=review.created_at.isoformat()
    )


@router.get("/stats")
async def get_review_stats(
    current_user: User = Depends(require_role(UserRole.ATTORNEY_PARTNER)),
    db: Session = Depends(get_db)
):
    """
    Get review statistics for senior partners
    """
    total_messages = db.query(ChatMessage)\
        .filter(ChatMessage.response.isnot(None))\
        .filter(ChatMessage.response != "")\
        .count()
    
    reviewed_messages = db.query(ChatMessage)\
        .join(ResponseReview, ChatMessage.id == ResponseReview.chat_message_id)\
        .distinct()\
        .count()
    
    pending_count = total_messages - reviewed_messages
    
    # Get review status breakdown
    approved = db.query(ResponseReview)\
        .filter(ResponseReview.review_status == "approved")\
        .count()
    
    needs_correction = db.query(ResponseReview)\
        .filter(ResponseReview.review_status == "needs_correction")\
        .count()
    
    flagged = db.query(ResponseReview)\
        .filter(ResponseReview.review_status == "flagged")\
        .count()
    
    # Average ratings
    avg_accuracy = db.query(ResponseReview.accuracy_rating)\
        .filter(ResponseReview.accuracy_rating.isnot(None))\
        .all()
    avg_accuracy = sum(r[0] for r in avg_accuracy) / len(avg_accuracy) if avg_accuracy else None
    
    avg_completeness = db.query(ResponseReview.completeness_rating)\
        .filter(ResponseReview.completeness_rating.isnot(None))\
        .all()
    avg_completeness = sum(r[0] for r in avg_completeness) / len(avg_completeness) if avg_completeness else None
    
    avg_clarity = db.query(ResponseReview.clarity_rating)\
        .filter(ResponseReview.clarity_rating.isnot(None))\
        .all()
    avg_clarity = sum(r[0] for r in avg_clarity) / len(avg_clarity) if avg_clarity else None
    
    return {
        "total_messages": total_messages,
        "reviewed_messages": reviewed_messages,
        "pending_reviews": pending_count,
        "review_breakdown": {
            "approved": approved,
            "needs_correction": needs_correction,
            "flagged": flagged
        },
        "average_ratings": {
            "accuracy": round(avg_accuracy, 2) if avg_accuracy else None,
            "completeness": round(avg_completeness, 2) if avg_completeness else None,
            "clarity": round(avg_clarity, 2) if avg_clarity else None
        }
    }









