"""
backend/routers/data.py — manifest upload, database load, and admin-gated
delete/wipe endpoints.

All endpoints except /db-status require a valid access token; the
delete/wipe endpoints additionally require the admin role AND (for the
full wipe) a typed "DELETE" confirmation in the request body — replacing
app.py's single shared plaintext delete password (app.py:590-612).
"""
import json

import pandas as pd
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from .. import db
from ..auth import TokenPayload, get_current_user, require_admin
from ..config import get_settings
from ..pipeline import EXPECTED_COLS, NEW_COLS, UploadError, clean_and_calculate, fuzzy_rename, read_raw_file

router = APIRouter(prefix="/data", tags=["data"])


def _rows_out(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of records (NaN -> None, dates -> str)."""
    d = df.copy()
    for col in d.columns:
        if d[col].dtype == object or str(d[col].dtype).startswith("date"):
            d[col] = d[col].astype(str).where(d[col].notna(), None)
    return json.loads(d.to_json(orient="records", date_format="iso"))


@router.get("/db-status")
def db_status():
    state, message = db.db_status()
    return {"state": state, "message": message}


@router.post("/upload")
def upload(
    files: list[UploadFile],
    method: str = Form("Hybrid"),
    pollutants: str = Form("CO2,NOx"),
    ambient: float = Form(28.0),
    basis: str = Form("passenger"),
    _user: TokenPayload = Depends(get_current_user),
):
    settings = get_settings()
    pollutant_list = [p.strip() for p in pollutants.split(",") if p.strip()]

    frames, file_log, auto_log = [], [], {}
    for f in files:
        fbytes = f.file.read()
        try:
            raw = read_raw_file(f.filename, fbytes, settings.max_upload_mb, settings.max_upload_rows)
        except UploadError as e:
            file_log.append({"name": f.filename, "rows": 0, "status": "error", "detail": str(e)})
            continue

        renamed, log, still_missing = fuzzy_rename(raw, EXPECTED_COLS, NEW_COLS)
        if still_missing:
            file_log.append({
                "name": f.filename, "rows": 0, "status": "error",
                "detail": f"Missing: {', '.join(still_missing)}",
                "cols": raw.columns.tolist(),
            })
            continue

        renamed["Source_File"] = f.filename
        frames.append(renamed)
        auto_log.update(log)
        file_log.append({"name": f.filename, "rows": len(renamed), "status": "ok", "detail": ""})

    if not frames:
        return {"rows": [], "file_log": file_log, "auto_log": auto_log, "row_count": 0}

    merged = pd.concat(frames, ignore_index=True, sort=False)
    calculated = clean_and_calculate(merged, method, pollutant_list, ambient, basis)
    rows = _rows_out(calculated)
    return {"rows": rows, "file_log": file_log, "auto_log": auto_log, "row_count": len(rows)}


@router.post("/load-db")
def load_db(
    method: str = Form("Hybrid"),
    pollutants: str = Form("CO2,NOx"),
    ambient: float = Form(28.0),
    basis: str = Form("passenger"),
    _user: TokenPayload = Depends(get_current_user),
):
    pollutant_list = [p.strip() for p in pollutants.split(",") if p.strip()]
    raw = db.load_trips()
    if raw is None or len(raw) == 0:
        return {"rows": [], "row_count": 0}
    calculated = clean_and_calculate(raw, method, pollutant_list, ambient, basis)
    return {"rows": _rows_out(calculated), "row_count": len(calculated)}


@router.get("/db-uploads")
def db_uploads(_user: TokenPayload = Depends(get_current_user)):
    return {"uploads": db.list_uploads()}


@router.delete("/db-uploads/{source_file}")
def delete_upload(source_file: str, _user: TokenPayload = Depends(require_admin)):
    result = db.delete_upload(source_file)
    if result["error"]:
        raise HTTPException(400, result["error"])
    return {"deleted": True}


@router.post("/db-wipe")
def db_wipe(confirm: str = Form(...), _user: TokenPayload = Depends(require_admin)):
    """Requires the caller to be an admin AND to have typed the literal
    string 'DELETE' in the confirm field — no single shared password can
    trigger this by itself anymore."""
    result = db.delete_all_trips(confirm)
    if result["error"]:
        raise HTTPException(400, result["error"])
    return {"deleted": True}


@router.post("/snapshot")
def snapshot(
    rows: list[dict],
    methodology: str = "Hybrid",
    ambient_c: float = 28.0,
    _user: TokenPayload = Depends(get_current_user),
):
    df = pd.DataFrame(rows)
    result = db.save_emissions_snapshot(df, methodology, ambient_c)
    if result["error"]:
        raise HTTPException(400, result["error"])
    return result
