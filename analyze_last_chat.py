import asyncio
import sys
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from server.models import ChatMessage, Base, User
from server.config import settings
from server.services.ollama_service import ollama_service

# Setup DB connection
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def analyze_last_chat():
    print("Connecting to database...")
    db = SessionLocal()
    try:
        # Get the most recent message
        last_message = db.query(ChatMessage).order_by(desc(ChatMessage.timestamp)).first()
        
        if not last_message:
            print("No chat history found.")
            return

        print(f"\n=== LAST INTERACTION (ID: {last_message.id}) ===")
        print(f"User Query: {last_message.message}")
        print(f"Response Length: {len(last_message.response)} chars")
        print("-" * 50)
        
        # Analyze it with Qwen
        analysis_prompt = f"""
        Analyze the quality of this legal AI response.
        
        USER QUESTION: {last_message.message}
        
        AI RESPONSE: {last_message.response}
        
        Analyze:
        1. Did the AI answer the specific legal question?
        2. Was the response legally accurate based on Virginia law (if known)?
        3. Was the tone appropriate?
        4. Give a brief rating (1-10).
        """
        
        print("\nRunning analysis with Qwen 2.5 14B...")
        analysis = await ollama_service.generate(analysis_prompt, max_tokens=1000)
        print("\n=== ANALYSIS RESULT ===")
        print(analysis)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(analyze_last_chat())














