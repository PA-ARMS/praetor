"""
Database Restore Script
Restores SQLite database and ChromaDB from backup
"""
import shutil
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.config import settings


def list_backups(backup_dir: str = None) -> list:
    """List all available backups"""
    if backup_dir is None:
        backup_dir = Path(settings.DATA_DIR) / "backups"
    else:
        backup_dir = Path(backup_dir)
    
    if not backup_dir.exists():
        return []
    
    backups = []
    for manifest in backup_dir.glob("manifest_*.json"):
        try:
            with open(manifest, 'r') as f:
                backup_info = json.load(f)
                backups.append(backup_info)
        except Exception:
            continue
    
    return sorted(backups, key=lambda x: x.get("timestamp", ""), reverse=True)


def restore_database(backup_id: str, backup_dir: str = None, confirm: bool = False) -> dict:
    """
    Restore database from backup
    
    Args:
        backup_id: Backup ID (timestamp) to restore
        backup_dir: Directory containing backups
        confirm: If False, will prompt for confirmation
    
    Returns:
        dict with restore information
    """
    if backup_dir is None:
        backup_dir = Path(settings.DATA_DIR) / "backups"
    else:
        backup_dir = Path(backup_dir)
    
    # Find manifest
    manifest_path = backup_dir / f"manifest_{backup_id}.json"
    if not manifest_path.exists():
        return {
            "success": False,
            "error": f"Backup {backup_id} not found"
        }
    
    # Load manifest
    with open(manifest_path, 'r') as f:
        backup_info = json.load(f)
    
    if not backup_info.get("success"):
        return {
            "success": False,
            "error": "Backup was not successful, cannot restore"
        }
    
    # Confirm restore
    if not confirm:
        print(f"\n⚠ WARNING: This will overwrite current database files!")
        print(f"Restoring backup: {backup_id} from {backup_info['timestamp']}")
        print(f"Files to restore: {len(backup_info['files'])}")
        response = input("\nType 'RESTORE' to confirm: ")
        if response != "RESTORE":
            return {
                "success": False,
                "error": "Restore cancelled by user"
            }
    
    restore_info = {
        "backup_id": backup_id,
        "timestamp": datetime.now().isoformat(),
        "files_restored": [],
        "success": True,
        "errors": []
    }
    
    # Restore each file
    for file_info in backup_info["files"]:
        source = Path(file_info["backup"])
        target = Path(file_info["source"])
        
        if not source.exists():
            restore_info["errors"].append(f"Backup file not found: {source}")
            continue
        
        try:
            # Create backup of current file before overwriting
            if target.exists():
                backup_current = target.parent / f"{target.name}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                if target.is_file():
                    shutil.copy2(target, backup_current)
                elif target.is_dir():
                    shutil.copytree(target, backup_current, dirs_exist_ok=True)
                print(f"  Backed up current: {backup_current}")
            
            # Restore
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            elif source.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(source, target)
            
            restore_info["files_restored"].append({
                "source": str(source),
                "target": str(target)
            })
            print(f"✓ Restored: {target}")
        except Exception as e:
            restore_info["success"] = False
            restore_info["errors"].append(f"Failed to restore {target}: {e}")
            print(f"✗ Failed to restore {target}: {e}")
    
    return restore_info


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Restore database from backup")
    parser.add_argument("--backup-id", help="Backup ID to restore (timestamp)")
    parser.add_argument("--dir", help="Backup directory (default: data/backups)")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    
    if args.list:
        backups = list_backups(args.dir)
        print(f"\nAvailable backups:\n")
        for i, backup in enumerate(backups, 1):
            print(f"  {i}. {backup['backup_id']} - {backup['timestamp']}")
            print(f"     Files: {len(backup['files'])}")
            print()
    elif args.backup_id:
        result = restore_database(args.backup_id, args.dir, args.confirm)
        if result["success"]:
            print(f"\n✓ Restore completed successfully")
            print(f"  Files restored: {len(result['files_restored'])}")
        else:
            print(f"\n✗ Restore failed: {result.get('error', 'Unknown error')}")
            if result.get("errors"):
                for error in result["errors"]:
                    print(f"  - {error}")
            sys.exit(1)
    else:
        print("Error: Must specify --backup-id or --list")
        parser.print_help()
        sys.exit(1)

