"""
SQLite Encryption Migration Script (Plain text to SQLCipher)

This script migrates your existing plain-text 'genie_memory.db' to an encrypted SQLCipher database.
Prerequisites:
    pip install pysqlcipher3

Usage:
    python migrate_to_sqlcipher.py <encryption_key>
"""
import sqlite3
import sys
import shutil
from pathlib import Path

try:
    from pysqlcipher3 import dbapi2 as sqlcipher
except ImportError:
    print("Error: pysqlcipher3 is not installed. Please install it to use SQLCipher encryption.")
    sys.exit(1)

def migrate_to_encrypted(db_path: Path, new_db_path: Path, key: str):
    if not db_path.exists():
        print(f"Source database not found: {db_path}")
        sys.exit(1)
        
    print(f"Migrating {db_path} to {new_db_path} with encryption...")
    
    # We use sqlite3 to connect to the unencrypted DB and ATTACH the new encrypted DB.
    # However, pysqlcipher3 is needed to handle the encrypted attach.
    conn = sqlcipher.connect(str(db_path))
    conn.execute(f"ATTACH DATABASE '{new_db_path}' AS encrypted KEY '{key}';")
    
    # sqlcipher_export() copies the schema and data from main to the attached db
    conn.execute("SELECT sqlcipher_export('encrypted');")
    conn.execute("DETACH DATABASE encrypted;")
    conn.close()
    
    print("Migration successful.")
    print("Next steps for the application:")
    print("1. Update backend/app/tools/memory_db.py to import pysqlcipher3 instead of sqlite3.")
    print(f"2. Add connection.execute(\"PRAGMA key = '{key}'\") right after connecting.")
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_to_sqlcipher.py <encryption_key>")
        sys.exit(1)
        
    encryption_key = sys.argv[1]
    
    base_dir = Path(__file__).resolve().parents[2] / "data"
    source_db = base_dir / "genie_memory.db"
    backup_db = base_dir / "genie_memory.db.bak"
    encrypted_db = base_dir / "genie_memory_encrypted.db"
    
    # Backup first
    if source_db.exists():
        print(f"Backing up original DB to {backup_db}")
        shutil.copy2(source_db, backup_db)
        
    migrate_to_encrypted(source_db, encrypted_db, encryption_key)
