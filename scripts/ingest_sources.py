import os
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict

from bs4 import BeautifulSoup
import pdfplumber

# Ensure server modules are importable when running from repo root
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.rag_service import rag_service  # noqa: E402

CATALOG_PATH = Path("config/source_catalog.json")
MANIFEST_ROOT = Path("data/manifests")

# Safety caps (can be overridden by env)
MAX_PER_SOURCE = int(os.environ.get("MAX_INGEST_PER_SOURCE", "200"))
MAX_TOTAL = int(os.environ.get("MAX_INGEST_TOTAL", "2000"))


def load_catalog() -> Dict[str, dict]:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    id_to_source = {s["id"]: s for s in catalog["sources"]}
    return id_to_source


def read_text_from_file(path: Path) -> Optional[str]:
    p = str(path).lower()
    try:
        if p.endswith(".html") or p.endswith(".xhtml") or p.endswith(".htm"):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                html = f.read()
            soup = BeautifulSoup(html, "lxml")
            # Remove nav/script/style
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.extract()
            text = soup.get_text("\n", strip=True)
            return text
        if p.endswith(".pdf"):
            out = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    out.append(page.extract_text() or "")
            txt = "\n".join(out).strip()
            return txt if txt else None
        if p.endswith(".xml"):
            # Basic XML text extraction
            content = path.read_text(encoding="utf-8", errors="ignore")
            soup = BeautifulSoup(content, "lxml-xml")
            txt = soup.get_text("\n", strip=True)
            return txt
    except Exception:
        return None
    return None


async def ingest_manifest(manifest_path: Path, catalog: Dict[str, dict], counters: Dict[str, int]) -> int:
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    source_id = m.get("source_id")
    items = m.get("items", [])

    src_meta = catalog.get(source_id, {})
    jurisdiction = src_meta.get("jurisdiction", "Unknown")
    source_name = src_meta.get("name", source_id)

    count = 0
    for item in items:
        if counters["total"] >= MAX_TOTAL or count >= MAX_PER_SOURCE:
            break
        path = item.get("path")
        url = item.get("url", "")
        if not path or not os.path.exists(path):
            continue
        text = read_text_from_file(Path(path))
        if not text or len(text) < 200:
            continue

        metadata = {
            "source": source_name,
            "jurisdiction": jurisdiction,
            "origin_url": url,
            "file_path": path
        }
        
        # Extract citation from text if available
        # The add_document method will also try to extract, but doing it here
        # allows us to log it during ingestion
        extracted_citation = rag_service._extract_citation_from_text(text)
        if extracted_citation:
            metadata['citation'] = extracted_citation
        
        try:
            await rag_service.add_document(text=text, metadata=metadata)
            count += 1
            counters["total"] += 1
            if extracted_citation:
                print(f"  ✓ Extracted citation: {extracted_citation}")
        except Exception:
            # Skip problematic docs but continue
            continue
    return count


async def main():
    catalog = load_catalog()
    manifests = sorted(MANIFEST_ROOT.glob("*.json"))
    target_id = os.environ.get("TARGET_SOURCE_ID")
    
    # Prioritize official, Virginia and Federal sources first using filename order heuristic
    counters = {"total": 0}
    total_ingested = 0

    for mpath in manifests:
        if mpath.name == "summary.json":
            continue
            
        if target_id and mpath.stem != target_id:
            continue
            
        ingested = await ingest_manifest(mpath, catalog, counters)
        total_ingested += ingested
        print(f"{mpath.name}: +{ingested} (running total: {total_ingested})")
        if counters["total"] >= MAX_TOTAL:
            break

    # Print stats via rag_service
    stats = rag_service.get_collection_stats()
    print("RAG stats:", stats)


if __name__ == "__main__":
    asyncio.run(main())

