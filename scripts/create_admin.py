"""
Script to create the first admin user
Run this after starting the server for the first time
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.models import SessionLocal, User, UserRole
from server.services.auth_service import get_password_hash

def create_admin():
    db = SessionLocal()
    try:
        # Check if admin already exists
        existing_admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if existing_admin:
            print(f"Admin user already exists: {existing_admin.username}")
            return
        
        # Create default admin
        username = input("Enter admin username (default: admin): ").strip() or "admin"
        email = input("Enter admin email: ").strip()
        if not email:
            print("Email is required!")
            return
        
        password = input("Enter admin password: ").strip()
        if not password:
            print("Password is required!")
            return
        
        full_name = input("Enter admin full name (default: System Administrator): ").strip() or "System Administrator"
        
        admin = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role=UserRole.ADMIN,
            is_active=True
        )
        
        db.add(admin)
        db.commit()
        print(f"\n✓ Admin user created successfully!")
        print(f"  Username: {username}")
        print(f"  Email: {email}")
        print(f"  Full Name: {full_name}")
        print(f"\nYou can now login with these credentials.")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()

