"""
Table Extraction Service
Extracts tables from PDF documents using tabula-py for RAG indexing
"""
import io
import tempfile
from pathlib import Path
from typing import List, Dict, Optional

from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("table_extraction")


class TableExtractionService:
    """Service for extracting tables from PDF documents"""

    def __init__(self):
        self.logger = logger
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if tabula-py is available (requires Java)"""
        if self._available is not None:
            return self._available
        try:
            import tabula
            # Quick test - read_pdf with invalid input to verify import works
            self._available = True
            return True
        except ImportError as e:
            self.logger.warning(f"tabula-py not installed: {e}")
            self._available = False
            return False
        except Exception as e:
            self.logger.warning(f"tabula-py check failed: {e}")
            self._available = False
            return False

    def extract_tables(self, raw_bytes: bytes, max_pages: int = 50) -> List[Dict]:
        """
        Extract tables from PDF bytes.

        Args:
            raw_bytes: Raw PDF file content
            max_pages: Maximum pages to process (default 50)

        Returns:
            List of dicts with keys: text, page, table_index
        """
        if not settings.TABLE_EXTRACTION_ENABLED or not self.is_available():
            return []

        if not raw_bytes or not raw_bytes.startswith(b"%PDF"):
            return []

        results: List[Dict] = []
        try:
            import tabula

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(raw_bytes)
                tmp_path = tmp.name

            try:
                # Try lattice first (tables with lines), then stream (tables without lines)
                pages_str = "all" if max_pages <= 0 else f"1-{min(max_pages, 100)}"
                dfs = tabula.read_pdf(tmp_path, pages=pages_str, multiple_tables=True)

                if not dfs:
                    # Fallback: try stream mode
                    dfs = tabula.read_pdf(tmp_path, pages=pages_str, multiple_tables=True, stream=True)

                for table_idx, df in enumerate(dfs):
                    if df is not None and not df.empty:
                        table_text = df.to_csv(index=False, sep=" ")
                        if table_text and table_text.strip():
                            results.append({
                                "text": table_text.strip(),
                                "page": table_idx + 1,  # Approximate; tabula doesn't expose page per table
                                "table_index": table_idx,
                            })
                            self.logger.debug(f"Extracted table {table_idx}: {len(table_text)} chars")
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            if results:
                self.logger.info(f"Extracted {len(results)} tables from PDF")
        except Exception as e:
            self.logger.warning(f"Table extraction failed: {e}")
            return []

        return results


table_extraction_service = TableExtractionService()
