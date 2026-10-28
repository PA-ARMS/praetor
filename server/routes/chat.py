"""
Chat API routes - Legal research queries
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator, Field
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
import json
import time

from server.services.ollama_service import ollama_service
from server.services.rag_service import rag_service
from server.services.guardrails_service import guardrails_service
from server.services.scotus_service import scotus_service
from server.services.semantic_cache_service import semantic_cache_service
from server.services.live_legal_lookup_service import live_legal_lookup_service
from server.config import settings
import re


def _format_bluebook_citation(citation: str) -> str:
    """
    Format citation to Bluebook format (industry standard).
    SCOTUS format: [Volume] U.S. [Page] (e.g., "384 U.S. 436")
    Handles multiple variations robustly.
    """
    if not citation:
        return ""
    
    # Remove extra whitespace and normalize
    citation = re.sub(r'\s+', ' ', citation.strip())
    
    # Multiple patterns to catch all variations
    patterns = [
        r'(\d+)\s+U\.?\s*S\.?\s+(\d+)',      # 606 U.S. 748 or 606 U. S. 748
        r'(\d+)\s+U\.\s*S\.\s+(\d+)',        # 606 U. S. 748 (with spaces)
        r'(\d+)\s+S\.?\s*Ct\.?\s+(\d+)',     # 606 S. Ct. 748
        r'(\d+)\s*U\.?\s*S\.?\s*(\d+)',      # 606U.S.748 (no spaces)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, citation)
        if match:
            volume = match.group(1)
            page = match.group(2)
            # Validate reasonable ranges
            try:
                vol_num = int(volume)
                page_num = int(page)
                if 1 <= vol_num <= 700 and 1 <= page_num <= 2000:
                    return f"{volume} U.S. {page}"
            except ValueError:
                continue
    
    # If no pattern matched, return original (might already be correct)
    return citation
from server.models import get_db, User, ChatMessage
from server.middleware.auth_middleware import require_auth
from server.services.auth_service import can_view_user_chat, get_accessible_user_ids


router = APIRouter()


_SOURCE_CATALOG_CACHE = None


def _load_source_catalog() -> Dict[str, dict]:
    """
    Load the source catalog so we can enrich sources with priority and URLs.
    Cached in-process for performance.
    """
    global _SOURCE_CATALOG_CACHE
    if _SOURCE_CATALOG_CACHE is not None:
        return _SOURCE_CATALOG_CACHE

    try:
        catalog_path = Path(__file__).parent.parent.parent / "config" / "source_catalog.json"
        if not catalog_path.exists():
            _SOURCE_CATALOG_CACHE = {}
            return _SOURCE_CATALOG_CACHE

        with catalog_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        mapping: Dict[str, dict] = {}
        for s in data.get("sources", []):
            key = s.get("name") or s.get("id")
            if key:
                mapping[key] = s

        _SOURCE_CATALOG_CACHE = mapping
        return _SOURCE_CATALOG_CACHE
    except Exception:
        _SOURCE_CATALOG_CACHE = {}
        return _SOURCE_CATALOG_CACHE


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    use_rag: bool = True
    max_results: int = 0  # 0 means no limit - return all relevant results
    doc_sources: Optional[List[str]] = None
    # Raw text from upload API (same turn); bypasses flaky vector lookup for chat context
    attachment_extracted_text: Optional[str] = Field(default=None, max_length=150000)
    include_scenario_analysis: Optional[bool] = None  # Auto-detect if None
    detail_level: Optional[str] = None  # "summary", "standard", "comprehensive", "complete", "unlimited", or None for auto
    exhaustive_search: bool = False  # Enable exhaustive trial prep mode (500+ sources)
    max_output_tokens: Optional[int] = None  # Override token limit
    skip_clarification: bool = False  # When True, answer with best effort even if clarification would normally be asked
    response_format: Optional[str] = None  # "memo" | "conversational" | None (auto: memo for legal/mixed)
    use_web: Optional[bool] = None  # Live official-source lookup; None = use server default
    
    # Pydantic v2 configuration
    model_config = {
        "from_attributes": True,  # Allow ORM mode
        "str_strip_whitespace": True,  # Automatically strip whitespace from strings
    }
    
    @field_validator('message')
    def validate_message(cls, v):
        """Validate message length and content"""
        if not v:
            raise ValueError("Message cannot be empty")
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be empty")
        MAX_MESSAGE_LENGTH = 50000  # Prevent abuse; long legal queries still allowed
        if len(stripped) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message must be {MAX_MESSAGE_LENGTH:,} characters or fewer")
        return stripped
    
    @field_validator('conversation_id')
    def validate_conversation_id(cls, v):
        """Validate conversation ID format"""
        if v and len(v) > 200:
            raise ValueError("Conversation ID too long")
        return v
    
    @field_validator('max_results', mode='before')
    @classmethod
    def validate_max_results(cls, v):
        """Coerce max_results to int if it's a string"""
        if v is None:
            return 0
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0  # Default to 0 if conversion fails
    
    @field_validator('exhaustive_search', mode='before')
    @classmethod
    def validate_exhaustive_search(cls, v):
        """Coerce exhaustive_search to bool"""
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on')
        return bool(v)
    
    @field_validator('use_rag', mode='before')
    @classmethod
    def validate_use_rag(cls, v):
        """Coerce use_rag to bool"""
        if v is None:
            return True  # Default to True
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on')
        return bool(v)

    @field_validator('use_web', mode='before')
    @classmethod
    def validate_use_web(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on')
        return bool(v)
    
    @field_validator('max_output_tokens', mode='before')
    @classmethod
    def validate_max_output_tokens(cls, v):
        """Coerce max_output_tokens to int if it's a string"""
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None  # Return None if conversion fails


def _effective_response_format(request: ChatRequest, intent_mode: str) -> str:
    """
    Firm default: research memo for legal/mixed; conversational for general.
    Explicit request.response_format overrides when set.
    """
    raw = getattr(request, "response_format", None)
    if raw is not None and str(raw).strip():
        v = str(raw).strip().lower()
        if v in ("memo", "research_memo", "firm", "legal_memo"):
            return "research_memo"
        if v in ("conversational", "chat", "plain"):
            return "conversational"
    if intent_mode in ("legal", "mixed"):
        return "research_memo"
    return "conversational"


def _want_live_lookup(request: ChatRequest) -> bool:
    if request.use_web is False:
        return False
    if request.use_web is True:
        return bool(getattr(settings, "LIVE_LEGAL_LOOKUP_ENABLED", True))
    return bool(getattr(settings, "LIVE_LEGAL_LOOKUP_ENABLED", True))


async def _merge_live_official_sources(query: str, sources_raw: List[Dict], warnings: List[str]) -> int:
    """Fetch allowlisted official pages and prepend them to retrieved sources."""
    try:
        live_hits = await live_legal_lookup_service.lookup(query)
    except Exception as e:
        warnings.append(f"Live official lookup failed: {e}")
        return 0
    if not live_hits:
        return 0
    existing = {s.get("id") for s in sources_raw}
    added = 0
    for hit in reversed(live_hits):
        sid = hit.get("id")
        if sid in existing:
            continue
        sources_raw.insert(0, hit)
        existing.add(sid)
        added += 1
    if added:
        warnings.append(
            f"Included {added} live official page(s) from law.lis.virginia.gov / allowlisted government sites. "
            "Verify effective dates independently before filing."
        )
    return added


class ChatResponse(BaseModel):
    response: str
    sources: List[dict]
    conversation_id: str
    timestamp: str
    warnings: List[str] = []
    message_id: Optional[int] = None
    scenario_prediction: Optional[dict] = None  # Scenario analysis if applicable
    detail_level: Optional[str] = None  # Actual detail level used
    recommended_level: Optional[str] = None  # Smart default recommendation
    is_streaming: bool = False  # Whether response was streamed
    total_sources: Optional[int] = None  # Total raw sources considered
    unique_sources: Optional[int] = None  # Unique grouped sources in summary
    verification_status: Optional[str] = None  # RAG verification status
    authoritative_sources_count: Optional[int] = None  # Count of authoritative source groups
    secondary_sources_count: Optional[int] = None  # Count of secondary source groups
    conflict_messages: Optional[List[str]] = None  # High-level conflict / verification messages
    search_total_results: Optional[int] = None  # Total raw RAG hits
    search_unique_sources: Optional[int] = None  # Unique source groups in RAG
    clarification_only: bool = False  # True when AI returned only clarification questions (clarify-first)
    clarification_questions: Optional[List[str]] = None  # Raw questions for UI display
    semantic_cache_hit: bool = False  # True when answer was reused from semantic similarity cache
    response_format: Optional[str] = None  # "research_memo" or "conversational" — how the answer was structured


class ChatHistoryResponse(BaseModel):
    id: int
    user_id: int
    username: str
    full_name: str
    conversation_id: str
    message: str
    response: Optional[str]
    sources: Optional[List[dict]]
    warnings: Optional[List[str]]
    timestamp: str
    
    class Config:
        from_attributes = True


class ChatHistoryListResponse(BaseModel):
    messages: List[ChatHistoryResponse]
    total: int


_LEGAL_FILENAME_MARKERS = frozenset(
    (
        "motion",
        "nonsuit",
        "dismiss",
        "complaint",
        "answer",
        "exhibit",
        "brief",
        "pleading",
        "discovery",
        "subpoena",
        "judgment",
        "memorandum",
        "response",
        "opposition",
        "demurrer",
        "petition",
        "hearing",
        "deposition",
        "court",
        "docket",
        "case no",
        "case no.",
    )
)


def _filenames_suggest_legal_filings(sources: Optional[List[str]]) -> bool:
    if not sources:
        return False
    for name in sources:
        low = (name or "").lower()
        if any(m in low for m in _LEGAL_FILENAME_MARKERS):
            return True
    return False


def _legal_attachment_orientation_block(names: Optional[List[str]]) -> str:
    """Reduce wrong-domain answers when exhibit OCR dominates the first pages."""
    if not names or not _filenames_suggest_legal_filings(names):
        return ""
    joined = ", ".join(names)
    return (
        "ORIENTATION (from filenames): These uploads look like litigation or court-related filings (motions, responses, exhibits, etc.). "
        "Treat the body text as part of that package. Exhibits often include scans, forms, or figures whose OCR can resemble unrelated domains—do NOT relabel the whole filing as an electronics schematic unless the user explicitly asks about circuits.\n"
        f"Filenames: {joined}\n\n"
    )


_CODE_LIKE_EXTENSIONS = (
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".asm",
    ".s",
)


def _sources_look_like_source_code_files(sources: Optional[List[str]]) -> bool:
    if not sources:
        return False
    for n in sources:
        low = (n or "").lower()
        if any(low.endswith(ext) for ext in _CODE_LIKE_EXTENSIONS):
            return True
    return False


def _window_attachment_text_for_llm(s: str, cap: int) -> str:
    """When over cap, send head+mid+tail so opening exhibit OCR is not the only signal."""
    if not s or len(s) <= cap:
        return s
    sep = "\n\n[... long attachment omitted; middle section ...]\n\n"
    sep2 = "\n\n[... long attachment omitted ...]\n\n"
    overhead = len(sep) + len(sep2)
    inner = max(900, cap - overhead)
    third = inner // 3
    if third < 150:
        return s[:cap]
    head = s[:third]
    mid_start = max(0, len(s) // 2 - third // 2)
    mid = s[mid_start : mid_start + third]
    tail = s[-third:]
    out = head + sep + mid + sep2 + tail
    if len(out) > cap:
        drop = len(out) - cap + 8
        shrink = min(drop // 3, third - 120)
        if shrink > 0:
            third2 = third - shrink
            head = s[:third2]
            mid = s[mid_start : mid_start + third2]
            tail = s[-third2:]
            out = head + sep + mid + sep2 + tail
    if len(out) > cap:
        out = out[:cap]
    return out


def _attachment_head_misleading_non_prose(text: str, sample: int = 24000) -> bool:
    """
    Heuristic: OCR / PDF-artifact blobs often look like random identifiers; models call that 'code'.
    """
    s = (text or "")[:sample]
    if len(s) < 1200:
        return False
    low = s.lower()
    legal_cues = (
        " court",
        "plaintiff",
        "defendant",
        " motion",
        "exhibit",
        " vs.",
        " v.",
        "case no",
        "hereby",
        "whereas",
        "paragraph",
        "petitioner",
        "respondent",
        "summary judgment",
        "signature",
        "subscribed",
        "sworn",
    )
    legal_hits = sum(low.count(c) for c in legal_cues)
    if legal_hits >= 5:
        return False
    glue = (" the ", " and ", " that ", " for ", " with ", " you ", " not ", " this ", " are ")
    glue_hits = sum(low.count(g) for g in glue)
    if legal_hits >= 2 and glue_hits >= 30:
        return False
    if glue_hits >= 60:
        return False
    letters = sum(1 for c in s if c.isalpha())
    if letters < 400:
        return False
    alpha_ratio = letters / max(1, len(s))
    if alpha_ratio < 0.38:
        return True
    tokens = re.findall(r"[A-Za-z]{4,}", s)
    if len(tokens) < 40:
        return False

    def _gibber_tok(tok: str) -> bool:
        t = tok.upper()
        vow = sum(1 for c in t if c in "AEIOUY")
        if len(t) >= 4 and vow == 0:
            return True
        if len(t) >= 5 and vow <= 1 and re.match(r"^[A-Z0-9]{4,}[A-Z0-9]*$", t):
            return True
        return False

    gib = sum(1 for t in tokens if _gibber_tok(t))
    ratio = gib / len(tokens)
    if ratio > 0.22:
        return True
    if glue_hits < 12 and ratio > 0.12:
        return True
    return False


def _ocr_attachment_guard_instruction(text: str, doc_sources: Optional[List[str]]) -> str:
    if not (text or "").strip():
        return ""
    if _sources_look_like_source_code_files(doc_sources):
        return ""
    if _filenames_suggest_legal_filings(doc_sources) or _attachment_head_misleading_non_prose(text):
        return (
            "QUALITY NOTE FOR THIS EXTRACTION: The text may come from a scan or PDF and can include OCR noise, "
            "font-encoding glitches, or non-text stream artifacts. It is almost certainly NOT a programming language. "
            "Unless every line unmistakably looks like real source code for one language (e.g. consistent Python/Java "
            "syntax with imports), do NOT describe it as code with functions, recursion, or control flow. Summarize as "
            "ordinary document text when possible: headings, parties, procedural labels, dates, relief requested, and "
            "readable sentences. If long stretches are nonsensical tokens, say that plainly and report only what is readable.\n\n"
        )
    return ""


# ---- Minimal chat (rebuild): one path, easy to extend ----
@router.post("/simple", response_model=ChatResponse)
async def chat_simple(
    request: ChatRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Minimal chat: RAG → prompt → Ollama → save → return. Use this for a reliable baseline."""
    from server.utils.logger import setup_logger
    from server.config import settings
    logger = setup_logger("chat")
    logger.info(f"[Chat/simple] user {current_user.id}: {request.message[:80]}...")
    t0 = time.time()

    conversation_id = request.conversation_id or f"conv_{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    warnings: List[str] = []

    try:
        attachment_raw = (getattr(request, "attachment_extracted_text", None) or "").strip()
        _attach_llm_cap = 48_000  # keep within typical local LLM context (avoid empty/no-op generations)
        attachment_truncated_for_llm = False
        attachment_extracted_text = attachment_raw
        if len(attachment_extracted_text) > _attach_llm_cap:
            attachment_extracted_text = _window_attachment_text_for_llm(
                attachment_extracted_text, _attach_llm_cap
            )
            attachment_truncated_for_llm = True
        has_inline_text = bool(attachment_raw)
        if attachment_truncated_for_llm:
            warnings.append(
                "Long attachment: the AI received a head/middle/tail sample of the text (not only the opening pages), "
                "due to context limits. Ask about a specific section if something is missing."
            )
        has_doc_sources = bool(request.doc_sources)
        has_attachment_turn = has_doc_sources or has_inline_text
        intent_mode = guardrails_service.detect_query_intent(request.message)
        if intent_mode == "general":
            q_lower = request.message.lower()
            if ("virginia" in q_lower or " va " in f" {q_lower} ") and any(
                t in q_lower
                for t in (
                    "law", "legislat", "statute", "code", "effective", "july",
                    "session", "bill", "assembly", "policy", "enact", "change",
                )
            ):
                intent_mode = "legal"
        # Attachments (filenames and/or inline extracted text): always retrieve / inject context
        corpus_busy = _corpus_update_in_progress()
        if corpus_busy:
            warnings.append(
                "Virginia Code index is rebuilding in the background. Statute search may be slow or "
                "unavailable; answers may rely on attachments and general knowledge until indexing completes."
            )
        effective_use_rag = bool(
            request.use_rag
            and (intent_mode in ("legal", "mixed") or has_attachment_turn)
        )
        if corpus_busy and request.use_rag:
            warnings.append(
                "Virginia Code index may be rebuilding; search results could be partial until UPDATE_VA_LAWS.bat completes."
            )

        effective_fmt = _effective_response_format(request, intent_mode)
        session_law_query = guardrails_service.is_session_law_query(request.message)
        effective_year = guardrails_service.parse_effective_year(request.message)

        enhanced_for_cache = guardrails_service.enhance_prompt(request.message)
        want_live = _want_live_lookup(request)
        scope_simple = semantic_cache_service.scope_fingerprint(
            effective_use_rag,
            False,
            "standard",
            request.max_results,
            request.doc_sources,
            False,
            effective_fmt,
            extra=f"web:{want_live}:{datetime.now().date().isoformat()}",
        )
        prior_count = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == current_user.id)
            .filter(ChatMessage.conversation_id == conversation_id)
            .count()
        )
        is_first_simple = prior_count == 0
        query_embedding_simple: Optional[List[float]] = None
        # Never use semantic cache for attachment turns: cache has no document text and will
        # return generic "can't access files" answers for similar questions.
        if (
            settings.SEMANTIC_CACHE_ENABLED
            and is_first_simple
            and effective_use_rag
            and not has_attachment_turn
        ):
            try:
                query_embedding_simple = await ollama_service.embed(enhanced_for_cache[:8000])
                simple_hit = semantic_cache_service.find_best_match(
                    db, current_user.id, query_embedding_simple, scope_simple, settings.OLLAMA_MODEL
                )
                if simple_hit:
                    response_cached, formatted_cached, full_cached, warn_cached, extra = semantic_cache_service.deserialize_cached_response(
                        simple_hit.row
                    )
                    if not guardrails_service.looks_like_generic_disclaimer(response_cached or ""):
                        semantic_cache_service.record_hit(db, simple_hit.row.id)
                        warnings = list(warn_cached or [])
                        chat_message = ChatMessage(
                            user_id=current_user.id,
                            conversation_id=conversation_id,
                            subject=None,
                            message=request.message,
                            response=response_cached,
                            sources=json.dumps(formatted_cached),
                            full_sources=json.dumps(full_cached),
                            warnings=json.dumps(warnings),
                        )
                        db.add(chat_message)
                        db.commit()
                        db.refresh(chat_message)
                        return ChatResponse(
                            response=response_cached,
                            sources=formatted_cached,
                            conversation_id=conversation_id,
                            timestamp=datetime.now().isoformat(),
                            warnings=warnings,
                            message_id=chat_message.id,
                            semantic_cache_hit=True,
                            response_format=(extra or {}).get("response_format") or effective_fmt,
                        )
                    logger.warning("[Chat/simple] semantic cache hit rejected (generic disclaimer)")
            except Exception as ex:
                logger.warning(f"[Chat/simple] semantic cache lookup failed: {ex}")

        sources_raw: List[Dict] = []
        upload_had_chunks = has_inline_text
        if effective_use_rag:
            seen_ids: set = set()
            enhanced_q = guardrails_service.enhance_prompt(request.message)
            if has_doc_sources and not has_inline_text:
                try:
                    upload_chunks = rag_service.get_chunks_for_sources(request.doc_sources, limit=80)
                    if upload_chunks:
                        upload_had_chunks = True
                    for s in upload_chunks:
                        sid = s.get("id")
                        if sid not in seen_ids:
                            seen_ids.add(sid)
                            sources_raw.append(s)
                    if not upload_chunks:
                        warnings.append(
                            "No indexed text was found for the attached filename(s). "
                            "The upload may have failed, the PDF may be empty or image-only without OCR, or text extraction failed."
                        )
                        doc_hits = await rag_service.search(
                            enhanced_q,
                            n_results=30,
                            filters={"source": {"$in": request.doc_sources}},
                            use_synonyms=False,
                        )
                        if doc_hits:
                            upload_had_chunks = True
                        for s in doc_hits:
                            sid = s.get("id")
                            if sid not in seen_ids:
                                seen_ids.add(sid)
                                sources_raw.append(s)
                        if not doc_hits:
                            logger.info(
                                "[Chat/simple] No chunks or vector hits for doc_sources=%s",
                                request.doc_sources,
                            )
                except Exception as e:
                    logger.warning(f"[Chat/simple] Uploaded-document retrieval failed: {e}")

            # Do not mix Virginia statutes into context when the user attached a file but we
            # recovered nothing—it misleads small models into saying they "can't access files".
            # Inline attachment text is already large; blending many statutes blows the LLM window
            # and can hide the user's question behind irrelevant context.
            blend_statutes = (not has_attachment_turn) or (
                has_attachment_turn
                and upload_had_chunks
                and intent_mode in ("legal", "mixed")
                and not has_inline_text
            )
            if blend_statutes:
                try:
                    rag_n = int(getattr(settings, "CHAT_SIMPLE_N_RESULTS", 8) or 8)
                    if session_law_query:
                        rag_n = max(rag_n, 15)
                    rag_start = time.time()
                    if session_law_query:
                        extra = await rag_service.search_legislative_effective_date(
                            request.message, year=effective_year, n_results=rag_n
                        )
                    else:
                        extra = await rag_service.search_fast(
                            request.message, n_results=rag_n, use_synonyms=True
                        )
                    logger.info(
                        f"[Chat/simple] RAG: {len(extra)} hits in {time.time() - rag_start:.2f}s "
                        f"(session_law={session_law_query})"
                    )
                    for s in extra:
                        sid = s.get("id")
                        if sid not in seen_ids:
                            seen_ids.add(sid)
                            sources_raw.append(s)
                except Exception as e:
                    logger.warning(f"RAG failed: {e}")
        live_added = 0
        if want_live and intent_mode in ("legal", "mixed") and not has_inline_text:
            live_added = await _merge_live_official_sources(request.message, sources_raw, warnings)
        context_str = ""
        snippet_len = int(getattr(settings, "CHAT_SIMPLE_SOURCE_SNIPPET_CHARS", 700) or 700)
        max_ctx_sources = int(getattr(settings, "CHAT_SIMPLE_MAX_CONTEXT_SOURCES", 12) or 12)
        if has_attachment_turn:
            max_ctx_sources = min(max_ctx_sources + 4, 16)
        if has_inline_text:
            context_str = (
                _legal_attachment_orientation_block(request.doc_sources)
                + _ocr_attachment_guard_instruction(attachment_raw, request.doc_sources)
                + "EXTRACTED TEXT FROM THE USER'S ATTACHED FILE(S) — this IS the document content; "
                "answer using this material:\n\n"
                + attachment_extracted_text
            )
            if sources_raw:
                parts_sup = []
                parts_sup.append(
                    "IMPORTANT: Additional numbered excerpts below may include statutes or cases; "
                    "for questions about the user's file, rely primarily on the attachment text above."
                )
                for i, s in enumerate(sources_raw[:max_ctx_sources], 1):
                    meta = s.get("metadata") or {}
                    parts_sup.append(
                        f"[{i}] {meta.get('source', 'Unknown')} ({meta.get('jurisdiction', '')}) {meta.get('citation', '')}\n{(s.get('text') or '')[:snippet_len]}"
                    )
                context_str += "\n\n--- Additional retrieval ---\n\n" + "\n\n".join(parts_sup)
        elif sources_raw:
            parts = []
            _ob = _legal_attachment_orientation_block(request.doc_sources)
            if _ob.strip():
                parts.append(_ob.rstrip())
            if has_attachment_turn and upload_had_chunks:
                parts.append(
                    "IMPORTANT: The numbered excerpts below ARE text extracted from the user's attached file(s) "
                    f"({', '.join(request.doc_sources or [])}). Describe and analyze THAT content. "
                    "Do not say you cannot access uploads or lack file-sharing."
                )
            for i, s in enumerate(sources_raw[:max_ctx_sources], 1):
                meta = s.get("metadata") or {}
                parts.append(f"[{i}] {meta.get('source', 'Unknown')} ({meta.get('jurisdiction', '')}) {meta.get('citation', '')}\n{(s.get('text') or '')[:snippet_len]}")
            context_str = "\n\n".join(parts)
        else:
            context_str = "No relevant documents found."

        if intent_mode in ("legal", "mixed"):
            system_prompt = guardrails_service.build_system_prompt(
                is_first_message=True,
                has_conversation_history=False,
                user_name=current_user.full_name,
                response_format=effective_fmt,
            )
            system_prompt += "\n\nUse ONLY the source excerpts above. Cite them. If none are relevant, say so."
            if live_added:
                system_prompt += (
                    "\n\nSome excerpts are LIVE OFFICIAL FETCHES from law.lis.virginia.gov "
                    "(or another allowlisted government site). Prefer those over older local-index text "
                    "when they conflict. Label live fetches as such. This is not open-web browsing."
                )
            system_prompt += guardrails_service.anti_generic_disclaimer_rules()
            if session_law_query and sources_raw:
                system_prompt += (
                    "\n\nThe user asks about NEW or SESSION laws by effective date. "
                    "List ONLY authorities in the excerpts that mention the effective date "
                    f"or enactment year requested ({effective_year or 'see question'}). "
                    "Do NOT claim there are no new laws statewide if excerpts are silent—"
                    "say what the indexed sources contain and what is missing."
                )
            if not sources_raw and not has_inline_text:
                system_prompt += (
                    "\n\nThe source index returned NO excerpts for this question. "
                    "You MUST start your reply with **No controlling authority found** and must NOT "
                    "claim that no laws exist statewide or cite your training knowledge."
                )
            if has_attachment_turn:
                system_prompt += (
                    "\n\nThe user attached file(s) in this request. If Relevant Context includes excerpts from those filenames, use them—do not claim you cannot view attachments. "
                    "Weave uploads into your analysis where relevant. "
                    "End with a clearly labeled section **Practical next steps** (numbered) grounded in the excerpts and authorities you cited."
                )
                if _filenames_suggest_legal_filings(request.doc_sources):
                    system_prompt += (
                        "\n\nWhen filenames refer to motions, nonsuit, dismissal, or exhibits, assume a litigation context. "
                        "Do not reclassify the filing as unrelated engineering work based on noisy exhibit OCR alone."
                    )
                if (
                    not _sources_look_like_source_code_files(request.doc_sources)
                    and _attachment_head_misleading_non_prose(attachment_raw)
                ):
                    system_prompt += (
                        "\n\nThe attachment excerpt may be dominated by OCR noise. Do not invent a programming-language "
                        "reading (functions, recursion, comments). Describe readable prose only; acknowledge unreadable spans."
                    )
        elif has_attachment_turn and effective_use_rag:
            system_prompt = guardrails_service.build_general_system_prompt(user_name=current_user.full_name)
            system_prompt += (
                "\n\nThe user uploaded document(s); excerpts above come from extraction (including OCR for scans when available). "
                "If numbered excerpts from their file(s) appear under Relevant Context, you MUST use them—do not claim you cannot view attachments. "
                "Respond with: (1) **Summary** — what the document(s) appear to be and key facts, parties, dates, or deadlines visible in the excerpts; "
                "(2) **Practical next steps** — numbered process-oriented actions appropriate to this content (filings, responses, records to gather, professionals to involve); "
                "(3) **Gaps / verify** — what is missing from the excerpts or unclear (including possible OCR errors). "
                "Ground statements in the excerpts; do not invent content. This is informational preparation only—not legal advice."
            )
            if _filenames_suggest_legal_filings(request.doc_sources):
                system_prompt += (
                    "\n\nWhen filenames refer to motions, nonsuit, dismissal, or exhibits, assume a litigation context. "
                    "Do not reclassify the filing as unrelated engineering work based on noisy exhibit OCR alone."
                )
            if (
                not _sources_look_like_source_code_files(request.doc_sources)
                and _attachment_head_misleading_non_prose(attachment_raw)
            ):
                system_prompt += (
                    "\n\nThe attachment excerpt may be dominated by OCR noise. Do not invent a programming-language "
                    "reading (functions, recursion, comments). Describe readable prose only; acknowledge unreadable spans."
                )
        else:
            system_prompt = guardrails_service.build_general_system_prompt(user_name=current_user.full_name)

        gen_max = request.max_output_tokens
        if gen_max is None:
            default_out = int(getattr(settings, "CHAT_SIMPLE_MAX_OUTPUT_TOKENS", 768) or 768)
            if has_attachment_turn and effective_use_rag:
                gen_max = min(default_out * 2, 1536)
            elif intent_mode in ("legal", "mixed") and effective_fmt == "research_memo":
                gen_max = min(default_out * 2, 1024)
            else:
                gen_max = default_out

        skip_llm = bool(has_attachment_turn and effective_use_rag and not upload_had_chunks)
        legal_no_sources = (
            intent_mode in ("legal", "mixed")
            and not sources_raw
            and not has_inline_text
            and effective_use_rag
        )
        session_law_no_relevant = (
            session_law_query
            and effective_use_rag
            and not has_inline_text
            and not sources_raw
        )
        if skip_llm:
            response_text = (
                "No extracted text was found in the index for your attachment(s), so the assistant had nothing to read. "
                "Typical causes: the upload failed (check for an error right after Send), the file has no selectable text "
                "(image-only PDF without OCR), or the backend could not index it. "
                "Try the Upload Document screen to confirm success, or export/save the PDF as text-searchable, then attach again."
            )
        elif session_law_no_relevant:
            response_text = guardrails_service.legal_session_law_message(
                request.message,
                year=effective_year,
                corpus_busy=corpus_busy,
            )
            warnings.append(
                "No indexed session-law sources matched this effective-date question."
            )
        elif legal_no_sources:
            response_text = guardrails_service.legal_empty_sources_message(
                request.message, corpus_busy=corpus_busy
            )
            warnings.append(
                "No Virginia sources were retrieved; returned AI Laws-compliant notice."
            )
        else:
            llm_start = time.time()
            response_text = await ollama_service.generate(
                prompt=request.message,
                context=context_str,
                system_prompt=system_prompt,
                max_tokens=gen_max,
                user_message_before_context=has_inline_text,
            )
            logger.info(f"[Chat/simple] LLM generate: {time.time() - llm_start:.2f}s (max_tokens={gen_max})")
            if not response_text or not response_text.strip():
                response_text = "I couldn't generate a response. Please try again."
            elif (
                intent_mode in ("legal", "mixed")
                and guardrails_service.looks_like_generic_disclaimer(response_text)
            ):
                logger.warning("[Chat/simple] Replacing generic model disclaimer with AI Laws notice")
                warnings.append("A generic chatbot-style disclaimer was suppressed.")
                response_text = guardrails_service.legal_session_law_message(
                    request.message, year=effective_year, corpus_busy=corpus_busy
                )

        logger.info(f"[Chat/simple] total request: {time.time() - t0:.2f}s")

        formatted_sources = [
            {
                "source": (s.get("metadata") or {}).get("source", "Unknown"),
                "jurisdiction": (s.get("metadata") or {}).get("jurisdiction", ""),
                "citation": (s.get("metadata") or {}).get("citation"),
                "url": (s.get("metadata") or {}).get("origin_url"),
                "link": (s.get("metadata") or {}).get("origin_url"),
                "live_fetch": bool((s.get("metadata") or {}).get("live_fetch")),
                "snippet": ((s.get("text") or "")[:400] + ("..." if len(s.get("text") or "") > 400 else "")),
            }
            for s in sources_raw[:20]
        ]

        chat_message = ChatMessage(
            user_id=current_user.id,
            conversation_id=conversation_id,
            subject=None,
            message=request.message,
            response=response_text,
            sources=json.dumps(formatted_sources),
            full_sources=json.dumps(sources_raw[:20]),
            warnings=json.dumps(warnings),
        )
        db.add(chat_message)
        db.commit()
        db.refresh(chat_message)

        if (
            settings.SEMANTIC_CACHE_ENABLED
            and is_first_simple
            and query_embedding_simple
            and not has_attachment_turn
            and response_text
            and not response_text.strip().startswith("No controlling authority")
        ):
            try:
                semantic_cache_service.store(
                    db,
                    user_id=current_user.id,
                    scope_fp=scope_simple,
                    ollama_model=settings.OLLAMA_MODEL,
                    query_preview=enhanced_for_cache,
                    query_embedding=query_embedding_simple,
                    response_text=response_text,
                    sources_display=formatted_sources,
                    full_sources=sources_raw[:20],
                    warnings=warnings,
                    extra={
                        "detail_level": "standard",
                        "recommended_level": None,
                        "total_sources": len(sources_raw[:20]),
                        "unique_sources": len(formatted_sources),
                        "response_format": effective_fmt,
                    },
                )
            except Exception as ex:
                logger.warning(f"[Chat/simple] semantic cache store skipped: {ex}")

        return ChatResponse(
            response=response_text,
            sources=formatted_sources,
            conversation_id=conversation_id,
            timestamp=datetime.now().isoformat(),
            warnings=warnings,
            message_id=chat_message.id,
            semantic_cache_hit=False,
            response_format=effective_fmt,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat/simple error: {e}", exc_info=True)
        err_msg = str(e).strip()
        # Return a clear message so the frontend can show it; include hint for common Ollama issues
        if "cpu buffer" in err_msg.lower() or "loading on cpu" in err_msg.lower():
            detail = (
                "Model failed to load (CPU RAM / GPU not used). "
                "Quit Ollama from the system tray, run RESTART_EVERYTHING.bat or START_OLLAMA_GPU.bat, then START_BACKEND.bat. "
                "In .env use OLLAMA_MODEL=tinyllama:latest (smallest). Raw: "
                + (err_msg[:400] + "…" if len(err_msg) > 400 else err_msg)
            )
        elif (
            ("not running" in err_msg.lower() and "11434" in err_msg)
            or "not reachable at" in err_msg.lower()
            or "cannot connect to ollama" in err_msg.lower()
        ):
            detail = (
                "Ollama is not running (nothing answered on port 11434). "
                "Do not start only the Python backend from the IDE unless Ollama is already up. "
                "From the LAWFIRMAI folder: run RESTART_EVERYTHING.bat, or run START_OLLAMA_GPU.bat (leave it open) then START_BACKEND.bat."
            )
        elif "model" in err_msg.lower() and "not found" in err_msg.lower():
            detail = err_msg + " Run: ollama pull <name> and match OLLAMA_MODEL in .env to ollama list."
        elif "Ollama" in err_msg or "ollama" in err_msg.lower():
            detail = err_msg + " Check Ollama on http://127.0.0.1:11434/api/tags and .env OLLAMA_MODEL."
        else:
            detail = err_msg
        raise HTTPException(status_code=500, detail=detail)


@router.post("/query", response_model=ChatResponse)
async def chat_query(
    request: ChatRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Main legal research query endpoint
    
    This is the core endpoint that handles all legal research queries. It:
    1. Detects if the query is asking for a specific statute (e.g., "Domestic Assault")
    2. Performs comprehensive RAG search across multiple query variations
    3. Retrieves relevant user corrections and knowledge
    4. Optionally performs scenario analysis for case outcome prediction
    5. Generates AI response using Ollama LLM
    6. Validates response against AI Laws
    7. Stores conversation in database
    
    Args:
        request: ChatRequest containing the user's query and options
        current_user: Authenticated user (from require_auth dependency)
        db: Database session
    
    Returns:
        ChatResponse with AI-generated answer, sources, warnings, and optional scenario prediction
    """
    from server.utils.logger import setup_logger
    logger = setup_logger("chat")
    logger.info(f"[Chat] Received query from user {current_user.id}: {request.message[:100]}...")
    query_start_time = time.time()
    
    # Initialize warnings list early - used throughout the function
    warnings: List[str] = []
    
    try:
        intent_mode = guardrails_service.detect_query_intent(request.message)
        effective_fmt = _effective_response_format(request, intent_mode)

        # === STEP 1: DETECT SPECIFICITY ===
        # Check if user is asking for a specific statute type (e.g., "Domestic Assault")
        # vs a general one (e.g., "Assault"). This helps ensure we provide the exact
        # statute requested, not a parent statute.
        from server.services.rag_service import rag_service
        from server.services.smart_default_service import smart_default_service
        from server.config import settings
        specificity_info = rag_service._detect_specific_statute_request(request.message)
        
        # === STEP 1.5: SMART DEFAULT DETECTION ===
        # Analyze query complexity and recommend appropriate detail level
        recommended_level = None
        detail_level_config = None
        
        # Get conversation history for context
        conversation_history_for_detection = []
        try:
            prev_msgs = db.query(ChatMessage)\
                .filter(ChatMessage.user_id == current_user.id)\
                .order_by(ChatMessage.timestamp.desc())\
                .limit(5)\
                .all()
            conversation_history_for_detection = [
                {"message": msg.message, "response": msg.response}
                for msg in prev_msgs
            ]
        except Exception:
            pass
        
        # Determine detail level (use provided or detect)
        if request.detail_level:
            # User explicitly specified detail level
            detail_level = request.detail_level
        else:
            # Use smart default detection
            detection_result = smart_default_service.detect_detail_level(
                request.message,
                conversation_history_for_detection
            )
            detail_level = detection_result["recommended_level"]
            recommended_level = detail_level
        
        # Get configuration for the detail level
        detail_level_config = settings.DETAIL_LEVELS.get(detail_level, settings.DETAIL_LEVELS["standard"])
        max_output_tokens = request.max_output_tokens or detail_level_config["max_tokens"]
        context_chars = detail_level_config["context_chars"]
        detail_instruction = detail_level_config["instruction"]
        
        # === STEP 2: CHECK CONVERSATION HISTORY AND DETECT SUBJECT ===
        # Check if this is the first message in the conversation and if there's history
        conversation_id = request.conversation_id or f"conv_{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        is_first_message = False
        has_conversation_history = False
        conversation_subject = None
        conversation_history_list = []
        
        try:
            # Get previous messages in this conversation
            previous_messages = db.query(ChatMessage)\
                .filter(ChatMessage.user_id == current_user.id)\
                .filter(ChatMessage.conversation_id == conversation_id)\
                .order_by(ChatMessage.timestamp.asc())\
                .all()
            is_first_message = (len(previous_messages) == 0)
            
            # Build conversation history for subject detection
            if previous_messages:
                conversation_history_list = [
                    {
                        "message": msg.message,
                        "response": msg.response,
                        "subject": msg.subject
                    }
                    for msg in previous_messages
                ]
                # Get subject from first message if available
                if previous_messages[0].subject:
                    conversation_subject = previous_messages[0].subject
            
            # Check if user has any conversation history at all
            total_messages = db.query(ChatMessage)\
                .filter(ChatMessage.user_id == current_user.id)\
                .count()
            has_conversation_history = (total_messages > 0)
        except Exception:
            pass  # Default to first message if check fails
        
        # Detect or update conversation subject
        from server.services.conversation_subject_service import conversation_subject_service
        if is_first_message or not conversation_subject:
            detected_subject = conversation_subject_service.detect_subject(
                request.message,
                conversation_history_list
            )
            if detected_subject:
                conversation_subject = detected_subject
        
        # === STEP 3: BUILD SYSTEM PROMPT ===
        # The system prompt tells the LLM how to behave. It includes:
        # - AI Laws (ethical guidelines from config/ai_laws.json)
        # - Accuracy requirements (cite sources, use Bluebook format)
        # - Specificity requirements (if asking for specific statute)
        # - Relationship building instructions
        system_prompt = guardrails_service.build_system_prompt(
            is_first_message=is_first_message,
            has_conversation_history=has_conversation_history,
            user_name=current_user.full_name,
            response_format=effective_fmt,
        )
        
        # Add extra specificity requirements if this is a specific statute request
        # This prevents the AI from generalizing (e.g., giving "Assault" when asked for "Domestic Assault")
        if specificity_info["is_specific_request"]:
            specific_terms_str = ", ".join(specificity_info["specific_terms"])
            system_prompt += f"\n\nCRITICAL SPECIFICITY REQUIREMENT:\n"
            system_prompt += f"- The user asked for a SPECIFIC statute type: {specific_terms_str}\n"
            system_prompt += f"- You MUST provide the SPECIFIC statute (e.g., 'Domestic Assault and Battery'), NOT the general parent statute (e.g., 'Assault and Battery')\n"
            system_prompt += f"- If you cannot find the specific statute requested, explicitly state: 'The specific statute requested ({specific_terms_str}) was not found. Found general statute instead: [citation]'\n"
            system_prompt += f"- Do NOT generalize or 'wrap' specific requests into parent statutes\n"
            system_prompt += f"- Cite the EXACT code section for the specific statute type requested\n"
        
        # Detail level and exhaustive mode removed - let AI format naturally
        
        # === STEP 3: ENHANCE USER PROMPT ===
        # The guardrails service may enhance/modify the user's prompt to ensure
        # it follows best practices (e.g., adding context, clarifying intent)
        enhanced_prompt = guardrails_service.enhance_prompt(request.message)

        # --- Semantic response cache (similar questions skip RAG + LLM) ---
        query_embedding: Optional[List[float]] = None
        semantic_cache_hit = False
        want_live = _want_live_lookup(request)
        scope_fp = semantic_cache_service.scope_fingerprint(
            request.use_rag,
            request.exhaustive_search,
            detail_level,
            request.max_results,
            request.doc_sources,
            request.skip_clarification,
            effective_fmt,
            extra=f"web:{want_live}:{datetime.now().date().isoformat()}",
        )
        if settings.SEMANTIC_CACHE_ENABLED and is_first_message:
            try:
                query_embedding = await ollama_service.embed(enhanced_prompt[:8000])
                cache_hit = semantic_cache_service.find_best_match(
                    db, current_user.id, query_embedding, scope_fp, settings.OLLAMA_MODEL
                )
                if cache_hit:
                    semantic_cache_service.record_hit(db, cache_hit.row.id)
                    response_text, formatted_sources, full_source_data, cached_warnings, extra = semantic_cache_service.deserialize_cached_response(
                        cache_hit.row
                    )
                    warnings = list(cached_warnings or [])
                    semantic_cache_hit = True
                    verification_status = extra.get("verification_status")
                    authoritative_sources_count = extra.get("authoritative_sources_count")
                    secondary_sources_count = extra.get("secondary_sources_count")
                    conflict_messages = extra.get("conflict_messages") or []
                    search_total_results = extra.get("search_total_results")
                    search_unique_sources = extra.get("search_unique_sources")
                    scenario_prediction = None
                    clarification_only = False
                    recommended_level_cached = extra.get("recommended_level")
                    detail_level_out = extra.get("detail_level") or detail_level
                    validation = {"warnings": list(warnings)}
                    conv_id = request.conversation_id or f"conv_{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    try:
                        from server.services.conversation_subject_service import conversation_subject_service
                        conversation_subject_cached = conversation_subject_service.detect_subject(request.message, []) or None
                    except Exception:
                        conversation_subject_cached = None
                    chat_message = ChatMessage(
                        user_id=current_user.id,
                        conversation_id=conv_id,
                        subject=conversation_subject_cached,
                        message=request.message,
                        response=response_text,
                        sources=json.dumps(formatted_sources),
                        full_sources=json.dumps(full_source_data),
                        warnings=json.dumps(validation.get("warnings", [])),
                    )
                    db.add(chat_message)
                    db.commit()
                    db.refresh(chat_message)
                    try:
                        from server.models import AuditLog
                        db.add(
                            AuditLog(
                                user_id=current_user.id,
                                action="chat_query",
                                path="/api/chat/query",
                                method="POST",
                                status=200,
                                details=json.dumps({"conversation_id": conv_id, "semantic_cache_hit": True})[:1000],
                            )
                        )
                        db.commit()
                    except Exception:
                        db.rollback()
                    return ChatResponse(
                        response=response_text,
                        sources=formatted_sources,
                        conversation_id=conv_id,
                        timestamp=datetime.now().isoformat(),
                        warnings=warnings,
                        message_id=chat_message.id,
                        scenario_prediction=None,
                        detail_level=detail_level_out,
                        recommended_level=recommended_level_cached if recommended_level_cached is not None else recommended_level,
                        is_streaming=False,
                        total_sources=extra.get("total_sources"),
                        unique_sources=extra.get("unique_sources"),
                        verification_status=verification_status,
                        authoritative_sources_count=authoritative_sources_count,
                        secondary_sources_count=secondary_sources_count,
                        conflict_messages=conflict_messages or None,
                        search_total_results=search_total_results,
                        search_unique_sources=search_unique_sources,
                        clarification_only=False,
                        clarification_questions=None,
                        semantic_cache_hit=True,
                        response_format=(extra or {}).get("response_format") or effective_fmt,
                    )
            except Exception as cache_ex:
                logger.warning(f"Semantic cache lookup failed (continuing with full pipeline): {cache_ex}")
        
        # === STEP 4: RETRIEVE RAG CONTEXT ===
        # If RAG is enabled, search the vector database for relevant legal documents
        # This uses semantic search to find documents similar to the query
        
        # CRITICAL: Query SCOTUS separately as a distinct authoritative database
        # SCOTUS is #1 in hierarchy. If this fails (no data, timeout), chat continues without SCOTUS.
        scotus_sources = []
        if request.use_rag:
            try:
                logger.info("[Chat] Querying SCOTUS database separately...")
                scotus_start = time.time()
                query_lower = enhanced_prompt.lower()
                case_name_matches = []
                landmark_case_names = ['heller', 'bruen', 'mcdonald', 'miller', 'miranda']
                for case_name in landmark_case_names:
                    if case_name in query_lower:
                        case_results = await scotus_service.search_scotus_by_case_name(case_name)
                        case_name_matches.extend(case_results[:2])
                scotus_sources = await scotus_service.search_scotus(enhanced_prompt, n_results=5)
                if case_name_matches:
                    seen_ids = {r['id'] for r in scotus_sources}
                    for case_match in case_name_matches:
                        if case_match['id'] not in seen_ids:
                            scotus_sources.insert(0, case_match)
                            seen_ids.add(case_match['id'])
                scotus_elapsed = time.time() - scotus_start
                logger.info(f"[Chat] SCOTUS search completed in {scotus_elapsed:.2f}s, found {len(scotus_sources)} cases")
            except Exception as e:
                logger.warning(f"[Chat] SCOTUS search failed (non-fatal): {e}")
                scotus_sources = []
        
        context = None
        sources = []
        # warnings already initialized at function start
        verification_status = None
        authoritative_sources_count = None
        secondary_sources_count = None
        conflict_messages: List[str] = []
        search_total_results = None
        search_unique_sources = None
        if request.use_rag:
            # Enhanced search with case law context for better statute understanding
            # This combines statute search with case precedents to better decipher user questions
            if request.exhaustive_search:
                # Use comprehensive search for trial prep mode
                n_results = 200
                search_result = await rag_service.search_comprehensive(
                    enhanced_prompt,
                    n_results_per_query=n_results,
                    require_multiple_sources=True,
                    min_authoritative_sources=2,
                    exhaustive=request.exhaustive_search
                )
                sources = search_result['results']
                case_contexts = []  # Comprehensive search doesn't include case context
            else:
                # Use enhanced case-aware search for standard queries
                # Reduced from 50 to 25 for faster responses
                n_results = 25
                logger.info(f"[Chat] Starting RAG search with case context (n_results={n_results})...")
                search_start = time.time()
                enhanced_search = await rag_service.search_with_case_context(
                    enhanced_prompt,
                    n_results=n_results,
                    use_synonyms=True
                )
                search_elapsed = time.time() - search_start
                logger.info(f"[Chat] RAG search completed in {search_elapsed:.2f}s")
                sources = enhanced_search['statute_results']
                case_contexts = enhanced_search.get('case_contexts', [])
                related_statutes = enhanced_search.get('related_statutes', {})
                search_result = enhanced_search  # For backward compatibility

            # Use ALL results, not limited by max_results
            # If user wants to limit, they can specify, but default is to return all relevant cases
            max_sources = request.max_results if request.max_results > 0 else len(sources)
            sources = sources[:max_sources]  # Use all results unless explicitly limited
            
            # CRITICAL: Combine SCOTUS + State results with proper hierarchy
            # SCOTUS goes FIRST (highest authority per AI Laws)
            # Then state/Virginia law
            all_sources = []
            
            # Add SCOTUS sources first (highest priority)
            if scotus_sources:
                for scotus_source in scotus_sources:
                    # Mark as SCOTUS for proper citation
                    scotus_source['metadata']['is_scotus'] = True
                    scotus_source['metadata']['authority_level'] = 'SCOTUS - Binding on all jurisdictions'
                    
                    # Ensure citation is in Bluebook format
                    citation = scotus_source['metadata'].get('citation', '')
                    if citation:
                        citation = _format_bluebook_citation(citation)
                        scotus_source['metadata']['citation'] = citation
                    else:
                        # Try to extract citation from text if missing
                        text = scotus_source.get('text', '')
                        if text:
                            # Use RAG service's SCOTUS citation extractor
                            from server.services.rag_service import rag_service
                            extracted = rag_service._extract_scotus_citation_from_text(text)
                            if extracted:
                                citation = extracted
                                scotus_source['metadata']['citation'] = citation
                    
                    all_sources.append(scotus_source)
                    case_name = scotus_source['metadata'].get('case_name', 'Unknown')
                    logger.info(f"[Chat] Added SCOTUS case: {case_name} ({citation or 'No citation'})")
            
            # Add state/Virginia sources after SCOTUS
            for state_source in sources:
                # Only add if not already in SCOTUS results (avoid duplicates)
                if state_source.get('id') not in [s.get('id') for s in scotus_sources]:
                    all_sources.append(state_source)
            
            sources = all_sources  # Replace with combined, properly ordered sources
            if want_live:
                await _merge_live_official_sources(request.message, sources, warnings)

            # Capture verification summary for UI (from search_result)
            verification_status = search_result.get("verification_status", "unverified")
            authoritative_sources_count = len(search_result.get("authoritative_sources", []) or [])
            secondary_sources_count = len(search_result.get("secondary_sources", []) or [])
            conflict_messages = [
                c.get("message", "")
                for c in search_result.get("conflicts", [])
                if c.get("message")
            ]
            search_total_results = search_result.get("total_results", len(sources))
            search_unique_sources = search_result.get("unique_sources", len(set([s.get('metadata', {}).get('source', 'Unknown') for s in sources])))

            # Add case law context to enhance AI understanding
            case_context_available = len(case_contexts) > 0
            
            # Build enhanced context with verification info
            context_parts = []
            
            # Add verification status
            if search_result['verification_status'] == 'verified':
                context_parts.append(
                    f"[VERIFIED: Found {len(search_result['authoritative_sources'])} authoritative source(s) "
                    f"across {search_result['unique_sources']} unique sources]"
                )
            else:
                context_parts.append(
                    f"[WARNING: Only found {len(search_result['authoritative_sources'])} authoritative source(s). "
                    f"Cross-reference required. Found {search_result['total_results']} total results across "
                    f"{len(search_result['query_variations'])} query variations.]"
                )
            
            # Add conflict warnings
            for conflict in search_result['conflicts']:
                if conflict['severity'] == 'warning':
                    context_parts.append(f"[WARNING: {conflict['message']}]")
            
            # Source information (no formatting instructions)
            
            # Add actual results with specificity highlighting
            if sources:
                # Helper function to format source text with truncation
                def format_source_text(text: str) -> str:
                    """Format source text with optional truncation based on detail level"""
                    if context_chars is None:
                        # No truncation for comprehensive+ modes
                        return text
                    elif len(text) > context_chars:
                        return text[:context_chars] + "..."
                    else:
                        return text
                
                # Check if we have specific matches for specific requests
                if specificity_info["is_specific_request"]:
                    specific_sources = []
                    general_sources = []
                    
                    for source in sources:
                        source_text = source.get('text', '').lower()
                        source_meta = str(source.get('metadata', {})).lower()
                        combined = f"{source_text} {source_meta}"
                        
                        # Check if source contains specific terms
                        has_specific = any(term in combined for term in specificity_info["specific_terms"])
                        
                        if has_specific:
                            specific_sources.append(source)
                        else:
                            general_sources.append(source)
                    
                    # Add specific sources first with highlighting
                    for i, source in enumerate(specific_sources, 1):
                        source_name = source['metadata'].get('source', 'Unknown')
                        jurisdiction = source['metadata'].get('jurisdiction', 'Unknown')
                        priority = rag_service._get_source_priority(source_name)
                        priority_label = "AUTHORITATIVE" if priority <= 2 else "SECONDARY"
                        
                        # Format citation in Bluebook format for SCOTUS
                        citation = source['metadata'].get('citation', '')
                        if citation and 'SCOTUS' in source_name.upper():
                            # Ensure Bluebook format: [Volume] U.S. [Page]
                            citation = _format_bluebook_citation(citation)
                        
                        citation_text = f" | Citation: {citation}" if citation else ""
                        context_parts.append(
                            f"\n[{i}] [SPECIFIC MATCH] [{priority_label}] Source: {source_name} ({jurisdiction}){citation_text}\n"
                            f"{format_source_text(source['text'])}"
                        )
                    
                    # Add general sources with warning
                    offset = len(specific_sources)
                    for i, source in enumerate(general_sources, offset + 1):
                        source_name = source['metadata'].get('source', 'Unknown')
                        jurisdiction = source['metadata'].get('jurisdiction', 'Unknown')
                        priority = rag_service._get_source_priority(source_name)
                        priority_label = "AUTHORITATIVE" if priority <= 2 else "SECONDARY"
                        
                        # Format citation in Bluebook format for SCOTUS
                        citation = source['metadata'].get('citation', '')
                        if citation and 'SCOTUS' in source_name.upper():
                            citation = _format_bluebook_citation(citation)
                        
                        citation_text = f" | Citation: {citation}" if citation else ""
                        context_parts.append(
                            f"\n[{i}] [GENERAL - NOT SPECIFIC] [{priority_label}] Source: {source_name} ({jurisdiction}){citation_text}\n"
                            f"{format_source_text(source['text'])}"
                        )
                    
                    # Add note if we found specific matches
                    if specific_sources:
                        context_parts.append(
                            f"\n[NOTE: Found {len(specific_sources)} source(s) matching the SPECIFIC statute type requested. "
                            f"Use these sources, NOT the general sources above.]")
                else:
                    # Standard display for non-specific requests
                    for i, source in enumerate(sources, 1):
                        source_name = source['metadata'].get('source', 'Unknown')
                        jurisdiction = source['metadata'].get('jurisdiction', 'Unknown')
                        priority = rag_service._get_source_priority(source_name)
                        priority_label = "AUTHORITATIVE" if priority <= 2 else "SECONDARY"
                        
                        # Format citation in Bluebook format for SCOTUS
                        citation = source['metadata'].get('citation', '')
                        if citation and ('SCOTUS' in source_name.upper() or jurisdiction == 'Federal'):
                            citation = _format_bluebook_citation(citation)
                        
                        citation_text = f" | Citation: {citation}" if citation else ""
                        context_parts.append(
                            f"\n[{i}] [{priority_label}] Source: {source_name} ({jurisdiction}){citation_text}\n"
                            f"{format_source_text(source['text'])}"
                        )
            else:
                context_parts.append("No relevant legal authority found.")
            
            # CRITICAL: Add explicit list of available statutes and regulations to prevent hallucination
            available_statutes = set()
            available_regulations = set()  # VAC citations
            available_cases = []
            for source in sources:
                # Extract citations from source text
                text = source.get('text', '')
                # Find all Virginia Code citations
                va_citations = re.findall(r'§\s*(\d+\.\d+-\d+(?:\.\d+)?)', text)
                available_statutes.update(va_citations)
                # Find Virginia Administrative Code (VAC) citations - e.g., 18 VAC 120-10-10
                vac_citations = re.findall(r'(\d+)\s*VAC\s*(\d+)[-.](\d+)(?:[-.](\d+))?', text, re.IGNORECASE)
                for vac in vac_citations:
                    if len(vac) == 4 and vac[3]:
                        available_regulations.add(f"{vac[0]} VAC {vac[1]}-{vac[2]}-{vac[3]}")
                    else:
                        available_regulations.add(f"{vac[0]} VAC {vac[1]}-{vac[2]}")
                # Also check metadata
                meta_cit = source.get('metadata', {}).get('citation', '')
                if meta_cit:
                    cit_match = re.search(r'(\d+\.\d+-\d+(?:\.\d+)?)', str(meta_cit))
                    if cit_match:
                        available_statutes.add(cit_match.group(1))
                    # Check for VAC in metadata
                    vac_meta = re.search(r'(\d+)\s*VAC\s*(\d+)[-.](\d+)(?:[-.](\d+))?', str(meta_cit), re.IGNORECASE)
                    if vac_meta:
                        g = vac_meta.groups()
                        if len(g) == 4 and g[3]:
                            available_regulations.add(f"{g[0]} VAC {g[1]}-{g[2]}-{g[3]}")
                        else:
                            available_regulations.add(f"{g[0]} VAC {g[1]}-{g[2]}")
                # Extract case names with citations
                case_pattern = r'(Commonwealth|State)\s+v\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?[,\s]+(\d+\s+(?:Va\.|Va\.\s+App\.|U\.S\.|S\.\s+Ct\.))'
                cases = re.findall(case_pattern, text, re.IGNORECASE)
                available_cases.extend([f"{c[0]} v. {c[1]}" for c in cases if len(c) == 2])
            
            # CRITICAL: ALWAYS add explicit statute list to prevent hallucination
            # This section MUST appear even if empty to prevent the AI from making up citations
            context_parts.append("\n" + "="*80)
            context_parts.append("CRITICAL: AVAILABLE STATUTES, REGULATIONS, AND CASES IN SOURCES")
            context_parts.append("="*80)
            context_parts.append("YOU MAY ONLY CITE THE FOLLOWING STATUTES THAT APPEAR IN THE SOURCES:")
            if available_statutes:
                for stat in sorted(available_statutes):
                    context_parts.append(f"  - § {stat}")
            else:
                context_parts.append("  - NO VIRGINIA CODE SECTIONS FOUND IN SOURCES")
                context_parts.append("  - THIS MEANS YOU CANNOT CITE ANY VIRGINIA CODE SECTIONS")
            context_parts.append("")
            context_parts.append("AVAILABLE REGULATIONS (Virginia Administrative Code) IN SOURCES:")
            if available_regulations:
                for reg in sorted(available_regulations):
                    context_parts.append(f"  - {reg}")
            else:
                context_parts.append("  - NO VAC REGULATIONS FOUND IN SOURCES")
            context_parts.append("")
            context_parts.append("AVAILABLE CASE CITATIONS IN SOURCES:")
            if available_cases:
                for case in available_cases[:10]:  # Limit to 10
                    context_parts.append(f"  - {case}")
            else:
                context_parts.append("  - NO CASE CITATIONS FOUND IN SOURCES")
            context_parts.append("")
            context_parts.append("ABSOLUTE RULE: DO NOT cite any statute, regulation, or case NOT listed above.")
            context_parts.append("If the list above shows 'NO VIRGINIA CODE SECTIONS FOUND', you MUST NOT cite any Virginia Code sections.")
            context_parts.append("If the list above shows 'NO VAC REGULATIONS FOUND', you MUST NOT cite any Virginia Administrative Code sections.")
            context_parts.append("If you need to discuss self-defense and no statute is listed above, you MUST state:")
            context_parts.append("'Self-defense in Virginia is primarily a common law defense. No specific Virginia Code section was found in the available sources.'")
            context_parts.append("")
            context_parts.append("FORBIDDEN: Do NOT cite § 18.2-50, § 18.2-56, § 18.2-57, § 19.2-274, or § 19.2-307 unless they appear in the list above.")
            context_parts.append("="*80)
            
            context = "\n".join(context_parts)
            
            # Add relevant verified corrections to context
            try:
                from server.services.correction_verification_service import correction_verification_service
                relevant_corrections = await correction_verification_service.get_relevant_corrections(
                    enhanced_prompt, db, limit=3
                )
                if relevant_corrections:
                    correction_context = "\n\n[RELEVANT PAST CORRECTIONS - Use these to avoid repeating errors:]"
                    for i, corr in enumerate(relevant_corrections, 1):
                        correction_context += f"\n[{i}] Correction Type: {corr['correction_type']}"
                        if corr['corrected']:
                            correction_context += f"\n   Original (INCORRECT): {corr['original']}"
                            correction_context += f"\n   Corrected: {corr['corrected']}"
                        if corr['details']:
                            correction_context += f"\n   Details: {corr['details']}"
                        if corr['is_attorney']:
                            correction_context += "\n   [VERIFIED BY ATTORNEY]"
                    context = f"{context}\n{correction_context}"
            except Exception as e:
                from server.utils.logger import setup_logger
                logger = setup_logger("chat")
                logger.warning(f"Error loading corrections: {e}")
            
            # Add relevant user knowledge to context
            try:
                from server.services.user_knowledge_service import user_knowledge_service
                relevant_knowledge = await user_knowledge_service.get_relevant_knowledge(
                    enhanced_prompt, db, limit=3, user_id=current_user.id
                )
                if relevant_knowledge:
                    knowledge_context = "\n\n[USER KNOWLEDGE & EXPERTISE - Incorporate this firm knowledge:]"
                    for i, know in enumerate(relevant_knowledge, 1):
                        knowledge_context += f"\n[{i}] {know['title']}"
                        knowledge_context += f"\n   Type: {know['knowledge_type']}"
                        if know['topic']:
                            knowledge_context += f"\n   Topic: {know['topic']}"
                        knowledge_context += f"\n   Content: {know['content']}"
                        if know['is_attorney']:
                            knowledge_context += "\n   [ATTORNEY EXPERTISE]"
                        if know['verified']:
                            knowledge_context += "\n   [VERIFIED BY ATTORNEY]"
                        if know['related_statutes']:
                            knowledge_context += f"\n   Related Statutes: {', '.join(know['related_statutes'])}"
                        # Track usage
                        user_knowledge_service.increment_usage(know['id'], db)
                    context = f"{context}\n{knowledge_context}"
            except Exception as e:
                print(f"[Chat] Error loading user knowledge: {e}")
            
            # Verification status noted but no formatting instructions added
        else:
            # If specific document sources provided (from recent uploads), prioritize them
            if getattr(request, "doc_sources", None):
                try:
                    filters = {"source": {"$in": request.doc_sources}}
                    # Reduced default from 500 to 25 for faster responses
                    n_results = request.max_results if request.max_results > 0 else 25
                    sources = await rag_service.search(enhanced_prompt, n_results, filters=filters)
                    
                    # Build context with dynamic truncation
                    if not sources:
                        context = await rag_service.get_context(enhanced_prompt, n_results, context_chars=context_chars)
                    else:
                        # Format sources with dynamic truncation based on detail level
                        context_parts = []
                        for i, s in enumerate(sources):
                            text = s['text']
                            if context_chars and len(text) > context_chars:
                                text = text[:context_chars] + "..."
                            
                            # Format citation in Bluebook format for SCOTUS
                            citation = s['metadata'].get('citation', '')
                            source_name = s['metadata'].get('source', '')
                            if citation and ('SCOTUS' in source_name.upper() or s['metadata'].get('jurisdiction') == 'Federal'):
                                citation = _format_bluebook_citation(citation)
                                citation_text = f" | Citation: {citation}"
                            else:
                                citation_text = f" | Citation: {citation}" if citation else ""
                            
                            context_parts.append(
                                f"[{i+1}] Source: {source_name} ({s['metadata'].get('jurisdiction','')}){citation_text}\n{text}"
                            )
                        context = "\n\n".join(context_parts)
                except Exception:
                    n_results = request.max_results if request.max_results > 0 else 500
                    sources = await rag_service.search(enhanced_prompt, n_results)
                    context = await rag_service.get_context(enhanced_prompt, n_results, context_chars=context_chars)
            else:
                # Reduced default from 500 to 25 for faster responses
                n_results = request.max_results if request.max_results > 0 else 25
                context = await rag_service.get_context(enhanced_prompt, n_results, context_chars=context_chars)
                sources = await rag_service.search(enhanced_prompt, n_results)
            
            # Add case law context to help decipher user questions
            if case_contexts and len(case_contexts) > 0:
                case_context_text = "\n\n[CASE LAW CONTEXT - Use these precedents to understand the legal concepts the user is asking about:]"
                for i, case in enumerate(case_contexts[:3], 1):  # Limit to top 3 cases
                    case_context_text += f"\n[{i}] Case Type: {case.get('case_type', 'Unknown')} | Jurisdiction: {case.get('jurisdiction', 'Unknown')} | Outcome: {case.get('outcome', 'Unknown')}"
                    if case.get('citation'):
                        # Format SCOTUS citations in Bluebook format
                        citation = case['citation']
                        if case.get('jurisdiction') == 'Federal' or 'SCOTUS' in str(case.get('source', '')).upper():
                            citation = _format_bluebook_citation(citation)
                        case_context_text += f" | Citation: {citation}"
                    case_context_text += f"\n   Legal Concepts: {', '.join(case.get('legal_concepts', [])[:5])}"
                    case_context_text += f"\n   Key Facts: {case.get('key_facts', '')[:300]}..."
                    case_context_text += f"\n   Similarity to Query: {case.get('similarity_score', 0):.2f}"

                if context:
                    context = f"{context}\n{case_context_text}"
                else:
                    context = case_context_text

                # Add query analysis insights
                query_analysis = search_result.get('query_analysis', {})
                if query_analysis.get('detected_intents'):
                    intent_text = f"\n\n[QUERY ANALYSIS - User seems to be asking about: {', '.join(query_analysis['detected_intents'])}]"
                    context = f"{context}{intent_text}"

                # Add related statutes information for systematic coverage
                if related_statutes:
                    related_text = "\n\n[RELATED STATUTES - When discussing these statutes, systematically mention ALL related statutes from these categories:]"
                    for primary_citation, statute_info in related_statutes.items():
                        related_text += f"\n\nPRIMARY STATUTE {primary_citation} ({statute_info.get('title', 'Unknown')}):"
                        for category, statutes in statute_info.items():
                            if category != 'title' and isinstance(statutes, dict):
                                related_text += f"\n{category.upper().replace('_', ' ')}:"
                                for citation, description in statutes.items():
                                    related_text += f"\n  • § {citation}: {description}"

                    context = f"{context}{related_text}"
                    # Related statutes context added (no formatting instructions)

            # Add user knowledge even when RAG is used differently
            try:
                from server.services.user_knowledge_service import user_knowledge_service
                relevant_knowledge = await user_knowledge_service.get_relevant_knowledge(
                    enhanced_prompt, db, limit=3, user_id=current_user.id
                )
                if relevant_knowledge:
                    knowledge_context = "\n\n[USER KNOWLEDGE & EXPERTISE - Incorporate this firm knowledge:]"
                    for i, know in enumerate(relevant_knowledge, 1):
                        knowledge_context += f"\n[{i}] {know['title']}"
                        knowledge_context += f"\n   Type: {know['knowledge_type']}"
                        if know['topic']:
                            knowledge_context += f"\n   Topic: {know['topic']}"
                        knowledge_context += f"\n   Content: {know['content']}"
                        if know['is_attorney']:
                            knowledge_context += "\n   [ATTORNEY EXPERTISE]"
                        if know['verified']:
                            knowledge_context += "\n   [VERIFIED BY ATTORNEY]"
                        if know['related_statutes']:
                            knowledge_context += f"\n   Related Statutes: {', '.join(know['related_statutes'])}"
                        # Track usage
                        user_knowledge_service.increment_usage(know['id'], db)
                    context = f"{context}\n{knowledge_context}" if context else knowledge_context
            except Exception as e:
                from server.utils.logger import setup_logger
                logger = setup_logger("chat")
                logger.warning(f"Error loading user knowledge: {e}")
        
        # Include recent conversation window for relationship building
        # Show current conversation and reference past conversations by subject
        try:
            # Get messages from current conversation first
            current_convo_msgs = db.query(ChatMessage)\
                .filter(ChatMessage.user_id == current_user.id)\
                .filter(ChatMessage.conversation_id == conversation_id)\
                .order_by(ChatMessage.timestamp.desc())\
                .limit(10).all()
            
            convo_parts = []
            
            # Add current conversation context with subject
            if current_convo_msgs:
                subject_header = f"[CURRENT CONVERSATION"
                if conversation_subject:
                    subject_header += f" - Subject: {conversation_subject}"
                subject_header += " - This is the ongoing conversation you're having:]"
                convo_parts.append(subject_header)
                for m in reversed(current_convo_msgs):
                    convo_parts.append(f"User: {m.message[:600]}")
                    if m.response:
                        convo_parts.append(f"You: {m.response[:600]}")
            
            # Get past conversations organized by subject
            if has_conversation_history:
                # Get conversations by subject
                conversations_by_subject = conversation_subject_service.get_conversations_by_subject(
                    current_user.id, db
                )
                
                # Find related subjects to current conversation
                related_subjects = []
                if conversation_subject:
                    # Find conversations with similar subjects
                    for subject, convs in conversations_by_subject.items():
                        if subject != conversation_subject:
                            # Check if related
                            if conversation_subject_service._is_related(
                                request.message, subject
                            ):
                                related_subjects.append((subject, convs))
                
                # Also get most recent conversations regardless of subject
                recent_convs = db.query(ChatMessage)\
                    .filter(ChatMessage.user_id == current_user.id)\
                    .filter(ChatMessage.conversation_id != conversation_id)\
                    .filter(ChatMessage.subject.isnot(None))\
                    .order_by(ChatMessage.timestamp.desc())\
                    .limit(5).all()
                
                if related_subjects or recent_convs:
                    convo_parts.append("\n[RELATED PAST CONVERSATIONS - Reference these naturally when relevant:]")
                    
                    # Add related subjects first
                    for subject, convs in related_subjects[:2]:
                        if convs:
                            latest_conv = convs[0]
                            convo_parts.append(f"Related topic '{subject}': Previous conversation about this topic")
                    
                    # Add recent conversations by subject
                    seen_subjects = set()
                    for msg in recent_convs[:3]:
                        if msg.subject and msg.subject not in seen_subjects:
                            seen_subjects.add(msg.subject)
                            convo_parts.append(f"Recent topic '{msg.subject}': User previously asked about this")
            
            if convo_parts:
                convo_text = "\n".join(convo_parts)
                if context:
                    context = f"{context}\n\n{convo_text}"
                else:
                    context = convo_text
        except Exception as e:
            logger.warning(f"Error loading conversation history: {e}")
            pass
        
        # Run scenario analysis BEFORE generating response (so we can include it in context)
        scenario_prediction = None
        scenario_context = None
        if request.include_scenario_analysis is not False:  # None or True
            try:
                from server.config import settings
                if settings.SCENARIO_DB_ENABLED:
                    # Detect if question is asking about a specific case situation with facts
                    scenario_keywords = [
                        "outcome", "likely", "probability", "chance", "predict", "what will happen",
                        "what happens", "result", "win", "lose", "settlement", "dismissal",
                        "success", "failure", "risk", "odds", "prospects", "scenario",
                        "my case", "this case", "our case", "client", "plaintiff", "defendant"
                    ]
                    message_lower = request.message.lower()
                    is_scenario_question = any(keyword in message_lower for keyword in scenario_keywords)
                    has_case_facts = len(request.message.split()) > 15
                    has_case_elements = any(term in message_lower for term in [
                        "plaintiff", "defendant", "filed", "sued", "claim", "alleged", 
                        "breach", "damages", "injury", "violation"
                    ])
                    
                    # If "scenario" is explicitly mentioned, always analyze
                    explicitly_scenario = "scenario" in message_lower
                    
                    should_analyze = (
                        request.include_scenario_analysis is True or
                        explicitly_scenario or  # Always analyze if "scenario" is mentioned
                        (is_scenario_question and has_case_facts) or
                        (has_case_elements and has_case_facts)
                    )
                    
                    if should_analyze:
                        from server.services.scenario_service import scenario_service
                        
                        case_type = None
                        jurisdiction = "Virginia"
                        if "contract" in message_lower or "breach" in message_lower:
                            case_type = "Contract"
                        elif "tort" in message_lower or "negligence" in message_lower:
                            case_type = "Tort"
                        elif "criminal" in message_lower:
                            case_type = "Criminal"
                        if "federal" in message_lower:
                            jurisdiction = "Federal"
                        
                        # Try with filters first, but if no results, try without filters
                        # Get DB session for learning feedback
                        from server.models import get_db as get_db_func
                        db_for_learning = next(get_db_func())
                        try:
                            scenario_prediction = await scenario_service.predict_outcome(
                                query_facts=request.message,
                                case_type=case_type,
                                jurisdiction=jurisdiction,
                                db_session=db_for_learning  # Pass for learning feedback
                            )
                        finally:
                            db_for_learning.close()
                        
                        # If filters resulted in no matches, try without filters
                        if scenario_prediction.get("similar_scenarios", 0) == 0 and (case_type or jurisdiction != "Virginia"):
                            # Reuse DB session for learning feedback
                            try:
                                scenario_prediction = await scenario_service.predict_outcome(
                                    query_facts=request.message,
                                    case_type=None,
                                    jurisdiction=None,
                                    db_session=db_for_learning  # Pass for learning feedback
                                )
                            except:
                                # If DB session closed, get new one
                                db_for_learning = next(get_db_func())
                                scenario_prediction = await scenario_service.predict_outcome(
                                    query_facts=request.message,
                                    case_type=None,
                                    jurisdiction=None,
                                    db_session=db_for_learning
                                )
                        
                        # Always return prediction (frontend will handle displaying appropriately)
                        if scenario_prediction.get("similar_scenarios", 0) > 0:
                            # Create context for LLM to naturally incorporate
                            scenario_context = (
                                f"Predictive Analysis (based on {scenario_prediction['similar_scenarios']} similar cases): "
                                f"Predicted outcome: {scenario_prediction['prediction']} "
                                f"({scenario_prediction['confidence']}% confidence). "
                                f"Outcome probabilities: {', '.join([f'{k} {v}%' for k, v in scenario_prediction.get('outcome_probabilities', {}).items()])}. "
                                f"Incorporate this predictive analysis naturally into your response when discussing likely outcomes."
                            )
                        else:
                            # Still return prediction, but don't add to context
                            scenario_context = None
            except Exception as e:
                from server.utils.logger import setup_logger
                logger = setup_logger("chat")
                logger.debug(f"Scenario analysis error (non-fatal): {e}", exc_info=True)
                scenario_prediction = None
                scenario_context = None
        
        # Add scenario context to main context if available
        if scenario_context and context:
            context = f"{context}\n\n{scenario_context}"
        elif scenario_context:
            context = scenario_context
        
        # Check if clarification is needed before generating response (unless user opted to skip)
        from server.services.clarification_service import clarification_service
        needs_clarification = False
        clarification_questions = None
        if not request.skip_clarification:
            needs_clarification, clarification_questions = clarification_service.needs_clarification(
                query=request.message,
                context=context,
                sources=sources if request.use_rag else None
            )
        
        # CLARIFY-FIRST: When clarification is needed, return ONLY questions—do not speculate (AI Laws Article I)
        clarification_only = False
        if request.use_rag and not sources:
            response_text = "No controlling authority found."
            # Add explicit warning that no sources were available
            warnings.append("No legal sources were found in the database for this query. The system cannot provide legal analysis without verified sources.")
        elif needs_clarification and clarification_questions:
            # Clarify-first: Do NOT generate—return only clarification questions to avoid speculation
            response_text = clarification_service.format_clarification_questions(
                clarification_questions,
                request.message
            )
            clarification_only = True
            logger.info(f"[Chat] Clarify-first: returning {len(clarification_questions)} question(s), skipping LLM generation")
        else:
            # Generate response (now includes scenario context if applicable)
            # Use configured token limit based on detail level
            from server.utils.logger import setup_logger
            logger = setup_logger("chat")
            logger.info(f"Calling Ollama generate (max_tokens: {max_output_tokens}, context length: {len(context) if context else 0})")
            try:
                response_text = await ollama_service.generate(
                    prompt=enhanced_prompt,
                    context=context,
                    system_prompt=system_prompt,
                    max_tokens=max_output_tokens  # Use detail level token limit
                )
                logger.info(f"Ollama returned response of {len(response_text)} characters")
                if not response_text or not response_text.strip():
                    logger.error("Ollama returned empty response!")
                    response_text = "I apologize, but I was unable to generate a response. Please try again."
            except Exception as e:
                logger.error(f"Ollama generation failed: {str(e)}", exc_info=True)
                raise  # Re-raise to be caught by outer exception handler
        
        # Validate specificity if this was a specific request (skip for clarification-only)
        if not clarification_only and specificity_info["is_specific_request"]:
            response_lower = response_text.lower()
            specific_terms_found = any(term in response_lower for term in specificity_info["specific_terms"])
            
            if not specific_terms_found:
                # Check if response mentions general statute but not specific one
                general_indicators = ["assault", "battery", "theft", "burglary", "robbery"]
                has_general = any(indicator in response_lower for indicator in general_indicators)
                
                if has_general:
                    # Warning: response may have generalized
                    warning_msg = f"\n\n[WARNING: The response may have provided a general statute instead of the specific '{', '.join(specificity_info['specific_terms'])}' statute requested. Please verify the citation matches the specific statute type.]"
                    response_text += warning_msg
        
        # Format sources for storage (complete) and display (grouped, reduced)
        # Initialize early so it can be used in uncertainty service
        full_source_data = []   # Complete for expansion
        if request.use_rag and sources:
            for source in sources:
                full_source_data.append({
                    "source": source['metadata'].get('source', 'Unknown'),
                    "jurisdiction": source['metadata'].get('jurisdiction', 'Unknown'),
                    "full_text": source['text'],  # Complete text, no truncation
                    "metadata": source.get('metadata', {}),
                    "distance": source.get('distance', None),
                    "id": source.get('id', None)
                })
        
        # full_source_data already initialized above - skip duplicate initialization
        
        # Validate and Correct Response (skip for clarification-only—no answer to validate)
        if not clarification_only:
            response_text = await guardrails_service.validate_and_correct(
                response_text, 
                request.message, 
                sources if request.use_rag else []
            )
        
        # Verify answer against sources (skip for clarification-only)
        if not clarification_only and request.use_rag and sources:
            from server.services.answer_verification_service import answer_verification_service
            verification_result = answer_verification_service.verify_answer_against_sources(
                answer=response_text,
                sources=sources,
                query=request.message
            )
            
            # Add warnings if verification failed
            if not verification_result["verified"]:
                if verification_result["unsupported_citations"]:
                    warnings.append(
                        f"Answer cites {len(verification_result['unsupported_citations'])} citation(s) "
                        f"not found in sources: {', '.join(verification_result['unsupported_citations'][:3])}"
                    )
                if verification_result["issues"]:
                    for issue in verification_result["issues"][:2]:  # Limit to 2 issues
                        if issue not in warnings:
                            warnings.append(issue)
        
        # Add Uncertainty Notice if conditions are met (skip for clarification-only)
        if not clarification_only:
            from server.services.uncertainty_service import uncertainty_service
            scenario_confidence = scenario_prediction.get("confidence") if scenario_prediction else None
            similar_scenarios = scenario_prediction.get("similar_scenarios") if scenario_prediction else None
            
            response_text = uncertainty_service.add_uncertainty_notice_to_response(
                response=response_text,
                authoritative_sources_count=authoritative_sources_count,
                secondary_sources_count=secondary_sources_count,
                verification_status=verification_status,
                scenario_confidence=scenario_confidence,
                similar_scenarios=similar_scenarios,
                conflict_messages=conflict_messages,
                total_sources=len(full_source_data) if request.use_rag else None
            )
        
        # Date disclosure removed - keep response cohesive
        
        # Validate response (skip for clarification-only)
        if clarification_only:
            validation = {"warnings": []}
        else:
            validation = guardrails_service.validate_response(response_text, sources)
            # Add specificity validation warnings
            if specificity_info["is_specific_request"]:
                response_lower = response_text.lower()
                specific_terms_found = any(term in response_lower for term in specificity_info["specific_terms"])
                if not specific_terms_found:
                    validation["warnings"].append(
                        f"Response may not match the specific statute type requested ({', '.join(specificity_info['specific_terms'])}). "
                        "Verify that the cited statute is the specific type, not the general parent statute."
                    )
        
        # full_source_data already initialized above - now just build summary groups

        # Build a reduced, informative summary for inline display
        catalog = _load_source_catalog()
        summary_groups: Dict[str, dict] = {}
        max_summary_items = 15  # Limit inline list for readability

        for item in full_source_data:
            metadata = item.get("metadata", {}) or {}
            source_name = item.get("source") or metadata.get("source") or "Unknown"
            jurisdiction = item.get("jurisdiction") or metadata.get("jurisdiction") or "Unknown"
            citation = metadata.get("citation")
            document_type = metadata.get("document_type")
            distance = item.get("distance")
            
            # Format SCOTUS citations in Bluebook format
            if citation and ('SCOTUS' in source_name.upper() or jurisdiction == 'Federal'):
                citation = _format_bluebook_citation(citation)

            # Group primarily by citation; fall back to source/jurisdiction/type
            key_parts = [source_name, jurisdiction]
            if citation:
                key_parts.append(citation)
            elif document_type:
                key_parts.append(document_type)
            key = "::".join(str(p) for p in key_parts)

            # Respect summary limit
            if key not in summary_groups and len(summary_groups) >= max_summary_items:
                continue

            catalog_entry = catalog.get(source_name, {})
            urls = catalog_entry.get("urls") or []
            link = urls[0] if urls else None
            priority = int(catalog_entry.get("priority", 5)) if catalog_entry else 5

            if key not in summary_groups:
                full_text = item.get("full_text") or ""
                snippet = full_text[:400] + ("..." if len(full_text) > 400 else "")

                summary_groups[key] = {
                    "source": source_name,
                    "jurisdiction": jurisdiction,
                    "citation": citation,
                    "document_type": document_type,
                    "snippet": snippet,
                    "distance": distance,
                    "priority": priority,
                    "link": link,
                    "count": 1,
                }
            else:
                group = summary_groups[key]
                group["count"] += 1
                if distance is not None:
                    current_best = group.get("distance")
                    if current_best is None or distance < current_best:
                        group["distance"] = distance

        # Sort summary for elegant display
        formatted_sources = sorted(
            summary_groups.values(),
            key=lambda s: (
                s.get("priority", 5),
                s.get("distance", 1.0) if s.get("distance") is not None else 1.0,
                s.get("source") or "",
            ),
        )
        
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or f"conv_{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Store chat message in database with subject and full sources
        chat_message = ChatMessage(
            user_id=current_user.id,
            conversation_id=conversation_id,
            subject=conversation_subject,  # Store detected subject
            message=request.message,
            response=response_text,
            sources=json.dumps(formatted_sources),      # Truncated for display
            full_sources=json.dumps(full_source_data),  # Complete for expansion
            warnings=json.dumps(validation.get("warnings", []))
        )
        
        # Update subject for all messages in this conversation if this is the first message
        if is_first_message and conversation_subject:
            try:
                # Update any existing messages in this conversation (shouldn't be any, but just in case)
                db.query(ChatMessage)\
                    .filter(ChatMessage.conversation_id == conversation_id)\
                    .filter(ChatMessage.subject.is_(None))\
                    .update({"subject": conversation_subject})
            except Exception:
                pass  # Non-critical
        db.add(chat_message)
        db.commit()
        db.refresh(chat_message)

        # Persist semantic cache after message is saved (first message only; not clarifications)
        if (
            settings.SEMANTIC_CACHE_ENABLED
            and is_first_message
            and not clarification_only
            and query_embedding
            and response_text
            and not response_text.strip().startswith("No controlling authority")
        ):
            try:
                semantic_cache_service.store(
                    db,
                    user_id=current_user.id,
                    scope_fp=scope_fp,
                    ollama_model=settings.OLLAMA_MODEL,
                    query_preview=enhanced_prompt,
                    query_embedding=query_embedding,
                    response_text=response_text,
                    sources_display=formatted_sources,
                    full_sources=full_source_data,
                    warnings=warnings,
                    extra={
                        "verification_status": verification_status,
                        "authoritative_sources_count": authoritative_sources_count,
                        "secondary_sources_count": secondary_sources_count,
                        "conflict_messages": conflict_messages or [],
                        "search_total_results": search_total_results,
                        "search_unique_sources": search_unique_sources,
                        "detail_level": detail_level,
                        "recommended_level": recommended_level,
                        "total_sources": len(full_source_data),
                        "unique_sources": len(formatted_sources),
                        "response_format": effective_fmt,
                    },
                )
            except Exception as cache_store_ex:
                logger.warning(f"Semantic cache store skipped: {cache_store_ex}")
        
        # Audit log
        try:
            from server.models import AuditLog
            db.add(AuditLog(
                user_id=current_user.id,
                action="chat_query",
                path="/api/chat/query",
                method="POST",
                status=200,
                details=json.dumps({"conversation_id": conversation_id})[:1000]
            ))
            db.commit()
        except Exception:
            db.rollback()

        
        # Validate response_text is not empty
        if not response_text or not response_text.strip():
            from server.utils.logger import setup_logger
            logger = setup_logger("chat")
            logger.error("Generated response is empty! This should not happen.")
            response_text = "I apologize, but I was unable to generate a response. Please try rephrasing your question or try again."
        
        return ChatResponse(
            response=response_text,
            sources=formatted_sources,
            conversation_id=conversation_id,
            timestamp=datetime.now().isoformat(),
            warnings=validation.get("warnings", []),
            message_id=chat_message.id,
            scenario_prediction=scenario_prediction,
            detail_level=detail_level,
            recommended_level=recommended_level,
            is_streaming=False,
            total_sources=len(full_source_data),
            unique_sources=len(formatted_sources),
            verification_status=verification_status,
            authoritative_sources_count=authoritative_sources_count,
            secondary_sources_count=secondary_sources_count,
            conflict_messages=conflict_messages or None,
            search_total_results=search_total_results,
            search_unique_sources=search_unique_sources,
            clarification_only=clarification_only,
            clarification_questions=clarification_questions if clarification_only else None,
            semantic_cache_hit=semantic_cache_hit,
            response_format=effective_fmt,
        )
    
    except Exception as e:
        # Log the full error for debugging
        from server.utils.logger import setup_logger
        logger = setup_logger("chat")
        logger.error(f"Chat query error: {str(e)}", exc_info=True)
        
        # Audit error
        try:
            from server.models import AuditLog
            db.add(AuditLog(
                user_id=current_user.id if current_user else None,
                action="chat_error",
                path="/api/chat/query",
                method="POST",
                status=500,
                details=json.dumps({"error": str(e)})[:1000]
            ))
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Streaming chat response with detail level support (requires authentication)"""
    from server.services.smart_default_service import smart_default_service
    from server.config import settings
    try:
        intent_mode = guardrails_service.detect_query_intent(request.message)
        effective_fmt = _effective_response_format(request, intent_mode)

        # Smart default detection for streaming
        conversation_history_for_detection = []
        try:
            prev_msgs = db.query(ChatMessage)\
                .filter(ChatMessage.user_id == current_user.id)\
                .order_by(ChatMessage.timestamp.desc())\
                .limit(5)\
                .all()
            conversation_history_for_detection = [
                {"message": msg.message, "response": msg.response}
                for msg in prev_msgs
            ]
        except Exception:
            pass
        
        # Determine detail level
        if request.detail_level:
            detail_level = request.detail_level
        else:
            detection_result = smart_default_service.detect_detail_level(
                request.message,
                conversation_history_for_detection
            )
            detail_level = detection_result["recommended_level"]
        
        # Get configuration for the detail level
        detail_level_config = settings.DETAIL_LEVELS.get(detail_level, settings.DETAIL_LEVELS["standard"])
        max_output_tokens = request.max_output_tokens or detail_level_config["max_tokens"]
        context_chars = detail_level_config["context_chars"]
        detail_instruction = detail_level_config["instruction"]
        
        # Build system prompt with detail level
        system_prompt = guardrails_service.build_system_prompt(response_format=effective_fmt)
        system_prompt += f"\n\nRESPONSE DETAIL LEVEL: {detail_level.upper()}\n"
        system_prompt += f"{detail_instruction}\n"
        if request.exhaustive_search:
            system_prompt += "EXHAUSTIVE TRIAL PREP MODE ENABLED: Include every single relevant case, statute, and authority.\n"
        
        enhanced_prompt = guardrails_service.enhance_prompt(request.message)
        
        # Get context with proper search
        context = None
        sources = []
        if request.use_rag:
            specificity_info = rag_service._detect_specific_statute_request(request.message)
            n_results = 50 if not request.exhaustive_search else 200
            search_result = await rag_service.search_comprehensive(
                enhanced_prompt,
                n_results_per_query=n_results,
                require_multiple_sources=True,
                min_authoritative_sources=2,
                exhaustive=request.exhaustive_search
            )
            
            sources = search_result['results']
            context_parts = []
            
            for i, source in enumerate(sources[:100], 1):  # Limit to 100 for streaming
                source_name = source['metadata'].get('source', 'Unknown')
                jurisdiction = source['metadata'].get('jurisdiction', 'Unknown')
                text = source['text']
                if context_chars and len(text) > context_chars:
                    text = text[:context_chars] + "..."
                context_parts.append(f"[{i}] Source: {source_name} ({jurisdiction})\n{text}")
            
            context = "\n\n".join(context_parts)
        
        # Clarify-first: check if clarification is needed (unless user opted to skip)
        from server.services.clarification_service import clarification_service
        needs_clarification = False
        clarification_questions = None
        if not request.skip_clarification:
            needs_clarification, clarification_questions = clarification_service.needs_clarification(
                query=request.message,
                context=context,
                sources=sources if request.use_rag else None
            )
        
        from fastapi.responses import StreamingResponse
        
        async def generate():
            # Send metadata first
            clarification_only = bool(needs_clarification and clarification_questions)
            metadata = {
                "type": "metadata",
                "detail_level": detail_level,
                "max_tokens": max_output_tokens,
                "source_count": len(sources) if request.use_rag else 0,
                "clarification_only": clarification_only,
                "clarification_questions": clarification_questions if clarification_only else None,
                "response_format": effective_fmt,
            }
            yield f"data: {json.dumps(metadata)}\n\n"
            
            # Clarify-first: if clarification needed, stream only questions (no LLM call)
            if needs_clarification and clarification_questions:
                clarification_text = clarification_service.format_clarification_questions(
                    clarification_questions,
                    request.message
                )
                # Send clarification as single chunk (same format as Ollama chunks)
                yield f"data: {clarification_text}\n\n"
            # No sources: stream "No controlling authority found."
            elif request.use_rag and not sources:
                yield f"data: No controlling authority found.\n\n"
            else:
                # Stream the response from Ollama
                async for chunk in ollama_service.generate_stream(
                    prompt=enhanced_prompt,
                    context=context,
                    system_prompt=system_prompt,
                    max_tokens=max_output_tokens
                ):
                    yield f"data: {chunk}\n\n"
            yield f"data: [DONE]\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error streaming response: {str(e)}")


@router.get("/message/{message_id}/full-sources")
async def get_full_sources(
    message_id: int,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Retrieve complete source list with full text for a specific message.
    This allows lawyers to get the complete case list after seeing the summary.
    """
    try:
        # Get message
        message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Check permissions
        if not can_view_user_chat(current_user, message.user_id, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Load full sources from DB
        full_sources = json.loads(message.full_sources) if message.full_sources else []

        # Build a reduced, display-friendly source list with links
        catalog = _load_source_catalog()
        grouped: Dict[str, dict] = {}
        max_display_groups = 50  # Limit for UI clarity

        for item in full_sources:
            metadata = item.get("metadata", {}) or {}
            source_name = item.get("source") or metadata.get("source") or "Unknown"
            jurisdiction = item.get("jurisdiction") or metadata.get("jurisdiction") or "Unknown"
            citation = metadata.get("citation")
            document_type = metadata.get("document_type")
            distance = item.get("distance")

            # Group primarily by citation when available; fall back to source/jurisdiction/type
            key_parts = [source_name, jurisdiction]
            if citation:
                key_parts.append(citation)
            elif document_type:
                key_parts.append(document_type)
            key = "::".join(str(p) for p in key_parts)

            # Stop once we have enough distinct display groups
            if key not in grouped and len(grouped) >= max_display_groups:
                continue

            catalog_entry = catalog.get(source_name, {})
            urls = catalog_entry.get("urls") or []
            link = urls[0] if urls else None
            priority = int(catalog_entry.get("priority", 5)) if catalog_entry else 5

            if key not in grouped:
                full_text = item.get("full_text") or ""
                snippet = full_text[:800] + ("..." if len(full_text) > 800 else "")

                grouped[key] = {
                    "source": source_name,
                    "jurisdiction": jurisdiction,
                    "citation": citation,
                    "document_type": document_type,
                    "snippet": snippet,
                    "distance": distance,
                    "chunk_count": 1,
                    "priority": priority,
                    "link": link,
                }
            else:
                group = grouped[key]
                group["chunk_count"] += 1
                # Keep best (lowest) distance
                if distance is not None:
                    current_best = group.get("distance")
                    if current_best is None or distance < current_best:
                        group["distance"] = distance
        
        # Sort groups by priority and distance for elegant display
        display_sources = sorted(
            grouped.values(),
            key=lambda s: (
                s.get("priority", 5),
                s.get("distance", 1.0) if s.get("distance") is not None else 1.0,
                s.get("source") or "",
            ),
        )

        return {
            "message_id": message_id,
            "total_sources": len(full_sources),
            "unique_sources": len(display_sources),
            "sources": display_sources,
            "query": message.message,
            "response_excerpt": message.response[:500] + "..." if len(message.response) > 500 else message.response
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving full sources: {str(e)}")


@router.post("/message/{message_id}/expand-response")
async def expand_response(
    message_id: int,
    detail_level: str = "comprehensive",
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Regenerate response for a message with more detail using cached full sources.
    This allows lawyers to request a more complete answer without re-querying.
    
    Args:
        message_id: ID of the chat message to expand
        detail_level: Target detail level ("comprehensive", "complete", or "unlimited")
    """
    from server.config import settings
    try:
        # Get message with full sources
        message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Check permissions
        if not can_view_user_chat(current_user, message.user_id, db):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get full sources
        full_sources_list = json.loads(message.full_sources) if message.full_sources else []
        
        if not full_sources_list:
            raise HTTPException(status_code=400, detail="No full sources available for this message")
        
        # Validate detail level
        if detail_level not in settings.DETAIL_LEVELS:
            raise HTTPException(status_code=400, detail=f"Invalid detail level: {detail_level}")
        
        # Get configuration for requested detail level
        detail_config = settings.DETAIL_LEVELS[detail_level]
        max_tokens = detail_config["max_tokens"]
        instruction = detail_config["instruction"]
        
        # Build context from full sources
        context_parts = []
        for i, source in enumerate(full_sources_list, 1):
            context_parts.append(
                f"[{i}] Source: {source['source']} ({source['jurisdiction']})\n{source['full_text']}"
            )
        
        full_context = "\n\n".join(context_parts)
        
        # Build system prompt
        system_prompt = guardrails_service.build_system_prompt()
        system_prompt += f"\n\nRESPONSE DETAIL LEVEL: {detail_level.upper()}\n"
        system_prompt += f"{instruction}\n"
        system_prompt += f"\n[You have {len(full_sources_list)} complete sources available. Include ALL relevant cases in your response.]\n"
        
        # Generate expanded response
        expanded_response = await ollama_service.generate(
            prompt=message.message,
            context=full_context,
            system_prompt=system_prompt,
            max_tokens=max_tokens
        )
        
        return {
            "message_id": message_id,
            "original_response": message.response,
            "expanded_response": expanded_response,
            "detail_level": detail_level,
            "sources_used": len(full_sources_list),
            "max_tokens": max_tokens
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error expanding response: {str(e)}")


def _corpus_update_in_progress() -> bool:
    """True while scripts/update_va_legal_corpus.py is rebuilding the statute index."""
    lock = Path(settings.DATA_DIR) / ".va_corpus_update.lock"
    return lock.exists()


@router.get("/ready")
async def chat_ready():
    """
    Check if chat backend is ready (Ollama + model, RAG path).
    No auth required. Use this to show "Chat ready" or hints before sending a message.
    """
    from server.config import settings
    result = {"ready": True, "backend": "ok", "ollama": "unknown", "model": settings.OLLAMA_MODEL, "rag": "ok"}
    if _corpus_update_in_progress():
        result["corpus_update_in_progress"] = True
        result["message"] = (
            "Virginia Code index is rebuilding. Chat works, but statute search may be slow or "
            "incomplete until the update finishes. Run updates overnight via UPDATE_VA_LAWS.bat."
        )
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if r.status_code != 200:
                result["ollama"] = "error"
                result["ready"] = False
                result["message"] = "Ollama returned an error. Is it running?"
                return result
            data = r.json() or {}
            model_list = data.get("models") if isinstance(data.get("models"), list) else []
            models = [m.get("name") for m in model_list if isinstance(m, dict) and m.get("name")]
            model_found = settings.OLLAMA_MODEL in models or any(
                n == settings.OLLAMA_MODEL or (n.startswith(settings.OLLAMA_MODEL + "-") or n.startswith(settings.OLLAMA_MODEL + ":"))
                for n in models
            )
            if model_found:
                result["ollama"] = "ok"
            else:
                result["ollama"] = "model_missing"
                result["ready"] = False
                result["message"] = f"Model '{settings.OLLAMA_MODEL}' not in Ollama. Run: ollama run {settings.OLLAMA_MODEL}"
                result["available_models"] = models[:10]
    except Exception as e:
        result["ollama"] = "unavailable"
        result["ready"] = False
        result["message"] = f"Ollama not reachable at {settings.OLLAMA_BASE_URL}. Start with: ollama serve"
    try:
        p = Path(settings.CHROMA_DB_PATH)
        if not p.exists():
            result["rag"] = "path_missing"
    except Exception:
        result["rag"] = "error"
    return result


@router.get("/models")
async def get_ollama_models():
    """
    Get available Ollama models. Used by AdminDashboard for AI engine status.
    Returns list of model names from Ollama.
    """
    try:
        import httpx
        from server.config import settings
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                return {"models": models, "status": "ok"}
    except Exception:
        pass
    return {"models": [], "status": "unavailable"}


@router.get("/history", response_model=ChatHistoryListResponse)
async def get_chat_history(
    user_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Get chat history (with permission checks)"""
    # If user_id is specified, check permissions
    if user_id and not can_view_user_chat(current_user, user_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this user's chat history")
    
    # Get accessible user IDs
    accessible_ids = get_accessible_user_ids(current_user, db)
    
    # Build query
    query = db.query(ChatMessage).join(User).filter(
        ChatMessage.user_id.in_(accessible_ids),
        User.is_active == True
    )
    
    # Filter by user_id if specified
    if user_id:
        query = query.filter(ChatMessage.user_id == user_id)
    
    # Filter by conversation_id if specified
    if conversation_id:
        query = query.filter(ChatMessage.conversation_id == conversation_id)
    
    # Get total count
    total = query.count()
    
    # Get messages with pagination
    messages = query.order_by(ChatMessage.timestamp.desc()).offset(offset).limit(limit).all()
    
    # Format response
    formatted_messages = []
    for msg in messages:
        sources = json.loads(msg.sources) if msg.sources else []
        warnings = json.loads(msg.warnings) if msg.warnings else []
        formatted_messages.append(ChatHistoryResponse(
            id=msg.id,
            user_id=msg.user_id,
            username=msg.user.username,
            full_name=msg.user.full_name,
            conversation_id=msg.conversation_id,
            message=msg.message,
            response=msg.response,
            sources=sources,
            warnings=warnings,
            timestamp=msg.timestamp.isoformat()
        ))
    
    return ChatHistoryListResponse(
        messages=formatted_messages,
        total=total
    )


@router.get("/history/conversations")
async def get_conversations(
    user_id: Optional[int] = None,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Get list of conversation IDs for a user"""
    # Check permissions
    if user_id and not can_view_user_chat(current_user, user_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    accessible_ids = get_accessible_user_ids(current_user, db)
    if user_id:
        accessible_ids = [user_id] if user_id in accessible_ids else []
    
    # Get unique conversation IDs
    conversations = db.query(ChatMessage.conversation_id).filter(
        ChatMessage.user_id.in_(accessible_ids)
    ).distinct().all()
    
    return {
        "conversations": [conv[0] for conv in conversations]
    }

