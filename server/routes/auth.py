"""
Authentication routes - Login, logout, user management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import timedelta, datetime
import json
import secrets

from server.models import get_db, User, UserRole, ChatMessage, PasswordResetToken
from server.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_user,
    get_user_by_id,
    get_accessible_user_ids,
    can_view_user_chat
)
from server.middleware.auth_middleware import get_current_user, require_auth
from server.utils.logger import setup_logger

router = APIRouter()
security = HTTPBearer()
logger = setup_logger("auth")


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    must_change_password: bool = False  # Flag indicating if password change is required


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    role: UserRole
    supervising_attorney_id: Optional[int] = None


class SignupRequest(BaseModel):
    """Public signup - only allowed when no users exist (first user becomes admin)."""
    username: str
    email: EmailStr
    password: str
    full_name: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    supervising_attorney_id: Optional[int] = None
    is_active: bool
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserResponse]


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """Login endpoint"""
    user = authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    from server.config import settings
    access_token_expires = timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value},
        expires_delta=access_token_expires
    )
    # Audit log
    try:
        from server.models import AuditLog
        from fastapi import Request
        log = AuditLog(
            user_id=user.id if user else None,
            action="login_success",
            path="/api/auth/login",
            method="POST",
            status=200
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to create audit log for login: {e}")

    return LoginResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "supervising_attorney_id": user.supervising_attorney_id
        },
        must_change_password=getattr(user, 'must_change_password', False)
    )


@router.post("/signup", response_model=UserResponse)
async def signup(
    request: SignupRequest,
    db: Session = Depends(get_db)
):
    """
    Create the first user account (no auth required).
    Only succeeds when there are no users yet; the first user is created as Admin.
    After that, new accounts must be created by an Admin or Attorney-Partner.
    """
    user_count = db.query(User).count()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account creation is by invitation only. Please contact your administrator."
        )
    try:
        user = create_user(
            db=db,
            username=request.username,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=UserRole.ADMIN,
            supervising_attorney_id=None
        )
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            supervising_attorney_id=user.supervising_attorney_id,
            is_active=user.is_active
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during signup: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating account. Please try again or contact support."
        )


@router.post("/register", response_model=UserResponse)
async def register(
    request: RegisterRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register a new user (requires authentication unless creating first admin)"""
    # Check if this is the first user (allow creation without auth)
    user_count = db.query(User).count()
    if user_count > 0:
        # Require authentication for subsequent registrations
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to create users"
            )
        # Only Admin and Attorney-Partner can create users
        if current_user.role not in [UserRole.ADMIN, UserRole.ATTORNEY_PARTNER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin and Attorney-Partner can create users"
            )
    
    try:
        user = create_user(
            db=db,
            username=request.username,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=request.role,
            supervising_attorney_id=request.supervising_attorney_id
        )
        
        # Audit log for user creation
        try:
            from server.models import AuditLog
            from fastapi import Request
            log = AuditLog(
                user_id=current_user.id if current_user else None,
                action="user_created",
                path="/api/auth/register",
                method="POST",
                status=200,
                details=json.dumps({"created_user_id": user.id, "created_username": user.username, "role": user.role.value})
            )
            db.add(log)
            db.commit()
        except Exception as e:
            db.rollback()
            # Don't fail registration if audit log fails
            logger.warning(f"Failed to create audit log for user registration: {e}")
        
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            supervising_attorney_id=user.supervising_attorney_id,
            is_active=user.is_active
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user. Please try again or contact support."
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(require_auth)
):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        supervising_attorney_id=current_user.supervising_attorney_id,
        is_active=current_user.is_active
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """List all users (Admin and Attorney-Partner only)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.ATTORNEY_PARTNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin and Attorney-Partner can list all users"
        )
    
    # Include all users (active and inactive) for admin management
    users = db.query(User).all()
    return UserListResponse(
        users=[
            UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                role=user.role.value,
                supervising_attorney_id=user.supervising_attorney_id,
                is_active=user.is_active
            )
            for user in users
        ]
    )


class UpdateUserRequest(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    supervising_attorney_id: Optional[int] = None


class PasswordResetRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Update user (Admin and Attorney-Partner only)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.ATTORNEY_PARTNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin and Attorney-Partner can update users"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deactivation
    if user_id == current_user.id and request.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    # Update fields
    if request.is_active is not None:
        user.is_active = request.is_active
    if request.role is not None:
        user.role = request.role
    if request.supervising_attorney_id is not None:
        user.supervising_attorney_id = request.supervising_attorney_id
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        supervising_attorney_id=user.supervising_attorney_id,
        is_active=user.is_active
    )


@router.patch("/users/{user_id}/password")
async def reset_user_password(
    user_id: int,
    request: PasswordResetRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Reset user password (Admin and Attorney-Partner only)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.ATTORNEY_PARTNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin and Attorney-Partner can reset passwords"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Validate password
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    # Hash and update password
    from server.services.auth_service import get_password_hash
    user.hashed_password = get_password_hash(request.password)
    db.commit()
    
    return {"message": "Password reset successfully"}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Change user's own password"""
    from server.services.auth_service import verify_password, get_password_hash, validate_password_strength
    
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Validate new password strength
    try:
        validate_password_strength(request.new_password)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password validation failed: {str(e)}"
        )
    
    # Check that new password is different from current
    if verify_password(request.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    # Update password and clear must_change_password flag
    current_user.hashed_password = get_password_hash(request.new_password)
    current_user.must_change_password = False
    db.commit()
    
    return {"message": "Password changed successfully"}


@router.get("/users/accessible", response_model=UserListResponse)
async def list_accessible_users(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """List users accessible by current user based on role"""
    accessible_ids = get_accessible_user_ids(current_user, db)
    users = db.query(User).filter(
        User.id.in_(accessible_ids),
        User.is_active == True
    ).all()

    return UserListResponse(
        users=[
            UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                role=user.role.value,
                supervising_attorney_id=user.supervising_attorney_id,
                is_active=user.is_active
            )
            for user in users
        ]
    )


class RequestPasswordResetRequest(BaseModel):
    username_or_email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/request-password-reset")
async def request_password_reset(
    request: RequestPasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Create a password reset token for the user.
    No email is sent; the token is returned in the response (for dev / admin handoff).
    In production you could send the token via email instead.
    """
    user = db.query(User).filter(
        (User.username == request.username_or_email) | (User.email == request.username_or_email)
    ).first()
    if not user or not user.is_active:
        # Do not reveal whether user exists
        return {"message": "If an account exists with that username or email, a reset link would be sent."}

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    db.add(PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at))
    db.commit()

    reset_url = f"/reset-password?token={token}"
    return {
        "message": "Password reset token created. Use it within 1 hour.",
        "reset_token": token,
        "reset_url": reset_url
    }


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password using a token from request-password-reset."""
    from server.services.auth_service import get_password_hash, validate_password_strength

    row = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == request.token,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    try:
        validate_password_strength(request.new_password)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

    user.hashed_password = get_password_hash(request.new_password)
    row.used_at = datetime.utcnow()
    db.commit()

    return {"message": "Password reset successfully. You can now sign in."}


@router.get("/export-my-data")
async def export_my_data(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Export current user's data (profile + chat history) for compliance."""
    messages = db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).order_by(ChatMessage.timestamp.asc()).all()
    return {
        "exported_at": datetime.utcnow().isoformat(),
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role.value
        },
        "chat_history": [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "subject": m.subject,
                "message": m.message,
                "response": m.response[:5000] if m.response else None,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None
            }
            for m in messages
        ]
    }

