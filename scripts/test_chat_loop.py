"""
Test chat in a loop until it works.
- Polls /api/chat/ready until backend + Ollama + model are ready.
- If TEST_USER and TEST_PASSWORD are set, logs in and sends a test message until it succeeds.

Usage (from repo root):
  set TEST_USER=your_username
  set TEST_PASSWORD=your_password
  python scripts/test_chat_loop.py

Or without credentials (ready check only):
  python scripts/test_chat_loop.py
"""
import os
import sys
import time
import urllib.request
import urllib.error
import json

# Run from repo root so server config can load
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO_ROOT)
sys.path.insert(0, REPO_ROOT)

BASE = os.environ.get("TEST_API_BASE", "http://localhost:5001")
READY_URL = f"{BASE}/api/chat/ready"
LOGIN_URL = f"{BASE}/api/auth/login"
CHAT_URL = f"{BASE}/api/chat/simple"
MAX_READY_ATTEMPTS = 60   # 60 * 2s = 2 min
MAX_CHAT_ATTEMPTS = 5
READY_INTERVAL = 2
CHAT_RETRY_INTERVAL = 10


def get_ready():
    try:
        req = urllib.request.Request(READY_URL)
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ready": False, "message": str(e)}


def login(username: str, password: str):
    try:
        data = json.dumps({"username": username, "password": password}).encode()
        req = urllib.request.Request(LOGIN_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as r:
            out = json.loads(r.read().decode())
            return out.get("access_token")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise Exception(f"Login failed {e.code}: {body}")
    except Exception as e:
        raise Exception(f"Login error: {e}")


def send_test_message(token: str):
    try:
        data = json.dumps({"message": "What is 1+1? Reply with just the number.", "use_rag": False}).encode()
        req = urllib.request.Request(CHAT_URL, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=120) as r:
            out = json.loads(r.read().decode())
            return out.get("response", "").strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return (None, f"HTTP {e.code}: {body[:500]}")
    except Exception as e:
        return (None, str(e))


def main():
    print("Chat test loop – will keep trying until chat is working.\n")
    print(f"  Ready: {READY_URL}")
    print(f"  Chat:  {CHAT_URL}\n")

    # 1) Loop until /api/chat/ready says ready
    for attempt in range(1, MAX_READY_ATTEMPTS + 1):
        r = get_ready()
        if r.get("ready"):
            print(f"[{attempt}] Chat ready. Model: {r.get('model', '?')}")
            break
        msg = r.get("message", r.get("ollama", "unknown"))
        print(f"[{attempt}] Not ready: {msg}")
        if attempt == MAX_READY_ATTEMPTS:
            print("\nGiving up on ready check. Fix Ollama/model and run again.")
            return 1
        time.sleep(READY_INTERVAL)

    # 2) Optional: login and send test message until success
    user = os.environ.get("TEST_USER", "").strip()
    pwd = os.environ.get("TEST_PASSWORD", "").strip()
    if not user or not pwd:
        print("\nChat is ready. To test a full message, set TEST_USER and TEST_PASSWORD and run again.")
        return 0

    print("\nLogging in and sending test message...")
    try:
        token = login(user, pwd)
    except Exception as e:
        print(f"Login failed: {e}")
        return 1

    for attempt in range(1, MAX_CHAT_ATTEMPTS + 1):
        result = send_test_message(token)
        if isinstance(result, tuple):
            _resp, err = result
            print(f"[{attempt}] Chat error: {err}")
            if "unable to allocate CPU buffer" in (err or ""):
                print("  -> Use a smaller model (e.g. OLLAMA_MODEL=llama3.2:3b) or ensure GPU is used (OLLAMA_NUM_GPU=-1).")
            if attempt < MAX_CHAT_ATTEMPTS:
                time.sleep(CHAT_RETRY_INTERVAL)
            else:
                return 1
        else:
            print(f"[{attempt}] Chat OK. Response: {result[:200]}{'...' if len(result) > 200 else ''}")
            print("\nChat is working.")
            return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
