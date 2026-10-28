"""
RAG Service - Retrieval Augmented Generation
Manages vector database and semantic search
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Optional
from pathlib import Path
from server.config import settings
import json
import re
import asyncio
import time
import uuid
import logging  # Added for log suppression
from server.services.ollama_service import ollama_service
from server.services.scenario_service import scenario_service
from server.utils.logger import setup_logger


def _sanitize_chroma_metadata(metadata: Dict) -> Dict:
    """
    Chroma metadata rules (see chromadb.api.types.validate_metadata):
    - Native Python lists are rejected if empty OR not homogeneously typed.
    - We never pass raw lists: non-empty lists become JSON strings; empty lists are omitted.
    - Nested dicts become JSON strings.
    """
    if not metadata:
        return {"source": "document"}
    out: Dict = {}
    for k, v in metadata.items():
        if v is None:
            continue
        if isinstance(v, tuple):
            v = list(v)
        if isinstance(v, dict):
            try:
                out[k] = json.dumps(v, ensure_ascii=False)[:16000]
            except (TypeError, ValueError):
                out[k] = str(v)[:16000]
            continue
        if isinstance(v, list):
            if len(v) == 0:
                continue
            flat = []
            for item in v:
                if item is None:
                    continue
                if isinstance(item, str) and not item.strip():
                    continue
                flat.append(item)
            if not flat:
                continue
            # Store as JSON string so Chroma never applies list validation (empty / heterogeneous).
            try:
                serializable = []
                for item in flat:
                    if isinstance(item, (str, int, float, bool)):
                        serializable.append(item)
                    else:
                        serializable.append(str(item)[:2000])
                out[k] = json.dumps(serializable, ensure_ascii=False)[:16000]
            except (TypeError, ValueError):
                out[k] = json.dumps([str(x) for x in flat])[:16000]
            continue
        if isinstance(v, (str, int, float, bool)):
            if isinstance(v, str) and len(v) > 16000:
                out[k] = v[:16000]
            else:
                out[k] = v
        else:
            out[k] = str(v)[:16000]
    if not out:
        return {"source": "document"}
    return out


def _coerce_chroma_metadata(metadata: Dict) -> Dict:
    """
    Normalize for Chroma, then verify against chromadb.api.types.validate_metadata.
    If anything still fails (edge-case types), force JSON/str so add() cannot error.
    """
    m = _sanitize_chroma_metadata(metadata)
    try:
        from chromadb.api.types import validate_metadata

        validate_metadata(m)
        return m
    except Exception as e:
        logging.getLogger(__name__).warning("Chroma metadata strict fallback after: %s", e)
    out: Dict = {}
    for k, v in m.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            if isinstance(v, str) and len(v) > 16000:
                out[k] = v[:16000]
            else:
                out[k] = v
        else:
            try:
                out[k] = json.dumps(v, default=str, ensure_ascii=False)[:16000]
            except Exception:
                out[k] = str(v)[:16000]
    if not out:
        out = {"source": "document"}
    try:
        from chromadb.api.types import validate_metadata

        validate_metadata(out)
    except Exception:
        out = {"source": "document", "note": "metadata_fallback"}
    return out


def _get_embedding_service():
    """Return embedding service: BGE if enabled, else Ollama."""
    if settings.BGE_EMBEDDINGS_ENABLED:
        try:
            from server.services.bge_embedding_service import bge_embedding_service
            if bge_embedding_service.is_available():
                return bge_embedding_service
        except Exception:
            pass
    return ollama_service


class RAGService:
    
    def _expand_query_with_synonyms(self, query: str) -> List[str]:
        """
        Expand a query to include Virginia Code legal terminology synonyms.
        Returns a list of SHORT, FOCUSED query variations for optimal semantic search.
        
        Long queries perform poorly in semantic search - we need focused terms.
        
        Example: "domestic violence" -> [
            "domestic violence Virginia",
            "assault and battery against a family or household member",
            "18.2-57.2 family household member",
            "family abuse Virginia statute"
        ]
        """
        query_lower = query.lower()
        expanded_queries = [query]  # Always include original
        matched_terms = []
        
        # Find all matching synonym keys in the query
        for common_term, legal_terms in self.LEGAL_SYNONYMS.items():
            if common_term in query_lower:
                matched_terms.append((common_term, legal_terms))
        
        if not matched_terms:
            return [query]  # No synonyms found, return original only
        
        # For each matched term, create SHORT focused queries
        for common_term, legal_terms in matched_terms:
            # Add the top legal synonyms as SHORT, FOCUSED queries
            # These are optimized for semantic search
            for legal_term in legal_terms[:4]:  # Top 4 synonyms
                # Create short focused query (better for embedding search)
                if len(legal_term) <= 10:  # Citation like "18.2-57.2"
                    focused = f"{legal_term} Virginia statute elements penalty"
                else:
                    focused = f"{legal_term} Virginia"
                
                if focused.lower() not in [q.lower() for q in expanded_queries]:
                    expanded_queries.append(focused)
            
            # Add the official legal term as a standalone query
            primary_legal_term = legal_terms[0]  # First synonym is usually the official term
            if primary_legal_term not in [q.lower() for q in expanded_queries]:
                expanded_queries.append(primary_legal_term)
        
        # NEW: Systematic Vernacular Translation
        # Loop through ALL synonyms to find matches and force citation-based searches
        for common_term, legal_terms in self.LEGAL_SYNONYMS.items():
            if common_term in query_lower:
                # Find the first term that looks like a citation (e.g., "18.2-57.2")
                citation = next((t for t in legal_terms if re.search(r'\d+\.\d+', t)), None)
                
                if citation:
                    # Ensure citation has "§" prefix if missing (matches DB format)
                    if not citation.startswith("§") and not citation.startswith("Section"):
                        db_citation = f"§ {citation}"
                    else:
                        db_citation = citation

                    # Found a citation mapping! Create precision legal queries.
                    # 1. Elements query (Case Law focus) - Puts this FIRST
                    expanded_queries.insert(0, f"{db_citation} elements of offense Commonwealth must prove")
                    # 2. Case Law Sufficiency (Precedent focus)
                    expanded_queries.insert(1, f"{db_citation} case law sufficiency of evidence")
                    # 3. Definition/Statute text (Statutory focus) - This triggers exact match lookup
                    expanded_queries.insert(2, f"text of {db_citation}")
                    # 4. RAW CITATION (Triggers Exact Metadata Lookup)
                    expanded_queries.insert(3, db_citation)
                    
                    self.logger.info(f"Vernacular Translation: '{common_term}' -> '{db_citation}'")

        max_var = int(getattr(settings, "CHAT_RAG_MAX_VARIATIONS", 4) or 4)
        return expanded_queries[:max(1, max_var)]

    def _legislative_effective_date_variations(self, query: str) -> List[str]:
        """Extra RAG queries for session-law / effective-date questions."""
        q = query.lower()
        extra: List[str] = []
        if re.search(r"july\s*1|effective\s+date|take\s+effect|enact", q):
            extra.append("Virginia uncodified act effective date July 1")
            extra.append("Virginia session law enacted effective")
        if re.search(r"\b20\d{2}\b", q):
            year = re.search(r"\b(20\d{2})\b", q)
            if year:
                extra.append(f"Virginia Acts {year.group(1)} Chapter effective")
        return extra[:2]

    async def search_fast(
        self,
        query: str,
        n_results: int = 8,
        filters: Optional[Dict] = None,
        use_synonyms: bool = True,
    ) -> List[Dict]:
        """
        Faster RAG path for chat: capped synonym variations, parallel embed/search.
        Does not query scenario DB or run case-context analysis.
        """
        n_results = n_results or int(getattr(settings, "CHAT_SIMPLE_N_RESULTS", 8) or 8)
        variations: List[str] = [query]
        if use_synonyms:
            variations = self._expand_query_with_synonyms(query)
            variations.extend(self._legislative_effective_date_variations(query))
            max_var = int(getattr(settings, "CHAT_RAG_MAX_VARIATIONS", 4) or 4)
            # Deduplicate while preserving order
            seen_v: set = set()
            deduped: List[str] = []
            for v in variations:
                key = v.lower().strip()
                if key not in seen_v:
                    seen_v.add(key)
                    deduped.append(v)
            variations = deduped[: max(1, max_var + 2)]
        if len(variations) > 1:
            return await self._search_with_variations(variations, n_results, filters)
        return await self.search(query, n_results, filters=filters, use_synonyms=False)

    async def search_legislative_effective_date(
        self,
        query: str,
        year: Optional[int] = None,
        n_results: int = 15,
    ) -> List[Dict]:
        """
        Search for session laws / statutes mentioning an effective date (e.g. July 1, 2026).
        Filters semantic hits to those whose text mentions the target year and July/effective language.
        """
        year = year or 2026
        year_s = str(year)
        queries = [
            query,
            f"Virginia uncodified act {year} chapter effective",
            f"Virginia Code effective July 1 {year}",
            f"Va. Acts {year}",
            f"enactment effective date {year} Virginia",
        ]
        raw: List[Dict] = []
        seen: set = set()
        for q in queries[:5]:
            batch = await self.search_fast(q, n_results=n_results, use_synonyms=False)
            for hit in batch:
                hid = hit.get("id")
                if hid and hid not in seen:
                    seen.add(hid)
                    raw.append(hit)

        july_re = re.compile(rf"july\s*1[,]?\s*{year_s}", re.I)
        effective_re = re.compile(
            rf"(effective|shall take effect|becomes effective).{{0,80}}{year_s}|{year_s}.{{0,80}}(effective|take effect)",
            re.I | re.DOTALL,
        )

        def _relevant(hit: Dict) -> bool:
            text = (hit.get("text") or "").lower()
            meta = hit.get("metadata") or {}
            meta_year = str(meta.get("year") or "")
            if meta_year == year_s:
                return True
            if july_re.search(text):
                return True
            if effective_re.search(text):
                return True
            if f"acts {year_s}" in text or f"act of {year_s}" in text:
                return True
            return False

        filtered = [h for h in raw if _relevant(h)]
        if filtered:
            return filtered[:n_results]

        # Metadata-only match (e.g. uncodified act row for target year)
        year_meta = [
            h for h in raw
            if str((h.get("metadata") or {}).get("year") or "") == year_s
        ]
        if year_meta:
            return year_meta[:n_results]

        return []

    async def _find_relevant_case_context(self, query: str, max_cases: int = 3) -> List[Dict]:
        """
        Search case law to understand legal concepts and statutes referenced in user questions.

        This helps decipher what statute or legal principle the user is asking about by
        examining how cases interpret and apply legal concepts.

        Args:
            query: User question
            max_cases: Maximum cases to return

        Returns:
            List of relevant case contexts with legal concepts
        """
        if not settings.SCENARIO_DB_ENABLED or getattr(settings, "CHAT_SKIP_CASE_CONTEXT", True):
            return []
        try:
            # Add timeout to prevent hanging - scenario service can be slow
            import asyncio
            self.logger.info(f"Searching for case context for query: {query[:100]}...")
            start_time = time.time()
            
            # Search for similar cases that might explain the legal concept
            # Use timeout to prevent hanging (5 seconds max)
            try:
                similar_cases = await asyncio.wait_for(
                    scenario_service.find_similar_scenarios(
                        query_facts=query,
                        n_results=max_cases
                    ),
                    timeout=5.0  # 5 second timeout
                )
                elapsed = time.time() - start_time
                self.logger.info(f"Case context search completed in {elapsed:.2f}s, found {len(similar_cases)} cases")
            except asyncio.TimeoutError:
                self.logger.warning(f"Case context search timed out after 5s, skipping case context")
                return []  # Return empty list if timeout

            case_contexts = []
            for case in similar_cases:
                # Extract legal concepts from case metadata and content
                case_data = {
                    "case_id": case.get("id", ""),
                    "case_type": case.get("case_type", "Unknown"),
                    "jurisdiction": case.get("jurisdiction", "Unknown"),
                    "court_level": case.get("court_level", "Unknown"),
                    "outcome": case.get("outcome", "Unknown"),
                    "citation": case.get("citation", ""),
                    "similarity_score": case.get("similarity_score", 0),
                    "key_facts": case.get("text", "")[:500] if case.get("text") else "",
                    "legal_concepts": self._extract_legal_concepts_from_case(case)
                }
                case_contexts.append(case_data)

            return case_contexts

        except Exception as e:
            self.logger.warning(f"Could not retrieve case context: {e}")
            return []

    def _extract_legal_concepts_from_case(self, case: Dict) -> List[str]:
        """
        Extract legal concepts, statutes, and principles from a case.

        Args:
            case: Case data dictionary

        Returns:
            List of legal concepts found in the case
        """
        concepts = []
        text = case.get("text", "").lower()
        metadata = case.get("metadata", {})

        # Check for specific statutes
        statute_patterns = [
            r"§\s*\d+\.\d+-\d+",  # § X.X-XX format
            r"virginia code §*\s*\d+\.\d+-\d+",  # Virginia Code references
            r"18\.2-\d+",  # Criminal code sections
            r"19\.2-\d+",  # Criminal procedure
            r"8\.01-\d+",  # Civil procedure
        ]

        for pattern in statute_patterns:
            matches = re.findall(pattern, text)
            concepts.extend(matches)

        # Check for legal concepts
        legal_concepts = [
            "assault", "battery", "domestic violence", "family abuse",
            "probable cause", "reasonable suspicion", "due process",
            "equal protection", "first amendment", "fourth amendment",
            "fifth amendment", "sixth amendment", "fourteenth amendment",
            "standing", "jurisdiction", "venue", "mootness", "ripeness",
            "statute of limitations", "sovereign immunity", "qualified immunity",
            "exclusionary rule", "fruit of the poisonous tree", "miranda",
            "plea bargain", "sentencing", "parole", "probation"
        ]

        for concept in legal_concepts:
            if concept in text:
                concepts.append(concept)

        # Add case type and jurisdiction context
        case_type = metadata.get("case_type", "")
        jurisdiction = metadata.get("jurisdiction", "")
        if case_type:
            concepts.append(f"case_type:{case_type}")
        if jurisdiction:
            concepts.append(f"jurisdiction:{jurisdiction}")

        return list(set(concepts))  # Remove duplicates

    async def search_with_case_context(self, query: str, n_results: int = 5, use_synonyms: bool = True) -> Dict:
        """
        Enhanced search that combines statute search with case law context.

        This provides a more complete understanding by:
        1. Finding relevant statutes (existing functionality)
        2. Finding relevant case law to understand legal concepts
        3. Using case precedents to help interpret statutes

        Args:
            query: User question
            n_results: Number of statute results to return
            use_synonyms: Whether to expand query with synonyms

        Returns:
            Dict with statutes, case_context, and combined insights
        """
        self.logger.info(f"[RAG] Starting search_with_case_context for: {query[:100]}...")
        start_time = time.time()
        
        # Get statute results (existing functionality)
        self.logger.info(f"[RAG] Step 1: Searching statutes (n_results={n_results})...")
        statute_start = time.time()
        statute_results = await self.search(query, n_results, use_synonyms=use_synonyms)
        statute_elapsed = time.time() - statute_start
        self.logger.info(f"[RAG] Step 1 complete: Found {len(statute_results)} statutes in {statute_elapsed:.2f}s")

        # Get case law context
        self.logger.info(f"[RAG] Step 2: Searching case context...")
        case_start = time.time()
        case_contexts = await self._find_relevant_case_context(query, max_cases=5)
        case_elapsed = time.time() - case_start
        self.logger.info(f"[RAG] Step 2 complete: Found {len(case_contexts)} case contexts in {case_elapsed:.2f}s")

        # Extract legal concepts from both sources
        all_legal_concepts = set()

        # From statutes
        for result in statute_results:
            text = result.get("text", "")
            concepts = self._extract_legal_concepts_from_text(text)
            all_legal_concepts.update(concepts)

        # From cases
        for case in case_contexts:
            all_legal_concepts.update(case.get("legal_concepts", []))

        # Generate insights about what statute the user might be referencing
        statute_references = self._analyze_statute_references(query, statute_results, case_contexts)

        # Find related statutes for any primary statutes found
        primary_statutes_found = self._find_statute_relationships_in_results(statute_results)
        related_statutes = {}

        for primary_citation in primary_statutes_found:
            related = self._get_related_statutes(primary_citation)
            if related:
                related_statutes[primary_citation] = related

        # === ADDED FOR COMPATIBILITY WITH CHAT ROUTE ===
        # Calculate verification metrics similar to search_comprehensive
        authoritative_sources = []
        secondary_sources = []
        source_groups = {}
        
        for result in statute_results:
            source = result['metadata'].get('source', 'Unknown')
            jurisdiction = result['metadata'].get('jurisdiction', 'Unknown')
            key = f"{source}_{jurisdiction}"
            priority = self._get_source_priority(source)
            
            if key not in source_groups:
                source_groups[key] = {
                    'source': source,
                    'jurisdiction': jurisdiction,
                    'priority': priority,
                    'results': []
                }
            source_groups[key]['results'].append(result)
            
        # Split into auth/secondary groups
        for key, group in source_groups.items():
            if group['priority'] <= 2:
                authoritative_sources.append(group)
            else:
                secondary_sources.append(group)
                
        # Determine status
        verification_status = 'verified' if len(authoritative_sources) >= 2 else 'unverified'
        
        # Create conflicts list
        conflicts = []
        if len(authoritative_sources) < 2:
            conflicts.append({
                'type': 'insufficient_sources',
                'message': f'Only found {len(authoritative_sources)} authoritative source(s)',
                'severity': 'warning'
            })

        return {
            "statute_results": statute_results,
            "results": statute_results,  # Alias
            "case_contexts": case_contexts,
            "legal_concepts": list(all_legal_concepts),
            "statute_references": statute_references,
            "related_statutes": related_statutes,
            "query_analysis": self._analyze_query_intent(query, statute_results, case_contexts),
            
            # Metadata fields expected by chat route
            "verification_status": verification_status,
            "authoritative_sources": authoritative_sources,
            "secondary_sources": secondary_sources,
            "conflicts": conflicts,
            "total_results": len(statute_results),
            "unique_sources": len(source_groups),
            "query_variations": [query]  # Basic implementation for compatibility
        }

    def _extract_legal_concepts_from_text(self, text: str) -> List[str]:
        """Extract legal concepts from statute text"""
        concepts = []
        text_lower = text.lower()

        # Statute references
        statute_matches = re.findall(r"§\s*\d+\.\d+-\d+", text)
        concepts.extend(statute_matches)

        # Legal terms
        legal_terms = [
            "assault", "battery", "felony", "misdemeanor", "penalty",
            "guilty", "conviction", "sentence", "probation", "jail",
            "prison", "fine", "restitution", "community service"
        ]

        for term in legal_terms:
            if term in text_lower:
                concepts.append(term)

        return concepts

    def _analyze_statute_references(self, query: str, statutes: List[Dict], cases: List[Dict]) -> Dict:
        """Analyze what statutes the user might be referencing based on context"""
        query_lower = query.lower()

        # Find statutes that appear in both search results and case law
        statute_mentions = {}
        for statute in statutes:
            statute_text = statute.get("text", "")
            statute_citations = re.findall(r"§\s*\d+\.\d+-\d+", statute_text)
            for citation in statute_citations:
                statute_mentions[citation] = statute_mentions.get(citation, 0) + 1

        # Find statutes mentioned in case law
        case_statute_mentions = {}
        for case in cases:
            case_text = case.get("key_facts", "")
            statute_citations = re.findall(r"§\s*\d+\.\d+-\d+", case_text)
            for citation in statute_citations:
                case_statute_mentions[citation] = case_statute_mentions.get(citation, 0) + 1

        # Cross-reference
        common_statutes = set(statute_mentions.keys()) & set(case_statute_mentions.keys())

        return {
            "primary_statutes": list(statute_mentions.keys()),
            "case_referenced_statutes": list(case_statute_mentions.keys()),
            "common_statutes": list(common_statutes),
            "statute_frequency": {**statute_mentions, **case_statute_mentions}
        }

    def _get_related_statutes(self, primary_statute_citation: str) -> Dict:
        """
        Get all related statutes for a primary statute citation.

        Args:
            primary_statute_citation: Statute citation (e.g., "18.2-57.2")

        Returns:
            Dict with related statutes organized by category
        """
        if primary_statute_citation in self.STATUTE_RELATIONSHIPS:
            return self.STATUTE_RELATIONSHIPS[primary_statute_citation]
        return {}

    def _find_statute_relationships_in_results(self, search_results: List[Dict]) -> List[str]:
        """
        Find which primary statutes from our relationships registry appear in search results.
        
        Args:
            search_results: List of statute search results
            
        Returns:
            List of primary statute citations that were found
        """
        found_primary_statutes = []
        
        for result in search_results:
            text = result.get("text", "")
            # Look for statute citations in the result text
            # Capture the number part from various formats:
            # § 18.2-57.2, Section 18.2-57.2, 18.2-57.2
            citations = re.findall(r'(?:§\s*|Section\s+|Code\s+)?(\d{1,2}\.\d+-\d+(?:\.\d+)?)', text)
            
            for citation in citations:
                # citation is now just the number part (e.g., "18.2-57.2")
                if citation in self.STATUTE_RELATIONSHIPS:
                    found_primary_statutes.append(citation)
                    
        return list(set(found_primary_statutes))  # Remove duplicates

    def _analyze_query_intent(self, query: str, statutes: List[Dict], cases: List[Dict]) -> Dict:
        """Analyze what the user is likely asking about"""
        query_lower = query.lower()

        intent_indicators = {
            "statute_lookup": ["what is the code", "what statute", "what law", "virginia code", "section"],
            "elements_analysis": ["elements", "requirements", "must prove", "burden of proof", "prove that"],
            "case_research": ["case", "precedent", "court", "ruling", "decision", "held that"],
            "penalty_inquiry": ["penalty", "punishment", "sentence", "jail", "fine", "misdemeanor", "felony"],
            "procedure": ["how to", "procedure", "process", "file", "motion", "hearing"]
        }

        detected_intents = []
        for intent, keywords in intent_indicators.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_intents.append(intent)

        # Analyze most relevant statutes based on case law context
        relevant_statutes = []
        for statute in statutes:
            statute_text = statute.get("text", "").lower()
            relevance_score = 0

            # Boost relevance if statute appears in case law
            statute_citations = re.findall(r"§\s*\d+\.\d+-\d+", statute.get("text", ""))
            for citation in statute_citations:
                if any(citation in case.get("key_facts", "") for case in cases):
                    relevance_score += 2

            # Boost based on query keywords
            for intent in detected_intents:
                if intent == "statute_lookup" and any(word in statute_text for word in ["assault", "battery", "domestic"]):
                    relevance_score += 1
                elif intent == "penalty_inquiry" and "penalty" in statute_text:
                    relevance_score += 1

            relevant_statutes.append({
                "statute": statute,
                "relevance_score": relevance_score
            })

        # Sort by relevance
        relevant_statutes.sort(key=lambda x: x["relevance_score"], reverse=True)

        return {
            "detected_intents": detected_intents,
            "most_relevant_statutes": [s["statute"] for s in relevant_statutes[:3]],
            "case_context_available": len(cases) > 0,
            "statute_case_connections": len([s for s in relevant_statutes if s["relevance_score"] > 0])
        }

    async def _search_with_variations(self, query_variations: List[str], n_results: int, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Search using multiple query variations and combine/deduplicate results.
        Variations run in parallel (bounded) to reduce chat latency.
        """
        all_results: List[Dict] = []
        seen_ids: set = set()
        has_citation_in_variations = any(self._extract_citation(var) for var in query_variations)
        citation_matches: List[str] = []
        merge_lock = asyncio.Lock()

        async def _search_one(query_var: str) -> None:
            embed_svc = _get_embedding_service()
            query_embedding = await embed_svc.embed(query_var)
            raw = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results * 2, 20),
                where=filters if filters else None,
            )
            ids = raw.get("ids", [[]])[0]
            docs = raw.get("documents", [[]])[0]
            metas = raw.get("metadatas", [[]])[0]
            dists = raw.get("distances", [[]])[0] if raw.get("distances") else []
            local_hits: List[Dict] = []
            for i in range(len(ids)):
                doc_id = ids[i]
                meta = metas[i] or {}
                source_name = meta.get("source", "")
                priority = self._get_source_priority(source_name)
                dist = dists[i] if i < len(dists) else None
                text = docs[i]
                priority_score = priority
                source_upper = source_name.upper()
                case_name_upper = (meta.get("case_name", "") or "").upper()
                jurisdiction = meta.get("jurisdiction", "")
                content_type = meta.get("content_type", "")
                scotus_indicators = [
                    "SCOTUS", "SUPREME COURT", "SUPREME COURT OF THE UNITED STATES",
                    "U.S. SUPREME COURT", "US SUPREME COURT", "UNITED STATES SUPREME COURT",
                    "SCOTUS OPINIONS", "SCOTUS_OPINIONS",
                ]
                is_scotus = any(ind in source_upper for ind in scotus_indicators)
                if not is_scotus:
                    is_scotus = any(ind in case_name_upper for ind in scotus_indicators)
                if not is_scotus and jurisdiction == "Federal" and content_type == "case_law":
                    is_scotus = True
                if is_scotus:
                    priority_score = -100
                    if dist is not None:
                        dist = dist * 0.1
                if has_citation_in_variations:
                    citation_in_text = self._extract_citation(text)
                    if citation_in_text:
                        priority_score -= 3
                statute_patterns = [
                    r"§\s*\d+\.\d+-\d+\.",
                    r"is guilty of",
                    r"shall be punished",
                    r"Any person who",
                    r"commits an assault",
                    r"family or household member",
                ]
                statute_content_boost = sum(
                    1 for p in statute_patterns if re.search(p, text, re.IGNORECASE)
                )
                if statute_content_boost > 0:
                    priority_score -= statute_content_boost
                title_page_indicators = [
                    "LIS", "Session Information", "Bills & Resolutions",
                    "State Budget", "Virginia Law", "Reports to the General Assembly",
                    "Code of Virginia - Title", "Chapter 1. Code of Virginia",
                ]
                title_penalty = sum(1 for ind in title_page_indicators if ind in text)
                if title_penalty > 0:
                    priority_score += title_penalty
                local_hits.append({
                    "id": doc_id,
                    "text": text,
                    "metadata": meta,
                    "distance": dist,
                    "priority": priority_score,
                    "matched_query": query_var,
                    "_citation_boost": bool(
                        has_citation_in_variations and self._extract_citation(text)
                    ),
                })
            async with merge_lock:
                for hit in local_hits:
                    doc_id = hit["id"]
                    if doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)
                    if hit.pop("_citation_boost", False) and doc_id not in citation_matches:
                        citation_matches.append(doc_id)
                    all_results.append(hit)

        sem = asyncio.Semaphore(4)

        async def _bounded(q: str) -> None:
            async with sem:
                await _search_one(q)

        await asyncio.gather(*[_bounded(q) for q in query_variations])

        # === EXPLICITLY ADD MISSING CITATIONS ===
        # If we found citation-based queries but vector search didn't return the actual document,
        # force-fetch it and add it to results.
        if has_citation_in_variations:
            for var in query_variations:
                citation = self._extract_citation(var)
                if citation:
                    # Check if we already found this citation in vector results
                    already_found = False
                    for r in all_results:
                        if r['metadata'].get('citation') == citation:
                            already_found = True
                            # Ensure it has SUPER high priority if found
                            r['priority'] = -100
                            if r['id'] not in citation_matches:
                                citation_matches.append(r['id'])
                            break
                    
                    # If not found, force fetch it
                    if not already_found:
                        try:
                            exact_results = self.collection.get(where={"citation": citation}, limit=1)
                            if exact_results['ids']:
                                doc_id = exact_results['ids'][0]
                                if doc_id not in seen_ids:
                                    seen_ids.add(doc_id)
                                    all_results.append({
                                        "id": doc_id,
                                        "text": exact_results['documents'][0],
                                        "metadata": exact_results['metadatas'][0],
                                        "distance": 0.0,  # Perfect match
                                        "priority": -100  # Super high priority
                                    })
                                    # Add to citation matches so it sorts to top
                                    if doc_id not in citation_matches:
                                        citation_matches.append(doc_id)
                        except Exception as e:
                            self.logger.debug(f"Could not force-fetch citation {citation}: {e}")

        # Sort by enhanced priority score, then by distance
        all_results.sort(key=lambda x: (x.get('priority', 5), x.get('distance', 1e9) or 1e9))

        # If we found citation matches, ensure they appear first
        if citation_matches:
            citation_first = []
            others = []
            for r in all_results:
                if r['id'] in citation_matches:
                    citation_first.append(r)
                else:
                    others.append(r)
            all_results = citation_first + others

        # Return top n_results
        results = all_results[:n_results]

        # Remove the extra fields before returning
        for r in results:
            r.pop('priority', None)
            r.pop('matched_query', None)

        return results
    
    def __init__(self):
        # Lazy init to avoid startup failure if DB migrations change
        self.client = None
        self.collection = None
        self._catalog = None  # source name -> priority
        self._query_cache = {}
        self._cache_keys = []
        self._cache_capacity: int = getattr(settings, "RAG_QUERY_CACHE_SIZE", 256)
        self.logger = setup_logger("rag")
        
        # Load configuration data
        self.LEGAL_SYNONYMS = {}
        self.STATUTE_RELATIONSHIPS = {}
        self._load_config_data()

    def _load_config_data(self):
        """Load synonyms and relationships from config files"""
        try:
            synonyms_path = Path(__file__).parent.parent.parent / "config" / "legal_synonyms.json"
            if synonyms_path.exists():
                self.LEGAL_SYNONYMS = json.loads(synonyms_path.read_text(encoding='utf-8'))
            else:
                self.logger.warning("legal_synonyms.json not found")
        except Exception as e:
            self.logger.error(f"Error loading synonyms: {e}")

        try:
            relationships_path = Path(__file__).parent.parent.parent / "config" / "statute_relationships.json"
            if relationships_path.exists():
                self.STATUTE_RELATIONSHIPS = json.loads(relationships_path.read_text(encoding='utf-8'))
            else:
                self.logger.warning("statute_relationships.json not found")
        except Exception as e:
            self.logger.error(f"Error loading statute relationships: {e}")

    def _ensure_initialized(self):
        if self.collection is not None:
            return
        
        # Suppress ChromaDB "Add of existing embedding ID" noise
        logging.getLogger("chromadb").setLevel(logging.ERROR)
        
        if self.client is None:
            self.client = chromadb.PersistentClient(
                path=settings.CHROMA_DB_PATH,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        try:
            self.collection = self.client.get_or_create_collection(
                name="legal_corpus",
                metadata={"description": "Virginia and Federal legal corpus"}
            )
        except Exception as e:
            # Create a fresh collection if schema mismatch occurs
            try:
                self.client.delete_collection("legal_corpus")
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(
                name="legal_corpus",
                metadata={"description": "Virginia and Federal legal corpus"}
            )
        # Load Source Catalog priorities
        try:
            if self._catalog is None:
                path = Path(__file__).parent.parent.parent / "config" / "source_catalog.json"
                data = json.loads(path.read_text(encoding='utf-8'))
                mapping = {}
                for s in data.get("sources", []):
                    mapping[s.get("name", s.get("id", ""))] = int(s.get("priority", 5))
                self._catalog = mapping
        except Exception:
            self._catalog = {}

    def _collection_count(self) -> int:
        """
        Return number of rows without loading all IDs into SQLite IN-clauses.
        Unbounded collection.get() triggers: too many SQL variables on large corpora.
        """
        self._ensure_initialized()
        try:
            return int(self.collection.count())
        except Exception as e:
            self.logger.warning(f"collection.count() failed ({e}); batched fallback")
            total = 0
            batch = 400
            offset = 0
            while True:
                part = self.collection.get(limit=batch, offset=offset, include=[])
                ids = part.get("ids") or []
                total += len(ids)
                if len(ids) < batch:
                    break
                offset += batch
            return total

    def _get_source_priority(self, source_name: str) -> int:
        """
        Get source priority with robust matching (case-insensitive, partial matching)
        
        This ensures that sources are correctly identified as authoritative even if:
        - Source names have slight variations
        - Case differences exist
        - Additional text is appended (e.g., "Code of Virginia § 46.2-391")
        
        Args:
            source_name: Source name from document metadata
            
        Returns:
            Priority value (1-5, where 1-2 are authoritative, 5 is default/secondary)
        """
        if not source_name:
            return 5  # Default to secondary
        
        # CRITICAL: SCOTUS gets highest priority (1) per AI Laws hierarchy
        # Check multiple variations of SCOTUS references
        source_upper = source_name.upper()
        scotus_indicators = [
            'SCOTUS',
            'SUPREME COURT',
            'SUPREME COURT OF THE UNITED STATES',
            'U.S. SUPREME COURT',
            'US SUPREME COURT',
            'UNITED STATES SUPREME COURT',
            'SCOTUS OPINIONS',
            'SCOTUS_OPINIONS'
        ]
        
        for indicator in scotus_indicators:
            if indicator in source_upper:
                return 1  # Highest priority for SCOTUS
        
        if not self._catalog:
            return 5  # Default to secondary
        
        # Try exact match first (most common case)
        priority = self._catalog.get(source_name, 5)
        if priority != 5:
            return priority
        
        # Try case-insensitive match
        for catalog_name, catalog_priority in self._catalog.items():
            if catalog_name.lower() == source_name.lower():
                return catalog_priority
        
        # Try partial match (e.g., "Code of Virginia" matches "Code of Virginia § 46.2-391")
        for catalog_name, catalog_priority in self._catalog.items():
            if catalog_name.lower() in source_name.lower() or source_name.lower() in catalog_name.lower():
                return catalog_priority
        
        # No match found - default to secondary
        return 5

    def get_chunks_for_sources(self, sources: List[str], limit: int = 80) -> List[Dict]:
        """
        Fetch indexed chunks by upload filename(s). Does not use embeddings—reliable right after upload.
        Matches metadata ``source`` or ``original_filename`` (same value on ingest).
        """
        self._ensure_initialized()
        if not sources:
            return []
        names = list(dict.fromkeys(s.strip() for s in sources if s and str(s).strip()))
        if not names:
            return []
        try:
            res = self.collection.get(
                where={
                    "$or": [
                        {"source": {"$in": names}},
                        {"original_filename": {"$in": names}},
                    ]
                },
                limit=limit,
            )
        except Exception as e:
            self.logger.warning(f"get_chunks_for_sources $or failed, retrying source-only: {e}")
            try:
                res = self.collection.get(where={"source": {"$in": names}}, limit=limit)
            except Exception as e2:
                self.logger.warning(f"get_chunks_for_sources failed for {names}: {e2}")
                return []

        ids = res.get("ids") or []
        docs = res.get("documents") or []
        metas = res.get("metadatas") or []
        out: List[Dict] = []
        for i in range(len(ids)):
            text = (docs[i] if i < len(docs) else "") or ""
            text = text.strip()
            if not text:
                continue
            meta = metas[i] if i < len(metas) else {}
            out.append(
                {
                    "id": ids[i],
                    "text": text,
                    "metadata": meta or {},
                    "distance": None,
                }
            )
        return out
    
    async def add_document(self, text: str, metadata: Dict, doc_id: Optional[str] = None):
        """Add document to vector database with chunking for large documents"""
        self._ensure_initialized()
        
        # Extract citation from text if not already in metadata
        # This is critical for exact citation matching in searches
        if 'citation' not in metadata or not metadata.get('citation'):
            # Check if this is a SCOTUS/Federal case - use SCOTUS citation extraction
            jurisdiction = metadata.get('jurisdiction', '')
            source = metadata.get('source', '')
            is_scotus = jurisdiction == 'Federal' or 'SCOTUS' in str(source).upper()
            
            if is_scotus:
                # Extract SCOTUS citation (Bluebook format)
                extracted_citation = self._extract_scotus_citation_from_text(text)
            else:
                # Extract Virginia Code citation
                extracted_citation = self._extract_citation_from_text(text)
            
            if extracted_citation:
                metadata['citation'] = extracted_citation
                self.logger.debug(f"Extracted citation {extracted_citation} from document")

        metadata = _coerce_chroma_metadata(metadata)
        
        # Chunk large documents for better searchability (max 2000 chars per chunk)
        CHUNK_SIZE = 2000
        CHUNK_OVERLAP = 200

        resolved_doc_id = doc_id if doc_id else f"upload_{uuid.uuid4().hex}"
        
        if len(text) <= CHUNK_SIZE:
            # Small document - add as single chunk
            embed_svc = _get_embedding_service()
            embedding = await embed_svc.embed(text)
            self.collection.add(
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata],
                ids=[resolved_doc_id]
            )
        else:
            # Large document - split into chunks
            chunks = []
            start = 0
            chunk_num = 0
            
            while start < len(text):
                end = start + CHUNK_SIZE
                chunk = text[start:end]
                
                # Try to break at sentence boundary
                if end < len(text):
                    last_period = chunk.rfind('.')
                    last_newline = chunk.rfind('\n')
                    break_point = max(last_period, last_newline)
                    if break_point > CHUNK_SIZE * 0.7:  # Only break if we got at least 70% of chunk
                        chunk = text[start:start + break_point + 1]
                        end = start + break_point + 1
                
                chunks.append((chunk, start, end))
                start = end - CHUNK_OVERLAP  # Overlap for context
                chunk_num += 1
            
            # Generate embeddings for all chunks
            chunk_texts = [chunk[0] for chunk in chunks]
            embed_svc = _get_embedding_service()
            embeddings = await asyncio.gather(*[embed_svc.embed(chunk_text) for chunk_text in chunk_texts])
            
            # Add chunks to collection
            chunk_ids = []
            chunk_docs = []
            chunk_metas = []
            
            base_id = resolved_doc_id
            
            for i, (chunk_text, start_pos, end_pos) in enumerate(chunks):
                chunk_meta = _coerce_chroma_metadata({
                    **metadata,
                    "chunk_index": i,
                    "chunk_start": start_pos,
                    "chunk_end": end_pos,
                    "total_chunks": len(chunks),
                    "is_chunk": True,
                })
                
                chunk_ids.append(f"{base_id}_chunk_{i}")
                chunk_docs.append(chunk_text)
                chunk_metas.append(chunk_meta)
            
            self.collection.add(
                embeddings=embeddings,
                documents=chunk_docs,
                metadatas=chunk_metas,
                ids=chunk_ids
            )
    
    def _extract_citation(self, query: str) -> Optional[str]:
        """Extract Virginia Code or Virginia Administrative Code citation from query
        
        Virginia Code examples:
            "18.2-57.2" -> "§ 18.2-57.2"
            "va code 18.2-95" -> "§ 18.2-95"
            "§ 19.2-81" -> "§ 19.2-81"
        
        Virginia Administrative Code (VAC) examples:
            "18 VAC 120-10-10" -> "18 VAC 120-10-10"
            "VAC 18-120-10" -> "18 VAC 120-10"
        """
        # Check for VAC (Virginia Administrative Code) first - format: 18 VAC 120-10-10
        vac_patterns = [
            r'(\d+)\s*VAC\s*(\d+)[-.](\d+)[-.]?(\d*)',   # 18 VAC 120-10-10 or 18 VAC 120-10
            r'VAC\s*(\d+)[-.](\d+)[-.]?(\d*)',            # VAC 18-120-10
        ]
        for pattern in vac_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 4 and groups[3]:
                    return f"{groups[0]} VAC {groups[1]}-{groups[2]}-{groups[3]}"
                elif len(groups) == 4:
                    return f"{groups[0]} VAC {groups[1]}-{groups[2]}"
                elif len(groups) == 3:
                    # VAC 18-120-10 -> 18 VAC 120-10
                    return f"{groups[0]} VAC {groups[1]}-{groups[2]}" if groups[2] else f"{groups[0]} VAC {groups[1]}"
        
        # Virginia Code: title-section or title-section.subsection
        pattern = r'(\d+\.?\d*-\d+\.?\d*(?:\.\d+)?)'
        match = re.search(pattern, query)
        if match:
            citation = match.group(1)
            if not citation.startswith('§'):
                citation = f"§ {citation}"
            return citation
        return None
    
    def _extract_scotus_citation_from_text(self, text: str) -> Optional[str]:
        """
        Extract SCOTUS citation from text (Bluebook format).
        Format: [Volume] U.S. [Page] (e.g., "384 U.S. 436")
        """
        if not text or len(text) < 50:
            return None
        
        # Check first 10000 chars for citation (often in header/title)
        search_text = text[:10000] if len(text) > 10000 else text
        
        patterns = [
            r'(\d+)\s+U\.?\s*S\.?\s+(\d+)',      # 606 U.S. 748 or 606 U. S. 748
            r'(\d+)\s+U\.\s*S\.\s+(\d+)',        # 606 U. S. 748 (with spaces)
            r'(\d+)\s+S\.?\s*Ct\.?\s+(\d+)',     # 606 S. Ct. 748
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, search_text)
            for match in matches:
                volume = match.group(1)
                page = match.group(2)
                # Validate: volume should be reasonable (1-700+), page should be reasonable (1-2000+)
                try:
                    vol_num = int(volume)
                    page_num = int(page)
                    if 1 <= vol_num <= 700 and 1 <= page_num <= 2000:
                        # Return in Bluebook format
                        return f"{volume} U.S. {page}"
                except ValueError:
                    continue
        
        return None
    
    def _extract_citation_from_text(self, text: str) -> Optional[str]:
        """Extract primary Virginia Code citation from document text
        
        Looks for patterns like:
        - § 46.2-391
        - Section 46.2-391
        - Va. Code Ann. § 46.2-391
        - Code of Virginia § 46.2-391
        
        Returns the first citation found, normalized to '§ 46.2-391' format.
        Prioritizes citations that appear early in the document (likely the primary statute).
        
        Args:
            text: Document text to search for citations
            
        Returns:
            Normalized citation string (e.g., "§ 46.2-391") or None if not found
        """
        if not text or len(text) < 50:
            return None
        
        search_text = text[:2000] if len(text) > 2000 else text
        
        # VAC (Virginia Administrative Code) patterns first - for regulations
        vac_patterns = [
            r'(\d+)\s*VAC\s*(\d+)[-.](\d+)[-.]?(\d*)',   # 18 VAC 120-10-10
            r'Virginia\s+Administrative\s+Code\s+(\d+)\s*VAC\s*(\d+)[-.](\d+)',
        ]
        for pattern in vac_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 3:
                    if len(groups) == 4 and groups[3]:
                        return f"{groups[0]} VAC {groups[1]}-{groups[2]}-{groups[3]}"
                    return f"{groups[0]} VAC {groups[1]}-{groups[2]}"
        
        # Virginia Code patterns
        patterns = [
            (r'§\s*(\d+\.?\d*-\d+\.?\d*(?:\.\d+)?)', 'explicit'),  # § 46.2-391
            (r'Section\s+(\d+\.?\d*-\d+\.?\d*(?:\.\d+)?)', 'section'),  # Section 46.2-391
            (r'Va\.?\s*Code\s+(?:Ann\.?)?\s*§\s*(\d+\.?\d*-\d+\.?\d*(?:\.\d+)?)', 'va_code'),  # Va. Code Ann. § 46.2-391
            (r'Code\s+of\s+Virginia\s+§\s*(\d+\.?\d*-\d+\.?\d*(?:\.\d+)?)', 'code_of_va'),  # Code of Virginia § 46.2-391
        ]
        
        # Try Virginia Code patterns
        for pattern, _ in patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                citation = match.group(1)
                # Normalize to include § symbol
                if not citation.startswith('§'):
                    citation = f"§ {citation}"
                return citation
        
        # Fallback: look for just the number pattern in the first 500 chars (less reliable)
        # This catches cases where the format is unusual
        fallback_pattern = r'(\d+\.?\d*-\d+\.?\d*(?:\.\d+)?)'
        fallback_text = text[:500] if len(text) > 500 else text
        match = re.search(fallback_pattern, fallback_text)
        if match:
            citation = match.group(1)
            # Only use fallback if it looks like a Virginia Code citation (title.section format)
            if '.' in citation and '-' in citation:
                if not citation.startswith('§'):
                    citation = f"§ {citation}"
                return citation
        
        return None
    
    async def search(self, query: str, n_results: int = 5, filters: Optional[Dict] = None, use_synonyms: bool = True) -> List[Dict]:
        """Search for relevant documents with automatic legal terminology expansion
        
        Args:
            query: Search query
            n_results: Number of results to return. If 0, returns all available results (up to 1000).
            filters: Optional metadata filters
            use_synonyms: Whether to expand query with legal terminology synonyms (default True)
        """
        self._ensure_initialized()
        # Handle "no limit" case (0 means return all)
        if n_results == 0:
            n_results = 1000  # Large number to get all results
        
        # === SYNONYM EXPANSION ===
        # Expand query to include Virginia Code legal terminology
        if use_synonyms:
            query_variations = self._expand_query_with_synonyms(query)
            if len(query_variations) > 1:
                self.logger.debug(f"Expanded query into {len(query_variations)} variations")
                # Search with all variations and combine results
                return await self._search_with_variations(query_variations, n_results, filters)
        
        # === CITATION DETECTION AND EXACT MATCH ===
        # Check if query contains a Virginia Code citation
        citation = self._extract_citation(query)
        
        # Do not short-circuit into statute-only retrieval when caller passed metadata filters
        # (e.g. chat attachment workflow: source $in filenames).
        if citation and filters is None:
            self.logger.info(f"Citation detected in query: {citation}")
            # Try exact metadata filter first for citation queries
            try:
                # Search with citation filter - ChromaDB uses where clause
                exact_results = self.collection.get(
                    where={"citation": citation},
                    limit=1
                )
                
                if exact_results['ids']:
                    self.logger.info(f"Exact match found for {citation}. Returning match ONLY to prevent noise.")
                    # Found exact match! Return it as top result
                    doc_id = exact_results['ids'][0]
                    doc_text = exact_results['documents'][0]
                    doc_meta = exact_results['metadatas'][0]
                    
                    # STRICT MODE: If we found the exact statute the user asked for (or was translated to),
                    # we prioritize it 100%. We do NOT mix in random semantic matches which might dilute it.
                    # We ONLY add related statutes if they exist in our relationships map.
                    
                    results = [{
                        "id": doc_id,
                        "text": doc_text,
                        "metadata": doc_meta,
                        "distance": 0.0,  # Perfect match
                        "is_exact_match": True  # NEW TAG
                    }]
                    
                    # Add related statutes if known
                    # This handles the "Collateral Consequences" requirement without relying on vector search luck
                    related_map = self.STATUTE_RELATIONSHIPS.get(citation.replace("§ ", ""), {})
                    if related_map:
                        # TODO: Fetch related statutes by ID
                        pass
                        
                    return results
            except Exception as e:
                # If exact match fails, fall through to semantic search
                # Log error but don't fail completely
                self.logger.debug(f"Citation exact match failed for {citation}: {e}")
                pass
        
        # === STANDARD SEMANTIC SEARCH ===
        # Cache (must include filters—otherwise filtered attachment searches reuse wrong results)
        filter_key = json.dumps(filters, sort_keys=True, default=str) if filters else ""
        cache_key = f"{query}::{n_results}::{filter_key}"
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]
        # Generate query embedding
        embed_svc = _get_embedding_service()
        query_embedding = await embed_svc.embed(query)
        
        # Search collection - request at least n_results, but ChromaDB may return more
        # We'll limit after scoring
        raw = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=max(n_results, 10),
            where=filters if filters else None
        )
        
        # Format results
        formatted_results = []
        ids = raw.get('ids', [[]])[0]
        docs = raw.get('documents', [[]])[0]
        metas = raw.get('metadatas', [[]])[0]
        dists = raw.get('distances', [[]])[0] if raw.get('distances') else []
        scored = []
        for i in range(len(ids)):
            meta = metas[i] or {}
            source_name = meta.get('source', '').upper()
            jurisdiction = meta.get('jurisdiction', '')
            content_type = meta.get('content_type', '')
            case_name = meta.get('case_name', '').upper()
            priority = self._get_source_priority(meta.get('source', ''))
            
            # CRITICAL: Boost SCOTUS/Federal case law per AI Laws hierarchy
            # SCOTUS is #1: "United States Constitution and U.S. Supreme Court precedent (binding on all jurisdictions)"
            # Check multiple variations of SCOTUS references
            is_scotus = False
            scotus_indicators = [
                'SCOTUS',
                'SUPREME COURT',
                'SUPREME COURT OF THE UNITED STATES',
                'U.S. SUPREME COURT',
                'US SUPREME COURT',
                'UNITED STATES SUPREME COURT',
                'SCOTUS OPINIONS',
                'SCOTUS_OPINIONS'
            ]
            
            # Check source name
            for indicator in scotus_indicators:
                if indicator in source_name:
                    is_scotus = True
                    break
            
            # Check case name (some cases might have SCOTUS in the name)
            if not is_scotus:
                for indicator in scotus_indicators:
                    if indicator in case_name:
                        is_scotus = True
                        break
            
            # Also check if it's Federal case law (SCOTUS is Federal)
            if not is_scotus and jurisdiction == 'Federal' and content_type == 'case_law':
                is_scotus = True
            
            if is_scotus:
                priority = -100  # Maximum priority boost (much lower number = much higher priority)
                # Also reduce distance significantly to boost ranking
                if dist is not None:
                    dist = dist * 0.1  # Make SCOTUS cases appear 10x closer in semantic space
                self.logger.debug(f"Maximum boost applied to SCOTUS/Federal case: {meta.get('source', 'Unknown')}")
            
            dist = dists[i] if i < len(dists) else None
            # For SCOTUS, we already adjusted dist above, so use the adjusted value
            score = (priority, dist if dist is not None else 1e9, i)
            scored.append((score, ids[i], docs[i], meta, dist))
        scored.sort(key=lambda x: x[0])
        # If n_results was 0 (now 1000), return all scored results, otherwise limit
        top = scored if n_results >= 1000 else scored[:n_results]
        for _, _id, text, meta, dist in top:
            formatted_results.append({
                "id": _id,
                "text": text,
                "metadata": meta,
                "distance": dist
            })
        # Cache store
        try:
            self._query_cache[cache_key] = formatted_results
            self._cache_keys.append(cache_key)
            if len(self._cache_keys) > self._cache_capacity:
                old = self._cache_keys.pop(0)
                self._query_cache.pop(old, None)
        except Exception:
            pass
        
        return formatted_results
    
    async def get_context(self, query: str, n_results: int = 5, context_chars: Optional[int] = None) -> str:
        """Get formatted context string for RAG with configurable truncation
        
        Args:
            query: Search query
            n_results: Number of results to include
            context_chars: Max chars per source (None = no truncation)
        """
        results = await self.search(query, n_results)
        
        if not results:
            return "No relevant legal authority found."
        
        context_parts = []
        for i, result in enumerate(results, 1):
            source = result['metadata'].get('source', 'Unknown')
            jurisdiction = result['metadata'].get('jurisdiction', 'Unknown')
            text = result['text']
            
            # Apply truncation if specified
            if context_chars and len(text) > context_chars:
                text = text[:context_chars] + "..."
            
            context_parts.append(
                f"[{i}] Source: {source} ({jurisdiction})\n{text}"
            )
        
        return "\n\n".join(context_parts)
    
    # Core laws: system-ingested statutes/case law that must not be deleted or overwritten.
    # Documents matching these sources or doc_id prefix are read-only for the UI/API.
    CORE_LAW_DOC_ID_PREFIX = "va_code_"
    CORE_LAW_SOURCE_NAMES = frozenset([
        "code of virginia", "va code", "virginia code",
        "virginia uncodified acts", "uncodified",
        "scotus opinions", "scotus portal", "supreme court of the united states",
        "virginia administrative code", "va admin code", "va register",
        "virginia courts", "virginia courts opinions portal", "va opinions",
        "united states code", "us code", "us code olrc", "us code govinfo", "u.s. code",
        "code of federal regulations", "cfr", "ecfr",
        "federal register", "us courts rules", "scotus",
    ])
    
    def _is_core_laws_document(self, doc_id: str, metadata: Optional[Dict] = None) -> bool:
        """Return True if this doc is part of the system's core laws (not user uploads)."""
        if not doc_id:
            return False
        if doc_id.startswith(self.CORE_LAW_DOC_ID_PREFIX):
            return True
        if metadata:
            source = (metadata.get("source") or "").strip().lower()
            if source and any(core in source for core in self.CORE_LAW_SOURCE_NAMES):
                return True
        return False
    
    def get_collection_stats(self) -> Dict:
        """Get statistics about the corpus"""
        self._ensure_initialized()
        return {
            "total_documents": self._collection_count(),
            "collection_name": "legal_corpus"
        }

    def list_documents(self, matter_id: Optional[str] = None) -> List[Dict]:
        """
        List indexed documents (deduplicated by base doc_id; chunks grouped).
        Optionally filter by matter_id (metadata field set on upload).
        """
        self._ensure_initialized()
        seen_base: Dict[str, Dict] = {}
        batch_size = 400
        offset = 0
        while True:
            data = self.collection.get(
                limit=batch_size,
                offset=offset,
                include=["metadatas"],
            )
            ids_list = data.get("ids") or []
            metadatas_list = data.get("metadatas") or []
            if not ids_list:
                break
            for i, doc_id in enumerate(ids_list):
                base_id = doc_id.split("_chunk_")[0] if "_chunk_" in doc_id else doc_id
                if base_id in seen_base:
                    continue
                meta = (metadatas_list[i] or {}) if i < len(metadatas_list) else {}
                if matter_id is not None:
                    mid = meta.get("matter_id")
                    if mid is not None and str(mid) != str(matter_id):
                        continue
                seen_base[base_id] = {
                    "doc_id": base_id,
                    "source": meta.get("source", ""),
                    "matter_id": meta.get("matter_id"),
                    "upload_date": meta.get("upload_date", ""),
                    "jurisdiction": meta.get("jurisdiction", ""),
                    "document_type": meta.get("document_type", ""),
                    "is_core": self._is_core_laws_document(base_id, meta),
                }
            offset += len(ids_list)
            if len(ids_list) < batch_size:
                break
        return list(seen_base.values())

    def _collect_ids_for_doc(self, doc_id: str) -> List[str]:
        """Return all collection ids for a base doc_id including chunk suffixes."""
        to_delete: List[str] = []
        batch_size = 400
        offset = 0
        while True:
            data = self.collection.get(
                limit=batch_size,
                offset=offset,
                include=[],
            )
            ids_list = data.get("ids") or []
            if not ids_list:
                break
            for rid in ids_list:
                if rid == doc_id or rid.startswith(doc_id + "_chunk_"):
                    to_delete.append(rid)
            offset += len(ids_list)
            if len(ids_list) < batch_size:
                break
        return to_delete

    def _is_va_statute_document(self, doc_id: str, metadata: Optional[Dict]) -> bool:
        """True if document is Virginia Code corpus (CSV or legacy ingest)."""
        if doc_id.startswith(self.CORE_LAW_DOC_ID_PREFIX):
            return True
        if doc_id.startswith("va_uncodified_"):
            return True
        if not metadata:
            return False
        source = (metadata.get("source") or "").strip().lower()
        if source == "code of virginia":
            return True
        if source.startswith("code of virginia"):
            return True
        if "uncodified" in source or source == "virginia uncodified acts":
            return True
        return False

    def purge_va_statutes(self) -> int:
        """
        Remove all Virginia Code statute documents from the vector DB.
        Used by scheduled corpus refresh (scripts/update_va_legal_corpus.py).
        """
        self._ensure_initialized()
        to_delete: List[str] = []
        batch_size = 400
        offset = 0
        while True:
            data = self.collection.get(
                limit=batch_size,
                offset=offset,
                include=["metadatas"],
            )
            ids_list = data.get("ids") or []
            metadatas_list = data.get("metadatas") or []
            if not ids_list:
                break
            for i, rid in enumerate(ids_list):
                meta = (metadatas_list[i] or {}) if i < len(metadatas_list) else {}
                if self._is_va_statute_document(rid, meta):
                    to_delete.append(rid)
            offset += len(ids_list)
            if len(ids_list) < batch_size:
                break
        if not to_delete:
            return 0
        step = 400
        for i in range(0, len(to_delete), step):
            self.collection.delete(ids=to_delete[i : i + step])
        self.logger.info(f"Purged {len(to_delete)} Virginia Code vectors for corpus refresh")
        return len(to_delete)

    async def upsert_document(self, text: str, metadata: Dict, doc_id: str) -> None:
        """Replace a document by doc_id (maintenance ingest; bypasses UI delete guard)."""
        self._ensure_initialized()
        existing = self._collect_ids_for_doc(doc_id)
        if existing:
            step = 400
            for i in range(0, len(existing), step):
                self.collection.delete(ids=existing[i : i + step])
        await self.add_document(text=text, metadata=metadata, doc_id=doc_id)

    def delete_document(self, doc_id: str) -> int:
        """
        Delete a document and all its chunks from the collection. Returns count of deleted ids.
        Core laws (system statutes/case law) cannot be deleted.
        """
        self._ensure_initialized()
        to_delete: List[str] = []
        first_meta: Optional[Dict] = None
        batch_size = 400
        offset = 0
        while True:
            data = self.collection.get(
                limit=batch_size,
                offset=offset,
                include=["metadatas"],
            )
            ids_list = data.get("ids") or []
            metadatas_list = data.get("metadatas") or []
            if not ids_list:
                break
            for i, rid in enumerate(ids_list):
                if rid == doc_id or rid.startswith(doc_id + "_chunk_"):
                    to_delete.append(rid)
                    if first_meta is None:
                        first_meta = (metadatas_list[i] or {}) if i < len(metadatas_list) else {}
            offset += len(ids_list)
            if len(ids_list) < batch_size:
                break
        if not to_delete:
            return 0
        # Check if this document is part of the system's core laws (do not allow delete)
        meta = first_meta or {}
        if self._is_core_laws_document(doc_id, meta):
            self.logger.warning(f"Blocked delete of core laws document: doc_id={doc_id}, source={meta.get('source')}")
            raise PermissionError(
                "Cannot delete: this document is part of the system's core laws. "
                "Only user-uploaded documents can be removed."
            )
        step = 400
        for i in range(0, len(to_delete), step):
            self.collection.delete(ids=to_delete[i : i + step])
        return len(to_delete)

    def _detect_specific_statute_request(self, query: str) -> Dict:
        """
        Detect if query is asking for a SPECIFIC statute vs general information
        Returns dict with specificity info
        """
        query_lower = query.lower()
        
        # Keywords that indicate specific statute requests
        specific_indicators = [
            "domestic", "aggravated", "simple", "felony", "misdemeanor",
            "first degree", "second degree", "third degree", "class a", "class b", "class c",
            "with intent", "without intent", "reckless", "knowing", "willful",
            "against", "upon", "involving", "related to"
        ]
        
        # Check for specific modifiers
        has_specific_modifier = any(indicator in query_lower for indicator in specific_indicators)
        
        # Check for code section references
        code_section_pattern = re.search(r'(\d+\.?\d*-\d+\.?\d*|\d+\.\d+\.\d+)', query)
        has_code_section = code_section_pattern is not None
        
        # Extract specific terms
        specific_terms = []
        for indicator in specific_indicators:
            if indicator in query_lower:
                specific_terms.append(indicator)
        
        return {
            "is_specific_request": has_specific_modifier or has_code_section,
            "specific_terms": specific_terms,
            "has_code_section": has_code_section,
            "code_section": code_section_pattern.group() if code_section_pattern else None
        }
    
    async def expand_query_concepts(self, query: str, exhaustive: bool = False) -> List[str]:
        """
        Expand a query into multiple legal concept variations
        to ensure all relevant sections are found
        PRESERVES SPECIFICITY - doesn't generalize specific requests
        
        Args:
            query: The search query
            exhaustive: If True, generate 10+ variations for trial prep
        """
        # Detect if this is a specific statute request
        specificity_info = self._detect_specific_statute_request(query)
        
        # Initial list of queries
        queries = [query]

        # NEW: Automatic Consequence Expansion
        # If the query seems to be about a crime/offense, add consequence searches
        crime_indicators = [
            "assault", "battery", "dui", "dwi", "theft", "fraud", "drug", "possession", 
            "felony", "misdemeanor", "crime", "offense", "charge", "arrest", "guilty",
            "conviction", "sentence", "penalty", "jail", "prison", "murder", "homicide",
            "robbery", "burglary", "larceny", "shoplifting", "weapon", "firearm", "gun"
        ]
        is_criminal_query = any(indicator in query.lower() for indicator in crime_indicators)

        if is_criminal_query:
            # Force the system to look for collateral consequences in the entire DB
            queries.append(f"collateral consequences of {query} conviction virginia")
            queries.append(f"firearm rights gun ban {query} virginia federal")
            queries.append(f"professional license suspension {query} virginia")
            queries.append(f"immigration consequences deportation {query}")
            queries.append(f"security clearance impact {query}")
            # Explicitly add "elements" search to differentiate definition from elements
            queries.append(f"elements of {query} must be proven by commonwealth")
            self.logger.info(f"Detected criminal query: Added {len(queries)-1} consequence search variations")
        
        # If specific request, prioritize exact matches
        if specificity_info["is_specific_request"]:
            # Keep original query first, then add variations that PRESERVE specificity
            queries = [query]  # Original query always first for exact match
            
            # Add variations that preserve specific terms
            if specificity_info["specific_terms"]:
                for term in specificity_info["specific_terms"]:
                    # Create variation that emphasizes the specific term
                    variation = f"{term} {query}"
                    if variation not in queries:
                        queries.append(variation)
            
            # Add code section search if detected
            if specificity_info["code_section"]:
                queries.append(f"Virginia Code {specificity_info['code_section']}")
            
            return queries
        
        # For general queries, use LLM expansion
        num_queries = "10-15" if exhaustive else "3-5"
        expansion_prompt = f"""Extract all legal concepts, statutes, regulations, and case law topics from this legal question. Generate {num_queries} specific search queries that would find ALL relevant legal sections:

Question: {query}

IMPORTANT: If the question asks for a SPECIFIC type (e.g., "domestic assault", "aggravated battery"), PRESERVE that specificity. Do NOT generalize to parent statutes.

Generate queries that cover:
1. Specific statutes or code sections mentioned (PRESERVE modifiers like "domestic", "aggravated", etc.)
2. Legal concepts and doctrines
3. Case law topics
4. Procedural rules
5. Related legal areas
{"6. Cross-jurisdictional parallels (federal vs state)" if exhaustive else ""}
{"7. Historical precedents and landmark cases" if exhaustive else ""}
{"8. Procedural and substantive law variations" if exhaustive else ""}

Return ONLY a JSON array of query strings, nothing else:"""
        
        try:
            response = await ollama_service.generate(
                prompt=expansion_prompt,
                system_prompt="You are a legal research assistant. Extract all legal concepts and generate comprehensive search queries."
            )
            # Try to parse JSON array from response
            # Extract JSON array from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                queries = json.loads(json_match.group())
                # Always include original query
                all_queries = [query] + queries
                return list(set(all_queries))  # Remove duplicates
        except Exception as e:
            self.logger.debug(f"Query expansion failed: {e}")
        
        # Fallback: return original query plus keyword variations
        return [query]

    async def search_comprehensive(
        self,
        query: str,
        n_results_per_query: int = 50,  # Increased default to get more results
        require_multiple_sources: bool = True,
        min_authoritative_sources: int = 2,
        exhaustive: bool = False  # NEW: Enable exhaustive trial prep mode
    ) -> Dict:
        """
        Comprehensive search that checks ALL relevant sections
        - Expands query into multiple concept variations
        - Searches each variation
        - Groups results by source
        - Verifies multiple authoritative sources agree
        - Detects conflicts
        
        In exhaustive mode (trial prep):
        - Generates 10+ query variations (vs 3-5)
        - Retrieves 200 results per query (vs 50)
        - Includes cross-jurisdictional search
        - Targets 500+ total sources
        """
        self._ensure_initialized()
        
        # Adjust parameters for exhaustive mode
        if exhaustive:
            n_results_per_query = 200  # Increase from 50 to 200
            self.logger.info("Exhaustive search mode enabled - targeting 500+ sources")
        
        # Step 1: Expand query into multiple legal concept variations
        query_variations = await self.expand_query_concepts(query, exhaustive=exhaustive)
        self.logger.debug(f"Expanded query into {len(query_variations)} variations")
        
        # Step 2: Search each query variation
        all_results = []
        seen_ids = set()
        
        for q_var in query_variations:
            results = await self.search(q_var, n_results_per_query)
            
            # Check if this query produced an exact match
            has_exact_match = any(r.get('is_exact_match', False) for r in results)
            
            if has_exact_match:
                self.logger.info(f"Exact match found in variation: '{q_var}'. Discarding fuzzy results.")
                # If exact match found, ONLY keep the exact matches from this result set
                # This prevents pollution from other "fuzzy" queries
                exact_results = [r for r in results if r.get('is_exact_match', False)]
                
                # Reset all_results to ONLY these exact matches
                all_results = exact_results
                seen_ids = {r['id'] for r in exact_results}
                break  # Stop searching other variations
                
            for result in results:
                if result['id'] not in seen_ids:
                    seen_ids.add(result['id'])
                    all_results.append(result)
        
        self.logger.debug(f"Found {len(all_results)} unique results across all query variations")
        
        # Step 3: Group results by source and jurisdiction
        source_groups = {}
        for result in all_results:
            source = result['metadata'].get('source', 'Unknown')
            jurisdiction = result['metadata'].get('jurisdiction', 'Unknown')
            key = f"{source}_{jurisdiction}"
            if key not in source_groups:
                priority = self._get_source_priority(source)
                source_groups[key] = {
                    'source': source,
                    'jurisdiction': jurisdiction,
                    'results': [],
                    'priority': priority
                }
            source_groups[key]['results'].append(result)
        
        # Step 4: Identify authoritative sources
        authoritative_sources = []
        secondary_sources = []
        
        for key, group in source_groups.items():
            priority = group['priority']
            if priority <= 2:  # Authoritative (priority 1-2)
                authoritative_sources.append(group)
            else:
                secondary_sources.append(group)
        
        # Step 5: Check for conflicts and verify agreement
        conflicts = []
        verification_status = 'unverified'
        
        # If we have at least one authoritative source, that's better than none
        # For exact citation matches, a single authoritative source is acceptable
        if len(authoritative_sources) == 0:
            # No authoritative sources found - this is a problem
            conflicts.append({
                'type': 'no_authoritative_sources',
                'message': f'No authoritative sources found. Only found {len(secondary_sources)} secondary source(s).',
                'severity': 'warning',
                'authoritative_sources': []
            })
        elif len(authoritative_sources) < min_authoritative_sources:
            # Have some authoritative sources but not enough for full verification
            source_names = [s['source'] for s in authoritative_sources]
            conflicts.append({
                'type': 'insufficient_sources',
                'message': f'Found {len(authoritative_sources)} authoritative source(s) ({", ".join(source_names)}), but {min_authoritative_sources} recommended for full verification',
                'severity': 'warning',
                'authoritative_sources': source_names
            })
            # Still mark as verified if we have at least 1 authoritative source
            # (better than nothing, especially for exact citation matches)
            if len(authoritative_sources) >= 1:
                verification_status = 'verified'
        else:
            verification_status = 'verified'
            # Check if sources agree (basic check - could be enhanced with LLM)
            source_names = [s['source'] for s in authoritative_sources]
            conflicts.append({
                'type': 'source_verification',
                'message': f'Found {len(authoritative_sources)} authoritative sources: {", ".join(source_names)}',
                'severity': 'info',
                'authoritative_sources': source_names
            })
        
        # Step 6: Rank results by priority, relevance, and SPECIFICITY
        specificity_info = self._detect_specific_statute_request(query)
        scored_results = []
        
        for result in all_results:
            source = result['metadata'].get('source', 'Unknown')
            priority = self._get_source_priority(source)
            distance = result.get('distance', 1.0)
            
            # Calculate specificity score
            specificity_score = 0.0
            if specificity_info["is_specific_request"]:
                result_text = result.get('text', '').lower()
                result_meta = str(result.get('metadata', {})).lower()
                combined_text = f"{result_text} {result_meta}"
                
                # Boost score if specific terms appear in result
                for term in specificity_info["specific_terms"]:
                    if term in combined_text:
                        specificity_score += 0.3  # Boost for each matching specific term
                
                # Extra boost if code section matches
                if specificity_info["code_section"]:
                    if specificity_info["code_section"] in combined_text:
                        specificity_score += 0.5
                
                # Penalize results that seem too general (contain parent terms but not specific ones)
                # This is a heuristic - if query has "domestic" but result doesn't, it's likely too general
                if "domestic" in query.lower() and "domestic" not in combined_text:
                    if any(parent_term in combined_text for parent_term in ["assault", "battery", "violence"]):
                        specificity_score -= 0.4  # Penalty for generalizing
            
            # Score: (priority, -specificity_score, distance)
            # Lower priority, higher specificity, lower distance = better
            score = (priority, -specificity_score, distance)
            scored_results.append((score, result))
        
        scored_results.sort(key=lambda x: x[0])
        ranked_results = [r[1] for r in scored_results]
        
        # If specific request, ensure top results match specificity
        if specificity_info["is_specific_request"] and ranked_results:
            # Re-check top results for specificity match
            top_results = ranked_results[:5]
            specific_matches = []
            general_matches = []
            
            for result in top_results:
                result_text = result.get('text', '').lower()
                result_meta = str(result.get('metadata', {})).lower()
                combined_text = f"{result_text} {result_meta}"
                
                # Check if result contains specific terms
                has_specific_terms = any(term in combined_text for term in specificity_info["specific_terms"])
                
                if has_specific_terms:
                    specific_matches.append(result)
                else:
                    general_matches.append(result)
            
            # Prioritize specific matches
            if specific_matches:
                ranked_results = specific_matches + general_matches + ranked_results[5:]
        
        return {
            'results': ranked_results,
            'query_variations': query_variations,
            'source_groups': source_groups,
            'authoritative_sources': authoritative_sources,
            'secondary_sources': secondary_sources,
            'conflicts': conflicts,
            'verification_status': verification_status,
            'total_results': len(all_results),
            'unique_sources': len(source_groups)
        }


rag_service = RAGService()

