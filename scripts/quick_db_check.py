import sqlite3
from pathlib import Path

output = []

def log(msg):
    output.append(msg)

CHROMA_DB = Path("C:/LAWFIRMAI/data/chroma_db/chroma.sqlite3")

log("=" * 60)
log("DATABASE VERIFICATION")
log("=" * 60)

try:
    conn = sqlite3.connect(str(CHROMA_DB))
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM embeddings")
    total = cursor.fetchone()[0]
    log(f"Total embeddings: {total:,}")
    
    cursor.execute("SELECT COUNT(*) FROM embedding_metadata WHERE key = 'jurisdiction' AND string_value = 'Virginia'")
    va = cursor.fetchone()[0]
    log(f"Virginia docs: {va:,}")
    
    # Check critical statutes
    critical = ["18.2-57.2", "18.2-266", "18.2-95", "19.2-243"]
    log("")
    log("Critical statutes:")
    
    for sec in critical:
        cursor.execute("SELECT COUNT(*) FROM embedding_metadata WHERE key = 'citation' AND string_value LIKE ?", (f"%{sec}%",))
        cnt = cursor.fetchone()[0]
        status = "FOUND" if cnt > 0 else "MISSING"
        log(f"  {sec}: {status} ({cnt})")
    
    conn.close()
    log("")
    log("Verification complete")
    
except Exception as e:
    log(f"ERROR: {e}")

# Write to file
Path("C:/LAWFIRMAI/data/db_check_result.txt").write_text("\n".join(output), encoding='utf-8')
print("\n".join(output))

