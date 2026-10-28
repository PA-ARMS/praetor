#!/usr/bin/env python3
"""
Live progress window for Virginia Code corpus rebuild.

Reads data/va_corpus_update_progress.json (written by update_va_legal_corpus.py).
Works for a rebuild already running or started from this window.

Usage:
    python scripts/va_rebuild_progress_gui.py
    SHOW_VA_REBUILD_PROGRESS.bat
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from corpus_progress import PROGRESS_PATH, LOCK_PATH, read_progress  # noqa: E402

UPDATE_SCRIPT = PROJECT_ROOT / "scripts" / "update_va_legal_corpus.py"
STATUS_PATH = PROJECT_ROOT / "data" / "va_law_update_status.json"
LOG_PATH = PROJECT_ROOT / "logs" / "va_law_update.log"


class VARebuildProgressGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Virginia Law Corpus Rebuild — Progress")
        self.geometry("720x520")
        self.minsize(560, 400)

        self.process = None
        self._poll_job = None

        self._build_ui()
        self._poll()

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        status_frame = ttk.LabelFrame(main, text="Rebuild status", padding=8)
        status_frame.pack(fill="x", pady=(0, 8))

        self.phase_label = ttk.Label(
            status_frame, text="Checking…", font=("Segoe UI", 11, "bold")
        )
        self.phase_label.pack(anchor="w")

        self.detail_label = ttk.Label(
            status_frame, text="", font=("Segoe UI", 9), foreground="#444"
        )
        self.detail_label.pack(anchor="w", pady=(4, 0))

        self.overall_var = tk.DoubleVar(value=0)
        ttk.Label(status_frame, text="Overall progress").pack(anchor="w", pady=(8, 2))
        self.overall_bar = ttk.Progressbar(
            status_frame, variable=self.overall_var, maximum=100, mode="determinate"
        )
        self.overall_bar.pack(fill="x")

        self.phase_var = tk.DoubleVar(value=0)
        ttk.Label(status_frame, text="Current step").pack(anchor="w", pady=(8, 2))
        self.phase_bar = ttk.Progressbar(
            status_frame, variable=self.phase_var, maximum=100, mode="determinate"
        )
        self.phase_bar.pack(fill="x")

        self.pct_label = ttk.Label(status_frame, text="0%", font=("Segoe UI", 9))
        self.pct_label.pack(anchor="e", pady=(4, 0))

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=(0, 8))

        self.start_btn = ttk.Button(
            btn_frame,
            text="Start rebuild (download + ingest)",
            command=lambda: self._start_rebuild(["--force"]),
        )
        self.start_btn.pack(side="left", padx=(0, 6))

        ttk.Button(
            btn_frame,
            text="Ingest only (CSVs on disk)",
            command=lambda: self._start_rebuild(["--ingest-only"]),
        ).pack(side="left", padx=(0, 6))

        self.stop_btn = ttk.Button(
            btn_frame, text="Stop", command=self._on_stop, state="disabled"
        )
        self.stop_btn.pack(side="left")

        ttk.Button(btn_frame, text="Refresh", command=self._poll).pack(side="right")

        log_frame = ttk.LabelFrame(main, text="Details", padding=4)
        log_frame.pack(fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, font=("Consolas", 9), height=12, state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Keep Ollama running (START_OLLAMA_GPU.bat). Do not use chat heavily during rebuild.",
            font=("Segoe UI", 8),
            foreground="gray",
        ).pack(anchor="w", pady=(8, 0))

    def _set_log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, text)
        self.log_text.configure(state="disabled")

    def _phase_title(self, phase: str) -> str:
        titles = {
            "idle": "Idle — no rebuild in progress",
            "starting": "Starting…",
            "download": "Downloading CSV files from LIS",
            "purge": "Purging old Virginia Code vectors",
            "statutes": "Ingesting Code of Virginia",
            "uncodified": "Ingesting session / uncodified acts",
            "search_tests": "Running citation spot-checks",
            "complete": "Complete",
            "failed": "Failed",
            "unknown": "Unknown",
        }
        return titles.get(phase, phase.replace("_", " ").title())

    def _poll(self):
        p = read_progress()
        phase = p.get("phase", "idle")
        running = p.get("running", False) or (
            self.process is not None and self.process.poll() is None
        )

        self.phase_label.config(
            text=("▶ " if running else "■ ") + self._phase_title(phase)
        )

        current = int(p.get("current") or 0)
        total = p.get("total")
        msg = p.get("message") or ""
        if total:
            detail = f"{msg}  ({current:,} / {int(total):,})"
        else:
            detail = msg or (
                "Waiting for progress file…"
                if running
                else "Start a rebuild or run UPDATE_VA_LAWS.bat"
            )
        self.detail_label.config(text=detail)

        overall = float(p.get("overall_percent") or 0)
        phase_pct = float(p.get("phase_percent") or 0)
        self.overall_var.set(overall)
        self.phase_var.set(phase_pct)
        self.pct_label.config(
            text=f"Overall {overall:.0f}%  ·  Step {phase_pct:.0f}%"
        )

        lines = [
            f"Updated: {p.get('updated_at', '—')}",
            f"Running: {running}",
            f"Phase: {phase}",
            f"Progress file: {PROGRESS_PATH}",
            f"Lock file: {'yes' if LOCK_PATH.exists() else 'no'}",
            "",
        ]
        if STATUS_PATH.exists():
            try:
                st = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
                lines.append("Last finished run:")
                lines.append(f"  success: {st.get('success')}")
                lines.append(f"  completed: {st.get('last_run_completed', '—')}")
                if st.get("steps"):
                    for k, v in st.get("steps", {}).items():
                        if isinstance(v, (int, float)):
                            lines.append(f"  {k}: {v:,}")
                        elif isinstance(v, dict) and "downloaded" in v:
                            lines.append(
                                f"  download: {v.get('downloaded')} new, {v.get('failed')} failed"
                            )
            except Exception:
                pass
        if LOG_PATH.exists():
            try:
                tail = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
                lines.append("")
                lines.append("Log tail:")
                lines.extend(tail)
            except Exception:
                pass

        self._set_log("\n".join(lines))

        if running:
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
        elif self.process is None:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")

        self._poll_job = self.after(1500, self._poll)

    def _start_rebuild(self, extra_args: list):
        if self.process and self.process.poll() is None:
            messagebox.showwarning("Running", "A rebuild is already running.")
            return
        if not UPDATE_SCRIPT.exists():
            messagebox.showerror("Missing", f"Not found: {UPDATE_SCRIPT}")
            return

        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(UPDATE_SCRIPT), *extra_args]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            log_f = open(LOG_PATH, "a", encoding="utf-8")
            log_f.write(f"\n\n=== GUI started rebuild {extra_args} ===\n")
            self.process = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=log_f,
                stderr=subprocess.STDOUT,
                env=env,
            )
            log_f.close()
        except Exception as e:
            messagebox.showerror("Start failed", str(e))
            return

        self.stop_btn.config(state="normal")
        self.start_btn.config(state="disabled")
        threading.Thread(target=self._wait_proc, daemon=True).start()
        self._poll()

    def _wait_proc(self):
        if self.process:
            self.process.wait()
        self.after(0, lambda: self._on_proc_done())

    def _on_proc_done(self):
        self.process = None
        self._poll()

    def _on_stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.stop_btn.config(state="disabled")
        self.start_btn.config(state="normal")

    def destroy(self):
        if self._poll_job:
            self.after_cancel(self._poll_job)
        super().destroy()


if __name__ == "__main__":
    app = VARebuildProgressGUI()
    app.mainloop()
