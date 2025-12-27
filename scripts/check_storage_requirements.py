"""
Check storage requirements for downloading all Virginia cases from CourtListener
"""
import requests
import os
import json
import sys
from pathlib import Path
from typing import Optional

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration
API_KEY = os.environ.get("COURTLISTENER_API_KEY", "")
BASE_URL = "https://www.courtlistener.com/api/rest/v4"

def get_total_virginia_cases() -> Optional[int]:
    """Get total count of Virginia cases from CourtListener API"""
    if not API_KEY:
        print("ERROR: COURTLISTENER_API_KEY not set in environment")
        print("Get a free API key at: https://www.courtlistener.com/api/")
        return None
    
    print("Querying CourtListener API for Virginia cases...")
    print(f"API Key: {API_KEY[:10]}...")
    
    # Make a request to get total count
    # V4 API returns count in the response
    params = {
        "court__jurisdiction": "va",  # Virginia jurisdiction
        "page_size": 1,  # Minimal page size just to get count
        "ordering": "-date_filed"
    }
    
    try:
        response = requests.get(
            f"{BASE_URL}/opinions/",
            params=params,
            headers={"Authorization": f"Token {API_KEY}"},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}")
            print(response.text[:500])
            return None
        
        data = response.json()
        
        # V4 API structure: check for 'count' field
        # The count might be a URL or a number - check the type
        count_value = data.get("count")
        
        # If count is a URL string, we need to fetch it separately
        if isinstance(count_value, str) and count_value.startswith("http"):
            # It's a URL - fetch the count
            try:
                count_response = requests.get(
                    count_value,
                    headers={"Authorization": f"Token {API_KEY}"},
                    timeout=30
                )
                if count_response.status_code == 200:
                    total_count = count_response.json().get("count", 0)
                else:
                    print(f"Warning: Could not fetch count from URL: {count_response.status_code}")
                    total_count = None
            except Exception as e:
                print(f"Error fetching count URL: {e}")
                total_count = None
        else:
            # It's a number or None
            total_count = count_value
        
        # Ensure it's an integer
        if total_count is None:
            print(f"Warning: Count field not found or is None")
            print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            # Try to estimate from pagination - but this is unreliable
            print("Note: Cannot determine exact count. Will use sample-based estimation.")
            return None
        
        try:
            total_count = int(total_count)
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not convert count to integer: {e}")
            print(f"Count value was: {count_value}")
            return None
        
        if total_count == 0:
            print("Warning: API returned 0 cases. Check your jurisdiction filter.")
            return None
        
        print(f"[OK] Found {total_count} total Virginia cases in CourtListener")
        return total_count
        
    except Exception as e:
        print(f"Error querying API: {e}")
        return None


def calculate_storage_requirements(total_cases: int):
    """Calculate storage requirements based on sample data"""
    # Check existing downloaded files for average size
    cases_dir = Path("data/scenarios/courtlistener")
    
    if cases_dir.exists():
        files = list(cases_dir.glob("*.json"))
        if files:
            total_size = sum(f.stat().st_size for f in files)
            avg_size = total_size / len(files)
            sample_count = len(files)
            
            print(f"\n{'='*60}")
            print("STORAGE REQUIREMENTS CALCULATION")
            print(f"{'='*60}")
            print(f"\nSample Data Analysis:")
            print(f"  - Sample files analyzed: {sample_count}")
            print(f"  - Total sample size: {total_size / 1024 / 1024:.2f} MB")
            print(f"  - Average file size: {avg_size / 1024:.2f} KB")
            print(f"  - Average file size: {avg_size / 1024 / 1024:.4f} MB")
            
            # Calculate for all cases
            estimated_total_size = (avg_size * total_cases) / 1024 / 1024 / 1024  # GB
            estimated_total_size_mb = (avg_size * total_cases) / 1024 / 1024  # MB
            
            print(f"\nEstimated Storage Requirements:")
            print(f"  - Total cases: {total_cases}")
            print(f"  - Estimated total size: {estimated_total_size:.2f} GB")
            print(f"  - Estimated total size: {estimated_total_size_mb:.0f} MB")
            
            # Add 20% overhead for metadata, processing, etc.
            overhead = 1.2
            with_overhead = estimated_total_size * overhead
            with_overhead_mb = estimated_total_size_mb * overhead
            
            print(f"\nWith 20% overhead (metadata, processing):")
            print(f"  - Recommended storage: {with_overhead:.2f} GB")
            print(f"  - Recommended storage: {with_overhead_mb:.0f} MB")
            
            # Time estimate (assuming 0.5s delay between requests)
            requests_needed = total_cases
            time_seconds = requests_needed * 0.5
            time_hours = time_seconds / 3600
            time_days = time_hours / 24
            
            print(f"\nDownload Time Estimate (0.5s delay per request):")
            print(f"  - Total requests: {requests_needed}")
            print(f"  - Estimated time: {time_hours:.1f} hours")
            print(f"  - Estimated time: {time_days:.2f} days")
            
            # API rate limits (CourtListener allows ~10 requests/second for free tier)
            # But we're using 0.5s delay = 2 requests/second to be safe
            print(f"\nAPI Rate Limits:")
            print(f"  - Current delay: 0.5s per request (2 requests/second)")
            print(f"  - Free tier allows ~10 requests/second")
            print(f"  - Could reduce delay to 0.1s for faster download (10 req/s)")
            
            if time_days > 1:
                faster_time_hours = (requests_needed * 0.1) / 3600
                faster_time_days = faster_time_hours / 24
                print(f"  - With 0.1s delay: {faster_time_hours:.1f} hours ({faster_time_days:.2f} days)")
            
            print(f"\n{'='*60}")
            print("RECOMMENDATIONS:")
            print(f"{'='*60}")
            print(f"1. Storage: Allocate at least {with_overhead:.2f} GB for Virginia cases")
            print(f"2. Download: Use batch processing with rate limiting")
            print(f"3. Consider: Downloading in chunks (e.g., by year or court level)")
            print(f"4. Monitor: Track download progress and handle API errors")
            print(f"{'='*60}")
            
        else:
            print("\nNo sample files found. Cannot calculate average file size.")
            print("Please download a small sample first (e.g., 10-20 cases) to estimate.")
    else:
        print("\nNo cases directory found. Cannot calculate average file size.")
        print("Please download a small sample first (e.g., 10-20 cases) to estimate.")


def main():
    print("="*60)
    print("VIRGINIA CASES STORAGE REQUIREMENTS CHECK")
    print("="*60)
    print()
    
    total_cases = get_total_virginia_cases()
    
    if total_cases:
        calculate_storage_requirements(total_cases)
    else:
        print("\nCould not retrieve total case count. Please check your API key.")


if __name__ == "__main__":
    main()

