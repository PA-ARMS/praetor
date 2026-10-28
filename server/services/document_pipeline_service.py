"""
Document Pipeline Service
Orchestrates extraction and enrichment for document uploads
"""
import io
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

# Minimum characters to accept extracted text (short orders, captions)
MIN_EXTRACTED_CHARS = 20

from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("document_pipeline")

# Filenames that often indicate multi-part PDFs (exhibits first → bad head-only OCR).
_LITIGATION_NAME_KEYS = (
    "motion",
    "nonsuit",
    "dismiss",
    "exhibit",
    "complaint",
    "brief",
    "response",
    "opposition",
    "pleading",
    "memorandum",
    "court",
    "petition",
    "judgment",
    "order",
    "notice",
)

# Raster images: OCR only (Tesseract then EasyOCR)
IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".jfif", ".webp", ".tif", ".tiff", ".bmp"}
)


class DocumentPipelineService:
    """Orchestrates document extraction and enrichment"""

    def __init__(self):
        self.logger = logger

    async def process_document(
        self,
        raw: bytes,
        filename: str,
        ext: str,
        skip_llm_structured: bool = False,
    ) -> Tuple[str, Dict, Optional[str]]:
        """
        Process document: extract text, enrich with summary and entities.

        Args:
            raw: Raw file bytes
            filename: Original filename
            ext: File extension (e.g. ".pdf")
            skip_llm_structured: If True, skip LLM JSON in structured extraction (e.g. when AI understanding runs next).

        Returns:
            (text, pre_metadata, parse_error)
            parse_error is None on success.
        """
        text, ocr_metadata, parse_error = self._extract_text(raw, filename, ext)
        if parse_error:
            return ("", {}, parse_error)

        if not text or len(text.strip()) < MIN_EXTRACTED_CHARS:
            return (
                text or "",
                {},
                parse_error or f"Insufficient text extracted (need at least {MIN_EXTRACTED_CHARS} characters)",
            )

        # Normalize whitespace
        text = text.strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {3,}", " ", text)

        # Enrichment: summarization (every document) and entity extraction
        pre_metadata = {}
        summary = ""
        if settings.SUMMARIZATION_MODEL_ENABLED:
            try:
                from server.services.summarization_service import summarization_service
                if summarization_service.is_available():
                    excerpt = self._excerpt_for_summarization(text, filename)
                    summary = summarization_service.summarize(
                        excerpt, max_length=150, min_length=30
                    )
            except Exception as e:
                self.logger.warning(f"Summarization failed: {e}")
        # Ensure every document has a summary: use BART result or fallback (first sentences)
        if summary:
            pre_metadata["summary"] = summary
        else:
            pre_metadata["summary"] = self._fallback_summary(text, filename=filename)

        try:
            from server.services.structured_document_extraction_service import (
                structured_document_extraction_service,
            )

            extracted_bundle = await structured_document_extraction_service.extract_all(
                text,
                filename,
                skip_llm=skip_llm_structured,
            )
            pre_metadata["entities"] = extracted_bundle.get("entities") or {}
            pre_metadata["extracted_data"] = extracted_bundle
            pre_metadata["structured_extraction_summary"] = (
                structured_document_extraction_service.build_metadata_summary(
                    extracted_bundle
                )
            )
        except Exception as e:
            self.logger.warning(f"Structured extraction failed: {e}")
            pre_metadata["entities"] = {}
            pre_metadata["extracted_data"] = {
                "patterns": {},
                "entities": {},
                "llm_structured": None,
                "methods_used": ["error"],
                "text_quality_score": 0.0,
                "error": str(e)[:500],
            }
            pre_metadata["structured_extraction_summary"] = "structured_extraction_failed"

        pre_metadata["ocr_metadata"] = ocr_metadata
        return (text, pre_metadata, None)

    def _filename_suggests_litigation(self, filename: str) -> bool:
        if not filename:
            return False
        low = filename.lower()
        return any(k in low for k in _LITIGATION_NAME_KEYS)

    def _excerpt_for_summarization(self, text: str, filename: str, max_chars: int = 10000) -> str:
        """Prefer head+mid+tail for long litigation PDFs so BART is not fed exhibit-only noise."""
        if len(text) <= max_chars:
            return text
        if not self._filename_suggests_litigation(filename):
            return text[:max_chars]
        third = max_chars // 3
        head = text[:third]
        mid_start = max(0, len(text) // 2 - third // 2)
        mid = text[mid_start : mid_start + third]
        tail = text[-third:]
        return (
            head
            + "\n\n[... omitted middle of document ...]\n\n"
            + mid
            + "\n\n[... omitted ...]\n\n"
            + tail
        )

    def _fallback_summary(self, text: str, max_chars: int = 400, filename: str = "") -> str:
        """Produce a short extract when BART is unavailable or fails. Every document gets a summary."""
        if not text or not text.strip():
            return "No summary available."
        text = text.strip()
        # Long filings: harvest caption-like lines from anywhere (head may be exhibit OCR).
        if self._filename_suggests_litigation(filename) and len(text) > 3000:
            cue = (
                "court",
                "plaintiff",
                "defendant",
                "motion",
                "exhibit",
                "case no",
                "cause no",
                " vs.",
                " v.",
                " nonsuit",
                "dismiss",
                "response",
                "petition",
            )
            hits: list[str] = []
            for line in text.splitlines():
                lo = line.lower()
                if any(w in lo for w in cue):
                    s = line.strip()
                    if len(s) > 8:
                        hits.append(s)
                if sum(len(x) + 1 for x in hits) > max_chars * 3:
                    break
            if hits:
                blob = " ".join(hits)
                if len(blob) >= 25:
                    return blob[:max_chars] + ("..." if len(blob) > max_chars else "")
        # Split on sentence boundaries; take first 2–3 sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        parts = [s.strip() for s in sentences[:3] if s.strip()]
        summary = " ".join(parts).strip()
        if len(summary) >= 15:
            return summary[:max_chars] + ("..." if len(summary) > max_chars else "")
        return text[:max_chars].strip() + ("..." if len(text) > max_chars else "")

    def _extract_text(
        self,
        raw: bytes,
        filename: str,
        ext: str,
    ) -> Tuple[Optional[str], Dict, Optional[str]]:
        """Extract text from document. Returns (text, ocr_metadata, parse_error)."""
        ocr_metadata = {"used": False}

        if ext in IMAGE_EXTENSIONS:
            return self._extract_image(raw, ocr_metadata)

        if ext in [".txt", ".md"]:
            try:
                text = raw.decode("utf-8", errors="ignore")
                return (text, ocr_metadata, None)
            except Exception as e:
                return (None, ocr_metadata, str(e))

        if ext in [".html", ".htm"]:
            # Best: try Unstructured first (layout-aware), then BeautifulSoup
            if settings.DOCUMENT_READER_ENABLED:
                try:
                    from server.services.document_reader_service import document_reader_service
                    if document_reader_service.is_available():
                        layout_text = document_reader_service.parse_document(raw, filename)
                        if layout_text and len(layout_text.strip()) >= 30:
                            return (layout_text.strip(), ocr_metadata, None)
                except Exception as e:
                    self.logger.warning(f"Unstructured HTML failed: {e}")
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(raw.decode("utf-8", errors="ignore"), "lxml")
                for tag in soup(["script", "style", "nav", "header", "footer"]):
                    tag.extract()
                text = soup.get_text("\n", strip=True)
                return (text, ocr_metadata, None)
            except Exception as e:
                return (None, ocr_metadata, str(e))

        if ext == ".pdf":
            return self._extract_pdf(raw, filename, ocr_metadata)

        if ext == ".docx":
            # Best: try Unstructured first (layout/tables), then python-docx
            if settings.DOCUMENT_READER_ENABLED:
                try:
                    from server.services.document_reader_service import document_reader_service
                    if document_reader_service.is_available():
                        layout_text = document_reader_service.parse_document(raw, filename)
                        if layout_text and len(layout_text.strip()) >= 30:
                            return (layout_text.strip(), ocr_metadata, None)
                except Exception as e:
                    self.logger.warning(f"Unstructured DOCX failed: {e}")
            try:
                from docx import Document
                doc = Document(io.BytesIO(raw))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                table_texts = []
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if cell.text.strip():
                                table_texts.append(cell.text.strip())
                text = "\n".join(paragraphs + table_texts).strip()
                return (text, ocr_metadata, None)
            except Exception as e:
                return (None, ocr_metadata, str(e))

        if ext == ".pptx":
            try:
                from pptx import Presentation
                prs = Presentation(io.BytesIO(raw))
                chunks = []
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            chunks.append(shape.text)
                text = "\n".join(chunks)
                return (text, ocr_metadata, None)
            except Exception as e:
                return (None, ocr_metadata, str(e))

        if ext in [".xlsx", ".xls", ".csv"]:
            try:
                import pandas as pd
                if ext == ".csv":
                    df = pd.read_csv(io.BytesIO(raw), encoding_errors="ignore")
                else:
                    df = pd.read_excel(io.BytesIO(raw))
                text = df.to_csv(index=False)
                return (text, ocr_metadata, None)
            except Exception as e:
                return (None, ocr_metadata, str(e))

        # Fallback
        try:
            text = raw.decode("utf-8", errors="ignore")
            return (text, ocr_metadata, None)
        except Exception as e:
            return (None, ocr_metadata, str(e))

    def _extract_image(
        self,
        raw: bytes,
        ocr_metadata: Dict,
    ) -> Tuple[Optional[str], Dict, Optional[str]]:
        """PNG/JPEG/etc.: Tesseract first, EasyOCR if weak or missing."""
        candidates: list[tuple[str, str]] = []

        try:
            from server.services.ocr_service import ocr_service

            if ocr_service.is_available():
                t = ocr_service.extract_text_from_image(raw, page_num=0)
                if t and len(t.strip()) >= 15:
                    candidates.append(("tesseract_image", t.strip()))
        except Exception as e:
            self.logger.warning(f"Tesseract image OCR failed: {e}")

        if settings.NEURAL_OCR_ENABLED:
            try:
                from server.services.neural_ocr_service import neural_ocr_service

                if neural_ocr_service.is_available():
                    r = neural_ocr_service.extract_text_from_image_bytes(raw)
                    nt = (r.get("text") or "").strip()
                    if nt and len(nt) >= 15:
                        candidates.append(("easyocr_image", nt))
            except Exception as e:
                self.logger.warning(f"EasyOCR image failed: {e}")

        if not candidates:
            return (
                None,
                ocr_metadata,
                "Could not extract text from image (try a clearer scan or install Tesseract).",
            )

        best = max(candidates, key=lambda x: len(x[1]))
        ocr_metadata["used"] = True
        if best[0].startswith("easyocr"):
            ocr_metadata["neural_ocr"] = True
        text = best[1]
        if len(text.strip()) < MIN_EXTRACTED_CHARS:
            return (text, ocr_metadata, "Insufficient text extracted from image")
        return (text, ocr_metadata, None)

    def _extract_pdf(
        self,
        raw: bytes,
        filename: str,
        ocr_metadata: Dict,
    ) -> Tuple[Optional[str], Dict, Optional[str]]:
        """Extract text from PDF using best methods: text extractors first, then layout/OCR."""
        candidates: list[tuple[str, str]] = []  # (source, text)
        file_size_mb = len(raw) / (1024 * 1024)
        max_ocr_pages = 20 if file_size_mb > 3 else 50

        # 1. pdfplumber (fast, good for text PDFs and tables)
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                out = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if not page_text and page.extract_tables():
                        page_text = "\n".join(
                            "\n".join(str(cell) or "" for cell in row)
                            for table in page.extract_tables()
                            for row in table
                        )
                    if page_text and page_text.strip():
                        out.append(page_text.strip())
                if out:
                    t = "\n".join(out).strip()
                    if len(t) >= 30:
                        candidates.append(("pdfplumber", t))
        except Exception as e:
            self.logger.warning(f"pdfplumber failed: {e}")

        # 2. PyMuPDF (fast, good for many PDFs)
        try:
            import fitz
            doc = fitz.open(stream=raw, filetype="pdf")
            out = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                if not page_text:
                    blocks = page.get_text("blocks")
                    page_text = "\n".join(block[4] for block in blocks if block[4])
                if page_text and page_text.strip():
                    out.append(page_text.strip())
            doc.close()
            if out:
                t = "\n".join(out).strip()
                if len(t) >= 30:
                    candidates.append(("pymupdf", t))
        except Exception as e:
            self.logger.warning(f"PyMuPDF failed: {e}")

        # 3. Unstructured (layout-aware; best for complex layouts)
        if settings.DOCUMENT_READER_ENABLED:
            try:
                from server.services.document_reader_service import document_reader_service
                if document_reader_service.is_available():
                    t = document_reader_service.parse_document(raw, filename)
                    if t and len(t.strip()) >= 30:
                        candidates.append(("unstructured", t.strip()))
            except Exception as e:
                self.logger.warning(f"Document reader failed: {e}")

        # 4. PyPDF2 fallback
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(raw))
            out = [p.extract_text().strip() for p in reader.pages if p.extract_text() and p.extract_text().strip()]
            if out:
                t = "\n".join(out).strip()
                if len(t) >= 30:
                    candidates.append(("pypdf2", t))
        except Exception as e:
            self.logger.warning(f"PyPDF2 failed: {e}")

        # 5. OCR (for scanned/image PDFs)
        if not candidates or max(len(c[1]) for c in candidates) < 100:
            try:
                from server.services.ocr_service import ocr_service
                if ocr_service.is_available():
                    ocr_result = ocr_service.extract_text_from_pdf_images(raw, max_pages=max_ocr_pages)
                    ocr_text = (ocr_result.get("text") or "").strip()
                    if ocr_text and len(ocr_text) >= 30:
                        candidates.append(("tesseract", ocr_text))
                        ocr_metadata.update({
                            "used": True,
                            "pages_processed": ocr_result.get("pages_processed", 0),
                            "pages_with_text": ocr_result.get("pages_with_text", 0),
                            "total_pages": ocr_result.get("total_pages", 0),
                        })
            except Exception as e:
                self.logger.warning(f"Tesseract OCR failed: {e}")

        best_len = max((len(c[1]) for c in candidates), default=0)
        if settings.NEURAL_OCR_ENABLED and (not candidates or best_len < 150):
            try:
                from server.services.neural_ocr_service import neural_ocr_service
                if neural_ocr_service.is_available():
                    result = neural_ocr_service.extract_text_from_pdf(raw, max_pages=max_ocr_pages)
                    neural_text = (result.get("text") or "").strip()
                    if neural_text and len(neural_text) >= 30:
                        candidates.append(("easyocr", neural_text))
                        ocr_metadata.update({
                            "used": True,
                            "neural_ocr": True,
                            "pages_processed": result.get("pages_processed", 0),
                            "pages_with_text": result.get("pages_with_text", 0),
                            "total_pages": result.get("total_pages", 0),
                        })
            except Exception as e:
                self.logger.warning(f"Neural OCR failed: {e}")

        # Pick best: longest extraction (most content)
        text = None
        if candidates:
            best = max(candidates, key=lambda x: len(x[1]))
            text = best[1]
            self.logger.info(f"PDF extraction: {best[0]} produced {len(text)} chars (from {len(candidates)} methods)")

        # 8. Table extraction - append to body
        if text and settings.TABLE_EXTRACTION_ENABLED:
            try:
                from server.services.table_extraction_service import table_extraction_service
                if table_extraction_service.is_available():
                    tables = table_extraction_service.extract_tables(raw, max_pages=max_ocr_pages)
                    if tables:
                        table_texts = [t["text"] for t in tables if t.get("text")]
                        if table_texts:
                            text = text + "\n\n[Extracted Tables]\n\n" + "\n\n".join(table_texts)
                            self.logger.info(f"Appended {len(tables)} tables to document")
            except Exception as e:
                self.logger.warning(f"Table extraction failed: {e}")

        if not text or len(text.strip()) < MIN_EXTRACTED_CHARS:
            return (
                text,
                ocr_metadata,
                "Could not extract sufficient text from PDF. Tried all available methods.",
            )
        return (text, ocr_metadata, None)


document_pipeline_service = DocumentPipelineService()
