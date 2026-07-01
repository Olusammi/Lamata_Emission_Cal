"""
LAMATA Emissions Engine  (full model)
=====================================
Faithful Python port of the calculation engine that powers the
"Operations Center" interface. Give it the trip-level CSV and it returns
per-trip and per-bus emissions for CO2, NOx and PM under three
methodologies (Hybrid, IPCC, COPERT) — including Electric and CNG buses,
A/C load uplift, and a full per-component breakdown so the Trip Inspector
and Formula Explainer can show every addend.

Model
-----
  CO2  : IPCC-style base factor x age deterioration
         + COPERT V speed correction (COPERT method only)
         + cold-start addend + idling addend + A/C load, all x load factor
         Electric buses: grid_kWh x distance x grid CO2 factor (0.46 kg/kWh)
  NOx  : base x Euro-class multiplier x age deterioration
         x speed function (IPCC = flat 1.0) x load        [hot running only]
  PM   : same structure as NOx with PM factors

  Efficiency = grams CO2 per passenger-kilometre  (total_g / (riders * km))
  Compliance thresholds are per bus-category (g CO2 / pkm).

Usage
-----
    import pandas as pd
    from emissions_engine import process, fleet_summary, trip_breakdown
    df = pd.read_csv("Final_Bus_Data.csv")
    trips, buses = process(df, method="Hybrid")
"""

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# Factor tables  (base g/km; cap = design capacity for load factor;
#                 kwh = grid energy per km for Electric buses)
# ----------------------------------------------------------------------
FACT = {
    "High Capacity": {
        "Diesel":   {"CO2": 1320, "NOx": 14.5, "PM": 0.28,  "cap": 150},
        "CNG":      {"CO2": 980,  "NOx": 5.2,  "PM": 0.03,  "cap": 150},
        "Electric": {"CO2": 0,    "NOx": 0,    "PM": 0,     "cap": 150, "kwh": 2.1},
    },
    "Midi": {
        "Diesel":   {"CO2": 860,  "NOx": 8.8,  "PM": 0.18,  "cap": 80},
        "CNG":      {"CO2": 640,  "NOx": 3.1,  "PM": 0.02,  "cap": 80},
        "Electric": {"CO2": 0,    "NOx": 0,    "PM": 0,     "cap": 80,  "kwh": 1.2},
    },
    "Mini": {
        "Petrol":   {"CO2": 400,  "NOx": 0.9,  "PM": 0.012, "cap": 18},
        "Diesel":   {"CO2": 450,  "NOx": 2.8,  "PM": 0.06,  "cap": 18},
        "CNG":      {"CO2": 300,  "NOx": 0.6,  "PM": 0.003, "cap": 18},
    },
}
DEFAULT_FACT = {"CO2": 1100, "NOx": 7.0, "PM": 0.15, "cap": 80, "kwh": 1.5}

GRID_CO2_KG_PER_KWH = 0.46   # Nigeria grid emission factor
AC_UPLIFT = 0.08             # +8% on hot-running CO2 when A/C is on

# Euro-standard multipliers (relative to Euro III = 1.0) for NOx / PM
EUROM = {
    "Euro II":  {"NOx": 1.30, "PM": 1.45},
    "Euro III": {"NOx": 1.00, "PM": 1.00},
    "Euro IV":  {"NOx": 0.55, "PM": 0.45},
    "Euro V":   {"NOx": 0.30, "PM": 0.25},
    "Euro VI":  {"NOx": 0.05, "PM": 0.04},
}

# Idling emission per record (value x 10 grams added)
IDLE = {
    "High Capacity": {"Diesel": 28, "CNG": 20},
    "Midi":          {"Diesel": 18, "CNG": 12},
    "Mini":          {"Petrol": 9,  "Diesel": 10, "CNG": 6.5},
}

# Compliance thresholds per category -> [good_max, monitor_max]  (g CO2/pkm)
THRESH = {
    "High Capacity": [30, 55],
    "Midi":          [45, 75],
    "Mini":          [60, 95],
}

# Raw-CSV value -> canonical name
CAT_MAP  = {"HC": "High Capacity", "Midi": "Midi", "FLM": "Mini",
            "FLM X30L": "Mini", "X30L": "Mini", "Mini": "Mini",
            "High Capacity": "High Capacity"}
FUEL_MAP = {"Diesel": "Diesel", "PMS": "Petrol", "Petrol": "Petrol",
            "CNG": "CNG", "Gas": "CNG",
            "Electric": "Electric", "EV": "Electric", "E": "Electric",
            "Battery": "Electric"}

# Column names we will accept for the (optional) A/C flag
AC_COLS = ["AC", "A/C", "Air_Conditioning", "Air_Conditioned",
           "AC_Status", "Has_AC", "AirCon", "Aircon"]
TRUEY = {"1", "true", "yes", "y", "on", "ac", "t"}

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
    return np.maximum(0.6, 4.5 - s / 20.0)   # PM


def _lookup(cat, fuel, key):
    node = FACT.get(cat, {}).get(fuel)
    if node is None:
        return DEFAULT_FACT.get(key, 0)
    return node.get(key, DEFAULT_FACT.get(key, 0))


def _find_ac_series(df):
    """Return a boolean Series for A/C status, or all-False if no column."""
    for c in AC_COLS:
        if c in df.columns:
            return df[c].astype(str).str.strip().str.lower().isin(TRUEY)
    return pd.Series(False, index=df.index)


# ----------------------------------------------------------------------
# Core: compute per-trip emissions for one methodology
# ----------------------------------------------------------------------
def compute_trips(df, method="Hybrid"):
    """Return a copy of df with per-component + total emission columns."""
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
    d["ac"]   = _find_ac_series(d).values

    # --- per-row factor lookups ---
    baseCO2 = d.apply(lambda r: _lookup(r["cat"], r["fuel"], "CO2"), axis=1)
    baseNOx = d.apply(lambda r: _lookup(r["cat"], r["fuel"], "NOx"), axis=1)
    basePM  = d.apply(lambda r: _lookup(r["cat"], r["fuel"], "PM"),  axis=1)
    cap     = d.apply(lambda r: _lookup(r["cat"], r["fuel"], "cap"), axis=1)
    kwh     = d.apply(lambda r: _lookup(r["cat"], r["fuel"], "kwh"), axis=1)
    idle    = d.apply(lambda r: IDLE.get(r["cat"], {}).get(r["fuel"], 0), axis=1)
    euroN   = d["euro"].map(lambda e: EUROM.get(e, EUROM["Euro III"])["NOx"])
    euroP   = d["euro"].map(lambda e: EUROM.get(e, EUROM["Euro III"])["PM"])

    is_ev = (d["fuel"] == "Electric").values
    diff  = d["fuel"].isin(["Diesel", "Petrol"]).values

    ageC = 1 + 0.004 * d["age"]
    ageN = 1 + np.where(diff, 0.015, 0.008) * d["age"]
    ageP = 1 + np.where(diff, 0.020, 0.005) * d["age"]
    load = 1 + (np.minimum(d["rider"] / cap.clip(lower=1), 1.2) - 0.5) * 0.05

    # --- CO2 (grams) — combustion buses ---
    efC  = baseCO2 * ageC
    spdC = _speed_factor("CO2", d["spd"]) if method == "COPERT" else 1.0
    hot   = efC * spdC * d["dist"]
    cold  = efC * np.minimum(d["dist"], 5) * 0.18 * d["trips"]
    idleg = idle * 10
    acg   = np.where(d["ac"].values & ~is_ev, hot * AC_UPLIFT, 0.0)

    # apply load factor to each component so components sum to the total
    hotL  = hot   * load
    coldL = cold  * load
    idleL = idleg * load
    acL   = pd.Series(acg, index=d.index) * load

    # --- Electric buses: grid electricity only ---
    grid_kwh = np.where(is_ev, kwh * d["dist"], 0.0)
    ev_co2_g = grid_kwh * GRID_CO2_KG_PER_KWH * 1000.0

    hotL  = np.where(is_ev, 0.0, hotL)
    coldL = np.where(is_ev, 0.0, coldL)
    idleL = np.where(is_ev, 0.0, idleL)
    acL   = np.where(is_ev, 0.0, acL)
    totC  = np.where(is_ev, ev_co2_g, hotL + coldL + idleL + acL)

    # --- NOx / PM (grams) — hot running only ---
    flat = (method == "IPCC")
    spN = 1.0 if flat else _speed_factor("NOx", d["spd"])
    spP = 1.0 if flat else _speed_factor("PM",  d["spd"])
    totN = baseNOx * euroN * ageN * spN * d["dist"] * load
    totP = basePM  * euroP * ageP * spP * d["dist"] * load
    totN = np.where(is_ev, 0.0, totN)
    totP = np.where(is_ev, 0.0, totP)

    # --- outputs ---
    d["CO2_hot_g"]  = hotL
    d["CO2_cold_g"] = coldL
    d["CO2_idle_g"] = idleL
    d["CO2_ac_g"]   = acL
    d["grid_kwh"]   = grid_kwh
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
        Route=("Route_Name", "first") if "Route_Name" in trips.columns else ("Operator", "first"),
        Category=("cat", "first"),
        Fuel=("fuel", "first"),
        Euro=("euro", "first"),
        AC=("ac", "max"),
        Age=("age", "max"),
        CO2_kg=("CO2_kg", "sum"),
        NOx_kg=("NOx_kg", "sum"),
        PM_kg=("PM_kg", "sum"),
        CO2_g=("CO2_g", "sum"),
        CO2_hot_g=("CO2_hot_g", "sum"),
        CO2_cold_g=("CO2_cold_g", "sum"),
        CO2_idle_g=("CO2_idle_g", "sum"),
        CO2_ac_g=("CO2_ac_g", "sum"),
        grid_kwh=("grid_kwh", "sum"),
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
        "ev_count": int((buses["Fuel"] == "Electric").sum()),
        "trips_good": int(buses["trips_good"].sum()),
        "trips_monitor": int(buses["trips_monitor"].sum()),
        "trips_over": int(buses["trips_over"].sum()),
    }


# ----------------------------------------------------------------------
# Single-record breakdown — powers Trip Inspector & Formula Explainer
# ----------------------------------------------------------------------
def trip_breakdown(rec, method="Hybrid"):
    """
    rec: dict with keys cat, fuel, euro, age, dist, spd, rider, trips, ac
    Returns a fully-labelled breakdown of one trip record for `method`.
    """
    cat  = CAT_MAP.get(str(rec.get("cat", "")).strip(), rec.get("cat", "Midi"))
    fuel = FUEL_MAP.get(str(rec.get("fuel", "")).strip(), rec.get("fuel", "Diesel"))
    euro = str(rec.get("euro", "Euro III")).strip()
    age  = float(rec.get("age", 0) or 0)
    dist = float(rec.get("dist", 0) or 0)
    spd  = float(rec.get("spd", 25) or 25)
    rider = max(1.0, float(rec.get("rider", 1) or 1))
    trips = max(1.0, round(float(rec.get("trips", 1) or 1)))
    ac   = bool(rec.get("ac", False))

    cap  = _lookup(cat, fuel, "cap")
    load = 1 + (min(rider / max(cap, 1), 1.2) - 0.5) * 0.05
    pass_km = rider * dist
    g, mn = THRESH.get(cat, [45, 75])

    out = {"cat": cat, "fuel": fuel, "euro": euro, "age": age, "dist": dist,
           "spd": spd, "rider": rider, "trips": trips, "ac": ac,
           "cap": cap, "load": load, "pass_km": pass_km,
           "method": method, "thresh": (g, mn)}

    if fuel == "Electric":
        kwh = _lookup(cat, fuel, "kwh")
        energy = kwh * dist
        co2_g = energy * GRID_CO2_KG_PER_KWH * 1000.0
        out.update({
            "ev": True,
            "grid_kwh": energy,
            "co2_g": co2_g, "nox_g": 0.0, "pm_g": 0.0,
            "components": {"Grid electricity": co2_g},
            "co2_steps": [
                ("Grid energy", f"{kwh:g} kWh/km × {dist:.1f} km", energy, "kWh"),
                ("× grid CO₂ factor", f"{energy:.1f} kWh × {GRID_CO2_KG_PER_KWH} kg/kWh",
                 co2_g / 1000.0, "kg"),
            ],
        })
    else:
        baseCO2 = _lookup(cat, fuel, "CO2")
        ageC = 1 + 0.004 * age
        efC  = baseCO2 * ageC
        spdC = _speed_factor("CO2", spd) if method == "COPERT" else 1.0
        hot  = efC * spdC * dist * load
        cold = efC * min(dist, 5) * 0.18 * trips * load
        idleg = (IDLE.get(cat, {}).get(fuel, 0) * 10) * load
        acg  = (hot * AC_UPLIFT) if ac else 0.0
        co2_g = hot + cold + idleg + acg

        em = EUROM.get(euro, EUROM["Euro III"])
        diff = fuel in ("Diesel", "Petrol")
        baseNOx = _lookup(cat, fuel, "NOx"); basePM = _lookup(cat, fuel, "PM")
        ageN = 1 + (0.015 if diff else 0.008) * age
        ageP = 1 + (0.020 if diff else 0.005) * age
        spN = 1.0 if method == "IPCC" else _speed_factor("NOx", spd)
        spP = 1.0 if method == "IPCC" else _speed_factor("PM", spd)
        nox_g = baseNOx * em["NOx"] * ageN * spN * dist * load
        pm_g  = basePM  * em["PM"]  * ageP * spP * dist * load

        out.update({
            "ev": False,
            "base_co2": baseCO2, "ageC": ageC, "efC": efC, "spdC": spdC,
            "co2_g": co2_g, "nox_g": nox_g, "pm_g": pm_g,
            "components": {"Hot running": hot, "Cold start": cold,
                           "Idling": idleg, "A/C load": acg},
            "co2_steps": [
                ("Base factor", f"{cat} · {fuel}", baseCO2, "g/km"),
                ("× age deterioration", f"1 + 0.004 × {age:g} yr", ageC, "×"),
                ("Emission factor", f"{baseCO2:g} × {ageC:.3f}", efC, "g/km"),
                (f"× speed factor ({method})",
                 "flat 1.0" if method != "COPERT" else f"f({spd:.0f} km/h)", spdC, "×"),
                ("Hot running", f"{efC:.0f} × {spdC:.3f} × {dist:.1f} km × load {load:.3f}",
                 hot, "g"),
                ("+ Cold start", f"{efC:.0f} × min({dist:.1f},5) × 0.18 × {trips:g} trips",
                 cold, "g"),
                ("+ Idling", f"idle {cat}/{fuel} × 10", idleg, "g"),
                ("+ A/C load", f"{'+8% of hot' if ac else 'A/C off'}", acg, "g"),
                ("Total CO₂", "sum of the above", co2_g / 1000.0, "kg"),
            ],
            "nox_detail": {"base": baseNOx, "euro": em["NOx"], "age": ageN, "speed": spN},
            "pm_detail":  {"base": basePM,  "euro": em["PM"],  "age": ageP, "speed": spP},
        })

    gpkm = (out["co2_g"] / pass_km) if pass_km > 0 else 0.0
    out["gpkm"] = gpkm
    out["status"] = "Good" if gpkm <= g else ("Monitor" if gpkm <= mn else "Over")
    return out


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "Final_Bus_Data.csv"
    df = pd.read_csv(path)
    for m in METHODS:
        _, buses = process(df, m)
        s = fleet_summary(buses)
        print(f"{m:>7}:  CO2 {s['co2_tonnes']:>8.0f} t   "
              f"eff {s['fleet_efficiency_gpkm']:>5.1f} g/pkm   "
              f"over {s['buses_over_limit']:>3} buses   EV {s['ev_count']:>3}   "
              f"trips g/m/o {s['trips_good']}/{s['trips_monitor']}/{s['trips_over']}")
