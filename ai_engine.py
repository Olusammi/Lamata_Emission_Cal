"""
ai_engine.py — Gemini-powered assistant for the Fleet Emissions Console
=======================================================================
Design rules (they make the free tier workable AND the answers honest):

  1. Gemini NARRATES, pandas CALCULATES. We never ask the model to do
     arithmetic. We compute exact aggregates locally into a compact
     "fact pack" (~2-3k tokens) and the model interprets it. Raw trip
     rows never leave the server.
  2. Every response is cached on (question, data fingerprint) — repeat
     questions cost zero API calls.
  3. Graceful absence: no key configured, quota hit (429), or network
     down → a clear message, and the rest of the console is untouched.

Free-tier notes: Flash / Flash-Lite models, ~10-15 requests/min and a
few hundred per day. Prompts on the free tier may be used by Google to
improve its products — hence rule 1: aggregates only.
"""

import time
import requests as _rq
import streamlit as st

# Flash-Lite has the most generous free-tier limits; switch to
# "gemini-2.5-flash" if you prefer better prose over higher quota.
MODEL = "gemini-2.5-flash-lite"
_FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash"]
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

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


# ──────────────────────────────────────────────────────────────
# CONFIG / TRANSPORT
# ──────────────────────────────────────────────────────────────
def get_key():
    try:
        return st.secrets["gemini"]["api_key"]
    except Exception:
        return None


def is_configured() -> bool:
    return bool(get_key())


def _call(prompt: str, system: str = SYSTEM_STYLE,
          temperature: float = 0.4, max_tokens: int = 900) -> tuple[str, bool]:
    """One generateContent call with backoff. Returns (text, ok)."""
    key = get_key()
    if not key:
        return "AI assistant is not configured — add a [gemini] api_key to secrets.", False

    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature,
                             "maxOutputTokens": max_tokens},
    }
    last_err = ""
    for model in _FALLBACK_MODELS:
        for attempt in range(3):
            try:
                r = _rq.post(_URL.format(model=model),
                             params={"key": key}, json=body, timeout=30)
                if r.status_code == 429:
                    # Free-tier rate limit — brief exponential backoff.
                    time.sleep(2 ** attempt)
                    last_err = "rate limit"
                    continue
                if r.status_code == 404:
                    last_err = f"{model} unavailable"
                    break                       # try next model
                r.raise_for_status()
                data = r.json()
                parts = data["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    return text, True
                last_err = "empty response"
            except Exception as e:
                last_err = str(e)[:120]
                time.sleep(1)
    if last_err == "rate limit":
        return ("The free Gemini quota is momentarily exhausted (rate limit). "
                "Wait a minute and try again — previous answers stay cached."), False
    return f"AI request failed ({last_err}). The console itself is unaffected.", False


# ──────────────────────────────────────────────────────────────
# FACT PACK — exact local aggregates the model is allowed to use
# ──────────────────────────────────────────────────────────────
def build_fact_pack(fdf, pollutants, basis, methodology, ambient_c,
                    corridor_fn=None, health_summary=None) -> str:
    """Compact, exact statistics. Everything the model may cite."""
    import pandas as pd
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

    # Per category / fuel / Euro — small exact tables
    for col, name in [("Bus_Category", "CATEGORY"), ("Fuel_Type", "FUEL"),
                      ("Euro_Standard", "EURO")]:
        if col in fdf.columns and "CO2_kg" in fdf.columns:
            g = fdf.groupby(col).agg(t=("CO2_kg", lambda x: x.sum()/1000),
                                     i=("CO2_g_pkm", "mean"),
                                     n=("Bus_ID", "nunique")).round(1)
            L.append(f"{name} (CO2 t | mean {unit} | buses): " +
                     "; ".join(f"{ix}: {r.t} | {r.i} | {int(r.n)}"
                               for ix, r in g.iterrows()))

    # Operators — best & worst by intensity (min 5 buses to be fair)
    if "Operator" in fdf.columns and "CO2_g_pkm" in fdf.columns:
        og = (fdf.groupby("Operator")
                 .agg(i=("CO2_g_pkm", "mean"), t=("CO2_kg", lambda x: x.sum()/1000),
                      n=("Bus_ID", "nunique"))
                 .query("n >= 5").round(1))
        if len(og):
            worst = og.sort_values("i", ascending=False).head(5)
            best = og.sort_values("i").head(5)
            L.append(f"WORST OPERATORS by intensity ({unit}|t|buses): " +
                     "; ".join(f"{ix}: {r.i}|{r.t}|{int(r.n)}" for ix, r in worst.iterrows()))
            L.append(f"BEST OPERATORS by intensity ({unit}|t|buses): " +
                     "; ".join(f"{ix}: {r.i}|{r.t}|{int(r.n)}" for ix, r in best.iterrows()))

    # Top individual emitters
    if "CO2_kg" in fdf.columns:
        tb = (fdf.groupby("Bus_ID")["CO2_kg"].sum().nlargest(5) / 1000).round(2)
        L.append("TOP 5 CO2 BUSES (t): " + "; ".join(f"{k}: {v}" for k, v in tb.items()))

    # Corridors
    if corridor_fn is not None:
        try:
            agg = corridor_fn(fdf, "CO2").round(1)
            L.append("CORRIDORS (CO2 t | mean intensity): " +
                     "; ".join(f"{r.Corridor}: {r.Total_kg/1000:.1f} | {r.Eff}"
                               for _, r in agg.iterrows()))
        except Exception:
            pass

    # Month over month
    m = fdf.copy()
    m["Month"] = pd.to_datetime(m["Date"], errors="coerce").dt.to_period("M").astype(str)
    mg = m.groupby("Month")["CO2_kg"].sum() / 1000
    if len(mg) >= 2:
        L.append("MONTHLY CO2 (t): " + "; ".join(f"{k}: {v:,.1f}" for k, v in mg.round(1).items()))

    # Fleet-health digest, if the caller has it
    if health_summary is not None and len(health_summary):
        inv = health_summary[health_summary["Health"] == "Investigate"]
        L.append(f"FLEET HEALTH: {len(inv)} buses flagged Investigate. Worst: " +
                 "; ".join(f"{r.Bus_ID} (rate {r.Anomaly_rate})"
                           for _, r in inv.head(5).iterrows()))

    L.append("NOTE: figures above are exact and pre-computed. Cite them as-is.")
    return "\n".join(L)


def fingerprint(fdf) -> str:
    """Cheap data fingerprint for cache keys."""
    try:
        return f"{len(fdf)}-{round(float(fdf['CO2_kg'].sum()), 1)}-{fdf['Date'].astype(str).max()}"
    except Exception:
        return str(len(fdf))


# ──────────────────────────────────────────────────────────────
# CACHED FEATURES — repeat calls are free
# ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def generate_insights(fact_pack: str, _fp: str) -> tuple[str, bool]:
    return _call(
        "FACT PACK:\n" + fact_pack +
        "\n\nTASK: Give the 4-5 most decision-relevant observations for a fleet "
        "manager: biggest emission drivers, notable outliers, compliance risks, "
        "and ONE concrete recommended action. Bullet points, each one sentence, "
        "each citing a number from the fact pack.")


@st.cache_data(ttl=3600, show_spinner=False)
def answer_question(fact_pack: str, question: str, history: str, _fp: str) -> tuple[str, bool]:
    return _call(
        "FACT PACK:\n" + fact_pack +
        ("\n\nRECENT CONVERSATION:\n" + history if history else "") +
        "\n\nUSER QUESTION: " + question +
        "\n\nAnswer from the fact pack only. If it can't be answered from these "
        "aggregates, say what's missing and where in the console to look.")


@st.cache_data(ttl=3600, show_spinner=False)
def explain_anomaly(bus_desc: str, _fp: str) -> tuple[str, bool]:
    return _call(
        "A machine-learning check flagged this bus. Its statistics:\n" + bus_desc +
        "\n\nTASK: In 3-4 sentences, give the most plausible operational or "
        "maintenance explanations for this emission pattern and what a workshop "
        "should check first. Be practical, not alarmist. Do not invent numbers.",
        temperature=0.5)


@st.cache_data(ttl=3600, show_spinner=False)
def report_narrative(fact_pack: str, _fp: str) -> tuple[str, bool]:
    return _call(
        "FACT PACK:\n" + fact_pack +
        "\n\nTASK: Write a 4-6 sentence executive summary paragraph for a "
        "monthly fleet emissions report. Formal, factual, cites the key totals "
        "and the single most important trend or risk. No bullet points.")
