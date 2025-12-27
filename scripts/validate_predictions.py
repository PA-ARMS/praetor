"""
Validation Script - Tests AI predictions against actual outcomes
Downloads cases, makes predictions, compares to actual outcomes, and analyzes errors
"""
import json
import asyncio
import sys
import re
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.models import PredictionValidation, ErrorAnalysis, LearningPattern, init_db, get_db
from server.services.scenario_service import scenario_service
from server.services.error_analysis_service import error_analysis_service
from server.services.learning_feedback_service import learning_feedback_service
from server.services.pattern_detection_service import pattern_detection_service
from server.services.outcome_extraction_service import outcome_extraction_service
from server.config import settings
from sqlalchemy.orm import Session


def extract_facts_without_outcome(case_data: Dict) -> str:
    """
    Extract facts from case, removing outcome-related content
    Uses improved outcome extraction service
    """
    facts = ""
    if case_data.get("plain_text"):
        facts = case_data["plain_text"]
    elif case_data.get("html_with_citations"):
        facts = case_data["html_with_citations"]
    elif case_data.get("html"):
        facts = case_data["html"]
    elif case_data.get("html_lawbox"):
        facts = case_data["html_lawbox"]
    
    if not facts:
        return ""
    
    # Use improved extraction service
    extracted = outcome_extraction_service.extract_facts_without_outcome(facts)
    
    # Fallback: if extraction removed too much, use first part of original
    if len(extracted.strip()) < 100 and len(facts) > 200:
        # Use first 2000 chars, but mask outcome keywords
        extracted = facts[:2000]
        outcome_keywords = ["granted", "denied", "dismissed", "affirmed", "reversed", "remanded", "settled"]
        for keyword in outcome_keywords:
            extracted = re.sub(rf"\b{keyword}\b", "[outcome]", extracted, flags=re.IGNORECASE)
    
    return extracted


def extract_actual_outcome(case_data: Dict) -> str:
    """Extract actual outcome from case data using improved service"""
    case_text = case_data.get("plain_text", "")
    return outcome_extraction_service.extract_outcome(case_text, case_data)


async def validate_case(
    case_file: Path,
    db: Session,
    analyze_errors: bool = True
) -> Optional[Dict]:
    """Validate a single case prediction"""
    try:
        # Load case data
        with open(case_file, "r", encoding="utf-8") as f:
            case_data = json.load(f)
        
        case_id = str(case_data.get("id", case_file.stem))
        case_name = case_data.get("case_name", "Unknown")[:255]
        
        # Extract facts (without outcome)
        case_facts = extract_facts_without_outcome(case_data)
        if not case_facts or len(case_facts.strip()) < 100:  # Increased minimum from 50 to 100
            print(f"  Skipping {case_id}: insufficient facts ({len(case_facts.strip()) if case_facts else 0} chars)")
            return None
        
        # Extract actual outcome
        actual_outcome = extract_actual_outcome(case_data)
        if actual_outcome == "Unknown":
            print(f"  Skipping {case_id}: unknown outcome")
            return None
        
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
        
        # Make prediction (with learning feedback)
        print(f"  Predicting case {case_id}...")
        prediction = await scenario_service.predict_outcome(
            query_facts=case_facts,
            case_type=case_type,
            jurisdiction=jurisdiction,
            db_session=db  # Pass DB session for learning feedback
        )
        
        predicted_outcome = prediction.get("prediction", "Unknown")
        predicted_confidence = prediction.get("confidence", 0.0)
        similar_scenarios = prediction.get("top_similar_scenarios", [])
        
        # Check if correct
        is_correct = (predicted_outcome == actual_outcome)
        
        # Determine error type and confidence issue
        error_type = None
        confidence_issue = None
        if not is_correct:
            if predicted_confidence >= 70:
                confidence_issue = "overconfident"
            elif predicted_confidence >= 50:
                confidence_issue = "moderately_overconfident"
            else:
                confidence_issue = "appropriate_uncertainty"
        
        # Store validation result
        validation = PredictionValidation(
            case_id=case_id,
            case_name=case_name,
            case_facts=case_facts,
            case_type=case_type,
            jurisdiction=jurisdiction,
            predicted_outcome=predicted_outcome,
            predicted_confidence=predicted_confidence,
            predicted_probabilities=json.dumps(prediction.get("outcome_probabilities", {})),
            similar_scenarios_count=prediction.get("similar_scenarios", 0),
            actual_outcome=actual_outcome,
            actual_outcome_source="CourtListener",
            is_correct=is_correct,
            error_type=error_type,
            confidence_issue=confidence_issue,
            case_metadata=json.dumps({
                "case_id": case_id,
                "courtlistener_id": case_data.get("id"),
                "date_filed": str(case_data.get("date_filed", "")),
                "court": case_data.get("court", "")
            })
        )
        
        db.add(validation)
        db.commit()
        db.refresh(validation)
        
        # Analyze error if prediction was wrong
        error_analysis_data = None
        if not is_correct and analyze_errors:
            # Less verbose - show brief message
            print(f"    Analyzing error...", end=" ", flush=True)
            try:
                error_analysis_data = await error_analysis_service.analyze_prediction_error(
                    case_facts=case_facts,
                    predicted_outcome=predicted_outcome,
                    actual_outcome=actual_outcome,
                    prediction_confidence=predicted_confidence,
                    similar_scenarios=similar_scenarios,
                    case_metadata={
                        "case_type": case_type,
                        "jurisdiction": jurisdiction,
                        "case_name": case_name
                    }
                )
                
                # Store error analysis
                error_analysis = ErrorAnalysis(
                    validation_id=validation.id,
                    error_type=error_analysis_data.get("error_type", "unknown"),
                    severity=error_analysis_data.get("outcome_mismatch", {}).get("severity"),
                    outcome_mismatch=json.dumps(error_analysis_data.get("outcome_mismatch", {})),
                    misleading_scenarios=json.dumps(error_analysis_data.get("misleading_scenarios", [])),
                    missing_factors=json.dumps(error_analysis_data.get("missing_factors", {})),
                    confidence_analysis=json.dumps(error_analysis_data.get("confidence_analysis", {})),
                    insights=json.dumps(error_analysis_data.get("insights", {})),
                    recommendations=json.dumps(error_analysis_data.get("recommendations", []))
                )
                
                db.add(error_analysis)
                db.commit()
                
                # Update validation with error type
                validation.error_type = error_analysis_data.get("error_type")
                db.commit()
                print("Done")  # Complete the analysis message
                
            except Exception as e:
                print(f"Failed: {e}")
                import traceback
                traceback.print_exc()
        
        result = {
            "case_id": case_id,
            "predicted": predicted_outcome,
            "actual": actual_outcome,
            "is_correct": is_correct,
            "confidence": predicted_confidence,
            "error_type": error_analysis_data.get("error_type") if error_analysis_data else None
        }
        
        status = "[OK]" if is_correct else "[ERROR]"
        print(f"  {status} Case {case_id}: Predicted '{predicted_outcome}' ({predicted_confidence:.1f}%), Actual '{actual_outcome}'")
        
        return result
        
    except Exception as e:
        print(f"  Error validating case {case_file}: {e}")
        import traceback
        traceback.print_exc()
        return None


async def validate_batch(
    case_dir: Path,
    limit: Optional[int] = None,
    analyze_errors: bool = True,
    analyze_all_errors: bool = True
) -> Dict:
    """Validate a batch of cases"""
    case_files = list(case_dir.glob("case_*.json"))
    
    if limit:
        case_files = case_files[:limit]
    
    print(f"\n{'='*60}")
    print(f"VALIDATION BATCH")
    print(f"{'='*60}")
    print(f"Cases to validate: {len(case_files)}")
    print(f"Error analysis: {'Enabled' if analyze_errors else 'Disabled'}")
    print(f"{'='*60}\n")
    
    # Initialize database
    init_db()
    db = next(get_db())
    
    # Initialize scenario service
    scenario_service._ensure_initialized()
    
    results = []
    correct = 0
    incorrect = 0
    errors_analyzed = 0
    
    for i, case_file in enumerate(case_files, 1):
        print(f"[{i}/{len(case_files)}] Processing {case_file.name}...")
        # If sample analysis mode, only analyze every 3rd error to speed things up
        # Check if we should analyze based on current error count
        should_analyze_this_error = analyze_errors and (analyze_all_errors or (incorrect % 3 == 0))
        result = await validate_case(case_file, db, should_analyze_this_error)
        
        if result:
            results.append(result)
            if result["is_correct"]:
                correct += 1
            else:
                incorrect += 1
                if should_analyze_this_error:
                    errors_analyzed += 1
    
    # Detect learning patterns from errors (if we have errors)
    patterns_detected = 0
    if incorrect > 0 and analyze_errors:
        print(f"\n{'='*60}")
        print(f"DETECTING LEARNING PATTERNS")
        print(f"{'='*60}")
        print(f"Analyzed {errors_analyzed} errors, detecting patterns from {incorrect} total errors...")
        try:
            patterns = pattern_detection_service.detect_patterns_from_errors(db, min_occurrences=2)
            if patterns:
                print(f"Found {len(patterns)} learning patterns:")
                for pattern in patterns:
                    saved = pattern_detection_service.save_pattern(db, pattern)
                    patterns_detected += 1
                    print(f"  - {pattern['pattern_type']}: {pattern['occurrence_count']} occurrences")
                    print(f"    Affects: {', '.join(pattern.get('affected_case_types', []))}")
            else:
                print("No patterns detected (need more error data)")
        except Exception as e:
            print(f"Warning: Could not detect patterns: {e}")
            import traceback
            traceback.print_exc()
    
    db.close()
    
    # Calculate metrics
    total = len(results)
    if total > 0:
        accuracy = (correct / total * 100)
        print(f"\n{'='*60}")
        print(f"VALIDATION COMPLETE")
        print(f"{'='*60}")
        print(f"Total cases: {total}")
        print(f"Correct: {correct} ({correct/total*100:.1f}%)")
        print(f"Incorrect: {incorrect} ({incorrect/total*100:.1f}%)")
        print(f"Overall Accuracy: {accuracy:.1f}%")
        if patterns_detected > 0:
            print(f"Learning Patterns Detected: {patterns_detected}")
            print(f"The AI will now use these patterns to improve future predictions!")
        print(f"{'='*60}\n")
    else:
        accuracy = 0
        print(f"\n{'='*60}")
        print(f"VALIDATION COMPLETE")
        print(f"{'='*60}")
        print(f"No cases were successfully validated.")
        print(f"Check case files and ensure they have sufficient data.")
        print(f"{'='*60}\n")
    
    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "accuracy": accuracy,
        "results": results
    }


async def main():
    """Main validation function"""
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
    analyze_errors = True
    analyze_all_errors = True  # By default, analyze all errors
    
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            print(f"Limiting validation to {limit} cases")
        except ValueError:
            if sys.argv[1] not in ["--no-analysis", "--sample-analysis"]:
                print("Usage: python validate_predictions.py [limit] [--no-analysis|--sample-analysis]")
                return
    
    if "--no-analysis" in sys.argv:
        analyze_errors = False
    elif "--sample-analysis" in sys.argv:
        analyze_all_errors = False  # Only analyze sample of errors
        print("Sample analysis mode: Will analyze subset of errors for faster processing")
    
    await validate_batch(case_dir, limit=limit, analyze_errors=analyze_errors, analyze_all_errors=analyze_all_errors)


if __name__ == "__main__":
    asyncio.run(main())

