"""
Master script to build complete SCOTUS database.
Runs fetching and ingestion in sequence.
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Run the complete SCOTUS database build process."""
    print("=" * 80)
    print("BUILDING COMPLETE SCOTUS DATABASE")
    print("=" * 80)
    print()
    print("This will:")
    print("  1. Fetch all SCOTUS opinions from the official website")
    print("  2. Download all PDFs (slip opinions, bound volumes, preliminary prints)")
    print("  3. Ingest all opinions into the RAG system")
    print()
    print("This may take a while depending on the number of opinions...")
    print()
    
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    print()
    print("=" * 80)
    print("STEP 1: FETCHING SCOTUS OPINIONS")
    print("=" * 80)
    print()
    
    # Run fetch script
    fetch_script = Path(__file__).parent / "fetch_scotus_opinions.py"
    result = subprocess.run([sys.executable, str(fetch_script)], 
                          capture_output=False)
    
    if result.returncode != 0:
        print()
        print("ERROR: Fetching failed. Please check the output above.")
        return
    
    print()
    print("=" * 80)
    print("STEP 2: INGESTING SCOTUS OPINIONS")
    print("=" * 80)
    print()
    
    # Run ingestion script
    ingest_script = Path(__file__).parent / "ingest_scotus_opinions.py"
    result = subprocess.run([sys.executable, str(ingest_script)],
                          capture_output=False)
    
    if result.returncode != 0:
        print()
        print("ERROR: Ingestion failed. Please check the output above.")
        return
    
    print()
    print("=" * 80)
    print("SCOTUS DATABASE BUILD COMPLETE!")
    print("=" * 80)
    print()
    print("Your system now has a comprehensive SCOTUS opinion database.")
    print("All opinions are available for legal research and analysis.")
    print()


if __name__ == "__main__":
    main()






