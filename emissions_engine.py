"""
LAMATA Emissions Engine v3
==========================
New in v3:
  - Euro Standard branching: separate NOx/PM factors per Euro class
  - Vehicle age deterioration multiplier (COPERT degradation model)
  - A/C status flag: actual per-trip A/C uplift vs assumed always-on
  - Num_Trips_Today: distributes cold-start penalty across correct trip count
  - Engine model lookup: fine-grained base CO2 correction by engine family

Methodology:
  CO2  — IPCC Tier 2 stoichiometric (g/km), corrected for age + AC + load
  NOx  — COPERT V speed-band function × Euro class factor × age deterioration
  PM   — COPERT V speed-band function × Euro class factor × age deterioration
  Cold start — EMEP/EEA Guidebook Table 3-27
  Idling     — fuel-burn at idle RPM × idle minutes
  Electric   — Scope 2 only: kWh/km × Nigeria grid EF (IEA 2023: 0.46 kg/kWh)
"""

import pandas as pd

# ──────────────────────────────────────────────────────────────
# SECTION 1: BASE EMISSION FACTORS (g/km at reference speed ~50 km/h)
# Source: IPCC 2006 Tier 2 + COPERT V West-Africa fleet calibration
# These are the Euro III reference factors; all other Euro classes
# are expressed as multipliers in EURO_FACTORS below.
# ──────────────────────────────────────────────────────────────
BASE_FACTORS = {
    "High Capacity": {
        "Diesel":   {"CO2": 1320.0, "NOx": 14.5, "PM": 0.28, "capacity": 150},
        "CNG":      {"CO2":  980.0, "NOx":  5.2,  "PM": 0.03, "capacity": 150},
        "Electric": {"CO2":    0.0, "NOx":  0.0,  "PM": 0.0,  "capacity": 150, "kwh_per_km": 2.1},
        "Biogas":   {"CO2":  110.0, "NOx":  4.8,  "PM": 0.03, "capacity": 150},
    },
    "Midi": {
        "Diesel":   {"CO2":  860.0, "NOx":  8.8,  "PM": 0.18, "capacity": 80},
        "CNG":      {"CO2":  640.0, "NOx":  3.1,  "PM": 0.02, "capacity": 80},
        "Electric": {"CO2":    0.0, "NOx":  0.0,  "PM": 0.0,  "capacity": 80,  "kwh_per_km": 1.2},
        "Hybrid":   {"CO2":  520.0, "NOx":  4.5,  "PM": 0.09, "capacity": 80},
    },
    "Mini": {
        "Petrol":   {"CO2":  400.0, "NOx":  0.9,  "PM": 0.012, "capacity": 18},
        "Diesel":   {"CO2":  450.0, "NOx":  2.8,  "PM": 0.06,  "capacity": 18},
        "CNG":      {"CO2":  300.0, "NOx":  0.6,  "PM": 0.003, "capacity": 18},
    },
}
FALLBACK_FACTORS = {"CO2": 1100.0, "NOx": 7.0, "PM": 0.15, "capacity": 80}

# ──────────────────────────────────────────────────────────────
# SECTION 1b: RAW DATA NORMALIZATION
# Real LAMATA export data uses operational codes/labels that don't
# match the engine's canonical category/fuel keys. These aliases
# map raw values onto the canonical keys used by BASE_FACTORS so
# rows don't silently fall through to FALLBACK_FACTORS.
# "Unknown" is intentionally NOT aliased — it is flagged instead
# of guessed, since fleet category materially changes the result.
# ──────────────────────────────────────────────────────────────
CATEGORY_ALIASES = {
    "HC":            "High Capacity",
    "High Capacity": "High Capacity",
    "Midi":          "Midi",
    "Mini":          "Mini",
    "FLM":           "Mini",   # feeder/last-mile — small bus
    "FLM X30L":      "Mini",
}

FUEL_ALIASES = {
    "Diesel":   "Diesel",
    "PMS":      "Petrol",      # Nigerian term for petrol/gasoline
    "Petrol":   "Petrol",
    "CNG":      "CNG",
    "Electric": "Electric",
    "Biogas":   "Biogas",
    "Hybrid":   "Hybrid",
}


def normalize_category(raw: str) -> tuple:
    """Returns (canonical_category, was_mapped: bool).
    Unmapped/unknown values pass through unchanged with was_mapped=False
    so callers can flag them instead of silently using fallback factors."""
    raw = str(raw).strip()
    mapped = CATEGORY_ALIASES.get(raw)
    if mapped is not None:
        return mapped, True
    return raw, False


def normalize_fuel(raw: str) -> tuple:
    """Returns (canonical_fuel, was_mapped: bool)."""
    raw = str(raw).strip()
    mapped = FUEL_ALIASES.get(raw)
    if mapped is not None:
        return mapped, True
    return raw, False


def parse_revenue_trip(raw) -> bool:
    """Revenue_Trip in real exports is fare revenue in Naira (e.g. 325080),
    not a boolean. Any positive numeric value = a revenue-generating trip.
    Still accepts True/False/1/0/yes/no for backward compatibility with
    older or synthetic test data."""
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no", "", "nan", "none"):
        return False
    try:
        return float(raw) > 0
    except (TypeError, ValueError):
        return False

# ──────────────────────────────────────────────────────────────
# SECTION 2: EURO CLASS MULTIPLIERS
# Applied to NOx and PM (not CO2 — Euro class mainly affects
# after-treatment, not thermodynamic carbon output).
# Source: EEA COPERT V Technical Report No 12 (Table 4.1)
# Euro II is reference at 1.0 here; Euro III is real-world slightly above.
# ──────────────────────────────────────────────────────────────
EURO_FACTORS = {
    # standard: {NOx_mult, PM_mult}
    "Euro II":  {"NOx": 1.30, "PM": 1.45},
    "Euro III": {"NOx": 1.00, "PM": 1.00},   # reference (our base factors)
    "Euro IV":  {"NOx": 0.55, "PM": 0.45},
    "Euro V":   {"NOx": 0.30, "PM": 0.25},
    "Euro VI":  {"NOx": 0.05, "PM": 0.04},
}
DEFAULT_EURO = "Euro III"

# ──────────────────────────────────────────────────────────────
# SECTION 3: ENGINE MODEL CO2 CORRECTION
# Fine-grained multiplier on base CO2 (g/km).
# Values reflect published fuel consumption data and fleet
# operator experience for Lagos conditions.
# ──────────────────────────────────────────────────────────────
ENGINE_CO2_CORRECTION = {
    "Yuchai YC6K":   1.04,   # older Chinese unit, slightly thirstier
    "Weichai WP7":   0.97,   # modern common-rail, good efficiency
    "Cummins ISB":   1.01,
    "Yuchai YC4G":   0.99,
    "Toyota 2TR":    0.95,   # small petrol, efficient for Mini class
    "Toyota 1HZ":    1.02,
    "Yuchai YC4D":   0.98,
    "BYD D9":        1.00,   # electric — correction handled via kWh
    "Higer KLQ6125": 1.00,   # electric
    "Scania OC9":    0.93,   # premium European engine, best in class
}
DEFAULT_ENGINE_CORRECTION = 1.00

# ──────────────────────────────────────────────────────────────
# SECTION 4: AGE DETERIORATION MULTIPLIERS
# Real-world EFs rise as engine and after-treatment age.
# CO2: +0.4%/year (COPERT degradation model)
# NOx: +1.5%/year for diesel, +0.8%/year for CNG
# PM:  +2.0%/year for diesel, +0.5%/year for CNG
# ──────────────────────────────────────────────────────────────
def age_deterioration(age_years: int, fuel_type: str) -> dict:
    age = max(0, min(age_years, 20))
    co2_rate  = 0.004
    nox_rate  = 0.015 if fuel_type in ("Diesel", "Petrol") else 0.008
    pm_rate   = 0.020 if fuel_type in ("Diesel", "Petrol") else 0.005
    return {
        "CO2": 1.0 + co2_rate * age,
        "NOx": 1.0 + nox_rate * age,
        "PM":  1.0 + pm_rate  * age,
    }

# ──────────────────────────────────────────────────────────────
# SECTION 5: A/C UPLIFT
# Per-trip: applied only when AC_Status is True.
# Lagos ambient ~32°C average — A/C load is significant.
# CARB 2021: 8% CO2 uplift for heavy-duty buses in warm climates.
# ──────────────────────────────────────────────────────────────
AC_UPLIFT_CO2 = 0.08

# ──────────────────────────────────────────────────────────────
# SECTION 6: COLD START
# Penalty applied to the first COLD_START_KM of EACH trip.
# With Num_Trips_Today we can scale total daily cold-start correctly.
# Source: EMEP/EEA Guidebook Table 3-27
# ──────────────────────────────────────────────────────────────
COLD_START_KM = 5.0
COLD_START_MULT = {"CO2": 1.18, "NOx": 2.8, "PM": 3.2}

# ──────────────────────────────────────────────────────────────
# SECTION 7: IDLING FACTORS (g CO2/min at idle)
# ──────────────────────────────────────────────────────────────
IDLING_EF = {
    "High Capacity": {
        "Diesel": {"CO2": 28.0, "NOx": 0.22, "PM": 0.006},
        "CNG":    {"CO2": 20.0, "NOx": 0.08, "PM": 0.001},
        "Biogas": {"CO2":  3.5, "NOx": 0.07, "PM": 0.001},
    },
    "Midi": {
        "Diesel": {"CO2": 18.0, "NOx": 0.14, "PM": 0.004},
        "CNG":    {"CO2": 12.0, "NOx": 0.05, "PM": 0.0005},
    },
    "Mini": {
        "Petrol": {"CO2":  9.0, "NOx": 0.03, "PM": 0.0005},
        "Diesel": {"CO2": 10.0, "NOx": 0.07, "PM": 0.002},
        "CNG":    {"CO2":  6.5, "NOx": 0.02, "PM": 0.0002},
    },
}
DEFAULT_IDLE_MINUTES = 10

# Grid emission factor — Nigeria (IEA 2023 regional estimate)
GRID_EF_KG_PER_KWH = 0.46

# ──────────────────────────────────────────────────────────────
# SECTION 8: SPEED-CORRECTION FUNCTIONS (COPERT V)
# ──────────────────────────────────────────────────────────────
def _spd_co2(s):
    if s <= 0: return 3.0
    s = max(5.0, min(s, 100.0))
    return 0.4 + 53.0 / s + s / 180.0

def _spd_nox(s):
    if s <= 0: return 2.5
    s = max(5.0, min(s, 100.0))
    return 0.85 + s / 90.0

def _spd_pm(s):
    if s <= 0: return 4.0
    s = max(5.0, min(s, 100.0))
    return max(0.6, 4.5 - s / 20.0)

SPD_FN = {"CO2": _spd_co2, "NOx": _spd_nox, "PM": _spd_pm}

# ──────────────────────────────────────────────────────────────
# SECTION 9: LOAD FACTOR VEHICLE-LEVEL CORRECTION
# ──────────────────────────────────────────────────────────────
def _load_corr(ridership, capacity):
    if capacity <= 0: return 1.0
    ratio = min(ridership / capacity, 1.2)
    return 1.0 + (ratio - 0.5) * 0.05

# ──────────────────────────────────────────────────────────────
# SECTION 10: MAIN ROW CALCULATOR
# ──────────────────────────────────────────────────────────────
def calculate_row(row, methodology: str, target_pollutants: list) -> pd.Series:
    bus_cat_raw  = str(row.get("Bus_Category", "")).strip()
    fuel_raw     = str(row.get("Fuel_Type", "")).strip()
    bus_cat, cat_mapped   = normalize_category(bus_cat_raw)
    fuel, fuel_mapped     = normalize_fuel(fuel_raw)
    distance     = float(row.get("Route_Distance_km", 0) or 0)
    speed        = float(row.get("Avg_Speed_kmh", 25) or 25)
    ridership    = max(1, int(row.get("Ridership", 1) or 1))
    is_revenue   = parse_revenue_trip(row.get("Revenue_Trip", "True"))
    euro         = str(row.get("Euro_Standard", DEFAULT_EURO)).strip()
    age          = int(row.get("Vehicle_Age_years", 0) or 0)
    ac_on        = str(row.get("AC_Status", "True")).strip().lower() in ("true", "1", "yes")
    num_trips    = max(1, int(row.get("Num_Trips_Today", 1) or 1))
    engine_model = str(row.get("Engine_Model", "")).strip()
    idle_minutes = float(row.get("Idle_Minutes", DEFAULT_IDLE_MINUTES))

    cat_data     = BASE_FACTORS.get(bus_cat, {})
    fuel_profile = cat_data.get(fuel, FALLBACK_FACTORS)
    capacity     = int(fuel_profile.get("capacity", 80))
    euro_mults   = EURO_FACTORS.get(euro, EURO_FACTORS[DEFAULT_EURO])
    age_mults    = age_deterioration(age, fuel)
    eng_corr     = ENGINE_CO2_CORRECTION.get(engine_model, DEFAULT_ENGINE_CORRECTION)
    load_c       = _load_corr(ridership, capacity)

    # ── Electric: Scope 2 only ──
    if fuel == "Electric":
        kwh_per_km = float(fuel_profile.get("kwh_per_km", 1.5))
        co2_kg = kwh_per_km * distance * GRID_EF_KG_PER_KWH if "CO2" in target_pollutants else 0.0
        return pd.Series({
            "CO2_kg":        round(co2_kg, 4),
            "NOx_kg":        0.0,
            "PM_kg":         0.0,
            "CO2_g_pkm":     round(co2_kg * 1000 / ridership, 2) if is_revenue else 0.0,
            "NOx_g_pkm":     0.0,
            "PM_g_pkm":      0.0,
            "load_factor":   round(ridership / capacity, 3),
            "euro_nox_mult": 0.0,
            "age_co2_mult":  1.0,
            "ac_uplift_kg":  0.0,
            "category_unmapped": not cat_mapped,
            "fuel_unmapped":     not fuel_mapped,
        })

    results = {}
    ac_uplift_kg = 0.0

    for pol in ["CO2", "NOx", "PM"]:
        base_ef = float(fuel_profile.get(pol, 0.0))
        if pol not in target_pollutants or base_ef == 0.0:
            results[f"{pol}_kg"]    = 0.0
            results[f"{pol}_g_pkm"] = 0.0
            continue

        # ── Apply Euro class (NOx, PM only) ──
        if pol in ("NOx", "PM"):
            base_ef *= euro_mults.get(pol, 1.0)

        # ── Apply engine model CO2 correction ──
        if pol == "CO2":
            base_ef *= eng_corr

        # ── Apply age deterioration ──
        base_ef *= age_mults.get(pol, 1.0)

        # ── Hot running ──
        if methodology == "IPCC":
            hot_g = base_ef * distance
        elif methodology == "COPERT":
            hot_g = base_ef * SPD_FN[pol](speed) * distance
        else:  # Hybrid
            if pol == "CO2":
                hot_g = base_ef * distance
            else:
                hot_g = base_ef * SPD_FN[pol](speed) * distance

        # ── Cold start (per trip, scaled by num_trips) ──
        cold_km    = min(distance, COLD_START_KM)
        cold_extra = base_ef * cold_km * (COLD_START_MULT.get(pol, 1.0) - 1.0) * num_trips

        # ── Idling ──
        idle_ef = IDLING_EF.get(bus_cat, {}).get(fuel, {}).get(pol, 0.0)
        idle_g  = idle_ef * idle_minutes

        # ── A/C uplift (CO2 only, conditional on AC_Status) ──
        ac_extra = (hot_g * AC_UPLIFT_CO2) if (pol == "CO2" and ac_on) else 0.0
        if pol == "CO2":
            ac_uplift_kg = ac_extra / 1000.0

        total_g = (hot_g + cold_extra + idle_g + ac_extra) * load_c
        results[f"{pol}_kg"]    = round(total_g / 1000.0, 4)
        results[f"{pol}_g_pkm"] = round(total_g / ridership, 2) if is_revenue else 0.0

    results["load_factor"]    = round(ridership / capacity, 3)
    results["euro_nox_mult"]  = euro_mults.get("NOx", 1.0)
    results["age_co2_mult"]   = round(age_mults["CO2"], 3)
    results["ac_uplift_kg"]   = round(ac_uplift_kg, 4)
    results["category_unmapped"] = not cat_mapped
    results["fuel_unmapped"]     = not fuel_mapped
    return pd.Series(results)


# ──────────────────────────────────────────────────────────────
# SECTION 11: SINGLE-TRIP BREAKDOWN (for Trip Inspector)
# ──────────────────────────────────────────────────────────────
def emission_breakdown(row, methodology="Hybrid") -> dict:
    bus_cat, _  = normalize_category(str(row.get("Bus_Category", "")).strip())
    fuel, _     = normalize_fuel(str(row.get("Fuel_Type",    "")).strip())
    distance = float(row.get("Route_Distance_km", 0) or 0)
    speed    = float(row.get("Avg_Speed_kmh", 25) or 25)
    ridership = max(1, int(row.get("Ridership", 1) or 1))
    idle_min = float(row.get("Idle_Minutes", DEFAULT_IDLE_MINUTES))
    euro     = str(row.get("Euro_Standard", DEFAULT_EURO)).strip()
    age      = int(row.get("Vehicle_Age_years", 0) or 0)
    ac_on    = str(row.get("AC_Status", "True")).strip().lower() in ("true", "1", "yes")
    num_trips = max(1, int(row.get("Num_Trips_Today", 1) or 1))
    engine   = str(row.get("Engine_Model", "")).strip()

    cat_data     = BASE_FACTORS.get(bus_cat, {})
    fuel_profile = cat_data.get(fuel, FALLBACK_FACTORS)
    euro_mults   = EURO_FACTORS.get(euro, EURO_FACTORS[DEFAULT_EURO])
    age_mults    = age_deterioration(age, fuel)
    eng_corr     = ENGINE_CO2_CORRECTION.get(engine, DEFAULT_ENGINE_CORRECTION)

    if fuel == "Electric":
        kwh   = fuel_profile.get("kwh_per_km", 1.5) * distance
        total = kwh * GRID_EF_KG_PER_KWH * 1000
        return {"hot_running": 0, "cold_start": 0, "idling": 0, "ac_load": 0,
                "grid_electric": round(total, 1), "total_g": round(total, 1)}

    base_ef = float(fuel_profile.get("CO2", 0.0)) * eng_corr * age_mults["CO2"]

    if methodology == "COPERT":
        hot_g = base_ef * SPD_FN["CO2"](speed) * distance
    else:
        hot_g = base_ef * distance

    cold_km    = min(distance, COLD_START_KM)
    cold_extra = base_ef * cold_km * (COLD_START_MULT["CO2"] - 1.0) * num_trips
    idle_ef    = IDLING_EF.get(bus_cat, {}).get(fuel, {}).get("CO2", 0.0)
    idle_g     = idle_ef * idle_min
    ac_extra   = hot_g * AC_UPLIFT_CO2 if ac_on else 0.0

    return {
        "hot_running":   round(hot_g, 1),
        "cold_start":    round(cold_extra, 1),
        "idling":        round(idle_g, 1),
        "ac_load":       round(ac_extra, 1),
        "grid_electric": 0,
        "total_g":       round(hot_g + cold_extra + idle_g + ac_extra, 1),
    }


# ──────────────────────────────────────────────────────────────
# SECTION 12: COMPLIANCE FLAG
# ──────────────────────────────────────────────────────────────
def compliance_flag(co2_g_pkm: float, bus_category: str) -> str:
    T = {
        "High Capacity": {"good": 30, "monitor": 55},
        "Midi":          {"good": 45, "monitor": 75},
        "Mini":          {"good": 60, "monitor": 95},
    }
    t = T.get(bus_category, {"good": 40, "monitor": 70})
    if co2_g_pkm <= t["good"]:    return "Good"
    if co2_g_pkm <= t["monitor"]: return "Monitor"
    return "Over Limit"
