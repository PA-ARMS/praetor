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
- TTS service preloading
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

# Import all route modules - these handle API endpoints
from server.routes import chat, forms, documents, rag, auth, tts, audit, corrections, user_knowledge, monitoring, system, reviews
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
    logger.info(f"RAG Database: {settings.CHROMA_DB_PATH}")

    # Configure eSpeak NG PATH for Coqui TTS on Windows
    # Coqui TTS requires eSpeak NG for phoneme generation, but Windows doesn't
    # always have it in PATH. We search common installation locations and add them.
    try:
        import platform, os
        if platform.system().lower().startswith("win"):
            espeak_candidates = [
                r"C:\Program Files\eSpeak NG",
                r"C:\Program Files (x86)\eSpeak NG",
            ]
            current_path = os.environ.get("PATH", "")
            for p in espeak_candidates:
                if os.path.isdir(p) and p not in current_path:
                    os.environ["PATH"] = current_path + os.pathsep + p
                    current_path = os.environ["PATH"]
            logger.debug("TTS PATH configured for eSpeak NG")
    except Exception as e:
        logger.warning(f"Could not adjust PATH for eSpeak NG: {e}")
    
    # Initialize SQLite database
    # This creates all tables defined in models.py if they don't exist
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized.")
    
    # Preload TTS service (optional but recommended)
    # Preloading downloads/loads the TTS model at startup so the first
    # text-to-speech request is faster. If TTS fails, the app continues without it.
    try:
        if settings.TTS_ENABLED:
            from server.services.tts_service import get_tts_service
            svc = get_tts_service()
            # Only initialize if not already done (prevents duplicate initialization)
            if not svc.initialized:
                logger.info("Preloading TTS model...")
                # Use configured model or default to high-quality VCTK model
                svc.initialize(model_name=settings.TTS_MODEL or "tts_models/en/vctk/vits",
                               voice_name=(settings.TTS_VOICE or None))
                logger.info("TTS preloaded.")
    except Exception as e:
        # TTS is optional - log warning but don't fail startup
        logger.warning(f"TTS service not available or failed to initialize: {e}")
    
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
    lifespan=lifespan  # Register lifespan manager for startup/shutdown
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
    return create_error_response(
        "Invalid request. Please check your input and try again.",
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

# Forms routes - legal form generation and management
app.include_router(forms.router, prefix="/api/forms", tags=["forms"])

# Documents routes - document management and storage
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])

# RAG routes - document upload, search, and retrieval
app.include_router(rag.router, prefix="/api/rag", tags=["rag"])

# TTS routes - text-to-speech functionality
app.include_router(tts.router, prefix="/api/tts", tags=["tts"])

# Audit routes - audit log viewing (admin/attorney only)
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])

# Monitoring routes - system health and statistics (admin/attorney only)
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])

# System routes - system status and stats
app.include_router(system.router, prefix="/api/system", tags=["system"])

# Corrections routes - user feedback and correction system
app.include_router(corrections.router, tags=["corrections"])

# User Knowledge routes - user-provided legal knowledge library
app.include_router(user_knowledge.router, tags=["user-knowledge"])

# Reviews routes - senior partner review system for AI responses
app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])

# Scenario routes - predictive case outcome analysis (optional feature)
# Only enabled if SCENARIO_DB_ENABLED environment variable is set to "True"
# This feature requires downloading and processing legal cases
logger.info(f"Checking SCENARIO_DB_ENABLED: value={settings.SCENARIO_DB_ENABLED}, type={type(settings.SCENARIO_DB_ENABLED)}")
logger.info(f"Environment variable SCENARIO_DB_ENABLED: {os.getenv('SCENARIO_DB_ENABLED', 'NOT SET')}")
if settings.SCENARIO_DB_ENABLED:
    try:
        from server.routes import scenarios
        app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
        logger.info("[OK] Scenario database features enabled")
    except Exception as e:
        logger.warning(f"Could not load scenario routes: {e}")
        import traceback
        logger.warning(traceback.format_exc())
else:
    logger.info("[INFO] Scenario database features disabled (set SCENARIO_DB_ENABLED=True to enable)")

# Validation routes - prediction validation and error analysis (optional feature)
# Used for testing AI accuracy and learning from mistakes
try:
    from server.routes import validation
    app.include_router(validation.router, prefix="/api/validation", tags=["validation"])
    logger.info("[OK] Validation and error analysis features enabled")
except Exception as e:
    logger.warning(f"Could not load validation routes: {e}")


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


@app.get("/health")
async def health():
    """
    Health check endpoint
    Used by monitoring systems and load balancers to verify server is healthy
    Returns detailed health status including database, Ollama, and ChromaDB connectivity
    """
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
    
    # Check database connectivity
    try:
        from server.models import get_db
        db = next(get_db())
        db.execute(text("SELECT 1"))
        checks["database"] = True
        db.close()
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
    
    # Check Ollama service
    try:
        response = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2)
        if response.status_code == 200:
            checks["ollama"] = True
    except Exception as e:
        logger.warning(f"Ollama health check failed: {e}")
    
    # Check ChromaDB
    try:
        chroma_path = Path(settings.CHROMA_DB_PATH)
        if chroma_path.exists() and chroma_path.is_dir():
            checks["chromadb"] = True
    except Exception as e:
        logger.warning(f"ChromaDB health check failed: {e}")
    
    # Check disk space (at least 1GB free)
    try:
        data_dir = Path(settings.DATA_DIR)
        if data_dir.exists():
            stat = shutil.disk_usage(data_dir)
            free_gb = stat.free / (1024 ** 3)
            checks["disk_space"] = free_gb >= 1.0
            checks["disk_free_gb"] = round(free_gb, 2)
    except Exception as e:
        logger.warning(f"Disk space check failed: {e}")
    
    # Overall status
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

