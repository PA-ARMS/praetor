import requests
import json
import time

# Auth - trying default admin credentials if paralegal1 fails
users_to_try = [
    {"username": "paralegal1", "password": "password123"},
    {"username": "admin", "password": "adminpassword"},
    {"username": "admin", "password": "password123"} 
]

token = None
headers = None

print("Attempting to login...")

for creds in users_to_try:
    try:
        print(f"Trying user: {creds['username']}...")
        auth_resp = requests.post("http://localhost:5000/api/auth/login", json=creds)
        
        if auth_resp.status_code == 200:
            token = auth_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print(f"Login successful as {creds['username']}")
            break
        else:
            print(f"Failed: {auth_resp.status_code} - {auth_resp.text}")
    except Exception as e:
        print(f"Connection error: {e}")

if not token:
    print("All login attempts failed. Exiting.")
    exit(1)

# Chat Query
print("\nSending test query...")
query_data = {
    "message": "What are the penalties for a first time DUI in Virginia?",
    "use_rag": True,
    "detail_level": "standard"
}

try:
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
    print(f"Error during query: {e}")












