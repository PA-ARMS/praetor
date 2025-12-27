"""Test ChromaDB with timeout and progress"""
import chromadb
from chromadb.config import Settings
import httpx
import asyncio
import time
import signal
import sys

print("Testing ChromaDB with timeout...")
print("This may take 1-2 minutes for first query (loading 54k vectors into memory)")

# Initialize client
client = chromadb.PersistentClient(
    path="data/chroma_db",
    settings=Settings(anonymized_telemetry=False)
)

collection = client.get_collection("legal_corpus")
print(f"Collection: {collection.name}, count: {collection.count()}")

# Generate embedding
async def get_embedding(text):
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text}
        )
        return response.json().get("embedding", [])

print("Generating embedding...")
emb = asyncio.run(get_embedding("domestic assault"))
print(f"Embedding dimension: {len(emb)}")

print("Querying collection (this may take 1-2 minutes on first run)...")
start = time.time()

try:
    results = collection.query(
        query_embeddings=[emb],
        n_results=3,
        include=["metadatas"]
    )
    elapsed = time.time() - start
    print(f"Query completed in {elapsed:.2f} seconds")
    print(f"Got {len(results['ids'][0])} results")
    
    for i, meta in enumerate(results['metadatas'][0]):
        print(f"  {i+1}. {meta.get('citation', 'N/A')}")
        
except Exception as e:
    elapsed = time.time() - start
    print(f"Query failed after {elapsed:.2f} seconds: {e}")

print("Done!")

















