"""
Download cases from Caselaw Access Project (CAP) API
CAP provides free access to over 6.5 million U.S. court decisions
API Documentation: https://case.law/api/
"""
import requests
import json
from pathlib import Path
import time
import os
import sys
from typing import Optional
from datetime import datetime

# Configuration
API_KEY = os.environ.get("CAP_API_KEY", "")
# CAP API base URL - may need adjustment based on actual API structure
BASE_URL = "https://api.case.law/v1"  # Try this first, may be https://case.law/api/v1
OUTPUT_DIR = Path("data/scenarios/cap")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Progress tracking
PROGRESS_FILE = OUTPUT_DIR / ".download_progress.json"

# Rate limiting (be respectful to API)
REQUEST_DELAY = 0.5  # Seconds between requests
BATCH_SAVE_INTERVAL = 100  # Save progress every N cases

# Target cases
TARGET_CASES = 1000  # Default target


def load_progress():
    """Load download progress from file"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        "last_page": 1,
        "total_downloaded": 0,
        "last_case_id": None,
        "start_time": datetime.now().isoformat(),
        "errors": []
    }


def save_progress(progress):
    """Save download progress to file"""
    progress["last_update"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)


def get_downloaded_case_ids():
    """Get set of already downloaded case IDs"""
    downloaded = set()
    if OUTPUT_DIR.exists():
        for file in OUTPUT_DIR.glob("case_*.json"):
            try:
                case_id = file.stem.replace("case_", "")
                downloaded.add(case_id)
            except:
                pass
    return downloaded


def download_cases_cap(max_cases: Optional[int] = None, jurisdiction: str = "va", resume: bool = True):
    """
    Download cases from CAP API
    
    Args:
        max_cases: Maximum number of cases to download (None = use TARGET_CASES)
        jurisdiction: Jurisdiction code (default: "va" for Virginia)
        resume: Whether to resume from last checkpoint
    """
    if not API_KEY:
        print("ERROR: CAP_API_KEY not set in environment")
        print("Get a free API key at: https://case.law/api/")
        print("Then set: export CAP_API_KEY='your-key-here'")
        return
    
    progress = load_progress()
    if not resume:
        progress = {
            "last_page": 1,
            "total_downloaded": 0,
            "last_case_id": None,
            "start_time": datetime.now().isoformat(),
            "errors": []
        }
    
    # Get already downloaded IDs
    downloaded_ids = get_downloaded_case_ids()
    print(f"Found {len(downloaded_ids)} already downloaded cases")
    
    target = max_cases or TARGET_CASES
    start_page = progress["last_page"]
    total_downloaded = progress["total_downloaded"]
    
    print(f"\n{'='*60}")
    print(f"CAP CASE DOWNLOAD")
    print(f"{'='*60}")
    print(f"Target: {target:,} cases")
    print(f"Starting from page: {start_page}")
    print(f"Already downloaded: {total_downloaded:,}")
    print(f"Remaining: {target - total_downloaded:,}")
    print(f"Jurisdiction: {jurisdiction.upper()}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"{'='*60}\n")
    
    # API parameters
    params = {
        "jurisdiction": jurisdiction,
        "page_size": 100,  # CAP allows up to 100 per page
        "ordering": "-decision_date"  # Most recent first
    }
    
    page = start_page
    consecutive_empty_pages = 0
    max_empty_pages = 10
    last_save = total_downloaded
    
    try:
        while total_downloaded < target:
            params["page"] = page
            
            try:
                response = requests.get(
                    f"{BASE_URL}/cases/",
                    params=params,
                    headers={
                        "Authorization": f"Token {API_KEY}",
                        "Accept": "application/json"
                    },
                    timeout=60
                )
                
                if response.status_code == 429:
                    # Rate limited - wait longer
                    print(f"\nRate limited. Waiting 60 seconds...")
                    time.sleep(60)
                    continue
                
                if response.status_code == 401:
                    print(f"\nERROR: Authentication failed. Check your CAP_API_KEY")
                    print("Get a free API key at: https://case.law/api/")
                    break
                
                if response.status_code != 200:
                    print(f"\nError: HTTP {response.status_code}")
                    error_text = response.text[:500]
                    print(error_text)
                    if response.status_code == 403:
                        print("\nNote: API key may need activation or you've hit rate limits.")
                        print("Waiting 5 minutes before retry...")
                        time.sleep(300)
                        continue
                    break
                
                data = response.json()
                results = data.get("results", [])
                
                if not results:
                    print(f"\nNo more results found at page {page}")
                    break
                
                print(f"\nPage {page}: Processing {len(results)} cases...")
                
                page_downloaded = 0
                for case in results:
                    if total_downloaded >= target:
                        break
                    
                    case_id = str(case.get("id", ""))
                    if not case_id:
                        continue
                    
                    # Skip if already downloaded
                    if case_id in downloaded_ids:
                        continue
                    
                    case_file = OUTPUT_DIR / f"case_{case_id}.json"
                    if case_file.exists():
                        downloaded_ids.add(case_id)
                        continue
                    
                    try:
                        # Save the case data
                        with open(case_file, "w", encoding="utf-8", errors="replace") as f:
                            json.dump(case, f, indent=2, ensure_ascii=False)
                        
                        downloaded_ids.add(case_id)
                        total_downloaded += 1
                        page_downloaded += 1
                        
                        # Progress update every 10 cases
                        if total_downloaded % 10 == 0:
                            elapsed = time.time() - time.mktime(
                                datetime.fromisoformat(progress["start_time"]).timetuple()
                            ) if "start_time" in progress else 0
                            rate = total_downloaded / elapsed if elapsed > 0 else 0
                            remaining = (target - total_downloaded) / rate if rate > 0 else 0
                            progress_pct = (total_downloaded / target * 100) if target > 0 else 0
                            
                            # Progress bar
                            bar_width = 40
                            filled = int(progress_pct / 100 * bar_width)
                            bar = "█" * filled + "░" * (bar_width - filled)
                            
                            # Time formatting
                            if remaining < 60:
                                eta_str = f"{remaining:.0f}s"
                            elif remaining < 3600:
                                eta_str = f"{remaining/60:.1f}m"
                            else:
                                eta_str = f"{remaining/3600:.1f}h"
                            
                            print(f"\r[{bar}] {progress_pct:.1f}% | "
                                  f"{total_downloaded:,}/{target:,} cases | "
                                  f"Rate: {rate:.2f}/s | "
                                  f"ETA: {eta_str}", end="", flush=True)
                        
                        # Detailed update every 100 cases
                        if total_downloaded % 100 == 0:
                            elapsed = time.time() - time.mktime(
                                datetime.fromisoformat(progress["start_time"]).timetuple()
                            ) if "start_time" in progress else 0
                            rate = total_downloaded / elapsed if elapsed > 0 else 0
                            remaining = (target - total_downloaded) / rate if rate > 0 else 0
                            
                            print(f"\n  ✓ Downloaded {total_downloaded:,} cases | "
                                  f"Rate: {rate:.2f} cases/sec | "
                                  f"ETA: {remaining/3600:.1f} hours")
                        
                        # Save progress periodically
                        if total_downloaded - last_save >= BATCH_SAVE_INTERVAL:
                            progress["last_page"] = page
                            progress["total_downloaded"] = total_downloaded
                            progress["last_case_id"] = case_id
                            save_progress(progress)
                            last_save = total_downloaded
                        
                        time.sleep(REQUEST_DELAY)
                        
                    except Exception as e:
                        error_msg = f"Error saving case {case_id}: {e}"
                        print(f"  {error_msg}")
                        progress["errors"].append({
                            "case_id": case_id,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        })
                        continue
                
                # Smart page skipping: if no new downloads, skip ahead
                if page_downloaded == 0:
                    consecutive_empty_pages += 1
                    print(f"  All cases on page {page} already downloaded (empty pages: {consecutive_empty_pages})")
                    
                    # Skip ahead if too many consecutive empty pages
                    if consecutive_empty_pages >= max_empty_pages:
                        skip_amount = max_empty_pages * 10
                        page += skip_amount
                        consecutive_empty_pages = 0
                        print(f"  ⚡ Skipping ahead to page {page} to find new cases...")
                    else:
                        page += 1
                else:
                    consecutive_empty_pages = 0
                    page += 1
                
                # Check for next page
                if not data.get("next"):
                    print(f"\nNo more pages available")
                    break
                
                # Save progress after each page
                progress["last_page"] = page
                progress["total_downloaded"] = total_downloaded
                save_progress(progress)
                
            except requests.exceptions.RequestException as e:
                print(f"\nNetwork error on page {page}: {e}")
                print("Waiting 30 seconds before retry...")
                time.sleep(30)
                continue
            except Exception as e:
                print(f"\nError on page {page}: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(10)
                continue
        
        # Final summary
        print(f"\n{'='*60}")
        print(f"DOWNLOAD COMPLETE")
        print(f"{'='*60}")
        print(f"Total cases downloaded: {total_downloaded:,}")
        print(f"Files saved to: {OUTPUT_DIR}")
        if progress.get("errors"):
            print(f"Errors encountered: {len(progress['errors'])}")
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        print(f"\n\nDownload interrupted by user")
        print(f"Progress saved. Resume with: python download_cases_cap.py --resume")
        save_progress(progress)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download cases from Caselaw Access Project (CAP)")
    parser.add_argument("--max-cases", type=int, help="Maximum number of cases to download")
    parser.add_argument("--jurisdiction", type=str, default="va", help="Jurisdiction code (default: va)")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh (don't resume)")
    
    args = parser.parse_args()
    
    resume = not args.no_resume if args.no_resume else True
    if args.resume:
        resume = True
    
    download_cases_cap(
        max_cases=args.max_cases,
        jurisdiction=args.jurisdiction,
        resume=resume
    )

