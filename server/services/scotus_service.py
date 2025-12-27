"""
SCOTUS Service - Separate SCOTUS Database Query
Treats SCOTUS as a separate authoritative database that's queried independently.
This ensures SCOTUS cases are always found and properly prioritized.
"""

from typing import List, Dict, Optional
import re
from server.services.rag_service import rag_service
from server.utils.logger import setup_logger


class SCOTUSService:
    """
    Separate service for querying SCOTUS opinions.
    Treats SCOTUS as a distinct authoritative database.
    """
    
    def __init__(self):
        self.logger = setup_logger("scotus")
        self.rag_service = rag_service
    
    def _expand_scotus_query(self, query: str) -> List[str]:
        """
        Expand query with SCOTUS-relevant terms for better case finding.
        Adds constitutional, federal law, and case law terminology.
        Recognizes landmark case names and adds their full citations.
        """
        query_lower = query.lower()
        expanded = [query]  # Always include original
        
        # Landmark case recognition - add full case names and citations
        landmark_cases = {
            'heller': ['District of Columbia v. Heller', '554 U.S. 570', 'Heller Second Amendment'],
            'bruen': ['NYSRPA v. Bruen', 'New York State Rifle & Pistol Association v. Bruen', '597 U.S. 1', '142 S. Ct. 2111', 'Bruen concealed carry'],
            'mcdonald': ['McDonald v. City of Chicago', '561 U.S. 742', 'McDonald Second Amendment incorporation'],
            'miller': ['United States v. Miller', '307 U.S. 174', 'Miller Second Amendment'],
            'miranda': ['Miranda v. Arizona', '384 U.S. 436', 'Miranda rights'],
        }
        
        # Check if query mentions a landmark case
        for case_key, case_terms in landmark_cases.items():
            if case_key in query_lower:
                expanded.extend(case_terms)
        
        # Constitutional/firearm related expansions
        if any(term in query_lower for term in ['firearm', 'gun', 'weapon', 'second amendment', 'bear arms']):
            expanded.extend([
                f"{query} Second Amendment",
                f"{query} constitutional right",
                f"{query} self-defense",
                "Second Amendment self-defense firearm",
                "constitutional right self-defense",
                "District of Columbia v. Heller",  # Always include Heller for firearm queries
                "NYSRPA v. Bruen"  # Always include Bruen for firearm queries
            ])
        
        # Self-defense expansions
        if 'self' in query_lower and 'defense' in query_lower:
            expanded.extend([
                f"{query} constitutional",
                f"{query} Second Amendment",
                "self-defense Second Amendment",
                "self-defense constitutional right",
                "stand your ground self-defense",
                "District of Columbia v. Heller",  # Heller is key for self-defense
                "NYSRPA v. Bruen"  # Bruen is key for modern self-defense
            ])
        
        # Add SCOTUS-specific terms
        expanded.append(f"{query} Supreme Court")
        expanded.append(f"{query} SCOTUS")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_expanded = []
        for q in expanded:
            q_lower = q.lower()
            if q_lower not in seen:
                seen.add(q_lower)
                unique_expanded.append(q)
        
        return unique_expanded[:8]  # Increased to 8 to include landmark cases
    
    async def search_scotus(self, query: str, n_results: int = 5) -> List[Dict]:
        """
        Search SCOTUS opinions as a separate database.
        
        This queries ONLY SCOTUS opinions, treating them as a distinct
        authoritative source that should be checked independently.
        
        Args:
            query: Search query
            n_results: Number of SCOTUS results to return
            
        Returns:
            List of SCOTUS opinion results
        """
        self.rag_service._ensure_initialized()
        
        # Expand query with SCOTUS-relevant terms for better matching
        query_variations = self._expand_scotus_query(query)
        
        # Search SCOTUS opinions - query all results then filter
        try:
            from server.services.ollama_service import ollama_service
            
            # Try multiple query variations to find relevant cases
            all_candidates = []
            seen_ids = set()
            
            for query_var in query_variations[:3]:  # Try top 3 variations
                # Generate query embedding
                query_embedding = await ollama_service.embed(query_var)
            
                # Query without filter first (ChromaDB where syntax is complex)
                # We'll filter results after
                # Get more results to ensure we find SCOTUS cases even if they're lower in semantic ranking
                raw = self.rag_service.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results * 10  # Get many more to filter for SCOTUS
                )
            
                # Process and filter for SCOTUS only
                ids = raw.get('ids', [[]])[0]
                docs = raw.get('documents', [[]])[0]
                metas = raw.get('metadatas', [[]])[0]
                dists = raw.get('distances', [[]])[0] if raw.get('distances') else []
                
                # SCOTUS indicators to check
                scotus_indicators = [
                    'SCOTUS',
                    'SUPREME COURT',
                    'SUPREME COURT OF THE UNITED STATES',
                    'U.S. SUPREME COURT',
                    'US SUPREME COURT',
                    'UNITED STATES SUPREME COURT'
                ]
                
                # Collect SCOTUS results from this query variation
                for i in range(len(ids)):
                    if ids[i] in seen_ids:
                        continue
                    
                    meta = metas[i] or {}
                    source_name = (meta.get('source', '') or '').upper()
                    jurisdiction = meta.get('jurisdiction', '')
                    content_type = meta.get('content_type', '')
                    
                    # Check if this is a SCOTUS case
                    is_scotus = False
                    for indicator in scotus_indicators:
                        if indicator in source_name:
                            is_scotus = True
                            break
                    
                    # Also check Federal case law
                    if not is_scotus and jurisdiction == 'Federal' and content_type == 'case_law':
                        is_scotus = True
                    
                    if is_scotus:
                        distance = dists[i] if i < len(dists) else None
                        all_candidates.append({
                            "id": ids[i],
                            "text": docs[i],
                            "metadata": meta,
                            "distance": distance,
                            "source_type": "SCOTUS",
                            "matched_query": query_var
                        })
                        seen_ids.add(ids[i])
            
            # Sort by distance (lower = more relevant) and take top n_results
            all_candidates.sort(key=lambda x: x['distance'] if x['distance'] is not None else float('inf'))
            results = all_candidates[:n_results]
            
            self.logger.info(f"Found {len(results)} SCOTUS opinions for query: {query[:50]}")
            return results
            
        except Exception as e:
            self.logger.error(f"Error searching SCOTUS: {e}")
            return []
    
    async def search_scotus_by_case_name(self, case_name: str) -> List[Dict]:
        """
        Search for SCOTUS cases by case name (e.g., "Heller", "Bruen", "District of Columbia v. Heller").
        
        Args:
            case_name: Case name or partial case name
            
        Returns:
            List of matching SCOTUS opinions
        """
        self.rag_service._ensure_initialized()
        
        try:
            # Get all SCOTUS documents and search by case name in metadata and text
            all_docs = self.rag_service.collection.get(
                where={"source": "SCOTUS Opinions"},
                limit=10000
            )
            
            ids = all_docs.get('ids', [])
            docs = all_docs.get('documents', [])
            metas = all_docs.get('metadatas', [])
            
            case_name_upper = case_name.upper()
            matches = []
            
            for i, meta in enumerate(metas):
                meta_case = (meta.get('case_name', '') or '').upper()
                meta_text = (docs[i] if i < len(docs) else '').upper()
                
                # Check if case name appears in metadata or document text
                if case_name_upper in meta_case or case_name_upper in meta_text[:5000]:  # Check first 5000 chars
                    matches.append({
                        "id": ids[i],
                        "text": docs[i] if i < len(docs) else '',
                        "metadata": meta,
                        "source_type": "SCOTUS"
                    })
            
            self.logger.info(f"Found {len(matches)} SCOTUS cases matching '{case_name}'")
            return matches
            
        except Exception as e:
            self.logger.error(f"Error searching SCOTUS by case name {case_name}: {e}")
            return []
    
    async def search_scotus_by_citation(self, citation: str) -> Optional[Dict]:
        """
        Search for a specific SCOTUS case by citation.
        
        Args:
            citation: Bluebook citation (e.g., "384 U.S. 436")
            
        Returns:
            SCOTUS opinion if found, None otherwise
        """
        self.rag_service._ensure_initialized()
        
        try:
            # Search by citation - get all with this citation, then filter for SCOTUS
            results = self.rag_service.collection.get(
                where={"citation": citation},
                limit=10  # Get multiple in case there are duplicates
            )
            
            # Filter for SCOTUS only
            scotus_indicators = ['SCOTUS', 'SUPREME COURT', 'SUPREME COURT OF THE UNITED STATES']
            
            for i, meta in enumerate(results.get('metadatas', [])):
                source_name = (meta.get('source', '') or '').upper()
                jurisdiction = meta.get('jurisdiction', '')
                content_type = meta.get('content_type', '')
                
                is_scotus = any(indicator in source_name for indicator in scotus_indicators)
                if not is_scotus and jurisdiction == 'Federal' and content_type == 'case_law':
                    is_scotus = True
                
                if is_scotus:
                    return {
                        "id": results['ids'][i],
                        "text": results['documents'][i],
                        "metadata": meta,
                        "source_type": "SCOTUS"
                    }
        except Exception as e:
            self.logger.error(f"Error searching SCOTUS by citation {citation}: {e}")
        
        return None


# Singleton instance
scotus_service = SCOTUSService()

