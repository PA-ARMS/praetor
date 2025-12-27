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

1. Install dependencies:
   ```bash
   pip install -r server/requirements.txt
   cd client && npm install
   ```

2. Configure environment:
   ```bash
   copy server\.env.example server\.env
   # Edit server\.env with your settings
   ```

3. Initialize data:
   ```bash
   python scripts/setup_data.py
   ```

4. Start services:
   ```bash
   python server/main.py
   # In another terminal:
   cd client && npm run dev
   ```

For detailed setup instructions, see [QUICKSTART.md](QUICKSTART.md) or [docs/SETUP.md](docs/SETUP.md).

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

## Documentation

- [Quick Start Guide](QUICKSTART.md) - Get started in 5 minutes
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

