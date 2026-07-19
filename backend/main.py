"""
backend/main.py — LAMATA Emissions API (Phase 3 skeleton)
=========================================================
A thin FastAPI service exposing the SAME emissions engine and ML code
the Streamlit app uses, so other consumers (LAMATA systems, a mobile
app, scheduled report jobs) can share one source of truth.

Run locally:
    pip install -r backend/requirements.txt
    export SUPABASE_URL="https://xxxx.supabase.co"
    export SUPABASE_SERVICE_KEY="sb_secret_..."
    uvicorn backend.main:app --reload

Deploy free/cheap on Railway or Render (both auto-detect uvicorn).

Endpoints:
    GET  /health              — liveness + database reachability
    POST /calculate           — run the emissions engine on one trip record
    GET  /fleet/summary       — totals straight from Supabase
    GET  /ml/anomalies        — latest saved anomaly scores
"""

import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Reuse the app's engine — one source of truth for the math:
sys.path.append(str(Path(__file__).resolve().parent.parent))
from emissions_engine import calculate_row, compliance_flag  # noqa: E402

app = FastAPI(title="LAMATA Emissions API", version="0.1.0")


# ── Supabase client from environment variables (no Streamlit here) ──
def get_db():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


# ── Request/response models ──
class TripRecord(BaseModel):
    Bus_Category: str = Field(examples=["HC"])
    Fuel_Type: str = Field(examples=["Diesel"])
    Route_Distance_km: float = 180
    Avg_Speed_kmh: float = 25
    Ridership: int = 300
    Num_Trips_Today: int = 6
    Euro_Standard: str = "Euro III"
    Vehicle_Age_years: int = 5
    AC_Status: bool = False
    Engine_Model: str = ""
    Revenue_Naira: float = 0
    methodology: str = "Hybrid"
    ambient_c: float = 28.0


@app.get("/health")
def health():
    db = get_db()
    db_ok = False
    if db is not None:
        try:
            db.table("trips").select("id").limit(1).execute()
            db_ok = True
        except Exception:
            db_ok = False
    return {"status": "ok", "database": "connected" if db_ok else "unavailable"}


@app.post("/calculate")
def calculate(trip: TripRecord):
    """Run the v4 engine on a single trip record."""
    row = trip.model_dump()
    row["Revenue_Trip"] = row.get("Revenue_Naira", 1) or 1
    result = calculate_row(row, trip.methodology, ["CO2", "NOx", "PM"], trip.ambient_c)
    out = {k: (None if v != v else v) for k, v in result.to_dict().items()}  # NaN → null
    out["compliance_passenger"] = compliance_flag(result.get("CO2_g_pkm"), trip.Bus_Category)
    out["compliance_vehicle"] = compliance_flag(result.get("CO2_g_km"), trip.Bus_Category, "vehicle")
    return out


@app.get("/fleet/summary")
def fleet_summary():
    """Row counts and stored-emissions totals from the database."""
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database not configured")
    trips = db.table("trips").select("id", count="exact").limit(1).execute().count or 0
    buses = db.table("buses").select("bus_id", count="exact").limit(1).execute().count or 0
    return {"trip_rows": trips, "buses": buses}


@app.get("/ml/anomalies")
def anomalies(limit: int = 50):
    """Latest saved Fleet Health scores (written by the Streamlit app)."""
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database not configured")
    rows = (db.table("ml_insights").select("*").eq("kind", "anomaly")
              .order("created_at", desc=True).limit(limit).execute().data)
    return {"count": len(rows), "results": rows}
