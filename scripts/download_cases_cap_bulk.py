"""
Download cases from CAP (Caselaw Access Project) Bulk Data
Uses static.case.law for direct file downloads (faster than API)
Reference: https://static.case.law/
"""
import requests
import json
from pathlib import Path
import time
import os
from typing import Optional, List
from datetime import datetime
import zipfile
import io

# Configuration
BASE_URL = "https://static.case.law"
OUTPUT_DIR = Path("data/scenarios/cap")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Progress tracking
PROGRESS_FILE = OUTPUT_DIR / ".download_progress_bulk.json"

# Rate limiting
REQUEST_DELAY = 0.5  # Seconds between requests

# Virginia jurisdiction codes from static.case.law
VA_JURISDICTIONS = [
    "va",           # Virginia Supreme Court
    "va-app",       # Virginia Court of Appeals
    "va-ch-dec",    # Virginia Chancery Decisions
    "va-cir",       # Virginia Circuit Court
    "va-col-dec",   # Virginia College Decisions
    "va-dec",       # Virginia Decisions
]


def load_progress():
    """Load download progress from file"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        "downloaded_jurisdictions": [],
        "total_downloaded": 0,
        "start_time": datetime.now().isoformat(),
        "errors": []
    }


def save_progress(progress):
    """Save download progress to file"""
    progress["last_update"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)


def get_jurisdiction_volumes(jurisdiction: str) -> List[str]:
    """Get list of volume numbers for a jurisdiction"""
    try:
        url = f"{BASE_URL}/{jurisdiction}/"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            # Parse directory listing (HTML table)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            volumes = set()
            for link in soup.find_all('a'):
                href = link.get('href', '')
                # Extract volume number from full URLs like:
                # https://static.case.law/va/1.zip or https://static.case.law/va/1/
                if f'/{jurisdiction}/' in href:
                    # Extract the part after jurisdiction
                    parts = href.split(f'/{jurisdiction}/')
                    if len(parts) > 1:
                        vol_part = parts[1].split('/')[0].split('.')[0]  # Get volume number before / or .
                        if vol_part.isdigit():
                            volumes.add(vol_part)
            return sorted(list(volumes), key=int)  # Sort numerically
    except Exception as e:
        print(f"Error getting volumes for {jurisdiction}: {e}")
        import traceback
        traceback.print_exc()
    return []


def download_volume_zip(jurisdiction: str, volume: str, max_cases: Optional[int] = None) -> int:
    """Download a volume ZIP file and extract cases"""
    url = f"{BASE_URL}/{jurisdiction}/{volume}.zip"
    downloaded = 0
    
    try:
        print(f"  Downloading volume {volume}.zip...")
        response = requests.get(url, timeout=120, stream=True)
        
        if response.status_code != 200:
            print(f"    Error: HTTP {response.status_code}")
            return 0
        
        # Download ZIP to memory
        zip_data = io.BytesIO(response.content)
        
        # Extract ZIP
        with zipfile.ZipFile(zip_data, 'r') as zip_ref:
            # Get list of files in ZIP
            file_list = zip_ref.namelist()
            
            # Process JSON files
            for filename in file_list:
                # Note: max_cases check is handled at volume level
                
                if filename.endswith('.json'):
                    try:
                        # Read JSON from ZIP
                        json_data = zip_ref.read(filename)
                        case_data = json.loads(json_data.decode('utf-8'))
                        
                        # Handle different structures
                        cases = []
                        if isinstance(case_data, list):
                            cases = case_data
                        elif isinstance(case_data, dict):
                            if 'results' in case_data:
                                cases = case_data['results']
                            elif 'cases' in case_data:
                                cases = case_data['cases']
                            else:
                                cases = [case_data]
                        
                        # Save each case
                        for case in cases:
                            # Note: max_cases check is handled at volume level
                            
                            case_id = str(case.get("id", case.get("case_id", f"cap_{jurisdiction}_{volume}_{downloaded}")))
                            case_file = OUTPUT_DIR / f"case_{case_id}.json"
                            
                            # Check if case exists in CAP directory
                            if case_file.exists():
                                continue
                            
                            # Also check if same case exists in CourtListener directory
                            courtlistener_file = Path("data/scenarios/courtlistener") / f"case_{case_id}.json"
                            if courtlistener_file.exists():
                                continue  # Skip if already in CourtListener
                            
                            # Check by case name to catch cross-source duplicates (fast lookup)
                            case_name = case.get("name") or case.get("case_name", "")
                            if case_name and cl_name_index:
                                # Normalize name for comparison
                                import re
                                normalized = re.sub(r'\s+', ' ', case_name.lower().strip())
                                normalized = re.sub(r'\s+v\.?\s+', ' v ', normalized)
                                
                                # Fast lookup in pre-built index
                                if normalized in cl_name_index and len(normalized) > 10:
                                    continue  # Skip duplicate by name
                            
                            if not case_file.exists():
                                with open(case_file, "w", encoding="utf-8", errors="replace") as f:
                                    json.dump(case, f, indent=2, ensure_ascii=False)
                                downloaded += 1
                                
                                if downloaded % 50 == 0:
                                    print(f"    Extracted {downloaded} cases from volume {volume}...")
                    except Exception as e:
                        print(f"    Error processing {filename} in ZIP: {e}")
                        continue
        
        return downloaded
        
    except Exception as e:
        print(f"    Error downloading volume {volume}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def build_courtlistener_name_index():
    """Build index of CourtListener case names for fast duplicate checking"""
    import re
    name_index = {}
    courtlistener_dir = Path("data/scenarios/courtlistener")
    
    if not courtlistener_dir.exists():
        return name_index
    
    print("Building CourtListener name index for duplicate detection...")
    case_files = list(courtlistener_dir.glob("case_*.json"))
    
    for case_file in case_files:
        try:
            with open(case_file, 'r', encoding='utf-8') as f:
                case_data = json.load(f)
            case_name = case_data.get("case_name") or case_data.get("name", "")
            if case_name:
                normalized = re.sub(r'\s+', ' ', case_name.lower().strip())
                normalized = re.sub(r'\s+v\.?\s+', ' v ', normalized)
                if len(normalized) > 10:  # Only index meaningful names
                    name_index[normalized] = case_file
        except:
            continue
    
    print(f"  Indexed {len(name_index)} CourtListener case names")
    return name_index

def download_cases_bulk(max_cases: Optional[int] = None, jurisdictions: Optional[List[str]] = None, download_all: bool = False):
    """
    Download cases from CAP bulk data repository
    
    Args:
        max_cases: Maximum number of cases to download
        jurisdictions: List of jurisdiction codes (default: Virginia jurisdictions)
        download_all: If True, download all cases (ignore max_cases)
    """
    if jurisdictions is None:
        jurisdictions = VA_JURISDICTIONS
    
    # Build name index for fast duplicate checking
    cl_name_index = build_courtlistener_name_index()
    
    progress = load_progress()
    total_downloaded = progress.get("total_downloaded", 0)
    # Only skip if we actually downloaded cases from this jurisdiction
    downloaded_jurisdictions = set(progress.get("downloaded_jurisdictions", []))
    
    print(f"\n{'='*60}")
    print(f"CAP BULK DATA DOWNLOAD")
    print(f"{'='*60}")
    print(f"Source: {BASE_URL}")
    if download_all:
        print(f"Target: ALL cases (no limit)")
    else:
        print(f"Target: {max_cases or 'unlimited'} cases")
    print(f"Jurisdictions: {', '.join(jurisdictions)}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Already downloaded: {total_downloaded:,} cases")
    print(f"{'='*60}\n")
    
    try:
        for jurisdiction in jurisdictions:
            if not download_all and max_cases and total_downloaded >= max_cases:
                break
            
            # Only skip if we actually have cases from this jurisdiction
            # Check if directory has cases, not just if it's in the list
            jurisdiction_has_cases = False
            if jurisdiction in downloaded_jurisdictions:
                # Verify we actually have cases
                jurisdiction_dir = OUTPUT_DIR
                existing_cases = list(jurisdiction_dir.glob("case_*.json"))
                if len(existing_cases) > 0:
                    jurisdiction_has_cases = True
            
            if jurisdiction_has_cases and total_downloaded > 0:
                print(f"Skipping {jurisdiction} (already has {len(existing_cases)} cases)")
                continue
            
            print(f"\nProcessing {jurisdiction}...")
            
            # Get list of volumes for this jurisdiction
            volumes = get_jurisdiction_volumes(jurisdiction)
            
            if not volumes:
                print(f"  No volumes found for {jurisdiction}")
                continue
            
            print(f"  Found {len(volumes)} volumes")
            
            # Download volumes
            for volume in volumes:
                if not download_all and max_cases and total_downloaded >= max_cases:
                    break
                
                remaining = max_cases - total_downloaded if (max_cases and not download_all) else None
                downloaded = download_volume_zip(jurisdiction, volume, remaining)
                total_downloaded += downloaded
                
                # Update progress
                progress["total_downloaded"] = total_downloaded
                progress["downloaded_jurisdictions"] = list(downloaded_jurisdictions)
                save_progress(progress)
                
                if downloaded > 0:
                    print(f"  Volume {volume}: {downloaded} cases (Total: {total_downloaded:,})")
                
                time.sleep(REQUEST_DELAY)
            
            downloaded_jurisdictions.add(jurisdiction)
            progress["downloaded_jurisdictions"] = list(downloaded_jurisdictions)
            save_progress(progress)
        
        print(f"\n{'='*60}")
        print(f"DOWNLOAD COMPLETE")
        print(f"{'='*60}")
        print(f"Total cases downloaded: {total_downloaded:,}")
        print(f"Files saved to: {OUTPUT_DIR}")
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        print(f"\n\nDownload interrupted by user")
        print(f"Progress saved. Resume by running again.")
        save_progress(progress)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download cases from CAP bulk data")
    parser.add_argument("--max-cases", type=int, help="Maximum number of cases to download")
    parser.add_argument("--jurisdiction", type=str, action="append", 
                       help="Jurisdiction code (can specify multiple)")
    parser.add_argument("--all", action="store_true", 
                       help="Download ALL cases (ignore max-cases limit)")
    
    args = parser.parse_args()
    
    download_cases_bulk(
        max_cases=args.max_cases,
        jurisdictions=args.jurisdiction,
        download_all=args.all
    )

