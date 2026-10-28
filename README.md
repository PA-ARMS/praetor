# Virginia Legal AI System

A local AI-powered legal research and form generation system for law firms, running on Ollama with RAG capabilities.

## System Requirements

- Windows 11
- NVIDIA RTX 5070 Ti (16GB VRAM)
- 32GB RAM
- Ollama 0.12.11+
- Python 3.10+
- Node.js 18+

## Architecture

- **Backend**: FastAPI server with Ollama integration
- **Frontend**: React web interface
- **RAG**: Vector database (Chroma) for legal corpus
- **Forms**: Template-based generation (Word/PDF)
- **Network**: LAN-accessible service

## Quick Start

**Get everything ready (one command):**

```bash
python scripts/get_ready.py
# Or with production secrets:  python scripts/get_ready.py --production
# On Windows you can double-click:  GET_READY.bat
```

**Verify everything is working:**

```bash
python scripts/verify_everything.py
# With tests:  python scripts/verify_everything.py --tests
# On Windows:  VERIFY_EVERYTHING.bat
```
First verify run may take 1-2 minutes while the BART summarization model loads.

1. Install dependencies:
   ```bash
   pip install -r server/requirements.txt
   python -m spacy download en_core_web_sm   # For entity extraction
   cd client && npm install
   ```
   Note: Document pipeline features (table extraction, neural OCR) require Java for tabula-py. Tesseract is required for OCR (see docs/OCR_SETUP.md).

2. Configure environment:
   ```bash
   copy server\.env.example .env
   python scripts/production_setup.py   # Generates secure secrets, sets production config
   ```

3. Initialize data:
   ```bash
   python scripts/setup_data.py
   ```

4. Pull the legal LLM (one-time; default is initium/law_model):
   ```bash
   ollama run initium/law_model
   ```
   This downloads the model if needed. Keep Ollama running (`ollama serve`).

5. Start services:
   ```bash
   python server/main.py
   # In another terminal:
   cd client && npm run dev
   ```

For detailed setup instructions, see [QUICKSTART.md](QUICKSTART.md) or [docs/SETUP.md](docs/SETUP.md).

## Production Deployment

Before deploying to production:

1. Run `python scripts/production_setup.py` to generate secure JWT/encryption keys and set production CORS
2. For LAN access, add your server IP to `CORS_ORIGINS` in `.env`
3. Restart the backend after config changes
4. See [DEPLOYMENT.md](DEPLOYMENT.md) for firewall and network setup

## Directory Structure

```
LAWFIRMAI/
├── server/          # FastAPI backend
├── client/          # React frontend
├── data/            # Legal corpus and documents (created on setup)
├── scripts/          # Data pipeline and utilities
├── config/          # Configuration files (AI Laws)
└── docs/            # Documentation

```

## Keeping Virginia Law Current

Statutes are refreshed from the official LIS CSV exports:

```bat
UPDATE_VA_LAWS.bat
```

To schedule an automatic yearly update (July 15): `SETUP_VA_LAW_UPDATE.bat`  
To watch progress during a rebuild: `SHOW_VA_REBUILD_PROGRESS.bat`  
See [docs/VA_LAW_ANNUAL_UPDATE.md](docs/VA_LAW_ANNUAL_UPDATE.md).

## Documentation

- [Quick Start Guide](QUICKSTART.md) - Get started in 5 minutes
- [Virginia Law Annual Update](docs/VA_LAW_ANNUAL_UPDATE.md) - Refresh Code of Virginia in RAG
- [Setup Guide](docs/SETUP.md) - Detailed installation instructions
- [Deployment Guide](DEPLOYMENT.md) - Network configuration for LAN access
- [API Documentation](docs/API.md) - API endpoints reference
- [Testing Guide](docs/TESTING.md) - Testing procedures
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md) - What's been built

## Features

- ✅ Legal research with RAG (Retrieval-Augmented Generation)
- ✅ Form generation from case data
- ✅ Workflow/procedure retrieval
- ✅ AI Laws compliance (10 Articles enforced)
- ✅ Source citation and verification
- ✅ Network-accessible service
- ✅ Streaming responses
- ✅ Document management

