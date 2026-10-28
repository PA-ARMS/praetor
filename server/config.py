"""Configuration settings"""
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from typing import List, Any, Optional
import os
import warnings


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 5001  # 5001 avoids Windows port 5000 conflict (AirPlay/UPnP)
    DEBUG: bool = False
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    # Default: small model often present after `ollama pull llama3.2:1b`. Override in .env (e.g. initium/law_model:latest).
    OLLAMA_MODEL: str = "llama3.2:1b"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    # -1 = NVIDIA GPU 1 only (app sends num_gpu=99; Ollama must be started with CUDA_VISIBLE_DEVICES=1). 0 = CPU only.
    OLLAMA_NUM_GPU: int = -1
    # Context window for /api/generate. 8192 is a good default for speed; raise for very long attachments.
    OLLAMA_NUM_CTX: int = 8192

    # Chat/RAG speed (simple endpoint uses these)
    CHAT_RAG_MAX_VARIATIONS: int = 4  # Max synonym query variants (was 10; each costs an embed+search)
    CHAT_SIMPLE_N_RESULTS: int = 8
    CHAT_SIMPLE_MAX_CONTEXT_SOURCES: int = 12
    CHAT_SIMPLE_SOURCE_SNIPPET_CHARS: int = 700
    CHAT_SIMPLE_MAX_OUTPUT_TOKENS: int = 768
    CHAT_SKIP_CASE_CONTEXT: bool = True  # Skip scenario DB case lookup on simple chat (saves seconds)
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/legal_ai.db"
    
    # RAG
    CHROMA_DB_PATH: str = "./data/chroma_db"
    EMBEDDING_DIMENSION: int = 768
    # In-process cache sizes (reduce if 32GB RAM is tight). RAG cache holds full search results; embed cache holds vectors.
    RAG_QUERY_CACHE_SIZE: int = 256
    OLLAMA_EMBED_CACHE_SIZE: int = 512

    # Semantic response cache (SQLite + embeddings): similar questions reuse prior answers (skips RAG + LLM)
    SEMANTIC_CACHE_ENABLED: bool = True
    SEMANTIC_CACHE_MIN_SIMILARITY: float = 0.88
    SEMANTIC_CACHE_MAX_CANDIDATES: int = 400
    SEMANTIC_CACHE_MAX_PER_USER: int = 2000
    
    # Security
    JWT_SECRET: str = "change-this-secret-key"
    ENCRYPTION_KEY: str = "change-this-32-char-encryption-key"
    
    # Network
    ALLOWED_IPS: str = "192.168.1.0/24,127.0.0.1"
    # CORS - Allow all origins from local network (for development)
    # In production, specify exact IPs: ["http://localhost:3000", "http://192.168.1.32:3000"]
    CORS_ORIGINS: List[str] = ["*"]  # Allow all origins for network access
    
    # File Upload Limits
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB default
    ALLOWED_FILE_EXTENSIONS: List[str] = [
        ".pdf", ".txt", ".docx", ".html", ".htm", ".md",
        ".png", ".jpg", ".jpeg", ".jfif", ".webp", ".tif", ".tiff", ".bmp",
    ]
    
    # Password Policy
    MIN_PASSWORD_LENGTH: int = 12
    REQUIRE_PASSWORD_COMPLEXITY: bool = True
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_CHAT_PER_MINUTE: int = 30
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 60
    
    # Token Expiration
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    
    @field_validator('JWT_SECRET')
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret is not using default value"""
        default_secrets = ["change-this-secret-key", ""]
        if v in default_secrets:
            if not os.getenv("JWT_SECRET"):  # Only warn if not set via env
                warnings.warn(
                    "⚠️  SECURITY WARNING: JWT_SECRET is using default value! "
                    "Set JWT_SECRET in .env file with a strong random string (32+ characters). "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'",
                    UserWarning,
                    stacklevel=2
                )
        elif len(v) < 32:
            warnings.warn(
                f"⚠️  SECURITY WARNING: JWT_SECRET is only {len(v)} characters. "
                "Recommend at least 32 characters for production.",
                UserWarning,
                stacklevel=2
            )
        return v
    
    @field_validator('ENCRYPTION_KEY')
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Validate encryption key is not using default value"""
        default_keys = ["change-this-32-char-encryption-key", ""]
        if v in default_keys:
            if not os.getenv("ENCRYPTION_KEY"):  # Only warn if not set via env
                warnings.warn(
                    "⚠️  SECURITY WARNING: ENCRYPTION_KEY is using default value! "
                    "Set ENCRYPTION_KEY in .env file with a strong random string (32 characters). "
                    "Generate with: python -c 'import secrets; print(secrets.token_hex(16))'",
                    UserWarning,
                    stacklevel=2
                )
        elif len(v) < 32:
            warnings.warn(
                f"⚠️  SECURITY WARNING: ENCRYPTION_KEY is only {len(v)} characters. "
                "Must be exactly 32 characters for AES-256.",
                UserWarning,
                stacklevel=2
            )
        return v
    
    @field_validator('CORS_ORIGINS')
    @classmethod
    def validate_cors_origins(cls, v: List[str]) -> List[str]:
        """Warn if CORS allows all origins in production"""
        if "*" in v and not os.getenv("DEBUG", "").lower() in ["true", "1", "yes"]:
            warnings.warn(
                "⚠️  SECURITY WARNING: CORS allows all origins (*). "
                "In production, restrict to specific domains in CORS_ORIGINS environment variable.",
                UserWarning,
                stacklevel=2
            )
        return v
    
    @model_validator(mode='before')
    @classmethod
    def strip_boolean_whitespace(cls, data: Any) -> Any:
        """Strip whitespace from boolean environment variables before parsing"""
        if isinstance(data, dict):
            # List of boolean field names
            boolean_fields = [
                'SCENARIO_DB_ENABLED', 'DEBUG', 'RATE_LIMIT_ENABLED',
                'REQUIRE_PASSWORD_COMPLEXITY', 'DOCUMENT_READER_ENABLED', 'NEURAL_OCR_ENABLED',
                'SUMMARIZATION_MODEL_ENABLED', 'BGE_EMBEDDINGS_ENABLED', 'ENTITY_EXTRACTION_ENABLED',
                'TABLE_EXTRACTION_ENABLED', 'SEMANTIC_CACHE_ENABLED', 'DOCUMENT_LLM_EXTRACTION_ENABLED',
                'LIVE_LEGAL_LOOKUP_ENABLED',
            ]
            for field in boolean_fields:
                if field in data and isinstance(data[field], str):
                    data[field] = data[field].strip()
        return data
    
    # Paths
    DATA_DIR: str = "./data"
    FORMS_DIR: str = "./data/forms"
    TEMPLATES_DIR: str = "./data/templates"
    CORPUS_DIR: str = "./data/corpus"
    AUDIO_DIR: str = "./data/audio"
    
    # Feature Flags (simplified build: scenario DB off by default; see docs/REMOVED_FEATURES.md)
    SCENARIO_DB_ENABLED: bool = False  # Set True to re-enable Scenario Analysis
    SCENARIO_DB_PATH: str = "./data/scenario_db"  # Path for scenario ChromaDB

    # Document Pipeline (parallel models)
    DOCUMENT_READER_ENABLED: bool = True  # Unstructured layout parsing
    NEURAL_OCR_ENABLED: bool = True  # EasyOCR fallback
    SUMMARIZATION_MODEL_ENABLED: bool = True  # BART for document summaries
    BGE_EMBEDDINGS_ENABLED: bool = False  # Set True when GPU has headroom; False avoids OOM with 7B
    ENTITY_EXTRACTION_ENABLED: bool = True  # spaCy NER
    TABLE_EXTRACTION_ENABLED: bool = True  # Camelot/Tabula
    # LLM JSON pass for parties, amounts, issues, etc. (requires Ollama). Patterns + NER always run when enabled.
    DOCUMENT_LLM_EXTRACTION_ENABLED: bool = True
    
    # Detail Level Configuration
    # Configures token limits and context handling for different response detail levels
    DETAIL_LEVELS: dict = {
        "summary": {
            "max_tokens": 768,  # Reduced from 1024 for faster generation
            "context_chars": 250,  # Reduced from 300 for faster processing
            "instruction": "Provide a concise summary with key cases only."
        },
        "standard": {
            "max_tokens": 1536,  # Reduced from 2048 for faster generation
            "context_chars": 800,  # Reduced from 1000 for faster processing
            "instruction": "Provide comprehensive analysis with all relevant cases."
        },
        "comprehensive": {
            "max_tokens": 6144,
            "context_chars": None,
            "instruction": "Provide detailed analysis including ALL cases with complete citations and excerpts."
        },
        "complete": {
            "max_tokens": 16384,
            "context_chars": None,
            "instruction": "Provide exhaustive legal analysis - include EVERY relevant authority with complete citations and full case summaries."
        },
        "unlimited": {
            "max_tokens": 32768,
            "context_chars": None,
            "instruction": "Complete unrestricted analysis - include all cases, all citations, all relevant excerpts, procedural history, and comprehensive legal reasoning."
        }
    }
    
    # Partner reviewers for user corrections (Peyton, Yulia - round-robin assignment)
    CORRECTION_REVIEWER_USERNAMES: List[str] = ["peyton.akers", "yulia.kovregina"]
    
    # API Keys (optional, used by download scripts)
    COURTLISTENER_API_KEY: str = ""  # CourtListener API key for downloading cases
    CAP_API_KEY: str = ""  # CAP (Caselaw Access Project) API key

    # Live official-source lookup during chat (no API keys). Allowlisted .gov pages only.
    LIVE_LEGAL_LOOKUP_ENABLED: bool = True
    LIVE_LEGAL_LOOKUP_TIMEOUT_SECONDS: float = 8.0
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env that aren't defined here


settings = Settings()

# Create directories if they don't exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.FORMS_DIR, exist_ok=True)
os.makedirs(settings.TEMPLATES_DIR, exist_ok=True)
os.makedirs(settings.CORPUS_DIR, exist_ok=True)
os.makedirs(settings.AUDIO_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)
# Create scenario directories if feature is enabled
if settings.SCENARIO_DB_ENABLED:
    os.makedirs(settings.SCENARIO_DB_PATH, exist_ok=True)
    os.makedirs(os.path.join(settings.DATA_DIR, "scenarios"), exist_ok=True)

