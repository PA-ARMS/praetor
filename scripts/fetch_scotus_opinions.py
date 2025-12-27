"""
Specialized SCOTUS Opinion Fetcher
Extracts and downloads all Supreme Court opinions from the official website.
This creates a comprehensive SCOTUS database for the legal AI system.
"""

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Set
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

OUTPUT_ROOT = Path("data/sources/SCOTUS_OPINIONS")
MANIFEST_ROOT = Path("data/manifests")
BASE_URL = "https://www.supremecourt.gov"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_REQUESTS = 1.0  # Reduced delay for faster downloads


def sanitize_filename(name: str) -> str:
    """Sanitize filename for filesystem."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)[:200]


def fetch_url(url: str) -> requests.Response:
    """Fetch URL with proper headers."""
    return requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)


def save_file(path: Path, content: bytes):
    """Save file content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def extract_pdf_links_from_slip_opinion_page(html_content: str, base_url: str) -> Set[str]:
    """
    Extract all PDF opinion links from a slip opinion HTML page.
    Looks for links in the format: /opinions/{TERM}pdf/{CITATION}_{ID}.pdf
    """
    pdf_links = set()
    soup = BeautifulSoup(html_content, "lxml")
    
    # Find all links that point to PDFs in the opinions directory
    for link in soup.find_all("a", href=True):
        href = link.get("href", "").strip()
        if not href:
            continue
        
        # Look for opinion PDF links
        # Pattern: /opinions/{TERM}pdf/{filename}.pdf
        if "/opinions/" in href and "pdf" in href.lower() and href.endswith(".pdf"):
            # Make absolute URL
            full_url = urljoin(base_url, href)
            pdf_links.add(full_url)
    
    return pdf_links


def extract_opinions_from_table(html_content: str, base_url: str) -> List[Dict[str, str]]:
    """
    Extract opinion metadata and PDF links from slip opinion table.
    Returns list of dicts with: url, docket, name, date, citation, justice
    """
    opinions = []
    soup = BeautifulSoup(html_content, "lxml")
    
    # Find all tables that contain opinion data
    tables = soup.find_all("table", class_="table")
    
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 6:  # Need at least 6 columns
                continue
            
            # Extract data from table cells
            # Format: R-, Date, Docket, Name (with link), Justice, Citation
            try:
                date = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                docket = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                
                # Name cell contains the link
                name_cell = cells[3] if len(cells) > 3 else None
                name_link = name_cell.find("a", href=True) if name_cell else None
                name = name_cell.get_text(strip=True) if name_cell else ""
                pdf_url = urljoin(base_url, name_link["href"]) if name_link and name_link.get("href") else ""
                
                justice = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                citation = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                
                if pdf_url and pdf_url.endswith(".pdf"):
                    opinions.append({
                        "url": pdf_url,
                        "docket": docket,
                        "name": name,
                        "date": date,
                        "citation": citation,
                        "justice": justice
                    })
            except Exception as e:
                # Skip malformed rows
                continue
    
    return opinions


def fetch_slip_opinions_for_term(term: int) -> List[Dict[str, str]]:
    """
    Fetch all slip opinions for a given term.
    Terms are numbered: 25 = 2025, 24 = 2024, etc.
    """
    opinions = []
    slip_url = f"{BASE_URL}/opinions/slipopinion/{term}"
    
    print(f"Fetching slip opinions for term {term} (October Term {2000 + term})...")
    
    try:
        resp = fetch_url(slip_url)
        if resp.status_code != 200:
            print(f"  Warning: Could not fetch {slip_url} (status {resp.status_code})")
            return opinions
        
        # Save the HTML page
        html_path = OUTPUT_ROOT / f"slipopinion_{term}.html"
        save_file(html_path, resp.content)
        
        # Extract opinions from the table
        opinions = extract_opinions_from_table(resp.text, BASE_URL)
        
        # Also extract any PDF links we might have missed
        pdf_links = extract_pdf_links_from_slip_opinion_page(resp.text, BASE_URL)
        
        # Add any PDFs we found that weren't in the table
        for pdf_url in pdf_links:
            if not any(op["url"] == pdf_url for op in opinions):
                opinions.append({
                    "url": pdf_url,
                    "docket": "",
                    "name": "",
                    "date": "",
                    "citation": "",
                    "justice": ""
                })
        
        print(f"  Found {len(opinions)} opinions")
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        
    except Exception as e:
        print(f"  Error fetching term {term}: {e}")
    
    return opinions


def fetch_bound_volumes() -> List[Dict[str, str]]:
    """Fetch all available bound volumes from US Reports page."""
    volumes = []
    us_reports_url = f"{BASE_URL}/opinions/USReports.aspx"
    
    print("Fetching bound volumes from US Reports page...")
    
    try:
        resp = fetch_url(us_reports_url)
        if resp.status_code != 200:
            print(f"  Warning: Could not fetch {us_reports_url}")
            return volumes
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        # Find all links to bound volumes
        # Pattern: boundvolumes/{VOL}BV.pdf
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "boundvolumes" in href and href.endswith(".pdf"):
                vol_url = urljoin(BASE_URL, href)
                vol_text = link.get_text(strip=True)
                
                # Extract volume number from text or URL
                vol_match = re.search(r'(\d+)', vol_text)
                vol_num = vol_match.group(1) if vol_match else ""
                
                volumes.append({
                    "url": vol_url,
                    "type": "bound_volume",
                    "volume": vol_num,
                    "name": vol_text,
                    "docket": "",
                    "date": "",
                    "citation": "",
                    "justice": ""
                })
        
        print(f"  Found {len(volumes)} bound volumes")
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        
    except Exception as e:
        print(f"  Error fetching bound volumes: {e}")
    
    return volumes


def fetch_preliminary_prints() -> List[Dict[str, str]]:
    """Fetch all available preliminary prints from US Reports page."""
    prints = []
    us_reports_url = f"{BASE_URL}/opinions/USReports.aspx"
    
    print("Fetching preliminary prints from US Reports page...")
    
    try:
        resp = fetch_url(us_reports_url)
        if resp.status_code != 200:
            print(f"  Warning: Could not fetch {us_reports_url}")
            return prints
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        # Find all links to preliminary prints
        # Pattern: preliminaryprint/{VOL}US{PART}PP_web.pdf or {VOL}US{PART}PP_final.pdf
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "preliminaryprint" in href and href.endswith(".pdf"):
                print_url = urljoin(BASE_URL, href)
                print_text = link.get_text(strip=True)
                
                # Extract volume number
                vol_match = re.search(r'Volume\s+(\d+)', print_text)
                vol_num = vol_match.group(1) if vol_match else ""
                
                prints.append({
                    "url": print_url,
                    "type": "preliminary_print",
                    "volume": vol_num,
                    "name": print_text,
                    "docket": "",
                    "date": "",
                    "citation": "",
                    "justice": ""
                })
        
        print(f"  Found {len(prints)} preliminary prints")
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        
    except Exception as e:
        print(f"  Error fetching preliminary prints: {e}")
    
    return prints


def download_opinion_pdf(opinion: Dict[str, str], out_dir: Path) -> Dict[str, any]:
    """
    Download a single opinion PDF and return manifest entry.
    """
    url = opinion["url"]
    parsed = urlparse(url)
    
    # Create filename from URL path
    path_parts = parsed.path.strip("/").split("/")
    filename = path_parts[-1] if path_parts else "opinion.pdf"
    file_path = out_dir / sanitize_filename(filename)
    
    # If file already exists, skip download but still return manifest entry
    if file_path.exists():
        return {
            "url": url,
            "path": str(file_path),
            "content_type": "application/pdf",
            "status": 200,
            "size": file_path.stat().st_size,
            "docket": opinion.get("docket", ""),
            "name": opinion.get("name", ""),
            "date": opinion.get("date", ""),
            "citation": opinion.get("citation", ""),
            "justice": opinion.get("justice", ""),
            "type": opinion.get("type", "slip_opinion"),
            "volume": opinion.get("volume", ""),
            "skipped": True
        }
    
    try:
        resp = fetch_url(url)
        if resp.status_code == 200:
            save_file(file_path, resp.content)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            
            return {
                "url": url,
                "path": str(file_path),
                "content_type": "application/pdf",
                "status": resp.status_code,
                "size": len(resp.content),
                "docket": opinion.get("docket", ""),
                "name": opinion.get("name", ""),
                "date": opinion.get("date", ""),
                "citation": opinion.get("citation", ""),
                "justice": opinion.get("justice", ""),
                "type": opinion.get("type", "slip_opinion"),
                "volume": opinion.get("volume", "")
            }
    except Exception as e:
        print(f"    Error downloading {url}: {e}")
        return None
    
    return None


def main():
    """Main function to fetch all SCOTUS opinions."""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("SCOTUS OPINION FETCHER")
    print("Building comprehensive Supreme Court opinion database")
    print("=" * 80)
    print()
    
    all_opinions = []
    manifest_items = []
    
    # Determine which terms to fetch
    # Current term is 25 (2025), and we want to go back as far as available
    # Terms typically go back to at least term 17 (2017) on the website
    current_term = 25
    start_term = 17  # Can be adjusted based on availability
    
    # Fetch slip opinions for each term
    print("STEP 1: Fetching slip opinions by term...")
    print("-" * 80)
    for term in range(start_term, current_term + 1):
        opinions = fetch_slip_opinions_for_term(term)
        all_opinions.extend(opinions)
    
    print()
    print(f"Total slip opinions found: {len(all_opinions)}")
    print()
    
    # Fetch bound volumes
    print("STEP 2: Fetching bound volumes...")
    print("-" * 80)
    bound_volumes = fetch_bound_volumes()
    all_opinions.extend(bound_volumes)
    print()
    
    # Fetch preliminary prints
    print("STEP 3: Fetching preliminary prints...")
    print("-" * 80)
    preliminary_prints = fetch_preliminary_prints()
    all_opinions.extend(preliminary_prints)
    print()
    
    # Download all PDFs
    print("STEP 4: Downloading opinion PDFs...")
    print("-" * 80)
    print(f"Downloading {len(all_opinions)} opinion files...")
    print()
    
    downloaded = 0
    skipped = 0
    errors = 0
    
    with tqdm(total=len(all_opinions), desc="Downloading", unit="file", 
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
        for opinion in all_opinions:
            manifest_entry = download_opinion_pdf(opinion, OUTPUT_ROOT)
            if manifest_entry:
                manifest_items.append(manifest_entry)
                if manifest_entry.get("skipped"):
                    skipped += 1
                elif manifest_entry["status"] == 200:
                    downloaded += 1
                else:
                    skipped += 1
            else:
                errors += 1
            pbar.update(1)
            # Update description with current stats
            pbar.set_postfix({'Downloaded': downloaded, 'Skipped': skipped, 'Errors': errors})
    
    print()
    print(f"Download complete:")
    print(f"  Downloaded: {downloaded}")
    print(f"  Skipped (already exists): {skipped}")
    print(f"  Errors: {errors}")
    print()
    
    # Save manifest
    manifest_path = MANIFEST_ROOT / "SCOTUS_OPINIONS.json"
    manifest_data = {
        "source_id": "SCOTUS_OPINIONS",
        "name": "SCOTUS Opinions",
        "jurisdiction": "Federal",
        "priority": 1,
        "fetched_at": datetime.now().isoformat(),
        "total_opinions": len(manifest_items),
        "items": manifest_items
    }
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)
    
    print(f"Manifest saved: {manifest_path}")
    print()
    print("=" * 80)
    print("SCOTUS OPINION FETCH COMPLETE")
    print("=" * 80)
    print()
    print(f"Next step: Run ingestion script to add opinions to RAG system:")
    print(f"  python scripts/ingest_sources.py")
    print()


if __name__ == "__main__":
    main()

