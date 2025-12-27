# Deployment Guide - Virginia Legal AI

## Deployment Architectures

This system supports two deployment architectures:

1. **Local Deployment** (both frontend and backend on same machine/network)
   - See "Network Configuration for LAN Access" below

2. **Split Deployment** (frontend on AWS, backend at local facility)
   - See [Frontend/Backend Split Guide](docs/FRONTEND_BACKEND_SPLIT.md)
   - [AWS Frontend Deployment](docs/AWS_FRONTEND_DEPLOYMENT.md)
   - [Backend Configuration for Remote Frontend](docs/BACKEND_REMOTE_FRONTEND.md)

## Network Configuration for LAN Access

This system runs on a single PC and serves attorneys over the local network.

### 1. Configure Windows Firewall

Allow incoming connections on ports 5000 (backend) and 3000 (frontend):

```powershell
# Run as Administrator
New-NetFirewallRule -DisplayName "Virginia Legal AI Backend" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Virginia Legal AI Frontend" -Direction Inbound -LocalPort 3000 -Protocol TCP -Action Allow
```

### 2. Set Static IP (Recommended)

1. Open Network Settings
2. Change adapter options
3. Right-click your network adapter → Properties
4. Select "Internet Protocol Version 4 (TCP/IPv4)" → Properties
5. Use static IP (e.g., 192.168.1.100)
6. Note this IP for client configuration

### 3. Configure Server

Edit `server/.env`:

```env
HOST=0.0.0.0  # Listen on all interfaces
PORT=5000
CORS_ORIGINS=http://localhost:3000,http://192.168.1.*
ALLOWED_IPS=192.168.1.0/24,127.0.0.1
```

### 4. Configure Client

Edit `client/.env` (create if needed):

```env
VITE_API_URL=http://192.168.1.100:5000
```

Replace `192.168.1.100` with your server's IP address.

### 5. Start Services

**Option A: Manual Start**
```bash
# Terminal 1 - Backend
cd C:\LAWFIRMAI
python server/main.py

# Terminal 2 - Frontend
cd C:\LAWFIRMAI\client
npm run dev
```

**Option B: Batch Scripts**
```bash
scripts\start_server.bat
scripts\start_client.bat
```

### 6. Access from Network

Attorneys can access the system at:
- `http://192.168.1.100:3000` (replace with your server IP)

### 7. Production Setup (Optional)

For production, consider:
- Using Nginx as reverse proxy
- Setting up HTTPS with self-signed certificate
- Running services as Windows services
- Setting up automatic startup on boot

## Service Management

### Run as Windows Service

Use NSSM (Non-Sucking Service Manager) or Task Scheduler to run services automatically.

### Health Check

Monitor service health:
- Backend: `http://192.168.1.100:5000/health`
- Frontend: `http://192.168.1.100:3000`

## Troubleshooting

1. **Can't access from network**: Check Windows Firewall rules
2. **CORS errors**: Verify CORS_ORIGINS in server/.env includes client IPs
3. **Ollama not responding**: Ensure Ollama service is running (`ollama serve`)
4. **Port already in use**: Change PORT in server/.env

