"""
Script to create user accounts with default password
Users will be required to change password on first login
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.models import SessionLocal, User, UserRole, init_db
from server.services.auth_service import get_password_hash

# Default password for all new users (must meet complexity requirements)
DEFAULT_PASSWORD = "ChangeMe123!"

# Users to create
USERS_TO_CREATE = [
    {"full_name": "Peyton Akers", "role": UserRole.ATTORNEY_PARTNER},
    {"full_name": "Elizabeth Qi", "role": UserRole.ATTORNEY},
    {"full_name": "Yulia Kovregina", "role": UserRole.ATTORNEY},
    {"full_name": "Meredith Brown", "role": UserRole.ATTORNEY},
    {"full_name": "Jared Pitts", "role": UserRole.ATTORNEY},
    {"full_name": "Kassandra Hamilton", "role": UserRole.PARALEGAL},
    {"full_name": "Scott Bucksbaum", "role": UserRole.ATTORNEY},
    {"full_name": "Aaron Skinne", "role": UserRole.ATTORNEY},
]

def generate_username(full_name: str) -> str:
    """Generate username from full name (firstname.lastname lowercase)"""
    parts = full_name.lower().split()
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    else:
        return parts[0].replace(" ", "")

def generate_email(full_name: str) -> str:
    """Generate email from full name"""
    username = generate_username(full_name)
    return f"{username}@akerslaw.com"

def create_users():
    """Create user accounts with default password"""
    print("="*60)
    print("Creating User Accounts")
    print("="*60)
    print(f"\nDefault password for all users: {DEFAULT_PASSWORD}")
    print("Users will be required to change password on first login.\n")
    
    # Initialize database
    print("Initializing database...")
    init_db()
    print("Database initialized.\n")
    
    db = SessionLocal()
    try:
        created_count = 0
        skipped_count = 0
        
        for user_data in USERS_TO_CREATE:
            full_name = user_data["full_name"]
            role = user_data["role"]
            username = generate_username(full_name)
            email = generate_email(full_name)
            
            # Check if user already exists
            existing = db.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing:
                print(f"[SKIP] User '{full_name}' already exists (username: {existing.username})")
                skipped_count += 1
                continue
            
            # Create user with default password and require password change
            user = User(
                username=username,
                email=email,
                hashed_password=get_password_hash(DEFAULT_PASSWORD),
                full_name=full_name,
                role=role,
                is_active=True,
                must_change_password=True  # Require password change on first login
            )
            
            db.add(user)
            print(f"[OK] Created: {full_name}")
            print(f"      Username: {username}")
            print(f"      Email: {email}")
            print(f"      Role: {role.value}")
            print()
            created_count += 1
        
        db.commit()
        
        print("="*60)
        print("USER CREATION SUMMARY")
        print("="*60)
        print(f"Created: {created_count} users")
        print(f"Skipped: {skipped_count} users (already exist)")
        print()
        print("="*60)
        print("LOGIN CREDENTIALS")
        print("="*60)
        print(f"Default Password: {DEFAULT_PASSWORD}")
        print()
        print("All users must change their password on first login.")
        print("="*60)
        
    except Exception as e:
        db.rollback()
        print(f"\nERROR: Failed to create users: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    create_users()




