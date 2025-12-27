import requests
import json
import time

# Auth
login_data = {
    "username": "paralegal1",
    "password": "password123"
}

print("Logging in...")
try:
    auth_resp = requests.post("http://localhost:5000/api/auth/login", data=login_data)
    if auth_resp.status_code != 200:
        print(f"Login failed: {auth_resp.text}")
        exit(1)
    
    token = auth_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")

    # Chat Query
    print("\nSending test query...")
    query_data = {
        "message": "What are the penalties for a first time DUI in Virginia?",
        "use_rag": True,
        "detail_level": "standard"
    }
    
    start_time = time.time()
    chat_resp = requests.post("http://localhost:5000/api/chat/query", json=query_data, headers=headers, timeout=300)
    duration = time.time() - start_time
    
    if chat_resp.status_code == 200:
        result = chat_resp.json()
        print(f"\nQuery successful ({duration:.2f}s)")
        print("-" * 50)
        print(f"Response:\n{result.get('response')}")
        print("-" * 50)
        print(f"Sources found: {len(result.get('sources', []))}")
    else:
        print(f"Query failed: {chat_resp.status_code} - {chat_resp.text}")

except Exception as e:
    print(f"Error: {e}")

