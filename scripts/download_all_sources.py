"""
Download ALL legal sources - comprehensive fetcher with no artificial limits.
Downloads from all non-commercial, non-auth sources in the catalog.
"""
import json
import os
import re
import time
import sys
import zipfile
import asyncio
from pathlib import Path
from urllib.parse import urlparse, urljoin
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

CATALOG_PATH = Path("config/source_catalog.json")
OUTPUT_ROOT = Path("data/sources")
MANIFEST_ROOT = Path("data/manifests")

DEFAULT_HEADERS = {
    "User-Agent": "LexTech-LegalCrawler/1.0 (+local; contact: admin@localhost)"
}

ALLOWED_CONTENT_TYPES = {
    "text/html",
    "application/pdf",
    "application/xml",
    "text/xml",
    "application/xhtml+xml",
    "text/plain"
}

# NO ARTIFICIAL LIMIT - download everything we can
MAX_PER_SOURCE = int(os.environ.get("MAX_PER_SOURCE", "10000"))
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_REQUESTS = float(os.environ.get("CRAWL_DELAY", "0.3"))

# Sources to prioritize (Virginia-focused)
PRIORITY_SOURCES = [
    # Virginia Priority 1
    "VA_CODE",
    "VA_ADMIN_CODE", 
    "VA_REGISTER",
    "VA_LIS_BILL_TRACKING",
    "VA_COURTS",
    "VA_OPINIONS",
    "VA_ACMS",
    # Federal Priority 1
    "US_CODE_OLRC",
    "US_CODE_GOVINFO",
    "CFR_GOVINFO",
    "SCOTUS_OPINIONS",
    "SCOTUS_PORTAL",
    "FED_REGISTER_GOVINFO",
    # Priority 2
    "ECFR",
    "ECFR_XML",
    "US_COURTS_RULES",
    "FEDERALREGISTER_PORTAL",
    # Priority 3 (Open aggregators)
    "US_CODE_LII",
    "JUSTIA_FED",
    "JUSTIA_VA_SCV",
    "JUSTIA_VA_COA",
    # Bulk data
    "GOVINFO_BULK",
    "FED_REGISTER_BULK",
    "USLM_SCHEMAS",
]


def is_allowed_source(src: dict) -> bool:
    """Check if source can be downloaded (no auth, not commercial)"""
    if src.get("auth_required"):
        return False
    if src.get("authority_type") == "commercial":
        return False
    return True


def domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lower()


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)[:200]


def save_bytes(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def guess_extension(content_type: str, url: str = "") -> str:
    if not content_type:
        # Try to guess from URL
        if url.lower().endswith(".pdf"):
            return ".pdf"
        if url.lower().endswith(".xml"):
            return ".xml"
        return ".html"
    ct = content_type.lower()
    if "html" in ct:
        return ".html"
    if "pdf" in ct:
        return ".pdf"
    if "xml" in ct:
        return ".xml"
    if "zip" in ct:
        return ".zip"
    if "plain" in ct:
        return ".txt"
    return ".html"


def fetch_url(url: str, timeout: int = REQUEST_TIMEOUT) -> requests.Response:
    return requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)


def crawl_site(source_id: str, base_url: str, out_dir: Path, limit: int = MAX_PER_SOURCE) -> list:
    """Crawl a website and download all linked pages/PDFs"""
    visited = set()
    queue = [base_url]
    manifest = []
    base_domain = domain_from_url(base_url)
    
    # Track what we've saved to avoid duplicates
    saved_paths = set()

    pbar = tqdm(total=limit, desc=f"{source_id}", unit="file", leave=True)

    while queue and len(manifest) < limit:
        url = queue.pop(0)
        
        # Normalize URL
        url = url.split("#")[0]  # Remove fragments
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = fetch_url(url)
        except Exception as e:
            continue

        if resp.status_code != 200:
            continue

        ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        
        # Accept more content types
        is_allowed = any(allowed in ctype for allowed in ["html", "pdf", "xml", "text"])
        if not is_allowed and not url.lower().endswith((".pdf", ".xml", ".html", ".htm")):
            continue

        ext = guess_extension(ctype, url)
        parsed = urlparse(url)
        rel_path = sanitize_filename(parsed.path.strip("/") or "index")
        
        # Add query string hash for uniqueness
        if parsed.query:
            rel_path += "_" + sanitize_filename(parsed.query)[:50]
        
        file_path = out_dir / f"{rel_path}{ext}"
        
        # Skip if already saved
        if str(file_path) in saved_paths:
            continue

        try:
            save_bytes(file_path, resp.content)
            saved_paths.add(str(file_path))
        except Exception:
            continue

        manifest.append({
            "url": url,
            "path": str(file_path),
            "content_type": ctype,
            "status": resp.status_code,
            "size": len(resp.content)
        })
        pbar.update(1)

        # Enqueue links if HTML
        if "html" in ctype:
            try:
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if not href or href.startswith(("javascript:", "mailto:", "tel:")):
                        continue
                    next_url = urljoin(url, href)
                    parsed_next = urlparse(next_url)
                    
                    # Stay on same domain
                    if parsed_next.scheme.startswith("http") and parsed_next.netloc.lower() == base_domain:
                        clean_url = next_url.split("#")[0]
                        if clean_url not in visited:
                            queue.append(clean_url)
            except Exception:
                pass

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    pbar.close()
    return manifest


def download_bulk(source_id: str, url: str, out_dir: Path) -> list:
    """Download bulk data files (ZIP, XML)"""
    manifest = []
    try:
        print(f"  Downloading bulk: {url}")
        resp = fetch_url(url, timeout=120)  # Longer timeout for bulk
        if resp.status_code == 200:
            filename = sanitize_filename(url.split("/")[-1] or f"{source_id}_bulk")
            ctype = resp.headers.get("Content-Type", "")
            
            if "zip" in ctype.lower() or url.endswith(".zip"):
                filename = filename if filename.endswith(".zip") else filename + ".zip"
            elif "xml" in ctype.lower() or url.endswith(".xml"):
                filename = filename if filename.endswith(".xml") else filename + ".xml"
            
            file_path = out_dir / filename
            save_bytes(file_path, resp.content)
            
            manifest.append({
                "url": url,
                "path": str(file_path),
                "content_type": ctype,
                "status": resp.status_code,
                "size": len(resp.content)
            })
            print(f"  ✓ Saved: {file_path} ({len(resp.content) / 1024 / 1024:.2f} MB)")
    except Exception as e:
        print(f"  ✗ Error downloading {url}: {e}")
    return manifest


def download_ecfr_xml(out_dir: Path) -> list:
    """Download eCFR XML data for all titles"""
    manifest = []
    base_url = "https://www.ecfr.gov/api/versioner/v1/full"
    
    print("  Downloading eCFR XML (all 50 titles)...")
    
    for title in tqdm(range(1, 51), desc="eCFR Titles"):
        try:
            url = f"{base_url}/{datetime.now().strftime('%Y-%m-%d')}/title-{title}.xml"
            resp = fetch_url(url, timeout=60)
            if resp.status_code == 200:
                file_path = out_dir / f"title_{title}.xml"
                save_bytes(file_path, resp.content)
                manifest.append({
                    "url": url,
                    "path": str(file_path),
                    "content_type": "application/xml",
                    "status": 200,
                    "size": len(resp.content)
                })
            time.sleep(0.5)
        except Exception:
            pass
    
    return manifest


def download_va_code_sections(out_dir: Path) -> list:
    """Download all Virginia Code sections systematically"""
    manifest = []
    base_url = "https://law.lis.virginia.gov"
    
    print("  Fetching Virginia Code table of contents...")
    
    try:
        # Get main page
        resp = fetch_url(f"{base_url}/vacode")
        if resp.status_code != 200:
            return crawl_site("VA_CODE", f"{base_url}/vacode", out_dir, MAX_PER_SOURCE)
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        # Find all title links
        title_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/vacode/title" in href:
                title_links.append(urljoin(base_url, href))
        
        title_links = list(set(title_links))
        print(f"  Found {len(title_links)} titles")
        
        # Download each title and its sections
        for title_url in tqdm(title_links, desc="VA Code Titles"):
            try:
                resp = fetch_url(title_url)
                if resp.status_code == 200:
                    # Save title page
                    parsed = urlparse(title_url)
                    filename = sanitize_filename(parsed.path.strip("/"))
                    file_path = out_dir / f"{filename}.html"
                    save_bytes(file_path, resp.content)
                    manifest.append({
                        "url": title_url,
                        "path": str(file_path),
                        "content_type": "text/html",
                        "status": 200,
                        "size": len(resp.content)
                    })
                    
                    # Find section links
                    soup = BeautifulSoup(resp.text, "lxml")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if "/vacode/" in href and href != title_url:
                            section_url = urljoin(base_url, href)
                            try:
                                sec_resp = fetch_url(section_url)
                                if sec_resp.status_code == 200:
                                    sec_parsed = urlparse(section_url)
                                    sec_filename = sanitize_filename(sec_parsed.path.strip("/"))
                                    sec_path = out_dir / f"{sec_filename}.html"
                                    if not sec_path.exists():
                                        save_bytes(sec_path, sec_resp.content)
                                        manifest.append({
                                            "url": section_url,
                                            "path": str(sec_path),
                                            "content_type": "text/html",
                                            "status": 200,
                                            "size": len(sec_resp.content)
                                        })
                                time.sleep(0.2)
                            except Exception:
                                pass
                time.sleep(0.3)
            except Exception:
                pass
                
    except Exception as e:
        print(f"  Error: {e}, falling back to crawl")
        return crawl_site("VA_CODE", f"{base_url}/vacode", out_dir, MAX_PER_SOURCE)
    
    return manifest


def download_justia_cases(source_id: str, base_url: str, out_dir: Path) -> list:
    """Download cases from Justia"""
    manifest = []
    
    print(f"  Crawling Justia: {base_url}")
    
    # Justia organizes by year, so we'll crawl systematically
    try:
        resp = fetch_url(base_url)
        if resp.status_code != 200:
            return []
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        # Find year links
        year_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if base_url in href or href.startswith("/cases/virginia"):
                full_url = urljoin("https://law.justia.com", href)
                year_links.append(full_url)
        
        year_links = list(set(year_links))[:100]  # Limit years
        
        for year_url in tqdm(year_links, desc=f"{source_id}"):
            try:
                resp = fetch_url(year_url)
                if resp.status_code == 200:
                    parsed = urlparse(year_url)
                    filename = sanitize_filename(parsed.path.strip("/"))
                    file_path = out_dir / f"{filename}.html"
                    save_bytes(file_path, resp.content)
                    manifest.append({
                        "url": year_url,
                        "path": str(file_path),
                        "content_type": "text/html",
                        "status": 200,
                        "size": len(resp.content)
                    })
                    
                    # Get case links from year page
                    soup = BeautifulSoup(resp.text, "lxml")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if "/cases/virginia" in href:
                            case_url = urljoin("https://law.justia.com", href)
                            try:
                                case_resp = fetch_url(case_url)
                                if case_resp.status_code == 200:
                                    case_parsed = urlparse(case_url)
                                    case_filename = sanitize_filename(case_parsed.path.strip("/"))
                                    case_path = out_dir / f"{case_filename}.html"
                                    if not case_path.exists():
                                        save_bytes(case_path, case_resp.content)
                                        manifest.append({
                                            "url": case_url,
                                            "path": str(case_path),
                                            "content_type": "text/html",
                                            "status": 200,
                                            "size": len(case_resp.content)
                                        })
                                time.sleep(0.3)
                            except Exception:
                                pass
                time.sleep(0.5)
            except Exception:
                pass
                
    except Exception as e:
        print(f"  Error: {e}")
    
    return manifest


def process_source(src: dict) -> dict:
    """Process a single source"""
    sid = src["id"]
    name = src["name"]
    urls = src.get("urls", [])
    access = src.get("access_method", [])
    
    print(f"\n{'='*60}")
    print(f"Processing: {name} ({sid})")
    print(f"{'='*60}")
    
    out_dir = OUTPUT_ROOT / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    
    source_manifest = []
    
    # Special handling for specific sources
    if sid == "ECFR_XML":
        source_manifest.extend(download_ecfr_xml(out_dir))
    elif sid == "VA_CODE":
        source_manifest.extend(download_va_code_sections(out_dir))
    elif sid in ("JUSTIA_VA_SCV", "JUSTIA_VA_COA", "JUSTIA_FED"):
        if urls:
            source_manifest.extend(download_justia_cases(sid, urls[0], out_dir))
    else:
        # Standard processing
        # Try bulk endpoints first
        if "bulk_zip" in access or "xml" in access:
            for u in urls:
                if any(key in u.lower() for key in ["bulk", "xml", "data"]):
                    source_manifest.extend(download_bulk(sid, u, out_dir))
        
        # Crawl website
        if "website_html" in access and urls:
            source_manifest.extend(crawl_site(sid, urls[0], out_dir, MAX_PER_SOURCE))
    
    # Save manifest
    manifest_path = MANIFEST_ROOT / f"{sid}.json"
    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump({
            "source_id": sid,
            "name": name,
            "jurisdiction": src.get("jurisdiction"),
            "priority": src.get("priority"),
            "downloaded_at": datetime.now().isoformat(),
            "items": source_manifest
        }, mf, ensure_ascii=False, indent=2)
    
    return {
        "id": sid,
        "count": len(source_manifest),
        "manifest": str(manifest_path)
    }


def run(sources_to_process: list = None):
    """Run the download for specified sources or all"""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    
    # Filter sources
    if sources_to_process:
        sources = [s for s in catalog["sources"] if s["id"] in sources_to_process and is_allowed_source(s)]
    else:
        sources = [s for s in catalog["sources"] if is_allowed_source(s)]
    
    # Sort by priority
    sources.sort(key=lambda x: (x.get("priority", 5), PRIORITY_SOURCES.index(x["id"]) if x["id"] in PRIORITY_SOURCES else 999))
    
    print(f"Will process {len(sources)} sources")
    
    all_results = {}
    
    for src in sources:
        try:
            result = process_source(src)
            all_results[src["id"]] = result
        except Exception as e:
            print(f"Error processing {src['id']}: {e}")
            all_results[src["id"]] = {"id": src["id"], "count": 0, "error": str(e)}
    
    # Save summary
    summary_path = MANIFEST_ROOT / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as sf:
        json.dump(all_results, sf, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print("DOWNLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"Summary saved to: {summary_path}")
    
    total_files = sum(r.get("count", 0) for r in all_results.values())
    print(f"Total files downloaded: {total_files}")


if __name__ == "__main__":
    # Parse command line args for specific sources
    if len(sys.argv) > 1:
        sources = sys.argv[1:]
        print(f"Processing specific sources: {sources}")
        run(sources)
    else:
        # Process all priority sources
        print("Processing all priority sources...")
        run(PRIORITY_SOURCES)


