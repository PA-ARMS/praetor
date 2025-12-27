"""
Comparative Motion Analysis Service
Analyzes two opposing motions and provides strategic advice for each side
Uses RAG to find relevant cases, statutes, and precedents
"""
from typing import Dict, List, Optional
import json

from server.services.motion_analysis_service import motion_analysis_service
from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service
from server.services.guardrails_service import guardrails_service
from server.utils.logger import setup_logger

logger = setup_logger("comparative_motion")


class ComparativeMotionService:
    """Analyzes two opposing motions and provides strategic advice"""
    
    async def analyze_opposing_motions(
        self,
        motion1_text: str,
        motion2_text: str,
        motion1_label: str = "Motion 1",
        motion2_label: str = "Motion 2",
        jurisdiction: str = "Virginia",
        case_type: Optional[str] = None
    ) -> Dict:
        """
        Analyze two opposing motions and provide strategic advice for each side
        
        Args:
            motion1_text: Text of first motion
            motion1_label: Label for first motion (e.g., "Plaintiff's Motion to Dismiss")
            motion2_text: Text of second motion
            motion2_label: Label for second motion (e.g., "Defendant's Motion for Summary Judgment")
            jurisdiction: Legal jurisdiction (default: Virginia)
            case_type: Type of case (optional, auto-detected if not provided)
        
        Returns:
            Dict with analysis for both motions, comparison, and strategic recommendations
        """
        
        logger.info(f"Starting comparative analysis: {motion1_label} vs {motion2_label}")
        
        # Step 1: Analyze each motion individually
        logger.info("Analyzing Motion 1...")
        motion1_analysis = await motion_analysis_service.analyze_motion(
            motion_text=motion1_text,
            motion_type=case_type,
            jurisdiction=jurisdiction
        )
        
        logger.info("Analyzing Motion 2...")
        motion2_analysis = await motion_analysis_service.analyze_motion(
            motion_text=motion2_text,
            motion_type=case_type,
            jurisdiction=jurisdiction
        )
        
        # Step 2: Extract key arguments from each motion
        motion1_args = self._extract_arguments(motion1_text, motion1_label)
        motion2_args = self._extract_arguments(motion2_text, motion2_label)
        
        # Step 3: Find relevant legal authorities using RAG
        logger.info("Searching for relevant legal authorities...")
        legal_authorities = await self._find_relevant_authorities(
            motion1_text, motion2_text, jurisdiction
        )
        
        # Step 4: Compare motions and identify strengths/weaknesses
        comparison = await self._compare_motions(
            motion1_text, motion1_label, motion1_analysis, motion1_args,
            motion2_text, motion2_label, motion2_analysis, motion2_args,
            legal_authorities
        )
        
        # Step 5: Generate strategic advice for each side
        logger.info("Generating strategic recommendations...")
        strategy1 = await self._generate_strategy(
            motion_text=motion1_text,
            motion_label=motion1_label,
            motion_analysis=motion1_analysis,
            opposing_motion_text=motion2_text,
            opposing_label=motion2_label,
            opposing_analysis=motion2_analysis,
            legal_authorities=legal_authorities,
            jurisdiction=jurisdiction
        )
        
        strategy2 = await self._generate_strategy(
            motion_text=motion2_text,
            motion_label=motion2_label,
            motion_analysis=motion2_analysis,
            opposing_motion_text=motion1_text,
            opposing_label=motion1_label,
            opposing_analysis=motion1_analysis,
            legal_authorities=legal_authorities,
            jurisdiction=jurisdiction
        )
        
        # Step 6: Calculate win probability for each side
        win_probabilities = self._calculate_win_probabilities(
            motion1_analysis, motion2_analysis, comparison
        )
        
        return {
            "motion1": {
                "label": motion1_label,
                "analysis": motion1_analysis,
                "arguments": motion1_args,
                "strategy": strategy1,
                "win_probability": win_probabilities["motion1"]
            },
            "motion2": {
                "label": motion2_label,
                "analysis": motion2_analysis,
                "arguments": motion2_args,
                "strategy": strategy2,
                "win_probability": win_probabilities["motion2"]
            },
            "comparison": comparison,
            "legal_authorities": legal_authorities,
            "summary": {
                "motion1_strengths": comparison["motion1_strengths"],
                "motion2_strengths": comparison["motion2_strengths"],
                "motion1_weaknesses": comparison["motion1_weaknesses"],
                "motion2_weaknesses": comparison["motion2_weaknesses"],
                "key_issues": comparison["key_issues"]
            }
        }
    
    def _extract_arguments(self, motion_text: str, label: str) -> Dict:
        """Extract key arguments from motion text"""
        # Use AI to extract structured arguments
        prompt = f"""Extract the key legal arguments from this {label}:

{motion_text[:3000]}

Provide:
1. Main legal theory/doctrine
2. Key facts cited
3. Statutory citations
4. Case citations
5. Procedural arguments

Format as JSON with keys: legal_theory, key_facts, statutes, cases, procedural_args"""
        
        try:
            response = ollama_service.generate(prompt, max_tokens=1024)
            # Try to parse JSON, fallback to text extraction
            try:
                return json.loads(response)
            except:
                return {"raw_analysis": response}
        except Exception as e:
            logger.error(f"Error extracting arguments: {e}")
            return {"error": str(e)}
    
    async def _find_relevant_authorities(
        self, motion1_text: str, motion2_text: str, jurisdiction: str
    ) -> Dict:
        """Find relevant cases, statutes, and legal authorities using RAG"""
        
        # Combine both motions to find comprehensive authorities
        combined_query = f"{motion1_text[:1000]} {motion2_text[:1000]}"
        
        # Search for relevant statutes
        statute_results = await rag_service.search(
            query=combined_query,
            n_results=10,
            filters={"jurisdiction": jurisdiction, "document_type": "Statute"}
        )
        
        # Search for case law (if available in database)
        case_results = await rag_service.search(
            query=combined_query,
            n_results=10
        )
        
        # Extract key legal terms for targeted search
        legal_terms = self._extract_legal_terms(motion1_text + " " + motion2_text)
        
        targeted_results = []
        for term in legal_terms[:5]:  # Top 5 terms
            results = await rag_service.search(
                query=f"{term} {jurisdiction}",
                n_results=5
            )
            targeted_results.extend(results)
        
        return {
            "statutes": [
                {
                    "citation": r.get("metadata", {}).get("citation", "Unknown"),
                    "source": r.get("metadata", {}).get("source", "Unknown"),
                    "text": r.get("text", "")[:500],
                    "relevance": "high" if r.get("distance", 1.0) < 0.3 else "medium"
                }
                for r in statute_results[:10]
            ],
            "cases": [
                {
                    "source": r.get("metadata", {}).get("source", "Unknown"),
                    "text": r.get("text", "")[:500],
                    "relevance": "high" if r.get("distance", 1.0) < 0.3 else "medium"
                }
                for r in case_results[:10]
            ],
            "targeted_search": [
                {
                    "term": term,
                    "results": [
                        {
                            "source": r.get("metadata", {}).get("source", "Unknown"),
                            "text": r.get("text", "")[:300]
                        }
                        for r in results[:3]
                    ]
                }
                for term, results in zip(legal_terms[:5], [targeted_results[i:i+3] for i in range(0, min(15, len(targeted_results)), 3)])
            ]
        }
    
    def _extract_legal_terms(self, text: str) -> List[str]:
        """Extract legal terms and concepts from text"""
        legal_keywords = [
            "motion", "dismiss", "summary judgment", "discovery", "evidence",
            "statute", "precedent", "jurisdiction", "venue", "standing",
            "breach", "contract", "tort", "negligence", "damages",
            "injunction", "relief", "remedy", "liability", "defense"
        ]
        
        found_terms = []
        text_lower = text.lower()
        for keyword in legal_keywords:
            if keyword in text_lower:
                found_terms.append(keyword)
        
        return found_terms
    
    async def _compare_motions(
        self,
        motion1_text: str, motion1_label: str, motion1_analysis: Dict, motion1_args: Dict,
        motion2_text: str, motion2_label: str, motion2_analysis: Dict, motion2_args: Dict,
        legal_authorities: Dict
    ) -> Dict:
        """Compare two motions and identify strengths/weaknesses"""
        
        prompt = f"""Compare these two opposing motions and identify:

1. Strengths of {motion1_label}
2. Weaknesses of {motion1_label}
3. Strengths of {motion2_label}
4. Weaknesses of {motion2_label}
5. Key legal issues in dispute
6. Which motion has stronger legal basis

{motion1_label}:
{motion1_text[:2000]}

{motion2_label}:
{motion2_text[:2000]}

Relevant Legal Authorities:
{json.dumps(legal_authorities.get('statutes', [])[:5], indent=2)}

Provide structured analysis."""
        
        try:
            comparison_text = ollama_service.generate(prompt, max_tokens=2048)
            
            # Parse structured comparison
            return {
                "motion1_strengths": self._extract_section(comparison_text, "strengths", motion1_label),
                "motion1_weaknesses": self._extract_section(comparison_text, "weaknesses", motion1_label),
                "motion2_strengths": self._extract_section(comparison_text, "strengths", motion2_label),
                "motion2_weaknesses": self._extract_section(comparison_text, "weaknesses", motion2_label),
                "key_issues": self._extract_section(comparison_text, "issues"),
                "raw_analysis": comparison_text
            }
        except Exception as e:
            logger.error(f"Error comparing motions: {e}")
            return {
                "error": str(e),
                "motion1_strengths": [],
                "motion1_weaknesses": [],
                "motion2_strengths": [],
                "motion2_weaknesses": [],
                "key_issues": []
            }
    
    def _extract_section(self, text: str, section_type: str, label: str = "") -> List[str]:
        """Extract specific section from comparison text"""
        # Simple extraction - can be enhanced
        lines = text.split('\n')
        section_lines = []
        in_section = False
        
        for line in lines:
            if section_type.lower() in line.lower() and (not label or label.lower() in line.lower()):
                in_section = True
                continue
            if in_section and line.strip():
                if line.strip().startswith(('-', '•', '1.', '2.')):
                    section_lines.append(line.strip())
                elif len(section_lines) > 0:
                    break
        
        return section_lines[:10]  # Limit to 10 items
    
    async def _generate_strategy(
        self,
        motion_text: str,
        motion_label: str,
        motion_analysis: Dict,
        opposing_motion_text: str,
        opposing_label: str,
        opposing_analysis: Dict,
        legal_authorities: Dict,
        jurisdiction: str
    ) -> Dict:
        """Generate strategic advice for winning the motion"""
        
        # Build comprehensive strategy prompt
        system_prompt = guardrails_service.build_system_prompt()
        
        strategy_prompt = f"""You are a legal strategist analyzing how to strengthen {motion_label} against {opposing_label}.

{motion_label} Analysis:
{json.dumps(motion_analysis, indent=2)[:2000]}

Opposing Motion ({opposing_label}):
{opposing_motion_text[:1500]}

Relevant Legal Authorities:
{json.dumps(legal_authorities.get('statutes', [])[:5], indent=2)}

Provide strategic recommendations to INCREASE THE ODDS OF WINNING {motion_label}:

1. **Strengthen Arguments:**
   - How to bolster weak points
   - Additional legal theories to consider
   - Statutory provisions to emphasize

2. **Counter Opposing Arguments:**
   - How to refute {opposing_label}'s strongest points
   - Legal precedents to cite against their position
   - Factual distinctions to highlight

3. **Tactical Recommendations:**
   - Additional evidence to gather
   - Witnesses to call
   - Expert testimony needed
   - Procedural maneuvers

4. **Legal Citations to Use:**
   - Specific statutes from the authorities provided
   - Case law that supports this motion
   - Precedents that distinguish from opposing cases

5. **Risk Mitigation:**
   - Potential weaknesses to address
   - Anticipated counter-arguments
   - How to prepare for them

Format as structured recommendations with actionable steps."""
        
        try:
            strategy_text = ollama_service.generate(
                prompt=strategy_prompt,
                system_prompt=system_prompt,
                max_tokens=3072
            )
            
            return {
                "recommendations": strategy_text,
                "key_points": self._extract_key_points(strategy_text),
                "legal_citations": self._extract_citations(strategy_text, legal_authorities),
                "action_items": self._extract_action_items(strategy_text)
            }
        except Exception as e:
            logger.error(f"Error generating strategy: {e}")
            return {
                "error": str(e),
                "recommendations": "Error generating strategy"
            }
    
    def _extract_key_points(self, text: str) -> List[str]:
        """Extract key strategic points"""
        lines = text.split('\n')
        key_points = []
        for line in lines:
            if any(marker in line for marker in ['**', '•', '-', '1.', '2.']):
                cleaned = line.strip().lstrip('•-1234567890. ').strip()
                if len(cleaned) > 20:
                    key_points.append(cleaned)
        return key_points[:10]
    
    def _extract_citations(self, text: str, legal_authorities: Dict) -> List[str]:
        """Extract legal citations mentioned"""
        citations = []
        for statute in legal_authorities.get('statutes', []):
            citation = statute.get('citation', '')
            if citation and citation in text:
                citations.append(citation)
        return citations[:10]
    
    def _extract_action_items(self, text: str) -> List[str]:
        """Extract actionable items"""
        action_keywords = ['gather', 'file', 'cite', 'argue', 'present', 'call', 'obtain']
        lines = text.split('\n')
        actions = []
        for line in lines:
            if any(keyword in line.lower() for keyword in action_keywords):
                cleaned = line.strip().lstrip('•-1234567890. ').strip()
                if len(cleaned) > 15:
                    actions.append(cleaned)
        return actions[:10]
    
    def _calculate_win_probabilities(
        self, motion1_analysis: Dict, motion2_analysis: Dict, comparison: Dict
    ) -> Dict:
        """Calculate win probability for each motion"""
        
        # Extract probabilities from individual analyses
        prob1 = motion1_analysis.get("prediction", {}).get("probability", 0.5)
        prob2 = motion2_analysis.get("prediction", {}).get("probability", 0.5)
        
        # Adjust based on comparison
        motion1_strength_count = len(comparison.get("motion1_strengths", []))
        motion1_weakness_count = len(comparison.get("motion1_weaknesses", []))
        motion2_strength_count = len(comparison.get("motion2_strengths", []))
        motion2_weakness_count = len(comparison.get("motion2_weaknesses", []))
        
        # Normalize probabilities (they should sum to ~1.0)
        total_strength = motion1_strength_count + motion2_strength_count
        total_weakness = motion1_weakness_count + motion2_weakness_count
        
        if total_strength > 0:
            adj_prob1 = (motion1_strength_count / total_strength) * 0.7 + prob1 * 0.3
            adj_prob2 = (motion2_strength_count / total_strength) * 0.7 + prob2 * 0.3
        else:
            adj_prob1 = prob1
            adj_prob2 = prob2
        
        # Normalize so they sum to 1.0
        total = adj_prob1 + adj_prob2
        if total > 0:
            adj_prob1 = adj_prob1 / total
            adj_prob2 = adj_prob2 / total
        
        return {
            "motion1": {
                "probability": round(adj_prob1, 2),
                "percentage": f"{round(adj_prob1 * 100, 1)}%",
                "confidence": "high" if abs(adj_prob1 - 0.5) > 0.2 else "medium"
            },
            "motion2": {
                "probability": round(adj_prob2, 2),
                "percentage": f"{round(adj_prob2 * 100, 1)}%",
                "confidence": "high" if abs(adj_prob2 - 0.5) > 0.2 else "medium"
            }
        }


comparative_motion_service = ComparativeMotionService()

