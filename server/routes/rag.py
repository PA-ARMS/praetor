"""
RAG API routes - Document management and search
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
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
            doc_id=f"{metadata.jurisdiction}_{metadata.source}_{uuid.uuid4().hex[:12]}"
        )
        return {"status": "success", "message": "Document added to corpus"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding document: {str(e)}")


@router.post("/upload-document")
async def upload_document(
    file: UploadFile = File(...), 
    jurisdiction: str = Form("Virginia"),
    analyze_against_scenarios: str = Form("false"),
    perform_ai_understanding: str = Form("true"),
    matter_id: Optional[str] = Form(None),
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

        perform_understanding = perform_ai_understanding.lower() in ["true", "1", "yes"]

        # Use document pipeline for extraction and enrichment
        from server.services.document_pipeline_service import document_pipeline_service

        # When AI understanding runs, skip duplicate LLM JSON pass in structured extraction (same Ollama load).
        text, pre_metadata, parse_error = await document_pipeline_service.process_document(
            raw=raw,
            filename=file.filename,
            ext=ext,
            skip_llm_structured=perform_understanding,
        )

        if parse_error:
            raise HTTPException(status_code=400, detail=parse_error)

        ocr_metadata = pre_metadata.get("ocr_metadata", {"used": False})
        extracted_bundle = pre_metadata.get("extracted_data")
        structured_summary = (pre_metadata.get("structured_extraction_summary") or "")[:512]

        # Extract metadata from filename
        base_metadata = {
            "source": file.filename,
            "jurisdiction": jurisdiction,
            "document_type": Path(file.filename).suffix[1:].upper() if Path(file.filename).suffix else "TXT",
            "upload_date": str(datetime.now()),
            "file_size": len(text),
            "original_filename": file.filename,
            "structured_extraction_summary": structured_summary,
        }
        
        # Use AI to understand the document (with pre-extracted summary/entities from pipeline)
        from server.services.document_understanding_service import document_understanding_service

        if perform_understanding:
            try:
                understanding = await document_understanding_service.understand_document(
                    text=text,
                    filename=file.filename,
                    document_type=base_metadata["document_type"],
                    pre_extracted_summary=pre_metadata.get("summary"),
                    pre_extracted_entities=pre_metadata.get("entities"),
                )
            except Exception as e:
                logger.warning(f"Document understanding failed (indexing continues): {e}")
                understanding = {
                    "summary": pre_metadata.get("summary", ""),
                    "document_type": base_metadata["document_type"],
                    "key_points": [],
                    "entities": pre_metadata.get("entities") or {},
                    "legal_concepts": [],
                    "word_count": len(text.split()),
                    "analyzed_at": str(datetime.now()),
                    "has_analysis": False,
                    "analysis_error": str(e)[:2000],
                }
        else:
            understanding = {
                "summary": pre_metadata.get("summary", ""),
                "document_type": base_metadata["document_type"],
                "key_points": [],
                "entities": pre_metadata.get("entities", {}),
                "legal_concepts": [],
            }
        
        # Merge understanding with base metadata (omit bulky JSON from vector DB metadata)
        metadata = {**base_metadata, **understanding}
        metadata.pop("extracted_data", None)
        if matter_id and str(matter_id).strip():
            metadata["matter_id"] = str(matter_id).strip()

        # Generate document ID from filename
        doc_id = f"upload_{Path(file.filename).stem}_{int(datetime.now().timestamp())}"
        
        try:
            await rag_service.add_document(text=text, metadata=metadata, doc_id=doc_id)
            
            # Get stats to confirm it was added
            stats = rag_service.get_collection_stats()
            
            # Echo extracted text for same-turn chat (must stay within chat request body limits).
            _inline_max = 150_000
            result = {
                "status": "success",
                "message": f"Document '{file.filename}' successfully indexed and analyzed",
                "indexed": True,
                "source": file.filename,
                "extracted_text": text[:_inline_max],
                "extracted_text_truncated": len(text) > _inline_max,
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
                },
                "extracted_data": extracted_bundle,
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


@router.get("/documents")
async def list_indexed_documents(matter_id: Optional[str] = None):
    """List indexed RAG documents, optionally filtered by matter_id (industry-standard document management)."""
    try:
        docs = rag_service.list_documents(matter_id=matter_id)
        return {"documents": docs, "count": len(docs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


@router.delete("/documents/{doc_id:path}")
async def delete_indexed_document(doc_id: str):
    """Remove a document and its chunks from the RAG index. Core laws cannot be deleted."""
    try:
        deleted = rag_service.delete_document(doc_id)
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Document not found or already deleted")
        return {"status": "success", "deleted_count": deleted}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

