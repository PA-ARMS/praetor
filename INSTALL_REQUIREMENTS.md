# Installation Requirements

Before starting the Virginia Legal AI system, you need to install:

## 1. Python 3.10 or Higher

### Option A: Official Python Installer (Recommended)
1. Download Python from: https://www.python.org/downloads/
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH" during installation
4. Verify installation:
   ```powershell
   python --version
   ```

### Option B: Microsoft Store
1. Open Microsoft Store
2. Search for "Python 3.11" or "Python 3.12"
3. Click Install
4. Verify installation:
   ```powershell
   python --version
   ```

## 2. Node.js 18 or Higher

### Download and Install
1. Download Node.js from: https://nodejs.org/
2. Choose the LTS version (recommended)
3. Run the installer (includes npm)
4. Verify installation:
   ```powershell
   node --version
   npm --version
   ```

## 3. After Installation

Once both are installed, restart your terminal/PowerShell and run:

```powershell
# Verify installations
python --version
node --version
npm --version

# Install Python dependencies
pip install -r server/requirements.txt

# Install Node dependencies
cd client
npm install
cd ..
```

## 4. Start the System

After installations are complete:

```powershell
# Terminal 1 - Backend
python server/main.py

# Terminal 2 - Frontend  
cd client
npm run dev
```

Or use the batch scripts:
```powershell
scripts\start_server.bat
scripts\start_client.bat
```

## Troubleshooting

### Python not found after installation
- Restart your terminal/PowerShell
- Check if Python is in PATH: `$env:PATH`
- Reinstall Python with "Add to PATH" checked

### npm install fails
- Make sure Node.js is installed (includes npm)
- Try: `npm install --legacy-peer-deps`
- Check Node version: `node --version` (should be 18+)

### Port already in use
- Change PORT in `server/.env` if 5000 is taken
- Change port in `client/vite.config.js` if 3000 is taken

