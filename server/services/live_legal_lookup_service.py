"""
Live official-source lookup (no API keys).

Fetches current statute text from allowlisted government sites so chat can
supplement the local RAG corpus. This is not open-web browsing: only official
legal domains are retrieved, and results are labeled as live fetches.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import quote_plus, urlparse

import httpx

from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("live_legal_lookup")

LIS_BASE = "https://law.lis.virginia.gov"
ALLOWED_HOSTS = frozenset(
    {
        "law.lis.virginia.gov",
        "lis.virginia.gov",
        "www.vacourts.gov",
        "vacourts.gov",
        "www.supremecourt.gov",
        "supremecourt.gov",
        "www.govinfo.gov",
        "govinfo.gov",
        "www.congress.gov",
        "congress.gov",
        "uscode.house.gov",
        "www.justice.gov",
        "justice.gov",
    }
)

STATUTE_RE = re.compile(
    r"(?:§\s*|va\.?\s*code\s*(?:§\s*)?|section\s+)?"
    r"(\d+\.\d+(?:\.\d+)?-\d+(?:\.\d+)*(?::\d+)?)",
    re.IGNORECASE,
)
BARE_STATUTE_RE = re.compile(r"\b(\d+\.\d+-\d+(?:\.\d+)*(?::\d+)?)\b")

_SYNONYMS: Optional[Dict[str, List[str]]] = None
_USER_AGENT = (
    "PRAETOR-LegalResearch/1.0 (local firm research; official-source lookup)"
)


def _load_synonyms() -> Dict[str, List[str]]:
    global _SYNONYMS
    if _SYNONYMS is not None:
        return _SYNONYMS
    path = Path(__file__).resolve().parents[2] / "config" / "legal_synonyms.json"
    try:
        _SYNONYMS = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not load legal_synonyms.json: {e}")
        _SYNONYMS = {}
    return _SYNONYMS


def _host_allowed(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in ALLOWED_HOSTS


def extract_statute_citations(query: str) -> List[str]:
    found: List[str] = []
    seen: Set[str] = set()
    for match in STATUTE_RE.finditer(query or ""):
        cite = match.group(1).strip()
        key = cite.lower()
        if key not in seen:
            seen.add(key)
            found.append(cite)
    if found:
        return found[:6]

    q = (query or "").lower()
    synonyms = _load_synonyms()
    for term, expansions in synonyms.items():
        if term.lower() in q:
            for exp in expansions:
                m = BARE_STATUTE_RE.search(str(exp))
                if m:
                    cite = m.group(1)
                    key = cite.lower()
                    if key not in seen:
                        seen.add(key)
                        found.append(cite)
    return found[:6]


def _lis_urls_for_citation(citation: str) -> List[str]:
    cite = citation.strip()
    title = cite.split("-", 1)[0]
    return [
        f"{LIS_BASE}/vacode/{cite}/",
        f"{LIS_BASE}/vacode/title{title}/section{cite}/",
    ]


def _html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return re.sub(r"<[^>]+>", " ", html or "")

    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "form"]):
        tag.decompose()
    main = (
        soup.find("article")
        or soup.find(id=re.compile(r"content|main|statute", re.I))
        or soup.find("main")
        or soup.body
        or soup
    )
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _source_record(url: str, text: str, citation: str = "") -> Dict:
    fetched_at = datetime.now(timezone.utc).isoformat()
    snippet = text[:8000]
    title_line = snippet.split("\n", 1)[0][:160] if snippet else url
    return {
        "id": f"live:{url}",
        "text": snippet,
        "metadata": {
            "source": "Virginia LIS (live official fetch)" if "lis.virginia.gov" in url else "Official government site (live fetch)",
            "jurisdiction": "Virginia" if "virginia.gov" in url else "Federal",
            "citation": f"§ {citation}" if citation and not citation.startswith("§") else citation,
            "title": title_line,
            "origin_url": url,
            "document_type": "Statute" if citation else "Official web page",
            "live_fetch": True,
            "fetched_at": fetched_at,
        },
        "distance": 0.0,
    }


async def _fetch_page(client: httpx.AsyncClient, url: str) -> Optional[str]:
    if not _host_allowed(url):
        return None
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return None
        ctype = (resp.headers.get("content-type") or "").lower()
        if "html" not in ctype and "text" not in ctype and "xml" not in ctype:
            return None
        text = _html_to_text(resp.text)
        if len(text) < 120:
            return None
        return text
    except Exception as e:
        logger.info(f"Live fetch failed for {url}: {e}")
        return None


async def _search_official_pages(client: httpx.AsyncClient, query: str, limit: int = 3) -> List[str]:
    """DuckDuckGo HTML search restricted to official LIS (no API key)."""
    q = f"{query[:180]} site:law.lis.virginia.gov"
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
    urls: List[str] = []
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return []
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a.result__a, a.result__url, a[href]"):
            href = (a.get("href") or "").strip()
            if "uddg=" in href:
                from urllib.parse import parse_qs, unquote, urlparse as _up

                qs = parse_qs(_up(href).query)
                raw = qs.get("uddg", [""])[0]
                href = unquote(raw) if raw else href
            if href.startswith("//"):
                href = "https:" + href
            if href.startswith("http") and _host_allowed(href) and href not in urls:
                urls.append(href)
            if len(urls) >= limit:
                break
    except Exception as e:
        logger.info(f"Official-site search failed: {e}")
    return urls


class LiveLegalLookupService:
    async def lookup(self, query: str, max_pages: int = 4) -> List[Dict]:
        if not getattr(settings, "LIVE_LEGAL_LOOKUP_ENABLED", True):
            return []
        query = (query or "").strip()
        if len(query) < 3:
            return []

        timeout = float(getattr(settings, "LIVE_LEGAL_LOOKUP_TIMEOUT_SECONDS", 8) or 8)
        headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
        results: List[Dict] = []
        seen_urls: Set[str] = set()

        citations = extract_statute_citations(query)
        candidate_urls: List[tuple[str, str]] = []  # (url, citation)
        for cite in citations:
            for u in _lis_urls_for_citation(cite):
                candidate_urls.append((u, cite))

        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            if not candidate_urls:
                for u in await _search_official_pages(client, query, limit=3):
                    candidate_urls.append((u, ""))

            for url, cite in candidate_urls:
                if url in seen_urls:
                    continue
                if len(results) >= max_pages:
                    break
                seen_urls.add(url)
                text = await _fetch_page(client, url)
                if not text:
                    continue
                results.append(_source_record(url, text, cite))

        if results:
            logger.info(
                f"Live official lookup: {len(results)} page(s) for query={query[:60]!r} "
                f"citations={citations}"
            )
        return results


live_legal_lookup_service = LiveLegalLookupService()
