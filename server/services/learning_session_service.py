"""
Learning Session Service - Manages background learning/processing sessions
"""
import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
import json

from server.config import settings
from server.utils.logger import setup_logger


class LearningSessionService:
    """Manages learning session processes"""
    
    def __init__(self):
        self.logger = setup_logger("learning_session")
        self.current_process: Optional[subprocess.Popen] = None
        self.log_handle = None  # Keep reference to log file handle
        self.session_status: Dict = {
            "is_running": False,
            "started_at": None,
            "max_cases": None,
            "pid": None
        }
        self.status_file = Path("data/scenarios/.learning_session.json")
    
    def start_session(self, max_cases: Optional[int] = None, continuous: bool = False, reasoning_only: bool = False) -> Dict:
        """Start a learning session (process cases or continuous learning)"""
        if self.current_process and self.current_process.poll() is None:
            return {
                "status": "error",
                "message": "A learning session is already running",
                "session": self.session_status
            }
        
        # Build command - use continuous learning loop if requested
        if continuous:
            script_path = Path(__file__).parent.parent.parent / "scripts" / "continuous_learning_loop.py"
            cmd = [sys.executable, str(script_path)]
            # Optional: add batch size and delay parameters
            if max_cases:
                # For continuous loop, max_cases could be used as batch size
                cmd.extend(["--batch-size", str(max_cases)])
            # Add reasoning-only mode flag
            if reasoning_only:
                cmd.extend(["--reasoning-only"])
        else:
            script_path = Path(__file__).parent.parent.parent / "scripts" / "process_scenarios_batch.py"
            cmd = [sys.executable, str(script_path)]
            if max_cases:
                cmd.extend(["--max-cases", str(max_cases)])
        
        # Start process in background
        try:
            # Use subprocess.Popen with creation flags for Windows
            import platform
            # Create log file for output (use different log for continuous learning)
            if continuous:
                log_file = Path("data/scenarios/.continuous_learning.log")
            else:
                log_file = Path("data/scenarios/.learning_session.log")
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            if platform.system() == "Windows":
                # Open log file for writing (append mode to preserve previous runs)
                self.log_handle = open(log_file, 'a', encoding='utf-8')
                # Write separator for new session
                self.log_handle.write(f"\n{'='*60}\n")
                self.log_handle.write(f"NEW LEARNING SESSION STARTED: {datetime.now().isoformat()}\n")
                self.log_handle.write(f"{'='*60}\n")
                self.log_handle.flush()
                
                # Verify script exists before starting
                if not script_path.exists():
                    raise FileNotFoundError(f"Script not found: {script_path}")
                
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=self.log_handle,
                    stderr=subprocess.STDOUT,  # Combine stderr with stdout
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    bufsize=1,  # Line buffered
                    cwd=str(Path(__file__).parent.parent.parent)  # Set working directory
                )
            else:
                self.log_handle = open(log_file, 'a', encoding='utf-8')
                self.log_handle.write(f"\n{'='*60}\n")
                self.log_handle.write(f"NEW LEARNING SESSION STARTED: {datetime.now().isoformat()}\n")
                self.log_handle.write(f"{'='*60}\n")
                self.log_handle.flush()
                
                # Verify script exists before starting
                if not script_path.exists():
                    raise FileNotFoundError(f"Script not found: {script_path}")
                
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=self.log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(Path(__file__).parent.parent.parent)  # Set working directory
                )
            
            self.session_status = {
                "is_running": True,
                "started_at": datetime.now().isoformat(),
                "max_cases": max_cases,
                "continuous": continuous,
                "pid": self.current_process.pid
            }
            
            self._save_status()
            
            return {
                "status": "started",
                "message": f"Learning session started (PID: {self.current_process.pid})",
                "session": self.session_status
            }
        except Exception as e:
            self.logger.error(f"Error starting learning session: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Failed to start learning session: {str(e)}",
                "session": self.session_status
            }
    
    def stop_session(self) -> Dict:
        """Stop the current learning session"""
        if not self.current_process:
            return {
                "status": "error",
                "message": "No learning session is running",
                "session": self.session_status
            }
        
        try:
            # Terminate the process
            self.current_process.terminate()
            
            # Wait a bit, then kill if still running
            try:
                self.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
                self.current_process.wait()
            
            self.session_status = {
                "is_running": False,
                "started_at": self.session_status.get("started_at"),
                "max_cases": self.session_status.get("max_cases"),
                "pid": None,
                "stopped_at": datetime.now().isoformat()
            }
            
            # Close log file handle
            if self.log_handle:
                try:
                    self.log_handle.write(f"\nSESSION STOPPED: {datetime.now().isoformat()}\n")
                    self.log_handle.flush()
                    self.log_handle.close()
                except:
                    pass
                self.log_handle = None
            
            self.current_process = None
            self._save_status()
            
            return {
                "status": "stopped",
                "message": "Learning session stopped",
                "session": self.session_status
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to stop learning session: {str(e)}",
                "session": self.session_status
            }
    
    def get_status(self) -> Dict:
        """Get current session status"""
        # Check if process is still running
        if self.current_process:
            if self.current_process.poll() is not None:
                # Process has ended
                # Close log file handle
                if self.log_handle:
                    try:
                        self.log_handle.write(f"\nPROCESS COMPLETED: {datetime.now().isoformat()}\n")
                        self.log_handle.flush()
                        self.log_handle.close()
                    except:
                        pass
                    self.log_handle = None
                
                self.current_process = None
                self.session_status["is_running"] = False
                self.session_status["pid"] = None
                self._save_status()
        
        # Also check status file for persistence
        self._load_status()
        
        return {
            "status": "running" if self.session_status.get("is_running") else "idle",
            "session": self.session_status
        }
    
    def _save_status(self):
        """Save session status to file"""
        try:
            self.status_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.status_file, 'w') as f:
                json.dump(self.session_status, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Error saving session status: {e}")
    
    def _load_status(self):
        """Load session status from file"""
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r') as f:
                    loaded = json.load(f)
                    # Only update if we don't have a running process
                    if not self.current_process:
                        self.session_status.update(loaded)
        except Exception as e:
            self.logger.warning(f"Error loading session status: {e}")


# Global instance
learning_session_service = LearningSessionService()

