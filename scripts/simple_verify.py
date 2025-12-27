"""Simple verification that writes to file"""
import sys
from pathlib import Path

# Output file
output_file = Path("C:/LAWFIRMAI/verification_results.txt")

def write_log(msg):
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")
    print(msg)

# Clear file
output_file.write_text("")

write_log("=" * 60)
write_log("CRITICAL VERIFICATION STARTING")
write_log("=" * 60)

try:
    sys.path.insert(0, 'C:/LAWFIRMAI')
    write_log("Path set")
    
    from server.services.rag_service import rag_service
    write_log("RAG service imported")
    
    rag_service._ensure_initialized()
    write_log("RAG initialized")
    
    collection = rag_service.collection
    all_docs = collection.get()
    total = len(all_docs['ids'])
    
    write_log(f"Total documents in database: {total}")
    
    # Count Virginia documents
    va_count = sum(1 for m in all_docs['metadatas'] if m.get('jurisdiction') == 'Virginia')
    write_log(f"Virginia documents: {va_count}")
    
    # Check for critical statutes
    critical_sections = [
        "18.2-57.2",  # Domestic assault
        "18.2-266",   # DUI
        "18.2-95",    # Grand larceny
        "19.2-243",   # Speedy trial
    ]
    
    write_log("")
    write_log("Checking critical statutes:")
    
    for section in critical_sections:
        found = False
        for i, meta in enumerate(all_docs['metadatas']):
            citation = meta.get('citation', '')
            sec = meta.get('section', '')
            if section in citation or section in sec:
                found = True
                break
        
        status = "FOUND" if found else "MISSING"
        write_log(f"  {section}: {status}")
    
    write_log("")
    write_log("Verification complete!")
    
except Exception as e:
    write_log(f"ERROR: {e}")
    import traceback
    write_log(traceback.format_exc())

write_log("=" * 60)

