"""
Real-time download and process - One case at a time with live updates
Fixed pagination to avoid duplicates
"""
import requests
import json
import asyncio
import sys
import os
from pathlib import Path
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.scenario_service import scenario_service
from server.services.outcome_extraction_service import outcome_extraction_service

# Configuration
API_KEY = os.environ.get("COURTLISTENER_API_KEY", "")
if not API_KEY:
    # Try to load from .env file
    env_file = Path("server/.env")
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith("COURTLISTENER_API_KEY="):
                    API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    os.environ["COURTLISTENER_API_KEY"] = API_KEY
                    break

BASE_URL = "https://www.courtlistener.com/api/rest/v4"
OUTPUT_DIR = Path("data/scenarios/courtlistener")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Progress tracking
PROCESSED_FILE = Path("data/scenarios/courtlistener/.processed_cases.json")


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


def save_processed(processed_ids: set, stats: dict):
    """Save processed case IDs and stats"""
    data = {
        "processed_ids": list(processed_ids),
        "total_processed": len(processed_ids),
        "last_update": datetime.now().isoformat(),
        "stats": stats
    }
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def extract_scenario_from_case(case_data: dict) -> dict:
    """Extract scenario data from case JSON"""
    # Get text content
    facts = case_data.get("plain_text", "") or \
            case_data.get("html_with_citations", "") or \
            case_data.get("html", "") or \
            case_data.get("html_lawbox", "")
    
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
    case_name = case_data.get("case_name", "Unknown")
    case_id = str(case_data.get("id", ""))
    
    # Infer case type
    case_type = "Unknown"
    facts_lower = facts_clean.lower()
    if any(term in facts_lower for term in ["contract", "breach", "agreement"]):
        case_type = "Contract"
    elif any(term in facts_lower for term in ["tort", "negligence", "injury", "damages"]):
        case_type = "Tort"
    elif any(term in facts_lower for term in ["criminal", "felony", "misdemeanor"]):
        case_type = "Criminal"
    
    # Get jurisdiction
    jurisdiction = "Virginia"
    court = case_data.get("court", "")
    if isinstance(court, dict):
        court_name = court.get("name", "").lower()
        if "federal" in court_name or "district" in court_name:
            jurisdiction = "Federal"
    
    metadata = {
        "outcome": outcome,
        "case_type": case_type,
        "jurisdiction": jurisdiction,
        "case_name": case_name[:200],
        "case_id": case_id,
    }
    
    # Remove None values
    metadata = {k: v for k, v in metadata.items() if v and v != "Unknown"}
    
    return {
        "facts": facts_clean[:2000],
        "metadata": metadata,
        "scenario_id": f"case_{case_id}"
    }


async def process_case(case_file: Path, processed_ids: set) -> dict:
    """Process a single case file"""
    case_id = case_file.stem.replace("case_", "")
    
    if case_id in processed_ids:
        return {"status": "skipped", "reason": "already processed"}
    
    try:
        with open(case_file, 'r', encoding='utf-8') as f:
            case_data = json.load(f)
        
        scenario = extract_scenario_from_case(case_data)
        if not scenario:
            return {"status": "failed", "reason": "could not extract scenario"}
        
        # Add to scenario database
        try:
            await scenario_service.add_scenario(
                facts=scenario["facts"],
                outcome=scenario["metadata"]["outcome"],
                metadata=scenario["metadata"],
                scenario_id=scenario["scenario_id"]
            )
            processed_ids.add(case_id)
            return {
                "status": "success",
                "outcome": scenario["metadata"]["outcome"],
                "case_type": scenario["metadata"].get("case_type", "Unknown")
            }
        except Exception as e:
            if "existing" in str(e).lower() or "duplicate" in str(e).lower():
                processed_ids.add(case_id)
                return {"status": "skipped", "reason": "duplicate in database"}
            raise
        
    except Exception as e:
        return {"status": "failed", "reason": str(e)}


def download_one_case(next_url: str = None, downloaded_ids: set = None) -> dict:
    """Download one case from CourtListener API using proper pagination"""
    if downloaded_ids is None:
        downloaded_ids = set()
    
    # If we have a next URL, use it; otherwise start fresh
    if next_url:
        url = next_url
    else:
        # Start from beginning
        params = {
            "court__jurisdiction": "va",
            "page_size": 20,  # Get a batch to find new cases
            "ordering": "-date_filed"
        }
        url = f"{BASE_URL}/opinions/"
    
    try:
        if next_url:
            response = requests.get(url, headers={"Authorization": f"Token {API_KEY}"}, timeout=30)
        else:
            response = requests.get(url, params=params, headers={"Authorization": f"Token {API_KEY}"}, timeout=30)
        
        if response.status_code == 429:
            return {"status": "rate_limited", "message": "Rate limited - need to wait"}
        
        if response.status_code != 200:
            return {"status": "error", "message": f"HTTP {response.status_code}"}
        
        data = response.json()
        results = data.get("results", [])
        
        if not results:
            return {"status": "no_more", "message": "No more cases available"}
        
        # Find the first case we haven't downloaded yet
        for case in results:
            case_id = case.get("id")
            
            if not case_id:
                continue
            
            case_id_str = str(case_id)
            
            # Check if already downloaded
            case_file = OUTPUT_DIR / f"case_{case_id_str}.json"
            if case_file.exists() or case_id_str in downloaded_ids:
                continue  # Skip this one, try next
            
            # Found a new case! Save it
            with open(case_file, "w", encoding="utf-8") as f:
                json.dump(case, f, indent=2, ensure_ascii=False)
            
            case_name = case.get("case_name", "Unknown")[:60]
            next_url = data.get("next")  # Get next URL for next iteration
            
            return {
                "status": "success",
                "case_id": case_id_str,
                "case_name": case_name,
                "case_file": case_file,
                "next_url": next_url
            }
        
        # If we got here, all cases in batch were duplicates
        # Get next URL and try again
        next_url = data.get("next")
        if not next_url:
            return {"status": "no_more", "message": "No more new cases available"}
        
        # Recursively try next page (but limit depth to avoid infinite loops)
        return download_one_case(next_url=next_url, downloaded_ids=downloaded_ids)
        
    except requests.exceptions.RequestException as e:
        if "429" in str(e) or "rate" in str(e).lower():
            return {"status": "rate_limited", "message": "Rate limited"}
        return {"status": "error", "message": str(e)}


async def main(max_cases: int = None):
    """Main loop - download and process one case at a time"""
    if not API_KEY:
        print("ERROR: COURTLISTENER_API_KEY not set")
        return
    
    # Initialize
    scenario_service._ensure_initialized()
    processed_ids = load_processed()
    downloaded_ids = {f.stem.replace("case_", "") for f in OUTPUT_DIR.glob("case_*.json")}
    
    stats = {
        "downloaded": 0,
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "duplicates": 0,
        "outcomes": {}
    }
    
    next_url = None  # Start fresh
    consecutive_duplicates = 0
    rate_limit_wait = 0
    
    db_stats = scenario_service.get_collection_stats()
    initial_count = db_stats.get("total_scenarios", 0)
    
    print(f"\n{'='*60}")
    print(f"REAL-TIME CASE DOWNLOAD & PROCESS")
    print(f"{'='*60}")
    print(f"Starting with {initial_count} scenarios in database")
    print(f"Already downloaded: {len(downloaded_ids)} cases")
    print(f"Already processed: {len(processed_ids)} cases")
    if max_cases:
        print(f"Target: {max_cases} new cases")
    print(f"{'='*60}\n")
    
    try:
        while True:
            if max_cases and stats["processed"] >= max_cases:
                print(f"\n[SUCCESS] Reached target of {max_cases} processed cases!")
                break
            
            # Handle rate limiting
            if rate_limit_wait > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Rate limited - waiting {rate_limit_wait} seconds...")
                for remaining in range(rate_limit_wait, 0, -10):
                    print(f"  {remaining} seconds remaining...", end="\r", flush=True)
                    time.sleep(min(10, remaining))
                print("  Ready to continue!                    ")
                rate_limit_wait = 0
            
            # Download one case
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Searching for new case...", end=" ", flush=True)
            download_result = download_one_case(next_url=next_url, downloaded_ids=downloaded_ids)
            
            if download_result["status"] == "no_more":
                print("No more cases available")
                break
            elif download_result["status"] == "rate_limited":
                rate_limit_wait = 120  # Wait 2 minutes for rate limit to clear
                print("Rate limited - will wait 2 minutes")
                continue
            elif download_result["status"] == "error":
                print(f"ERROR: {download_result['message']}")
                time.sleep(2)
                continue
            elif download_result["status"] == "success":
                case_id = download_result["case_id"]
                case_name = download_result["case_name"]
                case_file = download_result["case_file"]
                next_url = download_result.get("next_url")
                downloaded_ids.add(str(case_id))
                consecutive_duplicates = 0
                stats["downloaded"] += 1
                print(f"[OK] Downloaded: {case_name} (ID: {case_id})")
            else:
                # Shouldn't happen, but handle it
                print(f"Unexpected status: {download_result.get('status')}")
                time.sleep(1)
                continue
            
            # Process immediately
            print(f"  -> Processing...", end=" ", flush=True)
            process_result = await process_case(case_file, processed_ids)
            
            if process_result["status"] == "success":
                outcome = process_result["outcome"]
                case_type = process_result.get("case_type", "Unknown")
                stats["processed"] += 1
                stats["outcomes"][outcome] = stats["outcomes"].get(outcome, 0) + 1
                
                # Get updated database count
                db_stats = scenario_service.get_collection_stats()
                current_count = db_stats.get("total_scenarios", 0)
                
                print(f"[OK] Processed! Outcome: {outcome}, Type: {case_type}")
                print(f"  Database now has {current_count} scenarios (+{current_count - initial_count} new)")
            elif process_result["status"] == "skipped":
                reason = process_result.get("reason", "unknown")
                print(f"[SKIP] {reason}")
                stats["skipped"] += 1
            else:
                reason = process_result.get("reason", "unknown")
                print(f"[FAIL] {reason}")
                stats["failed"] += 1
            
            # Save progress
            save_processed(processed_ids, stats)
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
            
            # Show summary every 10 cases
            if stats["downloaded"] % 10 == 0:
                print(f"\n  [Progress] Downloaded: {stats['downloaded']}, "
                      f"Processed: {stats['processed']}, "
                      f"Failed: {stats['failed']}, "
                      f"Skipped: {stats['skipped']}")
                print()
    
    except KeyboardInterrupt:
        print(f"\n\nInterrupted by user")
    
    # Final summary
    db_stats = scenario_service.get_collection_stats()
    final_count = db_stats.get("total_scenarios", 0)
    
    print(f"\n{'='*60}")
    print(f"SESSION COMPLETE")
    print(f"{'='*60}")
    print(f"Downloaded: {stats['downloaded']} cases")
    print(f"Processed: {stats['processed']} cases")
    print(f"Failed: {stats['failed']} cases")
    print(f"Skipped: {stats['skipped']} cases")
    print(f"Database: {final_count} scenarios (started with {initial_count})")
    print(f"Outcome distribution:")
    for outcome, count in sorted(stats["outcomes"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {outcome}: {count}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Real-time download and process cases one at a time")
    parser.add_argument("--max-cases", type=int, help="Maximum number of cases to process")
    
    args = parser.parse_args()
    
    asyncio.run(main(max_cases=args.max_cases))
