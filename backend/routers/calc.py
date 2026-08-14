"""
backend/routers/calc.py — engine-recompute endpoints: Trip Inspector's
breakdown, Formula Explainer's step-by-step walkthrough, and the What-If
scenario simulator. All three re-run emissions_engine.py on the server —
the frontend never reimplements the math.
"""
import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel

import emissions_engine as em
from ..auth import TokenPayload, get_current_user

router = APIRouter(prefix="/calc", tags=["calc"])


# ── Trip Inspector: CO2 source breakdown for one row ──
class TripBreakdownRequest(BaseModel):
    row: dict
    methodology: str = "Hybrid"
    ambient_c: float = 28.0


@router.post("/trip-breakdown")
def trip_breakdown(body: TripBreakdownRequest, _user: TokenPayload = Depends(get_current_user)):
    return em.emission_breakdown(body.row, body.methodology, body.ambient_c)


# ── Formula Explainer: every multiplier/addend, with the row's real numbers ──
class FormulaStepsRequest(BaseModel):
    row: dict
    methodology: str = "Hybrid"
    ambient_c: float = 28.0


@router.post("/formula-steps")
def formula_steps(body: FormulaStepsRequest, _user: TokenPayload = Depends(get_current_user)):
    row = body.row
    methodology, ambient_c = body.methodology, body.ambient_c

    bus_cat, _ = em.normalize_category(str(row.get("Bus_Category", "")))
    fuel, _ = em.normalize_fuel(str(row.get("Fuel_Type", "")))
    distance = float(row.get("Route_Distance_km", 0) or 0)
    speed = float(row.get("Avg_Speed_kmh", 25) or 25)
    ridership = max(1, int(row.get("Ridership", 1) or 1))
    euro = str(row.get("Euro_Standard", em.DEFAULT_EURO))
    age = int(row.get("Vehicle_Age_years", 0) or 0)
    ac_on = str(row.get("AC_Status", "")).lower() in ("true", "1")
    num_trips = max(1, int(row.get("Num_Trips_Today", 1) or 1))
    engine_model = str(row.get("Engine_Model", ""))
    is_revenue = em.parse_revenue_trip(row.get("Revenue_Trip", "True"))

    fuel_profile = em.BASE_FACTORS.get(bus_cat, {}).get(fuel, em.FALLBACK_FACTORS)
    capacity = int(fuel_profile.get("capacity", 80))
    base_co2 = float(fuel_profile.get("CO2", 0.0))
    eng_corr = em.ENGINE_CO2_CORRECTION.get(engine_model, em.DEFAULT_ENGINE_CORRECTION)
    age_mults = em.age_deterioration(age, fuel)
    age_co2 = age_mults["CO2"]
    trip_km = distance / num_trips
    pax_per_trip = ridership / num_trips
    passenger_km = ridership * trip_km
    load_c = em._load_corr(pax_per_trip, capacity)

    steps = []

    if fuel == "Electric":
        kwh_per_km = float(fuel_profile.get("kwh_per_km", 1.5))
        total = kwh_per_km * distance * em.GRID_EF_KG_PER_KWH
        steps.append({
            "title": "Electric buses use Scope 2 grid intensity, not combustion factors",
            "formula": "CO2 (kg) = kWh/km × distance × Grid EF",
            "substitution": f"{kwh_per_km} kWh/km × {distance:.1f} km × {em.GRID_EF_KG_PER_KWH} kg/kWh",
            "result": f"{total:.3f} kg",
            "note": (f"Nigeria grid emission factor of {em.GRID_EF_KG_PER_KWH} kg CO₂e/kWh is IEA 2023's "
                     "regional estimate — applied because the bus itself has zero tailpipe emissions, "
                     "but the electricity that charged it didn't come from nowhere."),
        })
        return {"fuel": "Electric", "steps": steps, "total_kg": round(total, 3),
                "gauge": None, "capacity": capacity}

    ef_after_engine = base_co2 * eng_corr
    ef_after_age = ef_after_engine * age_co2

    steps.append({
        "title": "Base emission factor",
        "formula": "EF_base = BASE_FACTORS[category][fuel][CO2]",
        "substitution": f"BASE_FACTORS['{bus_cat}']['{fuel}']['CO2']",
        "result": f"{base_co2:.1f} g/km",
        "note": (f"Reference Euro III diesel/petrol/CNG/biogas factor for a {bus_cat} bus on {fuel}, "
                 f"from IPCC 2006 Tier 2 + COPERT V West-Africa calibration. Capacity assumed: {capacity} seats."),
    })
    steps.append({
        "title": "Engine model correction (CO₂ only)",
        "formula": "EF_1 = EF_base × EngineCorrection",
        "substitution": f"{base_co2:.1f} × {eng_corr:.2f} ({engine_model or 'no engine model — default 1.00'})",
        "result": f"{ef_after_engine:.1f} g/km",
        "note": None,
    })
    steps.append({
        "title": "Vehicle age deterioration",
        "formula": "EF_2 = EF_1 × (1 + 0.004 × age_years)",
        "substitution": f"{ef_after_engine:.1f} × (1 + 0.004 × {age}) = {ef_after_engine:.1f} × {age_co2:.3f}",
        "result": f"{ef_after_age:.1f} g/km",
        "note": f"+0.4%/year CO₂ degradation (COPERT model) — a {age}-year-old bus burns "
                f"{(age_co2 - 1) * 100:.1f}% more fuel per km than new, all else equal.",
    })

    use_speed = methodology == "COPERT"
    if use_speed:
        spd_factor = em._spd_co2(speed)
        hot_g = ef_after_age * spd_factor * distance
        steps.append({
            "title": "Hot running emissions over the route",
            "formula": "E_hot = EF_2 × f(v)/f(50) × distance,  f(v) = 1 + 25/v + v/400",
            "substitution": f"f_speed({speed:.0f} km/h) = {spd_factor:.3f} (normalised: =1.0 at 50 km/h); "
                             f"E_hot = {ef_after_age:.1f} × {spd_factor:.3f} × {distance:.1f} km",
            "result": f"{hot_g:.0f} g",
            "note": None,
        })
    else:
        hot_g = ef_after_age * distance
        note = None
        if methodology == "Hybrid":
            note = ("Hybrid methodology keeps CO₂ on the simpler IPCC distance-based formula — only NOx/PM "
                     "use the COPERT speed curve, since CO₂ tracks fuel burned far more linearly with "
                     "distance than with traffic speed.")
        steps.append({
            "title": "Hot running emissions over the route",
            "formula": "E_hot = EF_2 × distance",
            "substitution": f"{ef_after_age:.1f} g/km × {distance:.1f} km",
            "result": f"{hot_g:.0f} g",
            "note": note,
        })

    cold_mult = em.cold_start_multiplier("CO2", ambient_c)
    cold_km = min(trip_km, em.COLD_START_KM)
    cold_extra = ef_after_age * cold_km * (cold_mult - 1.0) * em.COLD_STARTS_PER_DAY
    steps.append({
        "title": "Cold start penalty (temperature-aware)",
        "formula": "E_cold = EF_2 × min(trip_km, 5) × (m(T) - 1) × starts/day",
        "substitution": f"chill = max(0, (30-{ambient_c})/30) → m(T)={cold_mult:.3f}; "
                         f"E_cold = {ef_after_age:.1f} × {cold_km:.1f} km × {cold_mult - 1:.3f} × "
                         f"{em.COLD_STARTS_PER_DAY} start/day",
        "result": f"{cold_extra:.0f} g",
        "note": (f"A cold engine over-emits for its first ~5 km, but buses running trips back-to-back "
                 f"stay warm — so the penalty is counted once per day, not once per trip. At {ambient_c}°C "
                 "ambient the effect is small: the multiplier shrinks linearly and vanishes at 30°C."),
    })

    idle_min = float(row.get("Idle_Minutes", em.DEFAULT_IDLE_MINUTES))
    idle_ef = em.IDLING_EF.get(bus_cat, {}).get(fuel, {}).get("CO2", 0.0)
    idle_g = idle_ef * idle_min
    steps.append({
        "title": "Idling",
        "formula": "E_idle = EF_idle × idle_minutes",
        "substitution": f"{idle_ef:.1f} g/min × {idle_min:.0f} min",
        "result": f"{idle_g:.0f} g",
        "note": None,
    })

    ac_extra = (hot_g + idle_g) * em.AC_UPLIFT_CO2 if ac_on else 0.0
    steps.append({
        "title": "A/C uplift",
        "formula": "E_ac = (E_hot + E_idle) × 0.08 (if A/C on)",
        "substitution": f"A/C status: {'ON' if ac_on else 'OFF'}",
        "result": f"{ac_extra:.0f} g" if ac_on else "0 g (not applied)",
        "note": None,
    })

    steps.append({
        "title": "Load factor correction",
        "formula": "LoadCorr = 1 + (min(pax/capacity, 1.2) - 0.5) × 0.08",
        "substitution": f"pax on board = {ridership}÷{num_trips} = {pax_per_trip:.0f}; "
                         f"pax/capacity = {pax_per_trip / capacity:.2f}",
        "result": f"{load_c:.4f}",
        "note": "A fuller bus weighs more and burns marginally more fuel — this nudges the total by a "
                "few percent in either direction depending on load.",
    })

    total_g = (hot_g + cold_extra + idle_g + ac_extra) * load_c
    steps.append({
        "title": "Total, and per-passenger figure",
        "formula": "Total = (E_hot + E_cold + E_idle + E_ac) × LoadCorr",
        "substitution": f"({hot_g:.0f} + {cold_extra:.0f} + {idle_g:.0f} + {ac_extra:.0f}) × {load_c:.4f}",
        "result": f"{total_g:.0f} g = {total_g / 1000:.3f} kg",
        "note": None,
    })

    gauge = None
    if is_revenue and passenger_km:
        gpkm = total_g / passenger_km
        thresholds = {"High Capacity": (30, 55), "Midi": (45, 75), "Mini": (60, 95)}.get(bus_cat, (40, 70))
        gauge = {"value": round(gpkm, 2), "good": thresholds[0], "monitor": thresholds[1]}
        steps.append({
            "title": "Total, and per-passenger figure (g/pkm)",
            "formula": "CO2 (g/pkm) = Total (g) / passenger-km",
            "substitution": f"passenger_km = {ridership} × {trip_km:.1f} km/trip = {passenger_km:,.0f} pkm",
            "result": f"{gpkm:.2f} g/pkm",
            "note": None,
        })
    elif not is_revenue:
        steps.append({
            "title": "Not a revenue trip",
            "formula": None, "substitution": None, "result": None,
            "note": "This wasn't a revenue trip (Revenue_Trip = 0/False), so it doesn't carry a g/pkm "
                    "compliance figure — only revenue trips are divided by ridership for the compliance "
                    "gauge, since deadheading/positioning runs have no fare-paying passengers.",
        })

    return {"fuel": fuel, "steps": steps, "total_kg": round(total_g / 1000, 3),
            "gauge": gauge, "capacity": capacity}


# ── What-If scenario simulator ──
class WhatIfRequest(BaseModel):
    rows: list[dict]                 # baseline rows (raw fields, as returned by /data/upload)
    methodology: str = "Hybrid"
    pollutants: list[str] = ["CO2", "NOx"]
    ambient_c: float = 28.0
    convert_n: int = 0
    convert_to: str = "CNG"          # "CNG" | "Electric"
    euro_target: str = "No change"   # "No change" | "Euro IV" | "Euro V" | "Euro VI"
    speed_gain: float = 0
    ac_policy: str = "No change"     # "No change" | "All A/C off" | "All A/C on"


@router.post("/whatif")
def whatif(body: WhatIfRequest, _user: TokenPayload = Depends(get_current_user)):
    fdf = pd.DataFrame(body.rows)
    base_cols = ["Bus_Category", "Fuel_Type", "Route_Distance_km", "Avg_Speed_kmh",
                 "Ridership", "Num_Trips_Today", "Euro_Standard", "Vehicle_Age_years",
                 "AC_Status", "Engine_Model", "Revenue_Trip", "Idle_Minutes"]
    sim = fdf[[c for c in base_cols if c in fdf.columns] + ["Bus_ID"]].copy()

    changed = pd.Series(False, index=sim.index)
    if body.convert_n > 0:
        worst = (fdf[fdf["Fuel_Type"] == "Diesel"].groupby("Bus_ID")["CO2_kg"]
                    .sum().sort_values(ascending=False).head(body.convert_n).index)
        m = sim["Bus_ID"].isin(worst)
        sim.loc[m, "Fuel_Type"] = body.convert_to
        if body.convert_to == "Electric":
            sim.loc[m & (sim["Bus_Category"] == "Mini"), "Bus_Category"] = "Midi"
        changed |= m

    if body.euro_target != "No change":
        order = {"Euro II": 2, "Euro III": 3, "Euro IV": 4, "Euro V": 5, "Euro VI": 6}
        tgt = order[body.euro_target]
        m = sim["Euro_Standard"].map(order).fillna(3) < tgt
        sim.loc[m, "Euro_Standard"] = body.euro_target
        changed |= m

    if body.speed_gain > 0:
        sim["Avg_Speed_kmh"] = pd.to_numeric(sim["Avg_Speed_kmh"], errors="coerce").fillna(25) + body.speed_gain
        changed |= True

    if body.ac_policy != "No change":
        sim["AC_Status"] = (body.ac_policy == "All A/C on")
        changed |= True

    n_changed = int(changed.sum()) if isinstance(changed, pd.Series) else len(sim)

    if isinstance(changed, pd.Series) and 0 < changed.sum() < len(sim):
        redo = sim[changed]
        res = redo.apply(lambda r: em.calculate_row(r, body.methodology, body.pollutants, body.ambient_c), axis=1)
        scen = {}
        for p in body.pollutants:
            col = f"{p}_kg"
            if col in fdf.columns and col in res.columns:
                scen[p] = float(fdf.loc[~changed, col].sum()) + float(res[col].sum())
    elif changed.sum() == 0:
        scen = {p: float(fdf[f"{p}_kg"].sum()) for p in body.pollutants if f"{p}_kg" in fdf.columns}
    else:
        res = sim.apply(lambda r: em.calculate_row(r, body.methodology, body.pollutants, body.ambient_c), axis=1)
        scen = {p: float(res[f"{p}_kg"].sum()) for p in body.pollutants if f"{p}_kg" in res.columns}

    baseline = {p: float(fdf[f"{p}_kg"].sum()) for p in body.pollutants if f"{p}_kg" in fdf.columns}
    return {"baseline": baseline, "scenario": scen, "rows_modified": n_changed, "rows_total": len(sim)}
