"""
Continuous Learning Loop - Processes cases and learns from errors
Runs continuously until stopped, getting better over time

This script:
1. Finds cases that haven't been learned from yet
2. Validates predictions on those cases
3. Analyzes errors when predictions are wrong
4. Detects patterns from errors
5. Applies learning to improve future predictions
6. Marks cases as learned to avoid duplicate processing
7. Repeats until stopped
"""
import json
import asyncio
import sys
import signal
import threading
from pathlib import Path
from typing import Dict, Optional, List, Set
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.models import (
    PredictionValidation,
    ErrorAnalysis,
    LearningPattern,
    ReasoningValidation,
    ReasoningTrace,
    init_db,
    get_db
)
from server.services.scenario_service import scenario_service
from server.services.error_analysis_service import error_analysis_service
from server.services.learning_feedback_service import learning_feedback_service
from server.services.pattern_detection_service import pattern_detection_service
from server.services.reasoning_validation_service import reasoning_validation_service
from server.services.outcome_extraction_service import outcome_extraction_service
from server.config import settings
from server.utils.logger import setup_logger
from sqlalchemy.orm import Session

# Setup logger
logger = setup_logger("continuous_learning")

# Global stop event for graceful shutdown
stop_event = threading.Event()

# Learning session tracking
LEARNING_SESSION_FILE = Path("data/scenarios/.continuous_learning_session.json")
# Support multiple case sources
CASE_DIRS = [
    Path("data/scenarios/courtlistener"),  # CourtListener cases
    Path("data/scenarios/cap"),            # CAP (Caselaw Access Project) cases
]
BATCH_SIZE = 50  # Process cases in batches
DELAY_BETWEEN_BATCHES = 5  # Seconds to wait between batches
DELAY_WHEN_NO_CASES = 60  # Seconds to wait when no cases available


def load_learned_cases() -> Set[str]:
    """
    Load set of case IDs that have already been learned from
    This prevents duplicate learning from the same cases
    """
    learned_file = Path("data/scenarios/.learned_cases.json")
    if learned_file.exists():
        try:
            with open(learned_file, 'r') as f:
                data = json.load(f)
                return set(data.get("learned_case_ids", []))
        except Exception as e:
            logger.warning(f"Error loading learned cases: {e}")
    return set()

def normalize_case_name(name: str) -> str:
    """Normalize case name for duplicate detection"""
    if not name:
        return ""
    import re
    # Remove extra whitespace, convert to lowercase
    name = re.sub(r'\s+', ' ', name.lower().strip())
    # Normalize "v." variations
    name = re.sub(r'\s+v\.?\s+', ' v ', name)
    return name

def load_learned_case_names() -> Set[str]:
    """Load set of normalized case names that have already been learned from"""
    learned_file = Path("data/scenarios/.learned_cases.json")
    if learned_file.exists():
        try:
            with open(learned_file, 'r') as f:
                data = json.load(f)
                learned_names = data.get("learned_case_names", [])
                return set(learned_names)
        except Exception as e:
            logger.warning(f"Error loading learned case names: {e}")
    return set()


def load_reasoning_processed_cases(db: Session) -> Set[str]:
    """
    Load set of case IDs that have already been processed for reasoning validation
    This allows re-processing cases for reasoning even if outcome was already learned
    """
    try:
        from server.models import PredictionValidation, ReasoningValidation
        # Get all case IDs that have reasoning validation records
        reasoning_validations = db.query(PredictionValidation.case_id)\
            .join(ReasoningValidation, PredictionValidation.id == ReasoningValidation.validation_id)\
            .distinct()\
            .all()
        return {str(case_id[0]) for case_id in reasoning_validations}
    except Exception as e:
        logger.warning(f"Error loading reasoning-processed cases: {e}")
        return set()


def save_learned_cases(learned_ids: Set[str], learned_names: Set[str], stats: Dict):
    """
    Save learned case IDs, names, and learning statistics
    This persists learning history across restarts and prevents duplicates by name
    """
    learned_file = Path("data/scenarios/.learned_cases.json")
    learned_file.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "learned_case_ids": list(learned_ids),
        "learned_case_names": list(learned_names),
        "total_learned": len(learned_ids),
        "last_update": datetime.now().isoformat(),
        "stats": stats
    }
    
    try:
        with open(learned_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving learned cases: {e}")


def load_session_status() -> Dict:
    """Load learning session status"""
    if LEARNING_SESSION_FILE.exists():
        try:
            with open(LEARNING_SESSION_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading session status: {e}")
    return {
        "is_running": False,
        "started_at": None,
        "total_processed": 0,
        "total_correct": 0,
        "total_incorrect": 0,
        "patterns_detected": 0,
        "last_update": None
    }


def save_session_status(status: Dict):
    """Save learning session status"""
    LEARNING_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(LEARNING_SESSION_FILE, 'w') as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving session status: {e}")


def extract_facts_without_outcome(case_data: Dict) -> str:
    """Extract facts from case, removing outcome-related content"""
    facts = ""
    
    # CourtListener format
    if case_data.get("plain_text"):
        facts = case_data["plain_text"]
    elif case_data.get("html_with_citations"):
        facts = case_data["html_with_citations"]
    elif case_data.get("html"):
        facts = case_data["html"]
    elif case_data.get("html_lawbox"):
        facts = case_data["html_lawbox"]
    
    # CAP (Caselaw Access Project) format
    if not facts and case_data.get("casebody"):
        casebody = case_data["casebody"]
        # Extract text from all opinions
        opinion_texts = []
        if casebody.get("opinions"):
            for opinion in casebody["opinions"]:
                if opinion.get("text"):
                    opinion_texts.append(opinion["text"])
        # Also include head_matter if available
        if casebody.get("head_matter"):
            opinion_texts.insert(0, casebody["head_matter"])
        if opinion_texts:
            facts = "\n\n".join(opinion_texts)
    
    if not facts:
        return ""
    
    # Use improved extraction service
    try:
        extracted = outcome_extraction_service.extract_facts_without_outcome(facts)
        
        # Fallback if extraction removed too much or failed
        if not extracted or len(extracted.strip()) < 100:
            if len(facts) > 200:
                # Use first 80% of text (facts usually come before outcome)
                extracted = facts[:int(len(facts) * 0.8)]
                # Also try to remove obvious outcome sections at the end
                # Look for common outcome section markers
                outcome_markers = [
                    "ORDERED", "ORDER", "CONCLUSION", "HOLDING", 
                    "For the foregoing reasons", "Accordingly", "Therefore"
                ]
                for marker in outcome_markers:
                    marker_idx = extracted.upper().rfind(marker)
                    if marker_idx > len(extracted) * 0.5:  # Only if in second half
                        extracted = extracted[:marker_idx]
                        break
            else:
                extracted = facts
    except Exception as e:
        logger.warning(f"Error in facts extraction, using fallback: {e}")
        # Fallback: use first 80% of text
        extracted = facts[:int(len(facts) * 0.8)] if len(facts) > 200 else facts
    
    return extracted


def get_case_text(case_data: Dict) -> str:
    """Assemble full case text from various formats."""
    case_text = case_data.get("plain_text") or case_data.get("html_with_citations") or case_data.get("html") or case_data.get("html_lawbox") or ""
    
    if not case_text and case_data.get("casebody"):
        casebody = case_data["casebody"]
        opinion_texts = []
        if casebody.get("opinions"):
            for opinion in casebody["opinions"]:
                if opinion.get("text"):
                    opinion_texts.append(opinion["text"])
        if casebody.get("head_matter"):
            opinion_texts.insert(0, casebody["head_matter"])
        if opinion_texts:
            case_text = "\n\n".join(opinion_texts)
    
    return case_text or ""


def extract_actual_outcome(case_data: Dict) -> str:
    """Extract actual outcome from case data"""
    case_text = get_case_text(case_data)
    return outcome_extraction_service.extract_outcome(case_text, case_data)


async def learn_from_case(
    case_file: Path,
    db: Session,
    learned_ids: Set[str],
    learned_names: Set[str],
    reasoning_processed_ids: Set[str] = None,
    reasoning_only_mode: bool = False
) -> Optional[Dict]:
    """
    Learn from a single case by:
    1. Making a prediction
    2. Comparing to actual outcome
    3. Analyzing errors if wrong
    4. Returning learning result
    """
    try:
        # Load case data
        with open(case_file, "r", encoding="utf-8") as f:
            case_data = json.load(f)
        
        case_id = str(case_data.get("id", case_file.stem))
        case_name = case_data.get("case_name") or case_data.get("name", "")
        normalized_name = normalize_case_name(case_name)
        
        # In reasoning-only mode, allow re-processing cases that were already learned for outcomes
        if reasoning_only_mode:
            # Check if this case already has reasoning validation
            if reasoning_processed_ids and case_id in reasoning_processed_ids:
                logger.debug(f"Skipping {case_id} - already processed for reasoning validation")
                return None
            # Don't skip based on learned_ids - we want to re-process for reasoning
        else:
            # Normal mode: skip if already learned from (by ID or by name)
            if case_id in learned_ids:
                return None
            
            # Also check by normalized case name to catch cross-source duplicates
            if normalized_name and normalized_name in learned_names:
                logger.debug(f"Skipping {case_id} - duplicate case name: {case_name}")
                return None
        
        # Detect source from file path
        if "cap" in str(case_file.parent).lower():
            actual_outcome_source = "CAP"
        else:
            actual_outcome_source = "CourtListener"
        
        # Extract facts (without outcome)
        case_facts = extract_facts_without_outcome(case_data)
        if not case_facts or len(case_facts.strip()) < 100:
            logger.debug(f"Skipping {case_id} - facts too short: {len(case_facts) if case_facts else 0} chars")
            return None
        
        # Extract actual outcome
        actual_outcome = extract_actual_outcome(case_data)
        if actual_outcome == "Unknown":
            logger.debug(f"Skipping {case_id} - outcome is Unknown")
            return None
        
        full_case_text = get_case_text(case_data)
        
        # Determine case type and jurisdiction
        case_type = None
        jurisdiction = "Virginia"
        text_lower = case_facts.lower()
        
        if any(term in text_lower for term in ["contract", "breach"]):
            case_type = "Contract"
        elif any(term in text_lower for term in ["tort", "negligence"]):
            case_type = "Tort"
        elif any(term in text_lower for term in ["criminal"]):
            case_type = "Criminal"
        if "federal" in text_lower:
            jurisdiction = "Federal"
        
        # Make prediction using scenario service
        scenario_service._ensure_initialized()
        prediction_result = await scenario_service.predict_outcome(
            query_facts=case_facts,
            case_type=case_type,
            jurisdiction=jurisdiction,
            db_session=db
        )
        
        predicted_outcome = prediction_result.get("prediction", "Unknown")
        predicted_confidence = prediction_result.get("confidence", 0.0)
        
        # Check if prediction is correct
        is_correct = (
            predicted_outcome.lower() == actual_outcome.lower() or
            (predicted_outcome.lower() in actual_outcome.lower()) or
            (actual_outcome.lower() in predicted_outcome.lower())
        )
        
        # Create or update validation record
        if reasoning_only_mode and existing_validation:
            # Update existing validation with reasoning data
            validation = existing_validation
        else:
            # Create new validation record
            validation = PredictionValidation(
                case_id=case_id,
                case_name=case_data.get("case_name", "Unknown")[:255],
            case_facts=case_facts[:5000],  # Limit size
            case_type=case_type,
            jurisdiction=jurisdiction,
            predicted_outcome=predicted_outcome,
            predicted_confidence=predicted_confidence,
            predicted_probabilities=json.dumps(prediction_result.get("outcome_probabilities", {})),
            similar_scenarios_count=prediction_result.get("similar_scenarios", 0),
            actual_outcome=actual_outcome,
            actual_outcome_source=actual_outcome_source,
            is_correct=is_correct,
            error_type=None,
            validated_at=datetime.utcnow()
        )
        db.add(validation)
        db.flush()  # Get validation ID
        
        error_analyzed = False
        reasoning_result = None
        
        # Analyze error if prediction is wrong
        if not is_correct:
            try:
                error_analysis = await error_analysis_service.analyze_prediction_error(
                    case_facts=case_facts,
                    predicted_outcome=predicted_outcome,
                    actual_outcome=actual_outcome,
                    prediction_confidence=predicted_confidence,
                    similar_scenarios=prediction_result.get("top_similar_scenarios", []),
                    case_metadata={
                        "case_type": case_type,
                        "jurisdiction": jurisdiction,
                        "case_id": case_id
                    }
                )
                
                # Store error analysis
                error_record = ErrorAnalysis(
                    validation_id=validation.id,
                    error_type=error_analysis.get("error_type", "unknown"),
                    severity=error_analysis.get("severity"),
                    outcome_mismatch=json.dumps(error_analysis.get("outcome_mismatch", {})),
                    misleading_scenarios=json.dumps(error_analysis.get("misleading_scenarios", [])),
                    missing_factors=json.dumps(error_analysis.get("missing_factors", {})),
                    confidence_analysis=json.dumps(error_analysis.get("confidence_analysis", {})),
                    insights=json.dumps(error_analysis.get("insights", {})),
                    recommendations=json.dumps(error_analysis.get("recommendations", [])),
                    analyzed_at=datetime.utcnow()
                )
                db.add(error_record)
                error_analyzed = True
                
                # Update validation with error type
                validation.error_type = error_analysis.get("error_type")
                
            except Exception as e:
                logger.warning(f"Error analyzing case {case_id}: {e}")
        
        # Evaluate reasoning alignment (even if prediction correct)
        try:
            reasoning_result = await reasoning_validation_service.evaluate_reasoning(
                case_data=case_data,
                case_text=full_case_text,
                case_facts=case_facts,
                predicted_outcome=predicted_outcome,
                similar_scenarios=prediction_result.get("top_similar_scenarios", [])
            )
        except Exception as e:
            logger.warning(f"Reasoning validation failed for case {case_id}: {e}")
        
        if reasoning_result:
            gt = reasoning_result.get("ground_truth", {})
            model_reasoning = reasoning_result.get("model_reasoning", {})
            comparison = reasoning_result.get("comparison", {})
            
            validation.actual_reasoning_excerpt = gt.get("excerpt")
            validation.actual_reasoning_citation = gt.get("citation")
            validation.predicted_reasoning = model_reasoning.get("text")
            
            trace = ReasoningTrace(
                validation_id=validation.id,
                thesis=model_reasoning.get("thesis"),
                supporting_factors=json.dumps(model_reasoning.get("supporting_factors", [])),
                citation_hints=json.dumps(model_reasoning.get("citations", []))
            )
            db.add(trace)
            
            rv = ReasoningValidation(
                validation_id=validation.id,
                reasoning_score=comparison.get("scores", {}).get("overall"),
                fidelity_score=comparison.get("scores", {}).get("fidelity"),
                completeness_score=comparison.get("scores", {}).get("completeness"),
                citation_alignment_score=comparison.get("scores", {}).get("citation_alignment"),
                missing_elements=json.dumps(comparison.get("missing_elements", [])),
                extra_elements=json.dumps(comparison.get("extra_elements", [])),
                curiosity_prompts=json.dumps(comparison.get("curiosity_prompts", []))
            )
            db.add(rv)
            
            if comparison.get("is_gap"):
                gap_recommendations = reasoning_result.get("recommendations", [])
                gap_details = {
                    "reasoning_score": comparison.get("scores", {}),
                    "missing_elements": comparison.get("missing_elements", []),
                    "extra_elements": comparison.get("extra_elements", [])
                }
                reasoning_error = ErrorAnalysis(
                    validation_id=validation.id,
                    error_type="reasoning_gap",
                    severity="major" if not is_correct else "minor",
                    outcome_mismatch=json.dumps(gap_details),
                    misleading_scenarios=json.dumps([]),
                    missing_factors=json.dumps({"missing_elements": comparison.get("missing_elements", [])}),
                    confidence_analysis=json.dumps({}),
                    insights=json.dumps({"curiosity_prompts": comparison.get("curiosity_prompts", [])}),
                    recommendations=json.dumps(gap_recommendations)
                )
                db.add(reasoning_error)
                if not validation.error_type:
                    validation.error_type = "reasoning_gap"
        
        db.commit()
        
        # Mark as learned
        learned_ids.add(case_id)
        if normalized_name:
            learned_names.add(normalized_name)
        
        return {
            "case_id": case_id,
            "is_correct": is_correct,
            "error_analyzed": error_analyzed,
            "predicted": predicted_outcome,
            "actual": actual_outcome,
            "confidence": predicted_confidence
        }
        
    except Exception as e:
        logger.error(f"Error learning from case {case_file.name}: {e}")
        db.rollback()
        return None


async def detect_and_save_patterns(db: Session, min_errors: int = 3) -> int:
    """
    Detect learning patterns from accumulated errors
    Returns number of patterns detected
    """
    try:
        # Get recent error analyses (last 100 errors)
        recent_errors = db.query(ErrorAnalysis)\
            .order_by(ErrorAnalysis.analyzed_at.desc())\
            .limit(100)\
            .all()
        
        if len(recent_errors) < min_errors:
            return 0
        
        # Detect patterns
        patterns = pattern_detection_service.detect_patterns_from_errors(
            db, min_occurrences=min_errors
        )
        
        patterns_saved = 0
        for pattern in patterns:
            try:
                pattern_detection_service.save_pattern(db, pattern)
                patterns_saved += 1
                logger.info(f"Saved pattern: {pattern['pattern_type']} ({pattern['occurrence_count']} occurrences)")
            except Exception as e:
                logger.warning(f"Error saving pattern: {e}")
        
        db.commit()
        return patterns_saved
        
    except Exception as e:
        logger.error(f"Error detecting patterns: {e}")
        db.rollback()
        return 0


async def continuous_learning_loop(
    batch_size: int = BATCH_SIZE,
    delay_between_batches: int = DELAY_BETWEEN_BATCHES,
    delay_when_no_cases: int = DELAY_WHEN_NO_CASES,
    pattern_detection_interval: int = 100  # Detect patterns every N cases
):
    """
    Main continuous learning loop
    
    This function runs until stop_event is set, continuously:
    1. Finding unprocessed cases
    2. Learning from them (validate, analyze errors)
    3. Detecting patterns periodically
    4. Getting better over time
    """
    logger.info("="*70)
    logger.info("CONTINUOUS LEARNING LOOP STARTED")
    logger.info("="*70)
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Delay between batches: {delay_between_batches}s")
    logger.info(f"Pattern detection interval: every {pattern_detection_interval} cases")
    logger.info("Press Ctrl+C or send stop signal to stop learning")
    logger.info("="*70)
    
    # Initialize database
    init_db()
    
    # Load learned cases (by ID and by name for cross-source duplicate detection)
    learned_ids = load_learned_cases()
    learned_names = load_learned_case_names()
    logger.info(f"Loaded {len(learned_ids)} previously learned cases (by ID)")
    logger.info(f"Loaded {len(learned_names)} previously learned case names (for duplicate detection)")
    
    # Load reasoning-processed cases if in reasoning-only mode
    reasoning_processed_ids = set()
    if reasoning_only_mode:
        from server.models import get_db
        db = next(get_db())
        try:
            reasoning_processed_ids = load_reasoning_processed_cases(db)
            logger.info(f"REASONING-ONLY MODE: Loaded {len(reasoning_processed_ids)} cases already processed for reasoning")
            logger.info("Will re-process cases for reasoning validation even if outcome was already learned")
        except Exception as e:
            logger.warning(f"Error loading reasoning-processed cases: {e}")
        finally:
            db.close()
    else:
        reasoning_processed_ids = None
    
    # Initialize session status
    session_status = {
        "is_running": True,
        "started_at": datetime.now().isoformat(),
        "total_processed": 0,
        "total_correct": 0,
        "total_incorrect": 0,
        "patterns_detected": 0,
        "last_update": datetime.now().isoformat()
    }
    save_session_status(session_status)
    
    db = next(get_db())
    cases_processed_since_pattern_detection = 0
    
    try:
        while not stop_event.is_set():
            # Find unprocessed case files from all sources
            case_files = []
            for case_dir in CASE_DIRS:
                if case_dir.exists():
                    case_files.extend(case_dir.glob("case_*.json"))
            
            # Filter out already learned cases (unless in reasoning-only mode)
            if reasoning_only_mode:
                # In reasoning-only mode, include all cases that haven't been processed for reasoning
                unlearned_files = [
                    f for f in case_files
                    if str(f.stem.replace("case_", "")) not in (reasoning_processed_ids or set())
                ]
            else:
                # Normal mode: filter out already learned cases
                unlearned_files = [
                    f for f in case_files
                    if str(f.stem.replace("case_", "")) not in learned_ids
                ]
            
            if not unlearned_files:
                logger.info(f"{'='*70}")
                logger.info(f"No unlearned cases found. Total learned: {len(learned_ids):,} | Waiting {delay_when_no_cases}s before checking again...")
                logger.info(f"{'='*70}")
                await asyncio.sleep(delay_when_no_cases)
                continue
            
            # Process a batch
            batch = unlearned_files[:batch_size]
            batch_num = (cases_processed_since_pattern_detection // batch_size) + 1
            logger.info(f"Processing batch {batch_num} of {len(batch)} cases ({(len(unlearned_files) - len(batch))} remaining)...")
            
            batch_correct = 0
            batch_incorrect = 0
            batch_errors_analyzed = 0
            
            for i, case_file in enumerate(batch, 1):
                if stop_event.is_set():
                    break
                
                logger.info(f"[{i}/{len(batch)}] Learning from {case_file.name}...")
                
                result = await learn_from_case(
                    case_file, db, learned_ids, learned_names,
                    reasoning_processed_ids=reasoning_processed_ids,
                    reasoning_only_mode=reasoning_only_mode
                )
                
                if result:
                    session_status["total_processed"] += 1
                    cases_processed_since_pattern_detection += 1
                    
                    if result["is_correct"]:
                        batch_correct += 1
                        session_status["total_correct"] += 1
                        accuracy = (session_status["total_correct"] / session_status["total_processed"] * 100) if session_status["total_processed"] > 0 else 0
                        logger.info(f"  [OK] Correct prediction: {result['predicted']} | Total: {session_status['total_processed']} | Accuracy: {accuracy:.1f}%")
                    else:
                        batch_incorrect += 1
                        session_status["total_incorrect"] += 1
                        if result["error_analyzed"]:
                            batch_errors_analyzed += 1
                        accuracy = (session_status["total_correct"] / session_status["total_processed"] * 100) if session_status["total_processed"] > 0 else 0
                        logger.info(f"  [ERROR] Wrong prediction: {result['predicted']} (actual: {result['actual']}) | Total: {session_status['total_processed']} | Accuracy: {accuracy:.1f}%")
                else:
                    # Log why case was skipped (for debugging)
                    logger.debug(f"  [SKIP] Case {case_file.name} skipped (already learned, no facts, or unknown outcome)")
                
                # Save progress after EVERY case (for real-time dashboard updates)
                session_status["last_update"] = datetime.now().isoformat()
                save_session_status(session_status)
                
                # Save learned cases every 10 cases (less frequent)
                if i % 10 == 0:
                    save_learned_cases(learned_ids, learned_names, {
                        "total_learned": len(learned_ids),
                        "accuracy": (session_status["total_correct"] / session_status["total_processed"] * 100) if session_status["total_processed"] > 0 else 0
                    })
            
            # Calculate batch accuracy
            batch_total = batch_correct + batch_incorrect
            if batch_total > 0:
                batch_accuracy = (batch_correct / batch_total) * 100
                overall_accuracy = (session_status["total_correct"] / session_status["total_processed"] * 100) if session_status["total_processed"] > 0 else 0
                
                logger.info(f"{'='*70}")
                logger.info(f"Batch {batch_num} complete: {batch_correct}/{batch_total} correct ({batch_accuracy:.1f}%)")
                logger.info(f"Overall Progress: {session_status['total_processed']} cases | {session_status['total_correct']} correct | {session_status['total_incorrect']} incorrect | {overall_accuracy:.1f}% accuracy")
                logger.info(f"{'='*70}")
            else:
                logger.warning(f"Batch {batch_num} processed but no cases were successfully learned (all skipped)")
            
            # Detect patterns periodically
            if cases_processed_since_pattern_detection >= pattern_detection_interval and batch_incorrect > 0:
                logger.info(f"Detecting learning patterns from recent errors...")
                patterns_detected = await detect_and_save_patterns(db, min_errors=2)
                if patterns_detected > 0:
                    session_status["patterns_detected"] += patterns_detected
                    logger.info(f"Detected {patterns_detected} new learning patterns")
                cases_processed_since_pattern_detection = 0
            
            # Save progress
            session_status["last_update"] = datetime.now().isoformat()
            save_session_status(session_status)
            save_learned_cases(learned_ids, learned_names, {
                "total_learned": len(learned_ids),
                "accuracy": overall_accuracy if batch_total > 0 else 0,
                "total_processed": session_status["total_processed"],
                "total_correct": session_status["total_correct"],
                "total_incorrect": session_status["total_incorrect"]
            })
            
            # Wait before next batch
            if not stop_event.is_set():
                logger.info(f"Waiting {delay_between_batches}s before next batch...")
                await asyncio.sleep(delay_between_batches)
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, stopping...")
    except Exception as e:
        logger.error(f"Error in learning loop: {e}", exc_info=True)
    finally:
        # Final save
        session_status["is_running"] = False
        session_status["stopped_at"] = datetime.now().isoformat()
        save_session_status(session_status)
        save_learned_cases(learned_ids, learned_names, {
            "total_learned": len(learned_ids),
            "accuracy": (session_status["total_correct"] / session_status["total_processed"] * 100) if session_status["total_processed"] > 0 else 0,
            "total_processed": session_status["total_processed"],
            "total_correct": session_status["total_correct"],
            "total_incorrect": session_status["total_incorrect"],
            "patterns_detected": session_status["patterns_detected"]
        })
        db.close()
        
        logger.info("="*70)
        logger.info("CONTINUOUS LEARNING LOOP STOPPED")
        logger.info("="*70)
        logger.info(f"Total cases processed: {session_status['total_processed']}")
        logger.info(f"Correct: {session_status['total_correct']}")
        logger.info(f"Incorrect: {session_status['total_incorrect']}")
        if session_status["total_processed"] > 0:
            accuracy = (session_status["total_correct"] / session_status["total_processed"]) * 100
            logger.info(f"Overall accuracy: {accuracy:.1f}%")
        logger.info(f"Patterns detected: {session_status['patterns_detected']}")
        logger.info("="*70)


def signal_handler(signum, frame):
    """Handle stop signals gracefully"""
    logger.info("Stop signal received, shutting down gracefully...")
    stop_event.set()


async def main():
    """Main entry point"""
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Continuous Learning Loop")
    parser.add_argument("--reasoning-only", action="store_true", 
                       help="Re-process cases for reasoning validation only (even if outcome was already learned)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Cases per batch")
    parser.add_argument("--delay", type=int, default=DELAY_BETWEEN_BATCHES, help="Delay between batches (seconds)")
    parser.add_argument("--pattern-interval", type=int, default=100, help="Detect patterns every N cases")
    args = parser.parse_args()
    
    # Run learning loop
    await continuous_learning_loop(
        reasoning_only_mode=args.reasoning_only,
        batch_size=args.batch_size,
        delay_between_batches=args.delay,
        pattern_detection_interval=args.pattern_interval
    )


if __name__ == "__main__":
    asyncio.run(main())

