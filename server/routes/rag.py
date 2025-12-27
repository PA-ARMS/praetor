"""
RAG API routes - Document management and search
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import aiofiles
from pathlib import Path
import io

from server.services.rag_service import rag_service
from server.services.motion_analysis_service import motion_analysis_service
from server.services.ocr_service import ocr_service
from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("rag")


router = APIRouter()


class DocumentMetadata(BaseModel):
    source: str
    jurisdiction: str
    document_type: str
    date: Optional[str] = None
    court: Optional[str] = None
    citation: Optional[str] = None


@router.post("/add-document")
async def add_document(text: str, metadata: DocumentMetadata):
    """Add document to RAG corpus"""
    try:
        await rag_service.add_document(
            text=text,
            metadata=metadata.dict(),
            doc_id=f"{metadata.jurisdiction}_{metadata.source}_{len(rag_service.collection.get()['ids'])}"
        )
        return {"status": "success", "message": "Document added to corpus"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding document: {str(e)}")


@router.post("/upload-document")
async def upload_document(
    file: UploadFile = File(...), 
    jurisdiction: str = Form("Virginia"),
    analyze_against_scenarios: str = Form("false"),
    perform_ai_understanding: str = Form("true")
):
    """
    Upload and index document file
    Supports OCR for scanned PDFs - can take several minutes for large documents
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    logger.info(f"Upload request received: {file.filename} ({file.size or 'unknown'} bytes) from network")
    
    try:
        # Read file content
        raw = await file.read()
        if not raw or len(raw) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        logger.info(f"File read successfully: {len(raw):,} bytes")
        
        ext = (Path(file.filename).suffix or "").lower()
        text = None
        parse_error = None
        
        # Initialize OCR metadata (will be set if OCR is used)
        ocr_metadata = {"used": False}

        # Parse by type
        try:
            if ext in [".txt", ".md"]:
                text = raw.decode('utf-8', errors='ignore')
            elif ext in [".html", ".htm"]:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(raw.decode('utf-8', errors='ignore'), "lxml")
                    for tag in soup(["script", "style", "nav", "header", "footer"]):
                        tag.extract()
                    text = soup.get_text("\n", strip=True)
                except ImportError:
                    parse_error = "BeautifulSoup4 not installed. Install with: pip install beautifulsoup4 lxml"
                except Exception as e:
                    parse_error = f"Error parsing HTML: {str(e)}"
            elif ext == ".pdf":
                # Try multiple PDF extraction methods for better compatibility
                text = None
                extraction_methods = []
                extraction_errors = []
                pdf_page_count = 0
                
                logger.info(f"=== PDF UPLOAD START: {file.filename} ({len(raw):,} bytes) ===")
                
                # First, verify it's actually a PDF by checking magic bytes
                if not raw.startswith(b'%PDF'):
                    logger.warning(f"File '{file.filename}' does not appear to be a valid PDF file (missing PDF header), but will attempt extraction anyway")
                else:
                    logger.info(f"Valid PDF detected (size: {len(raw):,} bytes)")
                
                # Continue with extraction attempts regardless of header check
                
                # IMMEDIATE OCR ATTEMPT FOR PDFs (before trying standard extraction)
                # This ensures OCR runs even if standard extraction completely fails
                # For large PDFs, we'll process in chunks to avoid timeouts
                if ocr_service.is_available():
                    logger.info("Attempting OCR FIRST (before standard extraction)...")
                    try:
                        # For very large PDFs (>3MB), limit to first 20 pages to avoid timeout
                        # User can still get the document indexed with partial content
                        file_size_mb = len(raw) / (1024 * 1024)
                        max_ocr_pages = 20 if file_size_mb > 3 else 50
                        logger.info(f"PDF size: {file_size_mb:.2f} MB - limiting OCR to first {max_ocr_pages} pages to avoid timeout")
                        
                        ocr_result = ocr_service.extract_text_from_pdf_images(raw, max_pages=max_ocr_pages)
                        ocr_text = ocr_result.get("text", "") or ""
                        ocr_text_stripped = ocr_text.strip() if ocr_text else ""
                        ocr_text_len = len(ocr_text_stripped)
                        
                        logger.info(f"OCR FIRST result: raw_text_len={len(ocr_text)}, stripped_len={ocr_text_len}, pages={ocr_result.get('pages_processed', 0)}, pages_with_text={ocr_result.get('pages_with_text', 0)}")
                        
                        if ocr_text and ocr_text_len >= 30:
                            text = ocr_text_stripped  # Use stripped version
                            ocr_metadata = {
                                "used": True,
                                "pages_processed": ocr_result.get("pages_processed", 0),
                                "pages_with_text": ocr_result.get("pages_with_text", 0),
                                "total_pages": ocr_result.get("total_pages", 0)
                            }
                            logger.info(f"OCR FIRST attempt SUCCESS: {ocr_text_len:,} characters from {ocr_result['pages_with_text']}/{ocr_result['pages_processed']} pages")
                            logger.info(f"Text variable set to {len(text)} characters")
                        else:
                            logger.warning(f"OCR FIRST attempt extracted only {ocr_text_len} characters (minimum: 30) - will try standard extraction")
                            if ocr_result.get("errors"):
                                logger.warning(f"OCR errors: {ocr_result['errors']}")
                            # Still store what we got if it's something
                            if ocr_text and ocr_text_len > 0:
                                text = ocr_text_stripped
                                logger.info(f"Storing {ocr_text_len} characters from OCR even though below minimum")
                    except Exception as ocr_first_error:
                        logger.error(f"OCR FIRST attempt failed: {ocr_first_error}", exc_info=True)
                        logger.warning("Will try standard extraction methods")
                
                # If OCR didn't work, try standard extraction methods
                # BUT: Don't overwrite OCR text if we already have it
                ocr_text_available = text and len(text.strip()) >= 30
                
                # Method 1: pdfplumber (best for text-based PDFs)
                try:
                    import pdfplumber
                    extraction_methods.append("pdfplumber")
                    out = []
                    with pdfplumber.open(io.BytesIO(raw)) as pdf:
                        pdf_page_count = len(pdf.pages)
                        logger.info(f"PDF has {pdf_page_count} pages")
                        for page_num, page in enumerate(pdf.pages):
                            try:
                                # Try multiple extraction methods per page
                                page_text = page.extract_text()
                                if not page_text or not page_text.strip():
                                    # Try extracting tables as text
                                    tables = page.extract_tables()
                                    if tables:
                                        table_text = "\n".join(["\n".join([str(cell) if cell else "" for cell in row]) for table in tables for row in table])
                                        if table_text.strip():
                                            page_text = table_text
                                
                                if page_text and page_text.strip():
                                    out.append(page_text.strip())
                                    logger.debug(f"Page {page_num + 1}: extracted {len(page_text)} chars")
                                else:
                                    logger.warning(f"Page {page_num + 1}: no text extracted (page_text is None or empty)")
                            except Exception as page_error:
                                logger.error(f"Error extracting page {page_num + 1}: {page_error}", exc_info=True)
                    if out:
                        text = "\n".join(out).strip()
                        # Remove excessive whitespace but keep structure
                        import re
                        text = re.sub(r'\n{3,}', '\n\n', text)
                        text = re.sub(r' {3,}', ' ', text)
                        logger.info(f"Successfully extracted {len(text)} chars using pdfplumber from {len(out)} pages")
                    else:
                        logger.warning("pdfplumber extracted no text from any pages")
                except ImportError:
                    logger.warning("pdfplumber not installed")
                    extraction_errors.append("pdfplumber: library not installed")
                    pass  # Try next method
                except Exception as e:
                    error_msg = f"pdfplumber: {str(e)}"
                    extraction_errors.append(error_msg)
                    logger.error(f"pdfplumber extraction failed: {e}", exc_info=True)
                
                # Method 2: PyMuPDF (fitz) - better for some PDFs and can detect scanned PDFs
                # Skip if we already have OCR text
                if not ocr_text_available and (not text or len(text.strip()) < 30):
                    try:
                        import fitz  # PyMuPDF
                        extraction_methods.append("PyMuPDF")
                        doc = fitz.open(stream=raw, filetype="pdf")
                        logger.info(f"PyMuPDF: PDF has {len(doc)} pages")
                        out = []
                        total_images = 0
                        pages_with_images = 0
                        
                        for page_num in range(len(doc)):
                            page = doc[page_num]
                            try:
                                # Try getting text
                                page_text = page.get_text()
                                if not page_text or not page_text.strip():
                                    # Try getting text blocks
                                    text_blocks = page.get_text("blocks")
                                    if text_blocks:
                                        page_text = "\n".join([block[4] for block in text_blocks if block[4]])
                                
                                # Count images on this page
                                images = page.get_images()
                                image_count = len(images)
                                if image_count > 0:
                                    total_images += image_count
                                    pages_with_images += 1
                                
                                if page_text and page_text.strip():
                                    out.append(page_text.strip())
                                    logger.debug(f"PyMuPDF Page {page_num + 1}: extracted {len(page_text)} chars, {image_count} images")
                            except Exception as page_error:
                                logger.warning(f"PyMuPDF error on page {page_num + 1}: {page_error}")
                        
                        doc.close()
                        
                        # Store image count for later use in error messages
                        if total_images > 0:
                            logger.warning(f"PDF contains {total_images} images across {pages_with_images} pages - may be scanned")
                        
                        if out:
                            new_text = "\n".join(out).strip()
                            if len(new_text) > len(text or ""):
                                text = new_text
                                logger.info(f"Successfully extracted {len(text)} chars using PyMuPDF from {len(out)} pages")
                        else:
                            logger.warning("PyMuPDF extracted no text from any pages")
                            if total_images > 0 and pages_with_images > len(doc) * 0.5:
                                # More than half the pages have images and no text - likely scanned
                                extraction_errors.append(f"Scanned PDF detected: {total_images} images, {pages_with_images} pages with images, no extractable text")
                    except ImportError:
                        logger.warning("PyMuPDF (fitz) not installed")
                        extraction_errors.append("PyMuPDF: library not installed")
                        pass  # Try next method
                    except Exception as e:
                        error_msg = f"PyMuPDF: {str(e)}"
                        extraction_errors.append(error_msg)
                        logger.error(f"PyMuPDF extraction failed: {e}", exc_info=True)
                
                # Method 3: PyPDF2 (fallback)
                # Skip if we already have OCR text
                if not ocr_text_available and (not text or len(text.strip()) < 30):
                    try:
                        import PyPDF2
                        extraction_methods.append("PyPDF2")
                        pdf_reader = PyPDF2.PdfReader(io.BytesIO(raw))
                        logger.info(f"PyPDF2: PDF has {len(pdf_reader.pages)} pages")
                        out = []
                        for page_num, page in enumerate(pdf_reader.pages):
                            try:
                                page_text = page.extract_text()
                                if page_text and page_text.strip():
                                    out.append(page_text)
                                    logger.debug(f"PyPDF2 Page {page_num + 1}: extracted {len(page_text)} chars")
                            except Exception as page_error:
                                logger.warning(f"PyPDF2 error on page {page_num + 1}: {page_error}")
                        if out:
                            new_text = "\n".join(out).strip()
                            if len(new_text) > len(text or ""):
                                text = new_text
                                logger.info(f"Successfully extracted {len(text)} chars using PyPDF2 from {len(out)} pages")
                        else:
                            logger.warning("PyPDF2 extracted no text from any pages")
                    except ImportError:
                        logger.warning("PyPDF2 not installed")
                        extraction_errors.append("PyPDF2: library not installed")
                        pass  # Try next method
                    except Exception as e:
                        error_msg = f"PyPDF2: {str(e)}"
                        extraction_errors.append(error_msg)
                        logger.error(f"PyPDF2 extraction failed: {e}", exc_info=True)
                
                # If still no text, automatically try OCR as primary fallback
                # Skip if we already have OCR text from FIRST attempt
                if not ocr_text_available and (not text or len(text.strip()) < 30):
                    logger.warning(f"No text extracted from PDF using standard methods (extracted {len(text.strip()) if text else 0} chars). Attempting OCR...")
                    
                    # Try OCR immediately if available (don't wait for image detection)
                    if ocr_service.is_available():
                        logger.info("OCR is available - attempting OCR extraction for PDF...")
                        try:
                            ocr_result = ocr_service.extract_text_from_pdf_images(
                                raw,
                                max_pages=50  # Limit to first 50 pages for performance
                            )
                            
                            ocr_text = ocr_result.get("text", "") or ""
                            ocr_text_stripped = ocr_text.strip() if ocr_text else ""
                            ocr_text_len = len(ocr_text_stripped)
                            
                            logger.info(f"OCR fallback result: text_len={ocr_text_len}, pages={ocr_result.get('pages_processed', 0)}, pages_with_text={ocr_result.get('pages_with_text', 0)}")
                            
                            if ocr_text and ocr_text_len >= 30:
                                text = ocr_text_stripped  # Use stripped version
                                logger.info(
                                    f"OCR successfully extracted {ocr_text_len:,} characters from "
                                    f"{ocr_result['pages_with_text']}/{ocr_result['pages_processed']} pages"
                                )
                                # Clear parse_error since OCR succeeded
                                parse_error = None
                                # Store OCR metadata for response
                                ocr_metadata = {
                                    "used": True,
                                    "pages_processed": ocr_result.get("pages_processed", 0),
                                    "pages_with_text": ocr_result.get("pages_with_text", 0),
                                    "total_pages": ocr_result.get("total_pages", pdf_page_count)
                                }
                            else:
                                logger.warning(f"OCR fallback extracted only {ocr_text_len} characters (minimum: 30)")
                                # Still store what we got if it's something
                                if ocr_text and ocr_text_len > 0:
                                    text = ocr_text_stripped
                                else:
                                    # OCR didn't extract enough text
                                    error_details = f"Extracted {len(text.strip()) if text else 0} characters using standard methods. OCR extracted {len(ocr_result.get('text', '') or '')} characters."
                                    parse_error = (
                                        f"Could not extract sufficient text from PDF. "
                                        f"{error_details} "
                                        f"Pages processed by OCR: {ocr_result.get('pages_processed', 0)}, "
                                        f"Pages with text: {ocr_result.get('pages_with_text', 0)}. "
                                        f"This PDF may be image-based or have very poor quality. "
                                        f"Try improving image quality or using a different OCR tool."
                                    )
                                    if ocr_result.get("errors"):
                                        parse_error += f" OCR Errors: {'; '.join(ocr_result['errors'][:2])}"
                        except Exception as ocr_error:
                            logger.error(f"OCR extraction failed: {ocr_error}", exc_info=True)
                            error_details = f"Extracted {len(text.strip()) if text else 0} characters. Tried methods: {', '.join(extraction_methods)}"
                            parse_error = (
                                f"Could not extract sufficient text from PDF. {error_details}. "
                                f"OCR was attempted but failed: {str(ocr_error)}"
                            )
                    else:
                        # OCR not available - provide installation instructions
                        if not extraction_methods:
                            parse_error = "No PDF extraction libraries installed. Install one of: pdfplumber, PyMuPDF, or PyPDF2"
                        else:
                            install_instructions = ocr_service.get_installation_instructions()
                            error_details = f"Extracted {len(text.strip()) if text else 0} characters. Tried methods: {', '.join(extraction_methods)}"
                            parse_error = (
                                f"Could not extract sufficient text from PDF. {error_details}. "
                                f"This PDF appears to be a scanned/image-based document.\n\n"
                                f"OCR (Optical Character Recognition) is required to extract text from scanned PDFs.\n\n"
                                f"{install_instructions}\n\n"
                                f"Alternatively, use OCR software (such as Adobe Acrobat or online OCR tools) "
                                f"to convert the scanned PDF to text before uploading."
                            )
            elif ext == ".docx":
                try:
                    from docx import Document
                    doc = Document(io.BytesIO(raw))
                    # Extract from paragraphs
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    # Also extract from tables
                    table_texts = []
                    for table in doc.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                if cell.text.strip():
                                    table_texts.append(cell.text.strip())
                    # Combine all text
                    all_text = paragraphs + table_texts
                    text = "\n".join(all_text).strip()
                    if text:
                        logger.info(f"Successfully extracted {len(text)} chars from DOCX ({len(paragraphs)} paragraphs, {len(table_texts)} table cells)")
                except ImportError:
                    parse_error = "python-docx not installed. Install with: pip install python-docx"
                except Exception as e:
                    parse_error = f"Error parsing DOCX: {str(e)}"
                    logger.error(f"DOCX parsing error: {e}", exc_info=True)
            elif ext == ".pptx":
                try:
                    from pptx import Presentation
                    prs = Presentation(io.BytesIO(raw))
                    chunks = []
                    for slide in prs.slides:
                        for shape in slide.shapes:
                            if hasattr(shape, "text"):
                                chunks.append(shape.text)
                    text = "\n".join(chunks)
                except ImportError:
                    parse_error = "python-pptx not installed. Install with: pip install python-pptx"
                except Exception as e:
                    parse_error = f"Error parsing PPTX: {str(e)}"
            elif ext in [".xlsx", ".xls", ".csv"]:
                try:
                    import pandas as pd
                    if ext == ".csv":
                        df = pd.read_csv(io.BytesIO(raw), encoding_errors="ignore")
                    else:
                        df = pd.read_excel(io.BytesIO(raw))
                    text = df.to_csv(index=False)
                except ImportError:
                    parse_error = "pandas/openpyxl not installed. Install with: pip install pandas openpyxl"
                except Exception as e:
                    parse_error = f"Error parsing spreadsheet: {str(e)}"
            else:
                # Fallback: best-effort utf-8 decode
                text = raw.decode('utf-8', errors='ignore')
        except Exception as e:
            parse_error = f"Error parsing file: {str(e)}"
            logger.error(f"Error during file parsing: {e}", exc_info=True)
        
        # For PDFs: If we have no text or a parse_error, try OCR as recovery
        if ext == ".pdf":
            logger.info(f"PDF processing: text={len(text) if text else 0} chars, parse_error={parse_error is not None}, OCR available={ocr_service.is_available()}")
            if (not text or len(text.strip()) < 30) and ocr_service.is_available():
                logger.info("PDF extraction failed or insufficient text - attempting OCR recovery...")
                try:
                    logger.info(f"Calling OCR service with {len(raw):,} bytes...")
                    ocr_result = ocr_service.extract_text_from_pdf_images(
                        raw,
                        max_pages=50
                    )
                    logger.info(f"OCR returned: text_len={len(ocr_result.get('text', '') or '')}, pages_processed={ocr_result.get('pages_processed', 0)}, pages_with_text={ocr_result.get('pages_with_text', 0)}")
                    if ocr_result["text"] and len(ocr_result["text"].strip()) >= 30:
                        text = ocr_result["text"]
                        parse_error = None  # Clear error since OCR succeeded
                        ocr_metadata = {
                            "used": True,
                            "pages_processed": ocr_result.get("pages_processed", 0),
                            "pages_with_text": ocr_result.get("pages_with_text", 0),
                            "total_pages": ocr_result.get("total_pages", pdf_page_count)
                        }
                        logger.info(f"OCR recovery successful: extracted {len(text):,} characters from {ocr_result['pages_with_text']}/{ocr_result['pages_processed']} pages")
                    else:
                        logger.warning(f"OCR recovery attempted but only extracted {len(ocr_result.get('text', '') or '')} characters")
                except Exception as ocr_recovery_error:
                    logger.error(f"OCR recovery attempt failed: {ocr_recovery_error}", exc_info=True)
                    # Keep the original parse_error if OCR fails
        
        # Now check parse_error (after OCR recovery attempt)
        if parse_error:
            raise HTTPException(status_code=500, detail=parse_error)

        # Log extraction result for debugging
        if text:
            logger.info(f"Extracted {len(text)} characters from {file.filename} (type: {ext})")
            # Log first 200 chars for debugging
            preview = text[:200].replace('\n', ' ').replace('\r', ' ')
            logger.debug(f"Text preview: {preview}...")
        else:
            logger.warning(f"No text extracted from {file.filename} (type: {ext}, size: {len(raw)} bytes)")
        
        # If text is too short, try OCR one more time for PDFs (final attempt)
        min_chars = 30  # Reduced from 50
        if not text or len(text.strip()) < min_chars:
            extracted_len = len(text.strip()) if text else 0
            logger.error(f"EXTRACTION FAILED: file={file.filename}, type={ext}, size={len(raw)} bytes, extracted={extracted_len} chars")
            
            # Final OCR attempt for PDFs (in case it wasn't tried yet)
            if ext == ".pdf" and ocr_service.is_available() and not ocr_metadata.get("used", False):
                logger.info("Final OCR attempt for PDF (last resort)...")
                try:
                    # Limit pages for large files to avoid timeout
                    file_size_mb = len(raw) / (1024 * 1024)
                    max_ocr_pages = 20 if file_size_mb > 3 else 50
                    logger.info(f"Final OCR: limiting to {max_ocr_pages} pages (file size: {file_size_mb:.2f} MB)")
                    
                    ocr_result = ocr_service.extract_text_from_pdf_images(raw, max_pages=max_ocr_pages)
                    ocr_text = ocr_result.get("text", "") or ""
                    ocr_text_stripped = ocr_text.strip() if ocr_text else ""
                    ocr_text_len = len(ocr_text_stripped)
                    
                    logger.info(f"Final OCR result: raw_text_len={len(ocr_text)}, stripped_len={ocr_text_len}, pages={ocr_result.get('pages_processed', 0)}, pages_with_text={ocr_result.get('pages_with_text', 0)}")
                    
                    if ocr_text and ocr_text_len >= min_chars:
                        text = ocr_text_stripped  # Use stripped version
                        ocr_metadata = {
                            "used": True,
                            "pages_processed": ocr_result.get("pages_processed", 0),
                            "pages_with_text": ocr_result.get("pages_with_text", 0),
                            "total_pages": ocr_result.get("total_pages", pdf_page_count)
                        }
                        logger.info(f"Final OCR attempt successful: {ocr_text_len:,} characters extracted")
                        logger.info(f"Text variable set to {len(text)} characters")
                    else:
                        logger.warning(f"Final OCR attempt extracted only {ocr_text_len} characters (minimum: {min_chars})")
                        if ocr_result.get("errors"):
                            logger.warning(f"Final OCR errors: {ocr_result['errors']}")
                        # Still store what we got if it's something
                        if ocr_text and ocr_text_len > 0:
                            text = ocr_text_stripped
                            logger.info(f"Storing {ocr_text_len} characters from OCR even though below minimum")
                except Exception as final_ocr_error:
                    logger.error(f"Final OCR attempt failed: {final_ocr_error}", exc_info=True)
            
            # If still no text after all attempts, raise error
            if not text or len(text.strip()) < min_chars:
                extracted_len = len(text.strip()) if text else 0
                
                # Log actual extracted text for debugging
                if text:
                    preview = text[:500].replace('\n', '\\n').replace('\r', '\\r')
                    logger.error(f"Extracted text preview: {preview}")
                
                # Provide helpful error message
                error_detail = (
                    f"Could not extract meaningful text from document '{file.filename}'. "
                    f"Extracted {extracted_len} characters (minimum required: {min_chars}). "
                )
                if ext == ".pdf":
                    if ocr_metadata.get("used", False):
                        error_detail += (
                            f"OCR was attempted and processed {ocr_metadata.get('pages_processed', 0)} pages, "
                            f"but only extracted {extracted_len} characters. "
                            f"This PDF may have very poor image quality or be corrupted. "
                        )
                    else:
                        error_detail += (
                            "This PDF may be image-based (scanned) and require OCR, or the text may be embedded in a way that prevents extraction. "
                            "Try converting the PDF to text format or using OCR software first. "
                        )
                    error_detail += f"File size: {len(raw):,} bytes. "
                elif ext == ".docx":
                    error_detail += (
                        "The document may be empty, password-protected, or in an unsupported format. "
                        "Try opening it in Microsoft Word and saving as a plain text file. "
                    )
                else:
                    error_detail += "The file may be corrupted, password-protected, or in an unsupported format."
                
                raise HTTPException(status_code=400, detail=error_detail)
        
        # Clean and normalize text
        text = text.strip()
        # Remove excessive whitespace
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {3,}', ' ', text)
        
        # Extract metadata from filename
        base_metadata = {
            "source": file.filename,
            "jurisdiction": jurisdiction,
            "document_type": Path(file.filename).suffix[1:].upper() if Path(file.filename).suffix else "TXT",
            "upload_date": str(datetime.now()),
            "file_size": len(text),
            "original_filename": file.filename
        }
        
        # Use AI to understand the document
        from server.services.document_understanding_service import document_understanding_service
        
        understanding = await document_understanding_service.understand_document(
            text=text,
            filename=file.filename,
            document_type=base_metadata["document_type"]
        )
        
        # Merge understanding with base metadata
        metadata = {**base_metadata, **understanding}
        
        # Generate document ID from filename
        doc_id = f"upload_{Path(file.filename).stem}_{int(datetime.now().timestamp())}"
        
        try:
            await rag_service.add_document(text=text, metadata=metadata, doc_id=doc_id)
            
            # Get stats to confirm it was added
            stats = rag_service.get_collection_stats()
            
            result = {
                "status": "success",
                "message": f"Document '{file.filename}' successfully indexed and analyzed",
                "indexed": True,
                "source": file.filename,
                "text_length": len(text),
                "total_documents": stats.get("total_documents", 0),
                "ocr_used": ocr_metadata.get("used", False),
                "understanding": {
                    "summary": understanding.get("summary", ""),
                    "document_type": understanding.get("document_type", base_metadata["document_type"]),
                    "key_points": understanding.get("key_points", [])[:5],  # Top 5 key points
                    "legal_concepts": understanding.get("legal_concepts", []),
                    "entities": {
                        "dates": understanding.get("entities", {}).get("dates", [])[:5],
                        "parties": understanding.get("entities", {}).get("parties", [])[:5],
                        "case_numbers": understanding.get("entities", {}).get("case_numbers", [])[:5],
                        "statutes": understanding.get("entities", {}).get("statutes", [])[:5]
                    }
                }
            }
            
            # Add OCR details if OCR was used
            if ocr_metadata.get("used"):
                result["ocr_details"] = {
                    "pages_processed": ocr_metadata.get("pages_processed", 0),
                    "pages_with_text": ocr_metadata.get("pages_with_text", 0),
                    "total_pages": ocr_metadata.get("total_pages", 0)
                }
            
            # Process document as scenario if scenario DB is enabled and document is a legal case
            if settings.SCENARIO_DB_ENABLED:
                try:
                    from server.services.document_to_scenario_service import document_to_scenario_service
                    scenario_result = await document_to_scenario_service.process_document_as_scenario(
                        text=text,
                        filename=file.filename,
                        jurisdiction=jurisdiction,
                        understanding=understanding
                    )
                    if scenario_result:
                        result["scenario_processed"] = True
                        result["scenario_id"] = scenario_result.get("scenario_id")
                        result["scenario_outcome"] = scenario_result.get("outcome")
                        result["message"] += " and added to learning system"
                    else:
                        result["scenario_processed"] = False
                        result["scenario_reason"] = "Document not identified as a legal case or outcome could not be determined"
                except Exception as e:
                    # Don't fail upload if scenario processing fails
                    logger.warning(f"Failed to process document as scenario: {e}")
                    result["scenario_processed"] = False
                    result["scenario_error"] = str(e)
            
            # If requested, also analyze against scenario database
            should_analyze = analyze_against_scenarios.lower() in ["true", "1", "yes"]
            if should_analyze and settings.SCENARIO_DB_ENABLED:
                try:
                    motion_analysis = await motion_analysis_service.analyze_motion(
                        motion_text=text,
                        motion_type=None,  # Auto-detect
                        jurisdiction=jurisdiction,
                        db_session=None
                    )
                    result["motion_analysis"] = motion_analysis
                    result["message"] += " and analyzed against scenario database"
                except Exception as e:
                    # Don't fail upload if analysis fails
                    result["motion_analysis_error"] = str(e)
            
            return result
        except HTTPException:
            # Re-raise HTTP exceptions (like extraction errors) as-is
            raise
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Error indexing document: {error_details}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error indexing document: {str(e)}. Check server logs for details."
            )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_msg = str(e)
        logger.error(f"Error uploading document: {error_details}")
        
        # Provide more helpful error messages for common network/timeout issues
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            error_detail = (
                f"Document processing timed out. This can happen with large scanned PDFs that require OCR. "
                f"Please try uploading a smaller file or splitting the document. "
                f"Original error: {error_msg}"
            )
        elif "memory" in error_msg.lower() or "out of memory" in error_msg.lower():
            error_detail = (
                f"Document is too large to process. Please try uploading a smaller file or splitting the document. "
                f"Original error: {error_msg}"
            )
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            error_detail = (
                f"Network connection error during upload. Please check your connection and try again. "
                f"Original error: {error_msg}"
            )
        else:
            error_detail = f"Error uploading document: {error_msg}. Check server logs for details."
        
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/search")
async def search(query: str, n_results: int = 5):
    """Search corpus"""
    try:
        results = await rag_service.search(query, n_results)
        return {"query": query, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching: {str(e)}")


@router.get("/stats")
async def get_stats():
    """Get corpus statistics"""
    try:
        stats = rag_service.get_collection_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


class MotionAnalysisRequest(BaseModel):
    document_text: str
    motion_type: Optional[str] = None
    jurisdiction: Optional[str] = "Virginia"


@router.post("/analyze-motion")
async def analyze_motion(request: MotionAnalysisRequest):
    """Analyze a motion document against scenario database"""
    try:
        if not settings.SCENARIO_DB_ENABLED:
            raise HTTPException(
                status_code=400,
                detail="Scenario database is not enabled. Enable it to analyze motions."
            )
        
        analysis = await motion_analysis_service.analyze_motion(
            motion_text=request.document_text,
            motion_type=request.motion_type,
            jurisdiction=request.jurisdiction,
            db_session=None  # Can add DB session if needed for learning
        )
        
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error analyzing motion: {str(e)}")

