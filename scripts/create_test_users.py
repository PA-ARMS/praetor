"""
Script to create test users for AK Legal Vault
Creates users with all roles for testing
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.models import SessionLocal, User, UserRole, init_db
import bcrypt

def create_test_users():
    # Initialize database first
    print("Initializing database...")
    init_db()
    print("Database initialized.\n")
    
    db = SessionLocal()
    try:
        # Check if users already exist
        existing_users = db.query(User).count()
        if existing_users > 0:
            print("Users already exist in the database.")
            response = input("Do you want to create additional test users? (y/n): ").strip().lower()
            if response != 'y':
                print("Cancelled.")
                return
        
        users_to_create = [
            {
                "username": "admin",
                "email": "admin@akerslaw.com",
                "password": "Admin123!",
                "full_name": "System Administrator",
                "role": UserRole.ADMIN
            },
            {
                "username": "partner",
                "email": "partner@akerslaw.com",
                "password": "Partner123!",
                "full_name": "John Partner",
                "role": UserRole.ATTORNEY_PARTNER
            },
            {
                "username": "attorney",
                "email": "attorney@akerslaw.com",
                "password": "Attorney123!",
                "full_name": "Jane Attorney",
                "role": UserRole.ATTORNEY
            },
            {
                "username": "paralegal",
                "email": "paralegal@akerslaw.com",
                "password": "Paralegal123!",
                "full_name": "Sarah Paralegal",
                "role": UserRole.PARALEGAL,
                "supervising_attorney_id": None  # Will be set after attorney is created
            }
        ]
        
        created_users = {}
        
        for user_data in users_to_create:
            # Check if user already exists
            existing = db.query(User).filter(User.username == user_data["username"]).first()
            if existing:
                print(f"[SKIP] User '{user_data['username']}' already exists. Skipping...")
                if user_data["role"] == UserRole.ATTORNEY:
                    created_users["attorney"] = existing
                continue
            
            # Remove supervising_attorney_id for now (will set after)
            supervising_id = user_data.pop("supervising_attorney_id", None)
            
            # Hash password using bcrypt directly
            password_bytes = user_data["password"].encode('utf-8')
            hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
            
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=hashed.decode('utf-8'),
                full_name=user_data["full_name"],
                role=user_data["role"],
                is_active=True
            )
            
            db.add(user)
            db.flush()  # Flush to get the ID
            
            # Store attorney for paralegal assignment
            if user_data["role"] == UserRole.ATTORNEY:
                created_users["attorney"] = user
            
            print(f"[OK] Created user: {user_data['username']} ({user_data['role'].value})")
        
        # Now assign paralegal to attorney if both exist
        paralegal = db.query(User).filter(User.username == "paralegal").first()
        attorney = created_users.get("attorney") or db.query(User).filter(User.role == UserRole.ATTORNEY).first()
        
        if paralegal and attorney:
            paralegal.supervising_attorney_id = attorney.id
            print(f"[OK] Assigned paralegal to attorney: {attorney.full_name}")
        
        db.commit()
        
        print("\n" + "="*60)
        print("TEST USER CREDENTIALS CREATED")
        print("="*60)
        print("\nAdmin:")
        print("  Username: admin")
        print("  Password: Admin123!")
        print("  Role: Admin (Full access to all chats)")
        print("\nAttorney-Partner:")
        print("  Username: partner")
        print("  Password: Partner123!")
        print("  Role: Attorney-Partner (Full access to all chats)")
        print("\nAttorney:")
        print("  Username: attorney")
        print("  Password: Attorney123!")
        print("  Role: Attorney (Own chats + paralegal's chats)")
        print("\nParalegal:")
        print("  Username: paralegal")
        print("  Password: Paralegal123!")
        print("  Role: Paralegal (Own chats only)")
        print(f"  Assigned to: {attorney.full_name if attorney else 'N/A'}")
        print("\n" + "="*60)
        print("You can now login with any of these credentials.")
        print("="*60)
        
    except Exception as e:
        db.rollback()
        print(f"\nERROR: Error creating users: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_users()

