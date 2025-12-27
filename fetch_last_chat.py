import sys
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from server.models import ChatMessage
from server.config import settings
import json

# Setup DB connection
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_last_chat():
    db = SessionLocal()
    try:
        # Get the most recent message
        last_message = db.query(ChatMessage).order_by(desc(ChatMessage.timestamp)).first()
        
        if not last_message:
            print("No chat history found.")
            return

        print(f"\n=== LAST INTERACTION (ID: {last_message.id}) ===")
        print(f"TIMESTAMP: {last_message.timestamp}")
        print(f"USER QUERY: {last_message.message}")
        print("-" * 50)
        print(f"AI RESPONSE:\n{last_message.response}")
        print("-" * 50)
        
        # Check sources to see if gun statute was found
        try:
            sources = json.loads(last_message.sources)
            print("\n=== SOURCES USED ===")
            for s in sources:
                citation = s.get('citation') or s.get('metadata', {}).get('citation')
                source_name = s.get('source') or s.get('metadata', {}).get('source')
                print(f"- {source_name} ({citation})")
        except:
            print("Could not parse sources.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    get_last_chat()















