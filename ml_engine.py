"""
ml_engine.py — Machine-learning intelligence for the LAMATA portal
==================================================================
Three tools, all scikit-learn / plain statistics (no GPUs, trains in
seconds on ~20k rows), all written to be explainable:

  1. detect_anomalies()  — Fleet Health: which buses are behaving
     unlike themselves and unlike their peers? (IsolationForest +
     per-bus z-scores). Early warning for maintenance issues.

  2. forecast_daily()    — projects daily fleet/corridor CO₂ and
     ridership forward with confidence bands. Deliberately a simple,
     transparent model: linear trend + weekday pattern. With only a
     month or two of history, anything fancier just overfits.

  3. compliance_risk()   — scores every bus's probability of going
     Over Limit, from its attributes and operating pattern
     (gradient-boosted trees).
"""

import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════
# 1. ANOMALY DETECTION — "Fleet Health"
# ══════════════════════════════════════════════════════════════
def detect_anomalies(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Two complementary checks per bus-day row:

      • self_z    — how far is today's CO₂/km from THIS bus's own
                    average, in standard deviations? Catches a bus
                    drifting away from its own normal (worn injectors,
                    dragging brakes, tyre pressure...).
      • iso_score — IsolationForest novelty score against the bus's
                    PEER GROUP (same category + fuel). Catches buses
                    that were always odd, not just newly odd.

    A row is flagged when self_z > 2.5 OR the forest marks it as an
    outlier. Returns (row_level_df, bus_summary_df).
    """
    from sklearn.ensemble import IsolationForest

    d = df.copy()
    need = ["Bus_ID", "CO2_g_km", "Avg_Speed_kmh", "load_factor"]
    for c in need:
        if c not in d.columns:
            d[c] = 0.0
    d = d[d["CO2_g_km"] > 0].copy()
    if len(d) < 50:
        return pd.DataFrame(), pd.DataFrame()

    # ── Check 1: each bus vs its own history ──
    g = d.groupby("Bus_ID")["CO2_g_km"]
    mu, sd = g.transform("mean"), g.transform("std").replace(0, np.nan)
    d["self_z"] = ((d["CO2_g_km"] - mu) / sd).fillna(0.0)

    # ── Check 2: each row vs its peer group (category + fuel) ──
    d["iso_outlier"] = False
    d["iso_score"] = 0.0
    feats = ["CO2_g_km", "Avg_Speed_kmh", "load_factor"]
    if "NOx_kg" in d.columns:
        feats.append("NOx_kg")
    for _, grp in d.groupby(["Bus_Category", "Fuel_Type"], dropna=False):
        if len(grp) < 40:               # too small a peer group to judge
            continue
        X = grp[feats].fillna(0.0).values
        forest = IsolationForest(n_estimators=150, contamination=0.03,
                                 random_state=42)
        pred = forest.fit_predict(X)                 # -1 = outlier
        d.loc[grp.index, "iso_outlier"] = pred == -1
        d.loc[grp.index, "iso_score"] = -forest.score_samples(X)  # higher = odder

    d["is_anomaly"] = (d["self_z"].abs() > 2.5) | d["iso_outlier"]

    # ── Bus-level summary for the league table ──
    summary = (d.groupby("Bus_ID")
                 .agg(Operator=("Operator", "last"),
                      Category=("Bus_Category", "last"),
                      Fuel=("Fuel_Type", "last"),
                      Days=("CO2_g_km", "count"),
                      Anomalous_days=("is_anomaly", "sum"),
                      Avg_CO2_g_km=("CO2_g_km", "mean"),
                      Worst_self_z=("self_z", lambda s: s.abs().max()),
                      Avg_iso_score=("iso_score", "mean"))
                 .reset_index())
    summary["Anomaly_rate"] = (summary["Anomalous_days"] / summary["Days"]).round(3)
    summary["Health"] = np.select(
        [summary["Days"] < 5,                       # not enough history to judge
         summary["Anomaly_rate"] >= 0.20,
         summary["Anomaly_rate"] >= 0.08],
        ["Insufficient data", "Investigate", "Watch"], default="Healthy")
    summary = summary.sort_values(["Anomaly_rate", "Worst_self_z"],
                                  ascending=False).round(2)
    return d, summary


# ══════════════════════════════════════════════════════════════
# 2. FORECASTING — daily CO₂ / ridership with confidence bands
# ══════════════════════════════════════════════════════════════
def forecast_daily(daily: pd.DataFrame, value_col: str,
                   horizon_days: int = 30) -> pd.DataFrame:
    """
    daily: DataFrame with columns ['Date', value_col], one row per day.

    Model (deliberately transparent):
        value(t) = linear trend(t) + weekday effect + noise
    The band is ±1.96 × the standard deviation of what the model
    couldn't explain in the history — an honest "this is how wrong
    we've typically been" interval.

    Returns Date, forecast, lo, hi, is_history.
    """
    h = daily.dropna().copy()
    h["Date"] = pd.to_datetime(h["Date"])
    h = h.sort_values("Date").reset_index(drop=True)
    if len(h) < 14:
        return pd.DataFrame()

    t = np.arange(len(h), dtype=float)
    y = h[value_col].astype(float).values

    # Linear trend by least squares:
    slope, intercept = np.polyfit(t, y, 1)
    trend = intercept + slope * t

    # Weekday pattern from what the trend leaves over:
    resid = y - trend
    h["dow"] = h["Date"].dt.dayofweek
    dow_effect = pd.Series(resid).groupby(h["dow"]).mean()
    fitted = trend + h["dow"].map(dow_effect).values
    noise_sd = float(np.std(y - fitted))

    # Project forward:
    future_dates = pd.date_range(h["Date"].iloc[-1] + pd.Timedelta(days=1),
                                 periods=horizon_days)
    tf = np.arange(len(h), len(h) + horizon_days, dtype=float)
    fut_trend = intercept + slope * tf
    fut = fut_trend + pd.Series(future_dates.dayofweek).map(dow_effect).fillna(0).values
    fut = np.maximum(fut, 0)

    hist = pd.DataFrame({"Date": h["Date"], "forecast": fitted,
                         "lo": fitted - 1.96 * noise_sd,
                         "hi": fitted + 1.96 * noise_sd,
                         "actual": y, "is_history": True})
    futr = pd.DataFrame({"Date": future_dates, "forecast": fut,
                         "lo": np.maximum(fut - 1.96 * noise_sd, 0),
                         "hi": fut + 1.96 * noise_sd,
                         "actual": np.nan, "is_history": False})
    return pd.concat([hist, futr], ignore_index=True)


# ══════════════════════════════════════════════════════════════
# 3. COMPLIANCE RISK — which buses will breach next?
# ══════════════════════════════════════════════════════════════
_EURO_ORD = {"Euro II": 2, "Euro III": 3, "Euro IV": 4, "Euro V": 5, "Euro VI": 6}


def compliance_risk(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trains a gradient-boosted classifier: given a bus-day's attributes
    (age, Euro class, category, fuel, speed, load, trips), what's the
    probability it lands Over Limit? Then averages per bus.

    Honest framing: with one/two months of data this is a risk SCORE
    learned from current patterns, not a crystal ball — its value is
    ranking which buses to inspect first, and showing WHICH factors
    drive the risk (feature importances).
    """
    from sklearn.ensemble import HistGradientBoostingClassifier

    d = df.dropna(subset=["Compliance"]).copy()
    d = d[d["Compliance"].isin(["Good", "Monitor", "Over Limit"])]
    if len(d) < 200 or (d["Compliance"] == "Over Limit").sum() < 10:
        return pd.DataFrame()

    d["y"] = (d["Compliance"] == "Over Limit").astype(int)
    d["euro_ord"] = d["Euro_Standard"].map(_EURO_ORD).fillna(3)
    d["cat_code"] = d["Bus_Category"].astype("category").cat.codes
    d["fuel_code"] = d["Fuel_Type"].astype("category").cat.codes

    feats = ["Vehicle_Age_years", "euro_ord", "cat_code", "fuel_code",
             "Avg_Speed_kmh", "load_factor", "Num_Trips_Today",
             "Route_Distance_km"]
    feats = [f for f in feats if f in d.columns]
    X = d[feats].fillna(0.0).values
    y = d["y"].values

    model = HistGradientBoostingClassifier(max_iter=200, random_state=42)
    model.fit(X, y)
    d["risk"] = model.predict_proba(X)[:, 1]

    out = (d.groupby("Bus_ID")
             .agg(Operator=("Operator", "last"),
                  Category=("Bus_Category", "last"),
                  Euro=("Euro_Standard", "last"),
                  Age=("Vehicle_Age_years", "last"),
                  Days=("y", "count"),
                  Breaches_so_far=("y", "sum"),
                  Risk_score=("risk", "mean"))
             .reset_index()
             .sort_values("Risk_score", ascending=False))
    out["Risk_score"] = out["Risk_score"].round(3)
    out["Risk_band"] = np.select(
        [out["Risk_score"] >= 0.5, out["Risk_score"] >= 0.2],
        ["High", "Elevated"], default="Low")
    return out
