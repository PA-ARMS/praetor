"""
User Knowledge Service - Manages user-provided legal knowledge and expertise
Incorporates user knowledge into RAG searches and responses
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import json

from server.models import UserKnowledge, User, UserRole
from server.services.rag_service import rag_service
from server.utils.logger import setup_logger


class UserKnowledgeService:
    def __init__(self):
        self.logger = setup_logger("user_knowledge")
    
    async def add_knowledge_to_rag(
        self,
        knowledge: UserKnowledge,
        db: Session
    ) -> bool:
        """
        Add user knowledge to RAG corpus for searchability
        Returns True if successfully added
        """
        try:
            # Create document from knowledge
            knowledge_doc = f"""
USER KNOWLEDGE: {knowledge.title}

Type: {knowledge.knowledge_type}
Topic: {knowledge.topic or 'General'}
Jurisdiction: {knowledge.jurisdiction or 'Not specified'}

Content:
{knowledge.content}

{f'Related Statutes: {knowledge.related_statutes}' if knowledge.related_statutes else ''}
{f'Related Cases: {knowledge.related_cases}' if knowledge.related_cases else ''}
{f'Tags: {knowledge.tags}' if knowledge.tags else ''}

Source: {'Attorney Expertise' if knowledge.is_attorney_knowledge else 'User Provided'}
Created: {knowledge.created_at}
"""
            
            # Add to RAG corpus with high priority for attorney knowledge
            metadata = {
                "source": "user_knowledge",
                "jurisdiction": knowledge.jurisdiction or "Virginia",
                "knowledge_id": str(knowledge.id),
                "knowledge_type": knowledge.knowledge_type,
                "topic": knowledge.topic or "",
                "is_attorney_knowledge": knowledge.is_attorney_knowledge,
                "verified": knowledge.verified_by_attorney,
                "priority": 2 if knowledge.is_attorney_knowledge else 3,  # Attorney knowledge is more authoritative
                "user_id": str(knowledge.user_id)
            }
            
            doc_id = f"user_knowledge_{knowledge.id}"
            await rag_service.add_document(knowledge_doc, metadata, doc_id=doc_id)
            
            # Mark as incorporated
            knowledge.incorporated_into_rag = True
            db.commit()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding knowledge to RAG: {e}", exc_info=True)
            db.rollback()
            return False
    
    async def get_relevant_knowledge(
        self,
        query: str,
        db: Session,
        limit: int = 5,
        user_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get relevant user knowledge for a query
        Prioritizes attorney knowledge and verified knowledge
        """
        # Search active knowledge
        query_lower = query.lower()
        
        # Build query
        db_query = db.query(UserKnowledge).filter(
            UserKnowledge.is_active == True
        )
        
        # Filter by user if specified (for personal knowledge)
        if user_id:
            # Include user's own knowledge + attorney knowledge + verified knowledge
            db_query = db_query.filter(
                (UserKnowledge.user_id == user_id) |
                (UserKnowledge.is_attorney_knowledge == True) |
                (UserKnowledge.verified_by_attorney == True)
            )
        else:
            # Only attorney and verified knowledge
            db_query = db_query.filter(
                (UserKnowledge.is_attorney_knowledge == True) |
                (UserKnowledge.verified_by_attorney == True)
            )
        
        # Get all matching knowledge
        all_knowledge = db_query.all()
        
        # Score and rank by relevance
        scored_knowledge = []
        for knowledge in all_knowledge:
            score = 0.0
            
            # Check content match
            content_lower = knowledge.content.lower()
            title_lower = knowledge.title.lower()
            topic_lower = (knowledge.topic or "").lower()
            
            # Score based on matches
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3:  # Only meaningful words
                    if word in content_lower:
                        score += 0.1
                    if word in title_lower:
                        score += 0.3
                    if word in topic_lower:
                        score += 0.2
            
            # Boost attorney knowledge
            if knowledge.is_attorney_knowledge:
                score += 0.5
            
            # Boost verified knowledge
            if knowledge.verified_by_attorney:
                score += 0.3
            
            # Boost by usage (popular knowledge)
            score += min(0.2, knowledge.usage_count * 0.01)
            
            scored_knowledge.append((score, knowledge))
        
        # Sort by score
        scored_knowledge.sort(key=lambda x: x[0], reverse=True)
        
        # Return top results
        results = []
        for score, knowledge in scored_knowledge[:limit]:
            if score > 0:  # Only return if some relevance
                results.append({
                    "id": knowledge.id,
                    "title": knowledge.title,
                    "content": knowledge.content[:300] + "..." if len(knowledge.content) > 300 else knowledge.content,
                    "knowledge_type": knowledge.knowledge_type,
                    "topic": knowledge.topic,
                    "jurisdiction": knowledge.jurisdiction,
                    "is_attorney": knowledge.is_attorney_knowledge,
                    "verified": knowledge.verified_by_attorney,
                    "related_statutes": json.loads(knowledge.related_statutes) if knowledge.related_statutes else [],
                    "related_cases": json.loads(knowledge.related_cases) if knowledge.related_cases else [],
                    "relevance_score": score
                })
        
        return results
    
    def increment_usage(self, knowledge_id: int, db: Session):
        """Increment usage count when knowledge is used"""
        knowledge = db.query(UserKnowledge).filter(UserKnowledge.id == knowledge_id).first()
        if knowledge:
            knowledge.usage_count += 1
            db.commit()
    
    def mark_helpful(self, knowledge_id: int, db: Session):
        """Mark knowledge as helpful"""
        knowledge = db.query(UserKnowledge).filter(UserKnowledge.id == knowledge_id).first()
        if knowledge:
            knowledge.helpful_count += 1
            db.commit()


# Singleton instance
user_knowledge_service = UserKnowledgeService()

