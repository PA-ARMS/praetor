#!/usr/bin/env python3
"""
POST a tiny .txt to /api/rag/upload-document so you can confirm extraction + indexing.

Restart the backend after pulling code changes, then:
  python scripts/test_rag_upload_http.py
  python scripts/test_rag_upload_http.py --base http://192.168.x.x:5001
"""
import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        default="http://127.0.0.1:5001",
        help="Backend base URL (no trailing slash)",
    )
    args = parser.parse_args()

    try:
        import httpx
    except ImportError:
        print("Install httpx: pip install httpx")
        return 1

    body = (
        "Verification upload. Party Alpha owes Party Beta $2,500.00 by March 1, 2026. "
        "Email contact: verifier@example.com. Case style: Smith v. Jones."
    )
    files = {"file": ("verify_upload.txt", body.encode("utf-8"), "text/plain")}
    data = {
        "jurisdiction": "Virginia",
        "perform_ai_understanding": "false",
        "analyze_against_scenarios": "false",
    }

    url = f"{args.base.rstrip('/')}/api/rag/upload-document"
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(url, files=files, data=data)

    print("HTTP", r.status_code, url)
    if r.status_code != 200:
        print(r.text)
        return 1

    j = r.json()
    print("indexed:", j.get("indexed"), "text_length:", j.get("text_length"))
    ed = j.get("extracted_data") or {}
    print("methods_used:", ed.get("methods_used"))
    if ed.get("patterns"):
        print("patterns (sample):", {k: v[:2] for k, v in ed["patterns"].items() if v})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
