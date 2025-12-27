"""
OCR Service for extracting text from scanned PDFs and images
Uses Tesseract OCR engine via pytesseract
"""
import io
import os
from pathlib import Path
from typing import Optional, Dict, List
import logging

from server.utils.logger import setup_logger

logger = setup_logger("ocr_service")

# Common Tesseract installation paths on Windows
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Tesseract-OCR\tesseract.exe",
]


class OCRService:
    """Service for Optical Character Recognition on scanned documents"""
    
    def __init__(self):
        self.logger = logger
        self._tesseract_available = None
        self._tesseract_path = None
        self._find_tesseract_path()
        self._check_tesseract_availability()
    
    def _find_tesseract_path(self):
        """Find Tesseract executable path"""
        try:
            import pytesseract
            
            # First, try to use pytesseract's default detection
            try:
                # This will use PATH if available
                pytesseract.get_tesseract_version()
                self._tesseract_path = None  # Use default (PATH)
                return
            except:
                pass
            
            # If not in PATH, check common installation locations
            for path in TESSERACT_PATHS:
                if os.path.exists(path):
                    self._tesseract_path = path
                    pytesseract.pytesseract.tesseract_cmd = path
                    self.logger.info(f"Found Tesseract at: {path}")
                    return
            
            self._tesseract_path = None
        except ImportError:
            self._tesseract_path = None
    
    def _check_tesseract_availability(self) -> bool:
        """Check if Tesseract OCR is installed and available"""
        if self._tesseract_available is not None:
            return self._tesseract_available
        
        try:
            import pytesseract
            # Try to get version to verify it's working
            try:
                version = pytesseract.get_tesseract_version()
                self.logger.info(f"Tesseract OCR version {version} detected")
                self._tesseract_available = True
                return True
            except Exception as e:
                error_msg = str(e).lower()
                # Check if it's a "not installed" or "not in PATH" error
                if "not installed" in error_msg or "not in your path" in error_msg or "not found" in error_msg:
                    self.logger.warning(f"Tesseract OCR is not installed or not in PATH: {e}")
                    self._tesseract_available = False
                    return False
                else:
                    # Other error - might be a different issue, but still mark as unavailable
                    self.logger.warning(f"Tesseract OCR version check failed: {e}")
                    self._tesseract_available = False
                    return False
        except ImportError:
            self.logger.warning("pytesseract not installed. OCR functionality will be unavailable.")
            self._tesseract_available = False
            return False
        except Exception as e:
            self.logger.error(f"Error checking Tesseract availability: {e}")
            self._tesseract_available = False
            return False
    
    def is_available(self) -> bool:
        """Check if OCR is available"""
        return self._tesseract_available is True
    
    def extract_text_from_image(self, image_bytes: bytes, page_num: int = 0) -> Optional[str]:
        """
        Extract text from an image using OCR
        
        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.)
            page_num: Page number for logging
            
        Returns:
            Extracted text or None if OCR fails
        """
        if not self.is_available():
            self.logger.warning("OCR not available - Tesseract not installed")
            return None
        
        try:
            from PIL import Image
            import pytesseract
            
            # Open image from bytes
            image = Image.open(io.BytesIO(image_bytes))
            
            # Perform OCR
            # Use PSM mode 6 (Assume a single uniform block of text)
            # This works well for legal documents
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(image, config=custom_config)
            
            if text and text.strip():
                self.logger.info(f"OCR extracted {len(text)} characters from page {page_num + 1}")
                return text.strip()
            else:
                self.logger.warning(f"OCR returned no text for page {page_num + 1}")
                return None
                
        except ImportError as e:
            self.logger.error(f"Required OCR libraries not installed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"OCR extraction failed for page {page_num + 1}: {e}", exc_info=True)
            return None
    
    def extract_text_from_pdf_images(
        self, 
        pdf_bytes: bytes, 
        max_pages: Optional[int] = None,
        pages_per_batch: int = 10
    ) -> Dict[str, any]:
        """
        Extract text from a scanned PDF by converting pages to images and running OCR
        
        Args:
            pdf_bytes: Raw PDF bytes
            max_pages: Maximum number of pages to process (None for all)
            pages_per_batch: Process pages in batches to manage memory
            
        Returns:
            Dictionary with:
            - text: Combined extracted text
            - pages_processed: Number of pages processed
            - pages_with_text: Number of pages that yielded text
            - errors: List of error messages
        """
        if not self.is_available():
            return {
                "text": None,
                "pages_processed": 0,
                "pages_with_text": 0,
                "errors": ["OCR not available - Tesseract not installed"]
            }
        
        try:
            import fitz  # PyMuPDF
            from PIL import Image
            import pytesseract
            
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)
            pages_to_process = min(max_pages or total_pages, total_pages)
            
            self.logger.info(f"Starting OCR extraction from {pages_to_process} pages of {total_pages} total pages")
            
            extracted_texts = []
            pages_with_text = 0
            errors = []
            
            # Process pages in batches to manage memory
            for batch_start in range(0, pages_to_process, pages_per_batch):
                batch_end = min(batch_start + pages_per_batch, pages_to_process)
                self.logger.info(f"Processing pages {batch_start + 1}-{batch_end}...")
                
                for page_num in range(batch_start, batch_end):
                    try:
                        page = doc[page_num]
                        
                        # Convert PDF page to image
                        # Use high DPI (300) for better OCR accuracy
                        mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
                        pix = page.get_pixmap(matrix=mat)
                        
                        # Convert to PIL Image
                        img_data = pix.tobytes("png")
                        image = Image.open(io.BytesIO(img_data))
                        
                        # Perform OCR
                        # PSM mode 6: Assume a single uniform block of text
                        # PSM mode 3: Fully automatic page segmentation (try this if 6 doesn't work well)
                        custom_config = r'--oem 3 --psm 6'
                        page_text = pytesseract.image_to_string(image, config=custom_config)
                        
                        if page_text and page_text.strip():
                            extracted_texts.append(page_text.strip())
                            pages_with_text += 1
                            self.logger.debug(f"Page {page_num + 1}: OCR extracted {len(page_text)} chars")
                        else:
                            # Try alternative PSM mode if first attempt failed
                            custom_config_alt = r'--oem 3 --psm 3'
                            page_text = pytesseract.image_to_string(image, config=custom_config_alt)
                            if page_text and page_text.strip():
                                extracted_texts.append(page_text.strip())
                                pages_with_text += 1
                                self.logger.debug(f"Page {page_num + 1}: OCR extracted {len(page_text)} chars (using PSM 3)")
                            else:
                                self.logger.warning(f"Page {page_num + 1}: OCR returned no text")
                        
                        # Clean up
                        pix = None
                        
                    except Exception as page_error:
                        error_msg = f"Error processing page {page_num + 1}: {str(page_error)}"
                        errors.append(error_msg)
                        self.logger.error(error_msg, exc_info=True)
                
                # Log progress
                progress_pct = (batch_end / pages_to_process * 100) if pages_to_process > 0 else 0
                self.logger.info(f"OCR progress: {batch_end}/{pages_to_process} pages ({progress_pct:.1f}%) - {pages_with_text} pages with text")
            
            doc.close()
            
            # Combine all extracted text
            combined_text = "\n\n".join(extracted_texts) if extracted_texts else None
            
            result = {
                "text": combined_text,
                "pages_processed": pages_to_process,
                "pages_with_text": pages_with_text,
                "total_pages": total_pages,
                "errors": errors
            }
            
            if combined_text:
                self.logger.info(
                    f"OCR extraction complete: {len(combined_text):,} characters from "
                    f"{pages_with_text}/{pages_to_process} pages"
                )
            else:
                self.logger.warning(f"OCR extraction complete but no text extracted from any pages")
            
            return result
            
        except ImportError as e:
            error_msg = f"Required OCR libraries not installed: {e}"
            self.logger.error(error_msg)
            return {
                "text": None,
                "pages_processed": 0,
                "pages_with_text": 0,
                "errors": [error_msg]
            }
        except Exception as e:
            error_msg = f"OCR extraction failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {
                "text": None,
                "pages_processed": 0,
                "pages_with_text": 0,
                "errors": [error_msg]
            }
    
    def get_installation_instructions(self) -> str:
        """Get instructions for installing Tesseract OCR"""
        import platform
        system = platform.system().lower()
        
        if system == "windows":
            return (
                "To enable OCR functionality, install Tesseract OCR:\n"
                "1. Download from: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "2. Run the installer (e.g., tesseract-ocr-w64-setup-5.x.x.exe)\n"
                "3. Add Tesseract to PATH or configure pytesseract.pytesseract.tesseract_cmd\n"
                "4. Restart the application"
            )
        elif system == "darwin":  # macOS
            return (
                "To enable OCR functionality, install Tesseract OCR:\n"
                "Run: brew install tesseract"
            )
        else:  # Linux
            return (
                "To enable OCR functionality, install Tesseract OCR:\n"
                "Ubuntu/Debian: sudo apt-get install tesseract-ocr\n"
                "Fedora: sudo dnf install tesseract\n"
                "Arch: sudo pacman -S tesseract"
            )


# Global instance
ocr_service = OCRService()

