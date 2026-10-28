"""
Ingestion Progress GUI
=====================
On-screen GUI showing real-time progress of the legal database build.
Runs verify_and_complete_database.py and displays live output.
"""
import os
import sys
import subprocess
import threading
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext

# Fix encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "verify_and_complete_database.py"
COMPLETE_SCRIPT = PROJECT_ROOT / "scripts" / "complete_legal_database.py"


class IngestionProgressGUI(tk.Tk):
    """GUI showing live ingestion progress."""

    def __init__(self):
        super().__init__()
        self.title("Legal Database Build - Progress")
        self.geometry("750x550")
        self.minsize(600, 400)

        self.process = None
        self.is_running = False
        self.current_step = "Idle"
        self.ingested_count = 0
        self._build_script = VERIFY_SCRIPT

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        # Status section
        status_frame = ttk.LabelFrame(main, text="Status", padding=8)
        status_frame.pack(fill="x", pady=(0, 8))

        self.step_label = ttk.Label(
            status_frame,
            text="Ready. Click 'Start Build' to begin.",
            font=("Segoe UI", 10, "bold"),
        )
        self.step_label.pack(anchor="w")

        self.detail_label = ttk.Label(
            status_frame,
            text="",
            font=("Segoe UI", 9),
            foreground="gray",
        )
        self.detail_label.pack(anchor="w")

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.pack(fill="x", pady=(8, 0))

        # Script choice
        choice_frame = ttk.Frame(main)
        choice_frame.pack(fill="x", pady=(0, 4))
        ttk.Label(choice_frame, text="Build type:").pack(side="left", padx=(0, 8))
        self.script_var = tk.StringVar(value="verify")
        ttk.Radiobutton(
            choice_frame,
            text="Verify & Ingest (existing downloads only)",
            variable=self.script_var,
            value="verify",
        ).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(
            choice_frame,
            text="Complete (download + ingest all sources)",
            variable=self.script_var,
            value="complete",
        ).pack(side="left")

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=(0, 8))

        self.start_btn = ttk.Button(
            btn_frame,
            text="Start Build",
            command=self._on_start,
        )
        self.start_btn.pack(side="left", padx=(0, 5))

        self.stop_btn = ttk.Button(
            btn_frame,
            text="Stop",
            command=self._on_stop,
            state="disabled",
        )
        self.stop_btn.pack(side="left")

        # Log output
        log_frame = ttk.LabelFrame(main, text="Live Output", padding=4)
        log_frame.pack(fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            height=20,
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

        # Footer
        footer = ttk.Label(
            main,
            text="Ensure Ollama is running (ollama serve) with nomic-embed-text model.",
            font=("Segoe UI", 8),
            foreground="gray",
        )
        footer.pack(anchor="w", pady=(8, 0))

    def _log(self, text: str):
        """Append text to log area."""
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _update_step(self, step: str, detail: str = ""):
        """Update status labels."""
        self.current_step = step
        self.step_label.config(text=step)
        self.detail_label.config(text=detail)

    def _parse_progress(self, line: str):
        """Parse output line for progress indicators."""
        # Step headers: [STEP 2/5] Ingesting Virginia Code...
        step_match = re.search(r'\[STEP (\d+)/(\d+)\]', line)
        if step_match:
            n, total = int(step_match.group(1)), int(step_match.group(2))
            pct = (n - 1) / total * 100  # Approximate - step just started
            self.progress_var.set(pct)
            return

        # "Ingested 500 sections..." or "Ingested 1,234 sections..."
        ingest_match = re.search(r'Ingested\s+([\d,]+)\s+sections', line)
        if ingest_match:
            self.ingested_count = int(ingest_match.group(1).replace(",", ""))
            self.detail_label.config(text=f"Virginia Code: {self.ingested_count:,} sections ingested")
            # Rough progress: assume ~15k VA sections = 30% of total build
            if self.ingested_count > 0:
                pct = min(30, (self.ingested_count / 15000) * 30)
                self.progress_var.set(pct)
            return

        # "Ingested X from SOURCE"
        source_match = re.search(r'Ingested (\d+) from (\w+)', line)
        if source_match:
            count, source = source_match.group(1), source_match.group(2)
            self.detail_label.config(text=f"{source}: {count} documents ingested")
            return

        # "Ingestion complete: X ingested"
        complete_match = re.search(r'Ingestion complete:\s*([\d,]+)\s+ingested', line)
        if complete_match:
            total = int(complete_match.group(1).replace(",", ""))
            self.progress_var.set(35)  # Step 2 done
            return

        # "COMPLETION SUMMARY" or "PRODUCTION READINESS SUMMARY"
        if "COMPLETION SUMMARY" in line or "PRODUCTION READINESS" in line:
            self.progress_var.set(100)
            self._update_step("Build complete!", "Check output above for results.")

    def _run_build(self):
        """Run verify script in subprocess (worker thread)."""
        self.is_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress_var.set(0)
        self.ingested_count = 0
        script_name = self._build_script.name
        self._update_step("Starting build...", f"Launching {script_name}")
        self._log("=" * 60 + "\n")
        self._log("Legal Database Build - Live Output\n")
        self._log("=" * 60 + "\n\n")

        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            self.process = subprocess.Popen(
                [sys.executable, str(self._build_script)],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                bufsize=1,
            )

            for line in iter(self.process.stdout.readline, ""):
                if not self.is_running:
                    break
                line = line.rstrip()
                if line:
                    self.after(0, lambda l=line: self._log(l + "\n"))
                    self.after(0, lambda l=line: self._parse_progress(l))

            self.process.wait()
        except Exception as e:
            self.after(0, lambda: self._log(f"\nError: {e}\n"))
        finally:
            self.after(0, self._on_finished)

    def _on_start(self):
        """Start the build."""
        script = COMPLETE_SCRIPT if self.script_var.get() == "complete" else VERIFY_SCRIPT
        if not script.exists():
            self._log(f"Error: Script not found: {script}\n")
            return
        self._build_script = script
        thread = threading.Thread(target=self._run_build, daemon=True)
        thread.start()

    def _on_stop(self):
        """Stop the build."""
        self.is_running = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self._log("\n[Build stopped by user]\n")

    def _on_finished(self):
        """Called when build finishes."""
        self.is_running = False
        self.process = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if self.progress_var.get() < 100:
            self._update_step("Build finished", "See output above for details.")


if __name__ == "__main__":
    app = IngestionProgressGUI()
    app.mainloop()
