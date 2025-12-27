"""
System status and statistics routes
Provides endpoints for monitoring system health and usage statistics
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import time
import os
import platform

from server.models import get_db, User, ChatMessage, AuditLog
from server.middleware.auth_middleware import get_current_user, require_auth
from server.config import settings

router = APIRouter()

# Track server start time for uptime calculation
SERVER_START_TIME = time.time()


@router.get("/status")
async def get_system_status():
    """Get system status including uptime and basic health information"""
    current_time = time.time()
    uptime_seconds = int(current_time - SERVER_START_TIME)
    
    # Check if key services are available
    ollama_status = "unknown"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.OLLAMA_HOST}/api/tags")
            if response.status_code == 200:
                ollama_status = "online"
            else:
                ollama_status = "error"
    except:
        ollama_status = "offline"
    
    return {
        "status": "running",
        "uptime": uptime_seconds,
        "started_at": datetime.fromtimestamp(SERVER_START_TIME).isoformat(),
        "version": "1.0.0",
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "services": {
            "ollama": ollama_status,
            "database": "online",
            "tts": "online" if settings.TTS_ENABLED else "disabled"
        }
    }


@router.get("/stats")
async def get_system_stats(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Get system usage statistics (requires authentication)"""
    # Calculate time range for today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Total users
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    
    # Active today (users who logged in today)
    try:
        active_today = db.query(AuditLog).filter(
            AuditLog.action == "login_success",
            AuditLog.timestamp >= today_start
        ).distinct(AuditLog.user_id).count()
    except:
        active_today = 0
    
    # Total queries (chat messages)
    try:
        total_queries = db.query(ChatMessage).filter(
            ChatMessage.role == "user"
        ).count()
    except:
        total_queries = 0
    
    # Queries today
    try:
        queries_today = db.query(ChatMessage).filter(
            ChatMessage.role == "user",
            ChatMessage.created_at >= today_start
        ).count()
    except:
        queries_today = 0
    
    # Documents uploaded (count from rag collection if available)
    documents_uploaded = 0
    try:
        # Try to count documents from ChromaDB
        from server.services.rag_service import get_rag_service
        rag = get_rag_service()
        if rag and rag.collection:
            documents_uploaded = rag.collection.count()
    except:
        pass
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "active_today": active_today,
        "total_queries": total_queries,
        "queries_today": queries_today,
        "documents_uploaded": documents_uploaded,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

