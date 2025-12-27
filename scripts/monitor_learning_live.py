"""Live monitor for learning session progress"""
import json
import time
from pathlib import Path
from datetime import datetime

def format_time(iso_str):
    """Format ISO timestamp to readable time"""
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime("%H:%M:%S")
    except:
        return iso_str

def get_progress_bar(current, total, width=40):
    """Create progress bar"""
    if total == 0:
        return "░" * width
    filled = int((current / total) * width)
    return "█" * filled + "░" * (width - filled)

def main():
    session_file = Path("data/scenarios/.continuous_learning_session.json")
    learned_file = Path("data/scenarios/.learned_cases.json")
    
    print("Learning Session Live Monitor")
    print("=" * 70)
    print("Press Ctrl+C to stop")
    print()
    
    last_processed = 0
    last_update_time = None
    
    try:
        while True:
            # Clear screen (works in most terminals)
            print("\033[2J\033[H", end="")
            
            print("Learning Session Live Monitor")
            print("=" * 70)
            print(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
            print()
            
            # Load session status
            if session_file.exists():
                with open(session_file, 'r', encoding='utf-8') as f:
                    session = json.load(f)
                
                is_running = session.get("is_running", False)
                started_at = session.get("started_at", "")
                total_processed = session.get("total_processed", 0)
                total_correct = session.get("total_correct", 0)
                total_incorrect = session.get("total_incorrect", 0)
                last_update = session.get("last_update", "")
                
                # Status
                status_color = "RUNNING" if is_running else "STOPPED"
                print(f"Status: {status_color}")
                print(f"Started: {format_time(started_at)}")
                print(f"Last Activity: {format_time(last_update)}")
                print()
                
                # Progress
                print("Progress:")
                print(f"  Cases Processed: {total_processed:,}")
                print(f"  Correct: {total_correct:,}")
                print(f"  Incorrect: {total_incorrect:,}")
                
                if total_processed > 0:
                    accuracy = (total_correct / total_processed) * 100
                    print(f"  Accuracy: {accuracy:.1f}%")
                else:
                    print(f"  Accuracy: N/A (no cases processed yet)")
                print()
                
                # Activity indicator
                if last_update_time != last_update:
                    if total_processed > last_processed:
                        print("  [ACTIVE] Processing cases...")
                        last_processed = total_processed
                        last_update_time = last_update
                    else:
                        print("  [WAITING] No new cases processed")
                else:
                    print("  [WAITING] No new activity")
                print()
                
            else:
                print("No active learning session found")
                print()
            
            # Load learned cases count
            if learned_file.exists():
                with open(learned_file, 'r', encoding='utf-8') as f:
                    learned = json.load(f)
                learned_count = len(learned.get("learned_case_ids", []))
                print(f"Total Learned Cases: {learned_count:,}")
                print()
            
            print("=" * 70)
            print("Refreshing every 2 seconds...")
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")

if __name__ == "__main__":
    main()

