import sys
from server.models import SessionLocal, User, UserRole
from server.services.auth_service import get_password_hash

def setup_test_user():
    db = SessionLocal()
    try:
        # Check if user exists
        user = db.query(User).filter(User.username == "paralegal1").first()
        if user:
            print(f"User 'paralegal1' found. Updating password...")
            user.hashed_password = get_password_hash("password123")
            db.commit()
            print("Password updated successfully.")
        else:
            print("Creating 'paralegal1' user...")
            user = User(
                username="paralegal1",
                email="paralegal1@example.com",
                hashed_password=get_password_hash("password123"),
                full_name="Test Paralegal",
                role=UserRole.PARALEGAL,
                is_active=True
            )
            db.add(user)
            db.commit()
            print("User created successfully.")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    setup_test_user()











