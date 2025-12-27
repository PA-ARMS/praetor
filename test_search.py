import chromadb
import httpx
import time
import sys

print('Starting test...', flush=True)

# Get embedding from Ollama
resp = httpx.post('http://localhost:11434/api/embeddings', 
    json={'model': 'nomic-embed-text', 'prompt': 'assault domestic violence'}, 
    timeout=30)
emb = resp.json().get('embedding', [])
print(f'Embedding dim: {len(emb)}', flush=True)

# Query ChromaDB
c = chromadb.PersistentClient(path='data/chroma_db')
col = c.get_collection('legal_corpus')
print(f'Collection has {col.count()} docs', flush=True)

start = time.time()
results = col.query(query_embeddings=[emb], n_results=3, include=['metadatas'])
elapsed = time.time() - start

print(f'Search time: {elapsed:.2f}s', flush=True)
print('Results:', flush=True)
for m in results['metadatas'][0]:
    citation = m.get('citation', 'N/A')
    print(f'  - {citation}', flush=True)

