# Security Setup Guide - Quick Start

## 🚀 Before First Production Deployment

### Step 1: Run Production Setup

Run the production setup script (generates secrets securely, never prints them):

```bash
python scripts/production_setup.py
```

This updates `.env` with:
- `JWT_SECRET` and `ENCRYPTION_KEY` (cryptographically generated)
- `CORS_ORIGINS` (restricted to localhost)
- `DEBUG=false`

### Step 2: Add LAN Access (if needed)

For network access, edit `.env` and add your server IP to CORS_ORIGINS:

```env
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://192.168.1.100:3000"]
```
Replace `192.168.1.100` with your server's static IP.

### Step 3: Restart Backend & Verify

Restart the backend for config changes to take effect, then check for warnings:
```bash
python -m uvicorn server.main:app --host 0.0.0.0 --port 5001
```

**Look for:**
- ✅ No security warnings about default secrets
- ✅ CORS configuration logged correctly
- ✅ All services healthy in `/health` endpoint

### Step 4: Set Up Automated Backups

**Windows (Task Scheduler):**
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: Daily at 2 AM
4. Action: Start a program
5. Program: `python`
6. Arguments: `C:\LAWFIRMAI\scripts\backup_database.py`
7. Start in: `C:\LAWFIRMAI`

**Linux/Mac (Cron):**
```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * cd /path/to/LAWFIRMAI && python scripts/backup_database.py
```

### Step 5: Test Security Features

1. **Test Password Policy:**
   - Try registering with weak password (should fail)
   - Try registering with strong password (should succeed)

2. **Test File Upload:**
   - Upload valid file (should succeed)
   - Upload oversized file (should fail)
   - Upload invalid file type (should fail)

3. **Test Health Check:**
   ```bash
   curl http://localhost:5001/health
   ```
   Should return detailed status

4. **Verify Request IDs:**
   ```bash
   curl -v http://localhost:5001/health
   ```
   Check for `X-Request-ID` header in response

---

## 🔒 Security Checklist

Before going to production, verify:

- [ ] Secrets generated and set in `.env`
- [ ] `.env` file is in `.gitignore` (already done)
- [ ] CORS origins restricted to specific domains
- [ ] Database backups scheduled and tested
- [ ] Password policy tested
- [ ] File upload restrictions tested
- [ ] Health check endpoint working
- [ ] Audit logs being created
- [ ] No security warnings on startup
- [ ] SSL/TLS configured (if using HTTPS)
- [ ] Firewall rules configured
- [ ] Rate limiting enabled and tested

---

## 📞 Troubleshooting

### "Security Warning: JWT_SECRET is using default value"
**Fix:** Generate secrets and add to `.env` file

### "Security Warning: CORS allows all origins"
**Fix:** Set `CORS_ORIGINS` in `.env` to specific domains

### File upload fails with "File too large"
**Fix:** Increase `MAX_FILE_SIZE` in config or `.env` (in bytes)

### Password registration fails
**Fix:** Ensure password meets requirements:
- At least 12 characters
- Contains uppercase, lowercase, number, and special character

### Health check shows "degraded"
**Fix:** Check individual service status in response:
- Database: Check SQLite file exists and is accessible
- Ollama: Ensure Ollama service is running
- ChromaDB: Check directory exists
- Disk space: Ensure at least 1GB free

---

## 🔄 Maintenance

### Rotate Secrets (Every 90 Days)

1. Run production setup: `python scripts/production_setup.py`
2. Update `.env` file
3. Restart server
4. All users will need to log in again (tokens invalidated)

### Monitor Backups

Check backup directory regularly:
```bash
ls -lh data/backups/
```

Ensure backups are being created and old ones cleaned up.

### Review Audit Logs

Regularly review audit logs for suspicious activity:
- Failed login attempts
- Unusual user registrations
- File upload patterns

---

**Your system is now secured!** 🎉










