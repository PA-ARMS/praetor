"""Direct ChromaDB test"""
import chromadb
from chromadb.config import Settings
import httpx
import asyncio

print("Testing ChromaDB directly...")

# Initialize client
client = chromadb.PersistentClient(
    path="data/chroma_db",
    settings=Settings(anonymized_telemetry=False)
)

print("Client created")

# Get collection
collection = client.get_collection("legal_corpus")
print(f"Collection: {collection.name}, count: {collection.count()}")

# Generate embedding via Ollama
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

print("Querying collection...")
try:
    results = collection.query(
        query_embeddings=[emb],
        n_results=3,
        include=["metadatas", "documents"]
    )
    print(f"Got {len(results['ids'][0])} results")
    
    for i, (id, meta) in enumerate(zip(results['ids'][0], results['metadatas'][0])):
        print(f"  {i+1}. {meta.get('citation', 'N/A')}")
        
except Exception as e:
    print(f"Query error: {e}")
    import traceback
    traceback.print_exc()

print("Done!")

















