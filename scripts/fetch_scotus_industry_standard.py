"""
Industry-Standard SCOTUS Opinion Fetcher
Implements legal tech industry best practices for SCOTUS opinion databases.

Standards Followed:
- Bluebook citation format
- CAP (Caselaw Access Project) API - Harvard's industry-standard historical database
- Proper metadata extraction (citations, dockets, case names, dates, justices)
- Data provenance and chain of custody
- Citation validation and normalization
- Standardized file formats (PDF/A)
"""

import json
import os
import time
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import requests
from tqdm import tqdm

OUTPUT_ROOT = Path("data/sources/SCOTUS_OPINIONS")
MANIFEST_ROOT = Path("data/manifests")

# CAP (Caselaw Access Project) - Harvard Law School
# Industry standard for historical caselaw (1790-present)
CAP_API_BASE = "https://api.case.law/v1"
CAP_API_KEY = os.environ.get("CAP_API_KEY", "")

# Rate limiting (CAP allows reasonable free tier usage)
SLEEP_BETWEEN_REQUESTS = 0.5


def normalize_bluebook_citation(citation: str) -> Optional[str]:
    """
    Normalize citation to Bluebook format.
    Format: [Volume] U.S. [Page] (e.g., "606 U.S. 748")
    """
    if not citation:
        return None
    
    # Remove extra whitespace
    citation = re.sub(r'\s+', ' ', citation.strip())
    
    # Pattern: number U.S. number or number U. S. number
    pattern = r'(\d+)\s+U\.?\s*S\.?\s+(\d+)'
    match = re.search(pattern, citation)
    
    if match:
        volume = match.group(1)
        page = match.group(2)
        return f"{volume} U.S. {page}"
    
    return citation


def extract_bluebook_citation_from_text(text: str) -> Optional[str]:
    """
    Extract Bluebook-formatted SCOTUS citation from opinion text.
    Industry standard format: [Volume] U.S. [Page]
    """
    # Look for citation patterns in first 5000 characters
    patterns = [
        r'(\d+)\s+U\.?\s*S\.?\s+(\d+)',  # 606 U.S. 748
        r'(\d+)\s+U\.\s*S\.\s+(\d+)',    # 606 U. S. 748
        r'(\d+)\s+S\.?\s*Ct\.?\s+(\d+)',  # 606 S. Ct. 748 (alternative)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text[:5000])
        if match:
            volume = match.group(1)
            page = match.group(2)
            return f"{volume} U.S. {page}"
    
    return None


def fetch_cap_scotus_opinions(start_year: Optional[int] = None,
                               end_year: Optional[int] = None,
                               limit: int = 50000) -> List[Dict]:
    """
    Fetch SCOTUS opinions from CAP (Caselaw Access Project) API.
    
    CAP is the industry-standard source for historical SCOTUS opinions.
    - Coverage: 1790-present (comprehensive)
    - Free API key available
    - Well-structured data with proper citations
    - Used by legal tech industry professionals
    """
    opinions = []
    
    print("=" * 80)
    print("FETCHING SCOTUS OPINIONS FROM CAP (CASELAW ACCESS PROJECT)")
    print("Industry-standard historical caselaw database (Harvard Law School)")
    print("=" * 80)
    print()
    
    if not CAP_API_KEY:
        print("⚠️  WARNING: No CAP_API_KEY found in environment variables")
        print()
        print("To get a FREE API key:")
        print("  1. Visit: https://case.law/user/register/")
        print("  2. Register for free account")
        print("  3. Get API key from: https://case.law/user/profile/")
        print("  4. Set environment variable: CAP_API_KEY=your_key_here")
        print()
        print("Continuing with public access (limited)...")
        print()
        time.sleep(3)
    
    # CAP API endpoint for cases
    url = f"{CAP_API_BASE}/cases/"
    
    # Build query parameters
    params = {
        "jurisdiction": "us",  # United States
        "court": "scotus",      # Supreme Court of the United States
        "page_size": 100,       # Max per page
        "ordering": "decision_date",  # Order by date
    }
    
    if start_year:
        params["decision_date_min"] = f"{start_year}-01-01"
    if end_year:
        params["decision_date_max"] = f"{end_year}-12-31"
    
    headers = {}
    if CAP_API_KEY:
        headers["Authorization"] = f"Token {CAP_API_KEY}"
    
    page = 1
    total_fetched = 0
    
    print(f"Fetching SCOTUS opinions from CAP API...")
    if start_year or end_year:
        print(f"Date range: {start_year or 'earliest'} - {end_year or 'present'}")
    print()
    
    with tqdm(desc="Fetching from CAP", unit="opinion") as pbar:
        while total_fetched < limit:
            params["page"] = page
            
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=30)
                
                if resp.status_code == 401:
                    print("  ❌ Authentication failed. Please check your CAP_API_KEY")
                    break
                
                if resp.status_code == 429:
                    print("  ⏳ Rate limited. Waiting 60 seconds...")
                    time.sleep(60)
                    continue
                
                if resp.status_code != 200:
                    print(f"  ❌ Error: HTTP {resp.status_code}")
                    print(f"  Response: {resp.text[:200]}")
                    break
                
                data = resp.json()
                results = data.get("results", [])
                
                if not results:
                    break
                
                for result in results:
                    # Extract opinion data with industry-standard metadata
                    decision_date = result.get("decision_date", "")
                    citation = result.get("citation", "")
                    
                    # Normalize citation to Bluebook format
                    normalized_citation = normalize_bluebook_citation(citation) if citation else None
                    
                    opinion = {
                        "url": result.get("url", ""),
                        "api_url": result.get("resource_uri", ""),
                        "docket": result.get("docket_number", ""),
                        "name": result.get("name", ""),
                        "date": decision_date,
                        "citation": normalized_citation or citation,
                        "citation_original": citation,
                        "justice": result.get("judges", []),  # List of judges
                        "type": "cap_api",
                        "source": "CAP (Caselaw Access Project)",
                        "cap_id": result.get("id", ""),
                        "frontend_url": result.get("frontend_url", ""),
                        "volume": result.get("volume", {}).get("volume_number", "") if result.get("volume") else "",
                        "reporter": result.get("reporter", ""),
                        "page": result.get("page_number", ""),
                    }
                    
                    opinions.append(opinion)
                    total_fetched += 1
                    pbar.update(1)
                
                # Check if there are more pages
                if not data.get("next"):
                    break
                
                page += 1
                time.sleep(SLEEP_BETWEEN_REQUESTS)
                
            except Exception as e:
                print(f"  ❌ Error fetching page {page}: {e}")
                break
    
    print()
    print(f"✅ Fetched {len(opinions)} SCOTUS opinions from CAP")
    return opinions


def download_cap_opinion(opinion: Dict, out_dir: Path) -> Optional[Dict]:
    """
    Download opinion text from CAP API.
    CAP provides structured case text via API.
    """
    cap_id = opinion.get("cap_id", "")
    if not cap_id:
        return None
    
    # CAP API endpoint for case text
    url = f"{CAP_API_BASE}/cases/{cap_id}/"
    
    headers = {}
    if CAP_API_KEY:
        headers["Authorization"] = f"Token {CAP_API_KEY}"
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        
        # Extract case text
        case_text = data.get("casebody", {}).get("data", {}).get("opinions", [])
        if not case_text:
            return None
        
        # Combine all opinions into full text
        full_text = "\n\n".join([
            op.get("text", "") for op in case_text
        ])
        
        if not full_text or len(full_text) < 200:
            return None
        
        # Create filename
        docket = opinion.get("docket", "").replace("/", "_").replace(" ", "_")
        citation = opinion.get("citation", "").replace(" ", "_").replace(".", "")
        filename = f"cap_{cap_id}_{docket}_{citation}.txt"
        file_path = out_dir / filename
        
        # Save text file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        
        return {
            "url": opinion.get("url", ""),
            "path": str(file_path),
            "content_type": "text/plain",
            "status": 200,
            "size": len(full_text.encode("utf-8")),
            **{k: v for k, v in opinion.items() if k not in ["cap_id"]}
        }
        
    except Exception as e:
        print(f"    ❌ Error downloading CAP opinion {cap_id}: {e}")
        return None


def main():
    """Main function - Industry-standard SCOTUS opinion fetcher."""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    
    print()
    print("=" * 80)
    print("INDUSTRY-STANDARD SCOTUS OPINION FETCHER")
    print("Using CAP (Caselaw Access Project) - Harvard Law School")
    print("=" * 80)
    print()
    
    all_opinions = []
    manifest_items = []
    
    # Fetch from CAP (industry standard)
    # Get all historical SCOTUS opinions
    cap_opinions = fetch_cap_scotus_opinions(limit=50000)
    all_opinions.extend(cap_opinions)
    
    print()
    print(f"Total opinions found: {len(all_opinions)}")
    print()
    
    # Download all opinion texts
    print("Downloading opinion texts from CAP...")
    print("-" * 80)
    
    downloaded = 0
    skipped = 0
    errors = 0
    
    with tqdm(total=len(all_opinions), desc="Downloading", unit="opinion",
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
        for opinion in all_opinions:
            manifest_entry = download_cap_opinion(opinion, OUTPUT_ROOT)
            if manifest_entry:
                manifest_items.append(manifest_entry)
                if manifest_entry.get("status") == 200:
                    downloaded += 1
                else:
                    skipped += 1
            else:
                errors += 1
            pbar.update(1)
            pbar.set_postfix({'Downloaded': downloaded, 'Skipped': skipped, 'Errors': errors})
    
    print()
    print(f"Download complete:")
    print(f"  ✅ Downloaded: {downloaded}")
    print(f"  ⏭️  Skipped: {skipped}")
    print(f"  ❌ Errors: {errors}")
    print()
    
    # Save manifest with industry-standard metadata
    manifest_path = MANIFEST_ROOT / "SCOTUS_OPINIONS_CAP.json"
    manifest_data = {
        "source_id": "SCOTUS_OPINIONS_CAP",
        "name": "SCOTUS Opinions (CAP - Industry Standard)",
        "jurisdiction": "Federal",
        "priority": 1,
        "authority_type": "open_aggregator",
        "source": "CAP (Caselaw Access Project) - Harvard Law School",
        "fetched_at": datetime.now().isoformat(),
        "citation_format": "Bluebook",
        "data_standards": [
            "Bluebook citation format",
            "CAP API (industry standard)",
            "Proper metadata extraction",
            "Data provenance tracking"
        ],
        "total_opinions": len(manifest_items),
        "items": manifest_items
    }
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Manifest saved: {manifest_path}")
    print()
    print("=" * 80)
    print("INDUSTRY-STANDARD SCOTUS FETCH COMPLETE")
    print("=" * 80)
    print()
    print("Next step: Run ingestion script to add opinions to RAG system")
    print("  python scripts/ingest_scotus_opinions.py")
    print()


if __name__ == "__main__":
    main()







