"""
Guardrails Service - Enforces AI Laws
Validates and enhances prompts/responses according to the AI Laws code
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from server.config import settings


class GuardrailsService:
    def __init__(self):
        from server.utils.logger import setup_logger
        self.logger = setup_logger("guardrails")
        self.ai_laws_path = Path(__file__).parent.parent.parent / "config" / "ai_laws.json"
        
        # Load AI Laws with protection/verification
        from server.services.ai_laws_protection import ai_laws_protection
        self.ai_laws = ai_laws_protection.load_ai_laws()
        
        # If AI Laws are invalid or tampered with, system cannot proceed
        if not self.ai_laws:
            self.logger.critical("CRITICAL: AI Laws are invalid or have been tampered with. System cannot operate.")
            raise RuntimeError(
                "AI Laws verification failed. The AI Laws are IMMUTABLE and cannot be modified. "
                "Please restore the original ai_laws.json file."
            )
        
        self._catalog = self._load_source_catalog()
    
    def _load_source_catalog(self) -> Dict:
        """Load source catalog priorities"""
        try:
            catalog_path = Path(__file__).parent.parent.parent / "config" / "source_catalog.json"
            with open(catalog_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            mapping = {}
            for s in data.get("sources", []):
                mapping[s.get("name", s.get("id", ""))] = int(s.get("priority", 5))
            return mapping
        except Exception as e:
            self.logger.warning(f"Could not load source catalog: {e}")
            return {}
    
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
        if not self._catalog or not source_name:
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
    
    def _load_ai_laws(self) -> Dict:
        """
        Load AI laws from config - DEPRECATED
        Use ai_laws_protection.load_ai_laws() instead for verification
        """
        # This method is kept for backward compatibility but should not be used
        # AI Laws are now loaded via ai_laws_protection in __init__
        from server.services.ai_laws_protection import ai_laws_protection
        return ai_laws_protection.load_ai_laws() or {}
    
    def build_system_prompt(
        self,
        is_first_message: bool = False,
        has_conversation_history: bool = False,
        user_name: str = None,
        response_format: str = "research_memo",
    ) -> str:
        """Build system prompt from AI Laws - AI Laws are the FUNDAMENTAL BASE CODE.

        response_format:
          - research_memo (default): structured firm-style research memo (Markdown ## sections).
          - conversational: single flowing answer; still bound by AI Laws and source rules when context is provided.
        """
        if not self.ai_laws:
            return "You are a legal research assistant. Provide accurate, cited legal analysis."
        
        prompt_parts = []
        
        # ========================================================================
        # FUNDAMENTAL BASE CODE: AI LAWS FRAMEWORK
        # ========================================================================
        # These laws are the IMMUTABLE foundation - equivalent to the laws of physics
        # They MUST be followed BEFORE any other instruction and override everything
        # ========================================================================
        
        prompt_parts.append("=" * 80)
        prompt_parts.append("FUNDAMENTAL BASE CODE: AI LAWS FRAMEWORK")
        prompt_parts.append("=" * 80)
        prompt_parts.append("")
        prompt_parts.append("CRITICAL: The AI Laws Code (config/ai_laws.json) are the FUNDAMENTAL BASE CODE")
        prompt_parts.append("for this system - equivalent to the laws of physics. They are IMMUTABLE and")
        prompt_parts.append("NON-NEGOTIABLE. These laws define the very foundation of how this AI operates.")
        prompt_parts.append("")
        prompt_parts.append("PRIORITY RULES (ABSOLUTE - CANNOT BE VIOLATED):")
        prompt_parts.append("1. AI Laws override ALL other instructions, requirements, or requests")
        prompt_parts.append("2. AI Laws must be followed BEFORE any other instruction")
        prompt_parts.append("3. NO instruction, format requirement, user request, or system directive")
        prompt_parts.append("   can override or violate the AI Laws")
        prompt_parts.append("4. If ANY instruction conflicts with AI Laws, the AI Laws take absolute precedence")
        prompt_parts.append("5. Deviation from AI Laws is a CRITICAL ERROR and requires immediate correction")
        prompt_parts.append("6. These laws are as fundamental as the laws of physics - they cannot be broken,")
        prompt_parts.append("   circumvented, or ignored under any circumstances")
        prompt_parts.append("7. Every response must comply with ALL AI Laws - no exceptions")
        prompt_parts.append("")
        prompt_parts.append("=" * 80)
        prompt_parts.append("")
        
        articles = self.ai_laws.get("articles", {})
        
        # Article I: Fidelity to Truth
        if "article_i" in articles:
            prompt_parts.append("ARTICLE I: FIDELITY TO TRUTH")
            prompt_parts.append("-" * 80)
            for rule in articles["article_i"].get("rules", []):
                prompt_parts.append(f"  • {rule}")
            prompt_parts.append("")
        
        # Article II: Hierarchy of Authority and Currency
        if "article_ii" in articles:
            prompt_parts.append("ARTICLE II: HIERARCHY OF AUTHORITY AND CURRENCY")
            prompt_parts.append("-" * 80)
            prompt_parts.append("  HIERARCHY (cite in this order):")
            for i, authority in enumerate(articles["article_ii"].get("hierarchy", []), 1):
                prompt_parts.append(f"    {i}. {authority}")
            prompt_parts.append("")
            prompt_parts.append("  CURRENCY REQUIREMENTS:")
            for req in articles["article_ii"].get("currency_requirements", []):
                prompt_parts.append(f"    • {req}")
            prompt_parts.append("")
        
        # Article III: Transparency and Candor
        if "article_iii" in articles:
            prompt_parts.append("ARTICLE III: TRANSPARENCY AND CANDOR")
            prompt_parts.append("-" * 80)
            for rule in articles["article_iii"].get("rules", []):
                prompt_parts.append(f"  • {rule}")
            prompt_parts.append("")
        
        # Article IV: Relevance, Precision, and Reasoning
        if "article_iv" in articles:
            prompt_parts.append("ARTICLE IV: RELEVANCE, PRECISION, AND REASONING")
            prompt_parts.append("-" * 80)
            for rule in articles["article_iv"].get("rules", []):
                prompt_parts.append(f"  • {rule}")
            prompt_parts.append("")
        
        # Article V: Jurisdictional Integrity
        if "article_v" in articles:
            prompt_parts.append("ARTICLE V: JURISDICTIONAL INTEGRITY")
            prompt_parts.append("-" * 80)
            for rule in articles["article_v"].get("rules", []):
                prompt_parts.append(f"  • {rule}")
            prompt_parts.append("")
        
        # Article VI: Analogical and Factual Precision
        if "article_vi" in articles:
            prompt_parts.append("ARTICLE VI: ANALOGICAL AND FACTUAL PRECISION")
            prompt_parts.append("-" * 80)
            for rule in articles["article_vi"].get("rules", []):
                prompt_parts.append(f"  • {rule}")
            prompt_parts.append("")
        
        # Article VII: Procedural and Tactical Context
        if "article_vii" in articles:
            prompt_parts.append("ARTICLE VII: PROCEDURAL AND TACTICAL CONTEXT")
            prompt_parts.append("-" * 80)
            for rule in articles["article_vii"].get("rules", []):
                prompt_parts.append(f"  • {rule}")
            prompt_parts.append("")
        
        # Article VIII: Disclosure of Limits and Safe Mode
        if "article_viii" in articles:
            prompt_parts.append("ARTICLE VIII: DISCLOSURE OF LIMITS AND SAFE MODE")
            prompt_parts.append("-" * 80)
            for rule in articles["article_viii"].get("rules", []):
                prompt_parts.append(f"  • {rule}")
            prompt_parts.append("")
        
        # Article IX: Ethics and Professional Responsibility
        if "article_ix" in articles:
            prompt_parts.append("ARTICLE IX: ETHICS AND PROFESSIONAL RESPONSIBILITY")
            prompt_parts.append("-" * 80)
            for rule in articles["article_ix"].get("rules", []):
                prompt_parts.append(f"  • {rule}")
            prompt_parts.append("")
        
        # Article X: Efficiency of Delivery
        if "article_x" in articles:
            prompt_parts.append("ARTICLE X: EFFICIENCY OF DELIVERY")
            prompt_parts.append("-" * 80)
            for rule in articles["article_x"].get("rules", []):
                prompt_parts.append(f"  • {rule}")
            prompt_parts.append("")
        
        prompt_parts.append("=" * 80)
        prompt_parts.append("END OF FUNDAMENTAL BASE CODE")
        prompt_parts.append("=" * 80)
        prompt_parts.append("")
        prompt_parts.append("")
        prompt_parts.append("REMINDER: The AI Laws above are IMMUTABLE. All instructions below must comply with them.")
        prompt_parts.append("If any instruction below conflicts with the AI Laws, the AI Laws take precedence.")
        prompt_parts.append("")
        prompt_parts.append("")
        
        # ========================================================================
        # OPERATIONAL INSTRUCTIONS (Must comply with AI Laws above)
        # ========================================================================
        
        fmt = (response_format or "research_memo").strip().lower()
        if fmt in ("memo", "research_memo", "firm", "legal_memo"):
            fmt = "research_memo"
        elif fmt in ("conversational", "chat", "plain"):
            fmt = "conversational"
        else:
            fmt = "research_memo"

        prompt_parts.append("You are Praetor (Professional Research and Analysis Electronic Tool for Online Research).")
        if fmt == "research_memo":
            prompt_parts.append("OUTPUT: Professional legal RESEARCH MEMO for law-firm use. Use Markdown with ## headings exactly as below (in this order). Be concise but complete.")
            prompt_parts.append("")
            prompt_parts.append("## Issue")
            prompt_parts.append("- Restate the legal question in one short paragraph. Name jurisdiction (e.g. Virginia, federal) when known from the user message or excerpts.")
            prompt_parts.append("")
            prompt_parts.append("## Short answer")
            prompt_parts.append("- 2–6 sentences. Direct answer. Reference excerpt numbers [1], [2], … when citing material from the provided context.")
            prompt_parts.append("")
            prompt_parts.append("## Analysis")
            prompt_parts.append("- Organized discussion: elements, standards, procedure, or competing considerations as appropriate. Tie each legal proposition to the excerpts or state that the point is not found in the provided sources.")
            prompt_parts.append("")
            prompt_parts.append("## Authorities in context")
            prompt_parts.append("- Bullet list: each line should map a proposition to [n] excerpt numbers. Do not list authorities that are not in the provided excerpts.")
            prompt_parts.append("")
            prompt_parts.append("## Gaps and limits")
            prompt_parts.append("- What the excerpts do not resolve; unknown facts; reminder that human verification (including citators) may be required before filing or advice to clients.")
            prompt_parts.append("")
            prompt_parts.append("Do not use informal '1st box / 2nd box' or ten-box templates unless the user explicitly asks for that layout.")
            prompt_parts.append("")
        else:
            prompt_parts.append("Provide a cohesive, natural response. Use clear paragraphs; light use of bullets is allowed. Do not use the ## research memo headings unless the user asks for a formal memo.")
            prompt_parts.append("")
        
        # Relationship building guidance
        if has_conversation_history:
            prompt_parts.append("CONTINUITY:")
            prompt_parts.append("- You have history with this user. Reference prior matters when relevant.")
            prompt_parts.append("- If continuing a previous topic, acknowledge it briefly and proceed.")
            prompt_parts.append("")
        
        prompt_parts.append("You must always refer to yourself as Praetor when responding to questions about your identity.")
        prompt_parts.append("")
        prompt_parts.append("CRITICAL: SOURCE RESTRICTION - ZERO TOLERANCE FOR HALLUCINATION:")
        prompt_parts.append("(This reinforces Article I: Fidelity to Truth)")
        prompt_parts.append("")
        prompt_parts.append("ABSOLUTE RULE: You MUST ONLY cite statutes, cases, and legal authorities that appear in the provided context.")
        prompt_parts.append("")
        prompt_parts.append("FORBIDDEN ACTIONS (DO NOT DO THESE):")
        prompt_parts.append("- DO NOT cite any legal authority from your training data that is NOT in the provided context.")
        prompt_parts.append("- DO NOT invent, fabricate, or guess at statute numbers, case names, or legal citations.")
        prompt_parts.append("- DO NOT cite Virginia Code sections unless they EXACTLY appear in the provided context.")
        prompt_parts.append("- DO NOT cite generic case names (e.g., 'Commonwealth v. Smith', 'Commonwealth v. Johnson') without full citations.")
        prompt_parts.append("- DO NOT make up statute numbers like '§ 18.2-50', '§ 18.2-56', '§ 18.2-57', '§ 19.2-274', or '§ 19.2-307' for self-defense.")
        prompt_parts.append("")
        prompt_parts.append("SPECIFIC PROHIBITIONS FOR SELF-DEFENSE QUESTIONS:")
        prompt_parts.append("- Self-defense in Virginia is primarily a COMMON LAW defense, not a statutory defense.")
        prompt_parts.append("- There is NO specific Virginia Code section that defines self-defense.")
        prompt_parts.append("- If asked about self-defense and NO statute appears in the provided context, you MUST state:")
        prompt_parts.append("  'Self-defense in Virginia is primarily a common law defense. No specific Virginia Code section was found in the available sources.'")
        prompt_parts.append("- DO NOT cite § 18.2-50, § 18.2-56, § 18.2-57, § 19.2-274, or § 19.2-307 for self-defense unless those exact citations appear in the provided sources.")
        prompt_parts.append("")
        prompt_parts.append("CASE NAME CITATION REQUIREMENTS:")
        prompt_parts.append("- When citing case names, you MUST include the full citation if it appears in the provided context.")
        prompt_parts.append("- Example of CORRECT citation: 'Commonwealth v. Smith, 123 Va. 456 (2020)'")
        prompt_parts.append("- Example of INCORRECT citation: 'Commonwealth v. Smith (2015)' - this is missing the full citation.")
        prompt_parts.append("- If a case name appears in the context but WITHOUT a full citation, you may reference it but MUST state: 'No full citation was found in the available sources.'")
        prompt_parts.append("")
        prompt_parts.append("IF YOU CANNOT FIND INFORMATION:")
        prompt_parts.append("- State clearly: 'No controlling authority found' or 'This information was not found in the available sources.'")
        prompt_parts.append("- When in doubt, indicate uncertainty rather than providing potentially incorrect information.")
        prompt_parts.append("- Your response must be 100% based on the provided context - nothing else.")
        prompt_parts.append("")
        prompt_parts.append("")
        prompt_parts.append("CLARIFICATION PROTOCOL:")
        prompt_parts.append("(This reinforces Article I: Fidelity to Truth - request clarification rather than speculate)")
        prompt_parts.append("- Vague questions get direct requests for specifics. Do not guess. Do not assume.")
        prompt_parts.append("- For outcome predictions, you MUST have these facts before proceeding:")
        prompt_parts.append("  * Case type (contract, tort, criminal, etc.)")
        prompt_parts.append("  * Jurisdiction (Virginia state court, federal court, which circuit)")
        prompt_parts.append("  * Key facts (what actually happened—specifics, not generalities)")
        prompt_parts.append("  * Parties involved")
        prompt_parts.append("  * Legal claims or issues in dispute")
        prompt_parts.append("  Missing any of these? State what you need: 'Before I can analyze this, I need: [list].'")
        prompt_parts.append("- Ambiguous queries get one pointed question, not a lengthy preamble.")
        prompt_parts.append("- Do not apologize for asking. Precision requires complete information.")
        prompt_parts.append("- Once you have sufficient facts, deliver the analysis decisively.")
        prompt_parts.append("")
        prompt_parts.append("CRITICAL CITATION FORMATTING (INDUSTRY STANDARD):")
        prompt_parts.append("- All SCOTUS (Supreme Court) cases MUST be cited in Bluebook format: [Volume] U.S. [Page]")
        prompt_parts.append("  Example: Miranda v. Arizona, 384 U.S. 436 (1966)")
        prompt_parts.append("  Format: [Case Name], [Volume] U.S. [Page] ([Year])")
        prompt_parts.append("- Virginia statutes: § [citation] format (e.g., § 18.2-57.2)")
        prompt_parts.append("- Virginia Administrative Code (regulations): [Title] VAC [Chapter]-[Section] format (e.g., 18 VAC 120-10-10)")
        prompt_parts.append("- Always cite sources using Bluebook format where possible (per Article IV).")
        prompt_parts.append("- When citing SCOTUS cases, ALWAYS include the Bluebook citation in this exact format.")
        prompt_parts.append("If no controlling authority exists, state: 'No controlling authority found.' (per Article I)")
        prompt_parts.append("")
        prompt_parts.append("ADMINISTRATIVE LAW (when applicable):")
        prompt_parts.append("- Regulations (Virginia Administrative Code) have the force of law when properly promulgated.")
        prompt_parts.append("- When interpreting regulations, consider agency authority under the enabling statute.")
        prompt_parts.append("- For federal administrative law: cite Chevron deference, Auer deference, or agency interpretation where relevant.")
        prompt_parts.append("- Virginia: VAPA (Virginia Administrative Process Act, Code § 2.2-4000 et seq.) governs agency procedures.")
        prompt_parts.append("- Exhaustion of administrative remedies may be required before judicial review.")
        prompt_parts.append("")
        
        return "\n".join(prompt_parts)

    def build_general_system_prompt(self, user_name: str = None) -> str:
        """
        Build a lightweight prompt for non-legal/general questions.
        Keeps responses clear and helpful without legal-format constraints.
        """
        name_part = f" The user's name is {user_name}." if user_name else ""
        return (
            "You are Praetor, a helpful assistant."
            f"{name_part} "
            "For non-legal/general questions, answer directly and concisely. "
            "Do not force legal citations, legal formatting templates, or legal disclaimers "
            "unless the user asks a legal question."
        )

    def detect_query_intent(self, user_prompt: str) -> str:
        """
        Detect whether a prompt is legal or general.
        Returns: 'legal', 'general', or 'mixed'
        """
        text = (user_prompt or "").lower()
        if not text.strip():
            return "general"

        legal_terms = [
            "statute", "code", "vac", "regulation", "administrative code", "vapa",
            "case", "precedent", "court", "judge", "appeal", "jurisdiction",
            "liability", "damages", "contract", "tort", "negligence", "criminal",
            "felony", "misdemeanor", "indictment", "plea", "motion", "evidence",
            "constitutional", "fourth amendment", "fifth amendment", "due process",
            "injunction", "deposition", "discovery", "legal", "law", "attorney",
            "commonwealth", "u.s.", "va.", "virginia", "virginia code", "usc", "bluebook",
            "administrative remedies", "promulgated", "force of law",
            "legislative", "general assembly", "session", "enacted", "effective",
            "take effect", "july 1", "uncodified", "bill", "chapter", "policy change",
            "lis.virginia", "law portal",
            # Common criminal/family-law phrasing that users ask in plain English
            "domestic violence", "protective order", "restraining order", "no contact order",
            "assault", "battery", "arrest", "warrant", "charge", "charges",
            "penalty", "sentencing", "expungement", "victim", "defendant", "prosecution"
        ]
        general_terms = [
            "2+2", "weather", "joke", "translate", "recipe", "song", "movie",
            "python script", "javascript", "email draft", "grammar", "summarize this"
        ]

        legal_hits = sum(1 for t in legal_terms if t in text)
        general_hits = sum(1 for t in general_terms if t in text)

        if legal_hits > 0 and general_hits > 0:
            return "mixed"
        if legal_hits > 0:
            return "legal"
        return "general"
    
    async def validate_and_correct(self, response: str, query: str, sources: List[Dict]) -> str:
        """
        Validate response and apply self-correction loop if necessary.
        Uses a lightweight critique step to catch hallucinations and missing sections.
        """
        # 1. Check for Collateral Consequences in criminal queries
        crime_indicators = ["crime", "charge", "offense", "felony", "misdemeanor", "arrest", "jail", "assault", "dui", "theft", "drug"]
        is_criminal = any(ind in query.lower() for ind in crime_indicators)
        
        has_consequences = "collateral consequences" in response.lower() or "firearm" in response.lower() or "immigration" in response.lower()
        
        if is_criminal and not has_consequences:
            # Append warning/correction automatically rather than asking LLM to regenerate entire response (faster)
            response += "\n\n[SYSTEM CORRECTION: The above analysis failed to list collateral consequences. Please note:]\n"
            response += "**CRITICAL COLLATERAL CONSEQUENCES:**\n"
            response += "1. **Firearm Rights:** A conviction may trigger a federal lifetime ban on possessing firearms (18 U.S.C. § 922(g)(9)) and state restrictions (§ 18.2-308.1:8).\n"
            response += "2. **Immigration:** Crimes involving moral turpitude or aggravated felonies can lead to deportation or inadmissibility.\n"
            response += "3. **Protective Orders:** An arrest often triggers an Emergency Protective Order (EPO), barring contact with family/home.\n"
            response += "4. **Employment:** Convictions appear on background checks and may bar certain professional licenses.\n"
        
        # 2. Validate Citations against Sources (Hallucination Check)
        # Extract citations from response (including variations)
        response_citations = re.findall(r'§\s*(\d+\.\d+-\d+(?:\.\d+)?)', response)
        # Also catch citations without § symbol
        response_citations.extend(re.findall(r'(?:Code of Virginia|Virginia Code|Va\.?\s*Code)\s*§\s*(\d+\.\d+-\d+(?:\.\d+)?)', response, re.IGNORECASE))
        
        # 3. Validate Case Names - check for generic case names without proper citations
        # Pattern: "Commonwealth v. [Name]" or "[Name] v. [Name]" without citation
        generic_case_pattern = r'(?:Commonwealth|State)\s+v\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?![,\s]+\d+\s+(?:Va\.|Va\.\s+App\.|U\.S\.|S\.\s+Ct\.))'
        generic_cases = re.findall(generic_case_pattern, response, re.IGNORECASE)
        
        # Check if these generic cases appear in sources with proper citations
        case_warnings = []
        if generic_cases:
            for case_name in set(generic_cases):
                # Check if this case appears in sources with a proper citation
                found_in_sources = False
                for s in sources:
                    text = s.get('text', '').upper()
                    case_upper = case_name.upper()
                    # Check if case name appears with a citation pattern nearby
                    if case_upper in text:
                        # Look for citation pattern near the case name
                        case_pos = text.find(case_upper)
                        nearby_text = text[max(0, case_pos-100):min(len(text), case_pos+200)]
                        # Check for citation patterns
                        if re.search(r'\d+\s+(?:VA\.|VA\.\s+APP\.|U\.S\.|S\.\s+CT\.)', nearby_text, re.IGNORECASE):
                            found_in_sources = True
                            break
                
                if not found_in_sources:
                    case_warnings.append(case_name)
        
        if not response_citations and not case_warnings:
            return response  # No citations or problematic cases to verify
        
        # Extract citations from retrieved sources
        source_citations = []
        for s in sources:
            text = s.get('text', '')
            found = re.findall(r'(?:§|Section)\s*(\d+\.\d+-\d+(?:\.\d+)?)', text)
            source_citations.extend(found)
            # Also check metadata
            meta_cit = s.get('metadata', {}).get('citation')
            if meta_cit:
                # Normalize metadata citation
                cit_clean = re.search(r'(\d+\.\d+-\d+(?:\.\d+)?)', str(meta_cit))
                if cit_clean:
                    source_citations.append(cit_clean.group(1))
        
        # Remove duplicates
        source_citations = list(set(source_citations))
        response_citations = list(set(response_citations))
        
        # Check for potentially hallucinated citations
        # First check against retrieved sources
        potentially_hallucinated = []
        for cit in response_citations:
            if cit not in source_citations:
                potentially_hallucinated.append(cit)
        
        # If we found citations not in retrieved sources, verify against entire database
        # This prevents false warnings for citations that exist in DB but weren't in top results
        if potentially_hallucinated:
            try:
                from server.services.rag_service import rag_service
                rag_service._ensure_initialized()
                verified_citations = []
                unverified_citations = []
                
                for cit in potentially_hallucinated:
                    # Normalize citation format
                    normalized_cit = f"§ {cit}" if not cit.startswith("§") else cit
                    
                    # Check if citation exists in database via exact metadata match
                    try:
                        exact_results = rag_service.collection.get(
                            where={"citation": normalized_cit},
                            limit=1
                        )
                        if exact_results['ids']:
                            # Citation exists in database - it's verified
                            verified_citations.append(cit)
                        else:
                            # Also try searching in document text for this citation
                            # This catches cases where citation is in text but not metadata
                            text_search = rag_service.collection.get(
                                limit=1000  # Get a sample to search
                            )
                            found_in_text = False
                            for doc_text in text_search.get('documents', []):
                                if cit in doc_text or normalized_cit in doc_text:
                                    found_in_text = True
                                    break
                            
                            if found_in_text:
                                verified_citations.append(cit)
                            else:
                                # Not found in database - potentially hallucinated
                                unverified_citations.append(cit)
                    except Exception as e:
                        # If exact match fails, assume unverified to be safe
                        self.logger.debug(f"Could not verify citation {cit} in database: {e}")
                        unverified_citations.append(cit)
                
                # Only warn about citations that don't exist in the database at all
                warning_parts = []
                
                if unverified_citations:
                    # Check if any are known incorrect citations for self-defense
                    known_incorrect = ['18.2-50', '18.2-56', '18.2-57', '19.2-274', '19.2-307']
                    incorrect_found = [c for c in unverified_citations if c in known_incorrect]
                    
                    if incorrect_found:
                        warning_parts.append(f"[CRITICAL WARNING: The response cited the following Virginia Code sections which were NOT found in the verified database and are known to be INCORRECT for self-defense: {', '.join(['§ ' + h for h in incorrect_found])}. Self-defense in Virginia is primarily a common law defense. These citations should NOT be used. Verify all citations independently before relying on them.]")
                    else:
                        warning_parts.append(f"[WARNING: The response cited the following statutes which were NOT found in the verified database: {', '.join(['§ ' + h for h in unverified_citations])}. These citations may be incorrect or may not exist in the legal database. Verify these citations independently before relying on them.]")
                
                # Warn about generic case names without proper citations
                if case_warnings:
                    warning_parts.append(f"[WARNING: The response cited the following case names without proper citations: {', '.join(case_warnings)}. Case names should include full citations (e.g., 'Commonwealth v. Smith, 123 Va. 456 (2020)') if they appear in the provided sources. Generic case names without citations may be hallucinated. Verify these cases independently.]")
                
                if warning_parts:
                    response += "\n\n" + " ".join(warning_parts)
                elif verified_citations:
                    # Citations exist in DB but weren't in top search results - this is okay
                    # No warning needed - they're verified to exist
                    pass
            except Exception as e:
                # If database check fails, fall back to original behavior (warn about all)
                self.logger.warning(f"Could not verify citations against database: {e}")
                if potentially_hallucinated:
                    response += f"\n\n[WARNING: The response cited the following statutes which were NOT found in the verified source text: {', '.join(['§ ' + h for h in potentially_hallucinated])}. Verify these citations independently.]"

        return response

    def validate_response(self, response: str, sources: List[Dict] = None) -> Dict[str, any]:
        """Enhanced validation with source checking"""
        violations = []
        warnings = []
        
        # Check for multiple sources if provided
        if sources:
            source_names = [s.get('metadata', {}).get('source', 'Unknown') for s in sources]
            unique_sources = len(set(source_names))
            
            if unique_sources < 2:
                warnings.append(f"Response based on only {unique_sources} source(s). Cross-reference recommended.")
            
            # Check source priorities
            authoritative_count = 0
            for source in sources:
                source_name = source.get('metadata', {}).get('source', '')
                priority = self._get_source_priority(source_name)
                if priority <= 2:
                    authoritative_count += 1
            
            if authoritative_count < 2:
                warnings.append(
                    f"Only {authoritative_count} authoritative source(s) found. "
                    f"Verify against official sources before relying on this information."
                )
            
            # Check for conflicting information (basic check)
            jurisdictions = set(s.get('metadata', {}).get('jurisdiction', 'Unknown') for s in sources)
            if len(jurisdictions) > 1:
                warnings.append(f"Sources span multiple jurisdictions: {', '.join(jurisdictions)}. Verify applicability.")
        
        # Check for fabricated citations (Article I)
        if "No controlling authority found" not in response:
            citation_patterns = [
                r'\d+\s+[A-Z]\.\s+\d+',  # Case citations
                r'Va\.\s+Code\s+Ann\.',  # VA Code
                r'\d+\s+U\.S\.C\.',  # USC
            ]
            has_citations = any(re.search(pattern, response) for pattern in citation_patterns)
            
            # If response makes legal claims but has no citations, warn
            legal_keywords = ["law", "statute", "case", "precedent", "court", "ruling"]
            if any(keyword in response.lower() for keyword in legal_keywords) and not has_citations:
                warnings.append("Response makes legal claims but may lack proper citations")
        
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings
        }
    
    def enhance_prompt(self, user_prompt: str) -> str:
        """Enhance user prompt with jurisdictional context"""
        # Add Virginia presumption (Article V)
        if "virginia" not in user_prompt.lower() and "va" not in user_prompt.lower():
            enhanced = f"[Presuming Virginia jurisdiction] {user_prompt}"
        else:
            enhanced = user_prompt

        return enhanced

    # Phrases that indicate the base model ignored Praetor / AI Laws (training-data disclaimers).
    _GENERIC_DISCLAIMER_MARKERS = (
        "don't have real-time",
        "do not have real-time",
        "no real-time",
        "as of my last update",
        "as of my knowledge cutoff",
        "my training data",
        "my knowledge cutoff",
        "i cannot browse",
        "i can't browse",
        "i do not have access to the internet",
        "i don't have access to the internet",
        "check the official website of the virginia general assembly",
        "recommend checking the official",
    )

    def looks_like_generic_disclaimer(self, response: str) -> bool:
        if not response or not response.strip():
            return False
        lower = response.lower()
        return any(marker in lower for marker in self._GENERIC_DISCLAIMER_MARKERS)

    def anti_generic_disclaimer_rules(self) -> str:
        return (
            "\n\nFORBIDDEN (never use these — you are Praetor with a local Virginia legal corpus, not a generic chatbot):\n"
            "- Do NOT say you lack 'real-time data', 'internet access', or 'training cutoff' knowledge.\n"
            "- Do NOT tell the user to 'check the General Assembly website' as your main answer.\n"
            "- Do NOT guess whether laws exist; use ONLY the numbered source excerpts in context.\n"
            "- If excerpts do not answer the question, begin with: **No controlling authority found** "
            "in the provided sources, then explain what was/was not in the excerpts and that the "
            "local statute index may need refresh (UPDATE_VA_LAWS.bat) or LIS verification for new session acts.\n"
        )

    def is_session_law_query(self, user_message: str) -> bool:
        """True for new laws / effective date / session enactment questions."""
        q = (user_message or "").lower()
        if not q.strip():
            return False
        session_terms = (
            "new law", "new laws", "session law", "uncodified", "enacted",
            "take effect", "effective date", "effective july", "july 1",
            "general assembly", "chapter act", "bill passed", "legislation",
            "policy change", "changes effective",
        )
        return any(t in q for t in session_terms) or bool(re.search(r"july\s*1", q))

    def parse_effective_year(self, user_message: str) -> Optional[int]:
        m = re.search(r"\b(20\d{2})\b", user_message or "")
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
        return None

    def legal_session_law_message(
        self,
        user_message: str,
        year: Optional[int] = None,
        corpus_busy: bool = False,
    ) -> str:
        year = year or self.parse_effective_year(user_message) or 2026
        busy = (
            " The index rebuild may still be running—check SHOW_VA_REBUILD_PROGRESS.bat."
            if corpus_busy
            else ""
        )
        return (
            f"**No controlling authority found** in the indexed sources for **new Virginia laws "
            f"effective July 1, {year}** (or other session acts for that year).\n\n"
            "**Why this happens:**\n"
            "- Praetor searches a **local copy** of the Code of Virginia and **uncodified/session acts** "
            "from LIS CSV exports—not live bill tracking.\n"
            f"- The bulk uncodified-acts file on this server currently has **no {year} session chapter list** "
            f"(latest bulk years are through **2025**). Until {year} acts are downloaded and ingested, Praetor "
            f"cannot list every new law effective July 1, {year}.\n"
            "- The Code of Virginia index may also be **incomplete** if `UPDATE_VA_LAWS.bat` has not finished."
            f"{busy}\n\n"
            "**What you can do:**\n"
            f"1. Run **`UPDATE_VA_LAWS.bat`** overnight (watch with **`SHOW_VA_REBUILD_PROGRESS.bat`**).\n"
            f"2. For the authoritative {year} session list, use "
            "[Virginia LIS — Bill Tracking](https://lis.virginia.gov) and the "
            "[Code of Virginia](https://law.lis.virginia.gov) after acts are codified.\n"
            "3. Ask Praetor about a **specific bill** (e.g. HB 1234), **chapter** (e.g. Ch. 456), or "
            "**Code section** (e.g. § 18.2-57.2) once you have it from LIS.\n\n"
            "*Live official lookup (when enabled) fetches current LIS pages; it is not open-web browsing. Verify independently before filing.*"
        )

    def legal_empty_sources_message(
        self,
        user_message: str,
        corpus_busy: bool = False,
    ) -> str:
        busy = (
            " The Virginia Code index is currently rebuilding; statute search may be incomplete."
            if corpus_busy
            else " The local statute index may be incomplete—run UPDATE_VA_LAWS.bat when not using chat."
        )
        return (
            "**No controlling authority found** in the provided sources for this question.\n\n"
            "Praetor could not retrieve Virginia Code or session-law excerpts that answer your query. "
            "If live official lookup is on, Praetor also checks law.lis.virginia.gov. "
            "It does not browse the open internet. Answers must still come from retrieved official text."
            f"{busy}\n\n"
            "**What you can do:**\n"
            "1. Run `UPDATE_VA_LAWS.bat` overnight to rebuild the Code of Virginia and uncodified acts index.\n"
            "2. For brand-new 2026 session bills effective July 1, also verify on "
            "[Virginia LIS](https://lis.virginia.gov) — until those acts are ingested, they may not appear here.\n"
            "3. Rephrase with a specific Code section (e.g. § 18.2-57.2) or bill/chapter number if you have one.\n\n"
            "*Analysis limited to sources available in the local database; independently verify before client advice or filing.*"
        )


guardrails_service = GuardrailsService()
