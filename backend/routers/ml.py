"""backend/routers/ml.py — anomaly detection, forecasting, compliance risk.
Thin wrappers around ml_engine.py (reused unmodified)."""
import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel

import ml_engine
from .. import db
from ..auth import TokenPayload, get_current_user

router = APIRouter(prefix="/ml", tags=["ml"])


def _records(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notna(df), None).to_dict("records")


class RowsRequest(BaseModel):
    rows: list[dict]


@router.post("/anomalies")
def anomalies(body: RowsRequest, _user: TokenPayload = Depends(get_current_user)):
    fdf = pd.DataFrame(body.rows)
    anom_rows, health = ml_engine.detect_anomalies(fdf)
    if health.empty:
        return {"ready": False, "rows": [], "summary": []}
    return {"ready": True, "rows": _records(anom_rows), "summary": _records(health)}


class SaveAnomaliesRequest(BaseModel):
    summary: list[dict]


@router.post("/anomalies/save")
def save_anomalies(body: SaveAnomaliesRequest, _user: TokenPayload = Depends(get_current_user)):
    recs = [{"bus_id": r["Bus_ID"], "score": float(r["Anomaly_rate"]),
             "payload": {"health": r["Health"], "days": int(r["Days"]),
                         "avg_co2_g_km": float(r["Avg_CO2_g_km"])}}
            for r in body.summary]
    result = db.save_ml_insights("anomaly", recs)
    return result


class ForecastRequest(BaseModel):
    rows: list[dict]        # [{Date, value}]
    value_col: str = "value"
    horizon_days: int = 30


@router.post("/forecast")
def forecast(body: ForecastRequest, _user: TokenPayload = Depends(get_current_user)):
    daily = pd.DataFrame(body.rows)
    fc = ml_engine.forecast_daily(daily, body.value_col, body.horizon_days)
    if fc.empty:
        return {"ready": False, "points": []}
    out = fc.copy()
    out["Date"] = out["Date"].astype(str)
    return {"ready": True, "points": _records(out)}


@router.post("/risk")
def risk(body: RowsRequest, _user: TokenPayload = Depends(get_current_user)):
    fdf = pd.DataFrame(body.rows)
    out = ml_engine.compliance_risk(fdf)
    if out.empty:
        return {"ready": False, "rows": []}
    return {"ready": True, "rows": _records(out)}


class SaveRiskRequest(BaseModel):
    rows: list[dict]


@router.post("/risk/save")
def save_risk(body: SaveRiskRequest, _user: TokenPayload = Depends(get_current_user)):
    recs = [{"bus_id": r["Bus_ID"], "score": float(r["Risk_score"]),
             "payload": {"band": r["Risk_band"], "breaches": int(r["Breaches_so_far"])}}
            for r in body.rows]
    result = db.save_ml_insights("risk", recs)
    return result
