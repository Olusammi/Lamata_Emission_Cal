"""
LAMATA Emissions Engine
=======================
Faithful Python port of the calculation engine that powers the
"Operations Center" dashboard. Give it the trip-level CSV and it
returns per-trip and per-bus emissions for CO2, NOx and PM under
three methodologies (Hybrid, IPCC, COPERT).

Model
-----
  CO2  : IPCC-style base factor x age deterioration
         + COPERT V speed correction (COPERT / Hybrid only)
         + cold-start addend + idling addend, all x load factor
  NOx  : COPERT base x Euro-class multiplier x age deterioration
         x speed function (IPCC = flat 1.0)
  PM   : same structure as NOx with PM factors

  Efficiency = grams CO2 per passenger-kilometre  (total_g / (riders * km))
  Compliance thresholds are per bus-category (g CO2 / pkm).

Usage
-----
    import pandas as pd
    from emissions_engine import process
    df = pd.read_csv("Final_Bus_Data.csv")
    trips, buses = process(df, method="Hybrid")
"""

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# Factor tables  (base g/km, cap = design capacity used for load factor)
# ----------------------------------------------------------------------
FACT = {
    "High Capacity": {
        "Diesel": {"CO2": 1320, "NOx": 14.5, "PM": 0.28,  "cap": 150},
        "CNG":    {"CO2": 980,  "NOx": 5.2,  "PM": 0.03,  "cap": 150},
    },
    "Midi": {
        "Diesel": {"CO2": 860,  "NOx": 8.8,  "PM": 0.18,  "cap": 80},
        "CNG":    {"CO2": 640,  "NOx": 3.1,  "PM": 0.02,  "cap": 80},
    },
    "Mini": {
        "Petrol": {"CO2": 400,  "NOx": 0.9,  "PM": 0.012, "cap": 18},
        "Diesel": {"CO2": 450,  "NOx": 2.8,  "PM": 0.06,  "cap": 18},
    },
}
DEFAULT_FACT = {"CO2": 1100, "NOx": 7.0, "PM": 0.15, "cap": 80}

# Euro-standard multipliers (relative to Euro III = 1.0) for NOx / PM
EUROM = {
    "Euro II":  {"NOx": 1.30, "PM": 1.45},
    "Euro III": {"NOx": 1.00, "PM": 1.00},
    "Euro IV":  {"NOx": 0.55, "PM": 0.45},
    "Euro V":   {"NOx": 0.30, "PM": 0.25},
    "Euro VI":  {"NOx": 0.05, "PM": 0.04},
}

# Idling emission per trip-day (grams / 10, i.e. value x 10 grams added)
IDLE = {
    "High Capacity": {"Diesel": 28},
    "Midi":          {"Diesel": 18},
    "Mini":          {"Petrol": 9, "Diesel": 10},
}

# Compliance thresholds per category  ->  [good_max, monitor_max]  (g CO2/pkm)
THRESH = {
    "High Capacity": [30, 55],
    "Midi":          [45, 75],
    "Mini":          [60, 95],
}

# Raw-CSV value -> canonical name
CAT_MAP  = {"HC": "High Capacity", "Midi": "Midi", "FLM": "Mini", "FLM X30L": "Mini"}
FUEL_MAP = {"Diesel": "Diesel", "PMS": "Petrol"}

STATUS = ["Good", "Monitor", "Over"]
METHODS = ("Hybrid", "IPCC", "COPERT")


# ----------------------------------------------------------------------
# Speed correction functions (COPERT V style, vectorised)
# ----------------------------------------------------------------------
def _speed_factor(pollutant, speed):
    s = np.clip(speed, 5, 100)
    if pollutant == "CO2":
        return 0.4 + 53.0 / s + s / 180.0
    if pollutant == "NOx":
        return 0.85 + s / 90.0
    # PM
    return np.maximum(0.6, 4.5 - s / 20.0)


def _lookup(cat, fuel, key):
    return FACT.get(cat, {}).get(fuel, DEFAULT_FACT)[key]


# ----------------------------------------------------------------------
# Core: compute per-trip emissions for one methodology
# ----------------------------------------------------------------------
def compute_trips(df, method="Hybrid"):
    """Return a copy of df with CO2_kg, NOx_kg, PM_kg, gpkm, Status columns."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")

    d = df.copy()

    # --- normalise inputs ---
    d["cat"]  = d["Bus_Category"].astype(str).str.strip().map(CAT_MAP).fillna("Midi")
    d["fuel"] = d["Fuel_Type"].astype(str).str.strip().map(FUEL_MAP).fillna("Diesel")
    d["euro"] = d["Euro_Standard"].astype(str).str.strip()
    d["age"]  = pd.to_numeric(d["Vehicle_Age_years"], errors="coerce").fillna(0.0)
    d["dist"] = pd.to_numeric(d["Route_Distance_km"], errors="coerce").fillna(0.0)
    d["spd"]  = pd.to_numeric(d["Avg_Speed_kmh"], errors="coerce").fillna(25.0)
    d["rider"] = pd.to_numeric(d["Ridership"], errors="coerce").fillna(1.0).clip(lower=1)
    d["trips"] = pd.to_numeric(d["Num_Trips_Today"], errors="coerce").fillna(1.0).clip(lower=1).round()

    # --- per-row factor lookups ---
    baseCO2 = d.apply(lambda r: _lookup(r["cat"], r["fuel"], "CO2"), axis=1)
    baseNOx = d.apply(lambda r: _lookup(r["cat"], r["fuel"], "NOx"), axis=1)
    basePM  = d.apply(lambda r: _lookup(r["cat"], r["fuel"], "PM"),  axis=1)
    cap     = d.apply(lambda r: _lookup(r["cat"], r["fuel"], "cap"), axis=1)
    idle    = d.apply(lambda r: IDLE.get(r["cat"], {}).get(r["fuel"], 0), axis=1)
    euroN   = d["euro"].map(lambda e: EUROM.get(e, EUROM["Euro III"])["NOx"])
    euroP   = d["euro"].map(lambda e: EUROM.get(e, EUROM["Euro III"])["PM"])

    diff = d["fuel"].isin(["Diesel", "Petrol"])

    ageC = 1 + 0.004 * d["age"]
    ageN = 1 + np.where(diff, 0.015, 0.008) * d["age"]
    ageP = 1 + np.where(diff, 0.020, 0.005) * d["age"]
    load = 1 + (np.minimum(d["rider"] / cap, 1.2) - 0.5) * 0.05

    # --- CO2 (grams) ---
    efC  = baseCO2 * ageC
    spdC = _speed_factor("CO2", d["spd"]) if method == "COPERT" else 1.0
    hotC  = efC * spdC * d["dist"]
    coldC = efC * np.minimum(d["dist"], 5) * 0.18 * d["trips"]
    idleC = idle * 10
    totC  = (hotC + coldC + idleC) * load

    # --- NOx / PM (grams) ---
    flat = (method == "IPCC")
    efN = baseNOx * euroN * ageN
    efP = basePM  * euroP * ageP
    spN = 1.0 if flat else _speed_factor("NOx", d["spd"])
    spP = 1.0 if flat else _speed_factor("PM",  d["spd"])
    totN = (efN * spN * d["dist"] + efN * np.minimum(d["dist"], 5) * 1.8 * d["trips"]) * load
    totP = (efP * spP * d["dist"] + efP * np.minimum(d["dist"], 5) * 2.2 * d["trips"]) * load

    # --- outputs ---
    d["CO2_g"], d["NOx_g"], d["PM_g"] = totC, totN, totP
    d["CO2_kg"] = totC / 1000.0
    d["NOx_kg"] = totN / 1000.0
    d["PM_kg"]  = totP / 1000.0
    d["pass_km"] = d["rider"] * d["dist"]
    d["gpkm"] = np.where(d["pass_km"] > 0, totC / d["pass_km"], 0.0)

    good = d["cat"].map(lambda c: THRESH.get(c, [45, 75])[0])
    mon  = d["cat"].map(lambda c: THRESH.get(c, [45, 75])[1])
    d["Status"] = np.where(d["gpkm"] <= good, "Good",
                    np.where(d["gpkm"] <= mon, "Monitor", "Over"))
    return d


# ----------------------------------------------------------------------
# Roll trip rows up to one row per bus (monthly totals)
# ----------------------------------------------------------------------
def aggregate_buses(trips):
    g = trips.groupby("Bus_ID")
    buses = g.agg(
        Operator=("Operator", "first"),
        Route=("Route_Name", "first"),
        Category=("cat", "first"),
        Fuel=("fuel", "first"),
        Euro=("euro", "first"),
        Age=("age", "max"),
        CO2_kg=("CO2_kg", "sum"),
        NOx_kg=("NOx_kg", "sum"),
        PM_kg=("PM_kg", "sum"),
        CO2_g=("CO2_g", "sum"),
        pass_km=("pass_km", "sum"),
        Passengers=("rider", "sum"),
        Trips=("trips", "sum"),
        trips_good=("Status", lambda s: (s == "Good").sum()),
        trips_monitor=("Status", lambda s: (s == "Monitor").sum()),
        trips_over=("Status", lambda s: (s == "Over").sum()),
    ).reset_index()

    buses["gpkm"] = np.where(buses["pass_km"] > 0, buses["CO2_g"] / buses["pass_km"], 0.0)
    good = buses["Category"].map(lambda c: THRESH.get(c, [45, 75])[0])
    mon  = buses["Category"].map(lambda c: THRESH.get(c, [45, 75])[1])
    buses["Status"] = np.where(buses["gpkm"] <= good, "Good",
                        np.where(buses["gpkm"] <= mon, "Monitor", "Over"))
    return buses


def process(df, method="Hybrid"):
    """Convenience: returns (trip_level_df, bus_level_df) for one methodology."""
    trips = compute_trips(df, method)
    buses = aggregate_buses(trips)
    return trips, buses


def fleet_summary(buses):
    """Headline KPIs matching the dashboard."""
    pw = buses["Passengers"].clip(lower=1)
    eff = float((buses["gpkm"] * pw).sum() / pw.sum()) if len(buses) else 0.0
    return {
        "buses": int(len(buses)),
        "operators": int(buses["Operator"].nunique()),
        "co2_tonnes": float(buses["CO2_kg"].sum() / 1000.0),
        "nox_tonnes": float(buses["NOx_kg"].sum() / 1000.0),
        "pm_kg": float(buses["PM_kg"].sum()),
        "trips": int(buses["Trips"].sum()),
        "passengers": int(buses["Passengers"].sum()),
        "fleet_efficiency_gpkm": round(eff, 1),
        "avg_age": round(float(buses["Age"].mean()), 1) if len(buses) else 0.0,
        "buses_over_limit": int((buses["Status"] == "Over").sum()),
        "trips_good": int(buses["trips_good"].sum()),
        "trips_monitor": int(buses["trips_monitor"].sum()),
        "trips_over": int(buses["trips_over"].sum()),
    }


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "Final_Bus_Data.csv"
    df = pd.read_csv(path)
    for m in METHODS:
        _, buses = process(df, m)
        s = fleet_summary(buses)
        print(f"{m:>7}:  CO2 {s['co2_tonnes']:>8.0f} t   "
              f"eff {s['fleet_efficiency_gpkm']:>5.1f} g/pkm   "
              f"over {s['buses_over_limit']:>3} buses   "
              f"trips good/mon/over {s['trips_good']}/{s['trips_monitor']}/{s['trips_over']}")
