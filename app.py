"""
Fleet Emissions Console
Modules: Dashboard · Fleet Intelligence · Pollutant Engine · Bus Efficiency ·
         Corridor Map · Fleet Health · Forecast · Data Quality · What-If ·
         Trip Inspector · Formula Explainer · Deep Search
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_option_menu import option_menu
from emissions_engine import calculate_row, emission_breakdown, compliance_flag
import db
import ai_engine
import themes as themes_mod

APP_NAME    = "Fleet Emissions Console"
APP_TAGLINE = "TRANSIT FLEET INTELLIGENCE"
APP_INITIALS = "FE"
FLEET_REGION = "Lagos"            # used only for corridor geometry + weather
FLEET_LAT, FLEET_LON = 6.52, 3.37 # Open-Meteo ambient temperature lookup

# ════════════════════════════════════════════════════════
# 0. PAGE CONFIG
# ════════════════════════════════════════════════════════
st.set_page_config(
    page_title=APP_NAME,
    page_icon="ido2tL42k3_1782393500014.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ════════════════════════════════════════════════════════
# 0.5. AUTHENTICATION
# ════════════════════════════════════════════════════════
def check_password():
    """Returns True if the user has a valid password."""
    # Check if user is already logged in during this session
    if st.session_state.get("authenticated", False):
        return True

    # Show the login form
    st.markdown(f"## 🔐 {APP_NAME} — Login")
    with st.form("login_form"):
        username = st.text_input("Username").strip()
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            # Check if the username exists in secrets and password matches
            if "credentials" in st.secrets and username in st.secrets["credentials"]:
                if st.secrets["credentials"][username] == password:
                    st.session_state["authenticated"] = True
                    st.rerun()  # Refresh page to bypass login
                else:
                    st.error("Incorrect password.")
            else:
                st.error("Unknown username.")
    return False

# Stop the app execution here if the user isn't logged in
if not check_password():
    st.stop()

# ════════════════════════════════════════════════════════
# 1. GLOBAL CSS  — premium dark-navy sidebar + clean main
# ════════════════════════════════════════════════════════
# ── Theme toggle (must be before CSS injection) ──
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

_theme = st.session_state.theme
_is_dark = (_theme == "dark")

if "theme_preset" not in st.session_state:
    st.session_state.theme_preset = themes_mod.DEFAULT_THEME
_preset = st.session_state.theme_preset
_css_vars = themes_mod.css_vars(_preset, _is_dark)
_accent_hex = themes_mod.accent(_preset, _is_dark)

st.markdown(f"""
<style>
@import url('{themes_mod.FONT_IMPORT}');

:root {{ {_css_vars} }}

/* ── chrome ── */
#MainMenu, footer, header {{ visibility: hidden; }}
div[data-testid="stSidebarNav"] {{ display: none; }}
html, body, [class*="css"] {{ font-family: var(--body); }}

/* ── headers use signage-style condensed display face ── */
h1, h2, h3, h4 {{ font-family: var(--disp) !important; font-weight: 600 !important; letter-spacing: 0.01em; }}

/* ── numeric readouts use monospace ── */
div[data-testid="stMetricValue"] > div,
.kpi-accent .val, .gauge-readout, .board-row .figure, .brow .val,
.banner-code, code {{ font-family: var(--mono) !important; }}

/* ── main background ── */
.stApp {{ background: var(--bg-app) !important; }}
section[data-testid="stMain"] > div {{ background: var(--bg-app) !important; }}

/* ── sidebar ── */
section[data-testid="stSidebar"] > div:first-child {{
    background: var(--sidebar-bg) !important;
    border-right: 1px solid #233029;
    padding-top: 0 !important;
}}
section[data-testid="stSidebar"] * {{ color: #8fa49a !important; }}
section[data-testid="stSidebar"] .stFileUploader label,
section[data-testid="stSidebar"] .stFileUploader small {{ color: #5c7268 !important; font-size:11px !important; }}
section[data-testid="stSidebar"] .stFileUploader [data-testid="stFileUploaderDropzone"] {{
    background: #151d1c !important; border-color: #233029 !important; border-radius: 4px !important;
}}

/* ── widget labels: small mono caps, consistent everywhere ── */
.stSelectbox label, .stMultiSelect label, .stTextInput label, .stDateInput label, .stCheckbox label {{
    font-family: var(--mono) !important; font-size: 10px !important; font-weight: 500 !important;
    letter-spacing: 0.06em !important; text-transform: uppercase !important; color: var(--text-tert) !important;
}}

/* ── dropdowns / selects (both sidebar and main content) ── */
div[data-baseweb="select"] > div {{
    background: var(--bg-card2) !important; border-color: var(--border) !important;
    border-radius: 4px !important; font-size: 12.5px !important; min-height: 38px !important;
}}
div[data-baseweb="select"] > div:focus-within {{ border-color: var(--accent) !important; box-shadow: 0 0 0 1px var(--accent) !important; }}
div[data-baseweb="select"] svg {{ fill: var(--text-tert) !important; }}
/* dropdown popover menu */
div[data-baseweb="popover"] ul {{ background: var(--bg-card2) !important; border: 1px solid var(--border) !important; }}
li[data-baseweb="menu-item"] {{ font-size: 12.5px !important; color: var(--text-sec) !important; }}
li[data-baseweb="menu-item"]:hover, li[aria-selected="true"] {{ background: var(--bg-card) !important; color: var(--text-prim) !important; }}
/* multiselect selected-value tags */
div[data-baseweb="tag"] {{
    background: var(--badge-good-bg) !important; border-radius: 3px !important;
    font-family: var(--mono) !important; font-size: 11px !important;
}}
div[data-baseweb="tag"] span {{ color: var(--badge-good-text) !important; }}
/* text/date inputs */
div[data-baseweb="input"] > div, div[data-baseweb="datepicker"] input {{
    background: var(--bg-card2) !important; border-color: var(--border) !important; border-radius: 4px !important;
}}

/* ── modern toggle switch (theme switcher) ── */
div[data-testid="stToggle"] label div[data-baseweb="checkbox"] > div:first-child {{
    background: var(--border2) !important;
}}
div[data-testid="stToggle"] label div[aria-checked="true"] {{
    background: var(--accent) !important;
}}

/* ── nav menu ── */
.nav-link {{ border-radius: 4px !important; margin: 1px 0 !important; font-size:13px !important; border-left: 3px solid transparent !important; }}
.nav-link-selected {{ background: #151d1c !important; color: var(--accent) !important; border-left: 3px solid var(--accent) !important; }}
.nav-link:hover {{ background: #0d1413 !important; }}

/* ── main text colours ── */
h1, h2, h3, h4, h5, h6 {{ color: var(--text-prim) !important; }}
p, li, span, div {{ color: var(--text-sec); }}
.stMarkdown p {{ color: var(--text-sec); }}
label, .stSelectbox label, .stMultiSelect label {{ color: var(--text-sec) !important; }}

/* ── metric cards ── */
div[data-testid="metric-container"] {{
    background: var(--metric-bg) !important;
    border: 1px solid var(--metric-bdr) !important;
    border-top: 2px solid var(--border2) !important;
    border-radius: 4px; padding: 16px 18px 14px !important;
    box-shadow: none;
}}
div[data-testid="stMetricLabel"] > div  {{ font-family: var(--mono) !important; font-size: 10px !important; color: var(--metric-lbl) !important; font-weight:500 !important; letter-spacing:0.07em; text-transform:uppercase; }}
div[data-testid="stMetricValue"] > div  {{ font-size: 26px !important; color: var(--metric-val) !important; font-weight:600 !important; letter-spacing:-0.01em; }}
div[data-testid="stMetricDelta"]        {{ font-family: var(--mono) !important; font-size: 11px !important; }}

/* ── banner ── */
.banner {{
    background: var(--banner-bg);
    color: var(--banner-text) !important;
    border-radius: 4px; padding: 14px 20px;
    font-size: 13px; line-height: 1.65; margin-bottom: 18px;
    border: 1px solid var(--banner-bdr);
}}
.banner strong {{ color: var(--accent) !important; }}
.banner code   {{ background: var(--banner-code-bg); color: var(--banner-code) !important;
                  padding: 1px 6px; border-radius:3px; font-size:11px; }}

/* ── chip bar ── */
.chip {{ display:inline-flex; align-items:center; gap:5px; padding: 5px 11px; border-radius:3px;
         font-family: var(--mono); font-size: 11px; font-weight:500; cursor:pointer; border: 1px solid transparent; }}
.chip-blue   {{ background:#142a2a; color:#5cc8c8; border-color:#1f4a4a; }}
.chip-green  {{ background:#11331f; color:#3ddc84; border-color:#1d4a30; }}
.chip-amber  {{ background:#4a3414; color:#ff9d2e; border-color:#5c3f12; }}
.chip-red    {{ background:#3a1414; color:#ff5252; border-color:#5c1818; }}
.chip-gray   {{ background:#151d1c; color:#8fa49a; border-color:#233029; }}
.chip-purple {{ background:#241a3a; color:#c9a8ff; border-color:#3a2a5c; }}

/* ── compliance badges ── */
.badge {{ display:inline-block; padding:3px 9px; border-radius:3px; font-family: var(--mono); font-size:10.5px; font-weight:600; letter-spacing:0.04em; }}
.badge-good    {{ background: var(--badge-good-bg); color: var(--badge-good-text); }}
.badge-monitor {{ background: var(--badge-mon-bg);  color: var(--badge-mon-text); }}
.badge-over    {{ background: var(--badge-over-bg); color: var(--badge-over-text); }}
.badge-na      {{ background: #151d1c; color: #5c7268; }}

/* ── kpi accent cards ── */
.kpi-accent {{ border-radius: 4px; padding: 16px 18px;
               border: 1px solid var(--border); border-top: 2px solid var(--border2); background: var(--bg-card); }}
.kpi-accent .val {{ font-size:26px; font-weight:600; color:var(--text-prim); letter-spacing:-0.01em; line-height:1.2; }}
.kpi-accent .lbl {{ font-family: var(--mono); font-size:10px; color:var(--text-tert); font-weight:500; text-transform:uppercase; letter-spacing:0.07em; margin-bottom:8px; }}
.kpi-accent .sub {{ font-size:12px; color:var(--text-sec); margin-top:4px; }}

/* ── section divider ── */
.sec-label {{
    font-family: var(--mono); font-size:10px; font-weight:500; letter-spacing:0.08em; text-transform:uppercase;
    color:var(--text-tert); margin: 22px 0 10px; display:flex; align-items:center; gap:10px;
}}
.sec-label::after {{ content:''; flex:1; height:1px; background:var(--border); }}

/* ── tip cards ── */
.tip {{ background:var(--tip-bg); border:1px solid var(--tip-bdr); border-radius:4px;
        padding:11px 14px; margin-bottom:8px; font-size:12px; color:var(--tip-text); line-height:1.6; }}
.tip strong {{ color: var(--tip-strong); }}

/* ── breakdown bar ── */
.brow {{ display:flex; align-items:center; gap:10px; margin-bottom:9px; }}
.brow .lbl {{ font-size:11px; color:var(--text-sec); width:90px; flex-shrink:0; }}
.brow .bg  {{ flex:1; height:7px; background:var(--bg-card2); border-radius:3px; overflow:hidden; }}
.brow .fill {{ height:100%; border-radius:3px; }}
.brow .val {{ font-size:12px; font-weight:600; color:var(--text-prim); width:62px; text-align:right; flex-shrink:0; }}

/* ── active filter bar ── */
.filter-bar {{
    background: var(--filter-bg); border:1px solid var(--filter-bdr);
    border-radius:4px; padding:10px 14px; margin-bottom:14px;
    font-size:12px; color:var(--filter-text);
}}

/* ── auto-rename bar ── */
.autorename-bar {{
    background: var(--autorename-bg); border:1px solid var(--autorename-bdr);
    border-radius:4px; padding:10px 16px; margin-bottom:12px;
    font-size:12px; color:var(--autorename-text);
}}

/* ── expanders ── */
div[data-testid="stExpander"] {{ background: var(--expander-bg) !important;
    border: 1px solid var(--border) !important; border-radius: 4px !important; }}
div[data-testid="stExpander"] summary span {{ color: var(--text-prim) !important; }}

/* ── dataframe ── */
div[data-testid="stDataFrame"] {{ border-radius:4px; overflow:hidden; border:1px solid var(--table-bdr); }}
div[data-testid="stDataFrame"] * {{ font-family: var(--mono) !important; }}

/* ── buttons ── */
.stButton > button {{ border-radius: 3px !important; font-family: var(--mono) !important; font-size: 11px !important; letter-spacing: 0.03em; }}

/* ── tabs ── */
div[data-testid="stTabs"] button {{ font-family: var(--mono) !important; font-size:12px !important; color: var(--text-sec) !important; }}
div[data-testid="stTabs"] button[aria-selected="true"] {{ color: var(--accent) !important; }}

/* ── empty state ── */
.empty {{ display:flex; flex-direction:column; align-items:center; justify-content:center;
          min-height:58vh; text-align:center; gap:14px; }}
.empty .icon {{ font-size:52px; }}
.empty h2 {{ font-size:22px; font-weight:600; color:var(--text-prim); }}
.empty p  {{ font-size:14px; color:var(--text-sec); max-width:440px; line-height:1.7; }}
.empty code {{ font-size:11px; background:var(--bg-card2); color:var(--accent); padding:2px 7px; border-radius:3px; }}

/* ── plotly transparent ── */
.js-plotly-plot .plotly .main-svg {{ background: transparent !important; }}

/* ── operator table cards ── */
.op-card {{
    background: var(--bg-card); border: 1px solid var(--border); border-top: 2px solid var(--border2);
    border-radius: 4px; padding: 14px 16px; margin-bottom: 8px;
}}
.op-card .op-name {{ font-size:13px; font-weight:600; color:var(--text-prim); margin-bottom:4px; }}
.op-card .op-meta {{ font-family: var(--mono); font-size:10.5px; color:var(--text-sec); }}
.op-bar-bg {{ background:var(--bg-card2); border-radius:3px; height:6px; margin-top:6px; overflow:hidden; }}
.op-bar    {{ height:100%; border-radius:3px; background: var(--accent); }}

/* ── compliance gauge (signature element) ── */
.gauge-wrap {{ text-align:center; }}
.gauge-readout {{ font-size:28px; font-weight:600; color:var(--text-prim); margin-top:4px; }}
.gauge-readout .u {{ font-family: var(--body); font-size:12px; color:var(--text-sec); }}
.gauge-status {{ display:inline-block; margin-top:8px; font-family: var(--mono); font-size:10.5px; font-weight:600;
    letter-spacing:0.06em; padding:4px 11px; border-radius:3px; }}
.gauge-status.good    {{ background: var(--badge-good-bg); color: var(--badge-good-text); }}
.gauge-status.monitor {{ background: var(--badge-mon-bg);  color: var(--badge-mon-text); }}
.gauge-status.over    {{ background: var(--badge-over-bg); color: var(--badge-over-text); }}

/* ── Floating AI assistant ── */
.st-key-ai_fab button {{
    position: fixed !important; top: 70px; right: 26px;
    width: 58px; height: 58px; border-radius: 50% !important;
    z-index: 1000001; font-size: 24px !important; line-height: 1 !important;
    background: var(--accent) !important; color: #ffffff !important;
    border: none !important; box-shadow: 0 10px 28px rgba(0,0,0,0.45) !important;
    transition: transform .15s ease;
}}
.st-key-ai_fab button:hover {{ transform: scale(1.08); }}
.st-key-ai_panel {{
    position: fixed !important; top: 140px; right: 26px;
    width: 400px; max-width: calc(100vw - 40px);
    max-height: 64vh; overflow-y: auto; z-index: 1000000;
    background: var(--bg-card) !important;
    border: 1px solid var(--border2) !important; border-radius: 14px;
    box-shadow: 0 18px 50px rgba(0,0,0,0.5);
    padding: 14px 16px 10px !important;
}}
.st-key-ai_panel .ai-head {{ display:flex; align-items:center; gap:8px;
    font-family: var(--disp); font-size: 14px; font-weight: 600;
    color: var(--text-prim); padding-bottom: 6px;
    border-bottom: 1px solid var(--border); margin-bottom: 8px; }}
.st-key-ai_panel .ai-sub {{ font-family: var(--mono); font-size: 9.5px;
    color: var(--text-tert); letter-spacing: .05em; }}
.ai-msg-u, .ai-msg-a {{ border-radius: 10px; padding: 8px 11px;
    font-size: 12.5px; line-height: 1.5; margin: 6px 0; }}
.ai-msg-u {{ background: var(--banner-code-bg); color: var(--text-prim);
    margin-left: 36px; }}
.ai-msg-a {{ background: var(--bg-card2); color: var(--text-sec);
    border: 1px solid var(--border); margin-right: 12px; }}
.ai-msg-a strong {{ color: var(--text-prim); }}
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# 2. CONSTANTS & HELPERS
# ════════════════════════════════════════════════════════
EXPECTED_COLS = [
    "Date","Route_Name","Bus_ID","Operator","Bus_Category",
    "Fuel_Type","Route_Distance_km","Avg_Speed_kmh","Ridership","Revenue_Trip",
]
NEW_COLS = ["Euro_Standard","Vehicle_Age_years","AC_Status","Num_Trips_Today","Engine_Model"]
ALL_COLS = EXPECTED_COLS + NEW_COLS

PALETTE  = ["#1E73BE","#3ddc84","#5cc8c8","#ff5252","#c9a8ff","#ffd166","#7fb8a8","#8fa49a"]
PLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter",size=12,color="#eef3f0" if _is_dark else "#0f1714"),
    margin=dict(l=4,r=4,t=36,b=4),
    legend=dict(bgcolor="rgba(0,0,0,0)",borderwidth=0),
)

def fmt_kg(v):  return f"{v:,.1f} kg"
def fmt_t(v):   return f"{v/1000:,.2f} t"
def fmt_gkm(v): return f"{v:,.1f} {st.session_state.get('eff_unit', 'g/pkm')}"

def badge_html(flag):
    cls = {"Good":"badge-good","Monitor":"badge-monitor","Over Limit":"badge-over"}.get(flag,"badge-na")
    return f'<span class="badge {cls}">{flag}</span>'

def gauge_svg(value, good_t, monitor_t, unit="g CO₂/pkm", max_val=None):
    """Renders the signature semicircular instrument-panel gauge used for
    compliance readouts. value/good_t/monitor_t are in the same units."""
    flag = "Good" if value <= good_t else ("Monitor" if value <= monitor_t else "Over Limit")
    status_cls = {"Good":"good","Monitor":"monitor","Over Limit":"over"}[flag]
    if max_val is None:
        max_val = max(monitor_t * 1.6, value * 1.1, 1)
    pct = max(0.0, min(value / max_val, 1.0))
    angle = 180 * pct  # 0..180 degrees sweep, left to right
    import math
    rad = math.radians(180 - angle)
    cx, cy, r = 110, 110, 80
    nx = cx + r * math.cos(rad) * 0.62
    ny = cy - r * math.sin(rad) * 0.62
    good_frac = min(good_t / max_val, 1.0)
    mon_frac  = min(monitor_t / max_val, 1.0)

    def arc_path(f0, f1):
        a0 = 180 - 180 * f0
        a1 = 180 - 180 * f1
        r0 = math.radians(a0); r1 = math.radians(a1)
        x0, y0 = cx + r*math.cos(r0), cy - r*math.sin(r0)
        x1, y1 = cx + r*math.cos(r1), cy - r*math.sin(r1)
        return f"M {x0:.1f} {y0:.1f} A {r} {r} 0 0 1 {x1:.1f} {y1:.1f}"

    return f"""
    <div class="gauge-wrap">
      <svg width="220" height="128" viewBox="0 0 220 128">
        <path d="{arc_path(0, good_frac)}" fill="none" stroke="#3ddc84" stroke-width="14" stroke-linecap="round"/>
        <path d="{arc_path(good_frac, mon_frac)}" fill="none" stroke="#ff9d2e" stroke-width="14" stroke-linecap="round"/>
        <path d="{arc_path(mon_frac, 1.0)}" fill="none" stroke="#ff5252" stroke-width="14" stroke-linecap="round"/>
        <line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#eef3f0" stroke-width="3" stroke-linecap="round"/>
        <circle cx="{cx}" cy="{cy}" r="6" fill="#eef3f0"/>
      </svg>
      <div class="gauge-readout">{value:.1f}<span class="u"> {unit}</span></div>
      <div class="gauge-status {status_cls}">{flag.upper()}</div>
    </div>"""

def chip(label, cls="chip-gray"):
    return f'<span class="chip {cls}">{label}</span>'


# ════════════════════════════════════════════════════════
# CHART SWITCHER — every major chart can be re-rendered as
# bar / line / area / pie / table with one compact selector
# ════════════════════════════════════════════════════════
_CS_ICONS = {"Bar": "📊", "Line": "📈", "Area": "📐", "Pie": "🥧",
             "Scatter": "✦", "Table": "🔢"}

def chart_switcher(data, x, y, key, kinds=("Bar", "Line", "Area", "Pie", "Table"),
                   color=None, default="Bar", height=340, y_label=None,
                   barmode="group", sort_desc=False, title=None):
    """Render `data` as the user's chosen chart type. Pie is only offered
    when it makes sense (single value column, no series split)."""
    y_cols = [y] if isinstance(y, str) else list(y)
    kinds = list(kinds)
    if "Pie" in kinds and (len(y_cols) > 1 or color):
        kinds.remove("Pie")            # a multi-series pie is nonsense
    idx = kinds.index(default) if default in kinds else 0
    kind = st.radio("view", [f"{_CS_ICONS.get(k,'')} {k}" for k in kinds],
                    index=idx, horizontal=True, key=f"cs_{key}",
                    label_visibility="collapsed").split(" ", 1)[1]

    d = data.copy()
    if sort_desc and kind in ("Bar", "Pie", "Table"):
        d = d.sort_values(y_cols[0], ascending=False)

    if kind == "Table":
        st.dataframe(d, use_container_width=True, hide_index=True)
        return
    if kind == "Pie":
        fig = px.pie(d, names=x, values=y_cols[0], hole=0.45)
    elif kind == "Line":
        fig = px.line(d, x=x, y=y_cols if len(y_cols) > 1 else y_cols[0],
                      color=color, markers=True)
    elif kind == "Area":
        fig = px.area(d, x=x, y=y_cols if len(y_cols) > 1 else y_cols[0], color=color)
    elif kind == "Scatter":
        fig = px.scatter(d, x=x, y=y_cols[0], color=color)
    else:
        fig = px.bar(d, x=x, y=y_cols if len(y_cols) > 1 else y_cols[0],
                     color=color, barmode=barmode)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=34 if title else 24, b=10),
                      legend=dict(orientation="h"), title=title, title_font_size=13,
                      yaxis_title=y_label or "", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True, key=f"csc_{key}_{kind}")


def with_table_option(fig, table_df, key, height=None):
    """For charts that only exist in one sensible form (heatmaps, donuts,
    bands, maps): offer the chart or its underlying numbers as a table."""
    mode = st.radio("view", ["📊 Chart", "🔢 Table"], horizontal=True,
                    key=f"wt_{key}", label_visibility="collapsed")
    if mode.endswith("Table"):
        st.dataframe(table_df, use_container_width=True, hide_index=True)
    else:
        if height:
            fig.update_layout(height=height)
        st.plotly_chart(fig, use_container_width=True, key=f"wtc_{key}")

def kpi_card(label, value, sub="", dot_color=None):
    dot = f'<span class="dot" style="background:{dot_color};"></span>' if dot_color else ""
    return f"""
    <div class="kpi-accent">
        <div class="lbl">{label}</div>
        <div class="val">{dot}{value}</div>
        {"<div class='sub'>"+sub+"</div>" if sub else ""}
    </div>"""

# ════════════════════════════════════════════════════════
# 3. SIDEBAR
# ════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style="background:var(--sidebar-bg);padding:20px 16px 16px;margin:-1rem -1rem 0;border-bottom:1px solid var(--border);">
        <div style="display:flex;align-items:center;gap:11px;">
            <div style="width:36px;height:36px;border:2px solid {_accent_hex};border-radius:3px;
                        display:flex;align-items:center;justify-content:center;
                        font-family:var(--disp);font-weight:700;color:{_accent_hex};font-size:13px;flex-shrink:0;">{APP_INITIALS}</div>
            <div>
                <div style="font-family:var(--disp);font-size:14px;font-weight:600;color:#eef3f0;letter-spacing:0.02em;">{APP_NAME}</div>
                <div style="font-family:var(--mono);font-size:9px;color:var(--text-tert);margin-top:2px;letter-spacing:0.06em;">{APP_TAGLINE}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Theme toggle — modern switch, right-aligned
    tcol1, tcol2 = st.columns([2, 1])
    with tcol1:
        st.markdown(
            '<div style="font-family:var(--mono);font-size:10.5px;color:#5a6ea0;'
            'letter-spacing:0.05em;padding-top:9px;">DARK MODE</div>',
            unsafe_allow_html=True)
    with tcol2:
        is_dark_toggle = st.toggle(" ", value=_is_dark, key="theme_toggle", label_visibility="collapsed")
    new_theme = "dark" if is_dark_toggle else "light"
    if new_theme != st.session_state.theme:
        st.session_state.theme = new_theme
        st.rerun()

    st.selectbox("Theme", list(themes_mod.THEMES.keys()), key="theme_preset",
                 label_visibility="collapsed",
                 help="Colour & font preset — each has matched dark and light variants.")

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

    selected_module = option_menu(
        menu_title=None,
        options=["Dashboard","Fleet Intelligence","Pollutant Engine","Bus Efficiency","Corridor Map","Fleet Health","Forecast","Data Quality","What-If","Trip Inspector","Formula Explainer","Deep Search"],
        icons=["speedometer2","diagram-3","cloud-haze2","bus-front","map","heart-pulse","graph-up-arrow","clipboard2-check","sliders","search-heart","calculator","table"],
        default_index=0,
        styles={
            "container":         {"padding":"0!important","background-color":"transparent"},
            "icon":              {"color":"#5c7268","font-size":"15px"},
            "nav-link":          {"font-size":"12.5px","text-align":"left","margin":"1px 0",
                                  "color":"#8fa49a","--hover-color":"#0d1413","padding":"9px 14px",
                                  "border-left":"3px solid transparent"},
            "nav-link-selected": {"background-color":"#0a1d5c","color":"#1E73BE",
                                  "font-weight":"600","border-radius":"4px","border-left":"3px solid #1E73BE"},
        },
    )

    # ── DATA INPUT ──
    st.markdown("""<div style="font-size:10px;font-weight:600;letter-spacing:0.08em;
        text-transform:uppercase;color:#5c7268;margin:18px 0 8px;padding:0 2px;">Data Input</div>""",
        unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Route manifests (CSV / XLSX) — one or more monthly files",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        help="Upload one file per month, or several at once — they're merged into a single fleet view automatically.",
    )

    # ── DATABASE ──
    st.markdown("""<div style="font-size:10px;font-weight:600;letter-spacing:0.08em;
        text-transform:uppercase;color:#5c7268;margin:18px 0 8px;padding:0 2px;">Database</div>""",
        unsafe_allow_html=True)
    _db_state, _db_msg = db.db_status()
    _db_dot = {"connected": "#3EF2A0", "empty": "#FFC24B",
               "unconfigured": "#5c7268", "error": "#FF6363"}[_db_state]
    st.markdown(
        f'<div style="font-size:11px;color:#8fa49a;line-height:1.5;padding:2px;">'
        f'<span style="color:{_db_dot};">●</span> {_db_msg}</div>',
        unsafe_allow_html=True)
    save_uploads_to_db = st.checkbox(
        "Auto-save uploads to database", value=(_db_state in ("connected", "empty")),
        disabled=(_db_state in ("unconfigured", "error")),
        help="New uploads are written to Supabase once (duplicates skipped), "
             "then every future session loads instantly with no upload needed.")
    if _db_state == "connected" and st.button("🔄 Reload from database", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
        
if _db_state == "connected":
        with st.expander("🗑 Manage / delete uploads"):
            st.caption("Deleting is permanent. Enter the delete password to enable.")
            _pw = st.text_input("Delete password", type="password", key="del_pw")
            _pw_ok = _pw and _pw == st.secrets.get("delete", {}).get("password", "")
            if _pw and not _pw_ok:
                st.error("Wrong password — delete disabled.")

            _uploads = db.list_uploads()
            if not _uploads:
                st.caption("No uploads stored.")
            for u in _uploads:
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{u['source_file']}**  \n{u['rows']:,} rows · {u['first']}→{u['last']}")
                if c2.button("Delete", key=f"del_{u['source_file']}", disabled=not _pw_ok):
                    res = db.delete_upload(u["source_file"])
                    if res["error"]:
                        st.warning(res["error"])
                    else:
                        st.success(f"Deleted {u['source_file']}")
                        st.cache_data.clear(); st.rerun()

            if st.button("⚠ Delete ALL trips", disabled=not _pw_ok, use_container_width=True):
                res = db.delete_all_trips()
                if res["error"]:
                    st.warning(res["error"])
                else:
                    st.success("All trips deleted.")
                    st.cache_data.clear(); st.rerun()

    # ── GLOBAL CONTROLS ──
    st.markdown("""<div style="font-size:10px;font-weight:600;letter-spacing:0.08em;
        text-transform:uppercase;color:#5c7268;margin:18px 0 8px;padding:0 2px;">Calculation</div>""",
        unsafe_allow_html=True)
    methodology = st.selectbox(
        "Method", ["Hybrid","IPCC","COPERT"],
        help="Hybrid: CO₂ via IPCC Tier 2, NOx/PM via COPERT V.\nIPCC: all pollutants fixed factor.\nCOPERT: all speed-corrected.",
    )
    target_pollutants = st.multiselect(
        "Pollutants", ["CO2","NOx","PM"], default=["CO2","NOx"],
    )
    basis_choice = st.radio(
        "Emission basis", ["Per passenger", "Per vehicle"],
        horizontal=True,
        help="Per passenger: grams per passenger-km (how efficiently people are moved).\n"
             "Per vehicle: grams per vehicle-km (what each bus physically emits).",
    )
    basis = "passenger" if basis_choice == "Per passenger" else "vehicle"
    st.session_state.eff_unit = "g/pkm" if basis == "passenger" else "g/km"
    use_live_temp = st.checkbox("🌡 Live ambient temp (Open-Meteo)", value=False,
        help="Fetches the current temperature for the fleet region from the free "
             "Open-Meteo API (no key needed) and feeds it to the cold-start "
             "correction. Untick to set it manually.")

    @st.cache_data(ttl=3600, show_spinner=False)
    def _fetch_live_temp(lat, lon):
        import requests as _rq
        try:
            r = _rq.get("https://api.open-meteo.com/v1/forecast",
                        params={"latitude": lat, "longitude": lon,
                                "current": "temperature_2m"}, timeout=6)
            return float(r.json()["current"]["temperature_2m"])
        except Exception:
            return None

    _live_t = _fetch_live_temp(FLEET_LAT, FLEET_LON) if use_live_temp else None
    if _live_t is not None:
        ambient_c = round(_live_t, 1)
        st.markdown(f'<div style="font-family:var(--mono);font-size:10.5px;color:var(--text-tert);'
                    f'padding:0 2px 6px;">● live: {ambient_c} °C ({FLEET_REGION})</div>',
                    unsafe_allow_html=True)
    else:
        if use_live_temp:
            st.caption("Live temp unavailable — using the slider.")
        ambient_c = st.slider(
            "Ambient temp (°C)", 15, 40, 28,
            help="Feeds the cold-start correction — a cold engine over-emits, "
                 "but the effect fades as ambient temperature rises and "
                 "disappears at 30 °C.",
        )

    st.markdown("""<div style="font-size:10px;font-weight:600;letter-spacing:0.08em;
        text-transform:uppercase;color:#5c7268;margin:18px 0 8px;padding:0 2px;">Data Quality</div>""",
        unsafe_allow_html=True)
    exclude_unmapped = st.checkbox(
        "Exclude rows with unmapped category/fuel",
        value=False,
        help="Rows where Bus_Category or Fuel_Type couldn't be matched to a known "
             "class (e.g. 'Unknown') use generic fallback emission factors. "
             "Check this to drop them from every module instead of flagging them.")

    # ── ACTIVE FILTERS ──
    if "active_operator" not in st.session_state: st.session_state.active_operator = None
    if "active_euro"     not in st.session_state: st.session_state.active_euro     = None
    if "active_fuel"     not in st.session_state: st.session_state.active_fuel     = None
    if "active_category" not in st.session_state: st.session_state.active_category = None
    if "active_month"    not in st.session_state: st.session_state.active_month    = None
    if "active_daterange" not in st.session_state: st.session_state.active_daterange = None

    st.markdown("""<div style="font-size:10px;font-weight:600;letter-spacing:0.08em;
        text-transform:uppercase;color:#5c7268;margin:18px 0 8px;padding:0 2px;">Quick Filters</div>""",
        unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px;color:#5c7268;margin-bottom:6px;">Applied across all modules</div>',
        unsafe_allow_html=True)

    if st.button("✕ Clear all filters", use_container_width=True,
                 type="secondary" if any([st.session_state.active_operator,
                    st.session_state.active_euro,st.session_state.active_fuel,
                    st.session_state.active_category,st.session_state.active_month,
                    st.session_state.active_daterange]) else "secondary"):
        st.session_state.active_operator = None
        st.session_state.active_euro     = None
        st.session_state.active_fuel     = None
        st.session_state.active_category = None
        st.session_state.active_month    = None
        st.session_state.active_daterange = None

    st.markdown("---")
    st.markdown(
        '<div style="font-size:10px;color:#3a4a42;line-height:1.7;padding:0 2px;">'
        'Factors: IPCC 2006 Tier 2 · COPERT V<br>'
        'Euro II–VI NOx/PM multipliers · Age deterioration<br>'
        'A/C per-trip flag · Engine model correction<br>'
        'Nigeria grid: 0.46 kg CO₂e/kWh (IEA 2023)'
        '</div>', unsafe_allow_html=True
    )

# ════════════════════════════════════════════════════════
# 4. DATA LOADING + CALCULATION
# ════════════════════════════════════════════════════════
# ── No hard gate: the full interface (sidebar, nav, every module page)
# renders from the first second. Without data, each module shows its own
# frame with a compact "awaiting manifest" panel where its charts will be.
MODULE_INTRO = {
    "Dashboard":         ("📊 Fleet Dashboard",
                          "Fleet-wide KPIs, compliance donut, daily emissions trend and attribute filters will appear here."),
    "Fleet Intelligence":("🚌 Fleet Intelligence",
                          "Engine-family league tables, Euro-class comparisons and operator breakdowns will appear here."),
    "Pollutant Engine":  ("🌫 Pollutant Engine",
                          "Methodology comparison, speed-vs-emission scatter and Euro × fuel heatmap will appear here."),
    "Bus Efficiency":    ("⚡ Bus Efficiency",
                          "Per-category efficiency, load-factor scatter and the bus compliance ranking will appear here."),
    "Corridor Map":      ("🗺 Corridor Map",
                          "Interactive Lagos BRT corridor map, coloured by emission intensity, will appear here."),
    "Fleet Health":      ("🩺 Fleet Health",
                          "ML anomaly detection: buses drifting from their own normal or their peer group — an early-warning list for maintenance."),
    "Data Quality":      ("🧪 Data Quality",
                          "Automated validation of the loaded manifest — impossible distances, speed outliers, over-capacity ridership, duplicates and unmapped values, each with severity."),
    "What-If":           ("🎛 What-If Simulator",
                          "Fleet planning scenarios — fuel conversions, Euro upgrades, A/C policy, speed improvements — recomputed through the real emissions engine."),
    "Forecast":          ("📈 Forecast",
                          "Projected daily fleet CO₂ and ridership with confidence bands, plus per-bus compliance risk scores."),
    "Trip Inspector":    ("🔍 Trip Inspector",
                          "Pick any bus and day to see its CO₂ split into hot-running, cold-start, idling and A/C load."),
    "Formula Explainer": ("🧮 Formula Explainer",
                          "Every multiplier and addend of the calculation, walked through with a real trip's numbers."),
    "Deep Search":       ("📋 Deep Search",
                          "Filter, inspect and export the full calculated manifest as CSV."),
}

import html as _html

def render_ai_assistant(data):
    """Floating Gemini assistant: FAB bottom-right, chat panel above it.
    Renders on every page, with or without data."""
    if "ai_open" not in st.session_state:
        st.session_state.ai_open = False
    if "ai_chat" not in st.session_state:
        st.session_state.ai_chat = []

    if st.button("✖" if st.session_state.ai_open else "✨", key="ai_fab",
                 help="Fleet Assistant (Gemini)"):
        st.session_state.ai_open = not st.session_state.ai_open
        st.rerun()
    if not st.session_state.ai_open:
        return

    with st.container(key="ai_panel"):
        st.markdown('<div class="ai-head">✨ Fleet Assistant '
                    '<span class="ai-sub">GEMINI · AGGREGATES ONLY</span></div>',
                    unsafe_allow_html=True)

        if not ai_engine.is_configured():
            st.markdown('<div class="ai-msg-a">Not configured — add a '
                        '<strong>[gemini] api_key</strong> to Streamlit secrets '
                        'to enable me. Everything else works without it.</div>',
                        unsafe_allow_html=True)
            return
        if data is None or len(data) == 0:
            st.markdown('<div class="ai-msg-a">No data loaded yet — upload a '
                        'manifest or connect the database, then ask me anything '
                        'about the fleet.</div>', unsafe_allow_html=True)
            return

        fp = ai_engine.fingerprint(data)
        pack = ai_engine.build_fact_pack(
            data, target_pollutants, basis, methodology, ambient_c,
            corridor_fn=globals().get("corridor_aggregate"))

        for role, msg in st.session_state.ai_chat[-8:]:
            cls = "ai-msg-u" if role == "user" else "ai-msg-a"
            safe = _html.escape(msg).replace("\n", "<br>")
            st.markdown(f'<div class="{cls}">{safe}</div>', unsafe_allow_html=True)

        qc1, qc2 = st.columns(2)
        with qc1:
            if st.button("✨ Insights", key="ai_ins", use_container_width=True,
                         help="4-5 decision-relevant observations from the current data"):
                with st.spinner("Analysing the fleet…"):
                    txt, _ok = ai_engine.generate_insights(pack, fp)
                st.session_state.ai_chat.append(("assistant", txt))
                st.rerun()
        with qc2:
            if st.button("🧹 Clear", key="ai_clr", use_container_width=True):
                st.session_state.ai_chat = []
                st.rerun()

        with st.form("ai_form", clear_on_submit=True, border=False):
            q = st.text_input("Ask", key="ai_q", label_visibility="collapsed",
                              placeholder="e.g. which operator should we inspect first?")
            sent = st.form_submit_button("Send ➤", use_container_width=True)
        if sent and q.strip():
            st.session_state.ai_chat.append(("user", q.strip()))
            hist = "\n".join(f"{r}: {m}" for r, m in st.session_state.ai_chat[-7:-1])
            with st.spinner("Thinking…"):
                txt, _ok = ai_engine.answer_question(pack, q.strip(), hist, fp)
            st.session_state.ai_chat.append(("assistant", txt))
            st.rerun()

        _mdl = st.session_state.get("_ai_model_used", "")
        st.markdown('<div class="ai-sub" style="padding-top:6px;">Answers use '
                    'pre-computed aggregate statistics only — raw trip rows never '
                    'leave the server. Cached answers are instant and cost no quota.'
                    + (f' · model: {_mdl}' if _mdl else '') + '</div>',
                    unsafe_allow_html=True)


def render_module_shell(module, db_connected=False):
    """Full interface, no data yet: draw the selected module's frame
    with a compact 'awaiting data' panel where its charts will be."""
    title, desc = MODULE_INTRO.get(module, (APP_NAME, ""))
    hint = ("The database is connected but empty — your first upload seeds it, "
            "and every session after that loads automatically."
            if db_connected else
            "Upload one or more monthly manifests in the sidebar — CSV or Excel (.xlsx). "
            "Several files at once are merged into a single fleet view automatically.")
    st.markdown(f"## {title}")
    st.markdown(f"""
    <div class="empty">
        <div class="icon">🚌</div>
        <h2>Awaiting route manifest</h2>
        <p>{desc}</p>
        <p>{hint}<br><br>
        Required columns: <code>Date</code> <code>Route_Name</code> <code>Bus_ID</code>
        <code>Operator</code> <code>Bus_Category</code> <code>Fuel_Type</code>
        <code>Route_Distance_km</code> <code>Avg_Speed_kmh</code> <code>Ridership</code>
        <code>Revenue_Trip</code><br><br>
        Recommended additions: <code>Euro_Standard</code> <code>Vehicle_Age_years</code>
        <code>AC_Status</code> <code>Num_Trips_Today</code> <code>Engine_Model</code></p>
        <p style="font-size:12px;color:var(--text-tert);">
        IPCC Tier 2 · COPERT V (normalised speed curves) · Euro class NOx/PM ·
        Age deterioration · Temperature-aware cold start · A/C correction</p>
    </div>""", unsafe_allow_html=True)

def _fuzzy_rename(df: pd.DataFrame, required: list, optional: list) -> tuple:
    """
    Column-order-independent loader with fuzzy name matching.

    Strategy (applied in order, stops at first match per target):
      1. Exact match            — 'Bus_Category'  == 'Bus_Category'
      2. Case-insensitive       — 'bus_category'  → 'Bus_Category'
      3. Strip spaces/dashes    — 'Bus Category'  → 'Bus_Category'
      4. Common abbreviations   — 'dist'          → 'Route_Distance_km'
      5. Substring match        — 'distance'      → 'Route_Distance_km'

    Returns (renamed_df, auto_renames_dict, still_missing_list)
    """
    import re

    ALIASES = {
        "Bus_Category":       ["bus_type","category","bus_size","vehicle_type","type"],
        "Fuel_Type":          ["fuel","fueltype","energy_source","propulsion"],
        "Route_Distance_km":  ["distance","dist","km","route_km","distance_km","trip_distance"],
        "Avg_Speed_kmh":      ["speed","avg_speed","average_speed","speed_kmh"],
        "Ridership":          ["passengers","pax","riders","passenger_count","boardings"],
        "Revenue_Trip":       ["revenue","is_revenue","paid_trip","commercial"],
        "Route_Name":         ["route","routename","line","route_id"],
        "Bus_ID":             ["bus","vehicle_id","vehicle","fleet_id","bus_no","plate"],
        "Operator":           ["company","operator_name","fleet_operator","owner"],
        "Date":               ["trip_date","date_of_trip","service_date","day"],
        "Euro_Standard":      ["euro","euro_class","emission_standard","euro_norm","standard"],
        "Vehicle_Age_years":  ["age","vehicle_age","age_years","bus_age","years_old"],
        "AC_Status":          ["ac","air_conditioning","aircon","has_ac","ac_on"],
        "Num_Trips_Today":    ["trips","daily_trips","trips_today","num_trips","trip_count"],
        "Engine_Model":       ["engine","motor","engine_type","engine_name","powerunit"],
    }

    def normalise(s):
        return re.sub(r"[\s\-/]", "_", str(s)).lower().strip("_")

    csv_cols   = list(df.columns)
    norm_map   = {normalise(c): c for c in csv_cols}   # normalised → original csv name
    rename_map = {}   # original csv name → canonical target name
    auto_log   = {}   # canonical → original (for user feedback)

    for target in (required + optional):
        if target in csv_cols:
            continue   # exact match, nothing to do

        norm_target = normalise(target)
        matched = None

        # 1. case-insensitive / spacing normalise
        if norm_target in norm_map:
            matched = norm_map[norm_target]

        # 2. alias list
        if not matched:
            for alias in ALIASES.get(target, []):
                if alias in norm_map:
                    matched = norm_map[alias]
                    break

        # 3. substring: csv col contains target keyword or vice-versa
        if not matched:
            kw = norm_target.split("_")[0]   # e.g. "route" from "route_distance_km"
            for nc, oc in norm_map.items():
                if kw in nc or nc in norm_target:
                    matched = oc
                    break

        if matched and matched not in rename_map:
            rename_map[matched] = target
            auto_log[target]    = matched

    df = df.rename(columns=rename_map)
    still_missing = [c for c in required if c not in df.columns]
    return df, auto_log, still_missing


def _read_raw_file(name, fbytes):
    """Read a single uploaded file (CSV or Excel) into a raw DataFrame."""
    import io
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if ext in ("xlsx", "xls"):
        try:
            df = pd.read_excel(io.BytesIO(fbytes), sheet_name=0)
        except Exception as e:
            return None, f"Could not read Excel file ({e.__class__.__name__})"
    else:
        df = None
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(io.BytesIO(fbytes), encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            return None, "Could not decode CSV (tried UTF-8, Latin-1, CP1252)"
    df.columns = [str(c).lstrip("\ufeff").strip() for c in df.columns]
    return df, None


@st.cache_data(show_spinner="Reading and calculating emissions…", ttl=300)
def load_and_calc(files, method, pollutants, ambient=28.0, basis="passenger"):
    """files: tuple of (filename, filebytes) — one per uploaded monthly manifest.
    Each file is read and column-matched independently, then all valid files
    are merged into a single dataframe before calculation."""
    frames, file_log, auto_log = [], [], {}

    for name, fbytes in files:
        raw, err = _read_raw_file(name, fbytes)
        if err:
            file_log.append({"name": name, "rows": 0, "status": "error", "detail": err})
            continue

        renamed, log, still_missing = _fuzzy_rename(raw, EXPECTED_COLS, NEW_COLS)
        if still_missing:
            file_log.append({"name": name, "rows": 0, "status": "error",
                              "detail": f"Missing: {', '.join(still_missing)}",
                              "cols": raw.columns.tolist()})
            continue

        renamed["Source_File"] = name
        frames.append(renamed)
        auto_log.update(log)
        file_log.append({"name": name, "rows": len(renamed), "status": "ok", "detail": ""})

    if not frames:
        return None, file_log, {}, []

    df = pd.concat(frames, ignore_index=True, sort=False)
    df = _clean_and_calculate(df, method, pollutants, ambient, basis)
    return df, file_log, auto_log, []


def _clean_and_calculate(df, method, pollutants, ambient, basis):
    """Shared pipeline: normalise a raw manifest DataFrame (from uploads
    OR the database) and run the emissions engine over it."""

    # ── Clean operator names (leading/trailing spaces) ──
    if "Operator" in df.columns:
        df["Operator"] = df["Operator"].astype(str).str.strip()

    # ── Date parsing — try DD/MM/YYYY first, then auto-detect ──
    if "Date" in df.columns:
        parsed = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        if parsed.isna().mean() > 0.5:
            parsed = pd.to_datetime(df["Date"], errors="coerce")
        df["Date"] = parsed.dt.date
        df["Month"] = parsed.dt.strftime("%b %Y")

    # ── Revenue_Trip: numeric = revenue amount in Naira; a trip only
    # counts as "revenue" if that amount is actually > 0 (per row, not blanket) ──
    if "Revenue_Trip" in df.columns:
        sample = pd.to_numeric(df["Revenue_Trip"].iloc[:20], errors="coerce").dropna()
        if len(sample) > 0 and sample.mean() > 10:
            numeric_rev = pd.to_numeric(df["Revenue_Trip"], errors="coerce").fillna(0)
            if "Revenue_Naira" not in df.columns:      # DB rows already carry it
                df = df.rename(columns={"Revenue_Trip": "Revenue_Naira"})
            df["Revenue_Trip"] = numeric_rev > 0
        else:
            df["Revenue_Trip"] = df["Revenue_Trip"].astype(str).str.lower() \
                .isin(["true", "1", "yes", "t"])

    # ── Bus_Category: normalise short codes to canonical names ──
    # NOTE: "unknown" is intentionally left as "Unknown" rather than
    # guessed — it falls through to FALLBACK_FACTORS in the engine and
    # is flagged via Category_Unmapped so it's visible/filterable in the UI,
    # instead of silently being counted as "High Capacity".
    CAT_MAP = {
        "hc": "High Capacity", "high capacity": "High Capacity",
        "midi": "Midi", "mid": "Midi",
        "mini": "Mini",
        "flm": "Mini", "flm x30l": "Mini", "x30l": "Mini",
    }
    if "Bus_Category" in df.columns:
        raw_cat = df["Bus_Category"].astype(str).str.strip()
        is_unmapped = ~raw_cat.str.lower().isin(CAT_MAP.keys())
        df["Category_Unmapped"] = is_unmapped
        df["Bus_Category"] = raw_cat.str.lower().map(CAT_MAP)
        df.loc[is_unmapped, "Bus_Category"] = raw_cat[is_unmapped]  # keep original label, e.g. "Unknown"

    # ── Fuel_Type: normalise aliases (PMS = petrol) ──
    FUEL_MAP = {
        "pms": "Petrol", "petrol": "Petrol", "gasoline": "Petrol",
        "diesel": "Diesel", "cng": "CNG", "electric": "Electric",
        "ev": "Electric", "biogas": "Biogas", "hybrid": "Hybrid",
    }
    if "Fuel_Type" in df.columns:
        raw_fuel = df["Fuel_Type"].astype(str).str.strip()
        df["Fuel_Unmapped"] = ~raw_fuel.str.lower().isin(FUEL_MAP.keys())
        df["Fuel_Type"] = raw_fuel.str.lower().map(lambda x: FUEL_MAP.get(x, str(x).title()) if pd.notna(x) else "Unknown")

    # ── Num_Trips_Today: real data has fractional values, floor to int ──
    if "Num_Trips_Today" in df.columns:
        df["Num_Trips_Today"] = pd.to_numeric(df["Num_Trips_Today"], errors="coerce") \
            .fillna(1).clip(lower=0).round().astype(int)
        df["Num_Trips_Today"] = df["Num_Trips_Today"].replace(0, 1)

    # ── Numeric coercion for key fields ──
    for col in ["Route_Distance_km", "Avg_Speed_kmh", "Ridership", "Vehicle_Age_years"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # ── Fill optional new columns with sensible defaults if absent ──
    defaults = {
        "Euro_Standard":     "Euro III",
        "Vehicle_Age_years": 5,
        "AC_Status":         False,
        "Num_Trips_Today":   6,
        "Engine_Model":      "",
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    # ── Calculate emissions ──
    results = df.apply(lambda r: calculate_row(r, method, pollutants, ambient), axis=1)
    df = pd.concat([df, results], axis=1)

    # ── Emission basis ──
    # The engine outputs both views for every pollutant:
    #   *_g_pkm  — grams per passenger-km (efficiency of moving people)
    #   *_g_km   — grams per vehicle-km   (what the bus physically emits)
    # All modules read the *_g_pkm columns, so in vehicle mode we point
    # those display columns at the per-vehicle values instead.
    if basis == "vehicle":
        for p in ("CO2", "NOx", "PM"):
            if f"{p}_g_km" in df.columns:
                df[f"{p}_g_pkm"] = df[f"{p}_g_km"]

    if "CO2" in pollutants:
        df["Compliance"] = df.apply(
            lambda r: compliance_flag(r.get("CO2_g_pkm"), r["Bus_Category"], basis),
            axis=1)
    else:
        df["Compliance"] = "N/A"

    return df


@st.cache_data(show_spinner="Loading fleet history from database…", ttl=300)
def load_db_and_calc(method, pollutants, ambient=28.0, basis="passenger"):
    """Database path: pull every stored trip (with bus attributes) and
    run it through the exact same cleaning + engine pipeline as uploads."""
    raw = db.load_trips()
    if raw is None or len(raw) == 0:
        return None
    return _clean_and_calculate(raw, method, pollutants, ambient, basis)


# ════════════════════════════════════════════════════════
# DATA RESOLUTION — uploads win; otherwise the database;
# otherwise the module shell (full interface, no data yet)
# ════════════════════════════════════════════════════════
df, file_log, auto_log = None, [], {}
data_source = None

if uploaded_files:
    files_payload = tuple((f.name, f.getvalue()) for f in uploaded_files)
    df, file_log, auto_log, _unused = load_and_calc(
        files_payload, methodology, target_pollutants, ambient_c, basis)
    data_source = "upload"

    # ── One-time ingestion into Supabase (deduplicated server-side) ──
    if df is not None and save_uploads_to_db:
        _ing_key = tuple((f.name, len(b)) for f, b in
                         zip(uploaded_files, (p[1] for p in files_payload)))
        if st.session_state.get("_ingested_key") != _ing_key:
            with st.spinner("Saving manifest to database…"):
                ing = db.ingest_dataframe(df, source_file=", ".join(f.name for f in uploaded_files))
            st.session_state._ingested_key = _ing_key
            if ing["error"]:
                st.warning(f"Database save failed (app continues from the upload): {ing['error']}")
            else:
                st.toast(f"💾 Saved to database — {ing['buses']} buses, "
                         f"{ing['trips_sent']:,} trip rows (duplicates skipped)")
elif _db_state == "connected":
    df = load_db_and_calc(methodology, tuple(target_pollutants), ambient_c, basis)
    data_source = "database"

if df is None and not uploaded_files:
    render_module_shell(selected_module, db_connected=(_db_state in ("connected", "empty")))
    render_ai_assistant(None)
    st.stop()

ok_files  = [f for f in file_log if f["status"] == "ok"]
err_files = [f for f in file_log if f["status"] == "error"]

if df is None and data_source == "upload":
    # ── Every file failed — rich diagnostic UI ──
    st.markdown("### ❌ None of the uploaded files could be read")
    FIX_HINT = {
        "Date":              "e.g. `Date`, `trip_date`, `service_date`",
        "Route_Name":        "e.g. `Route_Name`, `route`, `line`",
        "Bus_ID":            "e.g. `Bus_ID`, `bus_no`, `vehicle_id`",
        "Operator":          "e.g. `Operator`, `company`, `owner`",
        "Bus_Category":      "e.g. `Bus_Category`, `bus_type`, `category`",
        "Fuel_Type":         "e.g. `Fuel_Type`, `fuel`, `propulsion`",
        "Route_Distance_km": "e.g. `Route_Distance_km`, `distance`, `km`",
        "Avg_Speed_kmh":     "e.g. `Avg_Speed_kmh`, `speed`, `avg_speed`",
        "Ridership":         "e.g. `Ridership`, `passengers`, `pax`",
        "Revenue_Trip":      "e.g. `Revenue_Trip`, `revenue`, `is_revenue`",
    }
    for f in err_files:
        with st.expander(f"`{f['name']}` — {f['detail']}", expanded=True):
            if "cols" in f:
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**Columns found**")
                    for c in f["cols"]:
                        st.markdown(f"- `{c}`")
                with col_b:
                    st.markdown("**Could not resolve**")
                    for m in f["detail"].replace("Missing: ", "").split(", "):
                        hint = FIX_HINT.get(m, "see documentation")
                        st.markdown(f"- **`{m}`** — {hint}")
    st.info("💡 Tip: column order doesn't matter — only names need to match (case-insensitive, fuzzy-matched automatically).")
    st.stop()

# ── Manifest log — confirms exactly what got loaded ──
if data_source == "database":
    st.markdown(
        f'<div style="font-family:var(--mono,monospace);font-size:10.5px;letter-spacing:0.05em;'
        f'color:#5c7268;margin-bottom:4px;">DATA SOURCE · SUPABASE · {len(df):,} trip rows · '
        f'loaded automatically, no upload needed</div>', unsafe_allow_html=True)
elif file_log:
    log_rows = "".join(
        f'<div class="board-row" style="grid-template-columns:1fr 100px 90px;">'
        f'<div><div class="route">{f["name"]}</div></div>'
        f'<div class="figure">{f["rows"]:,} rows</div>'
        f'<div style="text-align:right;"><span class="status-chip {"good" if f["status"]=="ok" else "over"}">'
        f'{"LOADED" if f["status"]=="ok" else "FAILED"}</span></div></div>'
        for f in file_log
    )
    with st.expander(f"📋 Manifest log — {len(ok_files)} file(s) loaded, {len(df):,} total rows"
                      + (f", {len(err_files)} failed" if err_files else ""),
                      expanded=bool(err_files)):
        st.markdown(f'<div class="board">{log_rows}</div>', unsafe_allow_html=True)
        if err_files:
            st.warning(
                f"{len(err_files)} file(s) couldn't be matched and were skipped: "
                + ", ".join(f"`{f['name']}`" for f in err_files)
                + ". The rest of the data loaded fine — fix and re-upload the skipped file(s) separately if needed.")

# ── Notify user of any auto-renames ──
if auto_log:
    rename_chips = " &nbsp;" .join(
        f'<code style="font-size:11px;background:var(--autorename-bg);color:var(--autorename-text);padding:2px 7px;border-radius:3px;">{orig}</code> → <code style="font-size:11px;background:var(--badge-good-bg);color:var(--badge-good-text);padding:2px 7px;border-radius:3px;">{canon}</code>'
        for canon, orig in auto_log.items()
    )
    st.markdown(
        f'<div class="autorename-bar"><strong>🔄 Auto-matched {len(auto_log)} column name(s) across uploaded files:</strong>&nbsp; {rename_chips}</div>',
        unsafe_allow_html=True)
if not target_pollutants:
    st.warning("Select at least one pollutant in the sidebar.")
    st.stop()

# ── Flag rows using fallback emission factors due to unmapped category/fuel ──
n_cat_unmapped = int(df["Category_Unmapped"].sum()) if "Category_Unmapped" in df.columns else 0
n_fuel_unmapped = int(df["Fuel_Unmapped"].sum()) if "Fuel_Unmapped" in df.columns else 0
if (n_cat_unmapped or n_fuel_unmapped) and not exclude_unmapped:
    bits = []
    if n_cat_unmapped: bits.append(f"{n_cat_unmapped:,} row(s) with an unrecognised Bus_Category")
    if n_fuel_unmapped: bits.append(f"{n_fuel_unmapped:,} row(s) with an unrecognised Fuel_Type")
    st.markdown(
        f'<div style="background:var(--badge-over-bg);border:1px solid #5c1818;border-radius:4px;'
        f'padding:10px 16px;margin-bottom:12px;font-size:12px;color:var(--badge-over-text);">'
        f'<strong>⚠ Data quality:</strong> {" and ".join(bits)} — these are using generic '
        f'fallback emission factors, not their fleet-specific values. '
        f'Check <em>Exclude rows with unmapped category/fuel</em> in the sidebar to drop them, '
        f'or filter by them in Deep Search.</div>', unsafe_allow_html=True)

# ── Apply sidebar quick filters ──
def apply_filters(src):
    d = src.copy()
    if st.session_state.active_operator: d = d[d["Operator"]   == st.session_state.active_operator]
    if st.session_state.active_euro:     d = d[d["Euro_Standard"] == st.session_state.active_euro]
    if st.session_state.active_fuel:     d = d[d["Fuel_Type"]  == st.session_state.active_fuel]
    if st.session_state.active_category: d = d[d["Bus_Category"]== st.session_state.active_category]
    if st.session_state.active_month and "Month" in d.columns:
        d = d[d["Month"] == st.session_state.active_month]
    if st.session_state.active_daterange and "Date" in d.columns:
        start, end = st.session_state.active_daterange
        d = d[(d["Date"] >= start) & (d["Date"] <= end)]
    if exclude_unmapped:
        if "Category_Unmapped" in d.columns: d = d[~d["Category_Unmapped"]]
        if "Fuel_Unmapped"     in d.columns: d = d[~d["Fuel_Unmapped"]]
    return d

# ════════════════════════════════════════════════════════
# MODULE 0 — ACTIVE FILTER BANNER (shown on every page)
# ════════════════════════════════════════════════════════
active_filters = {k:v for k,v in {
    "Operator":  st.session_state.active_operator,
    "Euro":      st.session_state.active_euro,
    "Fuel":      st.session_state.active_fuel,
    "Category":  st.session_state.active_category,
    "Month":     st.session_state.active_month,
    "Date range": f"{st.session_state.active_daterange[0]} → {st.session_state.active_daterange[1]}"
                  if st.session_state.active_daterange else None,
}.items() if v}

if active_filters:
    chip_map = {"Operator":"chip-blue","Euro":"chip-purple","Fuel":"chip-green",
                "Category":"chip-amber","Month":"chip-blue","Date range":"chip-blue"}
    chips_html = " ".join(chip(f"{k}: {v}", chip_map.get(k,"chip-gray")) for k,v in active_filters.items())
    st.markdown(
        f'<div class="filter-bar">'
        f'<strong>Active filters:</strong>&nbsp; {chips_html}</div>',
        unsafe_allow_html=True)

fdf = apply_filters(df)  # filtered dataframe used by all modules


# ════════════════════════════════════════════════════════
# CORRIDOR MAP — reusable renderer (full module + dashboard mini)
# Geometry is schematic; region-specific but swappable. When per-route
# lat/lon columns are added to the manifest, exact plotting takes over.
# ════════════════════════════════════════════════════════
CORRIDORS = {
    "Abule Egba – Oshodi – TBS": {
        "path": [[3.2938, 6.6480], [3.3050, 6.6100], [3.3480, 6.5560],
                 [3.3690, 6.5310], [3.4053, 6.4433]],
        "keywords": ["abule", "sango", "abesan", "iyana-ipaja", "iyana ipaja", "dopemu", "meiran"],
    },
    "Ikorodu – TBS": {
        "path": [[3.5116, 6.6194], [3.4400, 6.6050], [3.3900, 6.5960],
                 [3.3860, 6.5870], [3.3690, 6.5310], [3.4053, 6.4433]],
        "keywords": ["ikorodu", "elepe", "igbogbo", "odogunyan", "odongunyan",
                     "agric", "isawo", "ogolonto", "fadeyi"],
    },
    "Ikeja Axis": {
        "path": [[3.2635, 6.6155], [3.3376, 6.6018], [3.3565, 6.6187],
                 [3.3200, 6.6250], [3.3480, 6.5560]],
        "keywords": ["ikeja", "agege", "ayobo", "egbeda", "ikotun", "igando",
                     "baruwa", "alausa", "allen", "ijaiye", "iju", "kola"],
    },
    "Ajah – CMS / Marina": {
        "path": [[3.5670, 6.4667], [3.4730, 6.4410], [3.4270, 6.4290],
                 [3.4059, 6.4488], [3.3890, 6.4500]],
        "keywords": ["ajah", "marina", "eko hotel", "cms", "lekki", "falomo",
                     "tinubu", "adeola"],
    },
    "Oshodi / Berger – Inner City": {
        "path": [[3.3776, 6.6413], [3.3860, 6.5870], [3.3792, 6.5095],
                 [3.3480, 6.5560], [3.2989, 6.4666]],
        "keywords": ["berger", "ojota", "yaba", "unilag", "oshodi", "cele",
                     "mile 2", "okokomaiko", "obalende", "ogba", "olowora",
                     "maryland", "magodo", "ketu", "dalemo", "joke-ayo"],
    },
}

def match_corridor(route_name):
    r = str(route_name).lower()
    for cname, cdef in CORRIDORS.items():
        if any(k in r for k in cdef["keywords"]):
            return cname
    return "Oshodi / Berger – Inner City"     # catch-all corridor

_MAP_STYLES = {
    "Dark":    "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    "Light":   "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    "Voyager": "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
}

def corridor_aggregate(data, pollutant):
    mdf = data.copy()
    mdf["Corridor"] = mdf["Route_Name"].apply(match_corridor)
    kg_col, eff_col = f"{pollutant}_kg", f"{pollutant}_g_pkm"
    return mdf.groupby("Corridor").agg(
        Total_kg=(kg_col, "sum") if kg_col in mdf.columns else ("Bus_ID", "count"),
        Eff=(eff_col, "mean") if eff_col in mdf.columns else ("Bus_ID", "count"),
        Trips=("Bus_ID", "count"),
        Buses=("Bus_ID", "nunique"),
        Pax=("Ridership", "sum"),
    ).reset_index()

def render_corridor_map(data, pollutant="CO2", metric="total", height=560,
                        theme="Dark", key="cmap"):
    """Draw the interactive corridor map. metric: 'total' | 'eff'."""
    import pydeck as pdk
    agg = corridor_aggregate(data, pollutant)
    val_col = "Total_kg" if metric == "total" else "Eff"
    vmax = max(float(agg[val_col].max() or 1), 1e-9)

    def _color(v):
        t = min(float(v or 0) / vmax, 1.0)
        if t < 0.5:
            f = t / 0.5
            return [int(62+f*(255-62)), int(242-f*(242-194)), int(160-f*(160-75)), 210]
        f = (t-0.5)/0.5
        return [255, int(194-f*(194-99)), int(75+f*(99-75)), 220]

    rows = []
    for _, r in agg.iterrows():
        cdef = CORRIDORS[r["Corridor"]]
        rows.append({
            "name": r["Corridor"], "path": cdef["path"],
            "color": _color(r[val_col]),
            "width": 60 + 240 * min(float(r[val_col] or 0)/vmax, 1.0),
            "total": f"{r['Total_kg']:,.0f} kg",
            "eff": f"{r['Eff']:.1f} {st.session_state.get('eff_unit','g/pkm')}",
            "trips": int(r["Trips"]), "buses": int(r["Buses"]),
            "pax": f"{int(r['Pax']):,}",
        })
    terminals = [{"name": n, "pos": c["path"][i]}
                 for n, c in CORRIDORS.items() for i in (0, -1)]
    deck = pdk.Deck(
        layers=[
            pdk.Layer("PathLayer", rows, get_path="path", get_color="color",
                      get_width="width", width_min_pixels=4, pickable=True,
                      cap_rounded=True, joint_rounded=True),
            pdk.Layer("ScatterplotLayer", terminals, get_position="pos",
                      get_radius=350, get_fill_color=[238, 243, 240, 200],
                      get_line_color=[30, 115, 190], line_width_min_pixels=2, stroked=True),
        ],
        initial_view_state=pdk.ViewState(latitude=6.545, longitude=3.38,
                                         zoom=10.4, pitch=35),
        map_style=_MAP_STYLES[theme],
        tooltip={"html": "<b>{name}</b><br/>"
                         f"{pollutant}: " + "{total} · {eff}<br/>"
                         "Trips: {trips} · Buses: {buses} · Passengers: {pax}"},
    )
    st.pydeck_chart(deck, height=height)
    return agg

def render_corridor_module():
    st.markdown("## 🗺 Corridor Map")
    st.markdown(
        '<div class="banner">Schematic transit corridors coloured by emission intensity. '
        'Routes are matched to corridors by name keywords for now — when per-route '
        'latitude/longitude columns are added to the manifest, this map will plot '
        'exact route geometry automatically.</div>', unsafe_allow_html=True)
    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        map_pol = st.selectbox("Pollutant",
            [p for p in ["CO2", "NOx", "PM"] if p in target_pollutants] or ["CO2"])
    with mc2:
        map_metric = st.selectbox("Colour by",
            ["Total emissions (kg)", f"Efficiency ({st.session_state.eff_unit})"])
    with mc3:
        map_theme = st.selectbox("Base map", ["Dark", "Light", "Voyager"])
    agg = render_corridor_map(fdf, map_pol,
                              "total" if map_metric.startswith("Total") else "eff",
                              height=560, theme=map_theme, key="cmap_full")
    st.markdown('<div class="sec-label">Corridor totals — switch the view if the map is not what you need</div>',
                unsafe_allow_html=True)
    board = agg.rename(columns={"Total_kg": f"{map_pol} kg",
                                "Eff": st.session_state.eff_unit,
                                "Trips": "Rows", "Pax": "Passengers"}).round(1)
    chart_switcher(board, x="Corridor", y=f"{map_pol} kg", key="cmap_board",
                   kinds=("Bar", "Pie", "Table"), default="Table",
                   sort_desc=True, height=320)
    st.caption("Corridor geometry is schematic. Add Route_Lat / Route_Lon columns "
               "to the manifest to unlock exact per-route plotting.")


# ── Basis banner — makes clear which unit every efficiency figure uses ──
_basis_txt = ("passenger-km (g/pkm) — how efficiently people are moved"
              if basis == "passenger" else
              "vehicle-km (g/km) — what each bus physically emits")
st.markdown(
    f'<div style="font-family:var(--mono,monospace);font-size:10.5px;letter-spacing:0.05em;'
    f'color:#5c7268;margin-bottom:8px;">EMISSION BASIS · per {_basis_txt} · '
    f'ambient {ambient_c} °C</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# MODULE 1 — DASHBOARD
# ════════════════════════════════════════════════════════
if selected_module == "Dashboard":
    st.markdown("## 📊 Fleet Dashboard")
    st.markdown(
        f'<div class="banner">Real-time fleet overview using <strong>{methodology}</strong> methodology. '
        f'Emission factors include <strong>Euro class corrections</strong>, <strong>vehicle age deterioration</strong>, '
        f'<strong>A/C status</strong>, and <strong>engine model</strong> adjustments. '
        f'Click any operator, Euro standard, fuel type, or category chip below to filter all modules.</div>',
        unsafe_allow_html=True)

    rev = fdf[fdf["Revenue_Trip"].astype(str).str.lower().isin(["true","1"])]
    co2_total   = fdf["CO2_kg"].sum()   if "CO2_kg"   in fdf else 0
    nox_total   = fdf["NOx_kg"].sum()   if "NOx_kg"   in fdf else 0
    avg_eff     = rev["CO2_g_pkm"].mean() if "CO2_g_pkm" in rev and "CO2" in target_pollutants else 0
    over_ct     = (fdf["Compliance"]=="Over Limit").sum()
    ac_trips    = fdf["AC_Status"].astype(str).str.lower().isin(["true","1"]).sum() if "AC_Status" in fdf else 0
    ac_uplift   = fdf["ac_uplift_kg"].sum() if "ac_uplift_kg" in fdf else 0
    avg_age     = fdf["Vehicle_Age_years"].mean() if "Vehicle_Age_years" in fdf else 0

    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Total trips",       f"{len(fdf):,}")
    k2.metric("Total passengers",  f"{fdf['Ridership'].sum():,}")
    k3.metric("Total CO₂",         fmt_kg(co2_total) if "CO2" in target_pollutants else "—",
              delta=fmt_t(co2_total)+" tonnes" if co2_total > 0 else None)
    k4.metric("Fleet efficiency",  fmt_gkm(avg_eff)  if "CO2" in target_pollutants else "—")
    k5.metric("Over-limit trips",  str(over_ct), delta=f"{over_ct} need review", delta_color="inverse")
    k6.metric("A/C CO₂ uplift",    fmt_kg(ac_uplift), delta=f"{ac_trips} A/C trips")

    st.markdown('<div class="sec-label">Filter by attribute — dropdowns apply across all modules</div>', unsafe_allow_html=True)

    # ── Dropdown filter bar: Operator · Month · Date range · Euro · Fuel · Category ──
    months_all = sorted(df["Month"].dropna().unique(), key=lambda m: pd.to_datetime(m, format="%b %Y")) \
                 if "Month" in df.columns else []
    ops_all   = sorted([str(op) for op in df["Operator"].dropna().unique()])
    euros_all = sorted([str(eu) for eu in df["Euro_Standard"].dropna().unique()])
    fuels_all = sorted([str(fu) for fu in df["Fuel_Type"].dropna().unique()])
    cats_all  = sorted([str(bu) for bu in df["Bus_Category"].dropna().unique()])

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        op_choice = st.selectbox("Operator", ["All"] + ops_all,
            index=0 if not st.session_state.active_operator else
                  (ops_all.index(st.session_state.active_operator) + 1
                   if st.session_state.active_operator in ops_all else 0))
        new_op = None if op_choice == "All" else op_choice
        if new_op != st.session_state.active_operator:
            st.session_state.active_operator = new_op; st.rerun()
    with fc2:
        month_choice = st.selectbox("Month", ["All"] + months_all,
            index=0 if not st.session_state.active_month else
                  (months_all.index(st.session_state.active_month) + 1
                   if st.session_state.active_month in months_all else 0))
        new_month = None if month_choice == "All" else month_choice
        if new_month != st.session_state.active_month:
            st.session_state.active_month = new_month; st.rerun()
    with fc3:
        if "Date" in df.columns and df["Date"].notna().any():
            dmin, dmax = df["Date"].min(), df["Date"].max()
            current = st.session_state.active_daterange or (dmin, dmax)
            dr = st.date_input("Date range", value=current, min_value=dmin, max_value=dmax)
            if isinstance(dr, tuple) and len(dr) == 2:
                new_dr = None if dr == (dmin, dmax) else dr
                if new_dr != st.session_state.active_daterange:
                    st.session_state.active_daterange = new_dr; st.rerun()

    fc4, fc5, fc6 = st.columns(3)
    with fc4:
        eu_choice = st.selectbox("Euro standard", ["All"] + euros_all,
            index=0 if not st.session_state.active_euro else
                  (euros_all.index(st.session_state.active_euro) + 1
                   if st.session_state.active_euro in euros_all else 0))
        new_eu = None if eu_choice == "All" else eu_choice
        if new_eu != st.session_state.active_euro:
            st.session_state.active_euro = new_eu; st.rerun()
    with fc5:
        fu_choice = st.selectbox("Fuel type", ["All"] + fuels_all,
            index=0 if not st.session_state.active_fuel else
                  (fuels_all.index(st.session_state.active_fuel) + 1
                   if st.session_state.active_fuel in fuels_all else 0))
        new_fu = None if fu_choice == "All" else fu_choice
        if new_fu != st.session_state.active_fuel:
            st.session_state.active_fuel = new_fu; st.rerun()
    with fc6:
        ca_choice = st.selectbox("Bus category", ["All"] + cats_all,
            index=0 if not st.session_state.active_category else
                  (cats_all.index(st.session_state.active_category) + 1
                   if st.session_state.active_category in cats_all else 0))
        new_ca = None if ca_choice == "All" else ca_choice
        if new_ca != st.session_state.active_category:
            st.session_state.active_category = new_ca; st.rerun()

    st.markdown('<div class="sec-label">Emission overview</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if "CO2" in target_pollutants:
            op_co2 = fdf.groupby("Operator")["CO2_kg"].sum().reset_index()\
                        .sort_values("CO2_kg", ascending=False).head(12)
            chart_switcher(op_co2.round(1), x="Operator", y="CO2_kg", key="dash_op",
                           kinds=("Pie", "Bar", "Table"), default="Pie",
                           title="CO₂ share by operator (top 12)",
                           y_label="kg CO₂", sort_desc=True, height=360)

    with col2:
        # Euro class CO2 comparison
        if "CO2" in target_pollutants and "Euro_Standard" in fdf.columns:
            eu_co2 = fdf.groupby("Euro_Standard")["CO2_g_pkm"].mean().reset_index()
            eu_co2.columns = ["Euro Standard", "Avg intensity"]
            chart_switcher(eu_co2.round(1), x="Euro Standard", y="Avg intensity",
                           key="dash_euro", kinds=("Bar", "Line", "Table"),
                           title="Average CO₂ intensity by Euro class",
                           y_label=st.session_state.eff_unit, sort_desc=True, height=360)

    # Daily CO2 trend
    if "CO2" in target_pollutants:
        daily = fdf.groupby("Date")["CO2_kg"].sum().reset_index()
        daily["Date"] = daily["Date"].astype(str)
        chart_switcher(daily.round(1), x="Date", y="CO2_kg", key="dash_daily",
                       kinds=("Area", "Line", "Bar", "Table"), default="Area",
                       title="Daily CO₂ total", y_label="kg CO₂", height=340)

    # Compliance + age heatmap side-by-side
    col3, col4 = st.columns(2)
    with col3:
        comp_ct = fdf["Compliance"].value_counts().reset_index()
        comp_ct.columns = ["Status", "Trips"]
        chart_switcher(comp_ct, x="Status", y="Trips", key="dash_comp",
                       kinds=("Bar", "Pie", "Table"), default="Bar",
                       title="Trips by compliance status", y_label="Trips", height=340)
    with col4:
        if "Vehicle_Age_years" in fdf.columns and "CO2" in target_pollutants:
            age_eff = fdf.groupby("Vehicle_Age_years")["CO2_g_pkm"].mean().reset_index()
            age_eff.columns = ["Vehicle age (yrs)", "Avg intensity"]
            chart_switcher(age_eff.round(1), x="Vehicle age (yrs)", y="Avg intensity",
                           key="dash_age", kinds=("Bar", "Line", "Area", "Table"),
                           title="CO₂ intensity vs vehicle age",
                           y_label=st.session_state.eff_unit, height=340)

    # ── Corridor overview — compact embedded map (full module for detail) ──
    if "CO2" in target_pollutants:
        with st.expander("🗺 Corridor overview — CO₂ by corridor", expanded=True):
            render_corridor_map(fdf, "CO2", "total", height=380,
                                theme="Dark" if _is_dark else "Light", key="cmap_mini")
            st.caption("Compact view · open the Corridor Map module for pollutant, "
                       "metric and base-map controls plus the corridor league.")

    # ── Month-over-month — appears automatically once 2+ months exist ──
    _mom = fdf.copy()
    _mom["Month"] = pd.to_datetime(_mom["Date"], errors="coerce").dt.to_period("M").astype(str)
    _months = sorted(m for m in _mom["Month"].dropna().unique() if m != "NaT")
    if len(_months) >= 2 and "CO2" in target_pollutants:
        st.markdown('<div class="sec-label">Month-over-month</div>', unsafe_allow_html=True)
        mom = _mom.groupby("Month").agg(
            CO2_t=("CO2_kg", lambda x: x.sum() / 1000.0),
            Intensity=("CO2_g_pkm", "mean"),
            Trips=("Bus_ID", "count"),
            Pax=("Ridership", "sum")).reset_index().round(2)
        mom["Δ CO₂ %"] = (mom["CO2_t"].pct_change() * 100).round(1)
        mcol1, mcol2 = st.columns([3, 2])
        with mcol1:
            chart_switcher(mom, x="Month", y="CO2_t", key="dash_mom",
                           kinds=("Bar", "Line", "Table"), default="Bar",
                           title="Total CO₂ by month (tonnes)", y_label="t CO₂", height=320)
        with mcol2:
            latest, prev = mom.iloc[-1], mom.iloc[-2]
            st.metric(f"CO₂ · {latest['Month']}", f"{latest['CO2_t']:,.1f} t",
                      delta=f"{latest['Δ CO₂ %']:+.1f}% vs {prev['Month']}",
                      delta_color="inverse")
            st.metric("Avg intensity", f"{latest['Intensity']:.1f} {st.session_state.eff_unit}",
                      delta=f"{latest['Intensity'] - prev['Intensity']:+.1f}",
                      delta_color="inverse")
            st.metric("Passengers", f"{int(latest['Pax']):,}",
                      delta=f"{int(latest['Pax'] - prev['Pax']):+,}")

    # ── One-click summary report (HTML — print to PDF from the browser) ──
    st.markdown('<div class="sec-label">Report</div>', unsafe_allow_html=True)
    rep1, rep2 = st.columns([1, 3])
    with rep1:
        if st.button("📄 Build summary report", use_container_width=True):
            top = (fdf.groupby(["Bus_ID", "Operator"])["CO2_kg"].sum()
                      .reset_index().sort_values("CO2_kg", ascending=False).head(10))
            comp = fdf["Compliance"].value_counts()
            _rows = "".join(
                f"<tr><td>{r.Bus_ID}</td><td>{r.Operator}</td>"
                f"<td style='text-align:right'>{r.CO2_kg:,.0f}</td></tr>"
                for r in top.itertuples())
            _dates = f"{fdf['Date'].astype(str).min()} → {fdf['Date'].astype(str).max()}"
            _ai_para = ""
            if ai_engine.is_configured():
                _p = ai_engine.build_fact_pack(fdf, target_pollutants, basis,
                        methodology, ambient_c, corridor_fn=globals().get("corridor_aggregate"))
                _n, _okn = ai_engine.report_narrative(_p, ai_engine.fingerprint(fdf))
                if _okn:
                    _ai_para = f"<h2>Executive summary</h2><p>{_n}</p>"
            html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>{APP_NAME} — Summary</title><style>
body{{font-family:Arial,Helvetica,sans-serif;color:#16211c;margin:36px;}}
h1{{font-size:22px;border-bottom:3px solid #0E8F5F;padding-bottom:8px;}}
h2{{font-size:15px;margin-top:26px;color:#0E8F5F;}}
table{{border-collapse:collapse;width:100%;font-size:13px;}}
td,th{{border:1px solid #d6e5dc;padding:6px 10px;text-align:left;}}
th{{background:#e8f1ec;}} .kpi{{display:inline-block;margin:8px 22px 8px 0;}}
.kpi b{{font-size:20px;display:block;}} .kpi span{{font-size:11px;color:#667;}}
</style></head><body>
<h1>{APP_NAME} — Fleet Summary</h1>
<p>Period: {_dates} · Methodology: {methodology} · Basis: {st.session_state.eff_unit}
 · Ambient: {ambient_c} °C · Engine v4</p>{_ai_para}
<h2>Key figures</h2>
<div class='kpi'><b>{fdf['CO2_kg'].sum()/1000:,.1f} t</b><span>Total CO₂</span></div>
<div class='kpi'><b>{fdf['CO2_g_pkm'].mean():,.1f}</b><span>Avg {st.session_state.eff_unit}</span></div>
<div class='kpi'><b>{fdf['Bus_ID'].nunique():,}</b><span>Buses</span></div>
<div class='kpi'><b>{len(fdf):,}</b><span>Trip rows</span></div>
<div class='kpi'><b>{int(fdf['Ridership'].sum()):,}</b><span>Passengers</span></div>
<h2>Compliance</h2>
<p>Good: {int(comp.get('Good',0)):,} · Monitor: {int(comp.get('Monitor',0)):,}
 · Over Limit: {int(comp.get('Over Limit',0)):,}</p>
<h2>Top 10 CO₂ emitters</h2>
<table><tr><th>Bus</th><th>Operator</th><th>kg CO₂</th></tr>{_rows}</table>
<p style='margin-top:30px;font-size:11px;color:#889;'>Generated by {APP_NAME}.
 Open in a browser and print to PDF for distribution.</p>
</body></html>"""
            st.session_state["_report_html"] = html
    with rep2:
        if st.session_state.get("_report_html"):
            st.download_button("⬇ Download report (HTML)",
                               data=st.session_state["_report_html"].encode(),
                               file_name="fleet_summary_report.html", mime="text/html")

# ════════════════════════════════════════════════════════
# MODULE 2 — FLEET INTELLIGENCE
# ════════════════════════════════════════════════════════
elif selected_module == "Fleet Intelligence":
    st.markdown("## 🔍 Fleet Intelligence")
    st.markdown(
        '<div class="banner">Drill into individual buses and engine families. '
        'See how <strong>Euro standard</strong>, <strong>vehicle age</strong>, '
        '<strong>A/C status</strong>, and <strong>engine model</strong> compound to drive '
        'each vehicle\'s emission profile. Use the tabs to pivot between dimensions.</div>',
        unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["By Engine Model","By Euro Standard","By Vehicle Age","A/C Impact"])

    with tab1:
        st.markdown('<div class="sec-label">CO₂ per engine family</div>', unsafe_allow_html=True)
        if "Engine_Model" in fdf.columns and "CO2" in target_pollutants:
            eng = fdf[fdf["Revenue_Trip"].astype(str).str.lower().isin(["true","1"])]\
                .groupby("Engine_Model").agg(
                    Avg_CO2_g_pkm=("CO2_g_pkm","mean"),
                    Total_CO2_kg=("CO2_kg","sum"),
                    Trips=("Bus_ID","count"),
                    Avg_Age=("Vehicle_Age_years","mean"),
                ).reset_index().sort_values("Avg_CO2_g_pkm")
            c1, c2 = st.columns([2,1])
            with c1:
                fig = px.bar(eng, x="Engine_Model", y="Avg_CO2_g_pkm",
                             color="Avg_CO2_g_pkm",
                             color_continuous_scale=["#22c55e","#ef4444"],
                             title="Average CO₂ g/pkm by engine model",
                             text=eng["Avg_CO2_g_pkm"].round(1).astype(str)+" g")
                fig.update_layout(**PLY_BASE, title_font_size=13, showlegend=False,
                                  coloraxis_showscale=False,
                                  xaxis_title="", yaxis_title="g CO₂/pkm")
                fig.update_traces(textposition="outside", cliponaxis=False)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.dataframe(eng.round(2), use_container_width=True, hide_index=True,
                    column_config={
                        "Engine_Model":  st.column_config.TextColumn("Engine"),
                        "Avg_CO2_g_pkm":st.column_config.NumberColumn("g CO₂/pkm", format="%.1f"),
                        "Total_CO2_kg": st.column_config.NumberColumn("Total kg",   format="%.1f"),
                        "Trips":        st.column_config.NumberColumn("Trips"),
                        "Avg_Age":      st.column_config.NumberColumn("Avg age",    format="%.1f"),
                    })

    with tab2:
        st.markdown('<div class="sec-label">Euro class emission comparison</div>', unsafe_allow_html=True)
        if "Euro_Standard" in fdf.columns:
            euro_agg = fdf.groupby(["Euro_Standard","Bus_Category"]).agg(
                CO2_g=("CO2_g_pkm","mean"),
                NOx_g=("NOx_g_pkm","mean") if "NOx_g_pkm" in fdf.columns else ("CO2_g_pkm","count"),
                PM_g =("PM_g_pkm", "mean")  if "PM_g_pkm"  in fdf.columns else ("CO2_g_pkm","count"),
                Trips=("Bus_ID","count"),
            ).reset_index()
            fig = px.bar(euro_agg, x="Euro_Standard", y="CO2_g",
                         color="Bus_Category", barmode="group",
                         title="Average CO₂ g/pkm by Euro class and bus category",
                         color_discrete_sequence=PALETTE)
            fig.update_layout(**PLY_BASE, title_font_size=13,
                              xaxis_title="Euro standard", yaxis_title="Avg g CO₂/pkm")
            st.plotly_chart(fig, use_container_width=True)

            if "NOx_g_pkm" in fdf.columns and "NOx" in target_pollutants:
                euro_nox = fdf.groupby("Euro_Standard")["NOx_g_pkm"].mean().reset_index()
                euro_nox.columns = ["Euro Standard","Avg NOx g/pkm"]
                fig2 = px.bar(euro_nox.sort_values("Avg NOx g/pkm", ascending=False),
                              x="Euro Standard", y="Avg NOx g/pkm",
                              title="Average NOx g/pkm by Euro class — impact of after-treatment",
                              color="Avg NOx g/pkm",
                              color_continuous_scale=["#22c55e","#ef4444"], text_auto=".2f")
                fig2.update_layout(**PLY_BASE, title_font_size=13, showlegend=False,
                                   coloraxis_showscale=False, xaxis_title="", yaxis_title="g NOx/pkm")
                st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.markdown('<div class="sec-label">Age deterioration curve</div>', unsafe_allow_html=True)
        if "Vehicle_Age_years" in fdf.columns and "CO2" in target_pollutants:
            rev_df = fdf[fdf["Revenue_Trip"].astype(str).str.lower().isin(["true","1"])]
            age_data = rev_df.groupby(["Vehicle_Age_years","Fuel_Type"])\
                .agg(CO2_g=("CO2_g_pkm","mean"),Trips=("Bus_ID","count")).reset_index()
            fig = px.scatter(age_data, x="Vehicle_Age_years", y="CO2_g",
                             color="Fuel_Type", size="Trips",
                             color_discrete_sequence=PALETTE,
                             title="CO₂ intensity vs vehicle age by fuel type",
                             labels={"Vehicle_Age_years":"Vehicle age (years)","CO2_g":"g CO₂/pkm"})
            fig.update_layout(**PLY_BASE, title_font_size=13)
            st.plotly_chart(fig, use_container_width=True)

            # Fleet age distribution
            fig2 = px.histogram(fdf.drop_duplicates("Bus_ID"), x="Vehicle_Age_years",
                                nbins=10, title="Fleet age distribution",
                                color_discrete_sequence=["#1E73BE"])
            fig2.update_layout(**PLY_BASE, title_font_size=13,
                               xaxis_title="Age (years)", yaxis_title="Vehicles")
            st.plotly_chart(fig2, use_container_width=True)

    with tab4:
        st.markdown('<div class="sec-label">A/C impact on CO₂</div>', unsafe_allow_html=True)
        if "AC_Status" in fdf.columns and "CO2" in target_pollutants and "ac_uplift_kg" in fdf.columns:
            ac_on  = fdf[fdf["AC_Status"].astype(str).str.lower().isin(["true","1"])]
            ac_off = fdf[~fdf["AC_Status"].astype(str).str.lower().isin(["true","1"])]
            a1,a2,a3,a4 = st.columns(4)
            a1.metric("A/C ON trips",    f"{len(ac_on):,}")
            a2.metric("A/C OFF trips",   f"{len(ac_off):,}")
            a3.metric("Total A/C uplift",fmt_kg(fdf["ac_uplift_kg"].sum()))
            avg_uplift_pct = (fdf["ac_uplift_kg"].sum() / max(fdf["CO2_kg"].sum(),0.001)) * 100
            a4.metric("A/C % of CO₂",   f"{avg_uplift_pct:.1f}%")

            ac_route = fdf.groupby(["Route_Name","AC_Status"]).agg(
                CO2_g=("CO2_g_pkm","mean")).reset_index()
            ac_route["AC_Status"] = ac_route["AC_Status"].astype(str).str.lower()\
                .map({"true":"A/C On","false":"A/C Off","1":"A/C On","0":"A/C Off"})
            fig = px.bar(ac_route, x="Route_Name", y="CO2_g", color="AC_Status",
                         barmode="group",
                         title="CO₂ g/pkm — A/C on vs off by route",
                         color_discrete_map={"A/C On":"#ef4444","A/C Off":"#22c55e"})
            fig.update_layout(**PLY_BASE, title_font_size=13,
                              xaxis_title="", yaxis_title="g CO₂/pkm")
            st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════
# MODULE 3 — POLLUTANT ENGINE
# ════════════════════════════════════════════════════════
elif selected_module == "Pollutant Engine":
    st.markdown("## ☁️ Pollutant Engine")
    st.markdown(
        f'<div class="banner">Methodology: <strong>{methodology}</strong>. '
        'CO₂ via IPCC Tier 2 stoichiometric. NOx and PM via COPERT V speed functions × '
        '<strong>Euro class multiplier</strong> × <strong>age deterioration</strong>. '
        'Electric buses: Scope 2 only (Nigeria grid 0.46 kg CO₂e/kWh).</div>',
        unsafe_allow_html=True)

    pol_cols = st.columns(len(target_pollutants))
    for i, pol in enumerate(target_pollutants):
        col = f"{pol}_kg"
        pol_cols[i].metric(f"Total {pol}", fmt_kg(fdf[col].sum()) if col in fdf else "—")

    st.markdown('<div class="sec-label">Pollutant breakdown</div>', unsafe_allow_html=True)
    agg_cols = [f"{p}_kg" for p in target_pollutants if f"{p}_kg" in fdf.columns]

    c1, c2 = st.columns(2)
    with c1:
        _top_ops = fdf.groupby("Operator")["CO2_kg"].sum().nlargest(10).index
        op_pol = fdf[fdf["Operator"].isin(_top_ops)]\
            .groupby("Operator")[agg_cols].sum().reset_index()\
            .melt(id_vars="Operator", var_name="Pollutant", value_name="kg")
        op_pol["Pollutant"] = op_pol["Pollutant"].str.replace("_kg","")
        chart_switcher(op_pol.round(1), x="Operator", y="kg", color="Pollutant",
                       key="pe_op", kinds=("Bar", "Line", "Table"),
                       title="Pollutant volume by operator (top 10)",
                       y_label="kg", height=360)
    with c2:
        fuel_pol = fdf.groupby("Fuel_Type")[agg_cols].sum().reset_index()\
            .melt(id_vars="Fuel_Type", var_name="Pollutant", value_name="kg")
        fuel_pol["Pollutant"] = fuel_pol["Pollutant"].str.replace("_kg","")
        chart_switcher(fuel_pol.round(1), x="Fuel_Type", y="kg", color="Pollutant",
                       key="pe_fuel", kinds=("Bar", "Area", "Table"),
                       title="Pollutant volume by fuel type", barmode="stack",
                       y_label="kg", height=360)

    # Speed vs NOx scatter
    if "NOx" in target_pollutants and "NOx_g_pkm" in fdf.columns:
        fig3 = px.scatter(fdf, x="Avg_Speed_kmh", y="NOx_g_pkm",
                          color="Euro_Standard" if "Euro_Standard" in fdf.columns else "Bus_Category",
                          size="Ridership", symbol="Bus_Category",
                          color_discrete_sequence=PALETTE,
                          title="Speed vs NOx intensity — Euro class differentiation",
                          labels={"Avg_Speed_kmh":"Avg speed (km/h)","NOx_g_pkm":"NOx g/pkm"})
        fig3.update_layout(**PLY_BASE, title_font_size=13)
        st.plotly_chart(fig3, use_container_width=True)

    # Euro × Fuel heatmap for CO2
    if "CO2" in target_pollutants and "Euro_Standard" in fdf.columns:
        st.markdown('<div class="sec-label">Euro class × Fuel type CO₂ heatmap</div>', unsafe_allow_html=True)
        heat = fdf.groupby(["Euro_Standard","Fuel_Type"])["CO2_g_pkm"].mean().reset_index()
        heat_pivot = heat.pivot(index="Euro_Standard", columns="Fuel_Type", values="CO2_g_pkm").fillna(0)
        fig4 = px.imshow(heat_pivot, text_auto=".1f",
                         color_continuous_scale=["#22c55e","#fbbf24","#ef4444"],
                         title=f"Mean CO₂ {st.session_state.eff_unit} — Euro class × fuel type")
        fig4.update_layout(**PLY_BASE, title_font_size=13)
        with_table_option(fig4, heat_pivot.reset_index().round(1), key="pe_heat")

# ════════════════════════════════════════════════════════
# MODULE 4 — BUS EFFICIENCY
# ════════════════════════════════════════════════════════
elif selected_module == "Bus Efficiency":
    st.markdown("## 🚌 Bus Efficiency")
    st.markdown(
        (f'<div class="banner">Efficiency = CO₂ grams per <strong>{"passenger-km" if basis=="passenger" else "vehicle-km"}</strong> '
         f'({st.session_state.eff_unit}) — lower is better. Compliance thresholds '
         + ('(per pkm): High Capacity ≤30 Good / ≤55 Monitor; Midi ≤45 / ≤75; Mini ≤60 / ≤95. '
            if basis == "passenger" else
            '(per vehicle-km): High Capacity ≤1500 Good / ≤2100 Monitor; Midi ≤1000 / ≤1400; Mini ≤500 / ≤750. ')
         + 'Scores reflect Euro class, age, A/C, and engine model corrections.</div>'),
        unsafe_allow_html=True)

    if "CO2" not in target_pollutants:
        st.warning("Enable CO₂ in the sidebar to view efficiency metrics.")
        st.stop()

    rev = fdf[fdf["Revenue_Trip"].astype(str).str.lower().isin(["true","1"])].copy()

    group_cols = ["Bus_Category","Fuel_Type"]
    if "Euro_Standard" in rev.columns: group_cols.append("Euro_Standard")

    eff = rev.groupby(group_cols).agg(
        Avg_CO2_g_pkm=("CO2_g_pkm","mean"),
        Total_CO2_kg=("CO2_kg","sum"),
        Trips=("Bus_ID","count"),
        Passengers=("Ridership","sum"),
        Avg_Age=("Vehicle_Age_years","mean") if "Vehicle_Age_years" in rev.columns else ("CO2_kg","count"),
    ).reset_index().sort_values("Avg_CO2_g_pkm").round(2)
    eff["Compliance"] = eff.apply(lambda r: compliance_flag(r["Avg_CO2_g_pkm"], r["Bus_Category"]), axis=1)

    c1, c2 = st.columns([2,1])
    with c1:
        color_col = "Euro_Standard" if "Euro_Standard" in eff.columns else "Fuel_Type"
        fig = px.bar(eff, x="Bus_Category", y="Avg_CO2_g_pkm", color=color_col,
                     barmode="group",
                     title="Average CO₂ per passenger-km by category",
                     color_discrete_sequence=PALETTE,
                     text=eff["Avg_CO2_g_pkm"].round(1).astype(str)+" g")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(**PLY_BASE, title_font_size=13,
                          xaxis_title="", yaxis_title="g CO₂/pkm")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown('<div class="sec-label">Compliance table</div>', unsafe_allow_html=True)
        display = eff[["Bus_Category","Fuel_Type","Avg_CO2_g_pkm","Compliance"]].copy()
        display["Status"] = display["Compliance"].apply(badge_html)
        st.markdown(
            display[["Bus_Category","Fuel_Type","Avg_CO2_g_pkm","Status"]]
            .rename(columns={"Bus_Category":"Category","Fuel_Type":"Fuel","Avg_CO2_g_pkm":"g/pkm"})
            .to_html(escape=False, index=False),
            unsafe_allow_html=True)

    # Load factor vs efficiency
    fig2 = px.scatter(rev, x="load_factor", y="CO2_g_pkm",
                      color="Bus_Category", size="Route_Distance_km",
                      symbol="Euro_Standard" if "Euro_Standard" in rev.columns else None,
                      color_discrete_sequence=PALETTE,
                      title="Load factor vs CO₂ intensity — fill your buses",
                      labels={"load_factor":"Load factor","CO2_g_pkm":"CO₂ g/pkm"})
    fig2.update_layout(**PLY_BASE, title_font_size=13)
    st.plotly_chart(fig2, use_container_width=True)

    # Per-bus ranking
    st.markdown('<div class="sec-label">Individual bus ranking</div>', unsafe_allow_html=True)
    bus_rank = rev.groupby("Bus_ID").agg(
        CO2_g_pkm=("CO2_g_pkm","mean"),
        CO2_kg=("CO2_kg","sum"),
        Trips=("Bus_ID","count"),
        Operator=("Operator","first"),
        Category=("Bus_Category","first"),
        Fuel=("Fuel_Type","first"),
        Euro=("Euro_Standard","first") if "Euro_Standard" in rev.columns else ("CO2_kg","count"),
        Age=("Vehicle_Age_years","first") if "Vehicle_Age_years" in rev.columns else ("CO2_kg","count"),
    ).reset_index().sort_values("CO2_g_pkm")
    bus_rank["Compliance"] = bus_rank.apply(
        lambda r: compliance_flag(r["CO2_g_pkm"], r["Category"], basis), axis=1)

    st.dataframe(bus_rank, use_container_width=True, hide_index=True,
        column_config={
            "Bus_ID":    st.column_config.TextColumn("Bus ID"),
            "CO2_g_pkm":st.column_config.ProgressColumn("g CO₂/pkm", min_value=0, max_value=200, format="%.1f"),
            "CO2_kg":   st.column_config.NumberColumn("Total CO₂ kg", format="%.2f"),
            "Compliance":st.column_config.TextColumn("Status"),
        })

    # Tip section
    worst = eff[eff["Compliance"]=="Over Limit"]
    if not worst.empty:
        st.markdown('<div class="sec-label">Recommended actions</div>', unsafe_allow_html=True)
        for _, r in worst.iterrows():
            st.markdown(
                f'<div class="tip">🔴 <strong>{r["Bus_Category"]} / {r["Fuel_Type"]}</strong> '
                f'averaging <strong>{r["Avg_CO2_g_pkm"]:.1f} g/pkm</strong>. '
                f'Upgrade to Euro V or VI (−50–95% NOx), reduce terminal idle time, '
                f'or increase ridership via dynamic scheduling.</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# MODULE 5 — TRIP INSPECTOR
# ════════════════════════════════════════════════════════
elif selected_module == "Corridor Map":
    render_corridor_module()

elif selected_module == "Fleet Health":
    st.markdown("## 🩺 Fleet Health")
    st.markdown(
        '<div class="banner">Machine-learning anomaly detection. Two checks per bus-day: '
        'is this bus drifting from <strong>its own</strong> normal CO₂/km (z-score), and does it '
        'stand out from <strong>its peer group</strong> of same-category, same-fuel buses '
        '(Isolation Forest)? Persistent anomalies usually mean injectors, filters, brakes or '
        'tyres — worth a workshop visit before they become breakdowns.</div>',
        unsafe_allow_html=True)

    import ml_engine
    with st.spinner("Training anomaly models on the current (filtered) fleet…"):
        anom_rows, health = ml_engine.detect_anomalies(fdf)

    if health.empty:
        st.info("Not enough data to train on — need at least ~50 rows with CO₂ enabled.")
    else:
        n_inv = int((health["Health"] == "Investigate").sum())
        n_watch = int((health["Health"] == "Watch").sum())
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Buses analysed", f"{len(health):,}")
        h2.metric("Investigate", str(n_inv), delta="priority list", delta_color="inverse")
        h3.metric("Watch", str(n_watch))
        h4.metric("Anomalous bus-days", f"{int(anom_rows['is_anomaly'].sum()):,} / {len(anom_rows):,}")

        st.markdown('<div class="sec-label">Bus health league — worst first</div>', unsafe_allow_html=True)
        show = health[health["Health"] != "Insufficient data"].head(40)
        st.dataframe(show, use_container_width=True, hide_index=True,
            column_config={
                "Anomaly_rate": st.column_config.ProgressColumn("Anomaly rate", min_value=0, max_value=1, format="%.2f"),
                "Avg_CO2_g_km": st.column_config.NumberColumn("Avg g CO₂/km", format="%.0f"),
                "Worst_self_z": st.column_config.NumberColumn("Worst z", format="%.1f"),
            })

        st.markdown('<div class="sec-label">Inspect one bus — daily CO₂/km with anomalous days marked</div>', unsafe_allow_html=True)
        pick = st.selectbox("Bus", show["Bus_ID"].tolist())
        b = anom_rows[anom_rows["Bus_ID"] == pick].sort_values("Date")
        if len(b):
            figh = go.Figure()
            figh.add_trace(go.Scatter(x=b["Date"], y=b["CO2_g_km"], mode="lines+markers",
                                      name="CO₂ g/km", line=dict(width=2)))
            bad = b[b["is_anomaly"]]
            figh.add_trace(go.Scatter(x=bad["Date"], y=bad["CO2_g_km"], mode="markers",
                                      name="Anomaly", marker=dict(size=11, symbol="x", color="#FF6363")))
            figh.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                               legend=dict(orientation="h"))
            st.plotly_chart(figh, use_container_width=True)

        if ai_engine.is_configured() and len(b):
            if st.button("🤖 Explain this pattern (AI)", key="ai_explain_bus"):
                _r = show[show["Bus_ID"] == pick].iloc[0]
                _desc = (f"Bus {pick} · operator {_r['Operator']} · {_r['Category']} {_r['Fuel']} · "
                         f"{int(_r['Days'])} days observed, {int(_r['Anomalous_days'])} anomalous "
                         f"(rate {_r['Anomaly_rate']}). Avg CO2 {_r['Avg_CO2_g_km']} g/km; "
                         f"worst self-z {_r['Worst_self_z']}. Peer group: same category+fuel buses. "
                         f"Daily CO2 g/km recent values: "
                         + ", ".join(str(round(v,0)) for v in b['CO2_g_km'].tail(10)))
                with st.spinner("Interpreting…"):
                    _txt, _ok = ai_engine.explain_anomaly(_desc, ai_engine.fingerprint(fdf))
                (st.info if _ok else st.warning)(_txt)

        if db.get_client() is not None and st.button("💾 Save health scores to database"):
            recs = [{"bus_id": r["Bus_ID"], "score": float(r["Anomaly_rate"]),
                     "payload": {"health": r["Health"], "days": int(r["Days"]),
                                 "avg_co2_g_km": float(r["Avg_CO2_g_km"])}}
                    for _, r in health.iterrows()]
            res = db.save_ml_insights("anomaly", recs)
            st.success(f"Saved {res['saved']} bus scores") if not res["error"] else st.warning(res["error"])

elif selected_module == "Forecast":
    st.markdown("## 📈 Forecast")
    st.markdown(
        '<div class="banner">Transparent forecasting: <strong>linear trend + weekday pattern</strong>, '
        'with a band showing how wrong the model has typically been on history. With a month or two '
        'of data this is honest short-range projection, not prophecy — the band says so. Below it, '
        'a gradient-boosted model scores each bus\'s <strong>compliance breach risk</strong> so '
        'enforcement can be proactive.</div>', unsafe_allow_html=True)

    import ml_engine
    fkind = st.radio("Forecast", ["Fleet CO₂ (kg/day)", "Ridership (pax/day)"], horizontal=True)
    val_col, src_col = (("CO2_kg", "CO2_kg") if fkind.startswith("Fleet") else ("Ridership", "Ridership"))
    horizon = st.slider("Horizon (days)", 7, 60, 30)

    daily = fdf.groupby("Date")[src_col].sum().reset_index()
    fc = ml_engine.forecast_daily(daily, src_col, horizon)
    if fc.empty:
        st.info("Need at least 14 days of history for a forecast.")
    else:
        fut = fc[~fc["is_history"]]
        figf = go.Figure()
        figf.add_trace(go.Scatter(x=fc["Date"], y=fc["hi"], line=dict(width=0),
                                  showlegend=False, hoverinfo="skip"))
        figf.add_trace(go.Scatter(x=fc["Date"], y=fc["lo"], fill="tonexty",
                                  fillcolor="rgba(30,115,190,0.15)", line=dict(width=0),
                                  name="95% band", hoverinfo="skip"))
        figf.add_trace(go.Scatter(x=fc[fc.is_history]["Date"], y=fc[fc.is_history]["actual"],
                                  mode="lines", name="Actual", line=dict(width=2)))
        figf.add_trace(go.Scatter(x=fut["Date"], y=fut["forecast"], mode="lines",
                                  name="Forecast", line=dict(width=2, dash="dash", color="#3EF2A0")))
        figf.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                           legend=dict(orientation="h"))
        st.plotly_chart(figf, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Next 7-day avg", f"{fut.head(7)['forecast'].mean():,.0f}")
        c2.metric(f"Projected total ({horizon}d)", f"{fut['forecast'].sum():,.0f}")
        trend_pct = (fut['forecast'].iloc[-1] / max(fc[fc.is_history]['forecast'].iloc[-1], 1e-9) - 1) * 100
        c3.metric("Trend over horizon", f"{trend_pct:+.1f}%")

    st.markdown('<div class="sec-label">Compliance breach risk — buses most likely to go Over Limit</div>',
                unsafe_allow_html=True)
    risk = ml_engine.compliance_risk(fdf)
    if risk.empty:
        st.info("Not enough Over-Limit examples in the current filter to train the risk model.")
    else:
        rc1, rc2 = st.columns([2, 1])
        with rc1:
            st.dataframe(risk.head(25), use_container_width=True, hide_index=True,
                column_config={"Risk_score": st.column_config.ProgressColumn(
                    "Breach risk", min_value=0, max_value=1, format="%.2f")})
        with rc2:
            band_ct = risk["Risk_band"].value_counts().reset_index()
            band_ct.columns = ["Band", "Buses"]
            st.plotly_chart(px.pie(band_ct, values="Buses", names="Band", hole=0.5,
                                   color="Band",
                                   color_discrete_map={"High": "#FF6363", "Elevated": "#FFC24B", "Low": "#3EF2A0"}),
                            use_container_width=True)
        if db.get_client() is not None and st.button("💾 Save risk scores to database"):
            recs = [{"bus_id": r["Bus_ID"], "score": float(r["Risk_score"]),
                     "payload": {"band": r["Risk_band"], "breaches": int(r["Breaches_so_far"])}}
                    for _, r in risk.iterrows()]
            res = db.save_ml_insights("risk", recs)
            st.success(f"Saved {res['saved']} risk scores") if not res["error"] else st.warning(res["error"])

elif selected_module == "Data Quality":
    st.markdown("## 🧪 Data Quality")
    st.markdown(
        '<div class="banner">A compliance tool is only as credible as its inputs. This module '
        'validates every loaded row and names what it finds — <strong>impossible values, '
        'outliers, duplicates and unmapped codes</strong> — with severity and affected-row '
        'counts, so figures elsewhere in the console can be read with the right confidence.</div>',
        unsafe_allow_html=True)

    q = fdf.copy()
    q["_trips"] = pd.to_numeric(q.get("Num_Trips_Today", 1), errors="coerce").fillna(1).clip(lower=1)
    q["_trip_km"] = pd.to_numeric(q["Route_Distance_km"], errors="coerce") / q["_trips"]
    q["_pax_trip"] = pd.to_numeric(q["Ridership"], errors="coerce") / q["_trips"]
    _caps = {"High Capacity": 150, "HC": 150, "Midi": 80, "MIDI": 80,
             "Mini": 18, "MINI": 18, "FLM": 18}
    q["_cap"] = q["Bus_Category"].map(_caps).fillna(80)

    checks = []  # (severity, name, mask, why-it-matters)
    checks.append(("Critical", "Non-positive distance",
        pd.to_numeric(q["Route_Distance_km"], errors="coerce").fillna(0) <= 0,
        "Zero/negative distance makes every per-km figure meaningless for the row."))
    checks.append(("Critical", "Ridership exceeds physical capacity",
        q["_pax_trip"] > q["_cap"] * 1.3,
        "More passengers per trip than 130% of the bus's capacity — likely a daily-vs-trip mixup."))
    checks.append(("Warning", "Implausible trip distance (>120 km per trip)",
        q["_trip_km"] > 120,
        "A single urban trip longer than 120 km suggests the distance column holds something else."))
    checks.append(("Warning", "Speed outlier (<5 or >90 km/h)",
        (pd.to_numeric(q["Avg_Speed_kmh"], errors="coerce") < 5) |
        (pd.to_numeric(q["Avg_Speed_kmh"], errors="coerce") > 90),
        "Outside the range the COPERT speed curves are valid for — the engine clamps it, but the input is suspect."))
    checks.append(("Warning", "Fractional trip counts",
        pd.to_numeric(q.get("Num_Trips_Today", 1), errors="coerce").fillna(0) % 1 != 0,
        "Half a trip doesn't exist — usually a sign of averaged or interpolated source data."))
    checks.append(("Warning", "Duplicate Date + Bus + Route rows",
        q.duplicated(subset=[c for c in ["Date", "Bus_ID", "Route_Name"] if c in q.columns], keep=False),
        "The same bus-day counted twice inflates totals. The database blocks these; uploads don't."))
    if "category_unmapped" in q.columns:
        checks.append(("Info", "Unrecognised bus category",
            q["category_unmapped"].astype(bool),
            "Fell back to default emission factors — add the code to CATEGORY_ALIASES."))
    if "fuel_unmapped" in q.columns:
        checks.append(("Info", "Unrecognised fuel type",
            q["fuel_unmapped"].astype(bool),
            "Fell back to default emission factors — add the code to FUEL_ALIASES."))
    checks.append(("Info", "Missing Euro standard",
        ~q["Euro_Standard"].astype(str).str.startswith("Euro") if "Euro_Standard" in q.columns
        else pd.Series(True, index=q.index),
        "Defaults to Euro III — NOx/PM for these rows are an assumption, not data."))

    results = []
    for sev, name, mask, why in checks:
        n = int(mask.fillna(False).sum())
        results.append({"Severity": sev, "Check": name, "Rows affected": n,
                        "% of data": round(100 * n / max(len(q), 1), 1), "Why it matters": why})
    res_df = pd.DataFrame(results)

    n_crit = int(res_df.loc[res_df.Severity == "Critical", "Rows affected"].gt(0).sum())
    n_warn = int(res_df.loc[res_df.Severity == "Warning", "Rows affected"].gt(0).sum())
    clean_pct = 100 - res_df["% of data"].max() if len(res_df) else 100
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Rows checked", f"{len(q):,}")
    d2.metric("Critical findings", str(n_crit), delta="fix before trusting totals" if n_crit else "none", delta_color="inverse" if n_crit else "off")
    d3.metric("Warnings", str(n_warn))
    d4.metric("Checks run", str(len(res_df)))

    st.markdown('<div class="sec-label">Findings</div>', unsafe_allow_html=True)
    _sev_icon = {"Critical": "🔴", "Warning": "🟡", "Info": "🔵"}
    res_df["Severity"] = res_df["Severity"].map(lambda x: f"{_sev_icon[x]} {x}")
    st.dataframe(res_df, use_container_width=True, hide_index=True,
                 column_config={"% of data": st.column_config.ProgressColumn(
                     "% of data", min_value=0, max_value=100, format="%.1f%%")})

    st.markdown('<div class="sec-label">Inspect affected rows</div>', unsafe_allow_html=True)
    pick_check = st.selectbox("Finding", [c[1] for c in checks])
    _mask = dict((c[1], c[2]) for c in checks)[pick_check].fillna(False)
    bad = q[_mask]
    if len(bad) == 0:
        st.success("No rows affected by this check. ✓")
    else:
        show_cols = [c for c in ["Date", "Bus_ID", "Operator", "Route_Name",
                                 "Route_Distance_km", "Num_Trips_Today", "Avg_Speed_kmh",
                                 "Ridership", "Bus_Category", "Fuel_Type", "Euro_Standard"]
                     if c in bad.columns]
        st.dataframe(bad[show_cols].head(200), use_container_width=True, hide_index=True)
        st.download_button("⬇ Download affected rows (CSV)",
                           data=bad[show_cols].to_csv(index=False).encode(),
                           file_name="data_quality_flagged.csv", mime="text/csv")

elif selected_module == "What-If":
    st.markdown("## 🎛 What-If Simulator")
    st.markdown(
        '<div class="banner">Fleet planning, not just reporting: pick interventions and the '
        'scenario is <strong>recomputed through the real emissions engine</strong> — same math, '
        'modified fleet. Baseline is the currently filtered data, so you can also scenario-test '
        'a single operator or corridor.</div>', unsafe_allow_html=True)

    w1, w2 = st.columns(2)
    with w1:
        conv_n = st.slider("Convert N worst CO₂ diesel buses…", 0, 100, 0,
                           help="Ranked by total CO₂ in the current data.")
        conv_to = st.selectbox("…to fuel", ["CNG", "Electric"])
        euro_target = st.selectbox("Upgrade everything below…",
                                   ["No change", "Euro IV", "Euro V", "Euro VI"],
                                   help="Retrofit / replacement scenario for NOx & PM.")
    with w2:
        speed_gain = st.slider("Average speed improvement (km/h)", 0, 15, 0,
                               help="Bus priority lanes / signal priority. Affects "
                                    "speed-corrected pollutants in COPERT & Hybrid modes.")
        ac_policy = st.selectbox("A/C policy", ["No change", "All A/C off", "All A/C on"])

    if st.button("▶ Run scenario", type="primary"):
        base_cols = ["Bus_Category", "Fuel_Type", "Route_Distance_km", "Avg_Speed_kmh",
                     "Ridership", "Num_Trips_Today", "Euro_Standard", "Vehicle_Age_years",
                     "AC_Status", "Engine_Model", "Revenue_Trip", "Idle_Minutes"]
        sim = fdf[[c for c in base_cols if c in fdf.columns] + ["Bus_ID"]].copy()

        changed = pd.Series(False, index=sim.index)
        if conv_n > 0:
            worst = (fdf[fdf["Fuel_Type"] == "Diesel"].groupby("Bus_ID")["CO2_kg"]
                        .sum().sort_values(ascending=False).head(conv_n).index)
            m = sim["Bus_ID"].isin(worst)
            sim.loc[m, "Fuel_Type"] = conv_to
            if conv_to == "Electric":
                sim.loc[m & (sim["Bus_Category"] == "Mini"), "Bus_Category"] = "Midi"
                # (no Electric Mini factor exists — modelled as the nearest class)
            changed |= m
        if euro_target != "No change":
            order = {"Euro II": 2, "Euro III": 3, "Euro IV": 4, "Euro V": 5, "Euro VI": 6}
            tgt = order[euro_target]
            m = sim["Euro_Standard"].map(order).fillna(3) < tgt
            sim.loc[m, "Euro_Standard"] = euro_target
            changed |= m
        if speed_gain > 0:
            sim["Avg_Speed_kmh"] = pd.to_numeric(sim["Avg_Speed_kmh"], errors="coerce").fillna(25) + speed_gain
            changed |= True
        if ac_policy != "No change":
            sim["AC_Status"] = (ac_policy == "All A/C on")
            changed |= True

        n_changed = int(changed.sum()) if isinstance(changed, pd.Series) else len(sim)
        with st.spinner(f"Re-running the engine on {n_changed:,} modified rows…"):
            # Only recompute rows the scenario touched; reuse baseline for the rest.
            if isinstance(changed, pd.Series) and changed.sum() < len(sim):
                redo = sim[changed]
                res = redo.apply(lambda r: calculate_row(
                    r, methodology, target_pollutants, ambient_c), axis=1)
                scen_co2 = float(fdf.loc[~changed, "CO2_kg"].sum() + res["CO2_kg"].sum())
                scen_nox = float(fdf.loc[~changed, "NOx_kg"].sum() + res["NOx_kg"].sum()) if "NOx_kg" in res else None
                scen_pm  = float(fdf.loc[~changed, "PM_kg"].sum() + res["PM_kg"].sum()) if "PM_kg" in res else None
            else:
                res = sim.apply(lambda r: calculate_row(
                    r, methodology, target_pollutants, ambient_c), axis=1)
                scen_co2 = float(res["CO2_kg"].sum())
                scen_nox = float(res["NOx_kg"].sum()) if "NOx_kg" in res else None
                scen_pm  = float(res["PM_kg"].sum()) if "PM_kg" in res else None

        base_co2 = float(fdf["CO2_kg"].sum())
        st.markdown('<div class="sec-label">Scenario result</div>', unsafe_allow_html=True)
        s1, s2, s3 = st.columns(3)
        s1.metric("Baseline CO₂", f"{base_co2/1000:,.1f} t")
        s2.metric("Scenario CO₂", f"{scen_co2/1000:,.1f} t",
                  delta=f"{(scen_co2-base_co2)/1000:+,.1f} t "
                        f"({(scen_co2/base_co2-1)*100:+.1f}%)",
                  delta_color="inverse")
        s3.metric("Rows modified", f"{n_changed:,}")

        rows = [{"Pollutant": "CO₂ (t)", "Baseline": base_co2/1000, "Scenario": scen_co2/1000}]
        if scen_nox is not None and "NOx" in target_pollutants:
            rows.append({"Pollutant": "NOx (kg)", "Baseline": float(fdf["NOx_kg"].sum()), "Scenario": scen_nox})
        if scen_pm is not None and "PM" in target_pollutants:
            rows.append({"Pollutant": "PM (kg)", "Baseline": float(fdf["PM_kg"].sum()), "Scenario": scen_pm})
        cmp_df = pd.DataFrame(rows).round(1)
        chart_switcher(cmp_df, x="Pollutant", y=["Baseline", "Scenario"], key="whatif_cmp",
                       kinds=("Bar", "Table"), default="Bar",
                       title="Baseline vs scenario", height=340)
        st.caption("Scenario totals use the same methodology, basis and ambient temperature "
                   "as the rest of the console. Electric conversions add Nigerian-grid "
                   "Scope 2 CO₂ — they are cleaner, not free.")

elif selected_module == "Trip Inspector":
    st.markdown("## 🔬 Trip Inspector")
    st.markdown(
        '<div class="banner">Select a single trip to see a full breakdown: '
        'hot running, cold start (scaled by <strong>Num_Trips_Today</strong>), '
        'idling, A/C load (only when <strong>AC_Status = True</strong>), '
        'and grid electricity for EVs. Euro class, age deterioration, and engine model '
        'corrections are all visible in the metadata panel.</div>',
        unsafe_allow_html=True)

    bus_ids = sorted(fdf["Bus_ID"].unique())
    sel_bus = st.selectbox("Bus ID", bus_ids)
    bus_trips = fdf[fdf["Bus_ID"]==sel_bus].reset_index(drop=True)
    trip_labels = [
        f"{i}: {row['Date']} · {row['Route_Name']} · {row['Route_Distance_km']} km · {row['Ridership']} pax"
        for i, (_, row) in enumerate(bus_trips.iterrows())
    ]
    sel_idx = st.selectbox("Trip", range(len(trip_labels)), format_func=lambda i: trip_labels[i])
    trip = bus_trips.iloc[sel_idx]
    bd = emission_breakdown(trip, methodology)

    st.markdown('<div class="sec-label">Vehicle metadata</div>', unsafe_allow_html=True)
    m1,m2,m3,m4,m5,m6 = st.columns(6)
    m1.metric("Bus category",   trip["Bus_Category"])
    m2.metric("Fuel type",      trip["Fuel_Type"])
    m3.metric("Euro standard",  trip.get("Euro_Standard","—"))
    m4.metric("Vehicle age",    f'{trip.get("Vehicle_Age_years","—")} yrs')
    m5.metric("Engine",         trip.get("Engine_Model","—") or "—")
    m6.metric("A/C status",     "On" if str(trip.get("AC_Status","")).lower() in ("true","1") else "Off")

    n1,n2,n3,n4 = st.columns(4)
    n1.metric("Distance",      f'{trip["Route_Distance_km"]} km')
    n2.metric("Avg speed",     f'{trip["Avg_Speed_kmh"]} km/h')
    n3.metric("Ridership",     f'{trip["Ridership"]}')
    n4.metric("Trips today",   str(trip.get("Num_Trips_Today","—")))

    st.markdown('<div class="sec-label">Emission source breakdown (CO₂)</div>', unsafe_allow_html=True)
    col_l, col_r = st.columns(2)

    with col_l:
        labels  = ["Hot running","Cold start","Idling","A/C load","Grid (EV)"]
        raw_g   = [bd["hot_running"],bd["cold_start"],bd["idling"],bd["ac_load"],bd["grid_electric"]]
        colors  = ["#1E73BE","#ffb84d","#ff5252","#3ddc84","#c9a8ff"]
        total_g = max(bd["total_g"],1)

        for lbl, grams, col in zip(labels, raw_g, colors):
            pct = grams/total_g*100
            st.markdown(f"""
            <div class="brow">
                <div class="lbl">{lbl}</div>
                <div class="bg"><div class="fill" style="width:{min(pct,100):.1f}%;background:{col};"></div></div>
                <div class="val">{grams/1000:.3f} kg</div>
            </div>""", unsafe_allow_html=True)

        st.markdown(
            f'<div style="margin-top:14px;padding:14px 18px;background:var(--bg-card2);'
            f'border:1px solid var(--border);border-top:2px solid var(--accent);border-radius:4px;">'
            f'<div style="font-family:var(--mono);font-size:10px;letter-spacing:0.07em;color:var(--text-tert);margin-bottom:4px;">TOTAL CO₂ THIS TRIP</div>'
            f'<div style="font-family:var(--mono);font-size:26px;font-weight:600;color:var(--text-prim);">{bd["total_g"]/1000:.3f} kg</div>'
            f'</div>', unsafe_allow_html=True)

        if "CO2" in target_pollutants:
            gpkm = float(trip.get("CO2_g_pkm",0))
            t = {"High Capacity": (30,55), "Midi": (45,75), "Mini": (60,95)}.get(trip["Bus_Category"], (40,70))
            st.markdown(
                f'<div style="margin-top:14px;">'
                f'<div style="font-size:11px;color:var(--text-tert);margin-bottom:6px;">Compliance status</div>'
                f'{gauge_svg(gpkm, t[0], t[1])}'
                f'</div>', unsafe_allow_html=True)

    with col_r:
        non_zero = [(l,g,c) for l,g,c in zip(labels,raw_g,colors) if g>0]
        if non_zero:
            nz_l, nz_v, nz_c = zip(*non_zero)
            fig = go.Figure(go.Pie(
                labels=nz_l, values=nz_v, hole=0.56,
                marker_colors=nz_c,
                textinfo="percent", textfont_size=11,
            ))
            ply_pie = dict(PLY_BASE)
            ply_pie.pop("legend", None)
            fig.update_layout(**ply_pie, title="Source split", title_font_size=13,
                              showlegend=True,
                              legend=dict(orientation="v", x=1.02, y=0.5))
            st.plotly_chart(fig, use_container_width=True)

        # Correction factors applied
        st.markdown('<div style="margin-top:10px;">', unsafe_allow_html=True)
        if "age_co2_mult" in trip:
            pct = (float(trip["age_co2_mult"]) - 1) * 100
            st.markdown(f'<div class="tip">🕐 Age deterioration adds <strong>+{pct:.1f}%</strong> to base CO₂ factors.</div>', unsafe_allow_html=True)
        if "euro_nox_mult" in trip and "NOx" in target_pollutants:
            st.markdown(f'<div class="tip">🏷 Euro {trip.get("Euro_Standard","")} NOx multiplier: <strong>{float(trip["euro_nox_mult"]):.2f}×</strong> vs Euro III baseline.</div>', unsafe_allow_html=True)
        if str(trip.get("AC_Status","")).lower() in ("true","1") and "ac_uplift_kg" in trip:
            st.markdown(f'<div class="tip">❄️ A/C ON adds <strong>{float(trip["ac_uplift_kg"])*1000:.1f} g CO₂</strong> (+8% of hot running).</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Reduction potential
    st.markdown('<div class="sec-label">Reduction potential</div>', unsafe_allow_html=True)
    idle_save = bd["idling"]*0.5/1000
    ac_save   = bd["ac_load"]*0.3/1000
    trip_save = bd["cold_start"]*0.2/1000
    total_save = idle_save+ac_save+trip_save
    r1,r2,r3,r4 = st.columns(4)
    r1.metric("Cut idle 50%",        f"−{idle_save:.3f} kg")
    r2.metric("Pre-cool at depot",    f"−{ac_save:.3f} kg")
    r3.metric("Reduce daily trips",   f"−{trip_save:.3f} kg")
    r4.metric("Combined saving",      f"−{total_save:.3f} kg",
              delta=f"{total_save/(bd['total_g']/1000)*100:.0f}% reduction" if bd["total_g"] > 0 else None)

# ════════════════════════════════════════════════════════
# MODULE 5b — FORMULA EXPLAINER
# ════════════════════════════════════════════════════════
elif selected_module == "Formula Explainer":
    st.markdown("## 🧮 Formula Explainer")
    st.markdown(
        f'<div class="banner">Pick any trip below and this walks through every multiplier and addend the '
        f'<strong>{methodology}</strong> engine applies to it, in order, with your data\'s actual numbers '
        f'substituted in — so the final kg CO₂ figure isn\'t a black box.</div>',
        unsafe_allow_html=True)

    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        e_op = st.selectbox("Operator", ["Any"] + sorted(fdf["Operator"].unique()), key="fe_op")
    pool = fdf if e_op == "Any" else fdf[fdf["Operator"] == e_op]
    with ec2:
        e_bus = st.selectbox("Bus ID", sorted(pool["Bus_ID"].unique()), key="fe_bus")
    bus_trips = pool[pool["Bus_ID"] == e_bus].reset_index(drop=True)
    with ec3:
        e_labels = [f"{r.get('Date','')} · {r.get('Route_Name','')[:28]}" for _, r in bus_trips.iterrows()]
        e_idx = st.selectbox("Trip", range(len(e_labels)), format_func=lambda i: e_labels[i], key="fe_trip")
    trip = bus_trips.iloc[e_idx]

    # ── Re-derive every intermediate value, mirroring emissions_engine.calculate_row ──
    import emissions_engine as _em
    bus_cat, _cm = _em.normalize_category(str(trip.get("Bus_Category","")))
    fuel, _fm    = _em.normalize_fuel(str(trip.get("Fuel_Type","")))
    distance     = float(trip.get("Route_Distance_km", 0) or 0)
    speed        = float(trip.get("Avg_Speed_kmh", 25) or 25)
    ridership    = max(1, int(trip.get("Ridership", 1) or 1))
    euro         = str(trip.get("Euro_Standard", _em.DEFAULT_EURO))
    age          = int(trip.get("Vehicle_Age_years", 0) or 0)
    ac_on        = str(trip.get("AC_Status","")).lower() in ("true","1")
    num_trips    = max(1, int(trip.get("Num_Trips_Today", 1) or 1))
    engine_model = str(trip.get("Engine_Model",""))
    is_revenue   = _em.parse_revenue_trip(trip.get("Revenue_Trip","True"))

    cat_data     = _em.BASE_FACTORS.get(bus_cat, {})
    fuel_profile = cat_data.get(fuel, _em.FALLBACK_FACTORS)
    capacity     = int(fuel_profile.get("capacity", 80))
    base_co2     = float(fuel_profile.get("CO2", 0.0))
    eng_corr     = _em.ENGINE_CO2_CORRECTION.get(engine_model, _em.DEFAULT_ENGINE_CORRECTION)
    age_mults    = _em.age_deterioration(age, fuel)
    age_co2      = age_mults["CO2"]
    euro_mults   = _em.EURO_FACTORS.get(euro, _em.EURO_FACTORS[_em.DEFAULT_EURO])
    # One row = one bus-day: derive the per-trip values the engine uses
    trip_km      = distance / num_trips           # length of one trip
    pax_per_trip = ridership / num_trips          # passengers on board at once
    passenger_km = ridership * trip_km            # total passenger-km that day
    load_c       = _em._load_corr(pax_per_trip, capacity)

    if fuel == "Electric":
        kwh_per_km = float(fuel_profile.get("kwh_per_km", 1.5))
        st.markdown('<div class="sec-label">Step 1 — Electric buses use Scope 2 grid intensity, not combustion factors</div>', unsafe_allow_html=True)
        st.latex(r"CO_2\,(kg) = \text{kWh/km} \times \text{distance} \times \text{Grid EF}")
        st.code(f"CO2 = {kwh_per_km} kWh/km × {distance:.1f} km × {_em.GRID_EF_KG_PER_KWH} kg/kWh"
                f" = {kwh_per_km*distance*_em.GRID_EF_KG_PER_KWH:.3f} kg",
                language=None)
        st.markdown(
            f'<div class="tip">Nigeria grid emission factor of <strong>{_em.GRID_EF_KG_PER_KWH} kg CO₂e/kWh</strong> '
            f'is IEA 2023\'s regional estimate — applied because the bus itself has zero tailpipe emissions, '
            f'but the electricity that charged it didn\'t come from nowhere.</div>', unsafe_allow_html=True)
    else:
        ef_after_engine = base_co2 * eng_corr
        ef_after_age    = ef_after_engine * age_co2

        st.markdown('<div class="sec-label">Step 1 — Base emission factor</div>', unsafe_allow_html=True)
        st.latex(r"EF_{base} = \text{BASE\_FACTORS}[\text{category}][\text{fuel}][\text{CO}_2]")
        st.code(f"EF_base = BASE_FACTORS['{bus_cat}']['{fuel}']['CO2'] = {base_co2:.1f} g/km", language=None)
        st.markdown(f'<div class="tip">Reference Euro III diesel/petrol/CNG/biogas factor for a '
                    f'<strong>{bus_cat}</strong> bus on <strong>{fuel}</strong>, from IPCC 2006 Tier 2 + '
                    f'COPERT V West-Africa calibration. Capacity assumed: {capacity} seats.</div>',
                    unsafe_allow_html=True)

        st.markdown('<div class="sec-label">Step 2 — Engine model correction (CO₂ only)</div>', unsafe_allow_html=True)
        st.latex(r"EF_1 = EF_{base} \times \text{EngineCorrection}")
        st.code(f"EF_1 = {base_co2:.1f} × {eng_corr:.2f}  ({engine_model or 'no engine model — default 1.00'})"
                f" = {ef_after_engine:.1f} g/km", language=None)

        st.markdown('<div class="sec-label">Step 3 — Vehicle age deterioration</div>', unsafe_allow_html=True)
        st.latex(r"EF_2 = EF_1 \times (1 + 0.004 \times \text{age\_years})")
        st.code(f"EF_2 = {ef_after_engine:.1f} × (1 + 0.004 × {age})  = {ef_after_engine:.1f} × {age_co2:.3f}"
                f" = {ef_after_age:.1f} g/km", language=None)
        st.markdown(f'<div class="tip">+0.4%/year CO₂ degradation (COPERT model) — a {age}-year-old bus burns '
                    f'<strong>{(age_co2-1)*100:.1f}% more</strong> fuel per km than new, all else equal.</div>',
                    unsafe_allow_html=True)

        st.markdown('<div class="sec-label">Step 4 — Hot running emissions over the route</div>', unsafe_allow_html=True)
        if methodology == "COPERT" or (methodology == "Hybrid" and False):
            spd_factor = _em._spd_co2(speed)
            st.latex(r"E_{hot} = EF_2 \times \frac{f(v)}{f(50)} \times \text{distance}, \qquad f(v) = 1 + \tfrac{25}{v} + \tfrac{v}{400}")
            st.code(f"f_speed({speed:.0f} km/h) = f({speed:.0f})/f(50) = {spd_factor:.3f}   (normalised: = 1.0 at 50 km/h)\n"
                    f"E_hot = {ef_after_age:.1f} × {spd_factor:.3f} × {distance:.1f} km = "
                    f"{ef_after_age*spd_factor*distance:.0f} g", language=None)
            hot_g = ef_after_age * spd_factor * distance
        else:
            st.latex(r"E_{hot} = EF_2 \times \text{distance}")
            st.code(f"E_hot = {ef_after_age:.1f} g/km × {distance:.1f} km = {ef_after_age*distance:.0f} g", language=None)
            hot_g = ef_after_age * distance
            if methodology == "Hybrid":
                st.markdown('<div class="tip">Hybrid methodology keeps CO₂ on the simpler IPCC distance-based '
                            'formula — only NOx/PM use the COPERT speed curve, since CO₂ tracks fuel burned '
                            'far more linearly with distance than with traffic speed.</div>', unsafe_allow_html=True)

        st.markdown('<div class="sec-label">Step 5 — Cold start penalty (temperature-aware)</div>', unsafe_allow_html=True)
        cold_mult  = _em.cold_start_multiplier("CO2", ambient_c)
        cold_km    = min(trip_km, _em.COLD_START_KM)
        cold_extra = ef_after_age * cold_km * (cold_mult - 1.0) * _em.COLD_STARTS_PER_DAY
        st.latex(r"E_{cold} = EF_2 \times \min(\text{trip km}, 5) \times (m(T) - 1) \times \text{starts/day}")
        st.code(f"chill = max(0, (30 − {ambient_c}) / 30) → m(T) = {cold_mult:.3f}\n"
                f"E_cold = {ef_after_age:.1f} × {cold_km:.1f} km × {cold_mult-1:.3f} × "
                f"{_em.COLD_STARTS_PER_DAY} start/day = {cold_extra:.0f} g", language=None)
        st.markdown(f'<div class="tip">A cold engine over-emits for its first ~5 km, but buses running trips '
                    f'back-to-back stay warm — so the penalty is counted <strong>once per day</strong>, not once '
                    f'per trip. And at Lagos\'s {ambient_c} °C ambient the effect is small: the multiplier shrinks '
                    f'linearly and vanishes at 30 °C.</div>', unsafe_allow_html=True)

        st.markdown('<div class="sec-label">Step 6 — Idling</div>', unsafe_allow_html=True)
        idle_min = float(trip.get("Idle_Minutes", _em.DEFAULT_IDLE_MINUTES))
        idle_ef  = _em.IDLING_EF.get(bus_cat, {}).get(fuel, {}).get("CO2", 0.0)
        idle_g   = idle_ef * idle_min
        st.latex(r"E_{idle} = EF_{idle} \times \text{idle\_minutes}")
        st.code(f"E_idle = {idle_ef:.1f} g/min × {idle_min:.0f} min = {idle_g:.0f} g", language=None)

        st.markdown('<div class="sec-label">Step 7 — A/C uplift</div>', unsafe_allow_html=True)
        ac_extra = (hot_g + idle_g) * _em.AC_UPLIFT_CO2 if ac_on else 0.0
        st.latex(r"E_{ac} = (E_{hot} + E_{idle}) \times 0.08 \quad \text{(if A/C on)}")
        st.code(f"A/C status: {'ON' if ac_on else 'OFF'}  →  E_ac = "
                f"{(f'{ac_extra:.0f} g') if ac_on else '0 g (not applied)'}", language=None)

        st.markdown('<div class="sec-label">Step 8 — Load factor correction</div>', unsafe_allow_html=True)
        st.latex(r"\text{LoadCorr} = 1 + \left(\min\!\left(\tfrac{\text{pax on board}}{\text{capacity}}, 1.2\right) - 0.5\right) \times 0.08")
        st.code(f"pax on board = {ridership} riders ÷ {num_trips} trips = {pax_per_trip:.0f}\n"
                f"pax/capacity = {pax_per_trip:.0f}/{capacity} = {pax_per_trip/capacity:.2f}\n"
                f"LoadCorr = 1 + ({min(pax_per_trip/capacity,1.2):.2f} - 0.5) × 0.08 = {load_c:.4f}", language=None)
        st.markdown('<div class="tip">A fuller bus weighs more and burns marginally more fuel — this nudges '
                    'the total by a few percent in either direction depending on load.</div>', unsafe_allow_html=True)

        total_g = (hot_g + cold_extra + idle_g + ac_extra) * load_c
        st.markdown('<div class="sec-label">Step 9 — Total, and per-passenger figure</div>', unsafe_allow_html=True)
        st.latex(r"Total = (E_{hot} + E_{cold} + E_{idle} + E_{ac}) \times \text{LoadCorr}")
        st.code(f"Total = ({hot_g:.0f} + {cold_extra:.0f} + {idle_g:.0f} + {ac_extra:.0f}) × {load_c:.4f}"
                f" = {total_g:.0f} g = {total_g/1000:.3f} kg", language=None)
        if is_revenue:
            gpkm = total_g / passenger_km if passenger_km else 0.0
            st.latex(r"CO_2\,(g/pkm) = \frac{Total\,(g)}{\text{passenger-km}} = \frac{Total\,(g)}{\text{ridership} \times \text{trip km}}")
            st.code(f"passenger_km = {ridership} riders × {trip_km:.1f} km/trip = {passenger_km:,.0f} pkm\n"
                    f"CO2_g_pkm = {total_g:.0f} g ÷ {passenger_km:,.0f} pkm = {gpkm:.2f} g/pkm", language=None)
            flag_thresholds = {"High Capacity": (30,55), "Midi": (45,75), "Mini": (60,95)}.get(bus_cat, (40,70))
            st.markdown(gauge_svg(gpkm, flag_thresholds[0], flag_thresholds[1]), unsafe_allow_html=True)
        else:
            st.markdown('<div class="tip">This wasn\'t a revenue trip (Revenue_Trip = 0/False), so it doesn\'t '
                        'carry a g/pkm compliance figure — only revenue trips are divided by ridership for the '
                        'compliance gauge, since deadheading/positioning runs have no fare-paying passengers.</div>',
                        unsafe_allow_html=True)

    with st.expander("📚 Where every constant comes from"):
        st.markdown("""
- **Base factors** — IPCC 2006 Tier 2 + COPERT V West-Africa fleet calibration, Euro III reference.
- **Euro class multipliers** (NOx/PM only) — EEA COPERT V Technical Report No 12, Table 4.1. CO₂ is *not*
  adjusted by Euro class — after-treatment changes pollutant chemistry, not carbon output.
- **Age deterioration** — COPERT degradation model: +0.4%/yr CO₂, +1.5%/yr NOx (diesel/petrol), +2.0%/yr PM.
- **Cold start** — EMEP/EEA Guidebook Table 3-27, applied to the first 5km of each trip, scaled by trips/day.
- **A/C uplift** — CARB 2021, 8% CO₂ uplift for heavy-duty buses in warm climates, applied per-trip only when
  `AC_Status` is true for that row (not assumed always-on).
- **Electric grid factor** — IEA 2023 regional estimate for Nigeria: 0.46 kg CO₂e/kWh.
- **Speed-correction curves** (COPERT/Hybrid NOx & PM) — fitted functions approximating COPERT V speed bands.
        """)

# ════════════════════════════════════════════════════════
# MODULE 6 — DEEP SEARCH
# ════════════════════════════════════════════════════════
elif selected_module == "Deep Search":
    st.markdown("## 🗂 Deep Search")
    st.markdown(
        '<div class="banner">Filter and export the full calculated manifest. '
        'All emission columns reflect current sidebar methodology, pollutants, and quick filters. '
        'New columns — Euro standard, vehicle age, A/C status, Num_Trips_Today, engine model — '
        'are visible and filterable here.</div>', unsafe_allow_html=True)

    with st.expander("🔧 Advanced filters", expanded=True):
        f1,f2,f3 = st.columns(3)
        with f1:
            try:
                import datetime
                dates_s = pd.to_datetime(fdf["Date"].dropna().astype(str), errors="coerce").dropna()
                mn = dates_s.min().date() if len(dates_s) else datetime.date.today()
                mx = dates_s.max().date() if len(dates_s) else datetime.date.today()
                dr = st.date_input("Date range", value=(mn, mx), min_value=mn, max_value=mx)
            except Exception:
                dr = ()
                st.info("Date filter unavailable.")
        with f2:
            sel_op  = st.multiselect("Operator",     sorted(fdf["Operator"].unique()))
            sel_cat = st.multiselect("Bus category", sorted(fdf["Bus_Category"].unique()))
        with f3:
            sel_fu  = st.multiselect("Fuel type",    sorted(fdf["Fuel_Type"].unique()))
            sel_eu  = st.multiselect("Euro standard",sorted(fdf["Euro_Standard"].unique())) \
                      if "Euro_Standard" in fdf.columns else []

        f4,f5,f6 = st.columns(3)
        with f4:
            bus_q   = st.text_input("Bus ID search", placeholder="e.g. HC-001")
        with f5:
            comp_f  = st.multiselect("Compliance", ["Good","Monitor","Over Limit","N/A"])
        with f6:
            rev_only = st.checkbox("Revenue trips only", value=False)
            unmapped_only = st.checkbox("Unmapped category/fuel only", value=False)

    mask = pd.Series([True]*len(fdf), index=fdf.index)
    if len(dr)==2: mask &= (fdf["Date"]>=dr[0]) & (fdf["Date"]<=dr[1])
    if sel_op:     mask &= fdf["Operator"].isin(sel_op)
    if sel_cat:    mask &= fdf["Bus_Category"].isin(sel_cat)
    if sel_fu:     mask &= fdf["Fuel_Type"].isin(sel_fu)
    if sel_eu and "Euro_Standard" in fdf.columns:
                   mask &= fdf["Euro_Standard"].isin(sel_eu)
    if bus_q:      mask &= fdf["Bus_ID"].str.contains(bus_q, case=False, na=False)
    if comp_f:     mask &= fdf["Compliance"].isin(comp_f)
    if rev_only:   mask &= fdf["Revenue_Trip"].astype(str).str.lower().isin(["true","1"])
    if unmapped_only:
        um = pd.Series([False]*len(fdf), index=fdf.index)
        if "Category_Unmapped" in fdf.columns: um |= fdf["Category_Unmapped"]
        if "Fuel_Unmapped"     in fdf.columns: um |= fdf["Fuel_Unmapped"]
        mask &= um

    out = fdf[mask].copy()
    st.markdown(f"**{len(out):,} records matched** of {len(fdf):,} total")

    SHOW = ["Date","Bus_ID","Route_Name","Operator","Bus_Category","Fuel_Type",
            "Euro_Standard","Vehicle_Age_years","AC_Status","Engine_Model",
            "Num_Trips_Today","Route_Distance_km","Avg_Speed_kmh","Ridership",
            "load_factor","CO2_kg","NOx_kg","PM_kg","CO2_g_pkm","Compliance",
            "Category_Unmapped","Fuel_Unmapped"]
    show_cols = [c for c in SHOW if c in out.columns]

    st.dataframe(out[show_cols].reset_index(drop=True),
        use_container_width=True, hide_index=True,
        column_config={
            "CO2_kg":             st.column_config.NumberColumn("CO₂ kg",        format="%.3f"),
            "NOx_kg":             st.column_config.NumberColumn("NOx kg",         format="%.4f"),
            "PM_kg":              st.column_config.NumberColumn("PM kg",          format="%.5f"),
            "CO2_g_pkm":          st.column_config.NumberColumn("g CO₂/pkm",      format="%.1f"),
            "load_factor":        st.column_config.ProgressColumn("Load", min_value=0, max_value=1, format="%.2f"),
            "Vehicle_Age_years":  st.column_config.NumberColumn("Age (yrs)"),
            "Num_Trips_Today":    st.column_config.NumberColumn("Trips/day"),
            "Route_Distance_km":  st.column_config.NumberColumn("Distance km",    format="%.1f"),
        })

    col_dl1, col_dl2 = st.columns([1,3])
    with col_dl1:
        st.download_button(
            "⬇ Download CSV", data=out[show_cols].to_csv(index=False).encode(),
            file_name="fleet_export.csv", mime="text/csv", use_container_width=True)
        if data_source == "database" and db.get_client() is not None:
            if st.button("💾 Snapshot results to DB", use_container_width=True,
                         help="Stores these calculated emissions stamped with methodology, "
                              "ambient temp and engine version — so any figure in a report "
                              "can be reproduced exactly later."):
                snap = db.save_emissions_snapshot(fdf, methodology, ambient_c)
                if snap["error"]:
                    st.warning(snap["error"])
                else:
                    st.success(f"Snapshot saved — {snap['saved']:,} rows under '{methodology}'")

# ── Floating AI assistant (renders over every module) ──
render_ai_assistant(fdf)
