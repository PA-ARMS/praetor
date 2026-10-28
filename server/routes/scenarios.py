"""
Scenario API routes - Predictive analysis and scenario management
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import json

from server.services.scenario_service import scenario_service
from server.services.learning_session_service import learning_session_service


def require_localhost(request: Request):
    """
    Require request to come from localhost only
    
    This check is lenient to allow requests through Vite proxy and from same machine:
    - Direct localhost connections
    - Requests through Vite proxy (which forwards to localhost:5001)
    - Requests from same machine via network interface (private IPs)
    - Requests with localhost in Origin/Referer headers
    """
    client_host = request.client.host if request.client else None
    
    # Check if request is from localhost directly
    if client_host in ["127.0.0.1", "localhost", "::1"]:
        return True
    
    # Check if request is from a private IP (same machine via network interface)
    # This allows requests from the same PC even if using network IP
    if client_host:
        # Check for private IP ranges (same machine, different interface)
        private_ip_ranges = [
            "192.168.",  # Private network
            "10.",       # Private network
            "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
            "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.",
            "172.28.", "172.29.", "172.30.", "172.31.",  # Private network
        ]
        if any(client_host.startswith(prefix) for prefix in private_ip_ranges):
            # Allow if Origin or Referer is from localhost (same machine)
            origin = request.headers.get("Origin", "")
            referer = request.headers.get("Referer", "")
            if "localhost" in origin or "127.0.0.1" in origin or "localhost" in referer or "127.0.0.1" in referer:
                return True
    
    # Check X-Forwarded-For header (for reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip in ["127.0.0.1", "localhost", "::1"]:
            return True
    
    # Check if request is coming through Vite proxy (common pattern)
    # Vite proxy forwards requests, so we check the Host header
    host_header = request.headers.get("Host", "")
    if "localhost" in host_header or "127.0.0.1" in host_header:
        return True
    
    # Check Origin header - if it's from localhost, allow it
    # This is the most reliable check for requests from the browser
    origin = request.headers.get("Origin", "")
    if origin:
        origin_lower = origin.lower()
        if "localhost" in origin_lower or "127.0.0.1" in origin_lower:
            return True
    
    # Check Referer header - if it's from localhost, allow it
    referer = request.headers.get("Referer", "")
    if referer:
        referer_lower = referer.lower()
        if "localhost" in referer_lower or "127.0.0.1" in referer_lower:
            return True
    
    # If all checks fail, block the request
    raise HTTPException(
        status_code=403, 
        detail="This endpoint is only accessible from localhost. Learning controls are restricted for security."
    )


router = APIRouter()


class ScenarioMetadata(BaseModel):
    outcome: str  # e.g., "Plaintiff Win", "Defendant Win", "Settlement", "Dismissal"
    case_type: str  # e.g., "Contract", "Tort", "Criminal", "Family Law"
    jurisdiction: str
    court_level: Optional[str] = None  # e.g., "Circuit Court", "Supreme Court"
    date: Optional[str] = None
    citation: Optional[str] = None
    key_factors: List[str] = []  # Factors that influenced outcome
    damages_amount: Optional[float] = None
    settlement_amount: Optional[float] = None
    duration_months: Optional[int] = None


class ScenarioInput(BaseModel):
    facts: str
    metadata: ScenarioMetadata


class PredictionRequest(BaseModel):
    facts: str
    case_type: Optional[str] = None
    jurisdiction: Optional[str] = None


@router.post("/add-scenario")
async def add_scenario(scenario: ScenarioInput):
    """Add a scenario to the database"""
    try:
        metadata_dict = scenario.metadata.dict()
        metadata_dict["added_date"] = str(datetime.now())
        
        await scenario_service.add_scenario(
            facts=scenario.facts,
            outcome=scenario.metadata.outcome,
            metadata=metadata_dict
        )
        return {"status": "success", "message": "Scenario added to database"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding scenario: {str(e)}")


@router.post("/predict")
async def predict_outcome(request: PredictionRequest):
    """Predict outcome probability for given facts"""
    try:
        prediction = await scenario_service.predict_outcome(
            query_facts=request.facts,
            case_type=request.case_type,
            jurisdiction=request.jurisdiction
        )
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error predicting outcome: {str(e)}")


@router.post("/find-similar")
async def find_similar_scenarios(
    facts: str,
    case_type: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    n_results: int = 10
):
    """Find similar scenarios"""
    try:
        # Build filters (ChromaDB requires $and operator for multiple filters)
        filters = None
        if case_type and jurisdiction:
            filters = {"$and": [{"case_type": case_type}, {"jurisdiction": jurisdiction}]}
        elif case_type:
            filters = {"case_type": case_type}
        elif jurisdiction:
            filters = {"jurisdiction": jurisdiction}
        
        results = await scenario_service.find_similar_scenarios(
            query_facts=facts,
            n_results=n_results,
            filters=filters
        )
        return {"query": facts, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding similar scenarios: {str(e)}")


@router.get("/stats")
async def get_stats(request: Request):
    """Get scenario database statistics"""
    # Localhost restriction removed for easier access
    
    try:
        stats = scenario_service.get_collection_stats()
        
        # Get outcome distribution
        try:
            scenario_service._ensure_initialized()
            outcomes = {}
            if scenario_service.collection:
                batch_size = 400
                offset = 0
                while True:
                    batch = scenario_service.collection.get(
                        limit=batch_size,
                        offset=offset,
                        include=["metadatas"],
                    )
                    metas = batch.get("metadatas") or []
                    if not metas:
                        break
                    for meta in metas:
                        if not meta:
                            continue
                        outcome = meta.get("outcome", "Unknown")
                        if outcome and outcome != "Unknown":
                            outcomes[outcome] = outcomes.get(outcome, 0) + 1
                    offset += len(metas)
                    if len(metas) < batch_size:
                        break
                stats["outcome_distribution"] = outcomes
            else:
                stats["outcome_distribution"] = {}
        except Exception as e:
            logger.warning(f"Error getting outcome distribution: {e}")
            stats['outcome_distribution'] = {}
        
        # Count total case files downloaded
        case_dir = Path("data/scenarios/courtlistener")
        if case_dir.exists():
            case_files = list(case_dir.glob("case_*.json"))
            stats['total_cases'] = len(case_files)
        else:
            stats['total_cases'] = 0
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@router.get("/progress")
async def get_progress(request: Request):
    """Get processing progress information"""
    # Localhost restriction removed for easier access
    
    progress_file = Path("data/scenarios/courtlistener/.processed_cases.json")
    
    if not progress_file.exists():
        return {
            "total_processed": 0,
            "success_rate": 0,
            "is_processing": False
        }
    
    try:
        with open(progress_file, 'r') as f:
            data = json.load(f)
        
        stats_data = data.get('stats', {})
        processed = stats_data.get('processed', 0)
        failed = stats_data.get('failed', 0)
        total_attempted = processed + failed
        
        success_rate = (processed / total_attempted * 100) if total_attempted > 0 else 0
        
        # Check if processing is active (file updated in last 2 minutes)
        from datetime import timedelta
        last_update_str = data.get('last_update', '')
        is_processing = False
        if last_update_str:
            try:
                last_update = datetime.fromisoformat(last_update_str)
                is_processing = (datetime.now() - last_update) < timedelta(minutes=2)
            except:
                pass
        
        # Also check if learning session service says it's running
        session_status = learning_session_service.get_status()
        if session_status.get("status") == "running":
            is_processing = True
        
        # Get progress information if available
        progress_info = data.get('progress', {})
        
        return {
            "total_processed": data.get('total_processed', 0),
            "success_rate": round(success_rate, 1),
            "is_processing": is_processing,
            "stats": stats_data,
            "progress": progress_info
        }
    except Exception as e:
        logger.warning(f"Error reading progress file: {e}")
        return {
            "total_processed": 0,
            "success_rate": 0,
            "is_processing": False
        }


class LearningSessionRequest(BaseModel):
    max_cases: Optional[int] = None
    continuous: bool = False  # If true, runs continuous learning loop
    reasoning_only: bool = False  # If true, re-process cases for reasoning validation only


@router.post("/learning/start")
async def start_learning_session(request: Request, body: LearningSessionRequest):
    """Start a learning session
    
    If continuous=True, starts the continuous learning loop that runs until stopped.
    Otherwise, processes a batch of cases (up to max_cases).
    """
    # Localhost restriction removed for easier access
    
    result = learning_session_service.start_session(
        max_cases=body.max_cases,
        continuous=body.continuous,
        reasoning_only=body.reasoning_only
    )
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/learning/stop")
async def stop_learning_session(request: Request):
    """Stop the current learning session"""
    # Localhost restriction removed for easier access
    
    result = learning_session_service.stop_session()
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.get("/learning/status")
async def get_learning_session_status(request: Request):
    """Get learning session status"""
    # Localhost restriction removed for easier access
    
    status = learning_session_service.get_status()
    
    # Also include log file contents if available
    # Check for continuous learning log first, then regular learning log
    log_file = None
    if status.get("session", {}).get("continuous"):
        log_file = Path("data/scenarios/.continuous_learning.log")
    else:
        log_file = Path("data/scenarios/.learning_session.log")
    
    log_lines = []
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                # Get last 50 lines
                all_lines = f.readlines()
                log_lines = all_lines[-50:] if len(all_lines) > 50 else all_lines
        except Exception as e:
            log_lines = [f"Error reading log: {e}"]
    
    status["log_tail"] = log_lines
    
    # Also include continuous learning session status if available
    continuous_session_file = Path("data/scenarios/.continuous_learning_session.json")
    if continuous_session_file.exists():
        try:
            with open(continuous_session_file, 'r') as f:
                continuous_status = json.load(f)
                status["continuous_learning"] = continuous_status
        except Exception as e:
            logger.warning(f"Error reading continuous learning status: {e}")
    
    return status

