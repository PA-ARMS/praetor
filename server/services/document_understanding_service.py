"""
Document Understanding Service
Uses AI to analyze, understand, and extract key information from uploaded documents
"""
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

from server.services.ollama_service import ollama_service
from server.utils.logger import setup_logger

logger = setup_logger("document_understanding")

_LITIGATION_NAME_KEYS = (
    "motion",
    "nonsuit",
    "dismiss",
    "exhibit",
    "complaint",
    "brief",
    "response",
    "opposition",
    "pleading",
    "memorandum",
    "court",
    "petition",
    "judgment",
    "order",
    "notice",
)


def _filename_suggests_litigation(filename: str) -> bool:
    if not filename:
        return False
    low = filename.lower()
    return any(k in low for k in _LITIGATION_NAME_KEYS)


def _legal_analysis_excerpt(full_text: str, max_total: int = 10000) -> str:
    """Head + mid + tail so LLM analysis is not dominated by exhibit-only openers."""
    if len(full_text) <= max_total:
        return full_text
    third = max_total // 3
    head = full_text[:third]
    mid_start = max(0, len(full_text) // 2 - third // 2)
    mid = full_text[mid_start : mid_start + third]
    tail = full_text[-third:]
    return (
        head
        + "\n\n[... document middle omitted for analysis ...]\n\n"
        + mid
        + "\n\n[... omitted ...]\n\n"
        + tail
        + f"\n\n[Document truncated for analysis — full text has {len(full_text)} characters.]"
    )


class DocumentUnderstandingService:
    """Service for understanding and analyzing uploaded documents"""
    
    def __init__(self):
        self.logger = logger
    
    async def understand_document(
        self,
        text: str,
        filename: str,
        document_type: Optional[str] = None,
        pre_extracted_summary: Optional[str] = None,
        pre_extracted_entities: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Analyze and understand a document using AI

        When pre_extracted_summary or pre_extracted_entities are provided (from
        parallel models like BART/spaCy), they are used instead of LLM/regex.
        """
        try:
            # Use pre-extracted summary if available (from BART)
            if pre_extracted_summary and pre_extracted_summary.strip():
                summary = pre_extracted_summary.strip()
                analysis = {"summary": summary, "document_type": document_type or "Unknown", "key_points": []}
            else:
                if _filename_suggests_litigation(filename) and len(text) > 12000:
                    analysis_text = _legal_analysis_excerpt(text, max_total=10000)
                else:
                    analysis_text = text[:10000]
                    if len(text) > 10000:
                        analysis_text += (
                            "\n\n[Document truncated for analysis - full text available in corpus]"
                        )
                analysis = await self._analyze_with_ai(analysis_text, filename, document_type)

            # Use pre-extracted entities if available (from spaCy)
            if pre_extracted_entities and isinstance(pre_extracted_entities, dict):
                entities = self._merge_entities(pre_extracted_entities, self._extract_entities(text))
            else:
                entities = self._extract_entities(text)

            legal_concepts = self._identify_legal_concepts(text)

            metadata = {
                "summary": analysis.get("summary", ""),
                "document_type": analysis.get("document_type", document_type or "Unknown"),
                "key_points": analysis.get("key_points", []),
                "entities": entities,
                "legal_concepts": legal_concepts,
                "word_count": len(text.split()),
                "analyzed_at": datetime.now().isoformat(),
                "has_analysis": True
            }
            return metadata
            
        except Exception as e:
            self.logger.warning(f"Error understanding document {filename}: {e}")
            # Return basic metadata if analysis fails
            return {
                "summary": f"Document uploaded: {filename}",
                "document_type": document_type or "Unknown",
                "key_points": [],
                "entities": {},
                "legal_concepts": [],
                "word_count": len(text.split()),
                "analyzed_at": datetime.now().isoformat(),
                "has_analysis": False,
                "analysis_error": str(e)
            }
    
    async def _analyze_with_ai(
        self,
        text: str,
        filename: str,
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Use AI to analyze document content"""
        
        prompt = f"""Analyze this legal document and provide a structured understanding:

FILENAME: {filename}
DOCUMENT TYPE: {document_type or "Unknown"}

DOCUMENT TEXT (first 10000 chars):
{text}

Provide a structured analysis in the following format:

DOCUMENT_TYPE: [Type of document: Motion, Brief, Contract, Statute, Case Law, etc.]
SUMMARY: [2-3 sentence summary of what this document is about]
KEY_POINTS:
- [Key point 1]
- [Key point 2]
- [Key point 3]
LEGAL_TOPICS: [Comma-separated list of legal topics/concepts]
IMPORTANT_DATES: [Any important dates mentioned]
PARTIES: [Any parties mentioned: Plaintiff, Defendant, etc.]
"""

        system_prompt = """You are a legal document analyst. Analyze documents systematically and extract key information. Be concise and accurate."""

        try:
            response = await ollama_service.generate(
                prompt=prompt,
                system_prompt=system_prompt
            )
            
            # Parse response
            return self._parse_analysis_response(response)
            
        except Exception as e:
            self.logger.error(f"AI analysis failed: {e}")
            return {
                "summary": "Document analysis unavailable",
                "document_type": document_type or "Unknown",
                "key_points": []
            }
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse AI analysis response into structured format"""
        result = {
            "summary": "",
            "document_type": "Unknown",
            "key_points": [],
            "legal_topics": [],
            "important_dates": [],
            "parties": []
        }
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect section headers
            if line.startswith("DOCUMENT_TYPE:"):
                result["document_type"] = line.replace("DOCUMENT_TYPE:", "").strip()
            elif line.startswith("SUMMARY:"):
                result["summary"] = line.replace("SUMMARY:", "").strip()
                current_section = "summary"
            elif line.startswith("KEY_POINTS:"):
                current_section = "key_points"
            elif line.startswith("LEGAL_TOPICS:"):
                topics = line.replace("LEGAL_TOPICS:", "").strip()
                result["legal_topics"] = [t.strip() for t in topics.split(",") if t.strip()]
            elif line.startswith("IMPORTANT_DATES:"):
                dates = line.replace("IMPORTANT_DATES:", "").strip()
                result["important_dates"] = [d.strip() for d in dates.split(",") if d.strip()]
            elif line.startswith("PARTIES:"):
                parties = line.replace("PARTIES:", "").strip()
                result["parties"] = [p.strip() for p in parties.split(",") if p.strip()]
            elif current_section == "key_points" and line.startswith("-"):
                result["key_points"].append(line.lstrip("- ").strip())
            elif current_section == "summary" and result["summary"]:
                result["summary"] += " " + line
        
        # Clean up
        result["summary"] = result["summary"].strip()
        result["key_points"] = [kp for kp in result["key_points"] if kp]
        
        return result
    
    def _merge_entities(self, pre_extracted: Dict, regex_entities: Dict) -> Dict[str, List[str]]:
        """Merge pre-extracted entities (spaCy) with regex fallback. Pre-extracted takes precedence."""
        result = {}
        for key in ["dates", "parties", "case_numbers", "statutes", "courts"]:
            pre = pre_extracted.get(key, [])
            reg = regex_entities.get(key, [])
            combined = list(dict.fromkeys((pre or []) + (reg or [])))[:10]
            result[key] = combined
        return result

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from document text"""
        entities = {
            "dates": [],
            "parties": [],
            "case_numbers": [],
            "statutes": [],
            "courts": []
        }
        
        # Extract dates (various formats)
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',  # Month DD, YYYY
            r'\b\d{4}\b'  # Year only
        ]
        for pattern in date_patterns:
            dates = re.findall(pattern, text, re.IGNORECASE)
            entities["dates"].extend(dates)
        
        # Extract case numbers (common patterns)
        case_patterns = [
            r'Case\s+No\.?\s*:?\s*([A-Z0-9-]+)',
            r'Civil\s+Action\s+No\.?\s*:?\s*([A-Z0-9-]+)',
            r'Docket\s+No\.?\s*:?\s*([A-Z0-9-]+)'
        ]
        for pattern in case_patterns:
            cases = re.findall(pattern, text, re.IGNORECASE)
            entities["case_numbers"].extend(cases)
        
        # Extract statutes (Virginia Code, USC, etc.)
        statute_patterns = [
            r'Va\.?\s+Code\s+§\s*(\d+\.\d+-\d+)',
            r'Virginia\s+Code\s+§\s*(\d+\.\d+-\d+)',
            r'(\d+)\s+U\.?S\.?C\.?\s+§\s*(\d+)',
            r'(\d+)\s+U\.?S\.?C\.?\s+(\d+)'
        ]
        for pattern in statute_patterns:
            statutes = re.findall(pattern, text, re.IGNORECASE)
            entities["statutes"].extend([str(s) if isinstance(s, tuple) else s for s in statutes])
        
        # Extract parties (Plaintiff, Defendant patterns)
        party_patterns = [
            r'Plaintiff[s]?:?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'Defendant[s]?:?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'Petitioner[s]?:?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'Respondent[s]?:?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        ]
        for pattern in party_patterns:
            parties = re.findall(pattern, text, re.IGNORECASE)
            entities["parties"].extend(parties)
        
        # Extract courts
        court_patterns = [
            r'(Circuit\s+Court\s+of\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'(Supreme\s+Court\s+of\s+Virginia)',
            r'(Court\s+of\s+Appeals\s+of\s+Virginia)',
            r'(United\s+States\s+District\s+Court)'
        ]
        for pattern in court_patterns:
            courts = re.findall(pattern, text, re.IGNORECASE)
            entities["courts"].extend(courts)
        
        # Remove duplicates and limit
        for key in entities:
            entities[key] = list(set(entities[key]))[:10]  # Limit to 10 per type
        
        return entities
    
    def _identify_legal_concepts(self, text: str) -> List[str]:
        """Identify legal concepts mentioned in document"""
        legal_concepts = []
        text_lower = text.lower()
        
        # Common legal concepts
        concept_keywords = {
            "Contract": ["contract", "agreement", "breach", "consideration", "offer", "acceptance"],
            "Tort": ["negligence", "tort", "duty", "causation", "damages", "liability"],
            "Criminal": ["criminal", "felony", "misdemeanor", "indictment", "arraignment"],
            "Family Law": ["divorce", "custody", "alimony", "child support", "visitation"],
            "Property": ["property", "real estate", "deed", "title", "easement"],
            "Employment": ["employment", "discrimination", "wrongful termination", "wage"],
            "Personal Injury": ["personal injury", "accident", "injury", "medical malpractice"],
            "Business": ["corporation", "llc", "partnership", "business entity"],
            "Estate": ["estate", "will", "probate", "trust", "inheritance"],
            "Immigration": ["immigration", "visa", "citizenship", "deportation"]
        }
        
        for concept, keywords in concept_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                legal_concepts.append(concept)
        
        return legal_concepts
    
    async def generate_summary(self, text: str, max_length: int = 200) -> str:
        """Generate a concise summary of the document"""
        try:
            # Use first 5000 chars for summary
            summary_text = text[:5000]
            if len(text) > 5000:
                summary_text += "\n\n[Document continues...]"
            
            prompt = f"""Provide a concise summary of this document in {max_length} words or less:

{summary_text}

Summary:"""

            response = await ollama_service.generate(
                prompt=prompt,
                system_prompt="You are a legal document summarizer. Provide concise, accurate summaries."
            )
            
            # Limit to max_length words
            words = response.split()
            if len(words) > max_length:
                return " ".join(words[:max_length]) + "..."
            return response.strip()
            
        except Exception as e:
            self.logger.warning(f"Summary generation failed: {e}")
            # Fallback: first sentence or first 200 chars
            sentences = text.split('.')
            if sentences:
                return sentences[0][:max_length]
            return text[:max_length]


# Singleton instance
document_understanding_service = DocumentUnderstandingService()

