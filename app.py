import streamlit as st
import pandas as pd
import plotly.express as px
from emissions_engine import calculate_row_emissions

st.set_page_config(page_title="Fleet Emission Tracker", layout="wide")

st.title("🚍 Fleet Emissions & Efficiency Tracker")
st.markdown("Upload the daily route manifest to calculate total greenhouse gas output and passenger efficiency.")

uploaded_file = st.file_uploader("Upload Route Data (CSV)", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    required_cols = ['Route_Name', 'Bus_ID', 'Operator', 'Bus_Category', 'Fuel_Type', 'Route_Distance_km', 'Ridership', 'Revenue_Trip']
    if not all(col in df.columns for col in required_cols):
        st.error(f"Missing required columns. Please ensure your CSV has: {', '.join(required_cols)}")
    else:
        df[['Total_CO2_kg', 'CO2_per_Passenger_g']] = df.apply(calculate_row_emissions, axis=1)
        
        total_emissions = df['Total_CO2_kg'].sum()
        avg_efficiency = df[df['Revenue_Trip'] == True]['CO2_per_Passenger_g'].mean()
        total_passengers = df['Ridership'].sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Fleet Emissions (kg CO2)", f"{total_emissions:,.2f}")
        col2.metric("Fleet Average Efficiency", f"{avg_efficiency:.1f} g/pkm")
        col3.metric("Total Passengers Moved", f"{total_passengers:,}")
        
        st.divider()
        
        st.subheader("Operator Efficiency Scorecard")
        
        op_summary = df.groupby('Operator').agg(
            Total_Trips=('Bus_ID', 'count'),
            Total_Emissions_kg=('Total_CO2_kg', 'sum'),
            Avg_Efficiency_g_pkm=('CO2_per_Passenger_g', 'mean')
        ).reset_index().sort_values('Avg_Efficiency_g_pkm')
        
        st.dataframe(op_summary, use_container_width=True)
        
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            fig1 = px.bar(op_summary, x='Operator', y='Total_Emissions_kg', title="Total Emissions by Operator")
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            fig2 = px.bar(op_summary, x='Operator', y='Avg_Efficiency_g_pkm', title="Average CO2 per Passenger", color='Avg_Efficiency_g_pkm', color_continuous_scale='Viridis_r')
            st.plotly_chart(fig2, use_container_width=True)

else:
    st.info("Awaiting CSV upload. Expected columns: Route_Name, Bus_ID, Operator, Bus_Category, Fuel_Type, Route_Distance_km, Ridership, Revenue_Trip")