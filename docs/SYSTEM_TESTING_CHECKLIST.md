# Virginia Legal AI – Full System Testing Checklist

**Purpose:** Comprehensive checklist of all systems and how to test each one.  
**Last updated:** 2025-03-08

---

## Quick Reference

| Category | Systems | Test Method |
|----------|---------|-------------|
| Infrastructure | Python, Node, Ollama, Dependencies | Scripts / Manual |
| Backend | FastAPI, DBs, Middleware | API / `full_system_check.py` |
| Auth | Login, Register, Roles, Password | API / UI |
| Chat | Query, RAG, History, Streaming | API / UI |
| RAG | Search, Upload, Index | API / Scripts |
| Forms | Generate, Workflow, Templates | API |
| Documents | Upload, List | API |
| TTS | Speak, Voices | API / UI |
| Scenarios | Predict, Learning, Similar | API / UI |
| Corrections | Submit, Review, Verify | API / UI |
| Reviews | Pending, Submit | API / UI |
| User Knowledge | Add, List, Incorporate | API |
| Audit | Logs | API / UI |
| System | Status, Health, Stats | API / UI |
| Frontend | All tabs, components | Browser |
| Network | LAN, Firewall, CORS | curl / Browser |

---

## 1. Infrastructure & Environment

### 1.1 Python Environment
- [ ] Python 3.10+ installed: `python --version`
- [ ] Virtual environment active (if used)
- [ ] Dependencies installed: `pip install -r server/requirements.txt`
- [ ] No import errors: `python -c "from server.main import app"`

### 1.2 Node.js Environment
- [ ] Node.js 18+ installed: `node --version`
- [ ] Client dependencies: `cd client && npm install`
- [ ] Build succeeds: `npm run build`

### 1.3 Ollama Service
- [ ] Ollama running: `ollama list` or `curl http://localhost:11434/api/tags`
- [ ] Primary model available: `qwen2.5:7b` (or configured model)
- [ ] Embedding model available: `nomic-embed-text`
- [ ] Generation works: `ollama run qwen2.5:7b "Say hello"`

### 1.4 Configuration
- [ ] `.env` exists (copy from `server/.env.example` if needed)
- [ ] Production secrets set: `python scripts/production_setup.py` (JWT_SECRET, ENCRYPTION_KEY)
- [ ] CORS_ORIGINS configured for LAN if needed
- [ ] `VITE_API_URL` set in `client/.env` for frontend

---

## 2. Backend Core

### 2.1 Server Startup
- [ ] Backend starts: `python server/main.py` (or `scripts/start_server.bat`)
- [ ] No startup errors in console
- [ ] AI Laws verification passes (logged on startup)
- [ ] Database initializes
- [ ] TTS preloads (if enabled) or logs warning

### 2.2 Health & Root Endpoints
| Endpoint | Method | Test | Expected |
|----------|--------|------|----------|
| `/` | GET | `curl http://localhost:5001/` | `{"service":"Virginia Legal AI","status":"running"}` |
| `/health` | GET | `curl http://localhost:5001/health` | `{"status":"healthy","checks":{...}}` |
| `/api/health` | GET | `curl http://localhost:5001/api/health` | Same as `/health` |

### 2.3 Full System Check Script
- [ ] Run: `python full_system_check.py`
- [ ] Backend API: RUNNING
- [ ] File structure: All critical files present
- [ ] Databases: SQLite, ChromaDB, Scenario DB (if enabled)
- [ ] RAG Service: OPERATIONAL, citation search works
- [ ] Ollama Service: Embeddings and generation work
- [ ] Data integrity: VA CSV, scenarios, sources
- [ ] Dependencies: Python and Node OK
- [ ] Service modules: All import successfully

---

## 3. Authentication

### 3.1 Login
- [ ] POST `/api/auth/login` with valid credentials → 200, `access_token`, `user`
- [ ] POST with wrong password → 401
- [ ] POST with nonexistent user → 401
- [ ] POST with empty body → 422

### 3.2 Registration
- [ ] POST `/api/auth/register` with valid data → 201
- [ ] Duplicate username → 4xx

### 3.3 Protected Endpoints
- [ ] GET `/api/auth/me` without token → 401/403
- [ ] GET `/api/auth/me` with valid token → 200, user object

### 3.4 Password & Reset
- [ ] POST `/api/auth/request-password-reset` → 200
- [ ] POST `/api/auth/reset-password` with token → 200
- [ ] POST `/api/auth/change-password` (if wired) → 200

### 3.5 Admin-Only
- [ ] GET `/api/auth/users` as admin → 200
- [ ] GET `/api/auth/users` as non-admin → 403
- [ ] PATCH `/api/auth/users/{id}` (edit user)
- [ ] PATCH `/api/auth/users/{id}/password` (reset password)

### 3.6 Data Export
- [ ] GET `/api/auth/export-my-data` with token → 200, data export

---

## 4. Chat

### 4.1 Query (requires auth)
- [ ] POST `/api/chat/query` with `message`, `use_rag: true` → 200, `response`, `sources`
- [ ] Response includes Virginia-specific law when relevant
- [ ] Citations follow Bluebook format
- [ ] Date disclosure present (AI Laws Article VIII)
- [ ] Verification reminder when appropriate (AI Laws Article IX)

### 4.2 Streaming
- [ ] POST `/api/chat/stream` → SSE stream

### 4.3 History
- [ ] GET `/api/chat/history` → list of conversations
- [ ] GET `/api/chat/history/conversations` → conversations list

### 4.4 Message Details
- [ ] GET `/api/chat/message/{id}/full-sources` → full source text
- [ ] POST `/api/chat/message/{id}/expand-response` → expanded response

### 4.5 Models
- [ ] GET `/api/chat/models` → available Ollama models

---

## 5. RAG (Retrieval-Augmented Generation)

### 5.1 Search
- [ ] GET `/api/rag/search?query=statute%20of%20limitations&n_results=3` (auth) → results with metadata
- [ ] Citation search works: e.g. `18.2-57.2` returns relevant statute

### 5.2 Upload
- [ ] POST `/api/rag/upload-document` with PDF/TXT/DOCX → document indexed
- [ ] POST `/api/rag/add-document` (text content) → document added

### 5.3 Stats
- [ ] GET `/api/rag/stats` → corpus size, document count

### 5.4 Motion Analysis
- [ ] POST `/api/rag/analyze-motion` with document → analysis result

---

## 6. Forms

### 6.1 Generate
- [ ] POST `/api/forms/generate` with `form_type`, `court`, `case_data` → form content, workflow_info

### 6.2 Workflow
- [ ] POST `/api/forms/workflow` with `form_type`, `court` → workflow info

### 6.3 Templates
- [ ] GET `/api/forms/templates` → available templates

**Note:** Forms API has no dedicated frontend; test via API or future Forms tab.

---

## 7. Documents

- [ ] POST `/api/documents/upload` → file stored
- [ ] GET `/api/documents/list` → list of documents

**Note:** Separate from RAG upload; may be for general file storage.

---

## 8. TTS (Text-to-Speech)

### 8.1 Speak
- [ ] POST `/api/tts/speak` with `text` → audio file (WAV/MP3)

### 8.2 Voices
- [ ] GET `/api/tts/voices` → list of available voices

### 8.3 Status
- [ ] GET `/api/tts/status` → TTS service status

---

## 9. Scenarios (if SCENARIO_DB_ENABLED=True)

### 9.1 Stats
- [ ] GET `/api/scenarios/stats` → scenario counts, learning status

### 9.2 Predict
- [ ] POST `/api/scenarios/predict` with case data → outcome prediction

### 9.3 Find Similar
- [ ] POST `/api/scenarios/find-similar` → similar cases

### 9.4 Learning
- [ ] GET `/api/scenarios/learning/status` → learning status
- [ ] POST `/api/scenarios/learning/start` → start learning
- [ ] POST `/api/scenarios/learning/stop` → stop learning
- [ ] GET `/api/scenarios/progress` → learning progress

### 9.5 Add Scenario (backend/script)
- [ ] POST `/api/scenarios/add-scenario` → add scenario (no frontend)

---

## 10. Corrections

### 10.1 Submit
- [ ] POST `/api/corrections/submit` with message_id, correction data → 200

### 10.2 List
- [ ] GET `/api/corrections/list` (admin) → all corrections

### 10.3 Assigned to Me
- [ ] GET `/api/corrections/assigned-to-me` (partner) → assigned corrections

### 10.4 Verify
- [ ] POST `/api/corrections/{id}/verify` → verify correction

---

## 11. Reviews (Senior Partner)

### 11.1 Pending
- [ ] GET `/api/reviews/pending` → messages awaiting review

### 11.2 Message Reviews
- [ ] GET `/api/reviews/message/{id}` → reviews for message

### 11.3 Submit
- [ ] POST `/api/reviews/submit` → submit review

### 11.4 Stats
- [ ] GET `/api/reviews/stats` → review statistics

---

## 12. User Knowledge

- [ ] POST `/api/user-knowledge/add` → add knowledge entry
- [ ] GET `/api/user-knowledge/list` → list entries
- [ ] POST `/api/user-knowledge/{id}/verify` → verify
- [ ] POST `/api/user-knowledge/{id}/incorporate` → incorporate
- [ ] POST `/api/user-knowledge/{id}/helpful` → mark helpful

**Note:** No dedicated frontend; test via API.

---

## 13. Audit

- [ ] GET `/api/audit/logs` (admin/attorney_partner) → audit log entries

---

## 14. System & Monitoring

### 14.1 System
- [ ] GET `/api/system/status` → system status
- [ ] GET `/api/system/stats` → statistics
- [ ] GET `/api/system/health` → health check

### 14.2 Monitoring (role-restricted)
- [ ] GET `/api/monitoring/health`
- [ ] GET `/api/monitoring/system`
- [ ] GET `/api/monitoring/stats`

---

## 15. Validation (Script/Testing Only)

- [ ] GET `/api/validation/stats`
- [ ] GET `/api/validation/validations`
- [ ] GET `/api/validation/validations/{id}/analysis`
- [ ] GET `/api/validation/patterns`
- [ ] GET `/api/validation/confusion-matrix`
- [ ] POST `/api/validation/detect-patterns`

---

## 16. Middleware & Guardrails

### 16.1 AI Laws (Guardrails)
- [ ] Query without RAG triggers appropriate warnings
- [ ] Response includes source disclosure when required
- [ ] No fabricated law (Article I)
- [ ] Hierarchy respected (Article II)
- [ ] Date disclosure present (Article VIII)

### 16.2 Rate Limiting
- [ ] Excessive requests throttled (check RATE_LIMIT_* in config)
- [ ] Health endpoint not rate-limited (or has higher limit)

### 16.3 CORS
- [ ] Frontend (port 3000) can call backend (port 5001)
- [ ] LAN clients can access if CORS_ORIGINS includes their origin

### 16.4 Request ID
- [ ] Responses include `X-Request-ID` header (if implemented)

---

## 17. Frontend (Browser Testing)

### 17.1 Login Page
- [ ] Loads at `http://localhost:3000`
- [ ] Login with valid credentials → redirects to app
- [ ] Invalid credentials → error message
- [ ] Forgot password link works
- [ ] Register link works (if enabled)

### 17.2 Chat Tab
- [ ] Chat interface loads
- [ ] Send message → response appears
- [ ] RAG toggle works (use_rag)
- [ ] Detail level selector works
- [ ] Source citations displayed
- [ ] Expand response modal works
- [ ] Full sources modal works
- [ ] Correction modal opens and submits

### 17.3 Chat History Tab
- [ ] Conversation list loads
- [ ] Select conversation → messages load
- [ ] User filter works (admin/attorney)

### 17.4 Upload Docs Tab
- [ ] File upload works
- [ ] Document indexed and searchable in chat

### 17.5 Scenario Analysis Tab (if enabled)
- [ ] Stats display
- [ ] Predict works with case input
- [ ] Find similar works
- [ ] Learning start/stop (admin)

### 17.6 Corrections Review Tab (admin/partner)
- [ ] Assigned corrections list
- [ ] Verify action works
- [ ] All corrections view (admin)

### 17.7 Response Review Tab (admin/partner)
- [ ] Pending reviews list
- [ ] Submit review works

### 17.8 Admin Dashboard
- [ ] Loads for admin role
- [ ] User list, edit user, reset password
- [ ] Audit logs view
- [ ] System status, AI engine status
- [ ] Stats display

### 17.9 Settings Menu
- [ ] Voice settings (TTS)
- [ ] Export my data
- [ ] Logout

### 17.10 Error Handling
- [ ] Error boundary catches React errors
- [ ] Network errors show user-friendly message
- [ ] 401 redirects to login

---

## 18. Network & Deployment

### 18.1 LAN Access
- [ ] Backend reachable: `curl http://[SERVER_IP]:5001/health`
- [ ] Frontend reachable: `http://[SERVER_IP]:3000` in browser
- [ ] Chat works from another machine

### 18.2 Firewall
- [ ] Port 5001 allowed (backend)
- [ ] Port 3000 allowed (frontend)

### 18.3 Static IP (optional)
- [ ] `SET_STATIC_IP.bat` or `scripts/set_static_ip.ps1` run as admin
- [ ] IP remains stable for CORS/config

---

## 19. Automated Tests

### 19.1 Backend Tests
- [ ] Run: `pytest tests/ -v`
- [ ] `test_auth.py`: login, wrong password, me, invalid token
- [ ] `test_api.py`: health, root, auth validation, chat requires auth, forms requires auth, monitoring requires auth

### 19.2 Run Tests Script
- [ ] `scripts/run_tests.bat` (if exists) runs all tests

---

## 20. Data & Scripts

### 20.1 Data Setup
- [ ] `python scripts/setup_data.py` (if exists)
- [ ] `data/va_csv` has VA Code CSVs
- [ ] `data/sources` has legal sources
- [ ] `data/chroma_db` populated
- [ ] `data/scenarios` has scenario JSONs (if scenario feature enabled)

### 20.2 Ingest
- [ ] `python scripts/ingest_sources.py` for RAG corpus
- [ ] `python scripts/ingest_forms.py` for forms

### 20.3 Backup
- [ ] `python scripts/backup_database.py` runs successfully
- [ ] Backup file created in `data/backups/`

---

## 21. Security Checklist

- [ ] JWT_SECRET not default (32+ chars)
- [ ] ENCRYPTION_KEY not default (32 chars)
- [ ] CORS_ORIGINS restricted in production (no `*`)
- [ ] DEBUG=false in production
- [ ] Password policy enforced (min length, complexity)
- [ ] Rate limiting enabled

---

## 22. Performance Benchmarks (from docs/TESTING.md)

| Metric | Target |
|--------|--------|
| Query response time | < 5 seconds |
| RAG retrieval | < 1 second |
| Form generation | < 10 seconds |
| Streaming latency | < 100ms per chunk |

---

## Summary: Minimum Viable Test Run

For a quick sanity check, run these in order:

1. `python full_system_check.py` – infrastructure and services
2. Start backend: `python server/main.py`
3. Start frontend: `cd client && npm run dev`
4. `curl http://localhost:5001/health` – backend up
5. Open `http://localhost:3000` – login and send one chat message
6. `pytest tests/ -v` – automated tests

---

## Related Documentation

- [TESTING.md](TESTING.md) – Test cases and evaluation criteria
- [API.md](API.md) – API reference
- [ENDPOINT_FRONTEND_AUDIT.md](ENDPOINT_FRONTEND_AUDIT.md) – Endpoint ↔ frontend mapping
- [DEPLOYMENT.md](../DEPLOYMENT.md) – Network and deployment
