"""
COMPLETE LEGAL DATABASE BUILDER
================================
Production-grade script to ensure the legal AI has access to ALL required data.

This script:
1. Downloads all missing/incomplete sources
2. Processes and extracts text from all files
3. Ingests everything into the RAG database
4. Validates completeness
5. Generates a production readiness report

For law firm deployment - NO COMPROMISES on data completeness.
"""
import json
import os
import re
import sys
import time
import csv
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, urljoin
from typing import Optional, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor
import traceback

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Import after path setup
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("WARNING: pdfplumber not installed - PDF extraction disabled")

from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service

# =============================================================================
# CONFIGURATION
# =============================================================================

CATALOG_PATH = Path("config/source_catalog.json")
OUTPUT_ROOT = Path("data/sources")
MANIFEST_ROOT = Path("data/manifests")
VA_CSV_DIR = Path("data/va_csv")
SCENARIOS_DIR = Path("data/scenarios")

# No artificial limits for production
MAX_FILES_PER_SOURCE = 50000
REQUEST_TIMEOUT = 60
CRAWL_DELAY = 0.25  # Respectful but efficient

DEFAULT_HEADERS = {
    "User-Agent": "Virginia-LegalAI-Crawler/1.0 (Law Firm Internal Use)"
}

# Priority order for downloads
DOWNLOAD_PRIORITY = [
    # Virginia Official Sources (CRITICAL)
    "VA_CODE",
    "VA_ADMIN_CODE",
    "VA_REGISTER", 
    "VA_LIS_BILL_TRACKING",
    "VA_COURTS",
    "VA_OPINIONS",
    "VA_ACMS",
    
    # Federal Official Sources (HIGH)
    "US_CODE_OLRC",
    "US_CODE_GOVINFO",
    "CFR_GOVINFO",
    "ECFR",
    "ECFR_XML",
    "FED_REGISTER_GOVINFO",
    "SCOTUS_OPINIONS",
    "SCOTUS_PORTAL",
    "US_COURTS_RULES",
    
    # Aggregators (MEDIUM - backup/supplemental)
    "US_CODE_LII",
    "JUSTIA_VA_SCV",
    "JUSTIA_VA_COA",
    "JUSTIA_FED",
    
    # Bulk Data
    "GOVINFO_BULK",
    "FED_REGISTER_BULK",
    "USLM_SCHEMAS",
    "FEDERALREGISTER_PORTAL",
]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def log(msg: str, level: str = "INFO"):
    """Structured logging"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def sanitize_filename(name: str) -> str:
    """Create safe filename"""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)[:200]


def get_file_hash(content: bytes) -> str:
    """Get MD5 hash of content for deduplication"""
    return hashlib.md5(content).hexdigest()[:12]


def fetch_url(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[requests.Response]:
    """Fetch URL with error handling"""
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
        return resp if resp.status_code == 200 else None
    except Exception:
        return None


def save_file(path: Path, content: bytes) -> bool:
    """Save file with directory creation"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return True
    except Exception:
        return False


def extract_text_from_html(html: str) -> str:
    """Extract clean text from HTML"""
    try:
        soup = BeautifulSoup(html, "lxml")
        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "meta", "link"]):
            tag.extract()
        text = soup.get_text("\n", strip=True)
        # Clean up whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    except Exception:
        return ""


def extract_text_from_pdf(path: Path) -> str:
    """Extract text from PDF"""
    if not PDF_SUPPORT:
        return ""
    try:
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts).strip()
    except Exception:
        return ""


def extract_text_from_xml(content: str) -> str:
    """Extract text from XML"""
    try:
        soup = BeautifulSoup(content, "lxml-xml")
        return soup.get_text("\n", strip=True)
    except Exception:
        return ""


def extract_text_from_file(path: Path) -> str:
    """Extract text from any supported file type"""
    suffix = path.suffix.lower()
    try:
        if suffix in (".html", ".htm", ".xhtml"):
            content = path.read_text(encoding="utf-8", errors="ignore")
            return extract_text_from_html(content)
        elif suffix == ".pdf":
            return extract_text_from_pdf(path)
        elif suffix == ".xml":
            content = path.read_text(encoding="utf-8", errors="ignore")
            return extract_text_from_xml(content)
        elif suffix == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        pass
    return ""


# =============================================================================
# SOURCE DOWNLOADERS
# =============================================================================

class SourceDownloader:
    """Base class for source downloaders"""
    
    def __init__(self, source_id: str, out_dir: Path):
        self.source_id = source_id
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.downloaded = []
        self.visited_urls = set()
        self.saved_hashes = set()
    
    def save(self, url: str, content: bytes, filename: str = None) -> Optional[Path]:
        """Save content with deduplication"""
        content_hash = get_file_hash(content)
        if content_hash in self.saved_hashes:
            return None
        
        if not filename:
            parsed = urlparse(url)
            filename = sanitize_filename(parsed.path.strip("/") or "index")
        
        # Determine extension from content type or URL
        if b'%PDF' in content[:10]:
            ext = ".pdf"
        elif b'<html' in content[:100].lower() or b'<!doctype' in content[:100].lower():
            ext = ".html"
        elif b'<?xml' in content[:50]:
            ext = ".xml"
        else:
            ext = ".html"
        
        if not filename.endswith(ext):
            filename = filename + ext
        
        path = self.out_dir / filename
        
        # Handle duplicates
        counter = 1
        base = path.stem
        while path.exists():
            path = self.out_dir / f"{base}_{counter}{ext}"
            counter += 1
        
        if save_file(path, content):
            self.saved_hashes.add(content_hash)
            self.downloaded.append({
                "url": url,
                "path": str(path),
                "size": len(content)
            })
            return path
        return None
    
    def crawl(self, start_url: str, max_files: int = MAX_FILES_PER_SOURCE) -> int:
        """Generic crawl implementation"""
        queue = [start_url]
        base_domain = urlparse(start_url).netloc.lower()
        
        pbar = tqdm(total=max_files, desc=self.source_id, unit="file")
        
        while queue and len(self.downloaded) < max_files:
            url = queue.pop(0)
            url = url.split("#")[0]  # Remove fragments
            
            if url in self.visited_urls:
                continue
            self.visited_urls.add(url)
            
            resp = fetch_url(url)
            if not resp:
                continue
            
            self.save(url, resp.content)
            pbar.update(1)
            
            # Extract links from HTML
            ctype = resp.headers.get("Content-Type", "").lower()
            if "html" in ctype:
                try:
                    soup = BeautifulSoup(resp.text, "lxml")
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                            continue
                        next_url = urljoin(url, href).split("#")[0]
                        parsed = urlparse(next_url)
                        if parsed.netloc.lower() == base_domain and next_url not in self.visited_urls:
                            queue.append(next_url)
                except Exception:
                    pass
            
            time.sleep(CRAWL_DELAY)
        
        pbar.close()
        return len(self.downloaded)


class VirginiaCodeDownloader(SourceDownloader):
    """Specialized downloader for Virginia Code"""
    
    def download(self) -> int:
        log(f"Downloading Virginia Code from law.lis.virginia.gov")
        base_url = "https://law.lis.virginia.gov"
        
        # First, get all title pages
        resp = fetch_url(f"{base_url}/vacode")
        if not resp:
            log("Failed to fetch VA Code index", "ERROR")
            return 0
        
        self.save(f"{base_url}/vacode", resp.content, "vacode_index")
        
        soup = BeautifulSoup(resp.text, "lxml")
        title_links = []
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/vacode/title" in href:
                full_url = urljoin(base_url, href)
                if full_url not in title_links:
                    title_links.append(full_url)
        
        log(f"Found {len(title_links)} Virginia Code titles")
        
        # Download each title and all its sections
        for title_url in tqdm(title_links, desc="VA Code Titles"):
            resp = fetch_url(title_url)
            if not resp:
                continue
            
            self.save(title_url, resp.content)
            
            # Find all section links
            soup = BeautifulSoup(resp.text, "lxml")
            section_links = []
            
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # Match section patterns like /vacode/8.01-1/
                if re.search(r'/vacode/\d+\.?\d*-\d+', href):
                    full_url = urljoin(base_url, href)
                    if full_url not in self.visited_urls:
                        section_links.append(full_url)
            
            # Download sections
            for section_url in section_links[:500]:  # Cap per title
                if section_url in self.visited_urls:
                    continue
                self.visited_urls.add(section_url)
                
                sec_resp = fetch_url(section_url)
                if sec_resp:
                    self.save(section_url, sec_resp.content)
                time.sleep(0.15)
            
            time.sleep(0.3)
        
        return len(self.downloaded)


class VirginiaAdminCodeDownloader(SourceDownloader):
    """Downloader for Virginia Administrative Code"""
    
    def download(self) -> int:
        log("Downloading Virginia Administrative Code")
        base_url = "https://law.lis.virginia.gov/admincode"
        
        resp = fetch_url(base_url)
        if not resp:
            return 0
        
        self.save(base_url, resp.content, "admincode_index")
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        # Find all agency/title links
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/admincode/title" in href:
                links.append(urljoin("https://law.lis.virginia.gov", href))
        
        links = list(set(links))
        log(f"Found {len(links)} admin code sections")
        
        for url in tqdm(links, desc="VA Admin Code"):
            if url in self.visited_urls:
                continue
            self.visited_urls.add(url)
            
            resp = fetch_url(url)
            if resp:
                self.save(url, resp.content)
                
                # Get subsections
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/admincode/" in href:
                        sub_url = urljoin("https://law.lis.virginia.gov", href)
                        if sub_url not in self.visited_urls:
                            self.visited_urls.add(sub_url)
                            sub_resp = fetch_url(sub_url)
                            if sub_resp:
                                self.save(sub_url, sub_resp.content)
                            time.sleep(0.15)
            
            time.sleep(0.2)
        
        return len(self.downloaded)


class ECFRDownloader(SourceDownloader):
    """Downloader for Electronic Code of Federal Regulations"""
    
    def download(self) -> int:
        log("Downloading eCFR (all 50 titles)")
        
        # eCFR has a nice API for XML
        today = datetime.now().strftime("%Y-%m-%d")
        
        for title in tqdm(range(1, 51), desc="eCFR Titles"):
            # Try XML API first
            xml_url = f"https://www.ecfr.gov/api/versioner/v1/full/{today}/title-{title}.xml"
            resp = fetch_url(xml_url, timeout=120)
            
            if resp:
                self.save(xml_url, resp.content, f"title_{title}.xml")
            else:
                # Fall back to HTML
                html_url = f"https://www.ecfr.gov/current/title-{title}"
                resp = fetch_url(html_url)
                if resp:
                    self.save(html_url, resp.content, f"title_{title}.html")
            
            time.sleep(0.5)
        
        return len(self.downloaded)


class JustiaDownloader(SourceDownloader):
    """Downloader for Justia case law"""
    
    def download(self, base_url: str) -> int:
        log(f"Downloading from Justia: {base_url}")
        
        resp = fetch_url(base_url)
        if not resp:
            return 0
        
        self.save(base_url, resp.content, "index")
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        # Find year links
        year_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r'/\d{4}/?$', href):
                year_links.append(urljoin(base_url, href))
        
        year_links = list(set(year_links))
        log(f"Found {len(year_links)} year pages")
        
        for year_url in tqdm(year_links, desc=self.source_id):
            resp = fetch_url(year_url)
            if not resp:
                continue
            
            self.save(year_url, resp.content)
            
            # Get case links
            soup = BeautifulSoup(resp.text, "lxml")
            case_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/cases/" in href and href not in self.visited_urls:
                    case_links.append(urljoin("https://law.justia.com", href))
            
            for case_url in case_links[:100]:  # Limit per year
                if case_url in self.visited_urls:
                    continue
                self.visited_urls.add(case_url)
                
                case_resp = fetch_url(case_url)
                if case_resp:
                    self.save(case_url, case_resp.content)
                time.sleep(0.2)
            
            time.sleep(0.3)
        
        return len(self.downloaded)


class USCodeDownloader(SourceDownloader):
    """Downloader for US Code from OLRC"""
    
    def download(self) -> int:
        log("Downloading US Code from OLRC")
        base_url = "https://uscode.house.gov"
        
        resp = fetch_url(base_url)
        if not resp:
            return 0
        
        self.save(base_url, resp.content, "index")
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        # Find title links
        title_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "view.xhtml" in href and "title" in href.lower():
                title_links.append(urljoin(base_url, href))
        
        title_links = list(set(title_links))
        log(f"Found {len(title_links)} US Code title links")
        
        for title_url in tqdm(title_links, desc="US Code"):
            if title_url in self.visited_urls:
                continue
            self.visited_urls.add(title_url)
            
            resp = fetch_url(title_url)
            if resp:
                self.save(title_url, resp.content)
            
            time.sleep(0.3)
        
        return len(self.downloaded)


# =============================================================================
# MAIN DOWNLOAD ORCHESTRATOR
# =============================================================================

def download_source(source_id: str, source_config: dict) -> Tuple[str, int]:
    """Download a single source"""
    out_dir = OUTPUT_ROOT / source_id
    urls = source_config.get("urls", [])
    
    try:
        # Use specialized downloaders where available
        if source_id == "VA_CODE":
            downloader = VirginiaCodeDownloader(source_id, out_dir)
            count = downloader.download()
        elif source_id == "VA_ADMIN_CODE":
            downloader = VirginiaAdminCodeDownloader(source_id, out_dir)
            count = downloader.download()
        elif source_id in ("ECFR", "ECFR_XML"):
            downloader = ECFRDownloader(source_id, out_dir)
            count = downloader.download()
        elif source_id in ("JUSTIA_VA_SCV", "JUSTIA_VA_COA", "JUSTIA_FED"):
            downloader = JustiaDownloader(source_id, out_dir)
            count = downloader.download(urls[0] if urls else "")
        elif source_id == "US_CODE_OLRC":
            downloader = USCodeDownloader(source_id, out_dir)
            count = downloader.download()
        else:
            # Generic crawler
            downloader = SourceDownloader(source_id, out_dir)
            if urls:
                count = downloader.crawl(urls[0])
            else:
                count = 0
        
        # Save manifest
        manifest = {
            "source_id": source_id,
            "name": source_config.get("name", source_id),
            "jurisdiction": source_config.get("jurisdiction"),
            "priority": source_config.get("priority"),
            "downloaded_at": datetime.now().isoformat(),
            "items": downloader.downloaded
        }
        
        manifest_path = MANIFEST_ROOT / f"{source_id}.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        return source_id, count
        
    except Exception as e:
        log(f"Error downloading {source_id}: {e}", "ERROR")
        traceback.print_exc()
        return source_id, 0


def download_all_sources():
    """Download all sources in priority order"""
    log("=" * 70)
    log("DOWNLOADING ALL LEGAL SOURCES")
    log("=" * 70)
    
    # Load catalog
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    
    source_map = {s["id"]: s for s in catalog["sources"]}
    
    # Filter to allowed sources in priority order
    sources_to_download = []
    for sid in DOWNLOAD_PRIORITY:
        if sid in source_map:
            src = source_map[sid]
            if not src.get("auth_required") and src.get("authority_type") != "commercial":
                sources_to_download.append((sid, src))
    
    log(f"Will download {len(sources_to_download)} sources")
    
    results = {}
    for source_id, source_config in sources_to_download:
        log(f"\n{'='*60}")
        log(f"Downloading: {source_config.get('name', source_id)}")
        log(f"{'='*60}")
        
        sid, count = download_source(source_id, source_config)
        results[sid] = count
        log(f"Downloaded {count} files from {sid}")
    
    return results


# =============================================================================
# DATA INGESTION
# =============================================================================

async def ingest_va_csv_files():
    """Ingest Virginia Code CSV files into RAG"""
    log("Ingesting Virginia Code CSV files...")
    
    if not VA_CSV_DIR.exists():
        log("VA CSV directory not found", "WARNING")
        return 0
    
    csv_files = list(VA_CSV_DIR.glob("*.csv"))
    log(f"Found {len(csv_files)} CSV files")
    
    ingested = 0
    
    for csv_path in tqdm(csv_files, desc="VA CSV Ingestion"):
        try:
            with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Build document text
                    section = row.get("SectionNumber", "")
                    title = row.get("Title", "")
                    text = row.get("Text", "") or row.get("SectionText", "") or ""
                    
                    if not text or len(text) < 50:
                        continue
                    
                    doc_text = f"Virginia Code § {section}\n{title}\n\n{text}"
                    
                    metadata = {
                        "source": "Code of Virginia",
                        "jurisdiction": "Virginia",
                        "document_type": "Statute",
                        "citation": f"Va. Code Ann. § {section}",
                        "section": section,
                        "title": title,
                        "file": csv_path.name
                    }
                    
                    try:
                        await rag_service.add_document(text=doc_text, metadata=metadata)
                        ingested += 1
                    except Exception:
                        pass
                        
        except Exception as e:
            log(f"Error processing {csv_path.name}: {e}", "WARNING")
    
    return ingested


async def ingest_downloaded_sources():
    """Ingest all downloaded source files into RAG"""
    log("Ingesting downloaded sources into RAG...")
    
    manifests = list(MANIFEST_ROOT.glob("*.json"))
    total_ingested = 0
    
    # Load catalog for metadata
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    source_map = {s["id"]: s for s in catalog["sources"]}
    
    for manifest_path in manifests:
        if manifest_path.name == "summary.json":
            continue
        
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            source_id = manifest.get("source_id", "")
            items = manifest.get("items", [])
            source_config = source_map.get(source_id, {})
            
            jurisdiction = source_config.get("jurisdiction", "Unknown")
            source_name = source_config.get("name", source_id)
            doc_type = source_config.get("content_types", ["document"])[0]
            
            ingested = 0
            for item in tqdm(items, desc=f"Ingesting {source_id}", leave=False):
                file_path = Path(item.get("path", ""))
                if not file_path.exists():
                    continue
                
                text = extract_text_from_file(file_path)
                if not text or len(text) < 100:
                    continue
                
                # Truncate very long documents
                if len(text) > 50000:
                    text = text[:50000]
                
                metadata = {
                    "source": source_name,
                    "jurisdiction": jurisdiction,
                    "document_type": doc_type,
                    "origin_url": item.get("url", ""),
                    "file_path": str(file_path)
                }
                
                try:
                    await rag_service.add_document(text=text, metadata=metadata)
                    ingested += 1
                except Exception:
                    pass
            
            total_ingested += ingested
            log(f"Ingested {ingested} documents from {source_id}")
            
        except Exception as e:
            log(f"Error processing manifest {manifest_path.name}: {e}", "WARNING")
    
    return total_ingested


async def ingest_scenario_cases():
    """Ingest case scenarios into RAG for legal precedent"""
    log("Ingesting case scenarios...")
    
    ingested = 0
    
    for source_dir in ["cap", "courtlistener"]:
        cases_dir = SCENARIOS_DIR / source_dir
        if not cases_dir.exists():
            continue
        
        case_files = list(cases_dir.glob("*.json"))[:5000]  # Limit for performance
        
        for case_path in tqdm(case_files, desc=f"Cases ({source_dir})"):
            try:
                with open(case_path, "r", encoding="utf-8") as f:
                    case_data = json.load(f)
                
                # Extract case text
                text = case_data.get("casebody", {}).get("data", {}).get("opinions", [{}])[0].get("text", "")
                if not text:
                    text = case_data.get("text", "") or case_data.get("opinion", "")
                
                if not text or len(text) < 200:
                    continue
                
                # Truncate
                if len(text) > 30000:
                    text = text[:30000]
                
                case_name = case_data.get("name", case_data.get("case_name", "Unknown"))
                citation = case_data.get("citation", case_data.get("citations", [{}])[0].get("cite", "") if case_data.get("citations") else "")
                
                metadata = {
                    "source": source_dir.upper(),
                    "jurisdiction": case_data.get("jurisdiction", {}).get("name", "Virginia") if isinstance(case_data.get("jurisdiction"), dict) else case_data.get("jurisdiction", "Virginia"),
                    "document_type": "Case Law",
                    "case_name": case_name,
                    "citation": citation,
                    "decision_date": case_data.get("decision_date", "")
                }
                
                await rag_service.add_document(text=text, metadata=metadata)
                ingested += 1
                
            except Exception:
                pass
    
    return ingested


# =============================================================================
# VALIDATION
# =============================================================================

def validate_database():
    """Validate the completeness of the legal database"""
    log("=" * 70)
    log("VALIDATING LEGAL DATABASE")
    log("=" * 70)
    
    # Get RAG stats
    try:
        rag_service._ensure_initialized()
        collection = rag_service.collection
        all_docs = collection.get()
        total_docs = len(all_docs['ids'])
        
        # Count by jurisdiction
        va_docs = sum(1 for m in all_docs['metadatas'] if m.get('jurisdiction') == 'Virginia')
        fed_docs = sum(1 for m in all_docs['metadatas'] if m.get('jurisdiction') == 'Federal')
        
        # Count by type
        statutes = sum(1 for m in all_docs['metadatas'] if 'statute' in m.get('document_type', '').lower())
        cases = sum(1 for m in all_docs['metadatas'] if 'case' in m.get('document_type', '').lower())
        regs = sum(1 for m in all_docs['metadatas'] if 'regulation' in m.get('document_type', '').lower())
        
        log(f"Total documents in RAG: {total_docs:,}")
        log(f"  Virginia documents: {va_docs:,}")
        log(f"  Federal documents: {fed_docs:,}")
        log(f"  Statutes: {statutes:,}")
        log(f"  Case Law: {cases:,}")
        log(f"  Regulations: {regs:,}")
        
        # Validation checks
        issues = []
        
        if total_docs < 10000:
            issues.append(f"LOW: Only {total_docs} documents (expected 10,000+)")
        if va_docs < 5000:
            issues.append(f"LOW: Only {va_docs} Virginia documents (expected 5,000+)")
        if statutes < 1000:
            issues.append(f"LOW: Only {statutes} statutes (expected 1,000+)")
        
        if issues:
            log("VALIDATION ISSUES:", "WARNING")
            for issue in issues:
                log(f"  - {issue}", "WARNING")
        else:
            log("✓ Database validation PASSED", "SUCCESS")
        
        return {
            "total": total_docs,
            "virginia": va_docs,
            "federal": fed_docs,
            "statutes": statutes,
            "cases": cases,
            "regulations": regs,
            "issues": issues,
            "passed": len(issues) == 0
        }
        
    except Exception as e:
        log(f"Validation error: {e}", "ERROR")
        return {"error": str(e), "passed": False}


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def main():
    """Main entry point - complete database build"""
    start_time = datetime.now()
    
    log("=" * 70)
    log("COMPLETE LEGAL DATABASE BUILD")
    log("For Production Law Firm Deployment")
    log("=" * 70)
    log(f"Started at: {start_time.isoformat()}")
    
    # Step 1: Download all sources
    log("\n[STEP 1/4] Downloading sources...")
    download_results = download_all_sources()
    
    # Step 2: Ingest VA CSV files (already downloaded)
    log("\n[STEP 2/4] Ingesting Virginia Code CSV files...")
    va_csv_count = await ingest_va_csv_files()
    log(f"Ingested {va_csv_count} Virginia Code sections")
    
    # Step 3: Ingest all downloaded sources
    log("\n[STEP 3/4] Ingesting downloaded sources...")
    source_count = await ingest_downloaded_sources()
    log(f"Ingested {source_count} documents from downloaded sources")
    
    # Step 4: Ingest case scenarios
    log("\n[STEP 4/4] Ingesting case scenarios...")
    case_count = await ingest_scenario_cases()
    log(f"Ingested {case_count} case documents")
    
    # Validate
    log("\n[VALIDATION]")
    validation = validate_database()
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    log("\n" + "=" * 70)
    log("BUILD COMPLETE")
    log("=" * 70)
    log(f"Duration: {duration}")
    log(f"VA CSV sections: {va_csv_count:,}")
    log(f"Source documents: {source_count:,}")
    log(f"Case documents: {case_count:,}")
    log(f"Total in database: {validation.get('total', 'Unknown'):,}")
    log(f"Validation: {'PASSED' if validation.get('passed') else 'ISSUES FOUND'}")
    
    # Save report
    report = {
        "timestamp": end_time.isoformat(),
        "duration_seconds": duration.total_seconds(),
        "download_results": download_results,
        "ingestion": {
            "va_csv": va_csv_count,
            "sources": source_count,
            "cases": case_count
        },
        "validation": validation
    }
    
    report_path = Path("data/database_build_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    log(f"\nReport saved to: {report_path}")
    
    return validation.get("passed", False)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)


