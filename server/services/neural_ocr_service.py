"""
Neural OCR Service
Uses EasyOCR for improved extraction from difficult scans
"""
import io
from typing import Dict, Optional

from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("neural_ocr")


class NeuralOCRService:
    """Service for neural OCR using EasyOCR (fallback when Tesseract fails)"""

    def __init__(self):
        self.logger = logger
        self._reader = None
        self._available: Optional[bool] = None

    def _ensure_loaded(self) -> bool:
        """Lazy-load EasyOCR reader"""
        if self._reader is not None:
            return True
        if not settings.NEURAL_OCR_ENABLED:
            return False
        try:
            import easyocr
            import torch
            # Use GPU if available, else CPU
            gpu = torch.cuda.is_available()
            self._reader = easyocr.Reader(["en"], gpu=gpu, verbose=False)
            self._available = True
            self.logger.info(f"EasyOCR loaded (gpu={gpu})")
            return True
        except ImportError as e:
            self.logger.warning(f"EasyOCR not installed: {e}")
            self._available = False
            return False
        except Exception as e:
            self.logger.warning(f"EasyOCR load failed: {e}")
            self._available = False
            return False

    def is_available(self) -> bool:
        """Check if neural OCR is available"""
        if self._available is not None:
            return self._available
        return self._ensure_loaded()

    def extract_text_from_pdf(self, raw_bytes: bytes, max_pages: int = 50) -> Dict:
        """
        Extract text from PDF using EasyOCR (for scanned/image-based PDFs).

        Args:
            raw_bytes: Raw PDF bytes
            max_pages: Maximum pages to process

        Returns:
            Dict with text, pages_processed, pages_with_text, total_pages, errors
        """
        if not settings.NEURAL_OCR_ENABLED or not self._ensure_loaded():
            return {"text": None, "pages_processed": 0, "pages_with_text": 0, "total_pages": 0, "errors": []}

        if not raw_bytes or not raw_bytes.startswith(b"%PDF"):
            return {"text": None, "pages_processed": 0, "pages_with_text": 0, "total_pages": 0, "errors": []}

        try:
            import fitz
            import numpy as np

            doc = fitz.open(stream=raw_bytes, filetype="pdf")
            total_pages = len(doc)
            pages_to_process = min(max_pages or total_pages, total_pages, 50)

            extracted_texts = []
            pages_with_text = 0
            errors = []

            for page_num in range(pages_to_process):
                try:
                    page = doc[page_num]
                    mat = fitz.Matrix(200 / 72, 200 / 72)  # 200 DPI for speed
                    pix = page.get_pixmap(matrix=mat)
                    img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                    if pix.n == 4:
                        img_array = img_array[:, :, :3]  # Drop alpha for EasyOCR

                    result = self._reader.readtext(img_array)
                    page_text = " ".join([item[1] for item in result if item[1].strip()]).strip()

                    if page_text:
                        extracted_texts.append(page_text)
                        pages_with_text += 1

                    pix = None
                except Exception as page_error:
                    errors.append(f"Page {page_num + 1}: {page_error}")

            doc.close()

            combined = "\n\n".join(extracted_texts) if extracted_texts else None
            self.logger.info(f"EasyOCR extracted {len(combined or '')} chars from {pages_with_text}/{pages_to_process} pages")
            return {
                "text": combined,
                "pages_processed": pages_to_process,
                "pages_with_text": pages_with_text,
                "total_pages": total_pages,
                "errors": errors,
            }
        except Exception as e:
            self.logger.warning(f"Neural OCR failed: {e}")
            return {"text": None, "pages_processed": 0, "pages_with_text": 0, "total_pages": 0, "errors": [str(e)]}

    def extract_text_from_image_bytes(self, raw_bytes: bytes) -> Dict:
        """
        OCR a single image file (PNG, JPEG, etc.) using EasyOCR.
        """
        if not settings.NEURAL_OCR_ENABLED or not self._ensure_loaded():
            return {"text": None, "errors": ["Neural OCR disabled or unavailable"]}

        if not raw_bytes:
            return {"text": None, "errors": ["Empty image"]}

        try:
            import io
            import numpy as np
            from PIL import Image

            image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            arr = np.array(image)
            result = self._reader.readtext(arr)
            page_text = " ".join([item[1] for item in result if item[1].strip()]).strip()
            return {
                "text": page_text if page_text else None,
                "errors": [],
            }
        except Exception as e:
            self.logger.warning(f"EasyOCR image decode failed: {e}")
            return {"text": None, "errors": [str(e)]}


neural_ocr_service = NeuralOCRService()
