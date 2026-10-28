"""
Document Reader Service
Layout-aware document parsing using Unstructured
"""
import io
from pathlib import Path
from typing import Optional

from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("document_reader")


class DocumentReaderService:
    """Service for layout-aware document parsing with Unstructured"""

    def __init__(self):
        self.logger = logger
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if Unstructured is available"""
        if self._available is not None:
            return self._available
        if not settings.DOCUMENT_READER_ENABLED:
            self._available = False
            return False
        try:
            from unstructured.partition.auto import partition
            self._available = True
            return True
        except ImportError as e:
            self.logger.warning(f"Unstructured not installed: {e}")
            self._available = False
            return False

    def parse_document(self, raw_bytes: bytes, filename: str) -> str:
        """
        Parse document with layout awareness using Unstructured.

        Args:
            raw_bytes: Raw file content
            filename: Original filename (for type detection)

        Returns:
            Extracted text, or empty string on failure
        """
        if not settings.DOCUMENT_READER_ENABLED or not self.is_available():
            return ""

        if not raw_bytes:
            return ""

        ext = (Path(filename).suffix or "").lower()
        supported = {".pdf", ".docx", ".html", ".htm", ".md", ".txt"}
        if ext not in supported:
            return ""

        try:
            from unstructured.partition.auto import partition

            file_obj = io.BytesIO(raw_bytes)
            elements = partition(file=file_obj, metadata_filename=filename)

            if not elements:
                return ""

            # Concatenate element text in order (preserves layout/reading order)
            parts = []
            for elem in elements:
                if hasattr(elem, "text") and elem.text:
                    parts.append(elem.text.strip())
            text = "\n\n".join(parts).strip()
            if text:
                self.logger.info(f"Unstructured extracted {len(text)} chars from {filename}")
            return text
        except Exception as e:
            self.logger.warning(f"Unstructured parse failed for {filename}: {e}")
            return ""


document_reader_service = DocumentReaderService()
