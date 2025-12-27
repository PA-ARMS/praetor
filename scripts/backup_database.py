#!/usr/bin/env python3
"""
Database Backup Script
Automatically backs up the SQLite database and optionally ChromaDB

Usage:
    python scripts/backup_database.py [--keep-days=30] [--include-chromadb]

This script should be run via cron/scheduler for automated backups.
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import shutil
import argparse
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backup_database(keep_days: int = 30, include_chromadb: bool = False):
    """
    Backup SQLite database and optionally ChromaDB
    
    Args:
        keep_days: Number of days of backups to keep (default: 30)
        include_chromadb: Whether to backup ChromaDB as well (default: False)
    """
    # Create backup directory
    backup_dir = Path(settings.DATA_DIR) / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_success = []
    backup_errors = []
    
    # Backup SQLite database
    db_path = Path(settings.DATA_DIR) / "legal_ai.db"
    if db_path.exists():
        try:
            backup_path = backup_dir / f"legal_ai_{timestamp}.db"
            shutil.copy2(db_path, backup_path)
            backup_success.append(f"Database: {backup_path.name}")
            logger.info(f"✓ Backed up database to {backup_path}")
        except Exception as e:
            backup_errors.append(f"Database backup failed: {e}")
            logger.error(f"✗ Database backup failed: {e}")
    else:
        backup_errors.append("Database file not found")
        logger.warning("Database file not found")
    
    # Backup ChromaDB if requested
    if include_chromadb:
        chroma_path = Path(settings.CHROMA_DB_PATH)
        if chroma_path.exists() and chroma_path.is_dir():
            try:
                chroma_backup_dir = backup_dir / f"chroma_db_{timestamp}"
                shutil.copytree(chroma_path, chroma_backup_dir)
                backup_success.append(f"ChromaDB: {chroma_backup_dir.name}")
                logger.info(f"✓ Backed up ChromaDB to {chroma_backup_dir}")
            except Exception as e:
                backup_errors.append(f"ChromaDB backup failed: {e}")
                logger.error(f"✗ ChromaDB backup failed: {e}")
    
    # Clean up old backups
    try:
        cutoff_date = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
        removed_count = 0
        
        for backup_file in backup_dir.glob("legal_ai_*.db"):
            if backup_file.stat().st_mtime < cutoff_date:
                backup_file.unlink()
                removed_count += 1
        
        # Remove old ChromaDB backups
        for chroma_backup in backup_dir.glob("chroma_db_*"):
            if chroma_backup.is_dir() and chroma_backup.stat().st_mtime < cutoff_date:
                shutil.rmtree(chroma_backup)
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} old backup(s)")
    except Exception as e:
        logger.warning(f"Error cleaning up old backups: {e}")
    
    # Summary
    if backup_success:
        logger.info(f"Backup completed successfully: {', '.join(backup_success)}")
    if backup_errors:
        logger.error(f"Backup errors: {', '.join(backup_errors)}")
        return 1
    
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup AKLAWMS database")
    parser.add_argument(
        "--keep-days",
        type=int,
        default=30,
        help="Number of days of backups to keep (default: 30)"
    )
    parser.add_argument(
        "--include-chromadb",
        action="store_true",
        help="Include ChromaDB in backup (can be large)"
    )
    
    args = parser.parse_args()
    
    exit_code = backup_database(
        keep_days=args.keep_days,
        include_chromadb=args.include_chromadb
    )
    
    sys.exit(exit_code)
