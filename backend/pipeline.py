"""
backend/pipeline.py — manifest ingestion pipeline.

Port of app.py's _fuzzy_rename / _read_raw_file / _clean_and_calculate
(app.py:850-1085), unchanged in logic, minus the Streamlit UI calls and
plus explicit upload-size/row-count guards (the original had none —
noted as a resource-exhaustion gap in the security review).
"""
import io
import re

import pandas as pd

from emissions_engine import calculate_row, compliance_flag

EXPECTED_COLS = [
    "Date", "Route_Name", "Bus_ID", "Operator", "Bus_Category",
    "Fuel_Type", "Route_Distance_km", "Avg_Speed_kmh", "Ridership", "Revenue_Trip",
]
NEW_COLS = ["Euro_Standard", "Vehicle_Age_years", "AC_Status", "Num_Trips_Today", "Engine_Model"]

ALIASES = {
    "Bus_Category":       ["bus_type", "category", "bus_size", "vehicle_type", "type"],
    "Fuel_Type":          ["fuel", "fueltype", "energy_source", "propulsion"],
    "Route_Distance_km":  ["distance", "dist", "km", "route_km", "distance_km", "trip_distance"],
    "Avg_Speed_kmh":      ["speed", "avg_speed", "average_speed", "speed_kmh"],
    "Ridership":          ["passengers", "pax", "riders", "passenger_count", "boardings"],
    "Revenue_Trip":       ["revenue", "is_revenue", "paid_trip", "commercial"],
    "Route_Name":         ["route", "routename", "line", "route_id"],
    "Bus_ID":             ["bus", "vehicle_id", "vehicle", "fleet_id", "bus_no", "plate"],
    "Operator":           ["company", "operator_name", "fleet_operator", "owner"],
    "Date":               ["trip_date", "date_of_trip", "service_date", "day"],
    "Euro_Standard":      ["euro", "euro_class", "emission_standard", "euro_norm", "standard"],
    "Vehicle_Age_years":  ["age", "vehicle_age", "age_years", "bus_age", "years_old"],
    "AC_Status":          ["ac", "air_conditioning", "aircon", "has_ac", "ac_on"],
    "Num_Trips_Today":    ["trips", "daily_trips", "trips_today", "num_trips", "trip_count"],
    "Engine_Model":       ["engine", "motor", "engine_type", "engine_name", "powerunit"],
}


class UploadError(ValueError):
    """Raised for user-facing upload/parse problems (bad file, too big, missing columns)."""


def _normalise(s):
    return re.sub(r"[\s\-/]", "_", str(s)).lower().strip("_")


def fuzzy_rename(df: pd.DataFrame, required: list, optional: list) -> tuple[pd.DataFrame, dict, list]:
    """Column-order-independent loader with fuzzy name matching.
    Returns (renamed_df, auto_renames_dict, still_missing_list)."""
    csv_cols = list(df.columns)
    norm_map = {_normalise(c): c for c in csv_cols}
    rename_map, auto_log = {}, {}

    for target in (required + optional):
        if target in csv_cols:
            continue
        norm_target = _normalise(target)
        matched = None
        if norm_target in norm_map:
            matched = norm_map[norm_target]
        if not matched:
            for alias in ALIASES.get(target, []):
                if alias in norm_map:
                    matched = norm_map[alias]
                    break
        if not matched:
            kw = norm_target.split("_")[0]
            for nc, oc in norm_map.items():
                if kw in nc or nc in norm_target:
                    matched = oc
                    break
        if matched and matched not in rename_map:
            rename_map[matched] = target
            auto_log[target] = matched

    df = df.rename(columns=rename_map)
    still_missing = [c for c in required if c not in df.columns]
    return df, auto_log, still_missing


def read_raw_file(name: str, fbytes: bytes, max_upload_mb: int, max_rows: int) -> pd.DataFrame:
    """Read one uploaded file (CSV or Excel) into a raw DataFrame, with
    size and row-count guards the original Streamlit app didn't have."""
    size_mb = len(fbytes) / (1024 * 1024)
    if size_mb > max_upload_mb:
        raise UploadError(f"'{name}' is {size_mb:.1f} MB, over the {max_upload_mb} MB limit.")

    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if ext in ("xlsx", "xls"):
        try:
            df = pd.read_excel(io.BytesIO(fbytes), sheet_name=0)
        except Exception as e:
            raise UploadError(f"Could not read Excel file ({e.__class__.__name__})") from e
    else:
        df = None
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(io.BytesIO(fbytes), encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            raise UploadError("Could not decode CSV (tried UTF-8, Latin-1, CP1252)")

    if len(df) > max_rows:
        raise UploadError(f"'{name}' has {len(df):,} rows, over the {max_rows:,} row limit.")

    df.columns = [str(c).lstrip("﻿").strip() for c in df.columns]
    return df


CAT_MAP = {
    "hc": "High Capacity", "high capacity": "High Capacity",
    "midi": "Midi", "mid": "Midi",
    "mini": "Mini",
    "flm": "Mini", "flm x30l": "Mini", "x30l": "Mini",
}
FUEL_MAP = {
    "pms": "Petrol", "petrol": "Petrol", "gasoline": "Petrol",
    "diesel": "Diesel", "cng": "CNG", "electric": "Electric",
    "ev": "Electric", "biogas": "Biogas", "hybrid": "Hybrid",
}


def clean_and_calculate(df: pd.DataFrame, method: str, pollutants: list[str],
                         ambient: float, basis: str) -> pd.DataFrame:
    """Shared pipeline: normalise a raw manifest DataFrame (from uploads
    OR the database) and run the emissions engine over it. Unchanged
    logic from app.py:_clean_and_calculate."""
    if "Operator" in df.columns:
        df["Operator"] = df["Operator"].astype(str).str.strip()

    if "Date" in df.columns:
        parsed = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        if parsed.isna().mean() > 0.5:
            parsed = pd.to_datetime(df["Date"], errors="coerce")
        df["Date"] = parsed.dt.date
        df["Month"] = parsed.dt.strftime("%b %Y")

    if "Revenue_Trip" in df.columns:
        sample = pd.to_numeric(df["Revenue_Trip"].iloc[:20], errors="coerce").dropna()
        if len(sample) > 0 and sample.mean() > 10:
            numeric_rev = pd.to_numeric(df["Revenue_Trip"], errors="coerce").fillna(0)
            if "Revenue_Naira" not in df.columns:
                df = df.rename(columns={"Revenue_Trip": "Revenue_Naira"})
            df["Revenue_Trip"] = numeric_rev > 0
        else:
            df["Revenue_Trip"] = df["Revenue_Trip"].astype(str).str.lower().isin(["true", "1", "yes", "t"])

    if "Bus_Category" in df.columns:
        raw_cat = df["Bus_Category"].astype(str).str.strip()
        is_unmapped = ~raw_cat.str.lower().isin(CAT_MAP.keys())
        df["Category_Unmapped"] = is_unmapped
        df["Bus_Category"] = raw_cat.str.lower().map(CAT_MAP)
        df.loc[is_unmapped, "Bus_Category"] = raw_cat[is_unmapped]

    if "Fuel_Type" in df.columns:
        raw_fuel = df["Fuel_Type"].astype(str).str.strip()
        df["Fuel_Unmapped"] = ~raw_fuel.str.lower().isin(FUEL_MAP.keys())
        df["Fuel_Type"] = raw_fuel.str.lower().map(
            lambda x: FUEL_MAP.get(x, str(x).title()) if pd.notna(x) else "Unknown")

    if "Num_Trips_Today" in df.columns:
        df["Num_Trips_Today"] = pd.to_numeric(df["Num_Trips_Today"], errors="coerce") \
            .fillna(1).clip(lower=0).round().astype(int)
        df["Num_Trips_Today"] = df["Num_Trips_Today"].replace(0, 1)

    for col in ["Route_Distance_km", "Avg_Speed_kmh", "Ridership", "Vehicle_Age_years"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    defaults = {
        "Euro_Standard": "Euro III", "Vehicle_Age_years": 5,
        "AC_Status": False, "Num_Trips_Today": 6, "Engine_Model": "",
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    results = df.apply(lambda r: calculate_row(r, method, pollutants, ambient), axis=1)
    df = pd.concat([df, results], axis=1)

    if basis == "vehicle":
        for p in ("CO2", "NOx", "PM"):
            if f"{p}_g_km" in df.columns:
                df[f"{p}_g_pkm"] = df[f"{p}_g_km"]

    if "CO2" in pollutants:
        df["Compliance"] = df.apply(
            lambda r: compliance_flag(r.get("CO2_g_pkm"), r["Bus_Category"], basis), axis=1)
    else:
        df["Compliance"] = "N/A"

    return df
