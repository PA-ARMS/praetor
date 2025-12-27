#!/usr/bin/env python3
"""
Generate Secure Secrets for AKLAWMS

This script generates cryptographically secure secrets for JWT and encryption.

Usage:
    python scripts/generate_secrets.py

Output will be printed to console. Copy these to your .env file.
"""
import secrets
import sys

def generate_jwt_secret():
    """Generate a secure JWT secret (32+ characters)"""
    return secrets.token_urlsafe(32)

def generate_encryption_key():
    """Generate a secure encryption key (32 bytes = 64 hex chars)"""
    return secrets.token_hex(16)  # 16 bytes = 32 hex characters

def main():
    print("=" * 60)
    print("AKLAWMS - Secure Secret Generator")
    print("=" * 60)
    print()
    print("Generate secure secrets for your .env file:")
    print()
    
    jwt_secret = generate_jwt_secret()
    encryption_key = generate_encryption_key()
    
    print("# Add these to your server/.env file:")
    print()
    print(f"JWT_SECRET={jwt_secret}")
    print(f"ENCRYPTION_KEY={encryption_key}")
    print()
    print("=" * 60)
    print("⚠️  IMPORTANT SECURITY NOTES:")
    print("=" * 60)
    print("1. Keep these secrets SECRET - never commit to git")
    print("2. Use different secrets for each environment (dev/prod)")
    print("3. Store .env file securely")
    print("4. Rotate secrets periodically (every 90 days recommended)")
    print("5. If secrets are compromised, regenerate immediately")
    print()
    print("✅ Secrets generated successfully!")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())









