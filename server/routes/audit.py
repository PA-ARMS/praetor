"""
Audit log routes - Restricted to Admin and Attorney-Partner
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime

from server.middleware.auth_middleware import require_role
from server.models import get_db, AuditLog, UserRole

router = APIRouter()


@router.get("/logs")
def list_audit_logs(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    since: Optional[str] = Query(None, description="ISO datetime, e.g., 2025-11-15T00:00:00"),
    limit: int = 100,
    offset: int = 0,
    _: str = Depends(require_role(UserRole.ADMIN, UserRole.ATTORNEY_PARTNER)),
    db: Session = Depends(get_db)
):
    """
    List audit logs with optional filters.
    Restricted to Admin and Attorney-Partner roles.
    """
    q = db.query(AuditLog).order_by(AuditLog.timestamp.desc())
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if since:
        try:
            dt = datetime.fromisoformat(since)
            q = q.filter(AuditLog.timestamp >= dt)
        except Exception:
            pass

    total = q.count()
    rows: List[AuditLog] = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "logs": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action": r.action,
                "path": r.path,
                "method": r.method,
                "status": r.status,
                "ip_address": r.ip_address,
                "user_agent": r.user_agent,
                "details": r.details,
                "timestamp": r.timestamp.isoformat()
            } for r in rows
        ]
    }

