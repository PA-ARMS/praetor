"""Check ChromaDB schema"""
import sqlite3
from pathlib import Path

conn = sqlite3.connect('data/chroma_db/chroma.sqlite3')
c = conn.cursor()

# Check tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print('Tables:', [t[0] for t in tables])

# Check collections
c.execute('SELECT * FROM collections LIMIT 1')
row = c.fetchone()
print('Collection:', row)

# Check embedding dimensions by looking at vector data
c.execute('SELECT dimension FROM collections WHERE name = ?', ('legal_corpus',))
dim = c.fetchone()
print('Dimension from collections:', dim)

conn.close()

















