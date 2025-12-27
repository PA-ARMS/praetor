"""
Direct database content verification.
Checks that critical statutes exist in the ChromaDB.
"""
import sqlite3
import json
from pathlib import Path

# Direct path to ChromaDB SQLite
CHROMA_DB = Path("data/chroma_db/chroma.sqlite3")

print("=" * 60)
print("DIRECT DATABASE VERIFICATION")
print("=" * 60)

if not CHROMA_DB.exists():
    print(f"ERROR: Database not found at {CHROMA_DB}")
    exit(1)

# Connect directly to ChromaDB SQLite
conn = sqlite3.connect(str(CHROMA_DB))
cursor = conn.cursor()

# Get total document count
cursor.execute("SELECT COUNT(*) FROM embeddings")
total_embeddings = cursor.fetchone()[0]
print(f"\nTotal embeddings in database: {total_embeddings:,}")

# Get collection info
cursor.execute("SELECT name FROM collections")
collections = cursor.fetchall()
print(f"Collections: {[c[0] for c in collections]}")

# Check for documents with Virginia jurisdiction
cursor.execute("""
    SELECT COUNT(*) FROM embedding_metadata 
    WHERE key = 'jurisdiction' AND string_value = 'Virginia'
""")
va_count = cursor.fetchone()[0]
print(f"Virginia documents: {va_count:,}")

# Check for statute documents
cursor.execute("""
    SELECT COUNT(*) FROM embedding_metadata 
    WHERE key = 'document_type' AND string_value LIKE '%Statute%'
""")
statute_count = cursor.fetchone()[0]
print(f"Statute documents: {statute_count:,}")

# Check for specific citations
print("\n" + "=" * 60)
print("CHECKING CRITICAL STATUTES")
print("=" * 60)

critical_sections = [
    ("18.2-57.2", "Assault family member"),
    ("18.2-266", "DUI"),
    ("18.2-95", "Grand larceny"),
    ("18.2-250", "Drug possession"),
    ("19.2-243", "Speedy trial"),
    ("19.2-163", "Right to counsel"),
    ("8.01-195.3", "Sovereign immunity"),
]

found = 0
missing = 0

for section, description in critical_sections:
    # Search for citation containing section
    cursor.execute("""
        SELECT COUNT(*) FROM embedding_metadata 
        WHERE key = 'citation' AND string_value LIKE ?
    """, (f"%{section}%",))
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"  ✓ {section}: Found ({count} matches) - {description}")
        found += 1
    else:
        # Try section field
        cursor.execute("""
            SELECT COUNT(*) FROM embedding_metadata 
            WHERE key = 'section' AND string_value LIKE ?
        """, (f"%{section}%",))
        count2 = cursor.fetchone()[0]
        
        if count2 > 0:
            print(f"  ✓ {section}: Found in section field ({count2}) - {description}")
            found += 1
        else:
            print(f"  ✗ {section}: NOT FOUND - {description}")
            missing += 1

print(f"\nResult: {found}/{found+missing} critical statutes found")

# Sample some actual content
print("\n" + "=" * 60)
print("SAMPLE DATABASE CONTENT")
print("=" * 60)

cursor.execute("""
    SELECT DISTINCT string_value FROM embedding_metadata 
    WHERE key = 'source' 
    LIMIT 20
""")
sources = cursor.fetchall()
print("\nUnique sources in database:")
for src in sources:
    print(f"  - {src[0]}")

conn.close()

print("\n" + "=" * 60)
if missing == 0:
    print("✓ ALL CRITICAL STATUTES PRESENT")
else:
    print(f"⚠ {missing} CRITICAL STATUTES MISSING")
print("=" * 60)

