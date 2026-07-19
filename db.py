"""
db.py — Supabase data layer for the LAMATA Emissions Portal
===========================================================
Everything database lives here, so app.py stays about the interface
and emissions_engine.py stays about the math.

The app works in three states, automatically:
    1. Supabase configured + reachable  → uploads are saved once,
       every future session loads instantly from the database.
    2. Supabase not configured          → app behaves exactly as
       before (upload each session). Nothing breaks.
    3. Supabase configured but down     → clear warning, upload
       path still works.

Tables used (see schema SQL in project docs):
    buses · trips · emissions · ml_insights
"""

import math
import pandas as pd
import streamlit as st

BATCH = 500  # rows per insert request — keeps payloads small and reliable


# ──────────────────────────────────────────────────────────────
# CONNECTION
# ──────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_client():
    """Create the Supabase client once per server process.
    Returns None (never raises) if secrets are missing or invalid."""
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"].rstrip("/")
        key = st.secrets["supabase"]["service_key"]
        return create_client(url, key)
    except Exception:
        return None


def db_status():
    """Returns (state, message) for the sidebar indicator.
    state ∈ {'connected', 'empty', 'unconfigured', 'error'}."""
    sb = get_client()
    if sb is None:
        return "unconfigured", "Database not configured — add [supabase] secrets"
    try:
        n = sb.table("trips").select("id", count="exact").limit(1).execute().count
        if n and n > 0:
            return "connected", f"Database connected · {n:,} trip rows stored"
        return "empty", "Database connected · no data yet — upload a manifest to seed it"
    except Exception as e:
        return "error", f"Database error: {str(e)[:120]}"


# ──────────────────────────────────────────────────────────────
# INGESTION  (upload → database, deduplicated)
# ──────────────────────────────────────────────────────────────
def _none_if_nan(v):
    """JSON can't carry NaN — convert to None for the API."""
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except TypeError:
        pass
    return v


def ingest_dataframe(df: pd.DataFrame, source_file: str = "") -> dict:
    """Write a cleaned manifest DataFrame (app column names) into
    Supabase. Buses are upserted; trips are inserted with duplicates
    silently skipped (unique on date + bus + route), so re-uploading
    the same monthly file is harmless.

    Returns {'buses': n, 'trips_sent': n, 'error': str|None}
    """
    sb = get_client()
    if sb is None:
        return {"buses": 0, "trips_sent": 0, "error": "not configured"}

    try:
        # ── 1. Bus register — latest attributes win ──
        bus_cols = {
            "Bus_ID": "bus_id", "Operator": "operator",
            "Bus_Category": "bus_category", "Fuel_Type": "fuel_type",
            "Euro_Standard": "euro_standard",
            "Vehicle_Age_years": "vehicle_age", "Engine_Model": "engine_model",
        }
        have = [c for c in bus_cols if c in df.columns]
        buses = (df[have].drop_duplicates("Bus_ID", keep="last")
                         .rename(columns={c: bus_cols[c] for c in have}))
        buses["bus_id"] = buses["bus_id"].astype(str)
        if "vehicle_age" in buses.columns:
            buses["vehicle_age"] = pd.to_numeric(buses["vehicle_age"], errors="coerce").fillna(0).astype(int)
        bus_records = [{k: _none_if_nan(v) for k, v in r.items()}
                       for r in buses.to_dict("records")]
        for i in range(0, len(bus_records), BATCH):
            sb.table("buses").upsert(bus_records[i:i + BATCH]).execute()

        # ── 2. Trip rows — dedup handled by the unique constraint ──
        trip_cols = {
            "Date": "trip_date", "Bus_ID": "bus_id", "Route_Name": "route_name",
            "Route_Distance_km": "route_distance_km", "Avg_Speed_kmh": "avg_speed_kmh",
            "Ridership": "ridership", "Num_Trips_Today": "num_trips_today",
            "AC_Status": "ac_status", "Idle_Minutes": "idle_minutes",
            "Revenue_Naira": "revenue_naira",
        }
        have = [c for c in trip_cols if c in df.columns]
        trips = df[have].rename(columns={c: trip_cols[c] for c in have}).copy()
        trips["bus_id"] = trips["bus_id"].astype(str)
        trips["trip_date"] = trips["trip_date"].astype(str)
        trips["source_file"] = source_file
        if "ac_status" in trips.columns:
            trips["ac_status"] = trips["ac_status"].astype(str).str.lower().isin(["true", "1", "yes"])
        trip_records = [{k: _none_if_nan(v) for k, v in r.items()}
                        for r in trips.to_dict("records")]
        sent = 0
        for i in range(0, len(trip_records), BATCH):
            chunk = trip_records[i:i + BATCH]
            sb.table("trips").upsert(
                chunk,
                on_conflict="trip_date,bus_id,route_name",
                ignore_duplicates=True,     # re-uploads are no-ops
            ).execute()
            sent += len(chunk)

        return {"buses": len(bus_records), "trips_sent": sent, "error": None}
    except Exception as e:
        return {"buses": 0, "trips_sent": 0, "error": str(e)[:200]}


# ──────────────────────────────────────────────────────────────
# LOADING  (database → app DataFrame)
# ──────────────────────────────────────────────────────────────
def load_trips() -> pd.DataFrame | None:
    """Load all trips joined with their bus attributes, paginated
    (the API caps single requests at 1000 rows). Returns a DataFrame
    with the app's canonical column names, or None."""
    sb = get_client()
    if sb is None:
        return None
    try:
        rows, page, size = [], 0, 1000
        while True:
            batch = (sb.table("trips")
                       .select("*, buses(operator, bus_category, fuel_type,"
                               " euro_standard, vehicle_age, engine_model)")
                       .order("id")
                       .range(page * size, page * size + size - 1)
                       .execute().data)
            rows.extend(batch)
            if len(batch) < size:
                break
            page += 1
        if not rows:
            return None

        df = pd.json_normalize(rows)   # flattens the joined buses.* fields
        df = df.rename(columns={
            "trip_date": "Date", "bus_id": "Bus_ID", "route_name": "Route_Name",
            "route_distance_km": "Route_Distance_km", "avg_speed_kmh": "Avg_Speed_kmh",
            "ridership": "Ridership", "num_trips_today": "Num_Trips_Today",
            "ac_status": "AC_Status", "idle_minutes": "Idle_Minutes",
            "revenue_naira": "Revenue_Naira", "source_file": "Source_File",
            "buses.operator": "Operator", "buses.bus_category": "Bus_Category",
            "buses.fuel_type": "Fuel_Type", "buses.euro_standard": "Euro_Standard",
            "buses.vehicle_age": "Vehicle_Age_years", "buses.engine_model": "Engine_Model",
        })
        # Revenue_Trip column expected downstream — revenue amount doubles as it
        df["Revenue_Trip"] = pd.to_numeric(df.get("Revenue_Naira", 0), errors="coerce").fillna(0)
        return df
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────
# SNAPSHOTS  (calculated results → database, on demand)
# ──────────────────────────────────────────────────────────────
def save_emissions_snapshot(df: pd.DataFrame, methodology: str, ambient_c: float) -> dict:
    """Store calculated emissions stamped with methodology + engine
    version, so any number in a report can be reproduced later.
    Requires the DB 'id' column (rows loaded from the database)."""
    sb = get_client()
    if sb is None or "id" not in df.columns:
        return {"saved": 0, "error": "needs database-loaded rows"}
    cols = {"CO2_kg": "co2_kg", "NOx_kg": "nox_kg", "PM_kg": "pm_kg",
            "CO2_g_km": "co2_g_km", "CO2_g_pkm": "co2_g_pkm",
            "NOx_g_pkm": "nox_g_pkm", "PM_g_pkm": "pm_g_pkm",
            "Compliance": "compliance"}
    try:
        recs = []
        for _, r in df.iterrows():
            rec = {"trip_id": int(r["id"]), "methodology": methodology,
                   "ambient_c": float(ambient_c)}
            for src, dst in cols.items():
                rec[dst] = _none_if_nan(r.get(src))
            recs.append(rec)
        for i in range(0, len(recs), BATCH):
            sb.table("emissions").upsert(
                recs[i:i + BATCH], on_conflict="trip_id,methodology").execute()
        return {"saved": len(recs), "error": None}
    except Exception as e:
        return {"saved": 0, "error": str(e)[:200]}


def save_ml_insights(kind: str, records: list) -> dict:
    """Persist ML outputs (anomaly scores, forecasts, risk scores).
    records: list of dicts with keys matching the ml_insights table."""
    sb = get_client()
    if sb is None:
        return {"saved": 0, "error": "not configured"}
    try:
        clean = [{k: _none_if_nan(v) for k, v in r.items()} for r in records]
        for r in clean:
            r["kind"] = kind
        for i in range(0, len(clean), BATCH):
            sb.table("ml_insights").insert(clean[i:i + BATCH]).execute()
        return {"saved": len(clean), "error": None}
    except Exception as e:
        return {"saved": 0, "error": str(e)[:200]}
