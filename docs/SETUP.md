# Setup Guide - Virginia Legal AI

## Prerequisites

- Windows 11
- NVIDIA RTX 5070 Ti (16GB VRAM confirmed)
- 32GB RAM
- Ollama 0.12.11+ (already installed)
- Python 3.10+
- Node.js 18+

## Initial Setup

### 1. Install Python Dependencies

```bash
pip install -r server/requirements.txt
```

### 2. Install Node Dependencies

```bash
cd client
npm install
```

### 3. Configure Environment

Copy and edit environment file:

```bash
copy server\.env.example server\.env
```

Edit `server/.env` with your settings:
- Set `OLLAMA_MODEL` if using different model
- Configure `CORS_ORIGINS` for network access
- Set `ALLOWED_IPS` for your LAN subnet

### 4. Initialize Data Structure

```bash
python scripts/setup_data.py
```

This creates:
- `data/` directory structure
- Sample corpus entry
- ChromaDB database

### 5. Add Legal Corpus

**Option A: Manual Upload**
- Place Virginia Code documents in `data/corpus/`
- Place Federal law documents in `data/corpus/`
- Use `/api/rag/upload-document` endpoint to index

**Option B: Automated Download**
- Implement scraping in `scripts/download_va_laws.py`
- Run: `python scripts/download_va_laws.py`

### 6. Add Form Templates

- Place Word templates in `data/templates/`
- Templates should be `.docx` format
- System will list available templates via `/api/forms/templates`

## Starting the System

### Development Mode

**Backend:**
```bash
python server/main.py
```

**Frontend:**
```bash
cd client
npm run dev
```

### Production Mode

**Backend:**
```bash
# Use production WSGI server
uvicorn server.main:app --host 0.0.0.0 --port 5000 --workers 1
```

**Frontend:**
```bash
cd client
npm run build
# Serve dist/ folder with static server
```

## Verifying Installation

1. Check Ollama:
```bash
ollama list
ollama run llama3.1:8b "test"
```

2. Check Backend:
```bash
curl http://localhost:5000/health
```

3. Check Frontend:
- Open `http://localhost:3000`
- Should see chat interface

4. Check RAG:
```bash
curl http://localhost:5000/api/rag/stats
```

## Next Steps

1. Add legal corpus (Virginia and Federal laws)
2. Add form templates
3. Configure network access (see DEPLOYMENT.md)
4. Test with sample queries
5. Train staff on usage

## Troubleshooting

### Ollama Not Responding
```bash
# Check if Ollama service is running
ollama serve
```

### Port Already in Use
Change `PORT` in `server/.env`

### CORS Errors
Verify `CORS_ORIGINS` in `server/.env` includes client URL

### GPU Not Used
- Check NVIDIA drivers
- Verify CUDA installation
- Ollama should auto-detect GPU

### Import Errors
```bash
# Reinstall dependencies
pip install -r server/requirements.txt --force-reinstall
```

