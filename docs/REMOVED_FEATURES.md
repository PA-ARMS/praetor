# Removed Features (Simplified Build)

This build is reduced to **chat** and **document reading/understanding** only. Everything below was disabled or removed so we can get the core working first. Add back one at a time as needed.

---

## How to re-enable a feature

1. **Backend:** In `server/main.py`, add back the route import and `app.include_router(...)` for the feature (see list below).
2. **Frontend:** In `client/src/App.jsx`, add back the tab button and the component for that tab; add the component import at the top.
3. **Config:** If the feature uses a flag (e.g. `SCENARIO_DB_ENABLED`), set it in `.env` or `server/config.py`.
4. Restart backend and frontend.

---

## Backend routes removed (can re-add in `server/main.py`)

| Feature | Router / Import | How to re-enable |
|--------|------------------|-------------------|
| **Forms** | `from server.routes import forms` | `app.include_router(forms.router, prefix="/api/forms", tags=["forms"])` |
| **Audit log** | `from server.routes import audit` | `app.include_router(audit.router, prefix="/api/audit", tags=["audit"])` |
| **Monitoring** | `from server.routes import monitoring` | `app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])` |
| **Corrections** | `from server.routes import corrections` | `app.include_router(corrections.router, tags=["corrections"])` |
| **User Knowledge** | `from server.routes import user_knowledge` | `app.include_router(user_knowledge.router, tags=["user-knowledge"])` |
| **Reviews** (partner review) | `from server.routes import reviews` | `app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])` |
| **Matters** | `from server.routes import matters` | `app.include_router(matters.router)` |
| **Scenarios** | Conditional in main; uses `SCENARIO_DB_ENABLED` | Set `SCENARIO_DB_ENABLED=True` in `.env` and ensure scenario router block in main.py is uncommented/enabled |
| **Validation** | `from server.routes import validation` | Uncomment the try/except block that includes `validation.router` |

---

## Frontend tabs / components removed (can re-add in `client/src/App.jsx`)

| Tab | Component | Import |
|-----|-----------|--------|
| **Matters** | MattersDashboard | `import MattersDashboard from './components/MattersDashboard'` |
| **Scenario Analysis** | ScenarioAnalysis | `import ScenarioAnalysis from './components/ScenarioAnalysis'` |
| **Review Responses** | ResponseReview | `import ResponseReview from './components/ResponseReview'` |
| **Review Corrections** | CorrectionsReview | `import CorrectionsReview from './components/CorrectionsReview'` |
| **Administration** | AdminDashboard | `import AdminDashboard from './components/AdminDashboard'` |

Add the tab button (e.g. `activeTab === 'matters'`) and `{activeTab === 'matters' && <MattersDashboard />}` (and optionally the scenario DB check for Scenario Analysis).

---

## Chat UI elements removed (can re-add in `client/src/components/ChatInterface.jsx`)

| Element | Purpose | How to re-add |
|--------|---------|----------------|
| **ScenarioPredictionPanel** | Shows scenario/case outcome prediction | Import `ScenarioPredictionPanel`, add state for `latestPrediction`, render `<ScenarioPredictionPanel prediction={latestPrediction} />`. Ensure chat API returns `scenarioPrediction` and you compute `latestPrediction` from messages. |
| **CorrectionModal** + "Report Incorrect" | Report a response for partner review | Import `CorrectionModal`, add `correctionModalMessageId` and `reportedMessageIds` state, add "Report Incorrect" button and `<CorrectionModal messageId={...} onClose={...} onSuccess={...} />`. |
| **Learning Dashboard** (in Settings) | Opens learning-dashboard.html | In SettingsMenu.jsx, add back the "AI Learning Status" section with the button that opens `/learning-dashboard.html`. |
| **System Administration** (in Settings) | Control panel note | In SettingsMenu.jsx, add back the admin-only "System Administration" section with the control panel note. |

---

## What is kept (core)

- **Auth:** Login, change password, export my data, logout
- **Chat:** Query, streaming, clarification, detail level, exhaustive search, sources, guardrail status, formatting
- **Chat History:** List and open past conversations (if your role has access)
- **Upload Docs:** Upload documents for RAG; OCR and pipeline for reading/understanding from all sources (scanned, PDF, etc.)
- **RAG:** Indexing, search, retrieval used by chat
- **Documents:** Document storage/corpus (if used)
- **System:** Health and status endpoints

---

## File reference (no changes needed to re-enable)

- Route files still exist: `server/routes/forms.py`, `audit.py`, `monitoring.py`, `corrections.py`, `user_knowledge.py`, `reviews.py`, `matters.py`, `scenarios.py`, `validation.py`
- Components still exist: `MattersDashboard.jsx`, `ScenarioAnalysis.jsx`, `ResponseReview.jsx`, `CorrectionsReview.jsx`, `AdminDashboard.jsx`, `ScenarioPredictionPanel.jsx`, `CorrectionModal.jsx`
- Only **registration** (main.py) and **UI tabs / chat UI** (App.jsx, ChatInterface.jsx, SettingsMenu.jsx) were changed.
