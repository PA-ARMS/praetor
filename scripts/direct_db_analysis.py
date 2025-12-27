"""
Direct database analysis - writes results to a known location
"""
import sqlite3
import json
from pathlib import Path

CHROMA_DB = Path("C:/LAWFIRMAI/data/chroma_db/chroma.sqlite3")
OUTPUT = Path("C:/LAWFIRMAI/data/db_analysis_result.json")

results = {
    "status": "running",
    "database_found": False,
    "total_embeddings": 0,
    "virginia_docs": 0,
    "critical_statutes": {},
    "errors": []
}

try:
    if CHROMA_DB.exists():
        results["database_found"] = True
        
        conn = sqlite3.connect(str(CHROMA_DB))
        cursor = conn.cursor()
        
        # Count total
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        results["total_embeddings"] = cursor.fetchone()[0]
        
        # Count Virginia
        cursor.execute("""
            SELECT COUNT(*) FROM embedding_metadata 
            WHERE key = 'jurisdiction' AND string_value = 'Virginia'
        """)
        results["virginia_docs"] = cursor.fetchone()[0]
        
        # Check critical statutes
        critical = ["18.2-57.2", "18.2-266", "18.2-95", "19.2-243", "19.2-163"]
        for section in critical:
            cursor.execute("""
                SELECT COUNT(*) FROM embedding_metadata 
                WHERE key = 'citation' AND string_value LIKE ?
            """, (f"%{section}%",))
            count = cursor.fetchone()[0]
            results["critical_statutes"][section] = count
        
        conn.close()
        results["status"] = "complete"
    else:
        results["errors"].append("Database file not found")
        
except Exception as e:
    results["errors"].append(str(e))
    results["status"] = "error"

# Write output
OUTPUT.write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))


















