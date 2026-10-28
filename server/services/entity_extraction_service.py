"""
Entity Extraction Service
Extracts legal entities (parties, dates, statutes, courts) using spaCy NER
"""
import re
from typing import Dict, List, Optional

from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("entity_extraction")


class EntityExtractionService:
    """Service for extracting entities from legal text using spaCy"""

    def __init__(self):
        self.logger = logger
        self._nlp = None
        self._available: Optional[bool] = None

    def _ensure_loaded(self) -> bool:
        """Lazy-load spaCy model"""
        if self._nlp is not None:
            return True
        if not settings.ENTITY_EXTRACTION_ENABLED:
            return False
        try:
            import spacy
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                self.logger.warning("spaCy model en_core_web_sm not found. Run: python -m spacy download en_core_web_sm")
                return False
            self._available = True
            return True
        except ImportError as e:
            self.logger.warning(f"spaCy not installed: {e}")
            self._available = False
            return False

    def is_available(self) -> bool:
        """Check if entity extraction is available"""
        if self._available is not None:
            return self._available
        return self._ensure_loaded()

    def extract_entities(self, text: str, max_chars: int = 50000) -> Dict:
        """
        Extract legal entities from text.

        Args:
            text: Document text to analyze
            max_chars: Maximum characters to process (spaCy can be slow on long text)

        Returns:
            Dict with keys: parties, dates, case_numbers, statutes, courts
        """
        if not settings.ENTITY_EXTRACTION_ENABLED or not self._ensure_loaded():
            return self._empty_entities()

        if not text or not text.strip():
            return self._empty_entities()

        try:
            # Truncate for performance
            analysis_text = text[:max_chars] if len(text) > max_chars else text

            doc = self._nlp(analysis_text)

            parties: List[str] = []
            dates: List[str] = []
            case_numbers: List[str] = []
            statutes: List[str] = []
            courts: List[str] = []

            # Extract from NER
            for ent in doc.ents:
                label = ent.label_
                value = ent.text.strip()
                if not value:
                    continue
                if label in ("PERSON", "ORG", "GPE"):
                    if value not in parties and len(value) > 2:
                        parties.append(value)
                elif label == "DATE":
                    if value not in dates:
                        dates.append(value)
                elif label == "LAW" or "statute" in value.lower() or "§" in value or "section" in value.lower():
                    if value not in statutes:
                        statutes.append(value)

            # Regex for case numbers (e.g., CL-2025-12345, 1:23-cv-456)
            case_pattern = r'\b(?:CL|CR|CA|CH|EP|FC|GC|PR)-\d{4,}-\d+\b|\b\d{1,2}:\d{2}-cv-\d+\b|\bNo\.\s*\d+\b'
            for match in re.finditer(case_pattern, text, re.IGNORECASE):
                cn = match.group(0).strip()
                if cn not in case_numbers:
                    case_numbers.append(cn)

            # Regex for Virginia/federal statute citations
            va_statute = r'§\s*\d+\.\d+-\d+|\b\d+\.\d+-\d+[A-Z]?\b'
            for match in re.finditer(va_statute, text):
                s = match.group(0).strip()
                if s not in statutes:
                    statutes.append(s)

            # Court names (common patterns)
            court_pattern = r'(?:Circuit Court|District Court|Supreme Court|Court of Appeals|Superior Court)[^.]{0,80}'
            for match in re.finditer(court_pattern, text, re.IGNORECASE):
                court = match.group(0).strip()
                if len(court) < 100 and court not in courts:
                    courts.append(court)

            return {
                "parties": parties[:20],
                "dates": dates[:20],
                "case_numbers": case_numbers[:20],
                "statutes": statutes[:20],
                "courts": courts[:10],
            }
        except Exception as e:
            self.logger.warning(f"Entity extraction failed: {e}")
            return self._empty_entities()

    def _empty_entities(self) -> Dict:
        """Return empty entity structure"""
        return {
            "parties": [],
            "dates": [],
            "case_numbers": [],
            "statutes": [],
            "courts": [],
        }


entity_extraction_service = EntityExtractionService()
