import streamlit as st
import pandas as pd
import plotly.express as px
from emissions_engine import calculate_fleet_emissions

st.set_page_config(page_title="LAMATA Advanced Emissions Engine", layout="wide")

st.title("🚍 LAMATA Advanced Emissions & Operational Engine")
st.markdown("Enterprise-grade analytical framework evaluating transit efficiency, operator profiles, and climate impacts.")

# --- SIDEBAR CONTROL MODULES ---
st.sidebar.header("🛠️ Configuration Modules")

# Module 1: Framework Controls
with st.sidebar.expander("1. Methodology Framework", expanded=True):
    methodology = st.selectbox(
        "Select Standard Factor Set",
        ["Hybrid", "COPERT", "IPCC"],
        help="IPCC is fuel-focused. COPERT adds precise speed curves. Hybrid pairs stable accounting with local speed metrics."
    )

# Module 2: Pollutant Target Matrix
with st.sidebar.expander("2. Pollutant Profiling", expanded=True):
    target_pollutants = st.multiselect(
        "Active Inventory Targets",
        ["CO2", "NOx", "PM"],
        default=["CO2", "NOx"]
    )

# Module 3: UI Visual Rendering Controls
with st.sidebar.expander("3. Reporting & Visualization", expanded=True):
    viz_type = st.selectbox(
        "Display Mode",
        ["Bar Chart", "Pie Chart", "Line Representation", "Granular Table Summary"]
    )
    metric_pollutant = st.selectbox(
        "Primary Chart Metric Target",
        target_pollutants if target_pollutants else ["CO2"]
    )

# --- CORE LOGIC WORKFLOW ---
uploaded_file = st.file_uploader("Upload Daily Operational Manifest (CSV)", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    required_cols = ['Route_Name', 'Bus_ID', 'Operator', 'Bus_Category', 'Fuel_Type', 'Route_Distance_km', 'Avg_Speed_kmh', 'Ridership', 'Revenue_Trip']
    if not all(col in df.columns for col in required_cols):
        st.error(f"Missing data criteria. Ensure columns match: {', '.join(required_cols)}")
    elif not target_pollutants:
        st.warning("Please select at least one target pollutant from the configuration sidebar.")
    else:
        # Compute multi-pollutant emission values
        calc_results = df.apply(lambda row: calculate_fleet_emissions(row, methodology, target_pollutants), axis=1)
        df = pd.concat([df, calc_results], axis=1)
        
        # Top Executive Information Tiles
        st.subheader(f"System Summary Profile ({methodology} Framework)")
        m1, m2, m3 = st.columns(3)
        
        if "CO2" in target_pollutants:
            m1.metric("Total CO₂ Output", f"{df['CO2_Total_kg'].sum():,.1f} kg")
        else:
            m1.metric("Total CO₂ Output", "Disabled")
            
        if "NOx" in target_pollutants:
            m2.metric("Total NOx Output", f"{df['NOx_Total_kg'].sum():,.2f} kg")
        else:
            m2.metric("Total NOx Output", "Disabled")
            
        if "PM" in target_pollutants:
            m3.metric("Total Particulate Matter", f"{df['PM_Total_kg'].sum():,.3f} kg")
        else:
            m3.metric("Total Particulate Matter", "Disabled")
            
        st.divider()
        
        # Consolidated Aggregation States
        op_summary = df.groupby('Operator').agg({
            'Bus_ID': 'count',
            f'{metric_pollutant}_Total_kg': 'sum',
            f'{metric_pollutant}_per_Passenger_g': 'mean'
        }).reset_index().rename(columns={'Bus_ID': 'Active_Fleet_Units'})
        
        # Dynamic View Render Logic Block
        st.subheader(f"Analysis Workspace: {metric_pollutant} Metrics by Operator")
        
        if viz_type == "Granular Table Summary":
            st.dataframe(op_summary, use_container_width=True)
            
        elif viz_type == "Bar Chart":
            fig = px.bar(
                op_summary, 
                x='Operator', 
                y=f'{metric_pollutant}_Total_kg', 
                title=f"Total Gross {metric_pollutant} Volume by Operator (kg)",
                text_auto='.2f'
            )
            st.plotly_chart(fig, use_container_width=True)
            
        elif viz_type == "Pie Chart":
            fig = px.pie(
                op_summary, 
                values=f'{metric_pollutant}_Total_kg', 
                names='Operator', 
                title=f"System Share Share: Gross Gross {metric_pollutant} Footprint"
            )
            st.plotly_chart(fig, use_container_width=True)
            
        elif viz_type == "Line Representation":
            # Showing efficiency profiles across different routes
            route_summary = df.groupby(['Route_Name', 'Operator'])[f'{metric_pollutant}_per_Passenger_g'].mean().reset_index()
            fig = px.line(
                route_summary, 
                x='Route_Name', 
                y=f'{metric_pollutant}_per_Passenger_g', 
                color='Operator',
                markers=True,
                title=f"Passenger Carbon Intensity Curve (g {metric_pollutant} / Passenger-km)"
            )
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Awaiting analytical data drop. Please verify your source CSV contains: Route_Name, Bus_ID, Operator, Bus_Category, Fuel_Type, Route_Distance_km, Avg_Speed_kmh, Ridership, Revenue_Trip")
