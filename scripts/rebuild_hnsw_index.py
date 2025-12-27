"""
Rebuild ChromaDB HNSW Index

The HNSW index is corrupted (link_lists.bin is too small).
This script will rebuild it properly.

WARNING: This may take 30-60 minutes for 54,729 documents.
"""
import os
import sys
import shutil
import sqlite3
import time
import json
from pathlib import Path

print("=" * 70)
print("ChromaDB HNSW Index Rebuild")
print("=" * 70)

CHROMA_PATH = "data/chroma_db"
SQLITE_PATH = os.path.join(CHROMA_PATH, "chroma.sqlite3")

# Step 1: Check current state
print("\n1. Checking current state...")
conn = sqlite3.connect(SQLITE_PATH)
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM embeddings")
total_docs = c.fetchone()[0]
print(f"   Total documents with embeddings: {total_docs:,}")

c.execute("SELECT id, name FROM collections")
collections = c.fetchall()
print(f"   Collections: {collections}")

if total_docs == 0:
    print("\n   ERROR: No documents found! Cannot rebuild.")
    sys.exit(1)

conn.close()

# Step 2: Delete the corrupted HNSW index folder
print("\n2. Removing corrupted HNSW index...")
for item in os.listdir(CHROMA_PATH):
    item_path = os.path.join(CHROMA_PATH, item)
    if os.path.isdir(item_path):
        print(f"   Removing: {item}")
        shutil.rmtree(item_path)
print("   HNSW index removed.")

# Step 3: Initialize ChromaDB (will trigger index rebuild)
print("\n3. Initializing ChromaDB client...")
print("   This will trigger automatic index rebuild...")

import chromadb
from chromadb.config import Settings

start = time.time()
client = chromadb.PersistentClient(
    path=CHROMA_PATH,
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)
elapsed = time.time() - start
print(f"   Client initialized in {elapsed:.2f}s")

# Step 4: Access the collection (triggers index build)
print("\n4. Accessing collection to trigger index build...")
start = time.time()
collection = client.get_collection("legal_corpus")
count = collection.count()
elapsed = time.time() - start
print(f"   Collection retrieved in {elapsed:.2f}s")
print(f"   Document count: {count:,}")

# Step 5: Force index build with a small query
print("\n5. Forcing index build with test query...")
print("   This step may take 5-30 minutes depending on your CPU...")

import httpx
import asyncio

async def get_embedding(text):
    async with httpx.AsyncClient(timeout=60) as http_client:
        response = await http_client.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text}
        )
        return response.json().get("embedding", [])

# Get a test embedding
test_emb = asyncio.run(get_embedding("assault and battery Virginia"))
print(f"   Test embedding generated (dim: {len(test_emb)})")

# Run query - this forces the HNSW index to be built
print("   Running query to build index...")
start = time.time()

try:
    results = collection.query(
        query_embeddings=[test_emb],
        n_results=5,
        include=["metadatas", "documents"]
    )
    elapsed = time.time() - start
    print(f"\n   ✅ Query succeeded in {elapsed:.2f}s!")
    print(f"   Results found: {len(results['ids'][0])}")
    
    if results['ids'][0]:
        print("\n   Sample results:")
        for i, (meta, doc) in enumerate(zip(results['metadatas'][0][:3], results['documents'][0][:3])):
            citation = meta.get('citation', 'N/A')
            doc_preview = doc[:100] if doc else 'N/A'
            print(f"   {i+1}. {citation}")
            print(f"      {doc_preview}...")
            
except Exception as e:
    elapsed = time.time() - start
    print(f"\n   ❌ Query failed after {elapsed:.2f}s: {e}")
    print("   The index may need more time to build.")
    print("   Try running this script again after a few minutes.")
    sys.exit(1)

# Step 6: Verify index files
print("\n6. Verifying new index files...")
for item in os.listdir(CHROMA_PATH):
    item_path = os.path.join(CHROMA_PATH, item)
    if os.path.isdir(item_path):
        print(f"   Index folder: {item}")
        for file in os.listdir(item_path):
            file_path = os.path.join(item_path, file)
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"     {file}: {size_mb:.2f} MB")

print("\n" + "=" * 70)
print("✅ HNSW Index Rebuild Complete!")
print("=" * 70)
print("\nVector search should now work properly.")
print("Try searching in the application.")

