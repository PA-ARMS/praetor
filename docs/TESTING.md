# Testing & Evaluation Guide

## Setup Testing Environment

1. Install dependencies:
```bash
pip install -r server/requirements.txt
cd client && npm install
```

2. Initialize data:
```bash
python scripts/setup_data.py
```

3. Start services:
```bash
# Terminal 1
python server/main.py

# Terminal 2
cd client && npm run dev
```

## Test Cases

### 1. Legal Research Query

**Test:** Basic legal question
```bash
curl -X POST http://localhost:5000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the statute of limitations for personal injury in Virginia?",
    "use_rag": true
  }'
```

**Expected:**
- Response includes Virginia-specific law
- Citations follow Bluebook format
- Sources listed with jurisdiction
- Date disclosure included

### 2. Form Generation

**Test:** Generate motion form
```bash
curl -X POST http://localhost:5000/api/forms/generate \
  -H "Content-Type: application/json" \
  -d '{
    "form_type": "Motion for Summary Judgment",
    "court": "Circuit Court of Fairfax County",
    "case_data": {
      "plaintiff": "Test Plaintiff",
      "defendant": "Test Defendant"
    }
  }'
```

**Expected:**
- Form content generated
- Workflow information included
- Verification required flag set

### 3. RAG Search

**Test:** Search corpus
```bash
curl "http://localhost:5000/api/rag/search?query=statute%20of%20limitations&n_results=3"
```

**Expected:**
- Relevant documents returned
- Metadata included
- Distance scores provided

### 4. Guardrails Validation

**Test:** Query that should trigger warnings
```bash
curl -X POST http://localhost:5000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me about contract law",
    "use_rag": false
  }'
```

**Expected:**
- Response includes warnings if citations missing
- System prompt includes AI Laws

## Evaluation Criteria

### Accuracy
- Legal citations are correct
- Statutory references are accurate
- Case law is properly cited

### Compliance with AI Laws
- Article I: No fabricated law
- Article II: Hierarchy respected
- Article III: Sources disclosed
- Article VIII: Date disclosure present
- Article IX: Verification reminder included

### RAG Quality
- Relevant documents retrieved
- Context improves responses
- Sources are properly attributed

### Form Generation
- All required fields filled
- Court-specific formatting followed
- Workflow information accurate

## Performance Benchmarks

- Query response time: < 5 seconds
- RAG retrieval: < 1 second
- Form generation: < 10 seconds
- Streaming latency: < 100ms per chunk

## Network Testing

1. Test from another machine on LAN:
```bash
curl http://[SERVER_IP]:5000/health
```

2. Test frontend access:
- Open `http://[SERVER_IP]:3000` in browser
- Verify chat interface loads
- Test query submission

## Load Testing

Use tools like Apache Bench or wrk:

```bash
ab -n 100 -c 10 http://localhost:5000/api/chat/query
```

Monitor:
- Response times
- Error rates
- GPU memory usage
- System resources

## Continuous Monitoring

Monitor these metrics:
- GPU utilization (nvidia-smi)
- Memory usage
- Query response times
- Error rates
- Corpus size growth

