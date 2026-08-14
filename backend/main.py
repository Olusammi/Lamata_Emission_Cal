"""
backend/main.py — LAMATA Emissions API

FastAPI service backing the React frontend (frontend/). Replaces the
Streamlit app's UI-embedded logic with a stateless REST API: the
emissions engine (emissions_engine.py) and ML models (ml_engine.py) are
reused unmodified; everything else (auth, uploads, database access,
AI assistant) is ported off Streamlit onto plain environment variables
and JWT auth. See MIGRATION.md at the repo root for setup.

Run locally:
    pip install -r backend/requirements.txt
    # set env vars — see MIGRATION.md — then:
    uvicorn backend.main:app --reload
"""
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Make the repo-root modules (emissions_engine, ml_engine) importable
# whether this is run as `uvicorn backend.main:app` from the repo root
# or the backend package is installed some other way.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from emissions_engine import calculate_row, compliance_flag  # noqa: E402

from . import db  # noqa: E402
from .config import get_settings  # noqa: E402
from .routers import ai as ai_router  # noqa: E402
from .routers import auth as auth_router  # noqa: E402
from .routers import calc as calc_router  # noqa: E402
from .routers import corridors as corridors_router  # noqa: E402
from .routers import data as data_router  # noqa: E402
from .routers import ml as ml_router  # noqa: E402

app = FastAPI(title="LAMATA Emissions API", version="1.0.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(data_router.router)
app.include_router(calc_router.router)
app.include_router(ml_router.router)
app.include_router(ai_router.router)
app.include_router(corridors_router.router)


@app.get("/health")
def health():
    state, _ = db.db_status()
    return {"status": "ok", "database": state}


# ── Kept for parity with the original Phase-3 skeleton: a single-row
# calculator that doesn't require auth or a full manifest upload. Useful
# for quick integration checks from other LAMATA systems. ──
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


@app.post("/calculate")
def calculate(trip: TripRecord):
    row = trip.model_dump()
    row["Revenue_Trip"] = row.get("Revenue_Naira", 1) or 1
    result = calculate_row(row, trip.methodology, ["CO2", "NOx", "PM"], trip.ambient_c)
    out = {k: (None if v != v else v) for k, v in result.to_dict().items()}
    out["compliance_passenger"] = compliance_flag(result.get("CO2_g_pkm"), trip.Bus_Category)
    out["compliance_vehicle"] = compliance_flag(result.get("CO2_g_km"), trip.Bus_Category, "vehicle")
    return out


@app.get("/fleet/summary")
def fleet_summary():
    sb = db.get_client()
    if sb is None:
        raise HTTPException(503, "Database not configured")
    trips = sb.table("trips").select("id", count="exact").limit(1).execute().count or 0
    buses = sb.table("buses").select("bus_id", count="exact").limit(1).execute().count or 0
    return {"trip_rows": trips, "buses": buses}
