"""
Virginia Legal AI - Main Server
FastAPI backend for legal research and form generation

This is the main entry point for the AKLAWMS (AK Law Management System) application.
It initializes the FastAPI server, sets up middleware, registers routes, and handles
startup/shutdown lifecycle events.

Key Components:
- FastAPI application with CORS support for network access
- Guardrails middleware to enforce AI Laws
- Multiple route modules for different features
- Database initialization
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from datetime import datetime
import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
# This must be done BEFORE importing config so the .env file is loaded
load_dotenv()

# Import route modules for core features only: auth, chat, documents, rag, system
# See docs/REMOVED_FEATURES.md for re-enabling forms, audit, corrections, matters, scenarios, etc.
from server.routes import chat, documents, rag, auth, system
# Import middleware for AI Laws enforcement
from server.middleware.guardrails_middleware import GuardrailsMiddleware
# Import rate limiting middleware
from server.middleware.rate_limit import RateLimitMiddleware
# Import request ID middleware
from server.middleware.request_id import RequestIDMiddleware
# Import configuration settings
from server.config import settings
# Import database initialization function
from server.models import init_db
# Import logging utility
from server.utils.logger import setup_logger
# Import Knowledge Builder
from server.services.knowledge_builder_service import knowledge_builder

# Initialize logger for this module
logger = setup_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - handles startup and shutdown events
    """
    # === STARTUP SEQUENCE ===
    logger.info(f"Starting Virginia Legal AI Server on {settings.HOST}:{settings.PORT}")
    
    # === CRITICAL: VERIFY AI LAWS INTEGRITY ===
    # AI Laws are IMMUTABLE and must be verified before system starts
    try:
        from server.services.ai_laws_protection import ai_laws_protection
        is_valid, error = ai_laws_protection.verify_ai_laws()
        if not is_valid:
            logger.critical("=" * 80)
            logger.critical("CRITICAL ERROR: AI LAWS VERIFICATION FAILED")
            logger.critical("=" * 80)
            logger.critical(f"Error: {error}")
            logger.critical("")
            logger.critical("The AI Laws are IMMUTABLE and cannot be modified by anyone.")
            logger.critical("The system cannot start without valid, unmodified AI Laws.")
            logger.critical("Please restore the original ai_laws.json file.")
            logger.critical("=" * 80)
            raise RuntimeError(
                "AI Laws verification failed on startup. "
                "The AI Laws are IMMUTABLE and cannot be modified. "
                "System cannot start without valid AI Laws."
            )
        logger.info("[OK] AI Laws verified - integrity confirmed (IMMUTABLE)")
    except RuntimeError:
        raise  # Re-raise to prevent server from starting
    except Exception as e:
        logger.critical(f"CRITICAL: Could not verify AI Laws: {e}")
        logger.critical("System cannot start without AI Laws verification.")
        raise RuntimeError("AI Laws verification system failed. Cannot start server.")
    
    # Start Background Knowledge Builder
    # await knowledge_builder.start()
    
    logger.info(f"Ollama Model: {settings.OLLAMA_MODEL}")
    logger.info(f"Ollama num_gpu: {settings.OLLAMA_NUM_GPU} (0=CPU, -1=full GPU, >0=split)")
    logger.info(f"RAG Database: {settings.CHROMA_DB_PATH}")

    # Initialize SQLite database
    # This creates all tables defined in models.py if they don't exist
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized.")

    # Ollama is required for chat; warn loudly if it is not up (common when only uvicorn is started from the IDE).
    try:
        import httpx
        base = settings.OLLAMA_BASE_URL.rstrip("/")
        async with httpx.AsyncClient(timeout=4.0) as oclient:
            r = await oclient.get(f"{base}/api/tags")
            if r.status_code == 200:
                logger.info(f"[OK] Ollama reachable at {base}")
            else:
                logger.warning(
                    "Ollama returned HTTP %s at %s — chat may fail until Ollama is healthy.",
                    r.status_code,
                    base,
                )
    except Exception as e:
        logger.warning(
            "%s\nOLLAMA NOT REACHABLE at %s (%s).\n"
            "Chat will fail until Ollama is running on port 11434.\n"
            "Fix: from the LAWFIRMAI folder run RESTART_EVERYTHING.bat, or START_OLLAMA_GPU.bat (keep open) then START_BACKEND.bat.\n"
            "Do not rely on starting only uvicorn from the IDE without Ollama.\n%s",
            "=" * 72,
            settings.OLLAMA_BASE_URL,
            e,
            "=" * 72,
        )

    # Yield control to FastAPI - app is now running
    yield
    
    # === SHUTDOWN SEQUENCE ===
    # This code runs when the server is shutting down
    logger.info("Shutting down server...")


# Create FastAPI application instance
# This is the main application object that handles all HTTP requests
app = FastAPI(
    title="Virginia Legal AI",
    description="Local AI-powered legal research and form generation system",
    version="1.0.0",
    lifespan=lifespan,  # Register lifespan manager for startup/shutdown
    # Increase request body size limit to 10MB for large legal documents/questions
    # This allows for very long messages (up to 5MB text + overhead)
)

# === MIDDLEWARE SETUP ===

# CORS (Cross-Origin Resource Sharing) middleware
# This allows the frontend (running on port 3000) to make API calls to the backend (port 5000)
# Also enables network access from other machines on the LAN
# In production, you should restrict allow_origins to specific domains/IPs via CORS_ORIGINS env var
cors_origins = settings.CORS_ORIGINS
if "*" in cors_origins:
    # Development mode - allow all origins but disable credentials
    allow_creds = False
    logger.warning("CORS: Allowing all origins (*) - this should be restricted in production")
else:
    # Production mode - specific origins, can enable credentials
    allow_creds = True
    logger.info(f"CORS: Restricted to origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Request ID middleware - adds unique ID to each request for tracing
# This should be first so all requests get an ID
app.add_middleware(RequestIDMiddleware)

# Rate limiting middleware - prevents abuse
# Limits requests per IP to prevent system overload
app.add_middleware(RateLimitMiddleware)

# Guardrails middleware - enforces AI Laws
# This middleware validates all chat requests/responses against the AI Laws code
# defined in config/ai_laws.json. It ensures the AI follows ethical guidelines.
app.add_middleware(GuardrailsMiddleware)

# Global exception handler for user-friendly error messages
from fastapi.exceptions import RequestValidationError
from server.utils.error_handler import handle_exception, AppError

@app.exception_handler(AppError)
async def app_error_handler(request, exc: AppError):
    """Handle application errors with user-friendly messages"""
    return handle_exception(exc, include_details=settings.DEBUG)

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    """Handle validation errors"""
    from server.utils.error_handler import create_error_response
    from server.utils.logger import setup_logger
    import json
    logger = setup_logger("main")
    
    # Log the validation errors for debugging
    errors = exc.errors()
    logger.warning(f"Validation error: {json.dumps(errors, indent=2)}")
    
    # Try to get the request body for debugging
    try:
        body = await request.body()
        logger.warning(f"Request body: {body[:500]}")  # First 500 chars
    except Exception as e:
        logger.warning(f"Could not read request body: {e}")
    
    # Return more detailed error message
    error_details = []
    for error in errors:
        field = ".".join(str(loc) for loc in error.get("loc", []))
        msg = error.get("msg", "Invalid value")
        error_type = error.get("type", "unknown")
        error_details.append(f"{field}: {msg} (type: {error_type})")
    
    return create_error_response(
        f"Invalid request: {', '.join(error_details)}",
        status_code=400
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle all other exceptions"""
    return handle_exception(exc, include_details=settings.DEBUG)

# === ROUTE REGISTRATION ===
# Register all API route modules with the FastAPI app
# Each router handles a specific feature area

# Authentication routes - login, registration, user management
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# Chat routes - main legal research query endpoint
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

# Documents routes - document management and storage
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])

# RAG routes - document upload, search, and retrieval (document reading/understanding)
app.include_router(rag.router, prefix="/api/rag", tags=["rag"])

# System routes - system status and health
app.include_router(system.router, prefix="/api/system", tags=["system"])

# === OPTIONAL FEATURES (disabled for simplified build) ===
# To re-enable, add the import and include_router() above. See docs/REMOVED_FEATURES.md.
# - forms, audit, monitoring, corrections, user_knowledge, reviews, matters
# - scenarios (conditional on SCENARIO_DB_ENABLED), validation


# === ROOT ENDPOINTS ===

@app.get("/")
async def root():
    """
    Root endpoint - returns basic service information
    Useful for checking if the server is running
    """
    return {
        "service": "Virginia Legal AI",
        "status": "running",
        "version": "1.0.0"
    }


async def _health_response():
    """Build health check response (database, Ollama, ChromaDB, disk). Used by /health and /api/health."""
    from sqlalchemy import text
    from pathlib import Path
    import shutil
    import requests

    checks = {
        "database": False,
        "ollama": False,
        "chromadb": False,
        "disk_space": False
    }

    try:
        from server.models import get_db
        db = next(get_db())
        db.execute(text("SELECT 1"))
        checks["database"] = True
        db.close()
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")

    try:
        response = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2)
        if response.status_code == 200:
            checks["ollama"] = True
    except Exception as e:
        logger.warning(f"Ollama health check failed: {e}")

    try:
        chroma_path = Path(settings.CHROMA_DB_PATH)
        if chroma_path.exists() and chroma_path.is_dir():
            checks["chromadb"] = True
    except Exception as e:
        logger.warning(f"ChromaDB health check failed: {e}")

    try:
        data_dir = Path(settings.DATA_DIR)
        if data_dir.exists():
            stat = shutil.disk_usage(data_dir)
            free_gb = stat.free / (1024 ** 3)
            checks["disk_space"] = free_gb >= 1.0
            checks["disk_free_gb"] = round(free_gb, 2)
    except Exception as e:
        logger.warning(f"Disk space check failed: {e}")

    all_healthy = all([
        checks["database"],
        checks["ollama"],
        checks["chromadb"],
        checks["disk_space"]
    ])
    status = "healthy" if all_healthy else "degraded"
    return {
        "status": status,
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/ping")
async def ping_root():
    """Liveness only — no DB/Ollama/Chroma. Use for quick port/process checks."""
    return {"ok": True}


@app.get("/api/ping")
async def ping_api():
    """Same as GET /ping; proxy-friendly."""
    return {"ok": True}


@app.get("/health")
async def health():
    """
    Health check endpoint.
    Used by monitoring and load balancers. Returns database, Ollama, ChromaDB, disk status.
    """
    return await _health_response()


@app.get("/api/health")
async def api_health():
    """
    Health check at /api/health for frontend (AdminDashboard, Login) and proxy-friendly URLs.
    Same response as /health.
    """
    return await _health_response()


# === SERVER STARTUP ===
# This code runs when the file is executed directly (python server/main.py)
# In production, you'd typically use: uvicorn server.main:app --host 0.0.0.0 --port 5000
if __name__ == "__main__":
    uvicorn.run(
        "main:app",  # Module path to FastAPI app
        host=settings.HOST,  # Listen on all interfaces (0.0.0.0)
        port=settings.PORT,  # Port 5000
        reload=settings.DEBUG,  # Auto-reload on code changes (development only)
        log_level="info"  # Logging verbosity
    )

