# What This Type of System Should Have Implemented

**Purpose:** Checklist of capabilities a mission-critical legal AI / law-firm system typically should have, with current implementation status. Use this to prioritize cleanup, hardening, and new work without touching core AI behavior.

**References:** [SYSTEM_REVIEW.md](../SYSTEM_REVIEW.md), [COMPLIANCE.md](COMPLIANCE.md), [SECURITY_SETUP_GUIDE.md](../SECURITY_SETUP_GUIDE.md)

**Recent implementations (completed):** `.env.example`, BACKUP_RESTORE_GUIDE.md, React ErrorBoundary, Audit log viewer in Admin, User data export (backend + Settings), Password reset (request-password-reset + reset-password + Login UI), Last backup in Admin/system status, Chat message max length (50k), Footer with Privacy & Compliance link and version.

---

## 1. Security & Authentication

| Capability | Status | Notes |
|------------|--------|--------|
| **Strong secrets (JWT, encryption)** | ⚠️ Partial | Config validates and warns; no `.env.example`. **Do:** Create `.env.example`, set real secrets in `.env`. |
| **CORS restricted in production** | ⚠️ Partial | Default `["*"]`; config warns. **Do:** Set `CORS_ORIGINS` in `.env` for production. |
| **Password policy** | ✅ Implemented | Min length 12, complexity in config. |
| **Rate limiting** | ✅ Implemented | Per-IP; chat 30/min, auth 10/min. |
| **Per-user rate limiting** | ❌ Missing | Only per-IP. **Consider:** Per-user limits for fairness and abuse control. |
| **Password reset (forgot password)** | ❌ Missing | Users cannot self-service reset. **Do:** Reset flow (email or admin-only) per policy. |
| **Two-factor authentication (2FA)** | ❌ Missing | Single-factor only. **Consider:** Optional TOTP for admin/attorney. |
| **Session management** | ❌ Missing | No list/revoke sessions or configurable timeout. **Consider:** Active sessions + revoke in Admin. |
| **Account lockout after failed logins** | ❌ Missing | No lockout. **Consider:** Lock after N failures with cooldown. |

---

## 2. Compliance & Audit

| Capability | Status | Notes |
|------------|--------|--------|
| **Audit logging** | ✅ Implemented | Model + auth/chat logging; `/api/audit/logs` for Admin/Partner. |
| **Audit log retention** | ⚠️ Documented | COMPLIANCE.md: 7 years recommended; no automated purge. **Do:** Document and optionally automate retention. |
| **Audit log export** | ❌ Missing | API returns JSON; no CSV/export for compliance packages. **Consider:** Export endpoint or Admin UI “Export logs”. |
| **Data export (user / GDPR-style)** | ❌ Missing | COMPLIANCE mentions “request to admin”; no self-service or automated export. **Do:** User data export (chats, profile) endpoint or Admin tool. |
| **Right to deletion** | ⚠️ Partial | Account deactivate exists; full deletion/retention carve-outs documented in COMPLIANCE. **Do:** Clarify process and any retention exceptions. |
| **Privacy policy / terms** | ⚠️ Documented | COMPLIANCE.md describes policy; no in-app links. **Consider:** Footer links to policy/terms. |

---

## 3. Operations & Reliability

| Capability | Status | Notes |
|------------|--------|--------|
| **Health check** | ✅ Implemented | `/health` and `/api/health`; DB, Ollama, ChromaDB, disk. |
| **Admin/office “system live” UI** | ✅ Implemented | Login status (LIVE/OFFLINE), Admin dashboard status cards + “System is live” banner. |
| **Database backup** | ✅ Implemented | `scripts/backup_database.py`; optional ChromaDB; retention. **Do:** Schedule (e.g. Task Scheduler / cron) and test restore. |
| **Backup/restore documentation** | ⚠️ Partial | COMPLIANCE references `BACKUP_RESTORE_GUIDE.md` which may not exist. **Do:** Add or point to `scripts/backup_database.py` and restore steps. |
| **Request ID / tracing** | ✅ Implemented | RequestIDMiddleware; `X-Request-ID` header. |
| **Structured logging** | ✅ Implemented | Logger per module. **Consider:** Correlation with request_id in log lines. |
| **Metrics / Prometheus** | ❌ Missing | No metrics endpoint. **Consider:** `/metrics` for Prometheus (request count, latency, errors). |
| **Alerting** | ❌ Missing | No automated alerts (disk, health, errors). **Consider:** Alerts when health degrades or backup fails. |
| **Graceful shutdown** | ⚠️ Partial | Uvicorn supports it; ensure in-flight requests complete. |

---

## 4. Admin & Office Experience

| Capability | Status | Notes |
|------------|--------|--------|
| **User management** | ✅ Implemented | Admin dashboard: create, activate/deactivate, reset password. |
| **System status at a glance** | ✅ Implemented | Backend, DB, AI Engine, Scenario DB cards; “System is live” when all up. |
| **Audit log viewer** | ✅ Implemented | `/api/audit/logs` (Admin/Partner); filters. **Consider:** In-app Audit tab in Admin UI. |
| **Monitoring / stats** | ✅ Implemented | `/api/system/stats`, `/api/monitoring/*` (role-restricted). **Consider:** Simple stats panel in Admin (queries today, active users). |
| **Scheduled backup visibility** | ❌ Missing | No UI showing last backup time or backup logs. **Consider:** “Last backup” in Admin or status API. |
| **Version / build info in UI** | ⚠️ Partial | Backend returns version; frontend shows “V.1.0” in header. **Do:** Single source of truth (e.g. env or build time). |

---

## 5. API & Integration

| Capability | Status | Notes |
|------------|--------|--------|
| **API versioning** | ❌ Missing | Routes under `/api/...` with no `/v1/`. **Consider:** `/api/v1/...` before breaking changes. |
| **OpenAPI / Swagger** | ✅ Implemented | FastAPI provides `/docs`, `/redoc`. |
| **Input validation** | ⚠️ Partial | Pydantic on many routes; some endpoints lack max length / sanitization. **Do:** Consistent limits (e.g. message length, query length). |
| **File upload security** | ⚠️ Partial | Size/type in config; auth and path handling should be verified. **Do:** Ensure auth, safe filenames, and no path traversal. |

---

## 6. Legal & Product Specifics

| Capability | Status | Notes |
|------------|--------|--------|
| **AI Laws / guardrails** | ✅ Implemented | Immutable AI Laws, checksum, guardrails middleware. |
| **Citation and sources** | ✅ Implemented | RAG, hierarchy, Bluebook-style, expandable sources in UI. |
| **Disclaimer / “not legal advice”** | ✅ Implemented | In-app disclaimer (e.g. Chat welcome). |
| **Response review (partner)** | ✅ Implemented | Response review flow and learning. |
| **Corrections and learning** | ✅ Implemented | User corrections, knowledge library, learning feedback. |
| **Scenario / outcome prediction** | ✅ Implemented | Optional scenario DB and UI. |
| **Legal accuracy regression tests** | ❌ Missing | No automated suite of “known query → expected behavior”. **Consider:** Curated legal Q&A tests run pre-release. |

---

## 7. Frontend & UX

| Capability | Status | Notes |
|------------|--------|--------|
| **Responsive layout** | ✅ Implemented | Layout and breakpoints in CSS. |
| **Loading and error states** | ✅ Implemented | Spinners, messages, timeout handling in chat/login/admin. |
| **Accessibility (basics)** | ⚠️ Partial | Some `aria-label` (e.g. ExpandableSources, Settings). **Do:** Focus management, keyboard nav, and aria where needed. |
| **Error boundary (React)** | ❌ Missing | No top-level ErrorBoundary. **Do:** Catch render errors and show fallback + optional report. |
| **Offline / connection loss** | ⚠️ Partial | Timeout and error messages; no explicit “connection lost” banner. **Consider:** Global connection status. |
| **Print / export of response** | ❌ Missing | No “Print” or “Export PDF” for a single response. **Consider:** Print-friendly view or export. |

---

## 8. Deployment & Environment

| Capability | Status | Notes |
|------------|--------|--------|
| **Environment config** | ⚠️ Partial | `.env` supported; no `.env.example` in repo. **Do:** Add `.env.example` with all keys (no secrets). |
| **Single-command / script start** | ✅ Implemented | `START_SYSTEM.bat`, status monitor. |
| **HTTPS** | ❌ Missing | Typically handled by reverse proxy. **Do:** Document HTTPS (e.g. Nginx) for production. |
| **Database migration path** | ⚠️ Partial | SQLite; COMPLIANCE/SYSTEM_REVIEW mention PostgreSQL for scale. **Do:** Document migration path if/when needed. |

---

## 9. Testing & Quality

| Capability | Status | Notes |
|------------|--------|--------|
| **API tests** | ⚠️ Partial | `tests/test_api.py`; coverage not guaranteed. **Do:** Run regularly; add critical-path tests. |
| **Frontend tests** | ❌ Missing | No Jest/Vitest (or similar) for React. **Consider:** Smoke tests for login, chat, admin. |
| **Legal accuracy tests** | ❌ Missing | No automated legal Q&A suite. **Consider:** Curated queries and expected behavior. |
| **Load / stress tests** | ❌ Missing | No documented load tests. **Consider:** Basic load test for chat and health. |

---

## 10. Documentation & Onboarding

| Capability | Status | Notes |
|------------|--------|--------|
| **Setup and quick start** | ✅ Implemented | README, QUICKSTART, SETUP. |
| **API reference** | ✅ Implemented | docs/API.md + OpenAPI. |
| **User guide** | ✅ Implemented | docs/USER_GUIDE.md. |
| **Compliance and retention** | ✅ Implemented | docs/COMPLIANCE.md. |
| **Backup/restore steps** | ⚠️ Partial | Script exists; BACKUP_RESTORE_GUIDE referenced but may be missing. **Do:** One doc with backup + restore steps. |
| **Admin runbook** | ⚠️ Partial | Scattered (DEPLOYMENT, SECURITY_SETUP_GUIDE). **Consider:** Single “Admin runbook” (start/stop, backup, health, logs). |

---

## Suggested Priorities (No Change to Core AI)

**High impact, low risk (do first)**  
1. Add `.env.example` and document required env vars.  
2. Document backup schedule and restore procedure (or create BACKUP_RESTORE_GUIDE).  
3. Add React ErrorBoundary and a simple “Something went wrong” fallback.  
4. Optional: Audit log viewer tab in Admin UI (consume existing `/api/audit/logs`).

**Next**  
5. User data export (e.g. “Export my data”) for compliance.  
6. Password reset flow (email or admin-mediated).  
7. Optional: “Last backup” in Admin status or system API.

**Later**  
8. Optional: API versioning (`/api/v1/...`).  
9. Optional: Per-user rate limiting and/or session list/revoke in Admin.  
10. Optional: Legal accuracy test suite and basic frontend smoke tests.

---

**Summary:** The system already has strong foundations (auth, roles, audit, health, backup script, AI Laws, RAG, review/corrections). The main gaps are: env template, backup/restore docs, self-service data export and password reset, optional Admin UX improvements (audit viewer, last backup), ErrorBoundary, and optional testing/monitoring (legal tests, metrics, alerting). None of these require changing core AI or RAG behavior.
