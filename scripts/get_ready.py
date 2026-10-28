#!/usr/bin/env python3
"""
Get Everything Ready - One-shot setup for Virginia Legal AI.

- Ensures .env exists (from server/.env.example)
- Installs Python dependencies (server/requirements.txt)
- Downloads spaCy model for entity extraction
- Optionally runs production_setup.py for secrets

Usage:
    python scripts/get_ready.py
    python scripts/get_ready.py --production   # Also run production_setup.py
"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = PROJECT_ROOT / "server" / ".env.example"
ENV_PATH = PROJECT_ROOT / ".env"
REQUIREMENTS = PROJECT_ROOT / "server" / "requirements.txt"


def run(cmd: list[str], cwd: Path = None, env=None) -> bool:
    """Run command; return True if success."""
    cwd = cwd or PROJECT_ROOT
    try:
        subprocess.run(
            cmd,
            cwd=cwd,
            env=env or os.environ,
            check=True,
            capture_output=False,
        )
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False


def main() -> int:
    print("=" * 60)
    print("Virginia Legal AI - Get Everything Ready")
    print("=" * 60)
    print()

    # 1. Ensure .env exists
    if not ENV_PATH.exists() and ENV_EXAMPLE.exists():
        import shutil
        shutil.copy(ENV_EXAMPLE, ENV_PATH)
        print("[OK] Created .env from server/.env.example")
    elif ENV_PATH.exists():
        print("[OK] .env already exists")
    else:
        print("[WARN] server/.env.example not found; create .env manually")
    print()

    # 2. Install Python dependencies
    print("Installing Python dependencies...")
    if not REQUIREMENTS.exists():
        print("[ERROR] server/requirements.txt not found")
        return 1
    if run([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)]):
        print("[OK] pip install -r server/requirements.txt")
    else:
        print("[WARN] pip install failed; run manually: pip install -r server/requirements.txt")
    print()

    # 3. Download spaCy model (for document pipeline entity extraction)
    print("Downloading spaCy model (en_core_web_sm)...")
    if run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"]):
        print("[OK] spaCy model en_core_web_sm")
    else:
        print("[WARN] spacy download failed; entity extraction may be limited.")
        print("       Run manually: python -m spacy download en_core_web_sm")
    print()

    # 4. Optional: production setup
    if "--production" in sys.argv or "-p" in sys.argv:
        print("Running production_setup.py...")
        setup_script = PROJECT_ROOT / "scripts" / "production_setup.py"
        if setup_script.exists() and run([sys.executable, str(setup_script)]):
            print("[OK] production_setup.py")
        else:
            print("[WARN] production_setup.py failed or not found")
        print()
    else:
        print("Tip: Run with --production to generate JWT/ENCRYPTION_KEY and set CORS.")
        print("     python scripts/get_ready.py --production")
        print()

    # 5. Quick import check
    print("Verifying server imports...")
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from server.config import settings
        from server.services.document_pipeline_service import document_pipeline_service
        print("[OK] Config and document pipeline load successfully")
    except Exception as e:
        print(f"[WARN] Import check: {e}")
    print()

    print("=" * 60)
    print("Ready. Next steps:")
    print("  1. (Optional) Run production_setup: python scripts/production_setup.py")
    print("  2. Start backend:  python server/main.py")
    print("  3. Start frontend: cd client && npm run dev")
    print("  4. (Optional) Table extraction needs Java 8+ for tabula-py")
    print("  5. (Optional) Tesseract for OCR: see docs/OCR_SETUP.md")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
