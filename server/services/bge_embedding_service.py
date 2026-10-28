"""
BGE Embedding Service
Uses sentence-transformers BGE model for embeddings (optional alternative to Ollama)
"""
import asyncio
from typing import List, Optional

from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("bge_embedding")


class BGEEmbeddingService:
    """Service for embeddings using BGE model"""

    def __init__(self):
        self.logger = logger
        self._model = None
        self._available: Optional[bool] = None
        self._dimension = 768  # BGE-base; BGE-large is 1024

    def _ensure_loaded(self) -> bool:
        """Lazy-load BGE model"""
        if self._model is not None:
            return True
        if not settings.BGE_EMBEDDINGS_ENABLED:
            return False
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("BAAI/bge-base-en-v1.5")
            self._available = True
            self.logger.info("BGE embedding model loaded")
            return True
        except Exception as e:
            self.logger.warning(f"Could not load BGE model: {e}")
            self._available = False
            return False

    def is_available(self) -> bool:
        """Check if BGE embeddings are available"""
        if self._available is not None:
            return self._available
        return self._ensure_loaded()

    @property
    def dimension(self) -> int:
        """Embedding dimension (768 for base, 1024 for large)"""
        return self._dimension

    def _embed_sync(self, text: str) -> List[float]:
        """Synchronous embedding (runs in thread when called via embed)"""
        if not text or not text.strip():
            return []
        embedding = self._model.encode(text.strip(), convert_to_numpy=True)
        return embedding.tolist()

    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding for text (async for compatibility with ollama_service).

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector)
        """
        if not settings.BGE_EMBEDDINGS_ENABLED or not self._ensure_loaded():
            return []

        if not text or not text.strip():
            return []

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._embed_sync, text.strip())
        except Exception as e:
            self.logger.warning(f"BGE embedding failed: {e}")
            return []


bge_embedding_service = BGEEmbeddingService()
