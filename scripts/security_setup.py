"""
Security Setup Script
Generates secure JWT secrets and encryption keys for production deployment
"""
import secrets
import sys
from pathlib import Path

def generate_secret_key(length: int = 32) -> str:
    """Generate a cryptographically secure random key"""
    return secrets.token_urlsafe(length)

def generate_jwt_secret() -> str:
    """Generate a secure JWT secret (64 bytes)"""
    return secrets.token_urlsafe(64)

def generate_encryption_key() -> str:
    """Generate a 32-character encryption key"""
    return secrets.token_urlsafe(32)[:32]

def check_current_secrets():
    """Check if current secrets are using defaults"""
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    jwt_secret = os.getenv("JWT_SECRET", "")
    encryption_key = os.getenv("ENCRYPTION_KEY", "")
    
    defaults = [
        "change-this-secret-key",
        "change-this-32-char-encryption-key"
    ]
    
    issues = []
    if jwt_secret in defaults or not jwt_secret:
        issues.append("JWT_SECRET is using default or not set")
    if encryption_key in defaults or not encryption_key:
        issues.append("ENCRYPTION_KEY is using default or not set")
    
    return issues

def update_env_file(env_path: Path = None):
    """Update .env file with secure keys"""
    if env_path is None:
        env_path = Path(".env")
    
    if not env_path.exists():
        print(f"⚠ .env file not found at {env_path}")
        print("Creating new .env file...")
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.touch()
    
    # Read existing .env
    lines = []
    if env_path.exists():
        with open(env_path, 'r') as f:
            lines = f.readlines()
    
    # Generate new keys
    jwt_secret = generate_jwt_secret()
    encryption_key = generate_encryption_key()
    
    # Update or add keys
    updated = {"JWT_SECRET": False, "ENCRYPTION_KEY": False}
    new_lines = []
    
    for line in lines:
        if line.strip().startswith("JWT_SECRET="):
            new_lines.append(f"JWT_SECRET={jwt_secret}\n")
            updated["JWT_SECRET"] = True
        elif line.strip().startswith("ENCRYPTION_KEY="):
            new_lines.append(f"ENCRYPTION_KEY={encryption_key}\n")
            updated["ENCRYPTION_KEY"] = True
        else:
            new_lines.append(line)
    
    # Add missing keys
    if not updated["JWT_SECRET"]:
        new_lines.append(f"JWT_SECRET={jwt_secret}\n")
    if not updated["ENCRYPTION_KEY"]:
        new_lines.append(f"ENCRYPTION_KEY={encryption_key}\n")
    
    # Write back
    with open(env_path, 'w') as f:
        f.writelines(new_lines)
    
    print(f"✓ Updated {env_path}")
    print(f"  JWT_SECRET: {'Updated' if updated['JWT_SECRET'] else 'Added'}")
    print(f"  ENCRYPTION_KEY: {'Updated' if updated['ENCRYPTION_KEY'] else 'Added'}")
    
    return jwt_secret, encryption_key

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate secure keys for production")
    parser.add_argument("--check", action="store_true", help="Check current secrets")
    parser.add_argument("--update", action="store_true", help="Update .env file with new keys")
    parser.add_argument("--env-file", help="Path to .env file (default: .env)")
    args = parser.parse_args()
    
    if args.check:
        issues = check_current_secrets()
        if issues:
            print("⚠ Security Issues Found:\n")
            for issue in issues:
                print(f"  - {issue}")
            print("\nRun with --update to generate secure keys")
            sys.exit(1)
        else:
            print("✓ Current secrets appear secure")
    elif args.update:
        env_path = Path(args.env_file) if args.env_file else None
        jwt_secret, encryption_key = update_env_file(env_path)
        print("\n✓ Security keys generated and updated")
        print("\n⚠ IMPORTANT:")
        print("  1. Restart the server for changes to take effect")
        print("  2. Keep .env file secure and never commit it to version control")
        print("  3. Back up .env file in a secure location")
    else:
        # Generate keys for display
        print("Generated Security Keys:\n")
        print(f"JWT_SECRET={generate_jwt_secret()}")
        print(f"ENCRYPTION_KEY={generate_encryption_key()}")
        print("\n⚠ Add these to your .env file manually or use --update")

