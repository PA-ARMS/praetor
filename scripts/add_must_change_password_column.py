"""
Migration script to add must_change_password column to users table
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.models import SessionLocal, engine
from sqlalchemy import text

def add_must_change_password_column():
    """Add must_change_password column to users table if it doesn't exist"""
    print("="*60)
    print("Adding must_change_password column to users table")
    print("="*60)
    
    db = SessionLocal()
    try:
        # Check if column already exists
        with engine.connect() as conn:
            # SQLite specific: Check if column exists
            result = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result]
            
            if 'must_change_password' in columns:
                print("[SKIP] Column 'must_change_password' already exists")
                return
            
            # Add the column
            print("Adding column 'must_change_password'...")
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN must_change_password BOOLEAN DEFAULT 0
            """))
            conn.commit()
            print("[OK] Column 'must_change_password' added successfully")
            
    except Exception as e:
        print(f"\nERROR: Failed to add column: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    add_must_change_password_column()





