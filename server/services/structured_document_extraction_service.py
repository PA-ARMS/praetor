"""
Structured document extraction — patterns, NER, and optional LLM JSON.
Produces a single payload suitable for API responses and a compact RAG metadata line.
"""
import json
import re
from typing import Any, Dict, List, Optional

from server.config import settings
from server.utils.logger import setup_logger

logger = setup_logger("structured_document_extraction")


# Conservative patterns (high precision; not exhaustive)
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
_PHONE_RE = re.compile(
    r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"
)
_URL_RE = re.compile(
    r"https?://[^\s\]>\"']+|www\.[^\s\]>\"']+",
    re.IGNORECASE,
)
# Currency amounts (US-style)
_MONEY_RE = re.compile(
    r"(?:\$|USD\s?)\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s?(?:USD|dollars?)\b",
    re.IGNORECASE,
)


class StructuredDocumentExtractionService:
    """Combine regex signals, spaCy entities, and optional LLM structured fields."""

    def _pattern_extract(self, text: str) -> Dict[str, List[str]]:
        if not text:
            return {
                "emails": [],
                "phone_numbers": [],
                "urls": [],
                "currency_amounts": [],
            }
        emails = list(dict.fromkeys(_EMAIL_RE.findall(text)))[:30]
        phones = list(dict.fromkeys(_PHONE_RE.findall(text)))[:20]
        urls = list(dict.fromkeys(_URL_RE.findall(text)))[:20]
        money = list(dict.fromkeys(_MONEY_RE.findall(text)))[:40]
        return {
            "emails": emails,
            "phone_numbers": phones,
            "urls": urls,
            "currency_amounts": money,
        }

    def _parse_json_from_llm(self, raw: str) -> Optional[Dict[str, Any]]:
        if not raw or not raw.strip():
            return None
        s = raw.strip()
        if s.startswith("```"):
            s = re.sub(r"^```\w*\s*", "", s)
            s = re.sub(r"\s*```$", "", s)
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(s[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("LLM returned non-JSON structured extraction")
        return None

    async def _llm_structured(self, text: str, filename: str) -> Optional[Dict[str, Any]]:
        from server.services.ollama_service import ollama_service

        sample = text[:12000] if len(text) > 12000 else text
        system = (
            "You extract factual structured data from legal and business documents. "
            "Respond with a single JSON object only — no markdown fences, no commentary."
        )
        prompt = f"""Filename: {filename}

From the document text, fill this JSON shape. Use empty strings or empty arrays where unknown.
Keys:
- document_title: short title or subject line if inferable
- parties: people or party names explicitly mentioned
- organizations: companies, agencies, firms
- key_dates: important dates as written
- amounts_currency: monetary amounts (with currency if stated)
- email_addresses, phone_numbers: from the text
- addresses: mailing or venue addresses if present
- legal_issues_or_topics: short phrases
- obligations_or_deadlines: duties, due dates, must/shall items
- defined_terms_or_key_definitions: quoted defined terms or explicit definitions

Text:
{sample}
"""
        raw = await ollama_service.generate(
            prompt,
            system_prompt=system,
            max_tokens=2048,
        )
        return self._parse_json_from_llm(raw)

    def build_metadata_summary(self, bundle: Dict[str, Any]) -> str:
        """Single compact line for Chroma (per-chunk metadata size)."""
        parts: List[str] = []
        pat = bundle.get("patterns") or {}
        if pat.get("emails"):
            parts.append(f"emails:{len(pat['emails'])}")
        if pat.get("currency_amounts"):
            parts.append(f"amounts:{len(pat['currency_amounts'])}")
        ent = bundle.get("entities") or {}
        for k in ("parties", "case_numbers", "statutes"):
            v = ent.get(k)
            if isinstance(v, list) and v:
                parts.append(f"{k}:{len(v)}")
        llm = bundle.get("llm_structured")
        if isinstance(llm, dict):
            t = (llm.get("document_title") or "").strip()
            if t:
                parts.append(t[:120])
        methods = bundle.get("methods_used") or []
        if methods:
            parts.append(f"methods:{','.join(methods)}")
        out = " | ".join(parts) if parts else "structured_extraction"
        return out[:512]

    async def extract_all(
        self,
        text: str,
        filename: str,
        skip_llm: bool = False,
    ) -> Dict[str, Any]:
        """
        Full structured extraction. Always includes patterns; entities if spaCy loads;
        LLM JSON block if DOCUMENT_LLM_EXTRACTION_ENABLED, not skip_llm, and Ollama succeeds.

        skip_llm: set True when upload will run document_understanding (same Ollama pass) to avoid duplicate calls.
        """
        methods: List[str] = ["patterns"]

        patterns = self._pattern_extract(text)

        entities: Dict = {}
        if settings.ENTITY_EXTRACTION_ENABLED:
            try:
                from server.services.entity_extraction_service import entity_extraction_service

                if entity_extraction_service.is_available():
                    entities = entity_extraction_service.extract_entities(text) or {}
                    methods.append("entities")
            except Exception as e:
                logger.warning(f"Entity extraction failed: {e}")

        llm_structured: Optional[Dict[str, Any]] = None
        if (
            settings.DOCUMENT_LLM_EXTRACTION_ENABLED
            and text.strip()
            and not skip_llm
        ):
            try:
                llm_structured = await self._llm_structured(text, filename)
                if llm_structured:
                    methods.append("llm")
            except Exception as e:
                logger.warning(f"LLM structured extraction failed: {e}")

        tq = min(1.0, max(0.0, len(text.strip()) / 4000.0))
        if len(text.strip()) < 80:
            tq *= 0.5

        bundle: Dict[str, Any] = {
            "patterns": patterns,
            "entities": entities,
            "llm_structured": llm_structured,
            "methods_used": methods,
            "text_quality_score": round(tq, 2),
        }
        return bundle


structured_document_extraction_service = StructuredDocumentExtractionService()
