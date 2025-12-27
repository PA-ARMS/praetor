"""
User Knowledge API - Manage user-provided legal knowledge
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json

from server.models import User, UserKnowledge, UserRole, get_db
from server.middleware.auth_middleware import require_auth, require_role
from server.services.user_knowledge_service import user_knowledge_service

router = APIRouter(prefix="/api/user-knowledge", tags=["user-knowledge"])


class KnowledgeRequest(BaseModel):
    title: str
    content: str
    knowledge_type: str  # "statute_interpretation", "case_note", "procedure", "precedent", "practice_tip", "other"
    topic: Optional[str] = None
    jurisdiction: Optional[str] = "Virginia"
    related_statutes: Optional[List[str]] = None
    related_cases: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class KnowledgeResponse(BaseModel):
    id: int
    title: str
    content: str
    knowledge_type: str
    topic: Optional[str]
    jurisdiction: Optional[str]
    is_attorney_knowledge: bool
    verified_by_attorney: bool
    incorporated_into_rag: bool
    usage_count: int
    created_at: datetime


class KnowledgeListResponse(BaseModel):
    knowledge: List[KnowledgeResponse]
    total: int


@router.post("/add", response_model=KnowledgeResponse)
async def add_knowledge(
    request: KnowledgeRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Add user knowledge to the learning library"""
    is_attorney = current_user.role in [UserRole.ATTORNEY, UserRole.ATTORNEY_PARTNER]
    
    knowledge = UserKnowledge(
        user_id=current_user.id,
        title=request.title,
        content=request.content,
        knowledge_type=request.knowledge_type,
        topic=request.topic,
        jurisdiction=request.jurisdiction or "Virginia",
        related_statutes=json.dumps(request.related_statutes) if request.related_statutes else None,
        related_cases=json.dumps(request.related_cases) if request.related_cases else None,
        tags=json.dumps(request.tags) if request.tags else None,
        notes=request.notes,
        is_attorney_knowledge=is_attorney,
        source_type="attorney_expertise" if is_attorney else "user_provided"
    )
    
    db.add(knowledge)
    db.commit()
    db.refresh(knowledge)
    
    # Automatically add attorney knowledge to RAG
    if is_attorney:
        await user_knowledge_service.add_knowledge_to_rag(knowledge, db)
    
    return KnowledgeResponse(
        id=knowledge.id,
        title=knowledge.title,
        content=knowledge.content,
        knowledge_type=knowledge.knowledge_type,
        topic=knowledge.topic,
        jurisdiction=knowledge.jurisdiction,
        is_attorney_knowledge=knowledge.is_attorney_knowledge,
        verified_by_attorney=knowledge.verified_by_attorney,
        incorporated_into_rag=knowledge.incorporated_into_rag,
        usage_count=knowledge.usage_count,
        created_at=knowledge.created_at
    )


@router.get("/list", response_model=KnowledgeListResponse)
async def list_knowledge(
    topic: Optional[str] = None,
    knowledge_type: Optional[str] = None,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """List user knowledge (filtered by permissions)"""
    query = db.query(UserKnowledge).filter(UserKnowledge.is_active == True)
    
    # Filter by user permissions
    if current_user.role in [UserRole.ADMIN, UserRole.ATTORNEY_PARTNER]:
        # Can see all knowledge
        pass
    elif current_user.role == UserRole.ATTORNEY:
        # Can see own + attorney knowledge + verified knowledge
        query = query.filter(
            (UserKnowledge.user_id == current_user.id) |
            (UserKnowledge.is_attorney_knowledge == True) |
            (UserKnowledge.verified_by_attorney == True)
        )
    else:
        # Paralegals can only see their own + verified attorney knowledge
        query = query.filter(
            (UserKnowledge.user_id == current_user.id) |
            (UserKnowledge.verified_by_attorney == True)
        )
    
    # Apply filters
    if topic:
        query = query.filter(UserKnowledge.topic.ilike(f"%{topic}%"))
    if knowledge_type:
        query = query.filter(UserKnowledge.knowledge_type == knowledge_type)
    
    knowledge_list = query.order_by(UserKnowledge.created_at.desc()).limit(100).all()
    
    return KnowledgeListResponse(
        knowledge=[
            KnowledgeResponse(
                id=k.id,
                title=k.title,
                content=k.content,
                knowledge_type=k.knowledge_type,
                topic=k.topic,
                jurisdiction=k.jurisdiction,
                is_attorney_knowledge=k.is_attorney_knowledge,
                verified_by_attorney=k.verified_by_attorney,
                incorporated_into_rag=k.incorporated_into_rag,
                usage_count=k.usage_count,
                created_at=k.created_at
            )
            for k in knowledge_list
        ],
        total=len(knowledge_list)
    )


@router.post("/{knowledge_id}/verify")
async def verify_knowledge(
    knowledge_id: int,
    current_user: User = Depends(require_role(UserRole.ATTORNEY, UserRole.ATTORNEY_PARTNER, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Verify knowledge (attorney/admin only)"""
    knowledge = db.query(UserKnowledge).filter(UserKnowledge.id == knowledge_id).first()
    
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    
    knowledge.verified_by_attorney = True
    knowledge.verifying_attorney_id = current_user.id
    
    # Add to RAG if not already added
    if not knowledge.incorporated_into_rag:
        await user_knowledge_service.add_knowledge_to_rag(knowledge, db)
    
    db.commit()
    db.refresh(knowledge)
    
    return {
        "status": "verified",
        "incorporated_into_rag": knowledge.incorporated_into_rag
    }


@router.post("/{knowledge_id}/incorporate")
async def incorporate_knowledge(
    knowledge_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Manually trigger incorporation into RAG"""
    knowledge = db.query(UserKnowledge).filter(UserKnowledge.id == knowledge_id).first()
    
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    
    # Check permissions
    if knowledge.user_id != current_user.id:
        if current_user.role not in [UserRole.ATTORNEY, UserRole.ATTORNEY_PARTNER, UserRole.ADMIN]:
            raise HTTPException(status_code=403, detail="You can only incorporate your own knowledge")
    
    success = await user_knowledge_service.add_knowledge_to_rag(knowledge, db)
    
    if success:
        return {"status": "incorporated", "knowledge_id": knowledge_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to incorporate knowledge")


@router.post("/{knowledge_id}/helpful")
async def mark_helpful(
    knowledge_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Mark knowledge as helpful"""
    user_knowledge_service.mark_helpful(knowledge_id, db)
    return {"status": "marked_helpful"}

