import chromadb

print('=== SCENARIO DATABASE ANALYSIS ===')

try:
    c = chromadb.PersistentClient(path='data/scenario_db')
    col = c.get_collection('scenario_corpus')

    results = col.get(include=['documents', 'metadatas'], limit=5)

    print(f'Total scenarios: {len(results["ids"])}')

    for i, (doc_id, doc, meta) in enumerate(zip(results['ids'], results['documents'], results['metadatas'])):
        print(f'\n--- Case {i+1}: {doc_id} ---')
        print(f'Metadata keys: {list(meta.keys()) if meta else "None"}')
        if meta:
            for key, value in meta.items():
                if key in ['case_type', 'jurisdiction', 'outcome', 'court_level', 'citation', 'key_factors']:
                    print(f'  {key}: {value}')
        print(f'Document preview: {doc[:200]}...')

    # Check for domestic violence cases
    print('\n=== SEARCHING FOR DOMESTIC VIOLENCE CASES ===')
    all_results = col.get(include=['documents', 'metadatas'])
    dv_cases = []

    for doc_id, doc, meta in zip(all_results['ids'], all_results['documents'], all_results['metadatas']):
        if meta and ('domestic' in str(meta).lower() or 'family' in str(meta).lower() or 'assault' in str(meta).lower()):
            dv_cases.append((doc_id, meta))

    print(f'Found {len(dv_cases)} cases potentially related to domestic/family/assault:')

    for doc_id, meta in dv_cases[:5]:  # Show first 5
        print(f'  {doc_id}: {meta.get("case_type", "N/A")} - {meta.get("outcome", "N/A")}')

except Exception as e:
    print(f'Error: {e}')















