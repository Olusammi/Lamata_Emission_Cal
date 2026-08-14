"""
backend/ai.py — Gemini-powered assistant, ported from ai_engine.py.

Same design rules as the original:
  1. Gemini NARRATES, pandas CALCULATES — the fact pack is exact
     pre-computed aggregates; the model never does arithmetic.
  2. Every response is cached on (question, data fingerprint).
  3. Graceful absence: no key, quota hit, or network failure → a clear
     message, nothing else breaks.

Two changes from the original:
  - No Streamlit: the API key comes from backend/config.py (env var),
    and st.cache_data is replaced with a tiny in-memory TTL cache.
  - The caller (frontend, via React) is responsible for escaping/rendering
    this text safely — the API returns plain text/markdown, never HTML,
    so there is nothing here for a browser to execute.
"""
import time

import pandas as pd
import requests as _rq

from .config import get_settings

_PREFERRED = [
    "gemini-3.1-flash-lite", "gemini-flash-lite-latest",
    "gemini-3.5-flash", "gemini-flash-latest",
    "gemini-2.5-flash-lite", "gemini-2.5-flash",
]
_BASE = "https://generativelanguage.googleapis.com/v1beta"
_URL = _BASE + "/models/{model}:generateContent"

SYSTEM_STYLE = (
    "You are the built-in analyst of a transit fleet emissions console. "
    "You are given pre-computed, exact aggregate statistics (the FACT PACK). "
    "Rules: (1) Use ONLY numbers present in the fact pack — never invent, "
    "extrapolate or re-derive figures. (2) If the fact pack cannot answer "
    "the question, say so plainly and suggest which module or filter would. "
    "(3) Be concise and concrete: short paragraphs or tight bullet lists, "
    "no headers, no fluff. (4) Emissions going DOWN is good. Lower g/pkm "
    "or g/km is better. (5) When useful, name the module where the user "
    "can see the detail (Dashboard, Fleet Intelligence, Pollutant Engine, "
    "Bus Efficiency, Corridor Map, Fleet Health, Forecast, Data Quality, "
    "What-If, Trip Inspector, Formula Explainer, Deep Search)."
)


# ── tiny in-memory TTL cache (replaces st.cache_data) ──
class _TTLCache:
    def __init__(self):
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str, ttl: int):
        hit = self._store.get(key)
        if hit is None:
            return None
        ts, val = hit
        if time.time() - ts > ttl:
            self._store.pop(key, None)
            return None
        return val

    def set(self, key: str, val: object):
        self._store[key] = (time.time(), val)


_model_cache = _TTLCache()
_response_cache = _TTLCache()


def get_key() -> str | None:
    return get_settings().gemini_api_key or None


def is_configured() -> bool:
    return bool(get_key())


def _discover_models() -> list[str]:
    key = get_key()
    cached = _model_cache.get(key or "none", ttl=86400)
    if cached is not None:
        return cached
    models, page_token = [], None
    try:
        for _ in range(5):
            params = {"key": key, "pageSize": 200}
            if page_token:
                params["pageToken"] = page_token
            r = _rq.get(_BASE + "/models", params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            for m in data.get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    models.append(m["name"].split("/")[-1])
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    except Exception:
        models = []
    _model_cache.set(key or "none", models)
    return models


def _candidate_models() -> list[str]:
    avail = _discover_models()
    if not avail:
        return _PREFERRED
    ordered = [m for m in _PREFERRED if m in avail]
    _skip = ("image", "tts", "audio", "live", "embed", "veo", "imagen", "robotics")
    extra = sorted(m for m in avail
                   if "flash" in m and m not in ordered and not any(x in m for x in _skip))
    picked = ordered + extra
    return picked[:5] if picked else _PREFERRED


def _call(prompt: str, system: str = SYSTEM_STYLE,
          temperature: float = 0.4, max_tokens: int = 900) -> tuple[str, bool, str]:
    """Returns (text, ok, model_used)."""
    key = get_key()
    if not key:
        return "AI assistant is not configured — set GEMINI_API_KEY.", False, ""

    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    last_err = ""
    for model in _candidate_models():
        for attempt in range(3):
            try:
                r = _rq.post(_URL.format(model=model), params={"key": key}, json=body, timeout=30)
                if r.status_code == 429:
                    time.sleep(2 ** attempt)
                    last_err = "rate limit"
                    continue
                if r.status_code == 404:
                    last_err = f"{model} unavailable"
                    break
                r.raise_for_status()
                data = r.json()
                parts = data["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    return text, True, model
                last_err = "empty response"
            except Exception as e:
                last_err = str(e)[:120]
                time.sleep(1)
    if last_err == "rate limit":
        return ("The free Gemini quota is momentarily exhausted (rate limit). "
                "Wait a minute and try again — previous answers stay cached."), False, ""
    tried = ", ".join(_candidate_models())
    return f"AI request failed ({last_err}). Models tried: {tried}. The console itself is unaffected.", False, ""


def build_fact_pack(rows: list[dict], pollutants: list[str], basis: str,
                     methodology: str, ambient_c: float,
                     corridor_agg: list[dict] | None = None,
                     health_summary: list[dict] | None = None) -> str:
    """Compact, exact statistics. Everything the model may cite.
    rows: computed trip records (same shape /data/upload returns)."""
    fdf = pd.DataFrame(rows)
    L = []
    unit = "g/pkm" if basis == "passenger" else "g/km"
    L.append(f"PERIOD: {fdf['Date'].astype(str).min()} to {fdf['Date'].astype(str).max()}"
             f" | rows(bus-days): {len(fdf):,} | buses: {fdf['Bus_ID'].nunique():,}"
             f" | operators: {fdf['Operator'].nunique()}")
    L.append(f"SETTINGS: methodology={methodology}, basis=per {basis} ({unit}), "
             f"ambient={ambient_c}C. Engine v4.")

    if "CO2_kg" in fdf.columns and "CO2" in pollutants:
        L.append(f"TOTAL CO2: {fdf['CO2_kg'].sum()/1000:,.1f} t | "
                 f"mean intensity: {fdf['CO2_g_pkm'].mean():.1f} {unit} | "
                 f"median: {fdf['CO2_g_pkm'].median():.1f} {unit}")
    for p in ("NOx", "PM"):
        if f"{p}_kg" in fdf.columns and p in pollutants:
            L.append(f"TOTAL {p}: {fdf[f'{p}_kg'].sum():,.1f} kg")

    if "Compliance" in fdf.columns:
        c = fdf["Compliance"].value_counts()
        L.append("COMPLIANCE rows: " + ", ".join(f"{k}={int(v):,}" for k, v in c.items()))

    for col, name in [("Bus_Category", "CATEGORY"), ("Fuel_Type", "FUEL"), ("Euro_Standard", "EURO")]:
        if col in fdf.columns and "CO2_kg" in fdf.columns:
            g = fdf.groupby(col).agg(t=("CO2_kg", lambda x: x.sum() / 1000),
                                     i=("CO2_g_pkm", "mean"),
                                     n=("Bus_ID", "nunique")).round(1)
            L.append(f"{name} (CO2 t | mean {unit} | buses): " +
                     "; ".join(f"{ix}: {r.t} | {r.i} | {int(r.n)}" for ix, r in g.iterrows()))

    if "Operator" in fdf.columns and "CO2_g_pkm" in fdf.columns:
        og = (fdf.groupby("Operator")
                 .agg(i=("CO2_g_pkm", "mean"), t=("CO2_kg", lambda x: x.sum() / 1000),
                      n=("Bus_ID", "nunique"))
                 .query("n >= 5").round(1))
        if len(og):
            worst = og.sort_values("i", ascending=False).head(5)
            best = og.sort_values("i").head(5)
            L.append(f"WORST OPERATORS by intensity ({unit}|t|buses): " +
                     "; ".join(f"{ix}: {r.i}|{r.t}|{int(r.n)}" for ix, r in worst.iterrows()))
            L.append(f"BEST OPERATORS by intensity ({unit}|t|buses): " +
                     "; ".join(f"{ix}: {r.i}|{r.t}|{int(r.n)}" for ix, r in best.iterrows()))

    if "CO2_kg" in fdf.columns:
        tb = (fdf.groupby("Bus_ID")["CO2_kg"].sum().nlargest(5) / 1000).round(2)
        L.append("TOP 5 CO2 BUSES (t): " + "; ".join(f"{k}: {v}" for k, v in tb.items()))

    if corridor_agg:
        L.append("CORRIDORS (CO2 t | mean intensity): " +
                 "; ".join(f"{r['Corridor']}: {r['Total_kg']/1000:.1f} | {r['Eff']}" for r in corridor_agg))

    m = fdf.copy()
    m["Month"] = pd.to_datetime(m["Date"], errors="coerce").dt.to_period("M").astype(str)
    mg = m.groupby("Month")["CO2_kg"].sum() / 1000
    if len(mg) >= 2:
        L.append("MONTHLY CO2 (t): " + "; ".join(f"{k}: {v:,.1f}" for k, v in mg.round(1).items()))

    if health_summary:
        inv = [r for r in health_summary if r.get("Health") == "Investigate"]
        L.append(f"FLEET HEALTH: {len(inv)} buses flagged Investigate. Worst: " +
                 "; ".join(f"{r['Bus_ID']} (rate {r['Anomaly_rate']})" for r in inv[:5]))

    L.append("NOTE: figures above are exact and pre-computed. Cite them as-is.")
    return "\n".join(L)


def fingerprint(rows: list[dict]) -> str:
    try:
        fdf = pd.DataFrame(rows)
        return f"{len(fdf)}-{round(float(fdf['CO2_kg'].sum()), 1)}-{fdf['Date'].astype(str).max()}"
    except Exception:
        return str(len(rows))


def _cached_call(cache_key: str, prompt: str, **kwargs) -> tuple[str, bool, str]:
    hit = _response_cache.get(cache_key, ttl=3600)
    if hit is not None:
        return hit
    result = _call(prompt, **kwargs)
    _response_cache.set(cache_key, result)
    return result


def generate_insights(fact_pack: str, fp: str) -> tuple[str, bool, str]:
    return _cached_call(
        f"insights:{fp}",
        "FACT PACK:\n" + fact_pack +
        "\n\nTASK: Give the 4-5 most decision-relevant observations for a fleet "
        "manager: biggest emission drivers, notable outliers, compliance risks, "
        "and ONE concrete recommended action. Bullet points, each one sentence, "
        "each citing a number from the fact pack.")


def answer_question(fact_pack: str, question: str, history: str, fp: str) -> tuple[str, bool, str]:
    return _cached_call(
        f"ask:{fp}:{hash(question)}:{hash(history)}",
        "FACT PACK:\n" + fact_pack +
        ("\n\nRECENT CONVERSATION:\n" + history if history else "") +
        "\n\nUSER QUESTION: " + question +
        "\n\nAnswer from the fact pack only. If it can't be answered from these "
        "aggregates, say what's missing and where in the console to look.")


def explain_anomaly(bus_desc: str, fp: str) -> tuple[str, bool, str]:
    return _cached_call(
        f"explain:{fp}:{hash(bus_desc)}",
        "A machine-learning check flagged this bus. Its statistics:\n" + bus_desc +
        "\n\nTASK: In 3-4 sentences, give the most plausible operational or "
        "maintenance explanations for this emission pattern and what a workshop "
        "should check first. Be practical, not alarmist. Do not invent numbers.",
        temperature=0.5)


def report_narrative(fact_pack: str, fp: str) -> tuple[str, bool, str]:
    return _cached_call(
        f"report:{fp}",
        "FACT PACK:\n" + fact_pack +
        "\n\nTASK: Write a 4-6 sentence executive summary paragraph for a "
        "monthly fleet emissions report. Formal, factual, cites the key totals "
        "and the single most important trend or risk. No bullet points.")
