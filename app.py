"""
LAMATA Emissions Portal v3
Modules: Dashboard · Fleet Intelligence · Pollutant Engine ·
         Bus Efficiency · Trip Inspector · Deep Search
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_option_menu import option_menu
from emissions_engine import calculate_row, emission_breakdown, compliance_flag

# ════════════════════════════════════════════════════════
# 0. PAGE CONFIG
# ════════════════════════════════════════════════════════
st.set_page_config(
    page_title="LAMATA Emissions Portal",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════════════════════
# 1. GLOBAL CSS  — premium dark-navy sidebar + clean main
# ════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

/* ── chrome ── */
#MainMenu, footer, header { visibility: hidden; }
div[data-testid="stSidebarNav"] { display: none; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── sidebar shell ── */
section[data-testid="stSidebar"] > div:first-child {
    background: #07111f;
    border-right: 1px solid #14283f;
    padding-top: 0 !important;
}
section[data-testid="stSidebar"] * { color: #b8cce0 !important; }

/* ── sidebar file uploader ── */
section[data-testid="stSidebar"] .stFileUploader label,
section[data-testid="stSidebar"] .stFileUploader small { color: #6a85a3 !important; font-size:11px !important; }
section[data-testid="stSidebar"] .stFileUploader [data-testid="stFileUploaderDropzone"] {
    background: #0e1f31 !important; border-color: #1e3a55 !important; border-radius: 8px !important;
}

/* ── sidebar selectbox / multiselect ── */
section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div,
section[data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"] > div {
    background: #0e1f31 !important; border-color: #1e3a55 !important; border-radius: 8px !important;
    font-size: 12px !important;
}

/* ── nav menu ── */
.nav-link { border-radius: 8px !important; margin: 1px 0 !important; font-size:13px !important; }
.nav-link-selected { background: #0f3460 !important; color: #4facfe !important; }
.nav-link:hover { background: #0d2137 !important; }

/* ── metric cards ── */
div[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e8edf5;
    border-radius: 14px;
    padding: 18px 20px 14px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
div[data-testid="stMetricLabel"] > div  { font-size: 11px !important; color: #7a8599 !important; font-weight:500 !important; letter-spacing:0.04em; text-transform:uppercase; }
div[data-testid="stMetricValue"] > div  { font-size: 28px !important; color: #0f1923 !important; font-weight:600 !important; letter-spacing:-0.5px; }
div[data-testid="stMetricDelta"]        { font-size: 12px !important; }

/* ── info / section banners ── */
.banner {
    background: linear-gradient(135deg, #0f3460 0%, #0a1f3a 100%);
    color: #c8dff5 !important;
    border-radius: 12px;
    padding: 14px 20px;
    font-size: 13px;
    line-height: 1.65;
    margin-bottom: 18px;
    border: 1px solid #1a3d5c;
}
.banner strong { color: #4facfe !important; }
.banner code   { background: rgba(79,172,254,0.12); color: #7fc8ff !important; padding: 1px 6px; border-radius:4px; font-size:11px; }

/* ── filter chip bar ── */
.chip-bar { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }
.chip {
    display:inline-flex; align-items:center; gap:5px;
    padding: 5px 12px; border-radius:20px;
    font-size: 12px; font-weight:500; cursor:pointer;
    border: 1.5px solid transparent;
    transition: all 0.15s;
}
.chip-blue   { background:#e8f2ff; color:#1a5fac; border-color:#aac9f0; }
.chip-green  { background:#eaf4e0; color:#2a6916; border-color:#9dcc72; }
.chip-amber  { background:#fef4e0; color:#7a4a06; border-color:#f0c060; }
.chip-red    { background:#fee8e8; color:#8b1a1a; border-color:#f09090; }
.chip-purple { background:#f0ecff; color:#3d1a8c; border-color:#b09de0; }
.chip-teal   { background:#e0f5f0; color:#0a5040; border-color:#70cbb8; }
.chip-gray   { background:#f0f2f5; color:#4a5568; border-color:#c8d0dc; }

/* ── compliance badges ── */
.badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; }
.badge-good    { background:#dcfce7; color:#15803d; }
.badge-monitor { background:#fef9c3; color:#92400e; }
.badge-over    { background:#fee2e2; color:#b91c1c; }
.badge-na      { background:#f1f5f9; color:#64748b; }

/* ── kpi accent cards ── */
.kpi-accent {
    border-radius: 14px; padding: 16px 18px;
    border: 1px solid #e2e8f0;
    background: #fff;
}
.kpi-accent .val  { font-size:26px; font-weight:600; color:#0f1923; letter-spacing:-0.5px; line-height:1.2; }
.kpi-accent .lbl  { font-size:11px; color:#7a8599; font-weight:500; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px; }
.kpi-accent .sub  { font-size:12px; color:#8a94a8; margin-top:4px; }
.kpi-accent .dot  { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; vertical-align:middle; }

/* ── section divider with label ── */
.sec-label {
    font-size:10px; font-weight:600; letter-spacing:0.1em; text-transform:uppercase;
    color:#9aa5bb; margin: 22px 0 10px; display:flex; align-items:center; gap:10px;
}
.sec-label::after { content:''; flex:1; height:1px; background:#e8edf5; }

/* ── plotly override ── */
.js-plotly-plot .plotly .main-svg { background: transparent !important; }

/* ── table ── */
div[data-testid="stDataFrame"] { border-radius:12px; overflow:hidden; border:1px solid #e8edf5; }

/* ── tab styling ── */
div[data-testid="stTabs"] button { font-size:13px !important; }

/* ── tip cards ── */
.tip { background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:11px 14px; margin-bottom:8px; font-size:12px; color:#14532d; line-height:1.6; }
.tip strong { color:#166534; }

/* ── breakdown bar ── */
.brow { display:flex; align-items:center; gap:10px; margin-bottom:9px; }
.brow .lbl  { font-size:11px; color:#7a8599; width:90px; flex-shrink:0; }
.brow .bg   { flex:1; height:7px; background:#f0f2f7; border-radius:4px; overflow:hidden; }
.brow .fill { height:100%; border-radius:4px; }
.brow .val  { font-size:12px; font-weight:600; color:#0f1923; width:62px; text-align:right; flex-shrink:0; }

/* ── empty state ── */
.empty { display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:58vh; text-align:center; gap:14px; }
.empty .icon { font-size:52px; }
.empty h2 { font-size:22px; font-weight:600; color:#0f1923; }
.empty p  { font-size:14px; color:#6b7a94; max-width:440px; line-height:1.7; }
.empty code { font-size:11px; background:#f0f4fa; color:#3451a1; padding:2px 7px; border-radius:4px; }
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

PALETTE  = ["#1a73e8","#34a853","#fbbc04","#ea4335","#9c27b0","#00bcd4","#ff6d00","#607d8b"]
PLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter",size=12,color="#374151"),
    margin=dict(l=4,r=4,t=36,b=4),
    legend=dict(bgcolor="rgba(0,0,0,0)",borderwidth=0),
)

def fmt_kg(v):  return f"{v:,.1f} kg"
def fmt_t(v):   return f"{v/1000:,.2f} t"
def fmt_gkm(v): return f"{v:,.1f} g/pkm"

def badge_html(flag):
    cls = {"Good":"badge-good","Monitor":"badge-monitor","Over Limit":"badge-over"}.get(flag,"badge-na")
    return f'<span class="badge {cls}">{flag}</span>'

def chip(label, cls="chip-gray"):
    return f'<span class="chip {cls}">{label}</span>'

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
    st.markdown("""
    <div style="background:#0d2137;padding:18px 16px 14px;margin:-1rem -1rem 0;border-bottom:1px solid #14283f;">
        <div style="display:flex;align-items:center;gap:11px;">
            <div style="width:38px;height:38px;background:linear-gradient(135deg,#1a73e8,#0a3d8f);
                        border-radius:10px;display:flex;align-items:center;justify-content:center;
                        font-size:20px;flex-shrink:0;">🚌</div>
            <div>
                <div style="font-size:15px;font-weight:600;color:#e8f2ff;letter-spacing:0.02em;">LAMATA</div>
                <div style="font-size:11px;color:#4a7fa8;margin-top:1px;">Emissions Portal v3</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

    selected_module = option_menu(
        menu_title=None,
        options=["Dashboard","Fleet Intelligence","Pollutant Engine","Bus Efficiency","Trip Inspector","Deep Search"],
        icons=["speedometer2","diagram-3","cloud-haze2","bus-front","search-heart","table"],
        default_index=0,
        styles={
            "container":         {"padding":"0!important","background-color":"transparent"},
            "icon":              {"color":"#3a6ea8","font-size":"15px"},
            "nav-link":          {"font-size":"13px","text-align":"left","margin":"1px 0",
                                  "color":"#7aaad0","--hover-color":"#0d2137","padding":"9px 14px"},
            "nav-link-selected": {"background-color":"#0f3460","color":"#4facfe",
                                  "font-weight":"600","border-radius":"8px"},
        },
    )

    # ── DATA INPUT ──
    st.markdown("""<div style="font-size:10px;font-weight:600;letter-spacing:0.08em;
        text-transform:uppercase;color:#3a6ea8;margin:18px 0 8px;padding:0 2px;">Data Input</div>""",
        unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Route manifest (CSV)", type=["csv"], label_visibility="collapsed"
    )

    # ── GLOBAL CONTROLS ──
    st.markdown("""<div style="font-size:10px;font-weight:600;letter-spacing:0.08em;
        text-transform:uppercase;color:#3a6ea8;margin:18px 0 8px;padding:0 2px;">Calculation</div>""",
        unsafe_allow_html=True)
    methodology = st.selectbox(
        "Method", ["Hybrid","IPCC","COPERT"],
        help="Hybrid: CO₂ via IPCC Tier 2, NOx/PM via COPERT V.\nIPCC: all pollutants fixed factor.\nCOPERT: all speed-corrected.",
        label_visibility="collapsed",
    )
    target_pollutants = st.multiselect(
        "Pollutants", ["CO2","NOx","PM"], default=["CO2","NOx"],
        label_visibility="collapsed",
    )

    # ── ACTIVE FILTERS ──
    if "active_operator" not in st.session_state: st.session_state.active_operator = None
    if "active_euro"     not in st.session_state: st.session_state.active_euro     = None
    if "active_fuel"     not in st.session_state: st.session_state.active_fuel     = None
    if "active_category" not in st.session_state: st.session_state.active_category = None

    st.markdown("""<div style="font-size:10px;font-weight:600;letter-spacing:0.08em;
        text-transform:uppercase;color:#3a6ea8;margin:18px 0 8px;padding:0 2px;">Quick Filters</div>""",
        unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px;color:#4a7fa8;margin-bottom:6px;">Applied across all modules</div>',
        unsafe_allow_html=True)

    if st.button("✕ Clear all filters", use_container_width=True,
                 type="secondary" if any([st.session_state.active_operator,
                    st.session_state.active_euro,st.session_state.active_fuel,
                    st.session_state.active_category]) else "secondary"):
        st.session_state.active_operator = None
        st.session_state.active_euro     = None
        st.session_state.active_fuel     = None
        st.session_state.active_category = None

    st.markdown("---")
    st.markdown(
        '<div style="font-size:10px;color:#2a4f6e;line-height:1.7;padding:0 2px;">'
        'Factors: IPCC 2006 Tier 2 · COPERT V<br>'
        'Euro II–VI NOx/PM multipliers · Age deterioration<br>'
        'A/C per-trip flag · Engine model correction<br>'
        'Nigeria grid: 0.46 kg CO₂e/kWh (IEA 2023)'
        '</div>', unsafe_allow_html=True
    )

# ════════════════════════════════════════════════════════
# 4. DATA LOADING + CALCULATION
# ════════════════════════════════════════════════════════
if not uploaded_file:
    st.markdown("""
    <div class="empty">
        <div class="icon">🚌</div>
        <h2>LAMATA Emissions Portal</h2>
        <p>Upload your route manifest CSV in the sidebar to activate all six modules.
        Required columns: <code>Date</code> <code>Route_Name</code> <code>Bus_ID</code>
        <code>Operator</code> <code>Bus_Category</code> <code>Fuel_Type</code>
        <code>Route_Distance_km</code> <code>Avg_Speed_kmh</code> <code>Ridership</code>
        <code>Revenue_Trip</code><br><br>
        Recommended additions: <code>Euro_Standard</code> <code>Vehicle_Age_years</code>
        <code>AC_Status</code> <code>Num_Trips_Today</code> <code>Engine_Model</code></p>
        <p style="font-size:12px;color:#9aa5bb;">
        IPCC Tier 2 · COPERT V · Euro class NOx/PM · Age deterioration · A/C correction</p>
    </div>""", unsafe_allow_html=True)
    st.stop()

@st.cache_data(show_spinner="Calculating emissions…", ttl=300)
def load_and_calc(fbytes, method, pollutants):
    import io
    df = pd.read_csv(io.BytesIO(fbytes))
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        return None, missing
    # Fill optional new columns with defaults if absent
    defaults = {
        "Euro_Standard":    "Euro III",
        "Vehicle_Age_years": 5,
        "AC_Status":         True,
        "Num_Trips_Today":   6,
        "Engine_Model":      "",
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val
    results = df.apply(lambda r: calculate_row(r, method, pollutants), axis=1)
    df = pd.concat([df, results], axis=1)
    if "CO2" in pollutants:
        df["Compliance"] = df.apply(
            lambda r: compliance_flag(float(r.get("CO2_g_pkm",0)), r["Bus_Category"]), axis=1)
    else:
        df["Compliance"] = "N/A"
    return df, []

file_bytes = uploaded_file.read()
df, missing = load_and_calc(file_bytes, methodology, target_pollutants)

if df is None:
    st.error(f"❌ Missing required columns: **{', '.join(missing)}**")
    st.stop()
if not target_pollutants:
    st.warning("Select at least one pollutant in the sidebar.")
    st.stop()

# ── Apply sidebar quick filters ──
def apply_filters(src):
    d = src.copy()
    if st.session_state.active_operator: d = d[d["Operator"]   == st.session_state.active_operator]
    if st.session_state.active_euro:     d = d[d["Euro_Standard"] == st.session_state.active_euro]
    if st.session_state.active_fuel:     d = d[d["Fuel_Type"]  == st.session_state.active_fuel]
    if st.session_state.active_category: d = d[d["Bus_Category"]== st.session_state.active_category]
    return d

# ════════════════════════════════════════════════════════
# MODULE 0 — ACTIVE FILTER BANNER (shown on every page)
# ════════════════════════════════════════════════════════
active_filters = {k:v for k,v in {
    "Operator":  st.session_state.active_operator,
    "Euro":      st.session_state.active_euro,
    "Fuel":      st.session_state.active_fuel,
    "Category":  st.session_state.active_category,
}.items() if v}

if active_filters:
    chip_map = {"Operator":"chip-blue","Euro":"chip-purple","Fuel":"chip-green","Category":"chip-amber"}
    chips_html = " ".join(chip(f"{k}: {v}", chip_map.get(k,"chip-gray")) for k,v in active_filters.items())
    st.markdown(
        f'<div style="background:#fefce8;border:1px solid #fde68a;border-radius:10px;'
        f'padding:10px 14px;margin-bottom:14px;font-size:12px;color:#78350f;">'
        f'<strong>Active filters:</strong>&nbsp; {chips_html}</div>',
        unsafe_allow_html=True)

fdf = apply_filters(df)  # filtered dataframe used by all modules

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

    st.markdown('<div class="sec-label">Filter by attribute — click to drill down</div>', unsafe_allow_html=True)

    # ── Operator chips ──
    st.markdown("**Operators**")
    ops = sorted(df["Operator"].unique())
    op_cols = st.columns(len(ops))
    for i, op in enumerate(ops):
        active = st.session_state.active_operator == op
        if op_cols[i].button(
            ("✓ " if active else "") + op,
            key=f"op_{op}",
            type="primary" if active else "secondary",
            use_container_width=True
        ):
            st.session_state.active_operator = None if active else op
            st.rerun()

    # ── Euro standard chips ──
    euros = sorted(df["Euro_Standard"].unique())
    st.markdown("**Euro standard**")
    euro_cols = st.columns(len(euros))
    for i, eu in enumerate(euros):
        active = st.session_state.active_euro == eu
        if euro_cols[i].button(
            ("✓ " if active else "") + eu,
            key=f"eu_{eu}",
            type="primary" if active else "secondary",
            use_container_width=True
        ):
            st.session_state.active_euro = None if active else eu
            st.rerun()

    # ── Fuel type + Category chips ──
    c_fuel, c_cat = st.columns(2)
    with c_fuel:
        st.markdown("**Fuel type**")
        fuels = sorted(df["Fuel_Type"].unique())
        fc = st.columns(min(len(fuels), 5))
        for i, fu in enumerate(fuels):
            active = st.session_state.active_fuel == fu
            if fc[i].button(("✓ " if active else "") + fu, key=f"fu_{fu}",
                            type="primary" if active else "secondary", use_container_width=True):
                st.session_state.active_fuel = None if active else fu
                st.rerun()
    with c_cat:
        st.markdown("**Bus category**")
        cats = sorted(df["Bus_Category"].unique())
        cc = st.columns(min(len(cats), 4))
        for i, ca in enumerate(cats):
            active = st.session_state.active_category == ca
            if cc[i].button(("✓ " if active else "") + ca, key=f"ca_{ca}",
                            type="primary" if active else "secondary", use_container_width=True):
                st.session_state.active_category = None if active else ca
                st.rerun()

    st.markdown('<div class="sec-label">Emission overview</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if "CO2" in target_pollutants:
            op_co2 = fdf.groupby("Operator")["CO2_kg"].sum().reset_index()
            fig = px.pie(op_co2, values="CO2_kg", names="Operator",
                         title="CO₂ share by operator", hole=0.52,
                         color_discrete_sequence=PALETTE)
            fig.update_traces(textposition="outside", textinfo="percent+label", textfont_size=11)
            fig.update_layout(**PLY_BASE, showlegend=False, title_font_size=13)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Euro class CO2 comparison
        if "CO2" in target_pollutants and "Euro_Standard" in fdf.columns:
            eu_co2 = fdf.groupby("Euro_Standard")["CO2_g_pkm"].mean().reset_index().sort_values("CO2_g_pkm", ascending=False)
            eu_co2.columns = ["Euro Standard","Avg CO₂ g/pkm"]
            fig2 = px.bar(eu_co2, x="Euro Standard", y="Avg CO₂ g/pkm",
                          title="Average CO₂ intensity by Euro class",
                          color="Avg CO₂ g/pkm",
                          color_continuous_scale=["#22c55e","#eab308","#ef4444"],
                          text_auto=".1f")
            fig2.update_layout(**PLY_BASE, title_font_size=13, showlegend=False,
                               coloraxis_showscale=False, xaxis_title="", yaxis_title="g CO₂/pkm")
            fig2.update_traces(textfont_size=11, cliponaxis=False)
            st.plotly_chart(fig2, use_container_width=True)

    # Daily CO2 trend
    if "CO2" in target_pollutants:
        daily = fdf.groupby("Date")["CO2_kg"].sum().reset_index()
        daily["Date"] = daily["Date"].astype(str)
        fig3 = px.area(daily, x="Date", y="CO2_kg",
                       title="Daily CO₂ total",
                       color_discrete_sequence=["#1a73e8"])
        fig3.update_traces(fillcolor="rgba(26,115,232,0.10)", line_width=2.5)
        fig3.update_layout(**PLY_BASE, title_font_size=13, xaxis_title="", yaxis_title="kg CO₂")
        st.plotly_chart(fig3, use_container_width=True)

    # Compliance + age heatmap side-by-side
    col3, col4 = st.columns(2)
    with col3:
        comp_ct = fdf["Compliance"].value_counts().reset_index()
        comp_ct.columns=["Status","Trips"]
        cmap = {"Good":"#22c55e","Monitor":"#eab308","Over Limit":"#ef4444","N/A":"#94a3b8"}
        fig4 = px.bar(comp_ct, x="Status", y="Trips", color="Status",
                      title="Trips by compliance status",
                      color_discrete_map=cmap, text_auto=True)
        fig4.update_layout(**PLY_BASE, showlegend=False, title_font_size=13,
                           xaxis_title="", yaxis_title="Trips")
        st.plotly_chart(fig4, use_container_width=True)
    with col4:
        if "Vehicle_Age_years" in fdf.columns and "CO2" in target_pollutants:
            age_eff = fdf[fdf["Revenue_Trip"].astype(str).str.lower().isin(["true","1"])]\
                .groupby("Vehicle_Age_years")["CO2_g_pkm"].mean().reset_index()
            fig5 = px.bar(age_eff, x="Vehicle_Age_years", y="CO2_g_pkm",
                          title="CO₂ intensity vs vehicle age",
                          color="CO2_g_pkm",
                          color_continuous_scale=["#22c55e","#ef4444"], text_auto=".1f")
            fig5.update_layout(**PLY_BASE, title_font_size=13, showlegend=False,
                               coloraxis_showscale=False,
                               xaxis_title="Vehicle age (years)", yaxis_title="g CO₂/pkm")
            st.plotly_chart(fig5, use_container_width=True)

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
                                color_discrete_sequence=["#1a73e8"])
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
        op_pol = fdf.groupby("Operator")[agg_cols].sum().reset_index()\
            .melt(id_vars="Operator", var_name="Pollutant", value_name="kg")
        op_pol["Pollutant"] = op_pol["Pollutant"].str.replace("_kg","")
        fig = px.bar(op_pol, x="Operator", y="kg", color="Pollutant", barmode="group",
                     title="Pollutant volume by operator",
                     color_discrete_sequence=PALETTE[:len(target_pollutants)])
        fig.update_layout(**PLY_BASE, title_font_size=13, xaxis_title="", yaxis_title="kg")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fuel_pol = fdf.groupby("Fuel_Type")[agg_cols].sum().reset_index()\
            .melt(id_vars="Fuel_Type", var_name="Pollutant", value_name="kg")
        fuel_pol["Pollutant"] = fuel_pol["Pollutant"].str.replace("_kg","")
        fig2 = px.bar(fuel_pol, x="Fuel_Type", y="kg", color="Pollutant", barmode="stack",
                      title="Pollutant volume by fuel type (stacked)",
                      color_discrete_sequence=PALETTE[:len(target_pollutants)])
        fig2.update_layout(**PLY_BASE, title_font_size=13, xaxis_title="", yaxis_title="kg")
        st.plotly_chart(fig2, use_container_width=True)

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
                         title="Mean CO₂ g/pkm — Euro class × fuel type")
        fig4.update_layout(**PLY_BASE, title_font_size=13)
        st.plotly_chart(fig4, use_container_width=True)

# ════════════════════════════════════════════════════════
# MODULE 4 — BUS EFFICIENCY
# ════════════════════════════════════════════════════════
elif selected_module == "Bus Efficiency":
    st.markdown("## 🚌 Bus Efficiency")
    st.markdown(
        '<div class="banner">Efficiency = CO₂ grams per passenger-kilometre (g CO₂/pkm). '
        'Lower is better. Compliance thresholds: High Capacity ≤30 Good / ≤55 Monitor; '
        'Midi ≤45 / ≤75; Mini ≤60 / ≤95. '
        'Scores reflect Euro class, age, A/C, and engine model corrections.</div>',
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
        lambda r: compliance_flag(r["CO2_g_pkm"], r["Category"]), axis=1)

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
        colors  = ["#1a73e8","#fbbc04","#ef4444","#34a853","#9c27b0"]
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
            f'<div style="margin-top:14px;padding:14px 18px;background:#f0f7ff;'
            f'border:1px solid #c0d8f8;border-radius:12px;">'
            f'<div style="font-size:11px;color:#5a7a9a;margin-bottom:4px;">TOTAL CO₂ THIS TRIP</div>'
            f'<div style="font-size:26px;font-weight:600;color:#0f1923;">{bd["total_g"]/1000:.3f} kg</div>'
            f'</div>', unsafe_allow_html=True)

        if "CO2" in target_pollutants:
            gpkm = float(trip.get("CO2_g_pkm",0))
            flag = compliance_flag(gpkm, trip["Bus_Category"])
            st.markdown(
                f'<div style="margin-top:12px;">'
                f'<div style="font-size:11px;color:#7a8599;margin-bottom:6px;">Compliance status</div>'
                f'{badge_html(flag)} <span style="font-size:13px;color:#374151;margin-left:6px;">{gpkm:.1f} g CO₂/pkm</span>'
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
            fig.update_layout(**PLY_BASE, title="Source split", title_font_size=13,
                              showlegend=True,
                              legend=dict(orientation="v",x=1.02,y=0.5))
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
            mn, mx = fdf["Date"].min(), fdf["Date"].max()
            dr = st.date_input("Date range", value=(mn,mx), min_value=mn, max_value=mx)
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

    out = fdf[mask].copy()
    st.markdown(f"**{len(out):,} records matched** of {len(fdf):,} total")

    SHOW = ["Date","Bus_ID","Route_Name","Operator","Bus_Category","Fuel_Type",
            "Euro_Standard","Vehicle_Age_years","AC_Status","Engine_Model",
            "Num_Trips_Today","Route_Distance_km","Avg_Speed_kmh","Ridership",
            "load_factor","CO2_kg","NOx_kg","PM_kg","CO2_g_pkm","Compliance"]
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
            file_name="lamata_export.csv", mime="text/csv", use_container_width=True)
