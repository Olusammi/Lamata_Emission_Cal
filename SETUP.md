# LAMATA Emissions Portal — Setup & Architecture

## Repo layout
```
app.py                  Streamlit interface (10 modules)
emissions_engine.py     v4 emissions math (readable, documented)
db.py                   Supabase data layer (ingest / load / snapshots)
ml_engine.py            ML: anomalies · forecasting · compliance risk
requirements.txt        Streamlit Cloud dependencies
backend/main.py         FastAPI service (optional, Phase 3)
backend/requirements.txt
```

## Deploy (Streamlit Cloud)
1. Push all files to your GitHub repo (NOT any secrets.toml).
2. App Settings → Secrets:
   [supabase]
   url = "https://YOURREF.supabase.co"
   service_key = "sb_secret_..."
   [credentials]
   youruser = "yourpassword"
3. Reboot the app. Sidebar shows a green "Database connected" dot.

## How data flows now
- First upload → parsed → calculated → auto-saved to Supabase
  (duplicates skipped via unique constraint on date+bus+route).
- Every later session → loads from Supabase automatically. No upload.
- "Reload from database" button clears cache and re-pulls.
- Deep Search → "Snapshot results to DB" stores calculated emissions
  stamped with methodology + ambient + engine version (reproducibility).
- Fleet Health / Forecast → "Save … to database" writes ML scores
  to ml_insights.

## Database schema (run once in Supabase SQL Editor)
See the CREATE TABLE statements from our setup conversation
(buses, trips, emissions, ml_insights — RLS enabled, no policies:
only the server-side secret key can read/write).

## Backend API (optional)
cd into repo, then:
  pip install -r backend/requirements.txt
  export SUPABASE_URL=... SUPABASE_SERVICE_KEY=...
  uvicorn backend.main:app --reload
Endpoints: GET /health · POST /calculate · GET /fleet/summary · GET /ml/anomalies
Deploys free/cheap on Railway or Render.

## Notes
- Free-tier Supabase pauses after ~1 week idle: dashboard → Restore.
- Rotate any key that ever leaves your secrets storage.
