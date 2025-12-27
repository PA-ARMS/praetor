"""Verify Virginia Code coverage and ingest missing statutes."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import asyncio
import re
from server.services.rag_service import rag_service
from bs4 import BeautifulSoup

async def verify_coverage():
    """Check what Virginia Code sections we have vs what we should have."""
    print("=" * 80)
    print("VIRGINIA CODE COVERAGE VERIFICATION")
    print("=" * 80)
    print()
    
    rag_service._ensure_initialized()
    
    # Get all Virginia Code documents from database
    db_docs = rag_service.collection.get(
        where={"source": "Code of Virginia"},
        limit=10000
    )
    
    db_ids = db_docs.get('ids', [])
    db_metas = db_docs.get('metadatas', [])
    
    print(f"Virginia Code documents in database: {len(db_ids)}")
    
    # Extract citations from database
    db_citations = set()
    for meta in db_metas:
        cit = meta.get('citation', '')
        if cit:
            # Extract just the number part (e.g., "18.2-57.2" from "§ 18.2-57.2")
            match = re.search(r'(\d+\.\d+-\d+(?:\.\d+)?)', cit)
            if match:
                db_citations.add(match.group(1))
    
    print(f"Unique Virginia Code citations in database: {len(db_citations)}")
    print()
    
    # Check source files
    va_code_dir = Path("data/sources/VA_CODE")
    if not va_code_dir.exists():
        print(f"ERROR: VA_CODE directory not found at {va_code_dir}")
        return
    
    html_files = list(va_code_dir.glob("**/*.html"))
    print(f"Virginia Code HTML files in data/sources/VA_CODE: {len(html_files)}")
    print()
    
    # Extract citations from file names and content
    file_citations = set()
    for html_file in html_files[:100]:  # Sample first 100
        try:
            # Try to extract citation from filename
            filename = html_file.name
            # Pattern: section_18_2_57_2.html or 18.2-57.2.html
            cit_match = re.search(r'(\d+[._]\d+[._-]\d+(?:[._]\d+)?)', filename)
            if cit_match:
                cit = cit_match.group(1).replace('_', '.').replace('-', '.')
                file_citations.add(cit)
            
            # Also try to extract from content
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                soup = BeautifulSoup(content, 'lxml')
                text = soup.get_text()
                
                # Look for citation patterns in text
                cit_pattern = r'§\s*(\d+\.\d+-\d+(?:\.\d+)?)'
                matches = re.findall(cit_pattern, text[:5000])  # First 5000 chars
                file_citations.update(matches)
        except Exception as e:
            continue
    
    print(f"Sample citations found in files: {len(file_citations)}")
    print(f"Sample: {sorted(list(file_citations))[:10]}")
    print()
    
    # Compare
    missing_in_db = file_citations - db_citations
    if missing_in_db:
        print(f"⚠️  WARNING: {len(missing_in_db)} citations found in files but NOT in database")
        print(f"Sample missing: {sorted(list(missing_in_db))[:10]}")
    else:
        print("✓ All sampled citations are in database")
    
    print()
    print("=" * 80)
    print("RECOMMENDATION:")
    print("=" * 80)
    if len(db_ids) < 1000:
        print("⚠️  Database appears to have fewer Virginia Code sections than expected.")
        print("   Run: python scripts/fetch_sources.py VA_CODE")
        print("   Then: python scripts/ingest_sources.py")
    else:
        print(f"✓ Database has {len(db_ids)} Virginia Code documents")
        print("   This should cover most statutes, but verify with a test query.")

if __name__ == "__main__":
    asyncio.run(verify_coverage())






