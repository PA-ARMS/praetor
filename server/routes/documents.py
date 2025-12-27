"""
Documents API routes - Document management
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import List
from pathlib import Path
import aiofiles
from datetime import datetime
import re

from server.config import settings
from server.middleware.auth_middleware import require_auth
from server.models import User
from server.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger("documents")


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(require_auth)
):
    """
    Upload document to corpus
    
    Requires authentication. Validates file size, type, and sanitizes filename.
    """
    try:
        # Read file content first to check size
        content = await file.read()
        
        # Validate file size
        if len(content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE / (1024*1024):.0f}MB"
            )
        
        # Validate file extension
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        ext = Path(file.filename).suffix.lower()
        if ext not in settings.ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_FILE_EXTENSIONS)}"
            )
        
        # Sanitize filename to prevent path traversal
        # Remove path components and dangerous characters
        safe_filename = Path(file.filename).name  # Remove any path components
        # Keep only alphanumeric, dots, dashes, and underscores
        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', safe_filename)
        # Prevent empty or only-dot filenames
        if not safe_filename or safe_filename in ['.', '..']:
            safe_filename = f"upload_{datetime.now().timestamp()}{ext}"
        
        # Create upload directory
        upload_dir = Path(settings.CORPUS_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Create unique filename with user ID and timestamp to prevent collisions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{current_user.id}_{timestamp}_{safe_filename}"
        file_path = upload_dir / unique_filename
        
        # Write file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        logger.info(f"User {current_user.id} uploaded file: {unique_filename} ({len(content)} bytes)")
        
        return {
            "status": "success",
            "filename": safe_filename,
            "stored_filename": unique_filename,
            "path": str(file_path),
            "size": len(content),
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_by": current_user.username
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error uploading document. Please try again or contact support."
        )


@router.get("/list")
async def list_documents(current_user: User = Depends(require_auth)):
    """List all documents in corpus (requires authentication)"""
    try:
        corpus_dir = Path(settings.CORPUS_DIR)
        documents = []
        
        if corpus_dir.exists():
            for doc_file in corpus_dir.iterdir():
                if doc_file.is_file():
                    documents.append({
                        "name": doc_file.name,
                        "size": doc_file.stat().st_size,
                        "modified": datetime.fromtimestamp(doc_file.stat().st_mtime).isoformat()
                    })
        
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Error listing documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error listing documents. Please try again or contact support."
        )

