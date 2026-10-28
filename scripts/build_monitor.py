"""
Build Monitor - Watch running build output in real time
========================================================
Displays live output from a database build running in another terminal.
Use this to monitor complete_legal_database.py or verify_and_complete_database.py.
"""
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog

# Fix encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Cursor stores terminal output in .cursor/projects/<slug>/terminals/
def find_terminal_files():
    """Find terminal files that might contain build output."""
    candidates = []
    term_dir = Path.home() / ".cursor" / "projects" / "c-LAWFIRMAI" / "terminals"
    if term_dir.exists():
        for f in term_dir.glob("*.txt"):
            try:
                candidates.append(f)
            except Exception:
                pass
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[:10]


class BuildMonitorGUI(tk.Tk):
    """GUI that tails a file and displays it."""

    def __init__(self):
        super().__init__()
        self.title("Build Monitor - Live Output")
        self.geometry("900x600")
        self.minsize(700, 400)

        self.watch_path = None
        self.last_size = 0
        self._refresh_job = None

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        # File selection
        sel_frame = ttk.LabelFrame(main, text="Monitor Source", padding=8)
        sel_frame.pack(fill="x", pady=(0, 8))

        row = ttk.Frame(sel_frame)
        row.pack(fill="x")

        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(row, textvariable=self.path_var, width=70)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ttk.Button(row, text="Browse...", command=self._on_browse).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Find Terminals", command=self._on_find_terminals).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Start Watching", command=self._on_start_watch).pack(side="left")

        self.status_label = ttk.Label(sel_frame, text="Select a file and click Start Watching", foreground="gray")
        self.status_label.pack(anchor="w", pady=(4, 0))

        # Output
        out_frame = ttk.LabelFrame(main, text="Live Output", padding=4)
        out_frame.pack(fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(
            out_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            height=25,
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

        # Auto-try to find and watch
        self.after(500, self._auto_find_and_watch)

    def _on_browse(self):
        path = filedialog.askopenfilename(
            title="Select log file to monitor",
            initialdir=Path.home(),
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.path_var.set(path)
            self._on_start_watch()

    def _on_find_terminals(self):
        files = find_terminal_files()
        if not files:
            self.status_label.config(text="No terminal files found. Run the build in a Cursor terminal first.")
            return
        # Pick most recently modified (likely the active build)
        best = max(files, key=lambda p: p.stat().st_mtime)
        self.path_var.set(str(best))
        self.status_label.config(text=f"Found: {best.name} (most recent)")
        self._on_start_watch()

    def _auto_find_and_watch(self):
        """Try to find and start watching automatically."""
        files = find_terminal_files()
        if files:
            best = max(files, key=lambda p: p.stat().st_mtime)
            self.path_var.set(str(best))
            self.status_label.config(text=f"Watching: {best.name}")
            self._on_start_watch()

    def _on_start_watch(self):
        path_str = self.path_var.get().strip()
        if not path_str:
            self.status_label.config(text="Enter or select a file path")
            return
        path = Path(path_str)
        if not path.exists():
            self.status_label.config(text=f"File not found: {path}")
            return
        self.watch_path = path
        self.last_size = 0
        self.status_label.config(text=f"Watching: {path.name} (refreshing every 2 sec)")
        self._schedule_refresh()

    def _schedule_refresh(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        if self.watch_path and self.watch_path.exists():
            self._refresh()
        self._refresh_job = self.after(2000, self._schedule_refresh)

    def _refresh(self):
        if not self.watch_path or not self.watch_path.exists():
            return
        try:
            with open(self.watch_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Only append new content (tail behavior)
            if len(content) > self.last_size:
                new_content = content[self.last_size:]
                self.log_text.configure(state="normal")
                self.log_text.insert(tk.END, new_content)
                self.log_text.see(tk.END)
                self.log_text.configure(state="disabled")
                self.last_size = len(content)
        except Exception as e:
            self.status_label.config(text=f"Error: {e}")

    def destroy(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        super().destroy()


if __name__ == "__main__":
    app = BuildMonitorGUI()
    app.mainloop()
