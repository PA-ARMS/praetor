"""
Batch Process Scenarios - Process downloaded cases in batches
Can run in parallel with download to process cases as they arrive
"""
import json
import asyncio
import sys
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.scenario_service import scenario_service
from server.services.outcome_extraction_service import outcome_extraction_service
from server.config import settings

PROCESSED_FILE = Path("data/scenarios/.processed_cases.json")
# Support multiple case sources
CASE_DIRS = [
    Path("data/scenarios/courtlistener"),  # CourtListener cases
    Path("data/scenarios/cap"),            # CAP (Caselaw Access Project) cases
]
BATCH_SIZE = 100  # Process in batches


def load_processed():
    """Load list of already processed case IDs"""
    if PROCESSED_FILE.exists():
        try:
            with open(PROCESSED_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get("processed_ids", []))
        except:
            pass
    return set()


def save_processed(processed_ids: set, stats: Dict, progress_info: Optional[Dict] = None):
    """Save processed case IDs and stats"""
    data = {
        "processed_ids": list(processed_ids),
        "total_processed": len(processed_ids),
        "last_update": datetime.now().isoformat(),
        "stats": stats
    }
    
    # Add progress information if provided
    if progress_info:
        data["progress"] = progress_info
    
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def extract_scenario_from_case(case_data: Dict) -> Optional[Dict]:
    """Extract scenario data from case JSON"""
    try:
        # Get text content - CourtListener format
        facts = case_data.get("plain_text", "")
        if not facts or len(facts.strip()) < 100:
            # Try other text fields
            facts = case_data.get("html_with_citations", "") or \
                   case_data.get("html", "") or \
                   case_data.get("html_lawbox", "")
        
        # CAP format: extract from casebody opinions
        if not facts or len(facts.strip()) < 100:
            if case_data.get("casebody"):
                casebody = case_data["casebody"]
                opinion_texts = []
                if casebody.get("opinions"):
                    for opinion in casebody["opinions"]:
                        if opinion.get("text"):
                            opinion_texts.append(opinion["text"])
                if casebody.get("head_matter"):
                    opinion_texts.insert(0, casebody["head_matter"])
                if opinion_texts:
                    facts = "\n\n".join(opinion_texts)
        
        if not facts or len(facts.strip()) < 100:
            return None
        
        # Extract facts without outcome
        facts_clean = outcome_extraction_service.extract_facts_without_outcome(facts)
        if not facts_clean or len(facts_clean.strip()) < 100:
            return None
        
        # Extract outcome
        outcome = outcome_extraction_service.extract_outcome(facts, case_data)
        if outcome == "Unknown":
            return None
        
        # Extract metadata
        case_name = case_data.get("case_name") or case_data.get("name", "Unknown")
        case_id = str(case_data.get("id", ""))
        
        # Infer case type from text
        case_type = "Unknown"
        facts_lower = facts_clean.lower()
        if any(term in facts_lower for term in ["contract", "breach", "agreement"]):
            case_type = "Contract"
        elif any(term in facts_lower for term in ["tort", "negligence", "injury", "damages"]):
            case_type = "Tort"
        elif any(term in facts_lower for term in ["criminal", "felony", "misdemeanor"]):
            case_type = "Criminal"
        elif any(term in facts_lower for term in ["family", "divorce", "custody"]):
            case_type = "Family"
        elif any(term in facts_lower for term in ["property", "real estate", "land"]):
            case_type = "Property"
        
        # Get jurisdiction
        jurisdiction = "Virginia"
        # Check jurisdiction field (CAP format)
        if case_data.get("jurisdiction"):
            juris = case_data["jurisdiction"]
            if isinstance(juris, dict):
                juris_name = juris.get("name", "").lower()
                if "virginia" in juris_name or "va" in juris_name:
                    jurisdiction = "Virginia"
                elif "federal" in juris_name or "us" in juris_name:
                    jurisdiction = "Federal"
        # Check court field (CourtListener format)
        court = case_data.get("court", "")
        if isinstance(court, dict):
            court_name = court.get("name", "").lower() or court.get("name_abbreviation", "").lower()
            if "federal" in court_name or "district" in court_name:
                jurisdiction = "Federal"
        
        # Get court level
        court_level = "Unknown"
        if isinstance(court, dict):
            court_name = court.get("name", "").lower()
            if "supreme" in court_name:
                court_level = "Supreme Court"
            elif "appeals" in court_name or "appellate" in court_name:
                court_level = "Appeals Court"
            elif "circuit" in court_name:
                court_level = "Circuit Court"
            elif "district" in court_name:
                court_level = "District Court"
        
        # Get date
        date_val = case_data.get("date_filed") or case_data.get("date_created") or case_data.get("decision_date", "")
        
        # Get citation
        citation = case_data.get("citation", "") or ""
        if isinstance(citation, list) and citation:
            # CourtListener format: list of citation strings
            citation = citation[0]
        elif isinstance(citation, list) and citation and isinstance(citation[0], dict):
            # CAP format: list of citation objects
            citation = citation[0].get("cite", "")
        
        # If no citation in metadata, extract from text
        if not citation and facts:
            import re
            # Look for Virginia Code citations (e.g., "§ 18.2-57.2" or "18.2-57.2")
            va_cite_match = re.search(r'§?\s*(\d+\.\d+-\d+\.?\d*)', facts[:3000])
            if va_cite_match:
                citation = f"§ {va_cite_match.group(1)}"
            # Look for case citations (e.g., "123 Va. 456" or "456 S.E.2d 123")
            elif not citation:
                case_cite_match = re.search(r'(\d+\s+Va\.?\s+\d+)', facts[:3000])
                if case_cite_match:
                    citation = case_cite_match.group(1)
                # Also check for S.E.2d format (Virginia Supreme Court)
                elif re.search(r'\d+\s+S\.E\.2d\s+\d+', facts[:3000]):
                    se_cite_match = re.search(r'(\d+\s+S\.E\.2d\s+\d+)', facts[:3000])
                    if se_cite_match:
                        citation = se_cite_match.group(1)
        
        # Build metadata (ChromaDB doesn't allow None values)
        metadata = {
            "outcome": outcome,
            "case_type": case_type,
            "jurisdiction": jurisdiction,
            "court_level": court_level,
            "date": str(date_val) if date_val else "",
            "citation": str(citation) if citation else "",
            "case_name": case_name[:200],
            "case_id": case_id,
        }
        
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v and v != "Unknown"}
        
        return {
            "facts": facts_clean[:6000],  # Keep more detail for better matching (increased from 2000)
            "metadata": metadata,
            "scenario_id": f"case_{case_id}"
        }
        
    except Exception as e:
        print(f"Error extracting scenario: {e}")
        return None


async def process_case_file(case_file: Path) -> Optional[Dict]:
    """Process a single case file"""
    try:
        with open(case_file, 'r', encoding='utf-8') as f:
            case_data = json.load(f)
        
        scenario = extract_scenario_from_case(case_data)
        if not scenario:
            # Debug: why did extraction fail?
            facts = case_data.get("plain_text", "") or case_data.get("html_with_citations", "") or case_data.get("html", "")
            if not facts or len(facts.strip()) < 100:
                # No sufficient text
                return None
            outcome = outcome_extraction_service.extract_outcome(facts, case_data)
            if outcome == "Unknown":
                # Couldn't determine outcome
                return None
            # Otherwise, facts extraction might have failed
            return None
        
        # Add to scenario database
        try:
            await scenario_service.add_scenario(
                facts=scenario["facts"],
                outcome=scenario["metadata"]["outcome"],
                metadata=scenario["metadata"],
                scenario_id=scenario["scenario_id"]
            )
        except Exception as e:
            # If it's a duplicate ID error, that's okay - skip it
            if "existing" in str(e).lower() or "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                # Don't count as success, just skip silently
                return None
            raise  # Re-raise other errors
        
        return scenario
        
    except json.JSONDecodeError as e:
        print(f"  Invalid JSON in {case_file.name}: {e}")
        return None
    except Exception as e:
        print(f"  Error processing {case_file.name}: {e}")
        import traceback
        print(f"  Traceback: {traceback.format_exc()}")
        return None


async def process_batch(case_files: List[Path], processed_ids: set) -> Dict:
    """Process a batch of case files"""
    stats = {
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "outcomes": {}
    }
    
    for case_file in case_files:
        case_id = case_file.stem.replace("case_", "")
        
        # Skip if already processed
        if case_id in processed_ids:
            stats["skipped"] += 1
            continue
        
        try:
            scenario = await process_case_file(case_file)
            if scenario:
                processed_ids.add(case_id)
                stats["processed"] += 1
                
                outcome = scenario["metadata"].get("outcome", "Unknown")
                stats["outcomes"][outcome] = stats["outcomes"].get(outcome, 0) + 1
            else:
                stats["failed"] += 1
        except Exception as e:
            print(f"Error in batch processing {case_file.name}: {e}")
            stats["failed"] += 1
    
    return stats


async def process_all_cases(max_cases: Optional[int] = None, continuous: bool = False):
    """Process all downloaded cases"""
    print(f"\n{'='*60}")
    print(f"BATCH SCENARIO PROCESSING")
    print(f"{'='*60}")
    
    # Initialize scenario service
    scenario_service._ensure_initialized()
    
    # Load processed IDs
    processed_ids = load_processed()
    print(f"Already processed: {len(processed_ids):,} cases")
    
    # Get case files from all sources
    case_files = []
    for case_dir in CASE_DIRS:
        if case_dir.exists():
            case_files.extend(case_dir.glob("case_*.json"))
    case_files = sorted(case_files)
    total_files = len(case_files)
    print(f"Found {total_files:,} case files")
    for case_dir in CASE_DIRS:
        if case_dir.exists():
            count = len(list(case_dir.glob("case_*.json")))
            source_name = "CAP" if "cap" in str(case_dir).lower() else "CourtListener"
            print(f"  - {source_name}: {count:,} cases")
    
    # Find unprocessed cases FIRST
    unprocessed = [f for f in case_files if f.stem.replace("case_", "") not in processed_ids]
    print(f"Unprocessed: {len(unprocessed):,} cases")
    
    # THEN apply max_cases limit if specified
    if max_cases and len(unprocessed) > max_cases:
        unprocessed = unprocessed[:max_cases]
        print(f"Limiting to {max_cases:,} cases for this session")
    
    print(f"{'='*60}\n")
    
    if not unprocessed:
        print("No unprocessed cases found!")
        print(f"All {total_files:,} cases have already been processed.")
        print(f"Total scenarios in database: {scenario_service.get_collection_stats().get('total_scenarios', 0):,}")
        return
    
    # Process in batches
    batch_num = 0
    total_stats = {
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "outcomes": {}
    }
    
    total_to_process = len(unprocessed)
    
    try:
        for i in range(0, len(unprocessed), BATCH_SIZE):
            batch = unprocessed[i:i+BATCH_SIZE]
            batch_num += 1
            
            print(f"Processing batch {batch_num} ({len(batch)} cases)...")
            
            # Filter out already processed cases from this batch
            batch = [f for f in batch if f.stem.replace("case_", "") not in processed_ids]
            
            if not batch:
                print(f"  All cases in batch already processed, skipping...")
                continue
            
            batch_stats = await process_batch(batch, processed_ids)
            
            # Update totals
            for key in ["processed", "failed", "skipped"]:
                total_stats[key] += batch_stats[key]
            for outcome, count in batch_stats["outcomes"].items():
                total_stats["outcomes"][outcome] = total_stats["outcomes"].get(outcome, 0) + count
            
            # Calculate progress
            total_attempted = total_stats["processed"] + total_stats["failed"]
            progress_percent = (total_attempted / total_to_process * 100) if total_to_process > 0 else 0
            
            # Save progress with progress info
            progress_info = {
                "total_to_process": total_to_process,
                "total_attempted": total_attempted,
                "total_processed": total_stats["processed"],
                "total_failed": total_stats["failed"],
                "progress_percent": round(progress_percent, 1),
                "current_batch": batch_num,
                "batch_size": len(batch),
                "batch_processed": batch_stats["processed"],
                "batch_failed": batch_stats["failed"]
            }
            save_processed(processed_ids, total_stats, progress_info)
            
            print(f"  Progress: {progress_percent:.1f}% ({total_attempted}/{total_to_process} cases)")
            
            # Get current database stats
            db_stats = scenario_service.get_collection_stats()
            
            print(f"  Batch complete: +{batch_stats['processed']} processed, "
                  f"{batch_stats['failed']} failed, {batch_stats['skipped']} skipped")
            print(f"  Total in database: {db_stats.get('total_scenarios', 0):,} scenarios")
            print(f"  Outcomes: {dict(batch_stats['outcomes'])}")
            
            # Check if we should stop
            if max_cases and total_stats["processed"] >= max_cases:
                break
        
        # Final save
        save_processed(processed_ids, total_stats)
        
        # Final stats
        db_stats = scenario_service.get_collection_stats()
        
        print(f"\n{'='*60}")
        print(f"PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Total processed: {total_stats['processed']:,}")
        print(f"Total failed: {total_stats['failed']:,}")
        print(f"Total skipped: {total_stats['skipped']:,}")
        print(f"Total scenarios in database: {db_stats.get('total_scenarios', 0):,}")
        print(f"Outcome distribution:")
        for outcome, count in sorted(total_stats['outcomes'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {outcome}: {count:,}")
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        print(f"\n\nProcessing interrupted by user")
        print(f"Progress saved. Resume by running again.")
        save_processed(processed_ids, total_stats)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch process cases into scenario database")
    parser.add_argument("--max-cases", type=int, help="Maximum number of cases to process")
    parser.add_argument("--continuous", action="store_true", help="Run continuously, checking for new cases")
    
    args = parser.parse_args()
    
    asyncio.run(process_all_cases(
        max_cases=args.max_cases,
        continuous=args.continuous
    ))

