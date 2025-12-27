"""
Detect Learning Patterns Script
Analyzes error patterns and creates learning patterns for system improvement
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.models import init_db, get_db
from server.services.pattern_detection_service import pattern_detection_service


def main():
    """Detect and save learning patterns from error analyses"""
    print("="*60)
    print("LEARNING PATTERN DETECTION")
    print("="*60)
    print()
    
    # Initialize database
    init_db()
    db = next(get_db())
    
    # Detect patterns (minimum 3 occurrences)
    print("Detecting patterns from error analyses...")
    patterns = pattern_detection_service.detect_patterns_from_errors(db, min_occurrences=3)
    
    print(f"Found {len(patterns)} patterns")
    print()
    
    if not patterns:
        print("No patterns detected. Need more error analyses to detect patterns.")
        print("Run validate_predictions.py first to generate error analyses.")
        db.close()
        return
    
    # Save patterns
    print("Saving patterns...")
    saved_count = 0
    for pattern in patterns:
        saved = pattern_detection_service.save_pattern(db, pattern)
        saved_count += 1
        print(f"  [{saved_count}] Saved pattern: {pattern['pattern_type']} ({pattern['occurrence_count']} occurrences)")
    
    db.close()
    
    print()
    print("="*60)
    print(f"Pattern detection complete! Saved {saved_count} patterns.")
    print("="*60)


if __name__ == "__main__":
    main()

