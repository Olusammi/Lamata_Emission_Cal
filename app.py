"""
LAMATA Emissions — Operations Center
====================================
Streamlit dashboard that renders the same public emissions overview as the
HTML "Operations Center" design, driven by emissions_engine.py.

Run:
    pip install streamlit pandas numpy plotly
    streamlit run app.py

Expects Final_Bus_Data.csv next to this file (or upload it in the sidebar).
"""

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from emissions_engine import process, fleet_summary, METHODS, THRESH

# ----------------------------------------------------------------------
# Page + theme
# ----------------------------------------------------------------------
st.set_page_config(page_title="LAMATA Emissions — Operations Center",
                   page_icon="🚌", layout="wide")

BG, PANEL, PANEL2 = "#0a0e0d", "#101715", "#16201d"
LINE, TEXT, TEXT2, TEXT3 = "#1e2a27", "#eaf2ef", "#8ba39c", "#5d746d"
GOOD, MONITOR, OVER = "#3ef2a0", "#ffc24b", "#ff6363"
INFO, VIOLET, ACCENT = "#5cc8ff", "#c9a0ff", "#3ef2a0"
STATUS_COLOR = {"Good": GOOD, "Monitor": MONITOR, "Over": OVER}

st.markdown(f"""
<style>
  .stApp {{ background:{BG}; color:{TEXT}; font-family:'Archivo',sans-serif; }}
  section[data-testid="stSidebar"] {{ background:#0d1312; border-right:1px solid {LINE}; }}
  #MainMenu, footer, header {{ visibility:hidden; }}
  .block-container {{ padding-top:1.2rem; }}
  .kpi {{ background:{PANEL}; border:1px solid {LINE}; border-top:2px solid {ACCENT};
          border-radius:10px; padding:14px 16px; }}
  .kpi .lab {{ font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:.08em; color:{TEXT3}; }}
  .kpi .val {{ font-family:'JetBrains Mono',monospace; font-size:26px; font-weight:700; color:{TEXT}; margin-top:6px; }}
  .kpi .sub {{ font-size:12px; color:{TEXT2}; margin-top:2px; }}
  .pill {{ display:inline-block; font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700;
           border-radius:6px; padding:5px 12px; letter-spacing:.06em; }}
  h1,h2,h3 {{ color:{TEXT}; font-family:'Archivo',sans-serif; }}
  .card {{ background:{PANEL}; border:1px solid {LINE}; border-radius:12px; padding:16px 18px; }}
</style>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Data loading (cached)
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_all(file):
    df = pd.read_csv(file)
    out = {}
    for m in METHODS:
        trips, buses = process(df, m)
        out[m] = {"trips": trips, "buses": buses}
    return out


st.sidebar.markdown("### ⚙️  Data source")
uploaded = st.sidebar.file_uploader("Trip CSV", type="csv")
source = uploaded if uploaded is not None else "Final_Bus_Data.csv"

try:
    DATA = load_all(source)
except FileNotFoundError:
    st.error("Final_Bus_Data.csv not found — upload the trip CSV in the sidebar.")
    st.stop()

# ----------------------------------------------------------------------
# Filters
# ----------------------------------------------------------------------
st.sidebar.markdown("### 🎛️  Filters")
method = st.sidebar.selectbox("Methodology", list(METHODS), index=0)
pollutant = st.sidebar.radio("Pollutant", ["CO2", "NOx", "PM"], horizontal=True)

buses_all = DATA[method]["buses"]
trips_all = DATA[method]["trips"]

operators = ["All"] + sorted(buses_all["Operator"].unique().tolist())
operator = st.sidebar.selectbox("Operator", operators, index=0)
fuel = st.sidebar.selectbox("Fuel", ["All", "Diesel", "Petrol"], index=0)
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
pol_label = "CO₂" if pollutant == "CO2" else pollutant
s = fleet_summary(buses)

# ----------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------
st.markdown(
    f"<div style='font-family:JetBrains Mono,monospace;font-size:11px;letter-spacing:.16em;color:{ACCENT}'>"
    f"PUBLIC EMISSIONS DASHBOARD · LAGOS METROPOLITAN &nbsp;·&nbsp; METHOD {method} · REPORTING MAY 2026</div>",
    unsafe_allow_html=True)
st.markdown(f"## Fleet Emissions Overview")

# ----------------------------------------------------------------------
# KPI row
# ----------------------------------------------------------------------
def kpi(col, lab, val, sub, tone=ACCENT):
    col.markdown(
        f"<div class='kpi' style='border-top-color:{tone}'>"
        f"<div class='lab'>{lab}</div><div class='val'>{val}</div><div class='sub'>{sub}</div></div>",
        unsafe_allow_html=True)

c = st.columns(6)
kpi(c[0], "TRIPS / MONTH", f"{s['trips']:,}", f"{s['buses']:,} buses in fleet", INFO)
kpi(c[1], "PASSENGERS", f"{s['passengers']/1000:,.0f}k", "monthly boardings", GOOD)
kpi(c[2], "TOTAL CO₂", f"{s['co2_tonnes']:,.0f} t", f"{s['co2_tonnes']*1000:,.0f} kg", ACCENT)
kpi(c[3], "FLEET EFFICIENCY", f"{s['fleet_efficiency_gpkm']:.1f}", "g CO₂ / pkm", VIOLET)
kpi(c[4], "BUSES OVER LIMIT", f"{s['buses_over_limit']:,}", "flagged for review", OVER)
kpi(c[5], "AVG FLEET AGE", f"{s['avg_age']:.1f}", "years in service", MONITOR)

st.write("")

# ----------------------------------------------------------------------
# Hero number + compliance gauge
# ----------------------------------------------------------------------
hero_val = buses[pol_kg].sum()
hero_disp = f"{hero_val:,.0f} kg" if pollutant == "PM" else f"{hero_val/1000:,.0f} t"

left, right = st.columns([1.4, 1])
with left:
    st.markdown(
        f"<div class='card'><div class='lab' style='font-family:JetBrains Mono,monospace;font-size:11px;color:{TEXT3}'>"
        f"TOTAL {pol_label} — FLEET, THIS MONTH</div>"
        f"<div style='font-family:JetBrains Mono,monospace;font-size:52px;font-weight:700'>{hero_disp}</div></div>",
        unsafe_allow_html=True)

with right:
    eff = s["fleet_efficiency_gpkm"]
    band = "GOOD" if eff <= 45 else "MONITOR" if eff <= 80 else "OVER LIMIT"
    band_c = GOOD if eff <= 45 else MONITOR if eff <= 80 else OVER
    gauge = go.Figure(go.Indicator(
        mode="gauge+number", value=eff,
        number={"suffix": " g/pkm", "font": {"color": TEXT, "size": 26}},
        gauge={
            "axis": {"range": [0, 110], "tickcolor": TEXT3},
            "bar": {"color": band_c},
            "bgcolor": PANEL,
            "steps": [
                {"range": [0, 45], "color": "rgba(62,242,160,.18)"},
                {"range": [45, 80], "color": "rgba(255,194,75,.18)"},
                {"range": [80, 110], "color": "rgba(255,99,99,.18)"},
            ],
        }))
    gauge.update_layout(height=210, margin=dict(l=10, r=10, t=10, b=0),
                        paper_bgcolor=PANEL, font_color=TEXT)
    st.plotly_chart(gauge, use_container_width=True)
    st.markdown(f"<span class='pill' style='color:{band_c};background:{band_c}22'>FLEET {band}</span>",
                unsafe_allow_html=True)

st.write("")

# ----------------------------------------------------------------------
# Operator bars + Euro bars
# ----------------------------------------------------------------------
def base_layout(fig, h=320):
    fig.update_layout(height=h, margin=dict(l=8, r=8, t=8, b=8),
                      paper_bgcolor=PANEL, plot_bgcolor=PANEL, font_color=TEXT2,
                      xaxis=dict(gridcolor=LINE), yaxis=dict(gridcolor=LINE))
    return fig

ca, cb = st.columns(2)

with ca:
    st.markdown(f"**{pol_label} by Operator** — top 8")
    op = (buses.groupby("Operator")[pol_kg].sum().sort_values(ascending=False).head(8))
    unit = op.values if pollutant == "PM" else op.values / 1000.0
    fig = go.Figure(go.Bar(x=unit, y=op.index, orientation="h",
                           marker_color=INFO, text=[f"{v:,.0f}" for v in unit],
                           textposition="outside"))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(base_layout(fig), use_container_width=True)

with cb:
    st.markdown("**Intensity by Euro Class** — avg g CO₂/pkm")
    order = ["Euro II", "Euro III", "Euro IV", "Euro V", "Euro VI"]
    ev = buses[buses["gpkm"] > 0].groupby("Euro")["gpkm"].mean()
    ev = ev.reindex([e for e in order if e in ev.index])
    colors = {"Euro II": OVER, "Euro III": MONITOR, "Euro IV": INFO, "Euro V": GOOD, "Euro VI": ACCENT}
    fig = go.Figure(go.Bar(x=ev.index, y=ev.values,
                           marker_color=[colors.get(e, INFO) for e in ev.index],
                           text=[f"{v:.0f}" for v in ev.values], textposition="outside"))
    st.plotly_chart(base_layout(fig), use_container_width=True)

# ----------------------------------------------------------------------
# Daily trend
# ----------------------------------------------------------------------
st.markdown(f"**Daily {pol_label} Output — {method}**")
day = pd.to_datetime(trips["Date"], errors="coerce").dt.day
gcol = {"CO2": "CO2_g", "NOx": "NOx_g", "PM": "PM_g"}[pollutant]
if gcol not in trips.columns:
    gcol = pol_kg
    daily = trips.assign(day=day).groupby("day")[gcol].sum()  # kg
else:
    daily = trips.assign(day=day).groupby("day")[gcol].sum() / 1e6  # tonnes
fig = go.Figure(go.Bar(x=daily.index, y=daily.values, marker_color=ACCENT))
st.plotly_chart(base_layout(fig, 220), use_container_width=True)

# ----------------------------------------------------------------------
# Compliance split + operator leaderboard
# ----------------------------------------------------------------------
cc, cd = st.columns([1, 1.5])

with cc:
    st.markdown("**Trip Compliance**")
    vals = [s["trips_good"], s["trips_monitor"], s["trips_over"]]
    fig = go.Figure(go.Pie(labels=["Good", "Monitor", "Over"], values=vals, hole=.62,
                           marker_colors=[GOOD, MONITOR, OVER], sort=False))
    fig.update_layout(height=300, paper_bgcolor=PANEL, font_color=TEXT2,
                      margin=dict(l=8, r=8, t=8, b=8), showlegend=True,
                      legend=dict(font=dict(color=TEXT2)))
    st.plotly_chart(fig, use_container_width=True)

with cd:
    st.markdown("**Operator Leaderboard** — ranked by fleet efficiency")
    grp = buses.groupby("Operator")
    lb = pd.DataFrame({
        "Buses": grp.size(),
        "Passengers": grp["Passengers"].sum(),
        "wsum": grp.apply(lambda g: (g["gpkm"] * g["Passengers"]).sum()),
    })
    lb["g CO₂/pkm"] = (lb["wsum"] / lb["Passengers"].clip(lower=1)).round(1)
    lb = lb[lb["Buses"] >= 2].sort_values("g CO₂/pkm").head(10)
    lb["Status"] = np.where(lb["g CO₂/pkm"] <= 45, "Good",
                     np.where(lb["g CO₂/pkm"] <= 80, "Monitor", "Over"))
    lb = lb.reset_index()[["Operator", "Buses", "g CO₂/pkm", "Status"]]
    lb.index = np.arange(1, len(lb) + 1)
    st.dataframe(lb, use_container_width=True, height=340)

st.caption("IPCC 2006 Tier 2 · COPERT V speed functions · Euro II–VI multipliers · "
           "age deterioration · efficiency = g CO₂ per passenger-km.")
