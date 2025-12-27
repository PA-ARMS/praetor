"""
Authentication service - JWT tokens, password hashing, user management
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import re
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from server.models import User, UserRole
from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("auth_service")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False


def validate_password_strength(password: str) -> None:
    """
    Validate password meets strength requirements
    
    Raises HTTPException if password doesn't meet requirements
    """
    if len(password) < settings.MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters long"
        )
    
    if settings.REQUIRE_PASSWORD_COMPLEXITY:
        errors = []
        
        if not re.search(r'[A-Z]', password):
            errors.append("uppercase letter")
        if not re.search(r'[a-z]', password):
            errors.append("lowercase letter")
        if not re.search(r'\d', password):
            errors.append("number")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>\[\]\\/_+=~`-]', password):
            errors.append("special character")
        
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password must contain at least one: {', '.join(errors)}"
            )


def get_password_hash(password: str) -> str:
    """Hash a password"""
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user by username and password"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get a user by username"""
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get a user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def create_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    full_name: str,
    role: UserRole,
    supervising_attorney_id: Optional[int] = None
) -> User:
    """Create a new user"""
    # Validate password strength
    validate_password_strength(password)
    
    # Validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    # Validate username (alphanumeric and underscores, 3-50 chars)
    if not re.match(r'^[a-zA-Z0-9_]{3,50}$', username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be 3-50 characters and contain only letters, numbers, and underscores"
        )
    
    # Check if username or email already exists
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate supervising attorney if paralegal
    if role == UserRole.PARALEGAL and supervising_attorney_id:
        attorney = db.query(User).filter(User.id == supervising_attorney_id).first()
        if not attorney:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supervising attorney not found"
            )
        if attorney.role not in [UserRole.ATTORNEY, UserRole.ATTORNEY_PARTNER]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supervising attorney must be an Attorney or Attorney-Partner"
            )
    
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        role=role,
        supervising_attorney_id=supervising_attorney_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def decode_token(token: str) -> Optional[dict]:
    """Decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def can_view_user_chat(current_user: User, target_user_id: int, db: Session) -> bool:
    """Check if current user can view target user's chat history"""
    # Attorney-Partner can view all
    if current_user.role == UserRole.ATTORNEY_PARTNER:
        return True
    
    # Admin can view all (for feedback collection)
    if current_user.role == UserRole.ADMIN:
        return True
    
    # Users can always view their own chats
    if current_user.id == target_user_id:
        return True
    
    # Attorneys can view their own chats and their paralegals' chats
    if current_user.role == UserRole.ATTORNEY:
        target_user = db.query(User).filter(User.id == target_user_id).first()
        if target_user and target_user.supervising_attorney_id == current_user.id:
            return True
    
    return False


def get_accessible_user_ids(current_user: User, db: Session) -> list:
    """Get list of user IDs that current user can access"""
    if current_user.role == UserRole.ATTORNEY_PARTNER:
        # Can access all users
        return [user.id for user in db.query(User).filter(User.is_active == True).all()]
    
    if current_user.role == UserRole.ADMIN:
        # Can access all users
        return [user.id for user in db.query(User).filter(User.is_active == True).all()]
    
    if current_user.role == UserRole.ATTORNEY:
        # Can access self and paralegals
        accessible_ids = [current_user.id]
        paralegals = db.query(User).filter(
            User.supervising_attorney_id == current_user.id,
            User.is_active == True
        ).all()
        accessible_ids.extend([p.id for p in paralegals])
        return accessible_ids
    
    # Paralegals can only access themselves
    return [current_user.id]

