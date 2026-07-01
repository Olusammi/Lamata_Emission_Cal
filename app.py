"""
LAMATA Emissions — Operations Center  (full Streamlit build)
============================================================
Seven-module public emissions console, driven by emissions_engine.py:

    Dashboard          fleet-wide overview + compliance
    Fleet Intelligence engine families, age deterioration, fuel mix
    Pollutant Engine   methodology comparison + speed/Euro factor curves
    Bus Efficiency     g CO2/pkm vs thresholds + recommended actions
    Trip Inspector     single-trip CO2 waterfall (hot/cold/idle/AC/grid)
    Formula Explainer  every multiplier & addend with your real numbers
    Deep Search        filter + export the full calculated manifest

Run:
    pip install streamlit pandas numpy plotly
    streamlit run app.py

Expects Final_Bus_Data.csv next to this file (or upload it in the sidebar).
"""

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from emissions_engine import (
    process, fleet_summary, trip_breakdown,
    METHODS, THRESH, FACT, EUROM, _speed_factor,
    GRID_CO2_KG_PER_KWH, AC_UPLIFT,
)

# ----------------------------------------------------------------------
# Theme
# ----------------------------------------------------------------------
st.set_page_config(page_title="LAMATA Emissions — Operations Center",
                   page_icon="🚌", layout="wide")

BG, BG2, PANEL, PANEL2 = "#0a0e0d", "#0d1312", "#101715", "#16201d"
LINE, LINE2 = "#1e2a27", "#2c3c38"
TEXT, TEXT2, TEXT3 = "#eaf2ef", "#8ba39c", "#5d746d"
GOOD, MONITOR, OVER = "#3ef2a0", "#ffc24b", "#ff6363"
INFO, VIOLET, ACCENT = "#5cc8ff", "#c9a0ff", "#3ef2a0"
STATUS_COLOR = {"Good": GOOD, "Monitor": MONITOR, "Over": OVER}
FUEL_COLOR = {"Diesel": "#f2a65a", "Petrol": "#ff8da3", "CNG": "#5cc8ff", "Electric": "#3ef2a0"}
EURO_COLOR = {"Euro II": OVER, "Euro III": MONITOR, "Euro IV": INFO, "Euro V": GOOD, "Euro VI": ACCENT}

st.markdown(f"""
<style>
  .stApp {{ background:{BG}; color:{TEXT}; font-family:'Archivo',sans-serif; }}
  section[data-testid="stSidebar"] {{ background:{BG2}; border-right:1px solid {LINE}; }}
  #MainMenu, footer, header {{ visibility:hidden; }}
  .block-container {{ padding-top:1.1rem; max-width:1500px; }}
  h1,h2,h3,h4 {{ color:{TEXT}; font-family:'Archivo',sans-serif; }}
  .mono {{ font-family:'JetBrains Mono',monospace; }}
  .eyebrow {{ font-family:'JetBrains Mono',monospace; font-size:11px; letter-spacing:.16em; color:{ACCENT}; }}
  .kpi {{ background:{PANEL}; border:1px solid {LINE}; border-top:2px solid {ACCENT};
          border-radius:10px; padding:14px 16px; }}
  .kpi .lab {{ font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:.08em; color:{TEXT3}; }}
  .kpi .val {{ font-family:'JetBrains Mono',monospace; font-size:24px; font-weight:700; color:{TEXT}; margin-top:6px; }}
  .kpi .sub {{ font-size:12px; color:{TEXT2}; margin-top:2px; }}
  .pill {{ display:inline-block; font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700;
           border-radius:6px; padding:5px 12px; letter-spacing:.06em; }}
  .card {{ background:{PANEL}; border:1px solid {LINE}; border-radius:12px; padding:16px 18px; margin-bottom:6px; }}
  .stepbox {{ background:{PANEL2}; border:1px solid {LINE2}; border-radius:8px; padding:10px 14px;
              margin-bottom:7px; font-family:'JetBrains Mono',monospace; font-size:13px; }}
  .stepbox b {{ color:{ACCENT}; }}
  .stDataFrame {{ border:1px solid {LINE}; border-radius:8px; }}
</style>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Data loading (cached)  — computes all three methods once
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_all(file):
    df = pd.read_csv(file)
    out = {}
    for m in METHODS:
        trips, buses = process(df, m)
        out[m] = {"trips": trips, "buses": buses}
    return out


def kpi(col, lab, val, sub, tone=ACCENT):
    col.markdown(
        f"<div class='kpi' style='border-top-color:{tone}'>"
        f"<div class='lab'>{lab}</div><div class='val'>{val}</div><div class='sub'>{sub}</div></div>",
        unsafe_allow_html=True)


def plot(fig, h=320, legend=False):
    fig.update_layout(height=h, margin=dict(l=8, r=8, t=8, b=8),
                      paper_bgcolor=PANEL, plot_bgcolor=PANEL, font_color=TEXT2,
                      showlegend=legend, legend=dict(font=dict(color=TEXT2)),
                      xaxis=dict(gridcolor=LINE, zerolinecolor=LINE),
                      yaxis=dict(gridcolor=LINE, zerolinecolor=LINE))
    st.plotly_chart(fig, use_container_width=True)


def section(title, sub=""):
    st.markdown(f"<div class='eyebrow'>{sub}</div><h3 style='margin:2px 0 10px'>{title}</h3>",
                unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Sidebar — data source + navigation + filters
# ----------------------------------------------------------------------
st.sidebar.markdown("<div class='eyebrow'>LAMATA · LAGOS METROPOLITAN</div>"
                    "<h3 style='margin:2px 0 14px'>Operations Center</h3>", unsafe_allow_html=True)

uploaded = st.sidebar.file_uploader("Trip CSV", type="csv")
source = uploaded if uploaded is not None else "Final_Bus_Data.csv"
try:
    DATA = load_all(source)
except FileNotFoundError:
    st.error("Final_Bus_Data.csv not found — upload the trip CSV in the sidebar.")
    st.stop()

MODULES = ["Dashboard", "Fleet Intelligence", "Pollutant Engine", "Bus Efficiency",
           "Trip Inspector", "Formula Explainer", "Deep Search"]
module = st.sidebar.radio("Module", MODULES, index=0)

st.sidebar.markdown("---")
method = st.sidebar.selectbox("Methodology", list(METHODS), index=0)
pollutant = st.sidebar.radio("Pollutant", ["CO2", "NOx", "PM"], horizontal=True)

buses_all = DATA[method]["buses"]
trips_all = DATA[method]["trips"]

operators = ["All"] + sorted(buses_all["Operator"].unique().tolist())
operator = st.sidebar.selectbox("Operator", operators, index=0)
fuels = ["All"] + sorted(buses_all["Fuel"].unique().tolist())
fuel = st.sidebar.selectbox("Fuel", fuels, index=0)
statuses = st.sidebar.multiselect("Status", ["Good", "Monitor", "Over"], default=[])

buses = buses_all.copy()
if operator != "All":
    buses = buses[buses["Operator"] == operator]
if fuel != "All":
    buses = buses[buses["Fuel"] == fuel]
if statuses:
    buses = buses[buses["Status"].isin(statuses)]
kept_ids = set(buses["Bus_ID"])
trips = trips_all[trips_all["Bus_ID"].isin(kept_ids)]

pol_kg = {"CO2": "CO2_kg", "NOx": "NOx_kg", "PM": "PM_kg"}[pollutant]
pol_g = {"CO2": "CO2_g", "NOx": "NOx_g", "PM": "PM_g"}[pollutant]
pol_label = "CO₂" if pollutant == "CO2" else pollutant
s = fleet_summary(buses) if len(buses) else fleet_summary(buses_all)

st.sidebar.markdown("---")
st.sidebar.caption(f"{len(buses):,} of {len(buses_all):,} buses in view · method {method}")


# ----------------------------------------------------------------------
# Header (shared)
# ----------------------------------------------------------------------
st.markdown(
    f"<div class='eyebrow'>PUBLIC EMISSIONS CONSOLE · {module.upper()} "
    f"&nbsp;·&nbsp; METHOD {method} · REPORTING MAY 2026</div>", unsafe_allow_html=True)

if len(buses) == 0:
    st.warning("No buses match the current filters. Widen the filters in the sidebar.")
    st.stop()


# ======================================================================
# 1 · DASHBOARD
# ======================================================================
def view_dashboard():
    st.markdown("## Fleet Emissions Overview")
    c = st.columns(6)
    kpi(c[0], "TRIPS / MONTH", f"{s['trips']:,}", f"{s['buses']:,} buses in fleet", INFO)
    kpi(c[1], "PASSENGERS", f"{s['passengers']/1000:,.0f}k", "monthly boardings", GOOD)
    kpi(c[2], "TOTAL CO₂", f"{s['co2_tonnes']:,.0f} t", f"{s['co2_tonnes']*1000:,.0f} kg", ACCENT)
    kpi(c[3], "FLEET EFFICIENCY", f"{s['fleet_efficiency_gpkm']:.1f}", "g CO₂ / pkm", VIOLET)
    kpi(c[4], "BUSES OVER LIMIT", f"{s['buses_over_limit']:,}", "flagged for review", OVER)
    kpi(c[5], "ELECTRIC BUSES", f"{s['ev_count']:,}", "zero tailpipe", GOOD)
    st.write("")

    hero_val = buses[pol_kg].sum()
    hero = f"{hero_val:,.0f} kg" if pollutant == "PM" else f"{hero_val/1000:,.0f} t"
    left, right = st.columns([1.4, 1])
    with left:
        st.markdown(
            f"<div class='card'><div class='mono' style='font-size:11px;color:{TEXT3}'>"
            f"TOTAL {pol_label} — FLEET, THIS MONTH</div>"
            f"<div class='mono' style='font-size:52px;font-weight:700'>{hero}</div>"
            f"<div style='color:{TEXT2};font-size:13px'>Across {s['buses']:,} buses · "
            f"{s['passengers']/1e6:,.1f}M passenger boardings</div></div>", unsafe_allow_html=True)
    with right:
        eff = s["fleet_efficiency_gpkm"]
        band = "GOOD" if eff <= 45 else "MONITOR" if eff <= 80 else "OVER LIMIT"
        bc = GOOD if eff <= 45 else MONITOR if eff <= 80 else OVER
        gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=eff,
            number={"suffix": " g/pkm", "font": {"color": TEXT, "size": 24}},
            gauge={"axis": {"range": [0, 110], "tickcolor": TEXT3}, "bar": {"color": bc},
                   "bgcolor": PANEL, "borderwidth": 0,
                   "steps": [{"range": [0, 45], "color": "rgba(62,242,160,.18)"},
                             {"range": [45, 80], "color": "rgba(255,194,75,.18)"},
                             {"range": [80, 110], "color": "rgba(255,99,99,.18)"}]}))
        gauge.update_layout(height=200, margin=dict(l=10, r=10, t=6, b=0),
                            paper_bgcolor=PANEL, font_color=TEXT)
        st.plotly_chart(gauge, use_container_width=True)
        st.markdown(f"<span class='pill' style='color:{bc};background:{bc}22'>FLEET {band}</span>",
                    unsafe_allow_html=True)

    ca, cb = st.columns(2)
    with ca:
        section(f"{pol_label} by Operator", "TOP 8 EMITTERS")
        op = buses.groupby("Operator")[pol_kg].sum().sort_values(ascending=False).head(8)
        unit = op.values if pollutant == "PM" else op.values / 1000.0
        fig = go.Figure(go.Bar(x=unit, y=op.index, orientation="h", marker_color=INFO,
                               text=[f"{v:,.0f}" for v in unit], textposition="outside"))
        fig.update_yaxes(autorange="reversed")
        plot(fig)
    with cb:
        section("Intensity by Euro Class", "AVG g CO₂ / pkm")
        order = ["Euro II", "Euro III", "Euro IV", "Euro V", "Euro VI"]
        ev = buses[buses["gpkm"] > 0].groupby("Euro")["gpkm"].mean()
        ev = ev.reindex([e for e in order if e in ev.index])
        fig = go.Figure(go.Bar(x=ev.index, y=ev.values,
                               marker_color=[EURO_COLOR.get(e, INFO) for e in ev.index],
                               text=[f"{v:.0f}" for v in ev.values], textposition="outside"))
        plot(fig)

    if "Date" in trips.columns:
        section(f"Daily {pol_label} Output", method.upper())
        day = pd.to_datetime(trips["Date"], errors="coerce").dt.day
        daily = trips.assign(day=day).dropna(subset=["day"]).groupby("day")[pol_g].sum()
        daily = daily / 1e6 if pollutant != "PM" else daily / 1e3  # t / kg
        fig = go.Figure(go.Bar(x=daily.index, y=daily.values, marker_color=ACCENT))
        plot(fig, 220)

    cc, cd = st.columns([1, 1.5])
    with cc:
        section("Trip Compliance", "SHARE OF TRIPS")
        vals = [s["trips_good"], s["trips_monitor"], s["trips_over"]]
        fig = go.Figure(go.Pie(labels=["Good", "Monitor", "Over"], values=vals, hole=.62,
                               marker_colors=[GOOD, MONITOR, OVER], sort=False))
        plot(fig, 300, legend=True)
    with cd:
        section("Operator Leaderboard", "RANKED BY FLEET EFFICIENCY")
        lb = _leaderboard(buses)
        st.dataframe(lb, use_container_width=True, height=340)

    st.caption("IPCC 2006 Tier 2 · COPERT V speed functions · Euro II–VI multipliers · "
               "age deterioration · A/C load · grid electricity for EVs · efficiency = g CO₂ per passenger-km.")


def _leaderboard(bdf):
    grp = bdf.groupby("Operator")
    lb = pd.DataFrame({
        "Buses": grp.size(),
        "Passengers": grp["Passengers"].sum(),
        "wsum": grp.apply(lambda g: (g["gpkm"] * g["Passengers"]).sum()),
    })
    lb["g CO₂/pkm"] = (lb["wsum"] / lb["Passengers"].clip(lower=1)).round(1)
    lb = lb[lb["Buses"] >= 2].sort_values("g CO₂/pkm").head(12)
    lb["Status"] = np.where(lb["g CO₂/pkm"] <= 45, "Good",
                     np.where(lb["g CO₂/pkm"] <= 80, "Monitor", "Over"))
    lb = lb.reset_index()[["Operator", "Buses", "g CO₂/pkm", "Status"]]
    lb.index = np.arange(1, len(lb) + 1)
    return lb


# ======================================================================
# 2 · FLEET INTELLIGENCE
# ======================================================================
def view_fleet():
    st.markdown("## Fleet Intelligence")
    st.caption("How Euro standard, vehicle age, fuel and A/C compound to drive each vehicle's emission profile.")

    c = st.columns(4)
    kpi(c[0], "AVG FLEET AGE", f"{s['avg_age']:.1f} yr", "years in service", MONITOR)
    kpi(c[1], "EURO VI SHARE", f"{100*(buses['Euro']=='Euro VI').mean():.0f}%", "cleanest class", GOOD)
    kpi(c[2], "A/C EQUIPPED", f"{100*buses['AC'].mean():.0f}%", "of buses in view", INFO)
    kpi(c[3], "ELECTRIC", f"{s['ev_count']}", "battery buses", ACCENT)
    st.write("")

    ca, cb = st.columns([1.3, 1])
    with ca:
        section("Age vs Efficiency", "EACH DOT IS A BUS · SIZE = PASSENGERS")
        fig = go.Figure()
        for fu, col in FUEL_COLOR.items():
            sub = buses[(buses["Fuel"] == fu) & (buses["gpkm"] > 0)]
            if len(sub):
                fig.add_trace(go.Scatter(
                    x=sub["Age"], y=sub["gpkm"], mode="markers", name=fu,
                    marker=dict(color=col, size=np.clip(sub["Passengers"]/sub["Passengers"].max()*22, 5, 24),
                                line=dict(width=0), opacity=.8)))
        fig.add_hline(y=45, line=dict(color=GOOD, dash="dot"))
        fig.add_hline(y=80, line=dict(color=OVER, dash="dot"))
        fig.update_xaxes(title="Vehicle age (years)")
        fig.update_yaxes(title="g CO₂ / pkm")
        plot(fig, 360, legend=True)
    with cb:
        section("Fuel Mix", "BUSES BY FUEL")
        fc = buses["Fuel"].value_counts()
        fig = go.Figure(go.Pie(labels=fc.index, values=fc.values, hole=.6,
                               marker_colors=[FUEL_COLOR.get(f, INFO) for f in fc.index]))
        plot(fig, 360, legend=True)

    section("Engine Families", "AVG g CO₂/pkm BY EURO CLASS × FUEL")
    order = ["Euro II", "Euro III", "Euro IV", "Euro V", "Euro VI"]
    fam = buses[buses["gpkm"] > 0]
    piv = fam.pivot_table(index="Euro", columns="Fuel", values="gpkm", aggfunc="mean")
    piv = piv.reindex([e for e in order if e in piv.index])
    z = piv.values
    fig = go.Figure(go.Heatmap(
        z=z, x=list(piv.columns), y=list(piv.index),
        colorscale=[[0, GOOD], [0.5, MONITOR], [1, OVER]],
        text=[[("" if np.isnan(v) else f"{v:.0f}") for v in row] for row in z],
        texttemplate="%{text}", textfont={"color": "#04120c", "size": 13},
        colorbar=dict(title="g/pkm", tickfont=dict(color=TEXT2))))
    plot(fig, 300)

    section("Fleet Register", "PER-BUS DETAIL")
    tbl = buses[["Bus_ID", "Operator", "Category", "Fuel", "Euro", "Age", "AC",
                 "Passengers", "gpkm", "CO2_kg", "Status"]].copy()
    tbl["Age"] = tbl["Age"].round(0).astype(int)
    tbl = tbl.rename(columns={"gpkm": "g CO₂/pkm", "CO2_kg": "CO₂ kg", "AC": "A/C"})
    tbl["g CO₂/pkm"] = tbl["g CO₂/pkm"].round(1)
    tbl["CO₂ kg"] = tbl["CO₂ kg"].round(0)
    st.dataframe(tbl.sort_values("g CO₂/pkm", ascending=False),
                 use_container_width=True, height=380, hide_index=True)


# ======================================================================
# 3 · POLLUTANT ENGINE
# ======================================================================
def view_pollutant():
    st.markdown("## Pollutant Engine")
    st.caption("CO₂ via IPCC Tier 2 stoichiometric; NOx & PM via COPERT V speed functions × Euro-class "
               "multiplier × age deterioration. Compare how the three methodologies score the same fleet.")

    # method comparison on the current filter selection
    ids = kept_ids
    rows = []
    for m in METHODS:
        bm = DATA[m]["buses"]
        bm = bm[bm["Bus_ID"].isin(ids)]
        rows.append({"Method": m, "CO₂ (t)": bm["CO2_kg"].sum()/1000,
                     "NOx (t)": bm["NOx_kg"].sum()/1000, "PM (kg)": bm["PM_kg"].sum()})
    comp = pd.DataFrame(rows).set_index("Method")

    ca, cb, cc = st.columns(3)
    for col, (metric, unit, color) in zip(
            [ca, cb, cc],
            [("CO₂ (t)", "tonnes", ACCENT), ("NOx (t)", "tonnes", INFO), ("PM (kg)", "kg", VIOLET)]):
        with col:
            section(metric.split(" ")[0], f"TOTAL BY METHOD · {unit}")
            fig = go.Figure(go.Bar(x=comp.index, y=comp[metric], marker_color=color,
                                   text=[f"{v:,.1f}" for v in comp[metric]], textposition="outside"))
            plot(fig, 240)

    ca, cb = st.columns(2)
    with ca:
        section("Speed Correction Functions", "COPERT V · MULTIPLIER vs SPEED")
        sp = np.arange(5, 101, 1)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sp, y=_speed_factor("CO2", sp), name="CO₂", line=dict(color=ACCENT)))
        fig.add_trace(go.Scatter(x=sp, y=_speed_factor("NOx", sp), name="NOx", line=dict(color=INFO)))
        fig.add_trace(go.Scatter(x=sp, y=_speed_factor("PM", sp), name="PM", line=dict(color=VIOLET)))
        fig.update_xaxes(title="Avg speed (km/h)")
        fig.update_yaxes(title="factor ×")
        plot(fig, 320, legend=True)
    with cb:
        section("Euro-Class Multipliers", "RELATIVE TO EURO III = 1.0")
        order = ["Euro II", "Euro III", "Euro IV", "Euro V", "Euro VI"]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=order, y=[EUROM[e]["NOx"] for e in order], name="NOx", marker_color=INFO))
        fig.add_trace(go.Bar(x=order, y=[EUROM[e]["PM"] for e in order], name="PM", marker_color=VIOLET))
        plot(fig, 320, legend=True)

    section("Base Emission Factors", "g/km · BY CATEGORY & FUEL")
    recs = []
    for cat, fuels_ in FACT.items():
        for fu, v in fuels_.items():
            recs.append({"Category": cat, "Fuel": fu, "CO₂ g/km": v["CO2"],
                         "NOx g/km": v["NOx"], "PM g/km": v["PM"], "Capacity": v["cap"],
                         "kWh/km": v.get("kwh", "—")})
    st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)
    st.caption(f"Electric buses: grid electricity × {GRID_CO2_KG_PER_KWH} kg CO₂/kWh. "
               f"A/C load adds {int(AC_UPLIFT*100)}% to hot-running CO₂. IPCC method holds all speed factors at 1.0.")


# ======================================================================
# 4 · BUS EFFICIENCY
# ======================================================================
def _recommend(row):
    if row["Status"] == "Good":
        return "Compliant — maintain service"
    tips = []
    if row["Fuel"] in ("Diesel", "Petrol") and row["Euro"] in ("Euro II", "Euro III"):
        tips.append("prioritise Euro VI / electric replacement")
    if row["Age"] >= 10:
        tips.append("aged unit — schedule engine overhaul")
    if row["AC"]:
        tips.append("review A/C load management")
    if row["gpkm"] > 0 and row["Passengers"] > 0:
        tips.append("raise load factor on this route")
    return "; ".join(tips[:2]) if tips else "reschedule to raise avg speed"


def view_efficiency():
    st.markdown("## Bus Efficiency")
    st.caption("Efficiency in grams CO₂ per passenger-kilometre against per-category compliance thresholds, "
               "with recommended actions for flagged vehicles.")

    c = st.columns(4)
    gd = (buses["Status"] == "Good").sum()
    mo = (buses["Status"] == "Monitor").sum()
    ov = (buses["Status"] == "Over").sum()
    kpi(c[0], "COMPLIANT", f"{gd:,}", f"{100*gd/len(buses):.0f}% of fleet", GOOD)
    kpi(c[1], "MONITOR", f"{mo:,}", f"{100*mo/len(buses):.0f}% of fleet", MONITOR)
    kpi(c[2], "OVER LIMIT", f"{ov:,}", f"{100*ov/len(buses):.0f}% of fleet", OVER)
    kpi(c[3], "FLEET EFFICIENCY", f"{s['fleet_efficiency_gpkm']:.1f}", "g CO₂ / pkm", VIOLET)
    st.write("")

    ca, cb = st.columns([1.3, 1])
    with ca:
        section("Efficiency Distribution", "BUSES BY g CO₂/pkm · COLOURED BY STATUS")
        fig = go.Figure()
        for st_name, col in STATUS_COLOR.items():
            sub = buses[buses["Status"] == st_name]
            if len(sub):
                fig.add_trace(go.Histogram(x=sub["gpkm"], name=st_name, marker_color=col,
                                           xbins=dict(size=5), opacity=.85))
        fig.update_layout(barmode="stack")
        fig.update_xaxes(title="g CO₂ / pkm", range=[0, 160])
        plot(fig, 340, legend=True)
    with cb:
        section("Compliance by Category", "STACKED SHARE")
        cats = ["High Capacity", "Midi", "Mini"]
        fig = go.Figure()
        for st_name, col in STATUS_COLOR.items():
            vals = [((buses["Category"] == c) & (buses["Status"] == st_name)).sum() for c in cats]
            fig.add_trace(go.Bar(x=cats, y=vals, name=st_name, marker_color=col))
        fig.update_layout(barmode="stack")
        plot(fig, 340, legend=True)

    section("Recommended Actions", "FLAGGED VEHICLES · MONITOR & OVER")
    flagged = buses[buses["Status"] != "Good"].copy()
    if len(flagged) == 0:
        st.success("Every bus in the current view is compliant. 🎉")
    else:
        flagged["Age"] = flagged["Age"].round(0).astype(int)
        flagged["Action"] = flagged.apply(_recommend, axis=1)
        out = flagged.sort_values("gpkm", ascending=False)[
            ["Bus_ID", "Operator", "Category", "Fuel", "Euro", "Age", "gpkm", "Status", "Action"]]
        out = out.rename(columns={"gpkm": "g CO₂/pkm"})
        out["g CO₂/pkm"] = out["g CO₂/pkm"].round(1)
        st.dataframe(out, use_container_width=True, height=380, hide_index=True)


# ======================================================================
# Shared trip picker for Inspector + Formula Explainer
# ======================================================================
def _pick_trip():
    ops = sorted(trips["Operator"].unique().tolist())
    csel = st.columns([1, 1, 2])
    with csel[0]:
        op = st.selectbox("Operator", ops, key="ti_op")
    bids = sorted(trips[trips["Operator"] == op]["Bus_ID"].unique().tolist())
    with csel[1]:
        bid = st.selectbox("Bus", bids, key="ti_bus")
    tr = trips[trips["Bus_ID"] == bid].reset_index(drop=True)
    labels = [f"Trip {i+1} · {r.get('Route_Name','route')} · "
              f"{r['dist']:.1f} km @ {r['spd']:.0f} km/h" for i, r in tr.iterrows()]
    with csel[2]:
        idx = st.selectbox("Trip record", range(len(tr)),
                           format_func=lambda i: labels[i], key="ti_trip")
    row = tr.iloc[idx]
    rec = {"cat": row["cat"], "fuel": row["fuel"], "euro": row["euro"], "age": row["age"],
           "dist": row["dist"], "spd": row["spd"], "rider": row["rider"],
           "trips": row["trips"], "ac": bool(row["ac"])}
    return row, rec


# ======================================================================
# 5 · TRIP INSPECTOR
# ======================================================================
def view_inspector():
    st.markdown("## Trip Inspector")
    st.caption("Full single-trip breakdown — hot running, cold start, idling, A/C load, and grid electricity for EVs.")
    row, rec = _pick_trip()
    b = trip_breakdown(rec, method)

    meta = st.columns(6)
    kpi(meta[0], "CATEGORY", rec["cat"], rec["fuel"], INFO)
    kpi(meta[1], "EURO", rec["euro"], f"{rec['age']:.0f} yr old", MONITOR)
    kpi(meta[2], "DISTANCE", f"{rec['dist']:.1f} km", f"{rec['spd']:.0f} km/h avg", VIOLET)
    kpi(meta[3], "RIDERSHIP", f"{rec['rider']:.0f}", f"cap {b['cap']:.0f} · load {b['load']:.2f}×", GOOD)
    kpi(meta[4], "A/C", "ON" if rec["ac"] else "OFF", "load uplift" if rec["ac"] else "no uplift", INFO)
    kpi(meta[5], "STATUS", b["status"], f"{b['gpkm']:.1f} g/pkm", STATUS_COLOR[b["status"]])
    st.write("")

    ca, cb = st.columns([1.5, 1])
    with ca:
        section("CO₂ Build-up", "GRAMS · THIS TRIP")
        comp = b["components"]
        names = list(comp.keys())
        vals = [comp[n] for n in names]
        if b["ev"]:
            fig = go.Figure(go.Bar(x=names, y=vals, marker_color=GOOD,
                                   text=[f"{v:,.0f}" for v in vals], textposition="outside"))
        else:
            fig = go.Figure(go.Waterfall(
                orientation="v", x=names + ["Total"],
                measure=["relative"]*len(names) + ["total"],
                y=vals + [None],
                text=[f"{v:,.0f}" for v in vals] + [f"{sum(vals):,.0f}"],
                textposition="outside",
                connector={"line": {"color": LINE2}},
                increasing={"marker": {"color": INFO}},
                totals={"marker": {"color": ACCENT}}))
        fig.update_yaxes(title="grams CO₂")
        plot(fig, 340)
    with cb:
        section("Other Pollutants", "THIS TRIP")
        st.markdown(
            f"<div class='card'>"
            f"<div class='mono' style='font-size:12px;color:{TEXT3}'>CO₂</div>"
            f"<div class='mono' style='font-size:30px;font-weight:700;color:{ACCENT}'>{b['co2_g']/1000:,.2f} kg</div>"
            f"<div class='mono' style='font-size:12px;color:{TEXT3};margin-top:12px'>NOx</div>"
            f"<div class='mono' style='font-size:22px;font-weight:700;color:{INFO}'>{b['nox_g']:,.1f} g</div>"
            f"<div class='mono' style='font-size:12px;color:{TEXT3};margin-top:12px'>PM</div>"
            f"<div class='mono' style='font-size:22px;font-weight:700;color:{VIOLET}'>{b['pm_g']:,.2f} g</div>"
            f"</div>", unsafe_allow_html=True)
        if b["ev"]:
            st.info(f"Electric bus — {b['grid_kwh']:.1f} kWh drawn from the grid "
                    f"@ {GRID_CO2_KG_PER_KWH} kg CO₂/kWh. Zero tailpipe NOx & PM.")


# ======================================================================
# 6 · FORMULA EXPLAINER
# ======================================================================
def view_formula():
    st.markdown("## Formula Explainer")
    st.caption("Every multiplier and addend the engine applies to a trip — with your data's actual numbers "
               "substituted in.")
    row, rec = _pick_trip()
    b = trip_breakdown(rec, method)

    st.markdown(f"#### CO₂  —  {rec['cat']} · {rec['fuel']} · {rec['euro']} · {method}")
    for label, formula, value, unit in b["co2_steps"]:
        vtxt = f"{value:,.3f}" if unit == "×" else f"{value:,.1f}"
        st.markdown(
            f"<div class='stepbox'><b>{label}</b> &nbsp;=&nbsp; {formula} "
            f"&nbsp;→&nbsp; <b>{vtxt} {unit}</b></div>", unsafe_allow_html=True)

    if not b["ev"]:
        st.markdown("#### NOx & PM  —  hot-running only")
        nd, pd_ = b["nox_detail"], b["pm_detail"]
        st.markdown(
            f"<div class='stepbox'><b>NOx</b> = {nd['base']:g} g/km × Euro {nd['euro']:g} "
            f"× age {nd['age']:.3f} × speed {nd['speed']:.3f} × {rec['dist']:.1f} km × load {b['load']:.3f} "
            f"→ <b>{b['nox_g']:,.1f} g</b></div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='stepbox'><b>PM</b> = {pd_['base']:g} g/km × Euro {pd_['euro']:g} "
            f"× age {pd_['age']:.3f} × speed {pd_['speed']:.3f} × {rec['dist']:.1f} km × load {b['load']:.3f} "
            f"→ <b>{b['pm_g']:,.2f} g</b></div>", unsafe_allow_html=True)

    g, mn = b["thresh"]
    st.markdown("#### Efficiency & compliance")
    st.markdown(
        f"<div class='stepbox'><b>g CO₂/pkm</b> = {b['co2_g']:,.0f} g ÷ "
        f"({rec['rider']:.0f} riders × {rec['dist']:.1f} km = {b['pass_km']:,.0f} pkm) "
        f"→ <b>{b['gpkm']:.1f} g/pkm</b></div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='stepbox'>Category thresholds ({rec['cat']}): Good ≤ {g} · Monitor ≤ {mn} · Over &gt; {mn} "
        f"→ <b style='color:{STATUS_COLOR[b['status']]}'>{b['status'].upper()}</b></div>",
        unsafe_allow_html=True)


# ======================================================================
# 7 · DEEP SEARCH
# ======================================================================
def view_search():
    st.markdown("## Deep Search")
    st.caption("Filter and export the full calculated manifest across all attributes and pollutants.")

    f = st.columns(4)
    with f[0]:
        cats = st.multiselect("Category", sorted(buses_all["Category"].unique()), default=[])
    with f[1]:
        euros = st.multiselect("Euro", sorted(buses_all["Euro"].unique()), default=[])
    with f[2]:
        amax = st.slider("Max age (yr)", 0, int(buses_all["Age"].max()) + 1,
                         int(buses_all["Age"].max()) + 1)
    with f[3]:
        emin = st.slider("Min g CO₂/pkm", 0, 200, 0)

    m = buses.copy()
    if cats:
        m = m[m["Category"].isin(cats)]
    if euros:
        m = m[m["Euro"].isin(euros)]
    m = m[(m["Age"] <= amax) & (m["gpkm"] >= emin)]

    cols = ["Bus_ID", "Operator", "Route", "Category", "Fuel", "Euro", "Age", "AC",
            "Passengers", "Trips", "CO2_kg", "NOx_kg", "PM_kg", "grid_kwh", "gpkm", "Status"]
    cols = [c for c in cols if c in m.columns]
    view = m[cols].copy()
    for c in ["CO2_kg", "NOx_kg", "PM_kg", "grid_kwh", "gpkm"]:
        if c in view.columns:
            view[c] = view[c].round(2)
    view["Age"] = view["Age"].round(0).astype(int)

    st.markdown(f"**{len(view):,} buses** match — {view['CO2_kg'].sum()/1000:,.1f} t CO₂ · "
                f"{view['NOx_kg'].sum()/1000:,.2f} t NOx · {view['PM_kg'].sum():,.1f} kg PM")
    st.dataframe(view.sort_values("gpkm", ascending=False),
                 use_container_width=True, height=460, hide_index=True)
    st.download_button("⬇  Download manifest (CSV)",
                       view.to_csv(index=False).encode("utf-8"),
                       file_name=f"lamata_manifest_{method}.csv", mime="text/csv")


# ----------------------------------------------------------------------
# Route
# ----------------------------------------------------------------------
{
    "Dashboard": view_dashboard,
    "Fleet Intelligence": view_fleet,
    "Pollutant Engine": view_pollutant,
    "Bus Efficiency": view_efficiency,
    "Trip Inspector": view_inspector,
    "Formula Explainer": view_formula,
    "Deep Search": view_search,
}[module]()
