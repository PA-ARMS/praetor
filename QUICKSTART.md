# Quick Start Guide

## 1. Install Dependencies

```bash
# Python dependencies
pip install -r server/requirements.txt

# Node dependencies
cd client
npm install
cd ..
```

## 2. Configure Environment

```bash
# Copy example env file
copy server\.env.example server\.env

# Edit server\.env and set:
# - Your server IP for CORS_ORIGINS
# - OLLAMA_MODEL if different from llama3.1:8b
```

## 3. Initialize Data

```bash
python scripts/setup_data.py
```

## 4. Start Services

**Terminal 1 - Backend:**
```bash
python server/main.py
```

**Terminal 2 - Frontend:**
```bash
cd client
npm run dev
```

## 5. Access System

- Local: http://localhost:3000
- Network: http://[YOUR_IP]:3000

## 6. Add Legal Corpus

Upload Virginia and Federal law documents:

```bash
# Via API
curl -X POST http://localhost:5000/api/rag/upload-document \
  -F "file=@path/to/document.txt" \
  -F "jurisdiction=Virginia"
```

Or place files in `data/corpus/` and use the upload endpoint.

## 7. Test System

Try a legal query:
- "What is the statute of limitations for breach of contract in Virginia?"
- "Generate a motion to dismiss form for Circuit Court"

## Next Steps

- See `docs/SETUP.md` for detailed setup
- See `DEPLOYMENT.md` for network configuration
- See `docs/API.md` for API documentation
- See `docs/TESTING.md` for testing procedures

