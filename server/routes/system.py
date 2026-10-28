"""
System status and statistics routes
Provides endpoints for monitoring system health and usage statistics
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pathlib import Path
import time
import os
import platform
import json

from server.models import get_db, User, ChatMessage, AuditLog
from server.middleware.auth_middleware import get_current_user, require_auth
from server.config import settings

router = APIRouter()

# Track server start time for uptime calculation
SERVER_START_TIME = time.time()


def _get_last_backup_info():
    """Read last backup timestamp from data/backups/last_backup.json if present."""
    try:
        backup_dir = Path(settings.DATA_DIR) / "backups"
        path = backup_dir / "last_backup.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            return {
                "timestamp": data.get("timestamp"),
                "success": data.get("success", [])
            }
    except Exception:
        pass
    return None


@router.get("/status")
async def get_system_status():
    """Get system status including uptime, basic health, and last backup."""
    current_time = time.time()
    uptime_seconds = int(current_time - SERVER_START_TIME)

    # Check if key services are available
    ollama_status = "unknown"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                ollama_status = "online"
            else:
                ollama_status = "error"
    except Exception:
        ollama_status = "offline"

    last_backup = _get_last_backup_info()

    return {
        "status": "running",
        "uptime": uptime_seconds,
        "started_at": datetime.fromtimestamp(SERVER_START_TIME).isoformat(),
        "version": "1.0.0",
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "last_backup": last_backup,
        "services": {
            "ollama": ollama_status,
            "database": "online"
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
    
    # Total queries (each ChatMessage = one user query + AI response)
    try:
        total_queries = db.query(ChatMessage).count()
    except Exception:
        total_queries = 0
    
    # Queries today
    try:
        queries_today = db.query(ChatMessage).filter(
            ChatMessage.timestamp >= today_start
        ).count()
    except Exception:
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

