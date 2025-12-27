"""
Download case law from CourtListener API and store locally
This script downloads cases for the scenario database
"""
import requests
import json
from pathlib import Path
import time
import os
from typing import Optional

# Configuration
API_KEY = os.environ.get("COURTLISTENER_API_KEY", "")  # Set in environment or .env
BASE_URL = "https://www.courtlistener.com/api/rest/v4"  # Using V4 API (required for new users)
OUTPUT_DIR = Path("data/scenarios/courtlistener")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting
REQUEST_DELAY = 0.5  # Seconds between requests


def download_virginia_cases(max_cases: Optional[int] = None):
    """Download all Virginia cases from CourtListener V4 API"""
    if not API_KEY:
        print("ERROR: COURTLISTENER_API_KEY not set in environment")
        print("Get a free API key at: https://www.courtlistener.com/api/")
        return
    
    print(f"Downloading Virginia cases to: {OUTPUT_DIR}")
    print(f"API Key: {API_KEY[:10]}...")
    print("Using CourtListener V4 API...")
    
    # V4 API uses 'opinions' endpoint for case law
    # Filter for Virginia cases
    params = {
        "court__jurisdiction": "va",  # Virginia jurisdiction
        "page_size": 20,  # Smaller page size for V4
        "ordering": "-date_filed"
    }
    
    page = 1
    total_downloaded = 0
    
    while True:
        if max_cases and total_downloaded >= max_cases:
            break
            
        params["page"] = page
        try:
            # V4 API uses /opinions/ endpoint for case opinions
            response = requests.get(
                f"{BASE_URL}/opinions/",
                params=params,
                headers={"Authorization": f"Token {API_KEY}"},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                error_text = response.text[:500]
                print(error_text)
                if response.status_code == 403:
                    print("\nNote: If you see a V3/V4 error, the API key may need time to activate.")
                break
                
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                print("No more results found.")
                break
            
            print(f"Page {page}: Found {len(results)} cases")
            
            for case in results:
                if max_cases and total_downloaded >= max_cases:
                    break
                
                # Case data is already in the results, no need for separate fetch
                case_id = case.get("id")
                if not case_id:
                    continue
                
                # Check if file already exists (skip duplicates)
                case_file = OUTPUT_DIR / f"case_{case_id}.json"
                if case_file.exists():
                    continue  # Skip if already downloaded
                
                try:
                    # Save the case data directly
                    with open(case_file, "w", encoding="utf-8", errors="replace") as f:
                        json.dump(case, f, indent=2, ensure_ascii=False)
                    
                    total_downloaded += 1
                    case_name = case.get("case_name", "Unknown")[:50]
                    print(f"  [{total_downloaded}] Downloaded: {case_name} (ID: {case_id})")
                    
                    time.sleep(REQUEST_DELAY)
                except Exception as e:
                    print(f"Error saving case {case_id}: {e}")
                    continue
            
            # Check for next page
            if not data.get("next"):
                break
                
            page += 1
                
        except Exception as e:
            print(f"Error on page {page}: {e}")
            break
    
    print(f"\n{'='*60}")
    print(f"Download complete! Total cases: {total_downloaded}")
    print(f"Files saved to: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    import sys
    
    # Allow limiting number of cases for testing
    max_cases = None
    if len(sys.argv) > 1:
        try:
            max_cases = int(sys.argv[1])
            print(f"Limiting download to {max_cases} cases")
        except ValueError:
            print("Usage: python download_cases.py [max_cases]")
            sys.exit(1)
    
    download_virginia_cases(max_cases=max_cases)

