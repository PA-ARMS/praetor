import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

CATALOG_PATH = Path("config/source_catalog.json")
OUTPUT_ROOT = Path("data/sources")
MANIFEST_ROOT = Path("data/manifests")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

ALLOWED_CONTENT_TYPES = {
    "text/html",
    "application/pdf",
    "application/xml",
    "text/xml"
}

MAX_PER_SOURCE = int(os.environ.get("MAX_PER_SOURCE", "500"))  # safety cap
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_REQUESTS = float(os.environ.get("CRAWL_DELAY", "5.0")) # Increased default delay


def is_allowed_source(src: dict) -> bool:
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


def guess_extension(content_type: str) -> str:
    if not content_type:
        return ".bin"
    if "html" in content_type:
        return ".html"
    if "pdf" in content_type:
        return ".pdf"
    if "xml" in content_type:
        return ".xml"
    return ".bin"


def fetch_url(url: str) -> requests.Response:
    return requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)


def crawl_site(source_id: str, base_url: str, out_dir: Path, limit: int) -> list[dict]:
    visited = set()
    queue = [base_url]
    manifest = []
    base_domain = domain_from_url(base_url)

    pbar = tqdm(total=limit, desc=f"{source_id} crawl", unit="file")

    while queue and len(manifest) < limit:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = fetch_url(url)
        except Exception:
            continue

        ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype not in ALLOWED_CONTENT_TYPES and not url.lower().endswith(".pdf"):
            # Skip unsupported types
            continue

        ext = guess_extension(ctype)
        parsed = urlparse(url)
        rel_path = sanitize_filename(parsed.path.strip("/")) or "index"
        if rel_path.endswith("/"):
            rel_path += "index"
        file_path = out_dir / f"{rel_path}{ext}"

        try:
            save_bytes(file_path, resp.content)
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
                    next_url = urljoin(url, href)
                    parsed_next = urlparse(next_url)
                    if parsed_next.scheme.startswith("http") and parsed_next.netloc.lower() == base_domain:
                        if next_url not in visited:
                            queue.append(next_url)
            except Exception:
                pass

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    pbar.close()
    return manifest


def download_bulk(source_id: str, url: str, out_dir: Path) -> list[dict]:
    manifest = []
    try:
        resp = fetch_url(url)
        if resp.status_code == 200:
            filename = sanitize_filename(url.split("/")[-1] or f"{source_id}_bulk.zip")
            if not filename.endswith((".zip", ".xml", ".json")):
                filename += ".zip"
            file_path = out_dir / filename
            save_bytes(file_path, resp.content)
            manifest.append({
                "url": url,
                "path": str(file_path),
                "content_type": resp.headers.get("Content-Type", ""),
                "status": resp.status_code,
                "size": len(resp.content)
            })
    except Exception:
        pass
    return manifest


def run():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Select sources: non-commercial, no auth, priority 1–2 (most authoritative), Federal & Virginia
    # Filter specifically for VA_COURTS_SELFHELP if other sources are already good, but here we just run it
    target_id = os.environ.get("TARGET_SOURCE_ID")
    sources = [
        s for s in catalog["sources"]
        if is_allowed_source(s) 
        and s.get("priority", 5) <= 2 
        and s.get("jurisdiction") in ("Federal", "Virginia")
        and (not target_id or s["id"] == target_id)
    ]

    all_results = {}

    for src in sources:
        sid = src["id"]
        urls = src.get("urls", [])
        access = src.get("access_method", [])

        out_dir = OUTPUT_ROOT / sid
        out_dir.mkdir(parents=True, exist_ok=True)

        source_manifest = []

        # Prefer bulk endpoints where available
        if "bulk_zip" in access or "xml" in access:
            for u in urls:
                if any(key in u.lower() for key in ["bulk", "xml"]):
                    source_manifest.extend(download_bulk(sid, u, out_dir))

        # Crawl website HTML for canonical sites (cap with limit)
        if "website_html" in access:
            # Use first canonical URL as entry
            if urls:
                source_manifest.extend(crawl_site(sid, urls[0], out_dir, limit=min(MAX_PER_SOURCE, 300)))

        # PDFs may not be discovered without crawling; crawling covers linked PDFs on-site

        # Save per-source manifest
        manifest_path = MANIFEST_ROOT / f"{sid}.json"
        with open(manifest_path, "w", encoding="utf-8") as mf:
            json.dump({
                "source_id": sid,
                "name": src.get("name"),
                "jurisdiction": src.get("jurisdiction"),
                "priority": src.get("priority"),
                "items": source_manifest
            }, mf, ensure_ascii=False, indent=2)

        all_results[sid] = {
            "count": len(source_manifest),
            "manifest": str(manifest_path)
        }

    # Write summary
    summary_path = MANIFEST_ROOT / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as sf:
        json.dump(all_results, sf, ensure_ascii=False, indent=2)

    print(f"Done. Summary: {summary_path}")


if __name__ == "__main__":
    run()

