"""
LAMATA Emissions Engine v4
==========================
Written to be READABLE first. Every step is plain arithmetic:

    total emissions  =  hot running  +  cold start  +  idling  +  A/C load

and every correction is a simple multiplier on a base factor.

──────────────────────────────────────────────────────────────
HOW A ROW IS READ  (important!)
──────────────────────────────────────────────────────────────
One row in the manifest = ONE BUS on ONE DAY.

    Route_Distance_km   → km the bus drove that day  (see DISTANCE_IS_DAILY_TOTAL)
    Num_Trips_Today     → trips completed that day
    Ridership           → passengers carried that day (all trips added up)

From those we derive:

    daily_km      = Route_Distance_km                  (default assumption)
    trip_km       = daily_km / Num_Trips_Today         (length of one trip)
    pax_per_trip  = Ridership / Num_Trips_Today        (people on board at once)
    passenger_km  = Ridership × trip_km                (each rider rides one trip)

Two efficiency views come out of every row:

    g/km   (vehicle view)   = total grams ÷ daily_km
    g/pkm  (passenger view) = total grams ÷ passenger_km

──────────────────────────────────────────────────────────────
METHODOLOGIES
──────────────────────────────────────────────────────────────
    IPCC    — flat emission factor × distance (no speed effect)
    COPERT  — factor × speed correction × distance (all pollutants)
    Hybrid  — CO₂ flat (IPCC style), NOx & PM speed-corrected (COPERT style)

The speed curves are NORMALISED: at the 50 km/h reference speed the
correction is exactly 1.0, so COPERT and IPCC agree at reference speed
and only diverge in congestion (slow) or free-flow (fast) conditions.
(v3 was missing this normalisation — it inflated COPERT results ~1.7×.)

Sources: IPCC 2006 Tier 2 base factors · EMEP/EEA Guidebook 2019 curve
shapes for urban buses · IEA 2023 Nigeria grid factor.
"""

import pandas as pd

# ══════════════════════════════════════════════════════════════
# SECTION 1 — BASE EMISSION FACTORS
# Grams emitted per km, for a Euro III vehicle at 50 km/h.
# Everything else in this file is a multiplier on these numbers.
# ══════════════════════════════════════════════════════════════
BASE_FACTORS = {
    "High Capacity": {
        "Diesel":   {"CO2": 1320.0, "NOx": 14.5, "PM": 0.28,  "capacity": 150},
        "CNG":      {"CO2":  980.0, "NOx":  5.2, "PM": 0.03,  "capacity": 150},
        "Electric": {"CO2":    0.0, "NOx":  0.0, "PM": 0.0,   "capacity": 150, "kwh_per_km": 2.1},
        "Biogas":   {"CO2":  110.0, "NOx":  4.8, "PM": 0.03,  "capacity": 150},
        "Petrol":   {"CO2": 1450.0, "NOx":  4.0, "PM": 0.05,  "capacity": 150},
    },
    "Midi": {
        "Diesel":   {"CO2":  860.0, "NOx":  8.8, "PM": 0.18,  "capacity": 80},
        "CNG":      {"CO2":  640.0, "NOx":  3.1, "PM": 0.02,  "capacity": 80},
        "Electric": {"CO2":    0.0, "NOx":  0.0, "PM": 0.0,   "capacity": 80,  "kwh_per_km": 1.2},
        "Hybrid":   {"CO2":  520.0, "NOx":  4.5, "PM": 0.09,  "capacity": 80},
    },
    "Mini": {
        "Petrol":   {"CO2":  400.0, "NOx":  0.9, "PM": 0.012, "capacity": 18},
        "Diesel":   {"CO2":  450.0, "NOx":  2.8, "PM": 0.06,  "capacity": 18},
        "CNG":      {"CO2":  300.0, "NOx":  0.6, "PM": 0.003, "capacity": 18},
    },
}
# Used when a row's category/fuel combination is unknown:
FALLBACK_FACTORS = {"CO2": 1100.0, "NOx": 7.0, "PM": 0.15, "capacity": 80}

# ══════════════════════════════════════════════════════════════
# SECTION 1b — RAW DATA NORMALISATION
# Real exports say "HC", "PMS", etc. Map them onto the canonical
# keys above. "Unknown" is deliberately NOT mapped — it gets
# flagged instead of guessed.
# ══════════════════════════════════════════════════════════════
CATEGORY_ALIASES = {
    "HC": "High Capacity", "High Capacity": "High Capacity",
    "MIDI": "Midi", "Midi": "Midi", "Mid": "Midi",
    "MINI": "Mini", "Mini": "Mini",
    "FLM": "Mini", "X30L": "Mini", "FLM X30L": "Mini",
}
FUEL_ALIASES = {
    "PMS": "Petrol", "Petrol": "Petrol", "Gasoline": "Petrol",
    "Diesel": "Diesel", "AGO": "Diesel",
    "CNG": "CNG", "Electric": "Electric", "EV": "Electric",
    "Biogas": "Biogas", "Hybrid": "Hybrid",
}


def normalize_category(raw):
    """Returns (canonical_category, was_mapped)."""
    raw = str(raw).strip()
    if raw in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[raw], True
    return raw, False


def normalize_fuel(raw):
    """Returns (canonical_fuel, was_mapped)."""
    raw = str(raw).strip()
    if raw in FUEL_ALIASES:
        return FUEL_ALIASES[raw], True
    return raw, False


def parse_revenue_trip(raw):
    """Revenue_Trip in real exports is fare revenue in Naira (e.g. 325080).
    Any positive number = a revenue trip. Also accepts True/False text."""
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no", "", "nan", "none"):
        return False
    try:
        return float(raw) > 0
    except (TypeError, ValueError):
        return False


# ══════════════════════════════════════════════════════════════
# SECTION 2 — EURO CLASS MULTIPLIERS  (NOx and PM only)
# Euro standards regulate after-treatment (catalysts, filters),
# which cuts NOx/PM — but NOT CO₂, which comes from burning fuel.
# Euro III = 1.0 because the base factors above are Euro III.
# Source: EEA COPERT V real-world factor ratios.
# ══════════════════════════════════════════════════════════════
EURO_FACTORS = {
    "Euro II":  {"NOx": 1.30, "PM": 1.45},
    "Euro III": {"NOx": 1.00, "PM": 1.00},   # ← reference
    "Euro IV":  {"NOx": 0.55, "PM": 0.45},
    "Euro V":   {"NOx": 0.30, "PM": 0.25},
    "Euro VI":  {"NOx": 0.05, "PM": 0.04},
}
DEFAULT_EURO = "Euro III"

# ══════════════════════════════════════════════════════════════
# SECTION 3 — ENGINE MODEL CO₂ CORRECTION
# Small multiplier for known engine families (fuel-efficiency
# differences observed in operator fuel records).
# ══════════════════════════════════════════════════════════════
ENGINE_CO2_CORRECTION = {
    "Yuchai YC6K": 1.04, "Weichai WP7": 0.97, "Cummins ISB": 1.01,
    "Yuchai YC4G": 0.99, "Toyota 2TR": 0.95, "Toyota 1HZ": 1.02,
    "Yuchai YC4D": 0.98, "BYD D9": 1.00, "Higer KLQ6125": 1.00,
    "Scania OC9": 0.93,
}
DEFAULT_ENGINE_CORRECTION = 1.00


# ══════════════════════════════════════════════════════════════
# SECTION 4 — AGE DETERIORATION
# Older engines and worn after-treatment emit more per km.
#   NOx: +1.5 %/year (diesel/petrol), +0.8 %/year (gas fuels)
#   PM : +2.0 %/year (diesel/petrol), +0.5 %/year (gas fuels)
#   CO₂: +0.4 %/year — a fuel-economy-ageing assumption, NOT a
#        COPERT rule (COPERT degrades CO/HC/NOx only). Set
#        CO2_AGEING_PER_YEAR = 0.0 to switch it off.
# ══════════════════════════════════════════════════════════════
CO2_AGEING_PER_YEAR = 0.004


def age_deterioration(age_years, fuel_type):
    """Returns {'CO2': x, 'NOx': y, 'PM': z} multipliers, capped at 20 yrs."""
    age = max(0, min(int(age_years), 20))
    nox_rate = 0.015 if fuel_type in ("Diesel", "Petrol") else 0.008
    pm_rate  = 0.020 if fuel_type in ("Diesel", "Petrol") else 0.005
    return {
        "CO2": 1.0 + CO2_AGEING_PER_YEAR * age,
        "NOx": 1.0 + nox_rate * age,
        "PM":  1.0 + pm_rate * age,
    }


# ══════════════════════════════════════════════════════════════
# SECTION 5 — SPEED CORRECTION  (the COPERT part)
# Buses emit MORE per km when crawling in traffic (engine runs
# longer per km, stop-and-go) and slightly less in free flow.
# Curve shape: 1 + K/V — the classic "congestion penalty" shape
# from the EMEP/EEA urban-bus curves, then NORMALISED so the
# multiplier is exactly 1.0 at REF_SPEED_KMH.
#
#   speed_factor = raw(V) / raw(50)
#
# Example (CO₂): 10 km/h → ×2.17   ·   50 km/h → ×1.00   ·   80 km/h → ×0.93
# ══════════════════════════════════════════════════════════════
REF_SPEED_KMH = 50.0
SPEED_MIN, SPEED_MAX = 5.0, 85.0          # curves valid in this range

_CONGESTION_K = {"CO2": 25.0, "NOx": 18.0, "PM": 30.0}
_FREEFLOW_SLOPE = {"CO2": 1 / 400.0, "NOx": 0.0, "PM": 0.0}


def _raw_curve(pollutant, v):
    """Un-normalised emission-vs-speed shape."""
    k = _CONGESTION_K[pollutant]
    m = _FREEFLOW_SLOPE[pollutant]
    return 1.0 + k / v + m * v


def speed_factor(pollutant, speed_kmh):
    """Multiplier on the base factor for a given average speed.
    Equals 1.0 at 50 km/h by construction."""
    v = max(SPEED_MIN, min(float(speed_kmh or REF_SPEED_KMH), SPEED_MAX))
    return _raw_curve(pollutant, v) / _raw_curve(pollutant, REF_SPEED_KMH)


# Backward-compatible helpers (used by the Formula Explainer):
def _spd_co2(s): return speed_factor("CO2", s)
def _spd_nox(s): return speed_factor("NOx", s)
def _spd_pm(s):  return speed_factor("PM", s)
SPD_FN = {"CO2": _spd_co2, "NOx": _spd_nox, "PM": _spd_pm}


# ══════════════════════════════════════════════════════════════
# SECTION 6 — COLD START  (temperature-aware)
# A cold engine over-emits for the first few km. Buses running
# trips back-to-back stay warm, so we count COLD STARTS PER DAY
# (default 1 — the morning start), NOT one per trip.
#
# The penalty shrinks with ambient temperature and disappears at
# 30 °C. In Lagos (~28 °C) it is small — as it should be.
#
#   chill  = max(0, (30 − ambient) / 30)        0 at 30°C, 1 at 0°C
#   mult   = 1 + (mult_at_0°C − 1) × chill
#   extra  = EF × cold_km × (mult − 1) × starts_per_day
# ══════════════════════════════════════════════════════════════
COLD_STARTS_PER_DAY = 1
COLD_START_KM = 5.0                        # distance driven "cold"
COLD_START_MULT_AT_0C = {"CO2": 1.25, "NOx": 2.8, "PM": 3.2}
COLD_START_MULT = COLD_START_MULT_AT_0C    # legacy alias
DEFAULT_AMBIENT_C = 28.0                   # Lagos average


def cold_start_multiplier(pollutant, ambient_c=DEFAULT_AMBIENT_C):
    """Cold-start over-emission multiplier at a given ambient temp."""
    chill = max(0.0, (30.0 - float(ambient_c)) / 30.0)
    return 1.0 + (COLD_START_MULT_AT_0C[pollutant] - 1.0) * chill


# ══════════════════════════════════════════════════════════════
# SECTION 7 — IDLING  (grams per minute at idle)
# Terminals, traffic lights, boarding. Multiplied by the row's
# Idle_Minutes column, or DEFAULT_IDLE_MINUTES if absent.
# ══════════════════════════════════════════════════════════════
IDLING_EF = {
    "High Capacity": {
        "Diesel": {"CO2": 28.0, "NOx": 0.22, "PM": 0.006},
        "CNG":    {"CO2": 20.0, "NOx": 0.08, "PM": 0.001},
        "Biogas": {"CO2":  3.5, "NOx": 0.07, "PM": 0.001},
        "Petrol": {"CO2": 30.0, "NOx": 0.05, "PM": 0.001},
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
DEFAULT_IDLE_MINUTES = 10.0

# ══════════════════════════════════════════════════════════════
# SECTION 8 — A/C AND ELECTRIC
# ══════════════════════════════════════════════════════════════
AC_UPLIFT_CO2 = 0.08          # +8 % CO₂ when A/C is on (hot + idle)
AC_UPLIFT_KWH = 0.10          # +10 % electricity for A/C on e-buses
GRID_EF_KG_PER_KWH = 0.46     # Nigeria grid, kg CO₂e per kWh (IEA 2023)

# ══════════════════════════════════════════════════════════════
# SECTION 9 — PASSENGER LOAD CORRECTION
# A fuller bus is heavier → burns a little more fuel. Roughly
# +8 % from empty to full for city buses (COPERT load effect).
# Uses passengers ON BOARD (per trip), not the daily total.
# ══════════════════════════════════════════════════════════════
def _load_corr(pax_on_board, capacity):
    """Multiplier: 0.96 empty · 1.00 half-full · 1.04 full."""
    if capacity <= 0:
        return 1.0
    ratio = min(pax_on_board / capacity, 1.2)
    return 1.0 + 0.08 * (ratio - 0.5)


# ══════════════════════════════════════════════════════════════
# SECTION 10 — ROW SEMANTICS SWITCH
# If your Route_Distance_km column is the length of ONE trip
# (not the whole day), set this to False — daily km then becomes
# distance × Num_Trips_Today.
# ══════════════════════════════════════════════════════════════
DISTANCE_IS_DAILY_TOTAL = True


def _derive_day(distance, num_trips, ridership):
    """Turn the raw columns into daily_km, trip_km, pax_per_trip, passenger_km."""
    num_trips = max(1, int(num_trips or 1))
    daily_km = distance if DISTANCE_IS_DAILY_TOTAL else distance * num_trips
    trip_km = daily_km / num_trips
    pax_per_trip = ridership / num_trips
    passenger_km = ridership * trip_km
    return daily_km, trip_km, pax_per_trip, passenger_km


# ══════════════════════════════════════════════════════════════
# SECTION 11 — MAIN ROW CALCULATOR
# ══════════════════════════════════════════════════════════════
def calculate_row(row, methodology, target_pollutants, ambient_c=DEFAULT_AMBIENT_C):
    """Compute one bus-day. Returns a pandas Series of results.

    Recipe per pollutant:
        EF      = base × euro × age × engine  (whichever apply)
        hot     = EF × speed_factor × daily_km     (speed only in COPERT modes)
        cold    = EF × cold_km × (cold_mult − 1) × starts_per_day
        idle    = idle_EF × idle_minutes
        A/C     = +8 % of (hot + idle) CO₂, if A/C on
        total   = (hot + cold + idle + A/C) × load_correction
    """
    # ── 1. Read the row ──
    bus_cat, cat_mapped = normalize_category(row.get("Bus_Category", ""))
    fuel, fuel_mapped   = normalize_fuel(row.get("Fuel_Type", ""))
    distance   = float(row.get("Route_Distance_km", 0) or 0)
    speed      = float(row.get("Avg_Speed_kmh", REF_SPEED_KMH) or REF_SPEED_KMH)
    ridership  = max(1, int(row.get("Ridership", 1) or 1))
    num_trips  = max(1, int(row.get("Num_Trips_Today", 1) or 1))
    euro       = str(row.get("Euro_Standard", DEFAULT_EURO)).strip()
    age        = int(row.get("Vehicle_Age_years", 0) or 0)
    ac_on      = str(row.get("AC_Status", "False")).strip().lower() in ("true", "1", "yes")
    engine     = str(row.get("Engine_Model", "")).strip()
    idle_min   = float(row.get("Idle_Minutes", DEFAULT_IDLE_MINUTES) or DEFAULT_IDLE_MINUTES)
    is_revenue = parse_revenue_trip(row.get("Revenue_Trip", "True"))
    revenue_n  = float(row.get("Revenue_Naira", 0) or 0)

    daily_km, trip_km, pax_per_trip, passenger_km = _derive_day(distance, num_trips, ridership)

    # ── 2. Look up factors and multipliers ──
    fuel_profile = BASE_FACTORS.get(bus_cat, {}).get(fuel, FALLBACK_FACTORS)
    capacity   = int(fuel_profile.get("capacity", 80))
    euro_mults = EURO_FACTORS.get(euro, EURO_FACTORS[DEFAULT_EURO])
    age_mults  = age_deterioration(age, fuel)
    eng_corr   = ENGINE_CO2_CORRECTION.get(engine, DEFAULT_ENGINE_CORRECTION)
    load_c     = _load_corr(pax_per_trip, capacity)

    out = {
        "load_factor":      round(min(pax_per_trip / capacity, 1.2), 3) if capacity else 0.0,
        "euro_nox_mult":    euro_mults["NOx"],
        "age_co2_mult":     round(age_mults["CO2"], 3),
        "category_unmapped": not cat_mapped,
        "fuel_unmapped":     not fuel_mapped,
    }

    # ── 3. Electric buses: no tailpipe — grid ("Scope 2") CO₂ only ──
    if fuel == "Electric":
        kwh_per_km = float(fuel_profile.get("kwh_per_km", 1.5))
        if ac_on:
            kwh_per_km *= (1.0 + AC_UPLIFT_KWH)
        co2_g = kwh_per_km * daily_km * GRID_EF_KG_PER_KWH * 1000.0
        co2_g = co2_g if "CO2" in target_pollutants else 0.0
        for pol, grams in (("CO2", co2_g), ("NOx", 0.0), ("PM", 0.0)):
            out[f"{pol}_kg"]    = round(grams / 1000.0, 4)
            out[f"{pol}_g_km"]  = round(grams / daily_km, 2) if daily_km else 0.0
            out[f"{pol}_g_pkm"] = round(grams / passenger_km, 2) if (is_revenue and passenger_km) else float("nan")
        out["ac_uplift_kg"] = 0.0
        out["CO2_kg_per_1000naira"] = round(out["CO2_kg"] / (revenue_n / 1000.0), 3) if revenue_n > 0 else float("nan")
        return pd.Series(out)

    # ── 4. Combustion buses: the four components, per pollutant ──
    ac_uplift_g = 0.0
    for pol in ("CO2", "NOx", "PM"):
        base_ef = float(fuel_profile.get(pol, 0.0))
        if pol not in target_pollutants or base_ef == 0.0:
            out[f"{pol}_kg"] = 0.0
            out[f"{pol}_g_km"] = 0.0
            out[f"{pol}_g_pkm"] = 0.0
            continue

        # Build the effective emission factor (g/km):
        ef = base_ef
        if pol in ("NOx", "PM"):
            ef *= euro_mults[pol]          # after-treatment quality
        if pol == "CO2":
            ef *= eng_corr                 # engine family efficiency
        ef *= age_mults[pol]               # wear and tear

        # HOT RUNNING — speed correction depends on methodology:
        use_speed = (methodology == "COPERT") or (methodology == "Hybrid" and pol != "CO2")
        hot_g = ef * (speed_factor(pol, speed) if use_speed else 1.0) * daily_km

        # COLD START — once per day, shrinks with warm ambient temp:
        cold_km = min(trip_km, COLD_START_KM)
        cold_g = ef * cold_km * (cold_start_multiplier(pol, ambient_c) - 1.0) * COLD_STARTS_PER_DAY

        # IDLING — grams/minute × minutes:
        idle_g = IDLING_EF.get(bus_cat, {}).get(fuel, {}).get(pol, 0.0) * idle_min

        # A/C — extra fuel burned to run the compressor (CO₂ only):
        ac_g = (hot_g + idle_g) * AC_UPLIFT_CO2 if (pol == "CO2" and ac_on) else 0.0
        if pol == "CO2":
            ac_uplift_g = ac_g

        total_g = (hot_g + cold_g + idle_g + ac_g) * load_c

        out[f"{pol}_kg"]    = round(total_g / 1000.0, 4)
        out[f"{pol}_g_km"]  = round(total_g / daily_km, 2) if daily_km else 0.0
        # Efficiency only makes sense for revenue service — non-revenue rows
        # get NaN so they never pollute averages or compliance:
        out[f"{pol}_g_pkm"] = round(total_g / passenger_km, 2) if (is_revenue and passenger_km) else float("nan")

    out["ac_uplift_kg"] = round(ac_uplift_g / 1000.0, 4)
    # Carbon intensity of revenue: kg CO₂ emitted per ₦1,000 earned.
    out["CO2_kg_per_1000naira"] = round(out.get("CO2_kg", 0.0) / (revenue_n / 1000.0), 3) if revenue_n > 0 else float("nan")
    return pd.Series(out)


# ══════════════════════════════════════════════════════════════
# SECTION 12 — SINGLE-TRIP CO₂ BREAKDOWN  (Trip Inspector)
# Same math as above, CO₂ only, returned as named components.
# ══════════════════════════════════════════════════════════════
def emission_breakdown(row, methodology="Hybrid", ambient_c=DEFAULT_AMBIENT_C):
    bus_cat, _ = normalize_category(row.get("Bus_Category", ""))
    fuel, _    = normalize_fuel(row.get("Fuel_Type", ""))
    distance  = float(row.get("Route_Distance_km", 0) or 0)
    speed     = float(row.get("Avg_Speed_kmh", REF_SPEED_KMH) or REF_SPEED_KMH)
    ridership = max(1, int(row.get("Ridership", 1) or 1))
    num_trips = max(1, int(row.get("Num_Trips_Today", 1) or 1))
    euro      = str(row.get("Euro_Standard", DEFAULT_EURO)).strip()
    age       = int(row.get("Vehicle_Age_years", 0) or 0)
    ac_on     = str(row.get("AC_Status", "False")).strip().lower() in ("true", "1", "yes")
    engine    = str(row.get("Engine_Model", "")).strip()
    idle_min  = float(row.get("Idle_Minutes", DEFAULT_IDLE_MINUTES) or DEFAULT_IDLE_MINUTES)

    daily_km, trip_km, _pax, _pkm = _derive_day(distance, num_trips, ridership)
    fuel_profile = BASE_FACTORS.get(bus_cat, {}).get(fuel, FALLBACK_FACTORS)

    if fuel == "Electric":
        kwh_per_km = float(fuel_profile.get("kwh_per_km", 1.5))
        if ac_on:
            kwh_per_km *= (1.0 + AC_UPLIFT_KWH)
        total = kwh_per_km * daily_km * GRID_EF_KG_PER_KWH * 1000.0
        return {"hot_running": 0, "cold_start": 0, "idling": 0, "ac_load": 0,
                "grid_electric": round(total, 1), "total_g": round(total, 1)}

    ef = (float(fuel_profile.get("CO2", 0.0))
          * ENGINE_CO2_CORRECTION.get(engine, DEFAULT_ENGINE_CORRECTION)
          * age_deterioration(age, fuel)["CO2"])

    use_speed = (methodology == "COPERT")
    hot_g  = ef * (speed_factor("CO2", speed) if use_speed else 1.0) * daily_km
    cold_g = ef * min(trip_km, COLD_START_KM) \
                * (cold_start_multiplier("CO2", ambient_c) - 1.0) * COLD_STARTS_PER_DAY
    idle_g = IDLING_EF.get(bus_cat, {}).get(fuel, {}).get("CO2", 0.0) * idle_min
    ac_g   = (hot_g + idle_g) * AC_UPLIFT_CO2 if ac_on else 0.0

    return {"hot_running": round(hot_g, 1), "cold_start": round(cold_g, 1),
            "idling": round(idle_g, 1), "ac_load": round(ac_g, 1),
            "grid_electric": 0,
            "total_g": round(hot_g + cold_g + idle_g + ac_g, 1)}


# ══════════════════════════════════════════════════════════════
# SECTION 13 — COMPLIANCE FLAG  (two bases)
#   basis="passenger" → thresholds in g CO₂ per passenger-km
#   basis="vehicle"   → thresholds in g CO₂ per vehicle-km
# ══════════════════════════════════════════════════════════════
THRESHOLDS_PKM = {   # g CO₂ / passenger-km
    "High Capacity": {"good": 30, "monitor": 55},
    "Midi":          {"good": 45, "monitor": 75},
    "Mini":          {"good": 60, "monitor": 95},
}
THRESHOLDS_VKM = {   # g CO₂ / vehicle-km
    "High Capacity": {"good": 1500, "monitor": 2100},
    "Midi":          {"good": 1000, "monitor": 1400},
    "Mini":          {"good":  500, "monitor":  750},
}
_DEFAULT_PKM = {"good": 40, "monitor": 70}
_DEFAULT_VKM = {"good": 1200, "monitor": 1700}


def compliance_flag(value, bus_category, basis="passenger"):
    """'Good' / 'Monitor' / 'Over Limit' — NaN (non-revenue) → 'N/A'."""
    if value is None or pd.isna(value):
        return "N/A"
    table, default = (THRESHOLDS_VKM, _DEFAULT_VKM) if basis == "vehicle" \
                     else (THRESHOLDS_PKM, _DEFAULT_PKM)
    t = table.get(bus_category, default)
    if value <= t["good"]:
        return "Good"
    if value <= t["monitor"]:
        return "Monitor"
    return "Over Limit"


# ══════════════════════════════════════════════════════════════
# WORKED EXAMPLE — run `python emissions_engine.py` to see it
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    example = {
        "Bus_Category": "HC", "Fuel_Type": "Diesel",
        "Route_Distance_km": 180, "Avg_Speed_kmh": 22,
        "Ridership": 300, "Num_Trips_Today": 6,   # ≈50 pax on board per trip
        "Euro_Standard": "Euro VI", "Vehicle_Age_years": 5,
        "AC_Status": "False", "Engine_Model": "Yuchai YC6K",
        "Revenue_Trip": 258120, "Revenue_Naira": 258120,
    }
    for method in ("IPCC", "Hybrid", "COPERT"):
        r = calculate_row(example, method, ["CO2", "NOx", "PM"])
        print(f"{method:7s}  CO2 {r['CO2_kg']:8.1f} kg   "
              f"{r['CO2_g_km']:7.1f} g/km   {r['CO2_g_pkm']:5.1f} g/pkm   "
              f"NOx {r['NOx_kg']:6.2f} kg   flag={compliance_flag(r['CO2_g_pkm'], 'High Capacity')}")
