"""Quick test of CourtListener API for SCOTUS opinions."""
import requests

url = "https://www.courtlistener.com/api/rest/v3/search/"
params = {
    "q": "court:scotus",
    "type": "o",
    "page_size": 5
}

try:
    r = requests.get(url, params=params, timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(f"Total count: {data.get('count', 'N/A')}")
    print(f"Results on this page: {len(data.get('results', []))}")
    
    if data.get('results'):
        sample = data['results'][0]
        print(f"\nSample opinion:")
        print(f"  Case: {sample.get('case_name', 'N/A')}")
        print(f"  Date: {sample.get('date_filed', 'N/A')}")
        print(f"  Citation: {sample.get('citation', 'N/A')}")
        print(f"  PDF: {sample.get('pdf', 'N/A')}")
except Exception as e:
    print(f"Error: {e}")







