# Quick Fixes - Critical Issues to Address Immediately

## 🔴 CRITICAL - Fix Before Production

### 1. Change Default Secrets
**File:** `server/config.py`

Add to `.env` file:
```bash
JWT_SECRET=<generate-32-char-random-string>
ENCRYPTION_KEY=<generate-32-char-random-string>
```

Generate secrets:
```python
import secrets
print("JWT_SECRET=" + secrets.token_urlsafe(32))
print("ENCRYPTION_KEY=" + secrets.token_hex(16))
```

### 2. Secure File Upload
**File:** `server/routes/documents.py`

Add authentication and validation:
```python
@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(require_auth)  # ADD THIS
):
    MAX_SIZE = 50 * 1024 * 1024  # 50MB
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, "File too large")
    
    # Sanitize filename
    safe_name = Path(file.filename).name
    file_path = upload_dir / f"{current_user.id}_{safe_name}"
```

### 3. Restrict CORS
**File:** `server/config.py`

Change:
```python
CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://your-production-domain.com"]
```

### 4. Add Password Policy
**File:** `server/services/auth_service.py`

Add validation function and call it in `create_user()`.

### 5. Database Backup Script
**File:** `scripts/backup_database.py` (create new)

See SYSTEM_REVIEW.md for full implementation.

---

## 🟡 HIGH PRIORITY - Fix Soon

- Add input validation (max lengths, sanitization)
- Improve error handling (log all errors)
- Add health check details
- Implement per-user rate limiting
- Add audit logging to all sensitive operations

---

## 📋 Full Details

See `SYSTEM_REVIEW.md` for comprehensive analysis of all 30+ issues found.










