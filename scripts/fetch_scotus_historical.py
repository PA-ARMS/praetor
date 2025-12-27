"""
Fetch Historical SCOTUS Opinions
Uses CourtListener API and other sources to get comprehensive historical coverage.
"""

import json
import os
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import requests
from tqdm import tqdm

OUTPUT_ROOT = Path("data/sources/SCOTUS_OPINIONS")
MANIFEST_ROOT = Path("data/manifests")

# CourtListener API (Free Law Project)
COURTLISTENER_API_BASE = "https://www.courtlistener.com/api/rest/v3"
COURTLISTENER_API_KEY = os.environ.get("COURTLISTENER_API_KEY", "")  # Optional but recommended

# Rate limiting
SLEEP_BETWEEN_REQUESTS = 0.5  # CourtListener allows reasonable rate


def fetch_courtlistener_scotus_bulk() -> List[Dict]:
    """
    Fetch SCOTUS opinions from CourtListener bulk data.
    CourtListener provides bulk ZIP downloads for comprehensive historical data.
    """
    print("Fetching SCOTUS opinions from CourtListener bulk data...")
    print("Note: CourtListener API requires authentication.")
    print("Bulk downloads are available at: https://www.courtlistener.com/api/bulk-data/")
    print()
    print("For now, we'll focus on:")
    print("  1. Recent opinions from SCOTUS.gov (already fetching)")
    print("  2. GovInfo bulk data (1937-1975)")
    print("  3. Library of Congress digitized United States Reports")
    print()
    return []


def fetch_courtlistener_scotus_opinions(start_date: Optional[str] = None, 
                                        end_date: Optional[str] = None,
                                        limit: int = 10000) -> List[Dict]:
    """
    Fetch SCOTUS opinions from CourtListener API.
    
    CourtListener has comprehensive SCOTUS coverage going back to the 1700s.
    """
    opinions = []
    
    print("Fetching SCOTUS opinions from CourtListener API...")
    print("(This is the most comprehensive source for historical opinions)")
    print()
    
    # CourtListener endpoint for SCOTUS opinions
    # Use the search endpoint with proper filters
    url = f"{COURTLISTENER_API_BASE}/search/"
    
    params = {
        "q": "court:scotus",  # Search for SCOTUS opinions
        "type": "o",  # Opinions only
        "order_by": "dateFiled asc",  # Oldest first
        "page_size": 100,  # Max per page
    }
    
    if start_date:
        params["filed_after"] = start_date
    if end_date:
        params["filed_before"] = end_date
    
    if COURTLISTENER_API_KEY:
        headers = {"Authorization": f"Token {COURTLISTENER_API_KEY}"}
    else:
        headers = {}
        print("  Note: No API key provided. Using public access (may have rate limits)")
        print()
    
    page = 1
    total_fetched = 0
    
    with tqdm(desc="Fetching from CourtListener", unit="opinion") as pbar:
        while total_fetched < limit:
            params["page"] = page
            
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=30)
                
                if resp.status_code == 429:
                    print("  Rate limited. Waiting 60 seconds...")
                    time.sleep(60)
                    continue
                
                if resp.status_code != 200:
                    print(f"  Error: HTTP {resp.status_code}")
                    print(f"  Response: {resp.text[:200]}")
                    break
                
                data = resp.json()
                results = data.get("results", [])
                
                if not results:
                    break
                
                for result in results:
                    # Extract opinion data
                    opinion = {
                        "url": result.get("absolute_url", ""),
                        "api_url": result.get("resource_uri", ""),
                        "docket": result.get("docket_number", ""),
                        "name": result.get("case_name", ""),
                        "date": result.get("date_filed", ""),
                        "citation": result.get("citation", ""),
                        "justice": result.get("author_str", ""),
                        "type": "courtlistener_api",
                        "pdf_url": result.get("pdf", ""),
                        "html_url": result.get("html", ""),
                        "courtlistener_id": result.get("id", ""),
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
                print(f"  Error fetching page {page}: {e}")
                break
    
    print(f"  Fetched {len(opinions)} opinions from CourtListener")
    return opinions


def download_opinion_from_courtlistener(opinion: Dict, out_dir: Path) -> Optional[Dict]:
    """
    Download opinion PDF or HTML from CourtListener.
    """
    pdf_url = opinion.get("pdf_url", "")
    html_url = opinion.get("html_url", "")
    
    # Prefer PDF, fall back to HTML
    download_url = pdf_url if pdf_url else html_url
    if not download_url:
        return None
    
    # Create filename
    cl_id = opinion.get("courtlistener_id", "")
    docket = opinion.get("docket", "").replace("/", "_").replace(" ", "_")
    filename = f"courtlistener_{cl_id}_{docket}.pdf" if pdf_url else f"courtlistener_{cl_id}_{docket}.html"
    file_path = out_dir / filename
    
    # Skip if exists
    if file_path.exists():
        return {
            "url": download_url,
            "path": str(file_path),
            "content_type": "application/pdf" if pdf_url else "text/html",
            "status": 200,
            "size": file_path.stat().st_size,
            **{k: v for k, v in opinion.items() if k not in ["pdf_url", "html_url"]}
        }
    
    try:
        headers = {}
        if COURTLISTENER_API_KEY:
            headers["Authorization"] = f"Token {COURTLISTENER_API_KEY}"
        
        resp = requests.get(download_url, headers=headers, timeout=30, allow_redirects=True)
        
        if resp.status_code == 200:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(resp.content)
            
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            
            return {
                "url": download_url,
                "path": str(file_path),
                "content_type": resp.headers.get("Content-Type", ""),
                "status": resp.status_code,
                "size": len(resp.content),
                **{k: v for k, v in opinion.items() if k not in ["pdf_url", "html_url"]}
            }
    except Exception as e:
        print(f"    Error downloading {download_url}: {e}")
        return None
    
    return None


def fetch_govinfo_scotus_bulk() -> List[Dict]:
    """
    Fetch SCOTUS decisions from GovInfo bulk data (1937-1975).
    This is official government data.
    """
    print("Fetching historical SCOTUS from GovInfo bulk data (1937-1975)...")
    
    # GovInfo has bulk SCOTUS decisions from 1937-1975
    # This would require downloading bulk ZIP files
    # For now, we'll note this as a source but focus on CourtListener for comprehensive coverage
    
    opinions = []
    # TODO: Implement GovInfo bulk download if needed
    # GovInfo URL: https://www.govinfo.gov/bulkdata
    
    print("  Note: GovInfo bulk data requires ZIP download and processing")
    print("  Focusing on CourtListener API for now (more comprehensive)")
    
    return opinions


def main():
    """Main function to fetch historical SCOTUS opinions."""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("HISTORICAL SCOTUS OPINION FETCHER")
    print("Fetching comprehensive historical Supreme Court opinions")
    print("=" * 80)
    print()
    
    all_opinions = []
    manifest_items = []
    
    # Fetch from CourtListener (most comprehensive)
    courtlistener_opinions = fetch_courtlistener_scotus_opinions(limit=50000)
    all_opinions.extend(courtlistener_opinions)
    
    print()
    print(f"Total opinions found: {len(all_opinions)}")
    print()
    
    # Download all PDFs/HTMLs
    print("Downloading opinion files...")
    print("-" * 80)
    
    downloaded = 0
    skipped = 0
    errors = 0
    
    with tqdm(total=len(all_opinions), desc="Downloading", unit="file",
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
        for opinion in all_opinions:
            manifest_entry = download_opinion_from_courtlistener(opinion, OUTPUT_ROOT)
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
    print(f"  Downloaded: {downloaded}")
    print(f"  Skipped (already exists): {skipped}")
    print(f"  Errors: {errors}")
    print()
    
    # Save manifest
    manifest_path = MANIFEST_ROOT / "SCOTUS_OPINIONS_HISTORICAL.json"
    manifest_data = {
        "source_id": "SCOTUS_OPINIONS_HISTORICAL",
        "name": "SCOTUS Opinions (Historical)",
        "jurisdiction": "Federal",
        "priority": 1,
        "fetched_at": datetime.now().isoformat(),
        "source": "CourtListener API",
        "total_opinions": len(manifest_items),
        "items": manifest_items
    }
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)
    
    print(f"Manifest saved: {manifest_path}")
    print()
    print("=" * 80)
    print("HISTORICAL SCOTUS FETCH COMPLETE")
    print("=" * 80)
    print()
    print("Next step: Run ingestion script to add opinions to RAG system")
    print()


if __name__ == "__main__":
    main()

