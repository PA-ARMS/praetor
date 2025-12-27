# Backend Configuration for Remote Frontend

This guide explains how to configure the AKLAWMS backend to accept requests from a frontend deployed on AWS (or any remote server).

## Overview

When the frontend is deployed remotely (e.g., on AWS), the backend needs to:
1. Allow CORS requests from the frontend domain
2. Be accessible from the internet
3. Maintain security while allowing remote access

## CORS Configuration

### Environment Variable

In `server/.env`, configure `CORS_ORIGINS`:

```env
# For single frontend domain
CORS_ORIGINS=https://your-aws-frontend-domain.com

# For multiple domains (production + staging + local dev)
CORS_ORIGINS=https://your-aws-frontend-domain.com,https://staging.your-aws-frontend-domain.com,http://localhost:3000

# Format: comma-separated list of origins (no spaces after commas)
```

### Security Warning

**Never use `*` in production CORS_ORIGINS** - this allows any website to make requests to your backend.

The backend will log a warning if `*` is used in production mode.

## Network Configuration

### Option 1: Port Forwarding

1. Configure your router to forward external port 5000 to your backend server's internal IP on port 5000
2. Use your public IP address or dynamic DNS domain to access backend

### Option 2: Reverse Proxy with Domain

Recommended for production:

1. Set up a reverse proxy (Nginx or Caddy) on your network
2. Configure domain to point to your public IP
3. Use Let's Encrypt for HTTPS
4. Proxy requests to backend on port 5000

Example Nginx configuration:

```nginx
server {
    listen 80;
    server_name api.your-domain.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Option 3: VPN Access

For enhanced security, require VPN connection to access backend:
- Configure backend to only accept connections from VPN IP range
- Users connect via VPN before accessing frontend

## Complete Backend .env Example

```env
# Server Configuration
HOST=0.0.0.0  # Listen on all interfaces
PORT=5000
DEBUG=False

# CORS - Allow AWS frontend domain
CORS_ORIGINS=https://your-aws-frontend-domain.com,https://www.your-aws-frontend-domain.com

# Security - IMPORTANT: Change these in production!
JWT_SECRET=your-very-secure-random-jwt-secret-minimum-32-characters
ENCRYPTION_KEY=your-32-character-encryption-key

# Database (local SQLite - no change needed)
DATABASE_URL=sqlite:///./data/legal_ai.db

# RAG Database (local - no change needed)
CHROMA_DB_PATH=./data/chroma_db

# Ollama (local - no change needed)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Optional: IP Restrictions (if needed)
# ALLOWED_IPS=192.168.1.0/24,127.0.0.1  # Comment out for internet access

# Rate Limiting (already configured, adjust if needed)
RATE_LIMIT_ENABLED=True
RATE_LIMIT_CHAT_PER_MINUTE=30
RATE_LIMIT_AUTH_PER_MINUTE=10
```

## Security Considerations

### 1. Use HTTPS

If exposing backend to internet, use HTTPS:
- Set up reverse proxy with SSL certificate (Let's Encrypt)
- Or use a tunnel service (ngrok, Cloudflare Tunnel)

### 2. Firewall Configuration

Configure Windows Firewall or router firewall:
- Allow incoming connections on port 5000 (or your chosen port)
- Consider restricting to specific IP ranges if possible
- Use fail2ban or similar for brute force protection

### 3. Authentication

The backend uses JWT tokens for authentication:
- Tokens are stored in frontend localStorage
- Ensure strong `JWT_SECRET` is configured
- Tokens expire after configured time (default: 24 hours)

### 4. Rate Limiting

Rate limiting is enabled by default:
- Chat: 30 requests per minute
- Auth: 10 requests per minute
- Default: 60 requests per minute

Adjust in `.env` if needed.

### 5. IP Restrictions (Optional)

If you want to restrict backend access to specific IPs:

```env
ALLOWED_IPS=192.168.1.0/24,127.0.0.1
```

**Note**: This will block all other IPs, including your AWS frontend! Only use if frontend connects via VPN or specific IP range.

## Testing Configuration

### 1. Test Backend Accessibility

From a machine outside your network:

```bash
# Test if backend is reachable
curl https://your-backend-domain.com/api/health

# Test CORS (should return CORS headers)
curl -H "Origin: https://your-aws-frontend-domain.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://your-backend-domain.com/api/chat/query
```

### 2. Test from Frontend

1. Deploy frontend with `VITE_API_URL` set to your backend URL
2. Open browser developer console
3. Attempt to login
4. Check for CORS errors
5. Verify API calls are successful

### 3. Check Backend Logs

Backend will log CORS configuration on startup:

```
INFO: CORS: Restricted to origins: ['https://your-aws-frontend-domain.com']
```

If you see:
```
WARNING: CORS: Allowing all origins (*) - this should be restricted in production
```

Update `CORS_ORIGINS` in `.env` to restrict to specific domains.

## Troubleshooting

### CORS Errors in Browser

**Error**: `Access to fetch at '...' from origin '...' has been blocked by CORS policy`

**Solutions**:
1. Verify `CORS_ORIGINS` in backend `.env` includes your frontend domain
2. Ensure protocol matches (http vs https)
3. Check for trailing slashes - should be exact match
4. Restart backend after changing `.env`

### Connection Refused

**Error**: `Failed to connect` or `Network Error`

**Solutions**:
1. Verify backend is running: `python server/main.py`
2. Check firewall allows port 5000
3. Verify port forwarding is configured correctly
4. Test backend URL directly in browser
5. Check backend logs for errors

### 401 Unauthorized Errors

**Error**: Authentication fails

**Solutions**:
1. Verify JWT token is being sent in Authorization header
2. Check `JWT_SECRET` matches (if changed)
3. Verify token hasn't expired
4. Check backend logs for authentication errors

## Dynamic DNS Setup

If you don't have a static IP, use dynamic DNS:

1. Sign up for dynamic DNS service (No-IP, DuckDNS, etc.)
2. Configure router to update DNS record with current IP
3. Use dynamic DNS domain in CORS_ORIGINS and frontend VITE_API_URL
4. Backend will work even if your IP changes

## Monitoring and Logging

Monitor backend for:
- Failed authentication attempts
- Rate limit violations
- Unusual traffic patterns
- CORS errors in logs

Backend logs include:
- Request IDs for tracing
- Authentication events
- Rate limit violations
- CORS configuration on startup

