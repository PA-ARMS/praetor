# Endpoint ↔ Frontend Audit

**Purpose:** Ensure all backend API endpoints have corresponding frontend usage where user-facing features exist.

**Last updated:** 2025-02-15

---

## Summary

| Category | Endpoints | Wired | Missing Frontend |
|----------|-----------|-------|------------------|
| Auth | 11 | 10 | 1 (change-password) |
| Chat | 7 | 7 | 0 |
| Corrections | 4 | 4 | 0 |
| Reviews | 4 | 4 | 0 |
| Scenarios | 7 | 6 | 1 (add-scenario) |
| RAG | 5 | 1 | 4 (internal/script use) |
| TTS | 3 | 2 | 1 (status) |
| Forms | 3 | 0 | 3 (no form UI) |
| Documents | 2 | 0 | 2 (separate from RAG upload) |
| User Knowledge | 5 | 0 | 5 (no knowledge UI) |
| Audit | 1 | 1 | 0 |
| System | 3 | 3 | 0 |
| Monitoring | 3 | 0 | 3 (admin may use system instead) |
| Validation | 6 | 0 | 6 (script/testing only) |

---

## Detailed Audit

### ✅ Auth (`/api/auth`) – Fully Wired

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/login` | POST | AuthContext.login |
| `/register` | POST | AuthContext.register |
| `/me` | GET | AuthContext.loadUser |
| `/users` | GET | AdminDashboard |
| `/users/{id}` | PATCH | AdminDashboard (edit user) |
| `/users/{id}/password` | PATCH | AdminDashboard (reset password) |
| `/users/accessible` | GET | ChatHistory (user filter) |
| `/request-password-reset` | POST | Login (forgot password) |
| `/reset-password` | POST | Login (reset flow) |
| `/export-my-data` | GET | SettingsMenu |

**Not wired:** `/change-password` (POST) – No in-app “Change my password” UI. Users use forgot-password or admin reset.

---

### ✅ Chat (`/api/chat`) – Fully Wired

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/query` | POST | ChatInterface |
| `/stream` | POST | Not used (Chat uses non-streaming /query) |
| `/models` | GET | AdminDashboard (AI engine status) – **added** |
| `/message/{id}/full-sources` | GET | FullSourcesModal |
| `/message/{id}/expand-response` | POST | ExpandResponseModal |
| `/history` | GET | ChatHistory |
| `/history/conversations` | GET | ChatHistory |

---

### ✅ Corrections (`/api/corrections`) – Mostly Wired

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/submit` | POST | CorrectionModal |
| `/assigned-to-me` | GET | CorrectionsReview |
| `/{id}/verify` | POST | CorrectionsReview |
| `/list` | GET | CorrectionsReview (Admin "All corrections" view) |

---

### ✅ Reviews (`/api/reviews`) – Fully Wired

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/pending` | GET | ResponseReview |
| `/message/{id}` | GET | ResponseReview |
| `/submit` | POST | ResponseReview |
| `/stats` | GET | ResponseReview |

---

### ✅ Scenarios (`/api/scenarios`) – Mostly Wired

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/stats` | GET | App, AdminDashboard, LearningDashboard |
| `/predict` | POST | ScenarioAnalysis |
| `/find-similar` | POST | ScenarioAnalysis |
| `/progress` | GET | LearningDashboard |
| `/learning/status` | GET | LearningDashboard |
| `/learning/start` | POST | LearningDashboard |
| `/learning/stop` | POST | LearningDashboard |
| `/add-scenario` | POST | **Not wired** – Script/backend only |

---

### ⚠️ RAG (`/api/rag`) – Partial

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/upload-document` | POST | ChatInterface, UploadDocument |
| `/add-document` | POST | Internal/script |
| `/search` | GET | Internal (chat uses it server-side) |
| `/stats` | GET | Internal |
| `/analyze-motion` | POST | UploadDocument passes flag to upload; separate analyze endpoint may exist |

---

### ✅ TTS (`/api/tts`) – Mostly Wired

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/speak` | POST | VoicePlayer |
| `/voices` | GET | VoiceSettings |
| `/status` | GET | **Not wired** – Optional health check |

---

### ❌ Forms (`/api/forms`) – No Frontend

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/generate` | POST | None |
| `/workflow` | POST | None |
| `/templates` | GET | None |

**Note:** Form generation may be invoked from chat or a future Forms tab.

---

### ❌ Documents (`/api/documents`) – No Frontend

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/upload` | POST | None (RAG upload used instead) |
| `/list` | GET | None |

**Note:** RAG handles document upload for search; documents API may be for general file storage.

---

### ❌ User Knowledge (`/api/user-knowledge`) – No Frontend

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/add` | POST | None |
| `/list` | GET | None |
| `/{id}/verify` | POST | None |
| `/{id}/incorporate` | POST | None |
| `/{id}/helpful` | POST | None |

**Note:** Knowledge library has no dedicated UI. Consider a “Knowledge” or “Expertise” tab for attorneys.

---

### ✅ Audit (`/api/audit`) – Wired

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/logs` | GET | AdminDashboard |

---

### ✅ System (`/api/system`) – Wired

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/status` | GET | AdminDashboard |
| `/stats` | GET | AdminDashboard |
| `/health` | GET | Duplicate of root /api/health |

---

### ⚠️ Monitoring (`/api/monitoring`) – Not Wired

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/health` | GET | Admin uses /api/health |
| `/system` | GET | Admin uses /api/system/status |
| `/stats` | GET | Admin uses /api/system/stats |

**Note:** Monitoring routes are role-restricted; AdminDashboard uses system routes instead.

---

### ❌ Validation (`/api/validation`) – Script/Testing Only

| Endpoint | Method | Frontend Usage |
|----------|--------|----------------|
| `/stats` | GET | None |
| `/validations` | GET | None |
| `/validations/{id}/analysis` | GET | None |
| `/patterns` | GET | None |
| `/confusion-matrix` | GET | None |
| `/detect-patterns` | POST | None |

**Note:** Used by learning/validation scripts, not end users.

---

## Recommendations

1. **Change password:** Add “Change my password” in SettingsMenu for logged-in users.
2. **Corrections list:** Add “All Corrections” view in Admin or CorrectionsReview for Admin/Partner.
3. **User Knowledge:** Add Knowledge/Expertise tab for attorneys to add and manage legal knowledge.
4. **Forms:** Add Forms tab or integrate form generation into chat if needed.
5. **Documents list:** If documents API is used, add a document browser; otherwise deprecate or document as internal.
