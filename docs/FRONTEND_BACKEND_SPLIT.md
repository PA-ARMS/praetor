# Frontend/Backend Split Deployment Guide

This guide explains how to deploy the AKLAWMS system with the frontend running on AWS and the backend running at your local facility.

## Architecture Overview

- **Frontend (AWS)**: React application served via AWS (CloudFront + S3, or EC2, or Elastic Beanstalk)
- **Backend (Local Facility)**: FastAPI server running at your facility, accessible over the internet

## Frontend Configuration

### Environment Variables

The frontend uses `VITE_API_URL` to connect to the backend API. 

#### For Production Build (AWS Deployment)

1. Create a `.env.production` file in the `client/` directory:
   ```env
   VITE_API_URL=https://your-backend-domain.com
   # OR if using IP with port:
   # VITE_API_URL=http://your-ip-address:5000
   ```

2. Replace `your-backend-domain.com` with your actual backend URL (the backend running at your facility).

3. Build the frontend:
   ```bash
   cd client
   npm run build
   ```

4. Deploy the `client/dist` folder to AWS.

#### For Local Development

1. Create a `.env.local` file in the `client/` directory:
   ```env
   # Leave empty to use Vite proxy (recommended)
   VITE_API_URL=
   
   # OR point to specific backend:
   # VITE_API_URL=http://localhost:5000
   # VITE_API_URL=http://192.168.1.100:5000
   ```

2. The Vite dev server will proxy `/api` requests to `localhost:5000` when `VITE_API_URL` is empty.

## Backend Configuration

### CORS Configuration

The backend must allow requests from your AWS frontend domain.

1. In `server/.env`, set `CORS_ORIGINS`:
   ```env
   CORS_ORIGINS=https://your-aws-frontend-domain.com,https://www.your-aws-frontend-domain.com
   ```

2. If you have multiple environments:
   ```env
   CORS_ORIGINS=https://your-aws-frontend-domain.com,https://staging.your-aws-frontend-domain.com,http://localhost:3000
   ```

3. **Important**: Remove `*` from CORS_ORIGINS in production for security.

### Backend Network Access

Your backend needs to be accessible from the internet:

1. **Port Forwarding**: Configure your router to forward port 5000 to your backend server
2. **Dynamic DNS**: Consider using a service like No-IP or DuckDNS for a stable domain name
3. **Security**: Ensure you have proper firewall rules and authentication
4. **HTTPS**: Consider using a reverse proxy (Nginx/Caddy) with Let's Encrypt for HTTPS

### Example Backend .env Configuration

```env
# Server
HOST=0.0.0.0
PORT=5000
DEBUG=False

# CORS - Allow AWS frontend domain
CORS_ORIGINS=https://your-aws-frontend-domain.com

# Security
JWT_SECRET=your-secure-jwt-secret-here
ENCRYPTION_KEY=your-32-char-encryption-key

# Database (local SQLite)
DATABASE_URL=sqlite:///./data/legal_ai.db

# RAG Database (local)
CHROMA_DB_PATH=./data/chroma_db

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

## AWS Deployment Options

### Option 1: S3 + CloudFront (Static Hosting - Recommended)

1. Build frontend:
   ```bash
   cd client
   npm run build
   ```

2. Upload `client/dist/*` to S3 bucket

3. Configure CloudFront distribution pointing to S3 bucket

4. Set environment variable `VITE_API_URL` before building to point to your backend

### Option 2: EC2 + Nginx

1. Build frontend on EC2 instance or locally
2. Copy `client/dist/*` to EC2
3. Configure Nginx to serve static files
4. Set up reverse proxy if needed

### Option 3: Elastic Beanstalk

1. Build frontend
2. Deploy using Elastic Beanstalk
3. Configure environment variables

## Security Considerations

1. **HTTPS**: Use HTTPS for both frontend and backend
2. **CORS**: Restrict CORS_ORIGINS to specific domains
3. **Authentication**: Ensure JWT tokens are properly secured
4. **Rate Limiting**: Backend has rate limiting enabled
5. **Firewall**: Configure firewall rules appropriately
6. **API Keys**: Never commit API keys or secrets to git

## Testing the Split Configuration

### Test Frontend Connection

1. Start backend at your facility:
   ```bash
   python server/main.py
   ```

2. Verify backend is accessible:
   ```bash
   curl https://your-backend-domain.com/api/health
   ```

3. Build and test frontend locally with production config:
   ```bash
   cd client
   # Set VITE_API_URL in .env.production
   npm run build
   npm run preview
   ```

4. Verify frontend can connect to backend

## Troubleshooting

### CORS Errors

If you see CORS errors in browser console:
- Verify `CORS_ORIGINS` in backend `.env` includes your frontend domain
- Check that backend is allowing credentials if needed
- Ensure protocol matches (http vs https)

### Connection Refused

If frontend can't connect to backend:
- Verify backend is running and accessible
- Check firewall rules
- Verify port forwarding configuration
- Test backend URL directly in browser/curl

### Environment Variables Not Working

- Ensure `.env.production` is in `client/` directory
- Variables must start with `VITE_` to be exposed to frontend
- Rebuild after changing environment variables (`npm run build`)

