"""Estimate storage requirements for CAP cases"""
import requests
from bs4 import BeautifulSoup
import json

BASE_URL = "https://static.case.law"

def estimate_storage(jurisdiction="va"):
    """Estimate total storage needed"""
    print(f"Estimating storage for {jurisdiction}...")
    
    # Get volumes
    url = f"{BASE_URL}/{jurisdiction}/"
    response = requests.get(url, timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    volumes = set()
    for link in soup.find_all('a'):
        href = link.get('href', '')
        if f'/{jurisdiction}/' in href:
            parts = href.split(f'/{jurisdiction}/')
            if len(parts) > 1:
                vol_part = parts[1].split('/')[0].split('.')[0]
                if vol_part.isdigit():
                    volumes.add(vol_part)
    
    volumes = sorted([int(v) for v in volumes])
    print(f"Found {len(volumes)} volumes")
    
    # Sample a few volumes to estimate
    sample_volumes = volumes[:min(5, len(volumes))]
    total_cases = 0
    total_size = 0
    
    print(f"\nSampling {len(sample_volumes)} volumes to estimate...")
    for vol in sample_volumes:
        try:
            zip_url = f"{BASE_URL}/{jurisdiction}/{vol}.zip"
            response = requests.head(zip_url, timeout=10)
            if response.status_code == 200:
                zip_size = int(response.headers.get('Content-Length', 0))
                total_size += zip_size
                print(f"  Volume {vol}: {zip_size / (1024*1024):.1f} MB")
        except:
            pass
    
    if sample_volumes:
        avg_zip_size = total_size / len(sample_volumes)
        avg_cases_per_vol = 50  # Rough estimate - will vary
        estimated_total_size = avg_zip_size * len(volumes)
        estimated_total_cases = avg_cases_per_vol * len(volumes)
        
        print(f"\n{'='*60}")
        print(f"ESTIMATED STORAGE REQUIREMENTS")
        print(f"{'='*60}")
        print(f"Total volumes: {len(volumes)}")
        print(f"Estimated cases: {estimated_total_cases:,} - {estimated_total_cases * 2:,}")
        print(f"Estimated ZIP size: {estimated_total_size / (1024**3):.1f} GB")
        print(f"Estimated extracted size: {estimated_total_size * 2 / (1024**3):.1f} GB")
        print(f"{'='*60}")
        
        return {
            "volumes": len(volumes),
            "estimated_cases": estimated_total_cases,
            "estimated_size_gb": estimated_total_size / (1024**3)
        }

if __name__ == "__main__":
    estimate_storage("va")

