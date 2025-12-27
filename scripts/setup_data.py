"""
Data setup script - Initialize data directories and download legal corpus
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.config import settings
from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service


async def setup_directories():
    """Create necessary directories"""
    directories = [
        settings.DATA_DIR,
        settings.FORMS_DIR,
        settings.TEMPLATES_DIR,
        settings.CORPUS_DIR,
        settings.CHROMA_DB_PATH
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")


async def initialize_corpus():
    """Initialize RAG corpus with sample data"""
    print("Initializing RAG corpus...")
    
    # Sample Virginia Code entry
    sample_va_code = """
    Code of Virginia, Title 8.01 - Civil Remedies and Procedure
    
    § 8.01-1. Definitions.
    As used in this title, unless the context requires a different meaning:
    "Action" means any civil action, suit, or proceeding at law or in equity.
    "Court" means any court of record.
    
    This statute governs civil procedure in Virginia courts.
    """
    
    await rag_service.add_document(
        text=sample_va_code,
        metadata={
            "source": "Code of Virginia",
            "jurisdiction": "Virginia",
            "document_type": "STATUTE",
            "citation": "Va. Code Ann. § 8.01-1"
        },
        doc_id="va_code_8_01_1"
    )
    
    print("Sample document added to corpus")
    print(f"Corpus stats: {rag_service.get_collection_stats()}")


async def main():
    """Main setup function"""
    print("Setting up Virginia Legal AI data structure...")
    
    await setup_directories()
    await initialize_corpus()
    
    print("\nSetup complete!")
    print("\nNext steps:")
    print("1. Add Virginia and Federal law documents to data/corpus/")
    print("2. Add form templates to data/templates/")
    print("3. Configure server/.env with your settings")
    print("4. Start the server: python server/main.py")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

