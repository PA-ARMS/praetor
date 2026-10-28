#!/usr/bin/env python3
"""
Check that Ollama is running and the configured model is available.
Run from project root:  python scripts/check_ollama.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    import httpx
    from server.config import settings

    base = settings.OLLAMA_BASE_URL
    model = settings.OLLAMA_MODEL
    print(f"Ollama URL: {base}")
    print(f"Configured model: {model}")
    print()

    try:
        r = httpx.get(f"{base}/api/tags", timeout=5.0)
        r.raise_for_status()
        data = r.json()
        models = data.get("models") or []
        names = [m.get("name", "") for m in models]
        print(f"Ollama is running. Models listed: {len(names)}")
        for n in names:
            print(f"  - {n}")

        if model in names:
            print(f"\nOK: Model '{model}' is available.")
            return 0
        # Tagged variant (e.g. qwen2.5:3b-q4_0)
        if any(n == model or n.startswith(model + "-") or n.startswith(model + ":") for n in names):
            print(f"\nOK: A variant of '{model}' is available.")
            return 0
        print(f"\nModel '{model}' not found. Run:  ollama run {model}")
        return 1
    except httpx.ConnectError:
        print("Ollama is not running. Start it with:  ollama serve")
        print("Then run:  ollama run " + model)
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
