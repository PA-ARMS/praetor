"""
Chat API routes - Legal research queries
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator
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


def _want_live_lookup(request: "ChatRequest") -> bool:
    if getattr(request, "use_web", None) is False:
        return False
    if getattr(request, "use_web", None) is True:
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


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    use_rag: bool = True
    max_results: int = 0  # 0 means no limit - return all relevant results
    doc_sources: Optional[List[str]] = None
    include_scenario_analysis: Optional[bool] = None  # Auto-detect if None
    detail_level: Optional[str] = None  # "summary", "standard", "comprehensive", "complete", "unlimited", or None for auto
    exhaustive_search: bool = False  # Enable exhaustive trial prep mode (500+ sources)
    max_output_tokens: Optional[int] = None  # Override token limit
    use_web: Optional[bool] = None  # Live official-source lookup; None = use server default
    
    @field_validator('message')
    def validate_message(cls, v):
        """Validate message length and content"""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        if len(v) > 10000:  # 10KB max message length
            raise ValueError("Message too long. Maximum 10,000 characters.")
        return v.strip()
    
    @field_validator('conversation_id')
    def validate_conversation_id(cls, v):
        """Validate conversation ID format"""
        if v and len(v) > 200:
            raise ValueError("Conversation ID too long")
        return v


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
            user_name=current_user.full_name
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
        
        # === STEP 4: RETRIEVE RAG CONTEXT ===
        # If RAG is enabled, search the vector database for relevant legal documents
        # This uses semantic search to find documents similar to the query
        
        # CRITICAL: Query SCOTUS separately as a distinct authoritative database
        # SCOTUS is #1 in hierarchy: "United States Constitution and U.S. Supreme Court precedent (binding on all jurisdictions)"
        scotus_sources = []
        if request.use_rag:
            logger.info("[Chat] Querying SCOTUS database separately...")
            scotus_start = time.time()
            # Check if query mentions a specific case name (Heller, Bruen, etc.)
            case_name_matches = []
            landmark_case_names = ['heller', 'bruen', 'mcdonald', 'miller', 'miranda']
            query_lower = enhanced_prompt.lower()
            
            for case_name in landmark_case_names:
                if case_name in query_lower:
                    # Search by case name first for exact matches
                    case_results = await scotus_service.search_scotus_by_case_name(case_name)
                    case_name_matches.extend(case_results[:2])  # Top 2 per case
            
            # Also do semantic search
            scotus_sources = await scotus_service.search_scotus(enhanced_prompt, n_results=5)
            
            # Combine case name matches with semantic search, prioritizing case name matches
            if case_name_matches:
                # Remove duplicates
                seen_ids = {r['id'] for r in scotus_sources}
                for case_match in case_name_matches:
                    if case_match['id'] not in seen_ids:
                        scotus_sources.insert(0, case_match)  # Insert at beginning
                        seen_ids.add(case_match['id'])
            scotus_elapsed = time.time() - scotus_start
            logger.info(f"[Chat] SCOTUS search completed in {scotus_elapsed:.2f}s, found {len(scotus_sources)} cases")
        
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
            if _want_live_lookup(request):
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
            
            # CRITICAL: Add explicit list of available statutes to prevent hallucination
            available_statutes = set()
            available_cases = []
            for source in sources:
                # Extract citations from source text
                text = source.get('text', '')
                # Find all Virginia Code citations
                va_citations = re.findall(r'§\s*(\d+\.\d+-\d+(?:\.\d+)?)', text)
                available_statutes.update(va_citations)
                # Also check metadata
                meta_cit = source.get('metadata', {}).get('citation', '')
                if meta_cit:
                    cit_match = re.search(r'(\d+\.\d+-\d+(?:\.\d+)?)', str(meta_cit))
                    if cit_match:
                        available_statutes.add(cit_match.group(1))
                # Extract case names with citations
                case_pattern = r'(Commonwealth|State)\s+v\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?[,\s]+(\d+\s+(?:Va\.|Va\.\s+App\.|U\.S\.|S\.\s+Ct\.))'
                cases = re.findall(case_pattern, text, re.IGNORECASE)
                available_cases.extend([f"{c[0]} v. {c[1]}" for c in cases if len(c) == 2])
            
            # CRITICAL: ALWAYS add explicit statute list to prevent hallucination
            # This section MUST appear even if empty to prevent the AI from making up citations
            context_parts.append("\n" + "="*80)
            context_parts.append("CRITICAL: AVAILABLE STATUTES AND CASES IN SOURCES")
            context_parts.append("="*80)
            context_parts.append("YOU MAY ONLY CITE THE FOLLOWING STATUTES THAT APPEAR IN THE SOURCES:")
            if available_statutes:
                for stat in sorted(available_statutes):
                    context_parts.append(f"  - § {stat}")
            else:
                context_parts.append("  - NO VIRGINIA CODE SECTIONS FOUND IN SOURCES")
                context_parts.append("  - THIS MEANS YOU CANNOT CITE ANY VIRGINIA CODE SECTIONS")
            context_parts.append("")
            context_parts.append("AVAILABLE CASE CITATIONS IN SOURCES:")
            if available_cases:
                for case in available_cases[:10]:  # Limit to 10
                    context_parts.append(f"  - {case}")
            else:
                context_parts.append("  - NO CASE CITATIONS FOUND IN SOURCES")
            context_parts.append("")
            context_parts.append("ABSOLUTE RULE: DO NOT cite any statute or case NOT listed above.")
            context_parts.append("If the list above shows 'NO VIRGINIA CODE SECTIONS FOUND', you MUST NOT cite any Virginia Code sections.")
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
        
        # Check if clarification is needed before generating response
        from server.services.clarification_service import clarification_service
        needs_clarification, clarification_questions = clarification_service.needs_clarification(
            query=request.message,
            context=context,
            sources=sources if request.use_rag else None
        )
        
        # If RAG returned nothing, force 'No controlling authority found.'
        # This is critical - we must NOT allow the AI to use training data when no sources are found
        if request.use_rag and not sources:
            response_text = "No controlling authority found."
            # Add explicit warning that no sources were available
            warnings.append("No legal sources were found in the database for this query. The system cannot provide legal analysis without verified sources.")
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
            
            # If clarification is needed and AI didn't ask, add clarification questions
            if needs_clarification and clarification_questions:
                # Check if response already contains questions
                response_lower = response_text.lower()
                has_questions = any(
                    marker in response_lower 
                    for marker in ["?", "could you", "can you", "would you", "please provide", "i need", "clarify"]
                )
                
                if not has_questions:
                    # Add clarification questions to response
                    clarification_text = clarification_service.format_clarification_questions(
                        clarification_questions,
                        request.message
                    )
                    response_text = response_text + clarification_text
        
        # Validate specificity if this was a specific request
        if specificity_info["is_specific_request"]:
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
        
        # Validate and Correct Response (NEW LOOP)
        response_text = await guardrails_service.validate_and_correct(
            response_text, 
            request.message, 
            sources if request.use_rag else []
        )
        
        # Verify answer against sources (ensure answer is "right")
        if request.use_rag and sources:
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
        
        # Add Uncertainty Notice if conditions are met (AI Laws Article VIII)
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
        
        # Validate response
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
        system_prompt = guardrails_service.build_system_prompt()
        system_prompt += f"\n\nRESPONSE DETAIL LEVEL: {detail_level.upper()}\n"
        system_prompt += f"{detail_instruction}\n"
        if request.exhaustive_search:
            system_prompt += "EXHAUSTIVE TRIAL PREP MODE ENABLED: Include every single relevant case, statute, and authority.\n"
        
        enhanced_prompt = guardrails_service.enhance_prompt(request.message)
        
        # Get context with proper search
        context = None
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
        
        from fastapi.responses import StreamingResponse
        
        async def generate():
            # Send metadata first
            metadata = {
                "type": "metadata",
                "detail_level": detail_level,
                "max_tokens": max_output_tokens,
                "source_count": len(sources) if request.use_rag else 0
            }
            yield f"data: {json.dumps(metadata)}\n\n"
            
            # Stream the response
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

