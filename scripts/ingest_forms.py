import os
import asyncio
from pathlib import Path
from typing import Optional

import pdfplumber
from bs4 import BeautifulSoup

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from server.services.rag_service import rag_service  # noqa: E402

FORMS_DIR = Path("data/forms")


def read_text(path: Path) -> Optional[str]:
    p = str(path).lower()
    try:
        if p.endswith(".pdf"):
            out = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    out.append(page.extract_text() or "")
            txt = "\n".join(out).strip()
            return txt or None
        if p.endswith(".html") or p.endswith(".htm"):
            html = path.read_text(encoding="utf-8", errors="ignore")
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.extract()
            return soup.get_text("\n", strip=True)
        if p.endswith(".txt"):
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    return None


async def main():
    if not FORMS_DIR.exists():
        print("No forms directory found.")
        return
    count = 0
    for root, _, files in os.walk(FORMS_DIR):
        for name in files:
            if not name.lower().endswith((".pdf", ".html", ".htm", ".txt")):
                continue
            path = Path(root) / name
            text = read_text(path)
            if not text or len(text) < 100:
                continue
            metadata = {
                "source": "Firm Forms",
                "jurisdiction": "Virginia",
                "file_path": str(path)
            }
            try:
                await rag_service.add_document(text=text, metadata=metadata)
                count += 1
            except Exception:
                continue
    stats = rag_service.get_collection_stats()
    print(f"Ingested forms: {count}")
    print("RAG stats:", stats)


if __name__ == "__main__":
    asyncio.run(main())

