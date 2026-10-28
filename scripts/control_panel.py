import sys
import os
import subprocess
import threading
import json
import urllib.request
import urllib.error
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext


class SystemControlPanel(tk.Tk):
    """
    Desktop control panel for AKLAWMS / Virginia Legal AI.
    - Start / stop the system using existing .bat scripts
    - Show live backend / frontend status
    - Run full system check and show a summary
    """

    def __init__(self) -> None:
        super().__init__()

        self.title("AKLAWMS System Control Panel")
        self.geometry("780x520")
        self.resizable(False, False)

        self.project_root = Path(__file__).resolve().parent.parent
        self.start_script = self.project_root / "START_SYSTEM.bat"
        self.stop_script = self.project_root / "STOP_SYSTEM.bat"
        self.system_check_script = self.project_root / "scripts" / "system_check.py"
        self.system_check_report = self.project_root / "data" / "system_check_report.json"

        self._build_ui()

        # Initial status update and periodic refresh
        self.update_status()
        self.after(5000, self._schedule_status_refresh)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Top section: controls
        controls_frame = ttk.LabelFrame(main_frame, text="Controls", padding=10)
        controls_frame.pack(fill="x")

        start_btn = ttk.Button(
            controls_frame, text="Start System", command=self._on_start_system
        )
        start_btn.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        stop_btn = ttk.Button(
            controls_frame, text="Stop System", command=self._on_stop_system
        )
        stop_btn.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        check_btn = ttk.Button(
            controls_frame,
            text="Run Full System Check",
            command=self._on_run_system_check,
        )
        check_btn.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        refresh_btn = ttk.Button(
            controls_frame,
            text="Refresh Status Now",
            command=self.update_status,
        )
        refresh_btn.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # Log access buttons (standard ops convenience)
        backend_log_btn = ttk.Button(
            controls_frame,
            text="Open Backend Log",
            command=self._on_open_backend_log,
        )
        backend_log_btn.grid(row=1, column=0, padx=5, pady=(0, 5), sticky="w")

        frontend_log_btn = ttk.Button(
            controls_frame,
            text="Open Frontend Log",
            command=self._on_open_frontend_log,
        )
        frontend_log_btn.grid(row=1, column=1, padx=5, pady=(0, 5), sticky="w")

        logs_folder_btn = ttk.Button(
            controls_frame,
            text="Open Logs Folder",
            command=self._on_open_logs_folder,
        )
        logs_folder_btn.grid(row=1, column=2, padx=5, pady=(0, 5), sticky="w")

        # Middle section: status indicators
        status_frame = ttk.LabelFrame(main_frame, text="Live Status", padding=10)
        status_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(status_frame, text="Backend (FastAPI / port 5001):").grid(
            row=0, column=0, sticky="w"
        )
        self.backend_status_label = ttk.Label(status_frame, text="Unknown")
        self.backend_status_label.grid(row=0, column=1, sticky="w", padx=(5, 0))

        ttk.Label(status_frame, text="Frontend (React / port 3000):").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        self.frontend_status_label = ttk.Label(status_frame, text="Unknown")
        self.frontend_status_label.grid(row=1, column=1, sticky="w", padx=(5, 0))

        ttk.Label(status_frame, text="Last System Check:").grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )
        self.check_summary_label = ttk.Label(
            status_frame, text="No report loaded yet"
        )
        self.check_summary_label.grid(row=2, column=1, sticky="w", padx=(5, 0))

        # Bottom section: log output
        log_frame = ttk.LabelFrame(main_frame, text="System Check Output", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap="word", height=16, state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

        # Footer hint
        footer = ttk.Label(
            main_frame,
            text="This panel uses existing Windows scripts and health checks. "
            "It does not connect to any external services.",
            font=("", 8),
        )
        footer.pack(fill="x", pady=(6, 0))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_start_system(self) -> None:
        if not self.start_script.exists():
            messagebox.showerror(
                "Start System",
                f"Start script not found:\n{self.start_script}",
            )
            return

        try:
            # Use shell=True to honor .bat semantics on Windows
            subprocess.Popen(
                [str(self.start_script)],
                cwd=str(self.project_root),
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            messagebox.showinfo(
                "Start System",
                "System start script launched.\n"
                "Give it a few seconds and then check the status indicators.",
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Start System", f"Failed to start system:\n{exc}")

    def _on_stop_system(self) -> None:
        if not self.stop_script.exists():
            messagebox.showerror(
                "Stop System",
                f"Stop script not found:\n{self.stop_script}",
            )
            return

        try:
            subprocess.Popen(
                [str(self.stop_script)],
                cwd=str(self.project_root),
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            messagebox.showinfo(
                "Stop System",
                "System stop script launched.\n"
                "Backend and frontend processes should stop shortly.",
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Stop System", f"Failed to stop system:\n{exc}")

    def _on_run_system_check(self) -> None:
        if not self.system_check_script.exists():
            messagebox.showerror(
                "System Check",
                f"System check script not found:\n{self.system_check_script}",
            )
            return

        # Run in a background thread so the UI stays responsive
        thread = threading.Thread(target=self._run_system_check_worker, daemon=True)
        thread.start()

    def _on_open_backend_log(self) -> None:
        log_path = self.project_root / "backend.log"
        self._open_path(log_path, description="Backend log")

    def _on_open_frontend_log(self) -> None:
        log_path = self.project_root / "frontend.log"
        self._open_path(log_path, description="Frontend log")

    def _on_open_logs_folder(self) -> None:
        self._open_path(self.project_root, description="Project folder", is_dir=True)

    # ------------------------------------------------------------------
    # Background work
    # ------------------------------------------------------------------
    def _run_system_check_worker(self) -> None:
        self._append_log("\n=== Running full system check ===\n")
        try:
            process = subprocess.Popen(
                [sys.executable, str(self.system_check_script)],
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"Failed to start system_check.py: {exc}\n")
            return

        assert process.stdout is not None
        for line in process.stdout:
            self._append_log(line)

        exit_code = process.wait()
        self._append_log(f"\nSystem check finished with exit code {exit_code}\n")

        # Try to load the summary report
        self._load_system_check_summary()

    def _schedule_status_refresh(self) -> None:
        self.update_status()
        # Refresh every 5 seconds
        self.after(5000, self._schedule_status_refresh)

    # ------------------------------------------------------------------
    # Status and logs
    # ------------------------------------------------------------------
    def update_status(self) -> None:
        backend_ok, backend_detail = self._check_http("http://localhost:5001/health")
        frontend_ok, frontend_detail = self._check_http("http://localhost:3000")

        self._set_status_label(
            self.backend_status_label,
            backend_ok,
            ok_text="RUNNING",
            fail_text="NOT RUNNING",
            detail=backend_detail,
        )
        self._set_status_label(
            self.frontend_status_label,
            frontend_ok,
            ok_text="RUNNING",
            fail_text="NOT RUNNING",
            detail=frontend_detail,
        )

        # Also refresh last known system check summary
        self._load_system_check_summary()

    def _set_status_label(
        self,
        label: ttk.Label,
        ok: bool,
        ok_text: str,
        fail_text: str,
        detail: str | None = None,
    ) -> None:
        if ok:
            text = ok_text
            color = "green"
        else:
            text = fail_text
            color = "red"
        if detail:
            text = f"{text} ({detail})"
        label.config(text=text, foreground=color)

    def _check_http(self, url: str) -> tuple[bool, str | None]:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                status = response.getcode()
                if status == 200:
                    # For backend health, we may get JSON with a "status" field
                    try:
                        content_type = response.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            body = response.read().decode("utf-8")
                            data = json.loads(body)
                            status_value = data.get("status")
                            if status_value:
                                return True, status_value
                    except Exception:  # noqa: BLE001
                        # If parsing fails, still treat HTTP 200 as OK
                        return True, None
                    return True, None
                return False, f"HTTP {status}"
        except urllib.error.URLError as exc:
            return False, str(exc.reason)
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    def _load_system_check_summary(self) -> None:
        if not self.system_check_report.exists():
            self.check_summary_label.config(text="No system_check_report.json found")
            return

        try:
            with self.system_check_report.open("r", encoding="utf-8") as f:
                report = json.load(f)
        except Exception as exc:  # noqa: BLE001
            self.check_summary_label.config(
                text=f"Could not read system_check_report.json: {exc}"
            )
            return

        passed = len(report.get("passed", []))
        failed = len(report.get("failed", []))
        warnings = len(report.get("warnings", []))
        timestamp = report.get("timestamp", "unknown time")

        summary = (
            f"{passed} passed, {failed} failed, {warnings} warnings "
            f"({timestamp})"
        )
        self.check_summary_label.config(text=summary)

    def _open_path(
        self, path: Path, *, description: str = "File", is_dir: bool = False
    ) -> None:
        """
        Open a file or folder in the default Windows handler.
        """
        if not path.exists():
            messagebox.showwarning(
                "Open",
                f"{description} not found:\n{path}",
            )
            return

        try:
            # On Windows, os.startfile opens both files and directories
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "Open",
                f"Could not open {description}:\n{path}\n\nError: {exc}",
            )

    def _append_log(self, text: str) -> None:
        # Ensure log updates happen on the main thread
        def _do_append() -> None:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.after(0, _do_append)


def main() -> None:
    app = SystemControlPanel()
    app.mainloop()


if __name__ == "__main__":
    main()


