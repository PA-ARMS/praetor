"""
Process downloaded case data into scenario database
Extracts facts, outcomes, and metadata from case files
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
import asyncio
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.scenario_service import scenario_service
from server.config import settings


def extract_scenario_from_case(case_data: Dict) -> Optional[Dict]:
    """
    Extract scenario information from a case JSON file (V4 API format)
    Returns dict with 'facts' and 'metadata' keys, or None if extraction fails
    """
    try:
        # Extract facts from plain_text (V4 API structure)
        facts = ""
        if case_data.get("plain_text"):
            # Get first 2000 characters as facts summary
            facts = case_data["plain_text"][:2000]
        elif case_data.get("snippet"):
            facts = case_data["snippet"]
        
        if not facts or len(facts.strip()) < 50:
            return None
        
        # Extract outcome from plain_text by looking for keywords
        outcome = "Unknown"
        plain_text_lower = facts.lower()
        
        # Look for outcome indicators in the text
        if any(word in plain_text_lower for word in ["granted", "motion granted", "dismissed with prejudice"]):
            outcome = "Defendant Win"
        elif any(word in plain_text_lower for word in ["denied", "motion denied", "affirmed"]):
            outcome = "Plaintiff Win"
        elif "dismissed" in plain_text_lower:
            outcome = "Dismissed"
        elif "reversed" in plain_text_lower:
            outcome = "Reversed"
        elif "remanded" in plain_text_lower:
            outcome = "Remanded"
        elif "settlement" in plain_text_lower or "settled" in plain_text_lower:
            outcome = "Settlement"
        
        # Try to get case name from plain_text
        case_name = "Unknown"
        if case_data.get("plain_text"):
            lines = case_data["plain_text"].split("\n")[:5]
            for line in lines:
                if "v." in line or "vs." in line or "versus" in line.lower():
                    case_name = line.strip()[:100]
                    break
        
        # Determine case type from text content
        case_type = "Unknown"
        text_lower = facts.lower()
        if any(term in text_lower for term in ["contract", "breach of contract", "agreement"]):
            case_type = "Contract"
        elif any(term in text_lower for term in ["tort", "negligence", "personal injury"]):
            case_type = "Tort"
        elif any(term in text_lower for term in ["criminal", "indictment", "guilty", "sentencing"]):
            case_type = "Criminal"
        elif any(term in text_lower for term in ["family", "divorce", "custody", "support"]):
            case_type = "Family Law"
        elif any(term in text_lower for term in ["employment", "discrimination", "wrongful termination"]):
            case_type = "Employment"
        elif any(term in text_lower for term in ["property", "real estate", "landlord", "tenant"]):
            case_type = "Property"
        
        # Extract jurisdiction and court from cluster or type
        jurisdiction = "Unknown"
        court_level = "Unknown"
        
        # V4 API: type field indicates court level
        opinion_type = case_data.get("type", "")
        if "supreme" in opinion_type.lower() or "scotus" in opinion_type.lower():
            court_level = "Supreme Court"
        elif "appeals" in opinion_type.lower() or "circuit" in opinion_type.lower():
            court_level = "Court of Appeals"
        elif "district" in opinion_type.lower() or "trial" in opinion_type.lower():
            court_level = "District/Trial Court"
        
        # Try to infer jurisdiction from text
        if "virginia" in facts.lower() or "va" in facts.lower():
            jurisdiction = "Virginia"
        elif "federal" in facts.lower() or "united states" in facts.lower():
            jurisdiction = "Federal"
        
        # Extract metadata (ChromaDB doesn't allow None values)
        date_val = case_data.get("date_created") or case_data.get("date_modified") or ""
        
        metadata = {
            "outcome": outcome,
            "case_type": case_type,
            "jurisdiction": jurisdiction,
            "court_level": court_level,
            "date": str(date_val) if date_val else "",
            "citation": "",  # V4 API may not have direct citation
            "case_name": case_name,
            "opinion_type": opinion_type,
        }
        
        # Extract additional info if available (only add if not None)
        if case_data.get("cluster_id"):
            metadata["cluster_id"] = str(case_data["cluster_id"])
        
        # Remove any None values and convert lists to strings
        metadata = {k: (", ".join(v) if isinstance(v, list) else v) for k, v in metadata.items() if v is not None}
        
        return {
            "facts": facts,
            "metadata": metadata
        }
    except Exception as e:
        print(f"Error extracting scenario: {e}")
        import traceback
        traceback.print_exc()
        return None


async def process_case_files(case_dir: Path, limit: Optional[int] = None):
    """Process all case JSON files in directory"""
    case_files = list(case_dir.glob("case_*.json"))
    
    if limit:
        case_files = case_files[:limit]
    
    print(f"Processing {len(case_files)} case files...")
    
    processed = 0
    failed = 0
    
    for case_file in case_files:
        try:
            with open(case_file, "r", encoding="utf-8") as f:
                case_data = json.load(f)
            
            scenario = extract_scenario_from_case(case_data)
            
            if scenario:
                await scenario_service.add_scenario(
                    facts=scenario["facts"],
                    outcome=scenario["metadata"]["outcome"],
                    metadata=scenario["metadata"],
                    scenario_id=f"case_{case_file.stem}"
                )
                processed += 1
                if processed % 10 == 0:
                    print(f"Processed {processed} scenarios...")
            else:
                failed += 1
        except Exception as e:
            print(f"Error processing {case_file}: {e}")
            failed += 1
    
    print(f"\nProcessing complete!")
    print(f"  Processed: {processed}")
    print(f"  Failed: {failed}")
    
    # Get final stats
    stats = scenario_service.get_collection_stats()
    print(f"  Total scenarios in database: {stats['total_scenarios']}")


async def main():
    """Main processing function"""
    if not settings.SCENARIO_DB_ENABLED:
        print("ERROR: Scenario database is not enabled")
        print("Set SCENARIO_DB_ENABLED=True in server/.env or environment")
        return
    
    case_dir = Path("data/scenarios/courtlistener")
    
    if not case_dir.exists():
        print(f"ERROR: Case directory not found: {case_dir}")
        print("Run download_cases.py first to download case data")
        return
    
    import sys
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            print(f"Limiting processing to {limit} cases")
        except ValueError:
            print("Usage: python process_scenarios.py [limit]")
            return
    
    await process_case_files(case_dir, limit=limit)


if __name__ == "__main__":
    asyncio.run(main())

