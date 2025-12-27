"""
Fix ChromaDB search - rebuild index with proper HNSW settings
"""
import chromadb
from chromadb.config import Settings
import sqlite3
import time
import sys

print("=" * 70)
print("ChromaDB Index Diagnostic and Fix")
print("=" * 70)

# Check current database state
print("\n1. Checking database state...")
conn = sqlite3.connect('data/chroma_db/chroma.sqlite3')
c = conn.cursor()

# Count documents
c.execute("SELECT COUNT(*) FROM embeddings")
count = c.fetchone()[0]
print(f"   Documents in embeddings table: {count}")

# Check collection info
c.execute("SELECT * FROM collections")
coll = c.fetchone()
print(f"   Collection: {coll}")

conn.close()

# Try to initialize ChromaDB with different settings
print("\n2. Initializing ChromaDB client...")
start = time.time()

client = chromadb.PersistentClient(
    path="data/chroma_db",
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)

elapsed = time.time() - start
print(f"   Client initialized in {elapsed:.2f}s")

# Get collection
print("\n3. Getting collection...")
start = time.time()
collection = client.get_collection("legal_corpus")
elapsed = time.time() - start
print(f"   Collection retrieved in {elapsed:.2f}s")
print(f"   Count: {collection.count()}")

# Try a simple get instead of query
print("\n4. Testing simple get (no embedding)...")
start = time.time()
try:
    results = collection.get(
        limit=5,
        include=["metadatas"]
    )
    elapsed = time.time() - start
    print(f"   Get completed in {elapsed:.2f}s")
    print(f"   Got {len(results['ids'])} documents")
    for i, meta in enumerate(results['metadatas'][:3]):
        print(f"     {i+1}. {meta.get('citation', 'N/A')}")
except Exception as e:
    print(f"   Get failed: {e}")

# Try metadata filter search
print("\n5. Testing metadata filter search...")
start = time.time()
try:
    results = collection.get(
        where={"citation": {"$eq": "§ 18.2-57.2"}},
        limit=5,
        include=["metadatas", "documents"]
    )
    elapsed = time.time() - start
    print(f"   Metadata search completed in {elapsed:.2f}s")
    print(f"   Got {len(results['ids'])} documents")
    if results['ids']:
        print(f"   Found: {results['metadatas'][0].get('citation', 'N/A')}")
except Exception as e:
    print(f"   Metadata search failed: {e}")

# Try embedding query with timeout
print("\n6. Testing embedding query (may take 1-2 minutes)...")
print("   Generating embedding...")

import httpx
import asyncio

async def get_embedding(text):
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text}
        )
        return response.json().get("embedding", [])

emb = asyncio.run(get_embedding("assault"))
print(f"   Embedding generated, dim: {len(emb)}")

print("   Running vector query...")
start = time.time()
try:
    # Try with very small n_results first
    results = collection.query(
        query_embeddings=[emb],
        n_results=1,  # Just 1 result to test
        include=["metadatas"]
    )
    elapsed = time.time() - start
    print(f"   Query completed in {elapsed:.2f}s")
    print(f"   Got {len(results['ids'][0])} results")
except Exception as e:
    elapsed = time.time() - start
    print(f"   Query failed after {elapsed:.2f}s: {e}")

print("\n" + "=" * 70)
print("Diagnostic complete")
print("=" * 70)

















