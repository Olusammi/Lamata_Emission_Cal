"""
backend/db.py — Supabase data layer for the FastAPI service.

Port of the root db.py, with two changes:
  1. No Streamlit dependency — credentials come from backend/config.py
     (environment variables) instead of st.secrets, and the client is
     cached with functools.lru_cache instead of st.cache_resource.
  2. delete_all_trips() takes an explicit confirm phrase argument; the
     router is what actually enforces it must equal "DELETE", but the
     function signature makes the call site show intent.

Tables used (unchanged from the original schema):
    buses · trips · emissions · ml_insights
"""
import math
from functools import lru_cache

import pandas as pd

from .config import get_settings

BATCH = 500  # rows per insert request — keeps payloads small and reliable


@lru_cache
def get_client():
    """Create the Supabase client once per process. Returns None (never
    raises) if credentials are missing or invalid."""
    try:
        from supabase import create_client
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_key:
            return None
        return create_client(settings.supabase_url.rstrip("/"), settings.supabase_service_key)
    except Exception:
        return None


def db_status() -> tuple[str, str]:
    """Returns (state, message). state in {'connected','empty','unconfigured','error'}."""
    sb = get_client()
    if sb is None:
        return "unconfigured", "Database not configured — set SUPABASE_URL / SUPABASE_SERVICE_KEY"
    try:
        n = sb.table("trips").select("id", count="exact").limit(1).execute().count
        if n and n > 0:
            return "connected", f"Database connected · {n:,} trip rows stored"
        return "empty", "Database connected · no data yet — upload a manifest to seed it"
    except Exception as e:
        return "error", f"Database error: {str(e)[:120]}"


def _none_if_nan(v):
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except TypeError:
        pass
    return v


def ingest_dataframe(df: pd.DataFrame, source_file: str = "") -> dict:
    """Write a cleaned manifest DataFrame (app column names) into Supabase.
    Buses are upserted; trips are inserted with duplicates silently
    skipped (unique on date + bus + route).

    Returns {'buses': n, 'trips_sent': n, 'error': str|None}
    """
    sb = get_client()
    if sb is None:
        return {"buses": 0, "trips_sent": 0, "error": "not configured"}

    try:
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
                chunk, on_conflict="trip_date,bus_id,route_name", ignore_duplicates=True,
            ).execute()
            sent += len(chunk)

        return {"buses": len(bus_records), "trips_sent": sent, "error": None}
    except Exception as e:
        return {"buses": 0, "trips_sent": 0, "error": str(e)[:200]}


def load_trips() -> pd.DataFrame | None:
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

        df = pd.json_normalize(rows)
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
        df["Revenue_Trip"] = pd.to_numeric(df.get("Revenue_Naira", 0), errors="coerce").fillna(0)
        return df
    except Exception:
        return None


def save_emissions_snapshot(df: pd.DataFrame, methodology: str, ambient_c: float) -> dict:
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
            rec = {"trip_id": int(r["id"]), "methodology": methodology, "ambient_c": float(ambient_c)}
            for src, dst in cols.items():
                rec[dst] = _none_if_nan(r.get(src))
            recs.append(rec)
        for i in range(0, len(recs), BATCH):
            sb.table("emissions").upsert(recs[i:i + BATCH], on_conflict="trip_id,methodology").execute()
        return {"saved": len(recs), "error": None}
    except Exception as e:
        return {"saved": 0, "error": str(e)[:200]}


def save_ml_insights(kind: str, records: list) -> dict:
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


def list_uploads() -> list:
    sb = get_client()
    if sb is None:
        return []
    try:
        rows = sb.table("trips").select("source_file, trip_date").execute().data
        by_file = {}
        for r in rows:
            f = r.get("source_file") or "(unnamed upload)"
            g = by_file.setdefault(f, {"source_file": f, "rows": 0,
                                       "first": r["trip_date"], "last": r["trip_date"]})
            g["rows"] += 1
            g["first"] = min(g["first"], r["trip_date"])
            g["last"] = max(g["last"], r["trip_date"])
        return sorted(by_file.values(), key=lambda x: x["last"], reverse=True)
    except Exception:
        return []


def delete_upload(source_file: str) -> dict:
    sb = get_client()
    if sb is None:
        return {"deleted": False, "error": "not configured"}
    try:
        sb.table("trips").delete().eq("source_file", source_file).execute()
        return {"deleted": True, "error": None}
    except Exception as e:
        return {"deleted": False, "error": str(e)[:200]}


def delete_all_trips(confirm_phrase: str) -> dict:
    """Wipe ALL trips (and cascaded emissions/ml). Keeps the bus register.
    Callers (the router) are responsible for checking the caller is an
    admin; this function additionally refuses to run unless the exact
    confirm phrase "DELETE" is passed, as a second, code-level guard
    against an accidental call."""
    if confirm_phrase != "DELETE":
        return {"deleted": False, "error": "confirmation phrase did not match"}
    sb = get_client()
    if sb is None:
        return {"deleted": False, "error": "not configured"}
    try:
        sb.table("trips").delete().neq("id", -1).execute()
        return {"deleted": True, "error": None}
    except Exception as e:
        return {"deleted": False, "error": str(e)[:200]}
