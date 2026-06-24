import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu
from emissions_engine import calculate_row

# ==========================================
# 1. PAGE CONFIG & STYLING
# ==========================================
st.set_page_config(page_title="LAMATA Emissions Portal", page_icon="🚍", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    div[data-testid="stSidebarNav"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR NAVIGATION
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Lagos_Metropolitan_Area_Transport_Authority_logo.png/600px-Lagos_Metropolitan_Area_Transport_Authority_logo.png", width=150)
    st.markdown("### Emissions Portal")
    
    selected_module = option_menu(
        menu_title=None,
        options=["Dashboard", "Pollutant Engine", "Bus Efficiency", "Advanced Search"],
        icons=["grid-1x2", "cloud-haze2", "bus-front", "search"],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#0056b3", "font-size": "18px"},
            "nav-link": {"font-size": "15px", "text-align": "left", "margin": "5px", "--hover-color": "#e9ecef"},
            "nav-link-selected": {"background-color": "#0056b3", "color": "white", "icon-color": "white"},
        }
    )

# ==========================================
# 3. DATA UPLOAD & PROCESSING
# ==========================================
expected_cols = ['Date', 'Route_Name', 'Bus_ID', 'Operator', 'Bus_Category', 'Fuel_Type', 'Route_Distance_km', 'Avg_Speed_kmh', 'Ridership', 'Revenue_Trip']

uploaded_file = st.sidebar.file_uploader("Upload Manifest (CSV)", type=["csv"])

if not uploaded_file:
    st.info("👋 Upload a CSV in the sidebar to activate the portal modules. Ensure it includes a 'Date' column!")
    st.stop()

df = pd.read_csv(uploaded_file)
if 'Date' in df.columns:
    df['Date'] = pd.to_datetime(df['Date']).dt.date

if not all(col in df.columns for col in expected_cols):
    st.error(f"Missing columns! Ensure your CSV has: {', '.join(expected_cols)}")
    st.stop()

# ==========================================
# 4. MODULE VIEWS
# ==========================================

# --- MODULE 1: DASHBOARD ---
if selected_module == "Dashboard":
    st.title("📊 System Dashboard")
    st.markdown("High-level operational overview based on standard Hybrid methodology.")
    
    df_dash = df.copy()
    dash_calc = df_dash.apply(lambda row: calculate_row(row, "Hybrid", ["CO2", "NOx"]), axis=1)
    df_dash = pd.concat([df_dash, dash_calc], axis=1)
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Trips", f"{len(df_dash):,}")
    m2.metric("Total Passengers", f"{df_dash['Ridership'].sum():,}")
    m3.metric("Total CO₂ (kg)", f"{df_dash['CO2_kg'].sum():,.0f}")
    m4.metric("Avg Fleet Efficiency", f"{df_dash['CO2_g_pkm'].mean():,.1f} g/pkm")
    
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        fig1 = px.pie(df_dash, values='CO2_kg', names='Operator', title="CO₂ Share by Operator", hole=0.4)
        st.plotly_chart(fig1, use_container_width=True)
    with col2:
        fig2 = px.bar(df_dash.groupby('Bus_Category')['Ridership'].sum().reset_index(), x='Bus_Category', y='Ridership', title="Ridership by Bus Category")
        st.plotly_chart(fig2, use_container_width=True)

# --- MODULE 2: POLLUTANT ENGINE ---
elif selected_module == "Pollutant Engine":
    st.title("☁️ Advanced Pollutant Engine")
    
    c1, c2 = st.columns([1, 2])
    with c1:
        methodology = st.selectbox("Methodology", ["Hybrid", "COPERT", "IPCC"])
    with c2:
        target_pollutants = st.multiselect("Pollutants to Track", ["CO2", "NOx", "PM"], default=["CO2", "NOx"])
        
    if not target_pollutants:
        st.warning("Select a pollutant.")
        st.stop()
        
    df_pol = df.copy()
    results = df_pol.apply(lambda row: calculate_row(row, methodology, target_pollutants), axis=1)
    df_pol = pd.concat([df_pol, results], axis=1)
    
    st.subheader("Gross Pollutant Volume (kg)")
    cols = st.columns(len(target_pollutants))
    for i, pol in enumerate(target_pollutants):
        cols[i].metric(f"{pol} Total", f"{df_pol[f'{pol}_kg'].sum():,.2f} kg")
        
    fig = px.bar(df_pol.groupby('Operator')[[f'{p}_kg' for p in target_pollutants]].sum().reset_index(), 
                 x='Operator', y=[f'{p}_kg' for p in target_pollutants], barmode='group', title="Pollutants by Operator")
    st.plotly_chart(fig, use_container_width=True)

# --- MODULE 3: BUS EFFICIENCY ---
elif selected_module == "Bus Efficiency":
    st.title("🚍 Per-Bus Efficiency (g/pkm)")
    st.markdown("Analyzing how effectively different bus types transport passengers (Hybrid model).")
    
    df_eff = df.copy()
    eff_res = df_eff.apply(lambda row: calculate_row(row, "Hybrid", ["CO2"]), axis=1)
    df_eff = pd.concat([df_eff, eff_res], axis=1)
    
    eff_summary = df_eff.groupby(['Bus_Category', 'Fuel_Type']).agg(
        Avg_CO2_g_pkm=('CO2_g_pkm', 'mean'),
        Total_Trips=('Bus_ID', 'count')
    ).reset_index().sort_values('Avg_CO2_g_pkm')
    
    col1, col2 = st.columns([2, 1])
    with col1:
        fig = px.bar(eff_summary, x='Bus_Category', y='Avg_CO2_g_pkm', color='Fuel_Type', barmode='group', 
                     title="Average CO₂ per Passenger-km by Category", color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.dataframe(eff_summary, use_container_width=True, hide_index=True)

# --- MODULE 4: ADVANCED SEARCH ---
elif selected_module == "Advanced Search":
    st.title("🔍 Deep Dive & Records Search")
    
    df_search = df.copy()
    search_res = df_search.apply(lambda row: calculate_row(row, "Hybrid", ["CO2", "NOx", "PM"]), axis=1)
    df_search = pd.concat([df_search, search_res], axis=1)
    
    f1, f2, f3 = st.columns(3)
    with f1:
        min_date, max_date = df_search['Date'].min(), df_search['Date'].max()
        date_range = st.date_input("Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    with f2:
        operators = st.multiselect("Filter Operator", options=df_search['Operator'].unique())
    with f3:
        bus_search = st.text_input("Search by Bus ID (e.g. HC-001)")
        
    filtered_df = df_search.copy()
    if len(date_range) == 2:
        filtered_df = filtered_df[(filtered_df['Date'] >= date_range[0]) & (filtered_df['Date'] <= date_range[1])]
    if operators:
        filtered_df = filtered_df[filtered_df['Operator'].isin(operators)]
    if bus_search:
        filtered_df = filtered_df[filtered_df['Bus_ID'].str.contains(bus_search, case=False, na=False)]
        
    st.markdown(f"**Found {len(filtered_df)} matching records.**")
    
    display_cols = ['Date', 'Bus_ID', 'Operator', 'Bus_Category', 'Fuel_Type', 'Route_Distance_km', 'Ridership', 'CO2_kg', 'NOx_kg']
    st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)
