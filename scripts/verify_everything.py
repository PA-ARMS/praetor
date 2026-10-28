#!/usr/bin/env python3
"""
Verify Everything - Run checks to ensure the system is working.

Usage:
    python scripts/verify_everything.py
    python scripts/verify_everything.py --tests   # Also run pytest

First run may take 1-2 minutes while BART summarization model loads.
"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_checks() -> list[tuple[str, bool, str]]:
    """Run all verification checks. Returns list of (name, passed, message)."""
    results = []

    # 1. Config
    try:
        from server.config import settings
        assert hasattr(settings, "DOCUMENT_READER_ENABLED") and hasattr(settings, "SUMMARIZATION_MODEL_ENABLED")
        results.append(("Config & pipeline flags", True, "OK"))
    except Exception as e:
        results.append(("Config & pipeline flags", False, str(e)))
        return results  # Stop early if config broken

    # 2. Document pipeline
    try:
        from server.services.document_pipeline_service import document_pipeline_service
        results.append(("Document pipeline service", True, "OK"))
    except Exception as e:
        results.append(("Document pipeline service", False, str(e)))

    # 3. Supporting services
    for name, mod in [
        ("Table extraction", "server.services.table_extraction_service"),
        ("Entity extraction", "server.services.entity_extraction_service"),
        ("Summarization", "server.services.summarization_service"),
        ("Document reader (Unstructured)", "server.services.document_reader_service"),
        ("Neural OCR", "server.services.neural_ocr_service"),
    ]:
        try:
            __import__(mod)
            results.append((name, True, "OK"))
        except Exception as e:
            results.append((name, False, str(e)))

    # 4. RAG routes + Chroma metadata sanitizer
    try:
        from server.routes.rag import router
        from server.services.rag_service import _sanitize_chroma_metadata

        sm = _sanitize_chroma_metadata({"key_points": [], "entities": {"a": 1}, "x": "y"})
        ok = "key_points" not in sm and "entities" in sm and isinstance(sm["entities"], str)
        results.append(("RAG routes + metadata sanitizer", ok, "OK" if ok else "sanitize mismatch"))
    except Exception as e:
        results.append(("RAG routes + metadata sanitizer", False, str(e)))

    # 5. Document understanding with pre-extracted params
    try:
        from server.services.document_understanding_service import document_understanding_service

        async def _check():
            m = await document_understanding_service.understand_document(
                "Short test document about contract law.",
                "test.txt",
                document_type="TXT",
                pre_extracted_summary="Test summary.",
                pre_extracted_entities={"parties": [], "dates": [], "case_numbers": [], "statutes": [], "courts": []},
            )
            return "summary" in m and "entities" in m

        ok = asyncio.run(_check())
        results.append(("Document understanding (pre-extracted)", ok, "OK" if ok else "Missing keys"))
    except Exception as e:
        results.append(("Document understanding (pre-extracted)", False, str(e)))

    # 6. Pipeline fallback summary
    try:
        from server.services.document_pipeline_service import document_pipeline_service
        s = document_pipeline_service._fallback_summary("First sentence. Second sentence. More text here.")
        ok = len(s) > 0
        results.append(("Pipeline fallback summary", ok, "OK" if ok else "Empty"))
    except Exception as e:
        results.append(("Pipeline fallback summary", False, str(e)))

    # 7. Pipeline process_document (TXT) - quick check; BART may load on first run
    try:
        from server.services.document_pipeline_service import document_pipeline_service
        raw = b"This is a sample document for verification. It has multiple sentences. The pipeline should extract and summarize it."
        text, meta, err = asyncio.run(
            document_pipeline_service.process_document(raw, "verify.txt", ".txt")
        )
        ok = (
            err is None
            and len(text) > 0
            and "summary" in meta
            and len(meta.get("summary", "")) > 0
            and "extracted_data" in meta
        )
        results.append(("Pipeline process_document (TXT)", ok, "OK" if ok else (err or "No summary")))
    except Exception as e:
        results.append(("Pipeline process_document (TXT)", False, str(e)))

    # 8. FastAPI app load
    try:
        from server.main import app
        results.append(("FastAPI app", True, "OK"))
    except Exception as e:
        results.append(("FastAPI app", False, str(e)))

    return results


def main() -> int:
    print("=" * 60)
    print("Virginia Legal AI - Verify Everything")
    print("=" * 60)
    print()

    results = run_checks()
    failed = []

    for name, passed, msg in results:
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status}  {name}: {msg}")
        if not passed:
            failed.append(name)

    print()
    if failed:
        print(f"Failed: {', '.join(failed)}")
        if "--tests" in sys.argv:
            print("Skipping pytest due to failures.")
        return 1
    print("All checks passed.")
    print()

    if "--tests" in sys.argv:
        print("Running pytest (tests/test_api.py)...")
        import subprocess
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_api.py", "-v", "--tb=short"],
            cwd=PROJECT_ROOT,
        )
        if r.returncode != 0:
            print("Some tests failed.")
            return r.returncode
        print("Tests passed.")
    else:
        print("Tip: Run with --tests to also run pytest:  python scripts/verify_everything.py --tests")

    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
