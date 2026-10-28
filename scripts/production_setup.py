#!/usr/bin/env python3
"""
Production Setup - Securely configure .env for production deployment.

Generates secure secrets and updates .env with production-safe settings.
Preserves existing values. Never prints secrets to console.

Usage:
    python scripts/production_setup.py
"""
import secrets
import os
import re
from pathlib import Path

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def generate_jwt_secret() -> str:
    """Generate a secure JWT secret (32+ characters)"""
    return secrets.token_urlsafe(32)


def generate_encryption_key() -> str:
    """Generate a secure encryption key (32 bytes = 64 hex chars)"""
    return secrets.token_hex(16)


def parse_env_file(path: Path) -> dict:
    """Parse .env file into key->value dict. Preserves order of keys."""
    result = {}
    if path.exists():
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()
    return result


def write_env_file(path: Path, values: dict, comments: dict = None):
    """Write .env file. comments maps key -> comment line to add before."""
    comments = comments or {}
    # Preferred order: security first, then server, then optional
    order = ["JWT_SECRET", "ENCRYPTION_KEY", "CORS_ORIGINS", "DEBUG", "HOST", "PORT"]
    ordered_keys = [k for k in order if k in values]
    other_keys = [k for k in values if k not in order]
    keys = ordered_keys + sorted(other_keys)

    lines = [
        "# Virginia Legal AI - Production Configuration",
        "# Generated/updated by scripts/production_setup.py",
        "",
    ]
    for key in keys:
        value = values[key]
        if key in comments:
            lines.append(f"# {comments[key]}")
        lines.append(f"{key}={value}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    print("=" * 60)
    print("AKLAWMS - Production Setup")
    print("=" * 60)
    print()

    # Generate new secrets (never printed)
    jwt_secret = generate_jwt_secret()
    encryption_key = generate_encryption_key()

    # Production CORS - localhost + 127.0.0.1; user adds LAN IP as needed
    cors_origins = '["http://localhost:3000","http://127.0.0.1:3000"]'

    # Read existing .env
    existing = parse_env_file(ENV_PATH)

    # Production values (override/add)
    production = {
        "JWT_SECRET": jwt_secret,
        "ENCRYPTION_KEY": encryption_key,
        "CORS_ORIGINS": cors_origins,
        "DEBUG": "false",
    }

    # Merge: production overrides, keep all other existing keys
    merged = {**existing, **production}

    comments = {
        "JWT_SECRET": "Required for production - do not share or commit",
        "ENCRYPTION_KEY": "Required for production - do not share or commit",
        "CORS_ORIGINS": "Add your LAN IP for network access: http://192.168.1.100:3000",
        "DEBUG": "Set to true only for development",
    }

    # Write .env
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_env_file(ENV_PATH, merged, comments)

    print("Production configuration applied successfully!")
    print()
    print("Updated .env with:")
    print("  - JWT_SECRET (secure, generated)")
    print("  - ENCRYPTION_KEY (secure, generated)")
    print("  - CORS_ORIGINS (restricted to localhost)")
    print("  - DEBUG=false")
    print()
    print("Next steps:")
    print("  1. For LAN access: Add your server IP to CORS_ORIGINS in .env")
    print("     Example: [\"http://localhost:3000\",\"http://192.168.1.100:3000\"]")
    print("  2. Restart the backend for changes to take effect")
    print("  3. Run: python full_system_check.py (with PYTHONIOENCODING=utf-8 on Windows)")
    print()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
