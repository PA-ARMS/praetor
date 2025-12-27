"""Ingest ALL Virginia Code statutes from downloaded files."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import asyncio
import re
from bs4 import BeautifulSoup
from server.services.rag_service import rag_service
from tqdm import tqdm

async def ingest_all_va_code():
    """Ingest all Virginia Code HTML files into the RAG database."""
    print("=" * 80)
    print("INGESTING ALL VIRGINIA CODE STATUTES")
    print("=" * 80)
    print()
    
    rag_service._ensure_initialized()
    
    va_code_dir = Path("data/sources/VA_CODE")
    if not va_code_dir.exists():
        print(f"ERROR: VA_CODE directory not found at {va_code_dir}")
        return
    
    html_files = list(va_code_dir.glob("**/*.html"))
    print(f"Found {len(html_files)} Virginia Code HTML files")
    print()
    
    ingested = 0
    skipped = 0
    errors = 0
    
    for html_file in tqdm(html_files, desc="Ingesting"):
        try:
            # Read and parse HTML
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                html = f.read()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Remove nav/script/style
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.extract()
            
            text = soup.get_text("\n", strip=True)
            
            # Skip if too short (likely navigation page)
            if len(text) < 200:
                skipped += 1
                continue
            
            # Extract citation from text
            citation = None
            # Look for patterns like "§ 18.2-57.2" or "Section 18.2-57.2"
            cit_patterns = [
                r'§\s*(\d+\.\d+-\d+(?:\.\d+)?)',
                r'Section\s+(\d+\.\d+-\d+(?:\.\d+)?)',
                r'Code\s+of\s+Virginia\s+§\s*(\d+\.\d+-\d+(?:\.\d+)?)',
            ]
            
            for pattern in cit_patterns:
                match = re.search(pattern, text[:2000], re.IGNORECASE)  # Check first 2000 chars
                if match:
                    citation = f"§ {match.group(1)}"
                    break
            
            # Also try filename
            if not citation:
                filename = html_file.name
                cit_match = re.search(r'(\d+[._]\d+[._-]\d+(?:[._]\d+)?)', filename)
                if cit_match:
                    cit = cit_match.group(1).replace('_', '.').replace('-', '.')
                    citation = f"§ {cit}"
            
            # Extract title if available
            title_match = re.search(r'Title\s+(\d+(?:\.\d+)?)', text[:1000], re.IGNORECASE)
            title = f"Title {title_match.group(1)}" if title_match else None
            
            # Create metadata
            metadata = {
                "source": "Code of Virginia",
                "jurisdiction": "Virginia",
                "content_type": "statute",
                "law_level": "primary",
                "authority_type": "official",
                "url": f"https://law.lis.virginia.gov/vacode/{html_file.name}",
            }
            
            if citation:
                metadata["citation"] = citation
            if title:
                metadata["title"] = title
            
            # Create doc_id from citation or filename
            doc_id = citation.replace("§ ", "").replace(".", "_") if citation else html_file.stem
            
            # Check if already exists
            try:
                existing = rag_service.collection.get(
                    where={"citation": citation} if citation else {"source": "Code of Virginia"},
                    limit=1
                )
                if existing['ids']:
                    skipped += 1
                    continue
            except:
                pass
            
            # Add to database
            try:
                await rag_service.add_document(
                    text=text,
                    metadata=metadata,
                    doc_id=f"va_code_{doc_id}"
                )
                ingested += 1
            except Exception as e:
                errors += 1
                if errors <= 5:  # Only print first 5 errors
                    print(f"  Error ingesting {html_file.name}: {e}")
        
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error processing {html_file.name}: {e}")
    
    print()
    print("=" * 80)
    print("INGESTION COMPLETE")
    print("=" * 80)
    print(f"  Ingested: {ingested}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")
    print()
    
    # Verify final count
    db_docs = rag_service.collection.get(
        where={"source": "Code of Virginia"},
        limit=10000
    )
    print(f"Total Virginia Code documents in database: {len(db_docs.get('ids', []))}")
    print()
    print("✓ All Virginia Code statutes should now be in the database!")

if __name__ == "__main__":
    asyncio.run(ingest_all_va_code())






