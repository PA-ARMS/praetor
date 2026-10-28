"""
Summarization Service
Uses BART model for fast document summarization without main LLM
"""
from typing import Optional

from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("summarization")


class SummarizationService:
    """Service for summarizing documents using BART"""

    def __init__(self):
        self.logger = logger
        self._model = None
        self._tokenizer = None
        self._available: Optional[bool] = None

    def _ensure_loaded(self) -> bool:
        """Lazy-load BART summarizer"""
        if getattr(self, "_summarizer", None) is not None:
            return True
        if not settings.SUMMARIZATION_MODEL_ENABLED:
            return False
        try:
            from transformers import pipeline
            # Use pipeline for simplicity; runs on CPU if no GPU
            self._summarizer = pipeline(
                "summarization",
                model="facebook/bart-large-cnn",
                device=-1,  # -1 = CPU, 0 = GPU
            )
            self._available = True
            self.logger.info("BART summarization model loaded")
            return True
        except Exception as e:
            self.logger.warning(f"Could not load BART summarization model: {e}")
            self._available = False
            return False

    def is_available(self) -> bool:
        """Check if summarization is available"""
        if self._available is not None:
            return self._available
        return self._ensure_loaded()

    def summarize(self, text: str, max_length: int = 150, min_length: int = 30) -> str:
        """
        Summarize text using BART.

        Args:
            text: Text to summarize
            max_length: Maximum summary length in tokens
            min_length: Minimum summary length in tokens

        Returns:
            Summary string, or empty string on failure
        """
        if not settings.SUMMARIZATION_MODEL_ENABLED or not self._ensure_loaded():
            return ""

        if not text or not text.strip():
            return ""

        try:
            # BART has 1024 token limit; truncate input
            max_input_length = 1024 * 4  # ~4k chars
            if len(text) > max_input_length:
                text = text[:max_input_length] + "..."

            result = self._summarizer(
                text,
                max_length=max_length,
                min_length=min_length,
                do_sample=False,
                truncation=True,
            )
            if result and len(result) > 0:
                summary = result[0].get("summary_text", "").strip()
                return summary if summary else ""
            return ""
        except Exception as e:
            self.logger.warning(f"Summarization failed: {e}")
            return ""


summarization_service = SummarizationService()
