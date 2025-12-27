"""
Monitoring Routes
System health and performance monitoring endpoints
Restricted to Admin and Attorney-Partner roles
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import datetime, timedelta
import os
import psutil
from pathlib import Path

from server.middleware.auth_middleware import require_role
from server.models import get_db, UserRole, ChatMessage, AuditLog, PredictionValidation
from server.config import settings
from server.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger("monitoring")


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    Public endpoint - no authentication required
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@router.get("/system")
async def system_status(
    current_user: str = Depends(require_role(UserRole.ADMIN, UserRole.ATTORNEY_PARTNER)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Detailed system status
    Restricted to Admin and Attorney-Partner
    """
    try:
        # Database stats
        from server.models import User
        total_users = db.query(User).count()
        total_chats = db.query(ChatMessage).count()
        recent_chats = db.query(ChatMessage).filter(
            ChatMessage.created_at >= datetime.now() - timedelta(days=1)
        ).count()
        
        # File system stats
        db_path = Path("data/legal_ai.db")
        db_size = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0
        
        chroma_path = Path(settings.CHROMA_DB_PATH)
        chroma_size = 0
        if chroma_path.exists():
            chroma_size = sum(
                f.stat().st_size for f in chroma_path.rglob('*') if f.is_file()
            ) / (1024 * 1024)
        
        # System resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Ollama check
        ollama_status = "unknown"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                if response.status_code == 200:
                    ollama_status = "running"
                else:
                    ollama_status = "error"
        except Exception:
            ollama_status = "unavailable"
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": {
                "size_mb": round(db_size, 2),
                "total_users": total_users,
                "total_chats": total_chats,
                "recent_chats_24h": recent_chats
            },
            "vector_db": {
                "size_mb": round(chroma_size, 2),
                "path": str(chroma_path)
            },
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2)
            },
            "services": {
                "ollama": ollama_status,
                "ollama_url": settings.OLLAMA_BASE_URL,
                "ollama_model": settings.OLLAMA_MODEL
            }
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")


@router.get("/stats")
async def system_stats(
    current_user: str = Depends(require_role(UserRole.ADMIN, UserRole.ATTORNEY_PARTNER)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    System statistics
    Restricted to Admin and Attorney-Partner
    """
    try:
        # User stats
        from server.models import User
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        
        # Chat stats
        total_chats = db.query(ChatMessage).count()
        chats_today = db.query(ChatMessage).filter(
            ChatMessage.created_at >= datetime.now().replace(hour=0, minute=0, second=0)
        ).count()
        chats_week = db.query(ChatMessage).filter(
            ChatMessage.created_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        # Audit log stats
        total_logs = db.query(AuditLog).count()
        logs_today = db.query(AuditLog).filter(
            AuditLog.timestamp >= datetime.now().replace(hour=0, minute=0, second=0)
        ).count()
        
        # Learning stats (if enabled)
        learning_stats = {}
        if settings.SCENARIO_DB_ENABLED:
            try:
                total_validations = db.query(PredictionValidation).count()
                correct_predictions = db.query(PredictionValidation).filter(
                    PredictionValidation.is_correct == True
                ).count()
                accuracy = (correct_predictions / total_validations * 100) if total_validations > 0 else 0
                learning_stats = {
                    "total_validations": total_validations,
                    "correct_predictions": correct_predictions,
                    "accuracy_percent": round(accuracy, 2)
                }
            except Exception:
                pass
        
        return {
            "users": {
                "total": total_users,
                "active": active_users
            },
            "chats": {
                "total": total_chats,
                "today": chats_today,
                "last_7_days": chats_week
            },
            "audit_logs": {
                "total": total_logs,
                "today": logs_today
            },
            "learning": learning_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

