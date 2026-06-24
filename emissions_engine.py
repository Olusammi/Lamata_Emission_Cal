"""
LAMATA Emissions Engine v2
==========================
Methodology: IPCC Tier 2 / COPERT V aligned
- CO2 base factors from IPCC 2006 Guidelines Table 3.2.2 (g CO2/km)
- NOx / PM from EEA COPERT V emission functions by speed band
- Load factor correction per EU Regulation 2019/1242 approach
- Cold start penalty per EMEP/EEA Air Pollutant Emission Inventory Guidebook
- Idling emission: fuel burn at idle RPM
- A/C auxiliary load: CARB 2021 estimate ~8% CO2 uplift for warm climates
- Nigeria grid: 0.46 kg CO2e/kWh (IEA 2023 Africa regional estimate)
"""

import pandas as pd
import math

# ─────────────────────────────────────────
# SECTION 1: BASE EMISSION FACTORS (g/km)
# Values represent a fully laden vehicle at reference speed (~50 km/h)
# Source: IPCC 2006 Tier 2 + COPERT V calibration for West African fleet age
# ─────────────────────────────────────────
BASE_FACTORS = {
    "High Capacity": {             # 18m articulated BRT, ~150 seats
        "Diesel":   {"CO2": 1320.0, "NOx": 14.5, "PM": 0.28, "capacity": 150},
        "CNG":      {"CO2":  980.0, "NOx":  5.2, "PM": 0.03, "capacity": 150},
        "Electric": {"CO2":    0.0, "NOx":  0.0, "PM": 0.0,  "capacity": 150, "kwh_per_km": 2.1},
        "Biogas":   {"CO2":  110.0, "NOx":  4.8, "PM": 0.03, "capacity": 150},
    },
    "Midi": {                      # 10–12m standard bus, ~80 seats
        "Diesel":   {"CO2":  860.0, "NOx":  8.8, "PM": 0.18, "capacity": 80},
        "CNG":      {"CO2":  640.0, "NOx":  3.1, "PM": 0.02, "capacity": 80},
        "Electric": {"CO2":    0.0, "NOx":  0.0, "PM": 0.0,  "capacity": 80, "kwh_per_km": 1.2},
        "Hybrid":   {"CO2":  520.0, "NOx":  4.5, "PM": 0.09, "capacity": 80},
    },
    "Mini": {                      # Danfo-style minibus, ~18 seats
        "Petrol":   {"CO2":  400.0, "NOx":  0.9, "PM": 0.012, "capacity": 18},
        "Diesel":   {"CO2":  450.0, "NOx":  2.8, "PM": 0.06,  "capacity": 18},
        "CNG":      {"CO2":  300.0, "NOx":  0.6, "PM": 0.003, "capacity": 18},
    },
}

# Fallback for unknown bus/fuel combos
FALLBACK_FACTORS = {"CO2": 1100.0, "NOx": 7.0, "PM": 0.15, "capacity": 80}

# Nigeria grid emission factor (Scope 2 for electric buses)
GRID_EF_KG_PER_KWH = 0.46

# A/C auxiliary load uplift (Lagos climate — assumed always on)
AC_UPLIFT_CO2 = 0.08   # +8% to CO2 and fuel-related pollutants

# Cold start distance: first 5 km of each trip run at elevated EF
COLD_START_KM = 5.0
COLD_START_MULTIPLIER = {"CO2": 1.18, "NOx": 2.8, "PM": 3.2}

# Idling EF at terminal/stops (g per minute of idle)
IDLING_EF = {
    "High Capacity": {"Diesel": {"CO2": 28.0, "NOx": 0.22, "PM": 0.006},
                      "CNG":    {"CO2": 20.0, "NOx": 0.08, "PM": 0.001},
                      "Biogas": {"CO2":  3.5, "NOx": 0.07, "PM": 0.001}},
    "Midi":          {"Diesel": {"CO2": 18.0, "NOx": 0.14, "PM": 0.004},
                      "CNG":    {"CO2": 12.0, "NOx": 0.05, "PM": 0.0005}},
    "Mini":          {"Petrol": {"CO2":  9.0, "NOx": 0.03, "PM": 0.0005},
                      "Diesel": {"CO2": 10.0, "NOx": 0.07, "PM": 0.002},
                      "CNG":    {"CO2":  6.5, "NOx": 0.02, "PM": 0.0002}},
}
DEFAULT_IDLE_MINUTES = 10  # assumed idle per trip (Lagos traffic + terminal dwell)

# ─────────────────────────────────────────
# SECTION 2: SPEED-CORRECTION FUNCTIONS
# COPERT V hot-emission functions by speed band
# ─────────────────────────────────────────
def _speed_factor_co2(speed_kmh: float) -> float:
    """
    CO2 is roughly proportional to fuel consumption.
    Minimum around 60–70 km/h; rises at very low (congestion) and very high speeds.
    Fitted to COPERT V heavy-duty bus curves.
    """
    if speed_kmh <= 0:
        return 3.0
    s = max(5.0, min(speed_kmh, 100.0))
    # U-shaped curve: optimal ~65 km/h
    return 0.4 + 53.0 / s + s / 180.0


def _speed_factor_nox(speed_kmh: float) -> float:
    """
    NOx peaks at moderate-high speed (high combustion temps).
    Monotonically increases with speed for diesel.
    """
    if speed_kmh <= 0:
        return 2.5
    s = max(5.0, min(speed_kmh, 100.0))
    return 0.85 + s / 90.0


def _speed_factor_pm(speed_kmh: float) -> float:
    """
    PM highest at very low speed (cold, rich combustion) and braking.
    Decreases with speed up to ~60, then flattens.
    """
    if speed_kmh <= 0:
        return 4.0
    s = max(5.0, min(speed_kmh, 100.0))
    return max(0.6, 4.5 - s / 20.0)


SPEED_FUNCTIONS = {
    "CO2": _speed_factor_co2,
    "NOx": _speed_factor_nox,
    "PM":  _speed_factor_pm,
}

# ─────────────────────────────────────────
# SECTION 3: LOAD FACTOR CORRECTION
# Emission per vehicle km is roughly constant regardless of passengers,
# but emission per passenger-km drops with more passengers.
# We also apply a small vehicle-level correction: heavier vehicle = more fuel.
# Reference: EU Reg 2019/1242 ±5% per 10% load deviation from reference.
# ─────────────────────────────────────────
def _load_correction(actual_ridership: int, capacity: int) -> float:
    """
    Returns a factor applied to total vehicle emissions (not per-pax).
    Higher load → heavier bus → slightly more fuel. 5% per 10-pax-load band.
    """
    if capacity <= 0:
        return 1.0
    load_ratio = min(actual_ridership / capacity, 1.2)
    reference_load = 0.5  # 50% load is the calibration point for base factors
    deviation = load_ratio - reference_load
    return 1.0 + deviation * 0.05


# ─────────────────────────────────────────
# SECTION 4: METHODOLOGY DISPATCHERS
# ─────────────────────────────────────────
def _calc_ipcc(base: float, pollutant: str, distance: float) -> float:
    """IPCC Tier 2: fixed EF × distance. No speed correction."""
    return base * distance


def _calc_copert(base: float, pollutant: str, distance: float, speed: float) -> float:
    """COPERT V: speed-corrected EF × distance."""
    fn = SPEED_FUNCTIONS.get(pollutant, lambda s: 1.0)
    return base * fn(speed) * distance


def _calc_hybrid(base: float, pollutant: str, distance: float, speed: float) -> float:
    """
    Hybrid (default LAMATA approach):
    - CO2: IPCC Tier 2 (fixed EF × distance) for carbon accounting
    - NOx / PM: COPERT V speed-corrected (air quality impact analysis)
    """
    if pollutant == "CO2":
        return _calc_ipcc(base, pollutant, distance)
    return _calc_copert(base, pollutant, distance, speed)


# ─────────────────────────────────────────
# SECTION 5: MAIN ROW CALCULATOR
# ─────────────────────────────────────────
def calculate_row(row, methodology: str, target_pollutants: list) -> pd.Series:
    bus_category = str(row.get("Bus_Category", "")).strip()
    fuel_type    = str(row.get("Fuel_Type", "")).strip()
    distance     = float(row.get("Route_Distance_km", 0) or 0)
    speed        = float(row.get("Avg_Speed_kmh", 25) or 25)
    ridership    = max(1, int(row.get("Ridership", 1) or 1))
    is_revenue   = bool(row.get("Revenue_Trip", True))
    idle_minutes = float(row.get("Idle_Minutes", DEFAULT_IDLE_MINUTES))

    category_data = BASE_FACTORS.get(bus_category, {})
    fuel_profile  = category_data.get(fuel_type, FALLBACK_FACTORS)
    capacity      = int(fuel_profile.get("capacity", 80))

    # ── Electric: Scope 2 only (grid electricity) ──
    if fuel_type == "Electric":
        kwh_per_km = float(fuel_profile.get("kwh_per_km", 1.5))
        total_kwh  = kwh_per_km * distance
        co2_kg     = total_kwh * GRID_EF_KG_PER_KWH if "CO2" in target_pollutants else 0.0
        results = {
            "CO2_kg":     round(co2_kg, 4),
            "NOx_kg":     0.0,
            "PM_kg":      0.0,
            "CO2_g_pkm":  round((co2_kg * 1000) / ridership, 2) if is_revenue else 0.0,
            "NOx_g_pkm":  0.0,
            "PM_g_pkm":   0.0,
            "load_factor": round(ridership / capacity, 3),
        }
        return pd.Series(results)

    results = {}
    load_corr = _load_correction(ridership, capacity)

    for pol in ["CO2", "NOx", "PM"]:
        base_ef = float(fuel_profile.get(pol, 0.0))

        if pol not in target_pollutants or base_ef == 0.0:
            results[f"{pol}_kg"]    = 0.0
            results[f"{pol}_g_pkm"] = 0.0
            continue

        # ── 1. Hot running emissions ──
        if methodology == "IPCC":
            hot_g = _calc_ipcc(base_ef, pol, distance)
        elif methodology == "COPERT":
            hot_g = _calc_copert(base_ef, pol, distance, speed)
        else:  # Hybrid
            hot_g = _calc_hybrid(base_ef, pol, distance, speed)

        # ── 2. Cold start penalty (first COLD_START_KM km) ──
        cold_km    = min(distance, COLD_START_KM)
        cs_mult    = COLD_START_MULTIPLIER.get(pol, 1.0)
        cold_extra = base_ef * cold_km * (cs_mult - 1.0)  # delta above hot

        # ── 3. Idling emissions ──
        idle_ef  = IDLING_EF.get(bus_category, {}).get(fuel_type, {}).get(pol, 0.0)
        idle_g   = idle_ef * idle_minutes

        # ── 4. A/C auxiliary uplift (CO2 only; does not affect NOx/PM directly) ──
        ac_extra = hot_g * AC_UPLIFT_CO2 if pol == "CO2" else 0.0

        # ── 5. Load factor vehicle-level correction ──
        total_g = (hot_g + cold_extra + idle_g + ac_extra) * load_corr

        total_kg = total_g / 1000.0
        results[f"{pol}_kg"]    = round(total_kg, 4)
        results[f"{pol}_g_pkm"] = round((total_g / ridership), 2) if is_revenue else 0.0

    results["load_factor"] = round(ridership / capacity, 3)

    return pd.Series(results)


# ─────────────────────────────────────────
# SECTION 6: FLEET SUMMARY UTILITIES
# ─────────────────────────────────────────
def emission_breakdown(row, methodology="Hybrid") -> dict:
    """
    Returns a breakdown of emission contributors for a single trip row.
    Useful for the 'Emission Source Breakdown' UI panel.
    """
    bus_category = str(row.get("Bus_Category", "")).strip()
    fuel_type    = str(row.get("Fuel_Type", "")).strip()
    distance     = float(row.get("Route_Distance_km", 0) or 0)
    speed        = float(row.get("Avg_Speed_kmh", 25) or 25)
    ridership    = max(1, int(row.get("Ridership", 1) or 1))
    idle_minutes = float(row.get("Idle_Minutes", DEFAULT_IDLE_MINUTES))

    category_data = BASE_FACTORS.get(bus_category, {})
    fuel_profile  = category_data.get(fuel_type, FALLBACK_FACTORS)
    base_ef       = float(fuel_profile.get("CO2", 0.0))

    if fuel_type == "Electric":
        kwh = fuel_profile.get("kwh_per_km", 1.5) * distance
        total = kwh * GRID_EF_KG_PER_KWH * 1000
        return {"hot_running": 0, "cold_start": 0, "idling": 0, "ac_load": 0,
                "grid_electric": round(total, 1), "total_g": round(total, 1)}

    if methodology == "COPERT":
        hot_g = _calc_copert(base_ef, "CO2", distance, speed)
    else:
        hot_g = _calc_ipcc(base_ef, "CO2", distance)

    cold_km    = min(distance, COLD_START_KM)
    cold_extra = base_ef * cold_km * (COLD_START_MULTIPLIER["CO2"] - 1.0)
    idle_ef    = IDLING_EF.get(bus_category, {}).get(fuel_type, {}).get("CO2", 0.0)
    idle_g     = idle_ef * idle_minutes
    ac_extra   = hot_g * AC_UPLIFT_CO2

    return {
        "hot_running":    round(hot_g, 1),
        "cold_start":     round(cold_extra, 1),
        "idling":         round(idle_g, 1),
        "ac_load":        round(ac_extra, 1),
        "grid_electric":  0,
        "total_g":        round(hot_g + cold_extra + idle_g + ac_extra, 1),
    }


def compliance_flag(co2_g_pkm: float, bus_category: str) -> str:
    """
    Flag trips against LAMATA internal thresholds (g CO2 per passenger-km).
    Returns: 'Good', 'Monitor', 'Over Limit'
    """
    THRESHOLDS = {
        "High Capacity": {"good": 30, "monitor": 55},
        "Midi":          {"good": 45, "monitor": 75},
        "Mini":          {"good": 60, "monitor": 95},
    }
    t = THRESHOLDS.get(bus_category, {"good": 40, "monitor": 70})
    if co2_g_pkm <= t["good"]:
        return "Good"
    if co2_g_pkm <= t["monitor"]:
        return "Monitor"
    return "Over Limit"
