"""Test the full chat flow to diagnose issues"""
import requests
import json
import sys
import time

print("=== Chat Flow Diagnostic Test ===\n")

# Step 1: Test login
print("1. Testing login...")
try:
    login_response = requests.post(
        "http://localhost:5000/api/auth/login",
        json={"username": "test", "password": "test123456789"},
        timeout=5
    )
    if login_response.status_code == 200:
        token = login_response.json().get("access_token")
        print(f"   ✓ Login successful (token received)")
    else:
        print(f"   ✗ Login failed: {login_response.status_code}")
        print(f"   Response: {login_response.text}")
        print("\n   NOTE: You may need to create a test user first.")
        sys.exit(1)
except Exception as e:
    print(f"   ✗ Login error: {e}")
    sys.exit(1)

# Step 2: Test chat endpoint
print("\n2. Testing chat endpoint...")
headers = {"Authorization": f"Bearer {token}"}
chat_payload = {
    "message": "What is assault?",
    "conversation_id": "test_diagnostic",
    "use_rag": True,
    "max_results": 10  # Limit for speed
}

print(f"   Sending request: {chat_payload['message']}")
print("   Waiting for response (this may take 30-60 seconds)...")

start_time = time.time()
try:
    chat_response = requests.post(
        "http://localhost:5000/api/chat/query",
        json=chat_payload,
        headers=headers,
        timeout=180  # 3 minute timeout
    )
    elapsed = time.time() - start_time
    
    print(f"   Response received in {elapsed:.1f} seconds")
    print(f"   Status code: {chat_response.status_code}")
    
    if chat_response.status_code == 200:
        data = chat_response.json()
        response_text = data.get('response', '')
        print(f"   ✓ SUCCESS!")
        print(f"   Response length: {len(response_text)} characters")
        print(f"   Sources found: {len(data.get('sources', []))}")
        print(f"   Response preview: {response_text[:200]}...")
    else:
        print(f"   ✗ Error: {chat_response.status_code}")
        print(f"   Response: {chat_response.text}")
        
except requests.exceptions.Timeout:
    elapsed = time.time() - start_time
    print(f"   ✗ TIMEOUT after {elapsed:.1f} seconds")
    print("   The request took too long. Possible issues:")
    print("   - Ollama is not responding")
    print("   - Model is too slow")
    print("   - RAG search is taking too long")
    
except Exception as e:
    elapsed = time.time() - start_time
    print(f"   ✗ ERROR after {elapsed:.1f} seconds: {type(e).__name__}")
    print(f"   {str(e)}")

print("\n=== Test Complete ===")







