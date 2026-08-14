"""backend/routers/ai.py — floating assistant endpoints. The client sends
the currently-filtered dataset + settings; the server builds the fact
pack and calls Gemini, exactly mirroring ai_engine.py's design (Gemini
narrates, pandas calculates)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import ai as ai_engine
from ..auth import TokenPayload, get_current_user

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def status():
    return {"configured": ai_engine.is_configured()}


class FactPackContext(BaseModel):
    rows: list[dict]
    pollutants: list[str] = ["CO2", "NOx"]
    basis: str = "passenger"
    methodology: str = "Hybrid"
    ambient_c: float = 28.0
    corridor_agg: list[dict] | None = None
    health_summary: list[dict] | None = None


def _pack_and_fp(ctx: FactPackContext) -> tuple[str, str]:
    pack = ai_engine.build_fact_pack(
        ctx.rows, ctx.pollutants, ctx.basis, ctx.methodology, ctx.ambient_c,
        corridor_agg=ctx.corridor_agg, health_summary=ctx.health_summary)
    return pack, ai_engine.fingerprint(ctx.rows)


@router.post("/insights")
def insights(ctx: FactPackContext, _user: TokenPayload = Depends(get_current_user)):
    pack, fp = _pack_and_fp(ctx)
    text, ok, model = ai_engine.generate_insights(pack, fp)
    return {"text": text, "ok": ok, "model": model}


class AskRequest(BaseModel):
    context: FactPackContext
    question: str
    history: str = ""


@router.post("/ask")
def ask(body: AskRequest, _user: TokenPayload = Depends(get_current_user)):
    pack, fp = _pack_and_fp(body.context)
    text, ok, model = ai_engine.answer_question(pack, body.question, body.history, fp)
    return {"text": text, "ok": ok, "model": model}


class ExplainAnomalyRequest(BaseModel):
    bus_desc: str
    fingerprint: str


@router.post("/explain-anomaly")
def explain_anomaly(body: ExplainAnomalyRequest, _user: TokenPayload = Depends(get_current_user)):
    text, ok, model = ai_engine.explain_anomaly(body.bus_desc, body.fingerprint)
    return {"text": text, "ok": ok, "model": model}


@router.post("/report-narrative")
def report_narrative(ctx: FactPackContext, _user: TokenPayload = Depends(get_current_user)):
    pack, fp = _pack_and_fp(ctx)
    text, ok, model = ai_engine.report_narrative(pack, fp)
    return {"text": text, "ok": ok, "model": model}
