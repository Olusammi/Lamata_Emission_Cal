"""
LAMATA Emissions Portal v2
==========================
Modules:
  1. Dashboard       — Fleet-level KPIs + trend charts
  2. Pollutant Engine — Multi-pollutant analysis with methodology selector
  3. Bus Efficiency  — Per-bus g CO2/pkm with compliance flags
  4. Trip Inspector  — Single-trip emission breakdown (hot/cold/idle/AC)
  5. Deep Search     — Filterable records table with CSV export
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_option_menu import option_menu
from emissions_engine import calculate_row, emission_breakdown, compliance_flag

# ══════════════════════════════════════════════════════════════
# 0. PAGE CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="LAMATA Emissions Portal",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════
# 1. GLOBAL STYLES
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Remove Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
div[data-testid="stSidebarNav"] { display: none; }

/* ── Base typography ── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0b1120;
    border-right: 1px solid #1e2d47;
}
section[data-testid="stSidebar"] * { color: #c9d4e8 !important; }
section[data-testid="stSidebar"] .stFileUploader label { color: #8899bb !important; font-size: 12px !important; }

/* ── Nav menu overrides ── */
.nav-link { border-radius: 8px !important; margin: 2px 0 !important; }
.nav-link-selected { background: #1a3460 !important; color: #60aaff !important; }
.nav-link-selected svg { color: #60aaff !important; }

/* ── Metric cards ── */
div[data-testid="stMetric"] {
    background: #f4f7ff;
    border: 1px solid #dde5f5;
    border-radius: 12px;
    padding: 16px 20px;
}
div[data-testid="stMetricLabel"] > div { font-size: 12px !important; color: #6c7a99 !important; font-weight: 500 !important; }
div[data-testid="stMetricValue"] > div { font-size: 26px !important; color: #111827 !important; font-weight: 600 !important; }
div[data-testid="stMetricDelta"] svg { display: none; }

/* ── Section headers ── */
.section-header {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #8899bb;
    margin: 20px 0 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid #1e2d47;
}

/* ── Info card ── */
.info-card {
    background: #f8faff;
    border: 1px solid #dde5f5;
    border-left: 4px solid #2563eb;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 16px;
    font-size: 13px;
    color: #374151;
    line-height: 1.6;
}

/* ── Compliance badges ── */
.badge-good    { background:#dcfce7; color:#166534; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; }
.badge-monitor { background:#fef9c3; color:#854d0e; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; }
.badge-over    { background:#fee2e2; color:#991b1b; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; }

/* ── Tip cards ── */
.tip-card {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    font-size: 13px;
    color: #14532d;
    line-height: 1.6;
}
.tip-card strong { color: #166534; }

/* ── Breakdown bar ── */
.breakdown-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.breakdown-label { font-size: 12px; color: #6c7a99; width: 80px; }
.breakdown-bar-bg { flex: 1; height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; }
.breakdown-bar-fill { height: 100%; border-radius: 4px; }
.breakdown-val { font-size: 12px; font-weight: 600; color: #111827; width: 60px; text-align: right; }

/* ── Plotly chart background ── */
.js-plotly-plot .plotly .main-svg { background: transparent !important; }

/* ── Divider ── */
hr { border: none; border-top: 1px solid #e5e9f5; margin: 20px 0; }

/* ── Table ── */
div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; border: 1px solid #dde5f5; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# 2. SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    # Logo area
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;padding:8px 4px 20px;">
        <div style="width:36px;height:36px;background:#2563eb;border-radius:9px;
                    display:flex;align-items:center;justify-content:center;flex-shrink:0;">
            <span style="font-size:18px;">🚌</span>
        </div>
        <div>
            <div style="font-size:14px;font-weight:700;color:#e8eeff;letter-spacing:0.02em;">LAMATA</div>
            <div style="font-size:11px;color:#6b80ab;">Emissions Portal v2</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    selected_module = option_menu(
        menu_title=None,
        options=["Dashboard", "Pollutant Engine", "Bus Efficiency", "Trip Inspector", "Deep Search"],
        icons=["speedometer2", "cloud-haze2", "bus-front", "search-heart", "table"],
        menu_icon="cast",
        default_index=0,
        styles={
            "container":        {"padding": "0 !important", "background-color": "transparent"},
            "icon":             {"color": "#5b7ec4", "font-size": "16px"},
            "nav-link":         {"font-size": "13px", "text-align": "left", "margin": "2px 0",
                                 "color": "#a0b0d0", "--hover-color": "#162040"},
            "nav-link-selected":{"background-color": "#162040", "color": "#60aaff",
                                 "font-weight": "600", "border-radius": "8px"},
        },
    )

    st.markdown('<div class="section-header">Data Input</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload route manifest (CSV)", type=["csv"], label_visibility="collapsed")

    # Methodology selector (global)
    st.markdown('<div class="section-header">Calculation Method</div>', unsafe_allow_html=True)
    methodology = st.selectbox(
        "Methodology",
        ["Hybrid", "IPCC", "COPERT"],
        help=(
            "**Hybrid** — CO₂ via IPCC Tier 2 fixed factor; NOx/PM via COPERT V speed function. "
            "Recommended for LAMATA reporting.\n\n"
            "**IPCC** — All pollutants at fixed emission factors regardless of speed.\n\n"
            "**COPERT** — All pollutants speed-corrected via COPERT V heavy-duty bus functions."
        ),
        label_visibility="collapsed",
    )

    st.markdown('<div class="section-header">Pollutants</div>', unsafe_allow_html=True)
    target_pollutants = st.multiselect(
        "Track pollutants",
        ["CO2", "NOx", "PM"],
        default=["CO2", "NOx"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown(
        '<div style="font-size:10px;color:#4a5e85;line-height:1.6;">'
        'Factors: IPCC 2006 Tier 2 · COPERT V · IEA Africa Grid 2023<br>'
        'Cold start · Idling · A/C load corrections applied.'
        '</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════
# 3. DATA LOADING
# ══════════════════════════════════════════════════════════════
EXPECTED_COLS = [
    "Date", "Route_Name", "Bus_ID", "Operator",
    "Bus_Category", "Fuel_Type", "Route_Distance_km",
    "Avg_Speed_kmh", "Ridership", "Revenue_Trip",
]

if not uploaded_file:
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:60vh;text-align:center;gap:16px;">
        <div style="font-size:56px;">🚌</div>
        <div style="font-size:24px;font-weight:700;color:#111827;">LAMATA Emissions Portal</div>
        <div style="font-size:15px;color:#6b7280;max-width:420px;line-height:1.7;">
            Upload a route manifest CSV in the sidebar to activate all modules.
            The file must include: <code>Date, Route_Name, Bus_ID, Operator, Bus_Category,
            Fuel_Type, Route_Distance_km, Avg_Speed_kmh, Ridership, Revenue_Trip</code>.
        </div>
        <div style="font-size:12px;color:#9ca3af;margin-top:8px;">
            Methodology: IPCC Tier 2 · COPERT V · Cold start · Idling · A/C corrections
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

@st.cache_data(show_spinner="Loading and calculating emissions…")
def load_and_calc(file_bytes, method, pollutants):
    import io
    df = pd.read_csv(io.BytesIO(file_bytes))
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        return None, missing
    results = df.apply(lambda r: calculate_row(r, method, pollutants), axis=1)
    df = pd.concat([df, results], axis=1)
    # Compliance flag based on CO2 g/pkm
    if "CO2" in pollutants:
        df["Compliance"] = df.apply(
            lambda r: compliance_flag(r.get("CO2_g_pkm", 0), r["Bus_Category"]), axis=1
        )
    else:
        df["Compliance"] = "N/A"
    return df, []

file_bytes = uploaded_file.read()
df, missing = load_and_calc(file_bytes, methodology, target_pollutants)

if df is None:
    st.error(f"❌ Missing columns: **{', '.join(missing)}**. Fix the CSV and re-upload.")
    st.stop()

if not target_pollutants:
    st.warning("Select at least one pollutant in the sidebar.")
    st.stop()


# ══════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", size=12, color="#374151"),
    margin=dict(l=8, r=8, t=36, b=8),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
)
BLUE_PALETTE   = ["#2563eb", "#60a5fa", "#93c5fd", "#bfdbfe", "#dbeafe"]
MULTI_PALETTE  = ["#2563eb", "#f59e0b", "#ef4444", "#10b981", "#8b5cf6"]


def fmt_kg(val):
    return f"{val:,.1f} kg"

def fmt_gkm(val):
    return f"{val:,.1f} g/pkm"


# ══════════════════════════════════════════════════════════════
# MODULE 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════
if selected_module == "Dashboard":
    st.title("📊 Fleet Dashboard")
    st.markdown(
        '<div class="info-card">High-level operational overview using the <strong>'
        + methodology
        + "</strong> methodology. CO₂ figures include cold-start, idling, and A/C auxiliary corrections.</div>",
        unsafe_allow_html=True,
    )

    rev_df = df[df["Revenue_Trip"] == True]
    total_co2   = df["CO2_kg"].sum() if "CO2_kg" in df else 0
    total_nox   = df["NOx_kg"].sum() if "NOx_kg" in df else 0
    avg_eff     = rev_df["CO2_g_pkm"].mean() if "CO2_g_pkm" in rev_df and "CO2" in target_pollutants else 0
    over_limit  = (df["Compliance"] == "Over Limit").sum()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Trips",      f"{len(df):,}")
    k2.metric("Total Passengers", f"{df['Ridership'].sum():,}")
    k3.metric("Total CO₂",        fmt_kg(total_co2) if "CO2" in target_pollutants else "—")
    k4.metric("Avg Efficiency",   fmt_gkm(avg_eff)  if "CO2" in target_pollutants else "—")
    k5.metric("Over-limit trips", str(over_limit), delta=f"{over_limit} need review", delta_color="inverse")

    st.markdown("---")

    col_l, col_r = st.columns(2)

    with col_l:
        # CO2 by operator donut
        if "CO2" in target_pollutants:
            op_co2 = df.groupby("Operator")["CO2_kg"].sum().reset_index()
            fig = px.pie(
                op_co2, values="CO2_kg", names="Operator",
                title="CO₂ share by operator",
                hole=0.52, color_discrete_sequence=BLUE_PALETTE,
            )
            fig.update_traces(textposition="outside", textinfo="percent+label")
            fig.update_layout(**PLOTLY_LAYOUT, showlegend=False, title_font_size=13)
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        # Ridership by category bar
        cat_rid = df.groupby("Bus_Category")["Ridership"].sum().reset_index()
        fig2 = px.bar(
            cat_rid, x="Bus_Category", y="Ridership",
            title="Ridership by bus category",
            color="Bus_Category", color_discrete_sequence=BLUE_PALETTE,
            text_auto=True,
        )
        fig2.update_layout(**PLOTLY_LAYOUT, showlegend=False, title_font_size=13,
                           xaxis_title="", yaxis_title="Passengers")
        fig2.update_traces(textfont_size=11, cliponaxis=False)
        st.plotly_chart(fig2, use_container_width=True)

    # Daily trend
    if "CO2" in target_pollutants:
        daily = df.groupby("Date")["CO2_kg"].sum().reset_index()
        daily["Date"] = daily["Date"].astype(str)
        fig3 = px.area(
            daily, x="Date", y="CO2_kg",
            title="Daily CO₂ trend",
            color_discrete_sequence=["#2563eb"],
        )
        fig3.update_layout(**PLOTLY_LAYOUT, title_font_size=13,
                           xaxis_title="", yaxis_title="kg CO₂")
        fig3.update_traces(fillcolor="rgba(37,99,235,0.12)", line_width=2)
        st.plotly_chart(fig3, use_container_width=True)

    # Compliance breakdown
    st.markdown("#### Compliance summary")
    comp_counts = df["Compliance"].value_counts().reset_index()
    comp_counts.columns = ["Status", "Trips"]
    color_map = {"Good": "#16a34a", "Monitor": "#d97706", "Over Limit": "#dc2626", "N/A": "#9ca3af"}
    fig4 = px.bar(
        comp_counts, x="Status", y="Trips",
        title="Trips by compliance status",
        color="Status",
        color_discrete_map=color_map,
        text_auto=True,
    )
    fig4.update_layout(**PLOTLY_LAYOUT, showlegend=False, title_font_size=13,
                       xaxis_title="", yaxis_title="Number of trips")
    st.plotly_chart(fig4, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# MODULE 2 — POLLUTANT ENGINE
# ══════════════════════════════════════════════════════════════
elif selected_module == "Pollutant Engine":
    st.title("☁️ Pollutant Engine")
    st.markdown(
        f'<div class="info-card">Methodology: <strong>{methodology}</strong>. '
        "CO₂ uses IPCC Tier 2 stoichiometric factors; NOx and PM use COPERT V speed-band hot-emission "
        "functions. All figures include cold-start and idle corrections. "
        "Electric buses show Scope 2 only (Nigeria grid: 0.46 kg CO₂e/kWh).</div>",
        unsafe_allow_html=True,
    )

    # KPI row
    pol_cols = st.columns(len(target_pollutants))
    for i, pol in enumerate(target_pollutants):
        col_name = f"{pol}_kg"
        total = df[col_name].sum() if col_name in df else 0
        pol_cols[i].metric(f"Total {pol}", fmt_kg(total))

    st.markdown("---")

    col_l, col_r = st.columns(2)

    with col_l:
        # Grouped bar by operator
        agg_cols = [f"{p}_kg" for p in target_pollutants if f"{p}_kg" in df]
        op_pol = df.groupby("Operator")[agg_cols].sum().reset_index()
        op_pol_melted = op_pol.melt(id_vars="Operator", var_name="Pollutant", value_name="kg")
        op_pol_melted["Pollutant"] = op_pol_melted["Pollutant"].str.replace("_kg", "")
        fig = px.bar(
            op_pol_melted, x="Operator", y="kg", color="Pollutant", barmode="group",
            title="Pollutant volume by operator",
            color_discrete_sequence=MULTI_PALETTE,
        )
        fig.update_layout(**PLOTLY_LAYOUT, title_font_size=13,
                          xaxis_title="", yaxis_title="kg")
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        # Scatter: speed vs NOx g/pkm
        if "NOx" in target_pollutants and "NOx_g_pkm" in df:
            fig2 = px.scatter(
                df, x="Avg_Speed_kmh", y="NOx_g_pkm",
                color="Bus_Category", size="Ridership",
                color_discrete_sequence=MULTI_PALETTE,
                title="Speed vs NOx intensity (g/pkm)",
                labels={"Avg_Speed_kmh": "Avg speed (km/h)", "NOx_g_pkm": "NOx g/pkm"},
            )
            fig2.update_layout(**PLOTLY_LAYOUT, title_font_size=13)
            st.plotly_chart(fig2, use_container_width=True)
        elif "CO2" in target_pollutants and "CO2_g_pkm" in df:
            fig2 = px.scatter(
                df, x="Avg_Speed_kmh", y="CO2_g_pkm",
                color="Bus_Category", size="Ridership",
                color_discrete_sequence=MULTI_PALETTE,
                title="Speed vs CO₂ intensity (g/pkm)",
                labels={"Avg_Speed_kmh": "Avg speed (km/h)", "CO2_g_pkm": "CO₂ g/pkm"},
            )
            fig2.update_layout(**PLOTLY_LAYOUT, title_font_size=13)
            st.plotly_chart(fig2, use_container_width=True)

    # Per fuel type breakdown
    fuel_agg = df.groupby("Fuel_Type")[agg_cols].sum().reset_index()
    fuel_melted = fuel_agg.melt(id_vars="Fuel_Type", var_name="Pollutant", value_name="kg")
    fuel_melted["Pollutant"] = fuel_melted["Pollutant"].str.replace("_kg", "")
    fig3 = px.bar(
        fuel_melted, x="Fuel_Type", y="kg", color="Pollutant", barmode="stack",
        title="Pollutant volume by fuel type",
        color_discrete_sequence=MULTI_PALETTE,
    )
    fig3.update_layout(**PLOTLY_LAYOUT, title_font_size=13,
                       xaxis_title="", yaxis_title="kg")
    st.plotly_chart(fig3, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# MODULE 3 — BUS EFFICIENCY
# ══════════════════════════════════════════════════════════════
elif selected_module == "Bus Efficiency":
    st.title("🚍 Bus Efficiency")
    st.markdown(
        '<div class="info-card">Efficiency measured as CO₂ grams per passenger-kilometre (g CO₂/pkm) — '
        "the standard metric for transit carbon performance. Lower is better. "
        "Compliance thresholds: High Capacity ≤30 g/pkm Good, ≤55 Monitor; "
        "Midi ≤45 Good, ≤75 Monitor; Mini ≤60 Good, ≤95 Monitor.</div>",
        unsafe_allow_html=True,
    )

    if "CO2" not in target_pollutants:
        st.warning("Enable CO₂ in the sidebar to see efficiency metrics.")
        st.stop()

    rev_df = df[df["Revenue_Trip"] == True].copy()

    eff_summary = (
        rev_df.groupby(["Bus_Category", "Fuel_Type"])
        .agg(
            Avg_CO2_g_pkm=("CO2_g_pkm", "mean"),
            Total_CO2_kg=("CO2_kg", "sum"),
            Total_Trips=("Bus_ID", "count"),
            Total_Passengers=("Ridership", "sum"),
        )
        .reset_index()
        .sort_values("Avg_CO2_g_pkm")
        .round(2)
    )
    eff_summary["Compliance"] = eff_summary.apply(
        lambda r: compliance_flag(r["Avg_CO2_g_pkm"], r["Bus_Category"]), axis=1
    )

    col_l, col_r = st.columns([2, 1])
    with col_l:
        fig = px.bar(
            eff_summary, x="Bus_Category", y="Avg_CO2_g_pkm", color="Fuel_Type",
            barmode="group",
            title="Average CO₂ per passenger-km by category and fuel",
            color_discrete_sequence=MULTI_PALETTE,
            text=eff_summary["Avg_CO2_g_pkm"].round(1).astype(str) + " g",
        )
        fig.update_layout(**PLOTLY_LAYOUT, title_font_size=13,
                          xaxis_title="", yaxis_title="g CO₂/pkm")
        fig.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        # Styled compliance table
        def style_compliance(val):
            if val == "Good":
                return '<span class="badge-good">Good</span>'
            if val == "Monitor":
                return '<span class="badge-monitor">Monitor</span>'
            if val == "Over Limit":
                return '<span class="badge-over">Over Limit</span>'
            return val

        display = eff_summary[["Bus_Category", "Fuel_Type", "Avg_CO2_g_pkm", "Compliance"]].copy()
        display["Status"] = display["Compliance"].apply(style_compliance)
        st.markdown(
            display[["Bus_Category", "Fuel_Type", "Avg_CO2_g_pkm", "Status"]]
            .rename(columns={"Bus_Category": "Category", "Fuel_Type": "Fuel", "Avg_CO2_g_pkm": "g/pkm"})
            .to_html(escape=False, index=False),
            unsafe_allow_html=True,
        )

    # Load factor vs efficiency scatter
    st.markdown("---")
    fig2 = px.scatter(
        rev_df, x="load_factor", y="CO2_g_pkm",
        color="Bus_Category", size="Route_Distance_km",
        color_discrete_sequence=MULTI_PALETTE,
        title="Load factor vs CO₂ intensity — more passengers = lower g/pkm",
        labels={"load_factor": "Load factor (actual ÷ capacity)", "CO2_g_pkm": "CO₂ g/pkm"},
    )
    fig2.update_layout(**PLOTLY_LAYOUT, title_font_size=13)
    st.plotly_chart(fig2, use_container_width=True)

    # Reduction tips
    worst = eff_summary[eff_summary["Compliance"] == "Over Limit"]
    if not worst.empty:
        st.markdown("#### Suggested actions for over-limit vehicles")
        for _, row_w in worst.iterrows():
            st.markdown(
                f'<div class="tip-card">🔴 <strong>{row_w["Bus_Category"]} / {row_w["Fuel_Type"]}</strong> '
                f'averaging <strong>{row_w["Avg_CO2_g_pkm"]:.1f} g/pkm</strong>. '
                "Consider increasing ridership via dynamic scheduling, reducing terminal idle time, "
                "or scheduling for route pre-cooling to cut A/C load.</div>",
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════
# MODULE 4 — TRIP INSPECTOR
# ══════════════════════════════════════════════════════════════
elif selected_module == "Trip Inspector":
    st.title("🔬 Trip Inspector")
    st.markdown(
        '<div class="info-card">Select a single trip to see a full breakdown of where '
        "its CO₂ comes from: hot running, cold start penalty, idling at terminals, and A/C load.</div>",
        unsafe_allow_html=True,
    )

    bus_ids = df["Bus_ID"].unique().tolist()
    selected_bus = st.selectbox("Select Bus ID", bus_ids)
    bus_trips = df[df["Bus_ID"] == selected_bus].reset_index(drop=True)

    trip_labels = [
        f"{i}: {row['Date']} · {row['Route_Name']} · {row['Route_Distance_km']} km"
        for i, (_, row) in enumerate(bus_trips.iterrows())
    ]
    selected_trip_idx = st.selectbox("Select trip", range(len(trip_labels)), format_func=lambda i: trip_labels[i])
    trip_row = bus_trips.iloc[selected_trip_idx]

    breakdown = emission_breakdown(trip_row, methodology)

    st.markdown("---")
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Bus category",   trip_row["Bus_Category"])
    t2.metric("Fuel type",      trip_row["Fuel_Type"])
    t3.metric("Distance",       f"{trip_row['Route_Distance_km']} km")
    t4.metric("Ridership",      f"{trip_row['Ridership']}")

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### CO₂ source breakdown")

        labels  = ["Hot running", "Cold start", "Idling", "A/C load", "Grid (electric)"]
        raw_g   = [
            breakdown["hot_running"], breakdown["cold_start"],
            breakdown["idling"], breakdown["ac_load"], breakdown["grid_electric"],
        ]
        colors  = ["#2563eb", "#f59e0b", "#ef4444", "#10b981", "#8b5cf6"]
        total_g = max(breakdown["total_g"], 1)

        for lbl, grams, color in zip(labels, raw_g, colors):
            pct = grams / total_g * 100
            st.markdown(
                f"""<div class="breakdown-row">
                    <div class="breakdown-label">{lbl}</div>
                    <div class="breakdown-bar-bg">
                        <div class="breakdown-bar-fill"
                             style="width:{min(pct, 100):.1f}%;background:{color};"></div>
                    </div>
                    <div class="breakdown-val">{grams/1000:.3f} kg</div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<div style="margin-top:14px;padding:12px 16px;background:#f4f7ff;'
            f'border-radius:10px;border:1px solid #dde5f5;">'
            f'<span style="font-size:12px;color:#6c7a99;">Total CO₂ this trip</span><br>'
            f'<span style="font-size:24px;font-weight:700;color:#111827;">'
            f'{breakdown["total_g"]/1000:.3f} kg</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_r:
        # Donut chart
        non_zero = [(l, g, c) for l, g, c in zip(labels, raw_g, colors) if g > 0]
        if non_zero:
            nz_labels, nz_vals, nz_colors = zip(*non_zero)
            fig = go.Figure(go.Pie(
                labels=nz_labels, values=nz_vals,
                hole=0.56, marker_colors=nz_colors,
                textinfo="percent", textfont_size=11,
            ))
            fig.update_layout(
                **PLOTLY_LAYOUT,
                showlegend=True,
                title="Emission source split",
                title_font_size=13,
                legend=dict(orientation="v", x=1, y=0.5),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Compliance flag for this trip
        if "CO2" in target_pollutants:
            co2_gpkm = trip_row.get("CO2_g_pkm", 0)
            flag = compliance_flag(co2_gpkm, trip_row["Bus_Category"])
            badge_class = {"Good": "badge-good", "Monitor": "badge-monitor", "Over Limit": "badge-over"}.get(flag, "")
            st.markdown(
                f'<div style="margin-top:12px;">'
                f'<div style="font-size:12px;color:#6c7a99;margin-bottom:6px;">Compliance status</div>'
                f'<span class="{badge_class}" style="font-size:14px;">{flag}</span> &nbsp;'
                f'<span style="font-size:13px;color:#374151;">{co2_gpkm:.1f} g CO₂/pkm</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Reduction potential
    st.markdown("---")
    st.markdown("#### Reduction potential for this trip")
    idle_saved   = breakdown["idling"] * 0.5 / 1000    # halve idle time
    ac_saved     = breakdown["ac_load"] * 0.3 / 1000   # pre-cooling saves 30%
    total_saving = idle_saved + ac_saved
    c1, c2, c3 = st.columns(3)
    c1.metric("Cut idling by 50%",      f"−{idle_saved:.3f} kg CO₂")
    c2.metric("Pre-cool at depot (A/C)", f"−{ac_saved:.3f} kg CO₂")
    c3.metric("Combined saving",         f"−{total_saving:.3f} kg CO₂",
              delta=f"{total_saving / (breakdown['total_g']/1000) * 100:.0f}% reduction",
              delta_color="normal")


# ══════════════════════════════════════════════════════════════
# MODULE 5 — DEEP SEARCH
# ══════════════════════════════════════════════════════════════
elif selected_module == "Deep Search":
    st.title("🔍 Deep Search")
    st.markdown(
        '<div class="info-card">Filter, explore, and export the full calculated manifest. '
        "All emission columns reflect the methodology and pollutants selected in the sidebar.</div>",
        unsafe_allow_html=True,
    )

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        min_d, max_d = df["Date"].min(), df["Date"].max()
        date_range = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
    with f2:
        operators = st.multiselect("Operator", options=sorted(df["Operator"].unique()))
    with f3:
        categories = st.multiselect("Bus category", options=sorted(df["Bus_Category"].unique()))
    with f4:
        bus_search = st.text_input("Bus ID search", placeholder="e.g. HC-001")

    filt = df.copy()
    if len(date_range) == 2:
        filt = filt[(filt["Date"] >= date_range[0]) & (filt["Date"] <= date_range[1])]
    if operators:
        filt = filt[filt["Operator"].isin(operators)]
    if categories:
        filt = filt[filt["Bus_Category"].isin(categories)]
    if bus_search:
        filt = filt[filt["Bus_ID"].str.contains(bus_search, case=False, na=False)]

    st.markdown(f"**{len(filt):,} records matched**")

    DISPLAY_COLS = [
        "Date", "Bus_ID", "Route_Name", "Operator", "Bus_Category", "Fuel_Type",
        "Route_Distance_km", "Avg_Speed_kmh", "Ridership", "load_factor",
        "CO2_kg", "NOx_kg", "PM_kg", "CO2_g_pkm", "Compliance",
    ]
    display_cols = [c for c in DISPLAY_COLS if c in filt.columns]

    st.dataframe(
        filt[display_cols].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        column_config={
            "CO2_kg":      st.column_config.NumberColumn("CO₂ (kg)",    format="%.3f"),
            "NOx_kg":      st.column_config.NumberColumn("NOx (kg)",    format="%.4f"),
            "PM_kg":       st.column_config.NumberColumn("PM (kg)",     format="%.5f"),
            "CO2_g_pkm":   st.column_config.NumberColumn("CO₂ g/pkm",  format="%.1f"),
            "load_factor": st.column_config.ProgressColumn("Load factor", min_value=0, max_value=1, format="%.2f"),
            "Compliance":  st.column_config.TextColumn("Status"),
        },
    )

    csv_data = filt[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇ Download filtered results as CSV",
        data=csv_data,
        file_name="lamata_emissions_export.csv",
        mime="text/csv",
    )
