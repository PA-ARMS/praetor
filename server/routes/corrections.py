"""
Corrections API - Handle user corrections and feedback
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from server.models import User, UserCorrection, ChatMessage, UserRole, get_db
from server.middleware.auth_middleware import require_auth, require_role
from server.services.correction_verification_service import correction_verification_service
from server.utils.logger import setup_logger

router = APIRouter(prefix="/api/corrections", tags=["corrections"])
logger = setup_logger("corrections")


class CorrectionRequest(BaseModel):
    chat_message_id: int
    correction_type: str  # "factual_error", "citation_error", "missing_info", "incorrect_interpretation", "other"
    corrected_response: Optional[str] = None
    correction_details: str


class CorrectionResponse(BaseModel):
    id: int
    chat_message_id: int
    correction_type: str
    correction_details: Optional[str]
    verification_status: str
    verified_by_rag: bool
    is_attorney_correction: bool
    created_at: datetime


class CorrectionListResponse(BaseModel):
    corrections: List[CorrectionResponse]
    total: int


@router.post("/submit", response_model=CorrectionResponse)
async def submit_correction(
    request: CorrectionRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Submit a correction to an AI response"""
    # Verify chat message exists and belongs to user (or user has permission)
    chat_message = db.query(ChatMessage).filter(
        ChatMessage.id == request.chat_message_id
    ).first()
    
    if not chat_message:
        raise HTTPException(status_code=404, detail="Chat message not found")
    
    # Check permissions: user can correct their own messages, attorneys can correct any
    if chat_message.user_id != current_user.id:
        if current_user.role not in [UserRole.ATTORNEY, UserRole.ATTORNEY_PARTNER, UserRole.ADMIN]:
            raise HTTPException(status_code=403, detail="You can only correct your own messages")
    
    # Check if correction already exists
    existing = db.query(UserCorrection).filter(
        UserCorrection.chat_message_id == request.chat_message_id,
        UserCorrection.user_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Correction already submitted for this message")
    
    # Create correction
    is_attorney = current_user.role in [UserRole.ATTORNEY, UserRole.ATTORNEY_PARTNER]
    
    correction = UserCorrection(
        chat_message_id=request.chat_message_id,
        user_id=current_user.id,
        original_response=chat_message.response or "",
        corrected_response=request.corrected_response,
        correction_type=request.correction_type,
        correction_details=request.correction_details,
        is_attorney_correction=is_attorney,
        verification_status="pending"
    )
    
    db.add(correction)
    db.commit()
    db.refresh(correction)
    
    # Automatically verify if attorney correction
    if is_attorney:
        # Verify against RAG
        verification_result = await correction_verification_service.verify_correction(correction, db)
        
        correction.verification_status = "verified" if verification_result["verified"] else "needs_review"
        correction.verified_by_rag = verification_result.get("verified", False)
        correction.rag_verification_details = str(verification_result)
        correction.verified_at = datetime.utcnow()
        
        # If verified, incorporate into RAG
        if verification_result["verified"]:
            await correction_verification_service.incorporate_verified_correction(correction, db)
        
        db.commit()
        db.refresh(correction)
    else:
        # For non-attorney corrections, verify in background
        try:
            verification_result = await correction_verification_service.verify_correction(correction, db)
            
            if verification_result["verified"] and verification_result.get("confidence", 0) >= 0.7:
                correction.verification_status = "verified"
                correction.verified_by_rag = True
                correction.rag_verification_details = str(verification_result)
                correction.verified_at = datetime.utcnow()
                
                # Incorporate if high confidence
                if verification_result.get("confidence", 0) >= 0.8:
                    await correction_verification_service.incorporate_verified_correction(correction, db)
            else:
                correction.verification_status = "needs_review"
            
            db.commit()
            db.refresh(correction)
        except Exception as e:
            logger.warning(f"Error verifying correction: {e}", exc_info=True)
            # Leave as pending for manual review
    
    return CorrectionResponse(
        id=correction.id,
        chat_message_id=correction.chat_message_id,
        correction_type=correction.correction_type,
        correction_details=correction.correction_details,
        verification_status=correction.verification_status,
        verified_by_rag=correction.verified_by_rag,
        is_attorney_correction=correction.is_attorney_correction,
        created_at=correction.created_at
    )


@router.get("/list", response_model=CorrectionListResponse)
async def list_corrections(
    status: Optional[str] = None,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """List corrections (filtered by user permissions)"""
    query = db.query(UserCorrection)
    
    # Filter by user permissions
    if current_user.role in [UserRole.ADMIN, UserRole.ATTORNEY_PARTNER]:
        # Can see all corrections
        pass
    elif current_user.role == UserRole.ATTORNEY:
        # Can see corrections for their own messages and their paralegals
        query = query.join(ChatMessage).filter(
            (ChatMessage.user_id == current_user.id) |
            (ChatMessage.user_id.in_(
                db.query(User.id).filter(User.supervising_attorney_id == current_user.id)
            ))
        )
    else:
        # Paralegals can only see their own corrections
        query = query.filter(UserCorrection.user_id == current_user.id)
    
    # Filter by status if provided
    if status:
        query = query.filter(UserCorrection.verification_status == status)
    
    corrections = query.order_by(UserCorrection.created_at.desc()).limit(100).all()
    
    return CorrectionListResponse(
        corrections=[
            CorrectionResponse(
                id=c.id,
                chat_message_id=c.chat_message_id,
                correction_type=c.correction_type,
                correction_details=c.correction_details,
                verification_status=c.verification_status,
                verified_by_rag=c.verified_by_rag,
                is_attorney_correction=c.is_attorney_correction,
                created_at=c.created_at
            )
            for c in corrections
        ],
        total=len(corrections)
    )


@router.post("/{correction_id}/verify")
async def verify_correction(
    correction_id: int,
    current_user: User = Depends(require_role(UserRole.ATTORNEY, UserRole.ATTORNEY_PARTNER, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Manually verify a correction (attorney/admin only)"""
    correction = db.query(UserCorrection).filter(UserCorrection.id == correction_id).first()
    
    if not correction:
        raise HTTPException(status_code=404, detail="Correction not found")
    
    # Verify against RAG
    verification_result = await correction_verification_service.verify_correction(correction, db)
    
    correction.verification_status = "verified" if verification_result["verified"] else "needs_review"
    correction.verified_by_rag = verification_result.get("verified", False)
    correction.rag_verification_details = str(verification_result)
    correction.verified_by_attorney = True
    correction.verifying_attorney_id = current_user.id
    correction.verified_at = datetime.utcnow()
    
    # Incorporate into RAG if verified
    if verification_result["verified"]:
        await correction_verification_service.incorporate_verified_correction(correction, db)
    
    db.commit()
    db.refresh(correction)
    
    return {
        "status": "success",
        "verification_status": correction.verification_status,
        "verified_by_rag": correction.verified_by_rag,
        "incorporated": correction.incorporated_into_rag
    }

