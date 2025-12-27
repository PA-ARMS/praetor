"""
Reasoning Validation Service
Captures and compares AI reasoning against official court reasoning.
"""
import json
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from server.services.ollama_service import ollama_service
from server.utils.logger import setup_logger


class ReasoningValidationService:
    def __init__(self):
        self.logger = setup_logger("reasoning_validation")
        self.section_markers = [
            "analysis", "discussion", "reasoning", "opinion", "holding",
            "legal analysis", "application", "standard of review"
        ]
        self.stopwords = {
            "the", "and", "that", "with", "from", "this", "which",
            "shall", "court", "case", "because", "therefore", "wherefore",
            "plaintiff", "defendant", "judge", "holding"
        }

    def extract_ground_truth_reasoning(self, case_data: Dict, case_text: str) -> Optional[Dict]:
        """Extract an official reasoning snippet and citation."""
        if not case_text:
            return None

        reasoning_excerpt = self._extract_reasoning_section(case_text)
        if not reasoning_excerpt:
            reasoning_excerpt = case_text[:1500]

        citation = self._extract_citation(case_data)
        return {
            "excerpt": reasoning_excerpt.strip(),
            "citation": citation
        }

    async def generate_model_reasoning(
        self,
        case_facts: str,
        predicted_outcome: str,
        similar_scenarios: List[Dict]
    ) -> Dict:
        """Ask the model to articulate its reasoning."""
        scenario_summary = []
        for scenario in similar_scenarios[:3]:
            scenario_summary.append(
                f"- {scenario.get('case_name', 'Similar Case')}: outcome={scenario.get('outcome', 'Unknown')}, "
                f"similarity={scenario.get('similarity_score', 0)}"
            )

        prompt = f"""You predicted the outcome "{predicted_outcome}" for the following legal scenario.

FACT SUMMARY (trimmed):
{case_facts[:1500]}

TOP SIMILAR CASES:
{chr(10).join(scenario_summary) if scenario_summary else "None"}

Explain WHY this outcome is legally justified.
Respond in the following structured format:

THESIS: <one sentence summarizing why the outcome follows>
SUPPORTING FACTORS:
- <Factor 1>
- <Factor 2>
- <Factor 3>
KEY CITATIONS OR AUTHORITIES TO USE:
- <Citation 1>
- <Citation 2>
"""
        reasoning_text = await ollama_service.generate(
            prompt=prompt,
            system_prompt="You are a Virginia litigator. Explain the legal reasoning clearly and cite controlling authority."
        )

        return self._parse_model_reasoning(reasoning_text)

    def compare_reasoning(self, ground_truth: Dict, model_reasoning: Dict) -> Dict:
        """Compare model reasoning to the court's reasoning excerpt."""
        ground_text = ground_truth.get("excerpt", "")
        model_text = model_reasoning.get("text", "")

        fidelity = self._similarity_score(ground_text, model_text)
        completeness, missing, extra = self._coverage_score(
            ground_text,
            model_text
        )
        citation_alignment = self._citation_score(
            ground_truth.get("citation"),
            model_reasoning.get("citations", [])
        )

        score = (fidelity * 0.5) + (completeness * 0.3) + (citation_alignment * 0.2)
        curiosity_prompts = self._build_curiosity_prompts(missing, ground_truth.get("citation"))

        return {
            "scores": {
                "overall": round(score * 100, 1),
                "fidelity": round(fidelity * 100, 1),
                "completeness": round(completeness * 100, 1),
                "citation_alignment": round(citation_alignment * 100, 1)
            },
            "missing_elements": missing,
            "extra_elements": extra,
            "curiosity_prompts": curiosity_prompts,
            "is_gap": (score < 0.7) or (completeness < 0.6) or (citation_alignment < 0.5)
        }

    async def evaluate_reasoning(
        self,
        case_data: Dict,
        case_text: str,
        case_facts: str,
        predicted_outcome: str,
        similar_scenarios: List[Dict]
    ) -> Optional[Dict]:
        """Full pipeline: capture ground truth, model reasoning, and comparison."""
        ground_truth = self.extract_ground_truth_reasoning(case_data, case_text)
        if not ground_truth:
            self.logger.debug("No ground-truth reasoning available for case_id=%s", case_data.get("id"))
            return None

        model_reasoning = await self.generate_model_reasoning(
            case_facts=case_facts,
            predicted_outcome=predicted_outcome,
            similar_scenarios=similar_scenarios
        )

        comparison = self.compare_reasoning(ground_truth, model_reasoning)

        recommendations = []
        if comparison["is_gap"]:
            recommendations.append(
                "Cross-check reasoning against official holding and cite the controlling authority explicitly."
            )
            if comparison["scores"]["citation_alignment"] < 60:
                recommendations.append("Align citations with the court's cited authority before finalizing reasoning.")
            if comparison["scores"]["completeness"] < 60:
                recommendations.append("Address the missing legal factors highlighted in the court's reasoning.")

        return {
            "ground_truth": ground_truth,
            "model_reasoning": model_reasoning,
            "comparison": comparison,
            "recommendations": recommendations
        }

    # --- Helper methods ---

    def _extract_reasoning_section(self, text: str) -> str:
        """Extract the likely reasoning/analysis portion of an opinion."""
        lower_text = text.lower()
        for marker in self.section_markers:
            idx = lower_text.find(marker)
            if idx != -1:
                snippet = text[idx:idx + 2000]
                return snippet
        # Fallback: middle portion of the opinion
        midpoint = len(text) // 2
        return text[midpoint: midpoint + 2000]

    def _extract_citation(self, case_data: Dict) -> str:
        """Best-effort citation extraction from case metadata."""
        citations = case_data.get("citations") or case_data.get("citation") or case_data.get("reporter")
        if isinstance(citations, list) and citations:
            first = citations[0]
            if isinstance(first, dict):
                return first.get("cite", "")
            return str(first)
        if isinstance(citations, dict):
            return citations.get("cite", "")
        if isinstance(citations, str):
            return citations
        return case_data.get("name", "") or case_data.get("case_name", "")

    def _parse_model_reasoning(self, reasoning_text: str) -> Dict:
        """Parse the LLM response into structured fields."""
        thesis = ""
        supporting_factors: List[str] = []
        citations: List[str] = []

        current = None
        for raw_line in reasoning_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            header = line.lower()
            if header.startswith("thesis"):
                current = "thesis"
                thesis = line.split(":", 1)[1].strip() if ":" in line else line
                continue
            if header.startswith("supporting factors"):
                current = "factors"
                continue
            if header.startswith("key citations"):
                current = "citations"
                continue

            if current == "factors" and line.startswith("-"):
                supporting_factors.append(line.lstrip("- ").strip())
            elif current == "citations" and line.startswith("-"):
                citations.append(line.lstrip("- ").strip())
            elif current == "thesis":
                thesis += " " + line

        return {
            "text": reasoning_text.strip(),
            "thesis": thesis.strip(),
            "supporting_factors": supporting_factors,
            "citations": citations
        }

    def _similarity_score(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _coverage_score(self, ground_text: str, model_text: str):
        ground_keywords = self._extract_keywords(ground_text)
        model_lower = model_text.lower()

        if not ground_keywords:
            return 1.0, [], []

        missing = []
        matched = 0
        for kw in ground_keywords:
            if kw in model_lower:
                matched += 1
            else:
                missing.append(kw)

        completeness = matched / len(ground_keywords)
        extra = [
            kw for kw in self._extract_keywords(model_text)
            if kw not in ground_keywords
        ][:5]

        return completeness, missing[:5], extra

    def _citation_score(self, official_citation: Optional[str], model_citations: List[str]) -> float:
        if not official_citation:
            return 0.5 if model_citations else 0.0

        official_clean = official_citation.lower().strip()
        for cite in model_citations:
            if official_clean in cite.lower():
                return 1.0
        return 0.3 if model_citations else 0.0

    def _build_curiosity_prompts(self, missing: List[str], citation: Optional[str]) -> List[str]:
        prompts = []
        if missing:
            prompts.append(
                f"What role did {missing[0]} play in the court's reasoning, and how should it influence future predictions?"
            )
        if citation:
            prompts.append(f"How does {citation} shape the legal outcome in similar fact patterns?")
        return prompts

    def _extract_keywords(self, text: str) -> List[str]:
        tokens = re.findall(r"[A-Za-z]{5,}", text.lower())
        keywords = []
        for token in tokens:
            if token in self.stopwords:
                continue
            keywords.append(token)
        # Limit to top unique keywords to keep scoring stable
        seen = set()
        filtered = []
        for token in keywords:
            if token not in seen:
                filtered.append(token)
                seen.add(token)
            if len(filtered) >= 10:
                break
        return filtered


reasoning_validation_service = ReasoningValidationService()


