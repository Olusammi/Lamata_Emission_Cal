"""backend/routers/corridors.py — static geometry + per-corridor aggregation."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import corridors as corridors_mod
from ..auth import TokenPayload, get_current_user

router = APIRouter(prefix="/corridors", tags=["corridors"])


@router.get("/geometry")
def geometry():
    return {
        "corridors": {name: {"path": c["path"]} for name, c in corridors_mod.CORRIDORS.items()},
        "center": {"lat": corridors_mod.FLEET_LAT, "lon": corridors_mod.FLEET_LON},
        "map_styles": corridors_mod.MAP_STYLES,
    }


class AggregateRequest(BaseModel):
    rows: list[dict]
    pollutant: str = "CO2"


@router.post("/aggregate")
def aggregate(body: AggregateRequest, _user: TokenPayload = Depends(get_current_user)):
    return {"corridors": corridors_mod.corridor_aggregate(body.rows, body.pollutant)}
