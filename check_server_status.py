import urllib.request
import json
import sys

try:
    with urllib.request.urlopen("http://localhost:5000/health") as response:
        if response.status == 200:
            print("Backend is responding (200 OK)")
            sys.exit(0)
        else:
            print(f"Backend responded with status {response.status}")
            sys.exit(1)
except Exception as e:
    print(f"Could not connect to backend: {e}")
    sys.exit(1)












