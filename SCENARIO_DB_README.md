# Scenario Database - Local Development

This feature adds predictive analysis capabilities to the legal AI system by storing case scenarios and predicting outcomes based on similar fact patterns.

## Status: Local Development (Not in Production)

**Feature Flag:** `SCENARIO_DB_ENABLED = False` (default)

The scenario database is **disabled by default** and will not affect your production system.

## File Structure

```
LAWFIRMAI/
├── server/
│   ├── config.py                    # MODIFIED: Added SCENARIO_DB_ENABLED flag
│   ├── main.py                      # MODIFIED: Conditional route loading
│   ├── routes/
│   │   └── scenarios.py             # NEW: Scenario API routes
│   └── services/
│       └── scenario_service.py      # NEW: Scenario database service
├── scripts/
│   ├── download_cases.py            # NEW: Download cases from CourtListener
│   └── process_scenarios.py        # NEW: Process cases into scenarios
└── data/
    ├── scenario_db/                 # NEW: Scenario ChromaDB (separate from RAG)
    └── scenarios/                   # NEW: Raw case data files
```

## Enabling the Feature

1. **Set environment variable:**
   ```bash
   # In server/.env file, add:
   SCENARIO_DB_ENABLED=True
   ```

2. **Or set in code (temporary):**
   ```python
   # In server/config.py, change:
   SCENARIO_DB_ENABLED: bool = True
   ```

3. **Restart the server:**
   ```bash
   python -m uvicorn server.main:app --host 0.0.0.0 --port 5000
   ```

4. **Verify it's enabled:**
   - Check server startup logs for: `✓ Scenario database features enabled`
   - API endpoints will be available at `/api/scenarios/*`

## API Endpoints

When enabled, these endpoints are available:

### POST `/api/scenarios/add-scenario`
Add a scenario to the database.

**Request:**
```json
{
  "facts": "Contract dispute over software delivery...",
  "metadata": {
    "outcome": "Settlement",
    "case_type": "Contract",
    "jurisdiction": "Virginia",
    "court_level": "Circuit Court",
    "key_factors": ["Force majeure clause", "Pandemic impact"],
    "settlement_amount": 150000
  }
}
```

### POST `/api/scenarios/predict`
Predict outcome probability for given facts.

**Request:**
```json
{
  "facts": "Contract dispute over delayed delivery...",
  "case_type": "Contract",
  "jurisdiction": "Virginia"
}
```

**Response:**
```json
{
  "prediction": "Settlement",
  "confidence": 72.5,
  "similar_scenarios": 15,
  "outcome_probabilities": {
    "Settlement": 45.2,
    "Plaintiff Win": 28.7,
    "Defendant Win": 18.3
  }
}
```

### POST `/api/scenarios/find-similar`
Find similar scenarios.

### GET `/api/scenarios/stats`
Get database statistics.

## Downloading Case Data

### Step 1: Get CourtListener API Key

1. Sign up at: https://www.courtlistener.com/api/
2. Get your free API key
3. Set environment variable:
   ```bash
   # In PowerShell:
   $env:COURTLISTENER_API_KEY="your-api-key-here"
   
   # Or add to server/.env:
   COURTLISTENER_API_KEY=your-api-key-here
   ```

### Step 2: Download Cases

```bash
# Download all Virginia cases (takes time)
python scripts/download_cases.py

# Or limit for testing:
python scripts/download_cases.py 100
```

Cases will be saved to: `data/scenarios/courtlistener/`

### Step 3: Process Cases into Scenarios

```bash
# Process all downloaded cases
python scripts/process_scenarios.py

# Or limit for testing:
python scripts/process_scenarios.py 100
```

This extracts facts, outcomes, and metadata from case files and adds them to the scenario database.

## Testing

### Test with Feature Disabled (Default)
```bash
# Start server (feature disabled)
python -m uvicorn server.main:app --host 0.0.0.0 --port 5000

# Verify existing system works normally
# Scenario endpoints should return 404
```

### Test with Feature Enabled
```bash
# Set environment variable
$env:SCENARIO_DB_ENABLED="True"

# Start server
python -m uvicorn server.main:app --host 0.0.0.0 --port 5000

# Test endpoint
curl http://localhost:5000/api/scenarios/stats
```

## Safety Features

✅ **Feature Flag:** Disabled by default  
✅ **Separate Database:** Uses `data/scenario_db/` (not `data/chroma_db/`)  
✅ **Separate Routes:** New routes file, doesn't modify existing  
✅ **Separate Service:** New service file, doesn't modify existing  
✅ **Conditional Loading:** Only loads if flag is enabled  
✅ **No Data Contamination:** Scenario data in separate directories  

## Current System Impact

**With `SCENARIO_DB_ENABLED = False` (default):**
- ✅ All existing functionality works exactly as before
- ✅ No new routes loaded
- ✅ No new services initialized
- ✅ No performance impact
- ✅ No data changes

**With `SCENARIO_DB_ENABLED = True`:**
- ✅ Existing system continues to work
- ✅ New scenario endpoints available
- ✅ Separate database (doesn't affect RAG)
- ✅ Can be disabled anytime by setting flag to False

## Development Notes

- All scenario code is in new files (no modifications to existing production code)
- Feature can be enabled/disabled with single flag
- Data stored separately from main RAG database
- Can develop and test without affecting production system

## Next Steps

1. Get CourtListener API key
2. Download test cases (start with 10-20 cases)
3. Process them into scenarios
4. Test prediction endpoint
5. Gradually increase dataset size
6. Refine extraction logic as needed

## Troubleshooting

**"Scenario database is not enabled"**
- Set `SCENARIO_DB_ENABLED=True` in environment or config

**"COURTLISTENER_API_KEY not set"**
- Get API key from https://www.courtlistener.com/api/
- Set as environment variable or in `.env` file

**"Case directory not found"**
- Run `download_cases.py` first to download case data

**Routes return 404**
- Check that `SCENARIO_DB_ENABLED=True`
- Restart server after changing flag
- Check server logs for error messages

