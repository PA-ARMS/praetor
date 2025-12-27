"""Check SCOTUS citations in database."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.rag_service import rag_service

rag_service._ensure_initialized()

results = rag_service.collection.get(
    where={"source": "SCOTUS Opinions"},
    limit=10
)

print(f"Found {len(results.get('ids', []))} SCOTUS opinions")
print()
print("Sample citations:")
for i, meta in enumerate(results.get('metadatas', [])[:10], 1):
    citation = meta.get('citation', 'MISSING')
    case = meta.get('case_name', 'N/A')[:50]
    print(f"{i}. Citation: '{citation}' | Case: {case}")






