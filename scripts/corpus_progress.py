"""
Shared progress file for Virginia corpus rebuild (update_va_legal_corpus.py).
Read by va_rebuild_progress_gui.py and optional API.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROGRESS_PATH = PROJECT_ROOT / "data" / "va_corpus_update_progress.json"
LOCK_PATH = PROJECT_ROOT / "data" / ".va_corpus_update.lock"

# Phase weights for overall percent (sum = 100)
PHASE_WEIGHTS = {
    "starting": 0,
    "download": 5,
    "purge": 7,
    "statutes": 70,
    "uncodified": 15,
    "search_tests": 2,
    "complete": 100,
    "failed": 100,
}


def read_progress() -> Dict[str, Any]:
    if not PROGRESS_PATH.exists():
        return {"running": LOCK_PATH.exists(), "phase": "idle"}
    try:
        data = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        data["running"] = LOCK_PATH.exists()
        return data
    except Exception:
        return {"running": LOCK_PATH.exists(), "phase": "unknown", "error": "Could not read progress file"}


def write_progress(
    phase: str,
    message: str = "",
    current: int = 0,
    total: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Write progress snapshot for GUI / monitoring."""
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing: Dict[str, Any] = {}
    if PROGRESS_PATH.exists():
        try:
            existing = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    phase_pct = 0.0
    if total and total > 0:
        phase_pct = min(100.0, (current / total) * 100.0)

    base = PHASE_WEIGHTS.get(phase, 0)
    prev_phase = existing.get("phase", "")
    # Overall: completed prior phases + fraction of current phase band
    overall = float(base)
    if phase == "statutes" and total:
        overall = PHASE_WEIGHTS["purge"] + (phase_pct / 100.0) * (
            PHASE_WEIGHTS["statutes"] - PHASE_WEIGHTS["purge"]
        )
    elif phase == "uncodified" and total:
        overall = PHASE_WEIGHTS["statutes"] + (phase_pct / 100.0) * (
            PHASE_WEIGHTS["uncodified"] - PHASE_WEIGHTS["statutes"]
        )
    elif phase in ("search_tests", "complete", "failed"):
        overall = PHASE_WEIGHTS.get(phase, 100)
    elif phase == "purge":
        overall = PHASE_WEIGHTS["purge"] if phase_pct >= 100 else PHASE_WEIGHTS["starting"] + 2

    payload: Dict[str, Any] = {
        "updated_at": datetime.now().isoformat(),
        "running": LOCK_PATH.exists(),
        "phase": phase,
        "message": message,
        "current": current,
        "total": total,
        "phase_percent": round(phase_pct, 1),
        "overall_percent": round(min(100.0, overall), 1),
        "started_at": existing.get("started_at") or datetime.now().isoformat(),
    }
    if extra:
        payload.update(extra)
    if phase in ("complete", "failed"):
        payload["running"] = False

    PROGRESS_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def init_progress(run_mode: str = "full") -> None:
    write_progress(
        "starting",
        message=f"Virginia corpus update started ({run_mode})",
        current=0,
        total=1,
        extra={"run_mode": run_mode},
    )
