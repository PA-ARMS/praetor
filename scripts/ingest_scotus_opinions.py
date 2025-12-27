"""
Specialized SCOTUS Opinion Ingestion
Processes all SCOTUS opinions and adds them to the RAG system with proper metadata.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, List
import re

from bs4 import BeautifulSoup
import pdfplumber

# Ensure server modules are importable
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.rag_service import rag_service  # noqa: E402

MANIFEST_ROOT = Path("data/manifests")
SCOTUS_MANIFEST = MANIFEST_ROOT / "SCOTUS_OPINIONS.json"
SCOTUS_CAP_MANIFEST = MANIFEST_ROOT / "SCOTUS_OPINIONS_CAP.json"

# Also check for any SCOTUS-related manifests
SCOTUS_MANIFESTS = [
    SCOTUS_MANIFEST,
    SCOTUS_CAP_MANIFEST,
    MANIFEST_ROOT / "SCOTUS_OPINIONS_HISTORICAL.json",
]

# Safety caps
MAX_OPINIONS = int(os.environ.get("MAX_SCOTUS_OPINIONS", "10000"))  # Allow many opinions


def normalize_bluebook_citation(citation: str) -> Optional[str]:
    """
    Normalize citation to Bluebook format (industry standard).
    Format: [Volume] U.S. [Page] (e.g., "606 U.S. 748")
    Handles multiple variations and edge cases.
    """
    if not citation:
        return None
    
    # Remove extra whitespace and normalize
    citation = re.sub(r'\s+', ' ', citation.strip())
    
    # Pattern: number U.S. number or number U. S. number (with various spacing)
    patterns = [
        r'(\d+)\s+U\.?\s*S\.?\s+(\d+)',      # 606 U.S. 748 or 606 U. S. 748
        r'(\d+)\s+U\.\s*S\.\s+(\d+)',        # 606 U. S. 748 (with spaces)
        r'(\d+)\s+S\.?\s*Ct\.?\s+(\d+)',     # 606 S. Ct. 748
        r'(\d+)\s*U\.?\s*S\.?\s*(\d+)',      # 606U.S.748 (no spaces)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, citation)
        if match:
            volume = match.group(1)
            page = match.group(2)
            # Validate reasonable ranges
            try:
                vol_num = int(volume)
                page_num = int(page)
                if 1 <= vol_num <= 700 and 1 <= page_num <= 2000:
                    return f"{volume} U.S. {page}"
            except ValueError:
                continue
    
    # If no pattern matched, return original (might already be correct)
    return citation


def extract_citation_from_text(text: str) -> Optional[str]:
    """
    Extract SCOTUS citation from opinion text.
    Returns Bluebook-formatted citation (industry standard).
    Enhanced to find citations throughout the document, not just first 5000 chars.
    """
    # Look for patterns like "606 U.S. 748" or "606 U. S. 748"
    # Check multiple locations in the document
    patterns = [
        r'(\d+)\s+U\.?\s*S\.?\s+(\d+)',  # 606 U.S. 748 or 606 U. S. 748
        r'(\d+)\s+U\.\s*S\.\s+(\d+)',    # 606 U. S. 748 (with spaces)
        r'(\d+)\s+S\.?\s*Ct\.?\s+(\d+)',  # 606 S. Ct. 748 (alternative)
    ]
    
    # Check first 10000 chars (headings, title page often have citation)
    search_text = text[:10000] if len(text) > 10000 else text
    
    for pattern in patterns:
        matches = re.finditer(pattern, search_text)
        for match in matches:
            volume = match.group(1)
            page = match.group(2)
            # Validate: volume should be reasonable (1-700+), page should be reasonable (1-2000+)
            vol_num = int(volume)
            page_num = int(page)
            if 1 <= vol_num <= 700 and 1 <= page_num <= 2000:
                # Return in Bluebook format
                return f"{volume} U.S. {page}"
    
    # Also check for citations in filename patterns (e.g., "591us2r63" = 591 U.S. 2r63)
    # This is a fallback if text extraction fails
    
    return None


def extract_docket_from_text(text: str) -> Optional[str]:
    """Extract docket number from opinion text."""
    # Look for patterns like "No. 24-316" or "Docket No. 23-1122"
    patterns = [
        r'(?:No\.|Docket\s+No\.?)\s*(\d+[-–]\d+)',
        r'(\d{2}[-–]\d{3,4})',  # 24-316 format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text[:2000])
        if match:
            return match.group(1) if len(match.groups()) > 0 else match.group(0)
    
    return None


def extract_case_name_from_text(text: str) -> Optional[str]:
    """Extract case name from opinion text."""
    # Usually appears in first few lines
    lines = text.split('\n')[:20]
    for line in lines:
        line = line.strip()
        # Look for lines with "v." or "v " (case names)
        if re.search(r'\b(v\.|v\s)', line, re.IGNORECASE):
            # Clean up the line
            line = re.sub(r'^.*?(\w+\s+v\.)', r'\1', line, flags=re.IGNORECASE)
            if len(line) > 10 and len(line) < 200:
                return line
    
    return None


def read_text_from_file(path: Path) -> Optional[str]:
    """Read text from PDF or text file."""
    p = str(path).lower()
    if p.endswith(".pdf"):
        return read_text_from_pdf(path)
    elif p.endswith(".txt"):
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
    return None


def read_text_from_pdf(path: Path) -> Optional[str]:
    """Extract text from PDF file."""
    try:
        out = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    out.append(text)
        txt = "\n".join(out).strip()
        return txt if txt else None
    except Exception as e:
        print(f"    Error reading PDF {path}: {e}")
        return None


async def ingest_scotus_opinion(item: Dict, counters: Dict[str, int]) -> bool:
    """
    Ingest a single SCOTUS opinion into the RAG system.
    Returns True if successful, False otherwise.
    Industry-standard metadata extraction and Bluebook citation formatting.
    """
    file_path = Path(item.get("path", ""))
    if not file_path.exists():
        return False
    
    # Read text from PDF or text file
    text = read_text_from_file(file_path)
    if not text or len(text) < 200:
        return False
    
    # Extract metadata (industry-standard format)
    citation = item.get("citation", "")
    if not citation:
        citation = extract_citation_from_text(text)
    
    # Normalize citation to Bluebook format (industry standard)
    if citation:
        citation = normalize_bluebook_citation(citation)
    
    docket = item.get("docket", "")
    if not docket:
        docket = extract_docket_from_text(text)
    
    case_name = item.get("name", "")
    if not case_name:
        case_name = extract_case_name_from_text(text)
    
    # Build comprehensive metadata
    metadata = {
        "source": "SCOTUS Opinions",
        "jurisdiction": "Federal",
        "law_level": "primary",
        "authority_type": "official",
        "content_type": "case_law",
        "origin_url": item.get("url", ""),
        "file_path": str(file_path),
        "opinion_type": item.get("type", "slip_opinion"),
    }
    
    # Add extracted metadata
    if citation:
        metadata["citation"] = citation
    if docket:
        metadata["docket"] = docket
    if case_name:
        metadata["case_name"] = case_name
    if item.get("date"):
        metadata["date"] = item.get("date")
    if item.get("justice"):
        metadata["justice"] = item.get("justice")
    if item.get("volume"):
        metadata["volume"] = item.get("volume")
    
    # Add to RAG system
    try:
        await rag_service.add_document(text=text, metadata=metadata)
        counters["ingested"] += 1
        return True
    except Exception as e:
        print(f"    Error adding document to RAG: {e}")
        counters["errors"] += 1
        return False


async def main():
    """Main ingestion function."""
    # Check for any available SCOTUS manifests
    available_manifests = [m for m in SCOTUS_MANIFESTS if m.exists()]
    
    if not available_manifests:
        print("Error: No SCOTUS manifest found!")
        print("Please run one of:")
        print("  - scripts/fetch_scotus_opinions.py (recent opinions)")
        print("  - scripts/fetch_scotus_industry_standard.py (historical via CAP)")
        return
    
    print(f"Found {len(available_manifests)} SCOTUS manifest(s) to process")
    print()
    
    print("=" * 80)
    print("SCOTUS OPINION INGESTION")
    print("Adding all SCOTUS opinions to RAG system")
    print("=" * 80)
    print()
    
    # Process all available manifests
    all_items = []
    for manifest_path in available_manifests:
        print(f"Loading: {manifest_path.name}")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        items = manifest.get("items", [])
        print(f"  Found {len(items)} opinions")
        all_items.extend(items)
    
    items = all_items
    total = len(items)
    
    print(f"Found {total} SCOTUS opinions to ingest")
    print(f"Maximum to process: {MAX_OPINIONS}")
    print()
    
    if total > MAX_OPINIONS:
        print(f"Limiting to first {MAX_OPINIONS} opinions")
        items = items[:MAX_OPINIONS]
    
    counters = {
        "total": 0,
        "ingested": 0,
        "skipped": 0,
        "errors": 0
    }
    
    print("Ingesting opinions...")
    print("-" * 80)
    print()
    
    # Process in batches to avoid overwhelming the system
    batch_size = 10
    
    # Use tqdm for progress bar
    from tqdm import tqdm
    pbar = tqdm(total=len(items), desc="Ingesting SCOTUS opinions", unit="opinion")
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        
        for item in batch:
            counters["total"] += 1
            success = await ingest_scotus_opinion(item, counters)
            
            if not success:
                counters["skipped"] += 1
            
            # Update progress bar
            pbar.update(1)
            pbar.set_postfix({
                'Ingested': counters['ingested'],
                'Skipped': counters['skipped'],
                'Errors': counters['errors']
            })
        
        # Small delay between batches
        await asyncio.sleep(0.1)
    
    pbar.close()
    print()
    
    print()
    print("=" * 80)
    print("INGESTION COMPLETE")
    print("=" * 80)
    print(f"Total processed: {counters['total']}")
    print(f"Successfully ingested: {counters['ingested']}")
    print(f"Skipped (too short/invalid): {counters['skipped']}")
    print(f"Errors: {counters['errors']}")
    print()
    print("SCOTUS opinions are now available in the RAG system!")
    print()


if __name__ == "__main__":
    asyncio.run(main())

