"""
Document to Scenario Service
Processes uploaded legal documents into scenarios for the learning system
"""
from typing import Dict, Optional, List
from datetime import datetime
import re

from server.services.outcome_extraction_service import outcome_extraction_service
from server.services.scenario_service import scenario_service
from server.services.document_understanding_service import document_understanding_service
from server.utils.logger import setup_logger

logger = setup_logger("document_to_scenario")


class DocumentToScenarioService:
    """Service to convert uploaded documents into learning scenarios"""
    
    def __init__(self):
        self.logger = logger
    
    async def process_document_as_scenario(
        self,
        text: str,
        filename: str,
        jurisdiction: str = "Virginia",
        understanding: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Process an uploaded document as a scenario for the learning system
        
        Returns:
            Dict with scenario information if successfully processed, None otherwise
        """
        try:
            # Use document understanding if not provided
            if not understanding:
                understanding = await document_understanding_service.understand_document(
                    text=text,
                    filename=filename
                )
            
            # Check if document is suitable for scenario processing
            # Look for legal case indicators
            is_legal_case = self._is_legal_case_document(text, understanding)
            
            if not is_legal_case:
                self.logger.debug(f"Document {filename} does not appear to be a legal case, skipping scenario processing")
                return None
            
            # Extract facts (without outcome)
            facts = outcome_extraction_service.extract_facts_without_outcome(text)
            if not facts or len(facts.strip()) < 100:
                self.logger.debug(f"Document {filename} has insufficient facts for scenario")
                return None
            
            # Extract outcome
            outcome = outcome_extraction_service.extract_outcome(text, {})
            if outcome == "Unknown":
                # Try to infer outcome from understanding
                outcome = self._infer_outcome_from_understanding(understanding, text)
                if outcome == "Unknown":
                    self.logger.debug(f"Document {filename} has unknown outcome, skipping scenario")
                    return None
            
            # Extract metadata
            metadata = self._build_scenario_metadata(
                text=text,
                filename=filename,
                jurisdiction=jurisdiction,
                understanding=understanding,
                outcome=outcome
            )
            
            # Generate scenario ID
            scenario_id = f"upload_{filename}_{int(datetime.now().timestamp())}"
            scenario_id = re.sub(r'[^a-zA-Z0-9_-]', '_', scenario_id)
            
            # Add to scenario database
            await scenario_service.add_scenario(
                facts=facts[:2000],  # Limit to 2000 chars
                outcome=outcome,
                metadata=metadata,
                scenario_id=scenario_id
            )
            
            self.logger.info(f"Processed document {filename} as scenario: {scenario_id}")
            
            return {
                "scenario_id": scenario_id,
                "outcome": outcome,
                "case_type": metadata.get("case_type", "Unknown"),
                "jurisdiction": metadata.get("jurisdiction", jurisdiction),
                "facts_length": len(facts)
            }
            
        except Exception as e:
            self.logger.warning(f"Error processing document {filename} as scenario: {e}")
            return None
    
    def _is_legal_case_document(self, text: str, understanding: Dict) -> bool:
        """Determine if document is a legal case suitable for scenario processing"""
        text_lower = text.lower()
        
        # Check document type from understanding
        doc_type = understanding.get("document_type", "").lower()
        if any(keyword in doc_type for keyword in ["case", "motion", "brief", "opinion", "decision", "order"]):
            return True
        
        # Check for legal case indicators in text
        case_indicators = [
            "plaintiff", "defendant", "petitioner", "respondent",
            "case no", "civil action", "docket",
            "court", "judge", "motion", "order", "opinion",
            "granted", "denied", "affirmed", "reversed",
            "judgment", "verdict", "ruling"
        ]
        
        indicator_count = sum(1 for indicator in case_indicators if indicator in text_lower)
        
        # If 3+ indicators found, likely a legal case
        if indicator_count >= 3:
            return True
        
        # Check understanding entities
        entities = understanding.get("entities", {})
        if entities.get("parties") or entities.get("case_numbers") or entities.get("courts"):
            return True
        
        # Check legal concepts
        legal_concepts = understanding.get("legal_concepts", [])
        if legal_concepts:
            return True
        
        return False
    
    def _infer_outcome_from_understanding(self, understanding: Dict, text: str) -> str:
        """Try to infer outcome from document understanding"""
        text_lower = text.lower()
        
        # Check key points for outcome indicators
        key_points = understanding.get("key_points", [])
        for point in key_points:
            point_lower = point.lower()
            if any(word in point_lower for word in ["granted", "grant"]):
                return "Defendant Win"  # Motion granted typically favors defendant
            elif any(word in point_lower for word in ["denied", "deny"]):
                return "Plaintiff Win"  # Motion denied typically favors plaintiff
            elif "affirmed" in point_lower:
                # Check if it's affirming plaintiff or defendant win
                if "plaintiff" in point_lower:
                    return "Plaintiff Win"
                elif "defendant" in point_lower:
                    return "Defendant Win"
            elif "reversed" in point_lower:
                return "Reversed"
        
        # Check text for outcome patterns
        if re.search(r"motion.*granted", text_lower):
            return "Defendant Win"
        elif re.search(r"motion.*denied", text_lower):
            return "Plaintiff Win"
        elif re.search(r"judgment.*for.*plaintiff", text_lower):
            return "Plaintiff Win"
        elif re.search(r"judgment.*for.*defendant", text_lower):
            return "Defendant Win"
        elif re.search(r"dismissed", text_lower):
            return "Dismissed"
        
        return "Unknown"
    
    def _build_scenario_metadata(
        self,
        text: str,
        filename: str,
        jurisdiction: str,
        understanding: Dict,
        outcome: str
    ) -> Dict:
        """Build metadata for scenario"""
        
        # Get case type from understanding or infer
        case_type = understanding.get("document_type", "Unknown")
        if case_type == "Unknown":
            # Infer from legal concepts
            legal_concepts = understanding.get("legal_concepts", [])
            if legal_concepts:
                case_type = legal_concepts[0]
            else:
                # Infer from text
                text_lower = text.lower()
                if any(term in text_lower for term in ["contract", "breach", "agreement"]):
                    case_type = "Contract"
                elif any(term in text_lower for term in ["tort", "negligence", "injury"]):
                    case_type = "Tort"
                elif any(term in text_lower for term in ["criminal", "felony", "misdemeanor"]):
                    case_type = "Criminal"
                else:
                    case_type = "General"
        
        # Extract entities
        entities = understanding.get("entities", {})
        
        # Build metadata
        metadata = {
            "outcome": outcome,
            "case_type": case_type,
            "jurisdiction": jurisdiction,
            "source": "uploaded_document",
            "filename": filename,
            "upload_date": datetime.now().isoformat(),
            "case_name": understanding.get("summary", filename)[:200] if understanding.get("summary") else filename[:200]
        }
        
        # Add entities if available
        if entities.get("case_numbers"):
            metadata["case_number"] = entities["case_numbers"][0]
        if entities.get("courts"):
            metadata["court"] = entities["courts"][0]
        if entities.get("statutes"):
            metadata["statutes"] = ", ".join(entities["statutes"][:3])  # Top 3
        
        # Add key points as factors
        key_points = understanding.get("key_points", [])
        if key_points:
            metadata["key_factors"] = key_points[:5]  # Top 5 key points
        
        # Remove None and empty values
        metadata = {k: v for k, v in metadata.items() if v and v != "Unknown"}
        
        return metadata


# Singleton instance
document_to_scenario_service = DocumentToScenarioService()

