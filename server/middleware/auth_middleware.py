"""
Authentication middleware - Protect routes and extract current user
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from server.models import get_db, User
from server.services.auth_service import decode_token


security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current authenticated user from request"""
    # Try to get token from Authorization header
    if not credentials:
        return None
    
    token = credentials.credentials
    
    # Decode token
    payload = decode_token(token)
    if not payload:
        return None
    
    # Get user from database
    username: str = payload.get("sub")
    if username is None:
        return None
    
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not user.is_active:
        return None
    
    return user


def require_auth(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """Require authentication - raise exception if not authenticated"""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_role(*allowed_roles):
    """Create a dependency that requires specific role(s)"""
    def role_checker(user: User = Depends(require_auth)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join([r.value if hasattr(r, 'value') else str(r) for r in allowed_roles])}"
            )
        return user
    return role_checker

