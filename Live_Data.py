import streamlit as st
import pandas as pd
import numpy as np
import base64
import pytz
import re
from datetime import datetime

# --- CONFIGURATION ---
# Replace with your OneDrive "Anyone with the link" share link
ONEDRIVE_LINK = "https://lamatang-my.sharepoint.com/:x:/g/personal/shassan_lamata-ng_com/IQCMUYI0-upfQpfXQtl4Gq-hAXfKzIaM59fTi8KRkJmOUDc?e=54882R"

st.set_page_config(page_title="LAMATA Master Dashboard", layout="wide", page_icon="🚌")

# --- CORE LOGIC FROM ATTACHED FILES ---

def get_onedrive_direct(sharing_url):
    """Encodes OneDrive link for direct download"""
    try:
        encoded = base64.b64encode(bytes(sharing_url, 'utf-8'))
        encoded_str = encoded.decode('utf-8').replace('/','_').replace('+','-').rstrip("=")
        return f"https://api.onedrive.com/v1.0/shares/u!{encoded_str}/root/content"
    except:
        return None

def clean_bus_id(bus_id_series):
    """Vectorized BusID cleaning from trip_count.py"""
    return bus_id_series.astype(str).str.replace(r'^(FM|PM|C|F|G)(\d+.*)', r'0\2', regex=True)

def get_bus_mapping():
    """Capacity mapping from trip_count.py"""
    mapping = {
        "FLM X30": 7, "FLM X30L": 10, "Midi": 40, "HC": 55
    }
    # For this script, we use a simplified version. 
    # You can expand the issuer_to_type_map here as per your original file.
    return mapping

@st.cache_data(ttl=3600)
def load_and_process_data(link):
    """Combines loading logic from Scraper/Merge with processing from Summary"""
    direct_url = get_onedrive_direct(link)
    df = pd.read_csv(direct_url, low_memory=False)
    
    # Cleaning
    df['busID'] = clean_bus_id(df['busID'])
    df['transDate_NG'] = pd.to_datetime(df['transDate_NG'])
    df['date'] = df['transDate_NG'].dt.date
    df['hour'] = df['transDate_NG'].dt.hour
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    
    return df

# --- DASHBOARD UI ---

st.title("🚌 LAMATA Unified Operations Center")
st.markdown("### Integrated Data Insight Engine")

if ONEDRIVE_LINK == "PASTE_YOUR_MERGED_CSV_LINK_HERE":
    st.warning("Please update the ONEDRIVE_LINK variable with your shared file link.")
    st.stop()

# 1. Load Master Data
df = load_and_process_data(ONEDRIVE_LINK)

# 2. Global Sidebar Filters
st.sidebar.header("Filter Controls")
all_issuers = sorted(df['issuerName'].dropna().unique())
selected_issuers = st.sidebar.multiselect("Operator (Issuer)", all_issuers, default=all_issuers[:3])

all_routes = sorted(df['routeName'].dropna().unique())
selected_routes = st.sidebar.multiselect("Route Name", all_routes)

# Apply Filters
mask = df['issuerName'].isin(selected_issuers)
if selected_routes:
    mask &= df['routeName'].isin(selected_routes)
filtered_df = df[mask]

# 3. Top Level Metrics (Summary Logic)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Ridership", f"{len(filtered_df):,}")
m2.metric("Total Revenue", f"₦{filtered_df['amount'].sum():,.2f}")
m3.metric("Unique Buses", f"{filtered_df['busID'].nunique()}")
m4.metric("Avg Fare", f"₦{filtered_df['amount'].mean():,.2f}")

# 4. Multi-Metric Tabs
tab1, tab2, tab3 = st.tabs(["📊 Performance Summary", "🛣️ Route Analysis", "🚌 Trip Efficiency"])

with tab1:
    st.subheader("Hourly Transaction Volume")
    hourly_trend = filtered_df.groupby('hour').size()
    st.line_chart(hourly_trend, color="#007bff")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top Operators by Revenue")
        op_rev = filtered_df.groupby('issuerName')['amount'].sum().sort_values(ascending=False).head(10)
        st.bar_chart(op_rev)
    with col2:
        st.subheader("Top Routes by Ridership")
        rt_rid = filtered_df.groupby('routeName').size().sort_values(ascending=False).head(10)
        st.bar_chart(rt_rid)

with tab2:
    # Logic from Combined_Summary.py
    st.subheader("Route-Level Operational Table")
    route_summary = filtered_df.groupby(['issuerName', 'routeName', 'date']).agg({
        'amount': 'sum',
        'id': 'count',
        'busID': 'nunique'
    }).reset_index()
    route_summary.columns = ['Operator', 'Route', 'Date', 'Revenue', 'Ridership', 'Unique_Buses']
    st.dataframe(route_summary, use_container_width=True)
    
    st.download_button("Export Summary to CSV", route_summary.to_csv(index=False), "route_summary.csv")

with tab3:
    # Logic from trip_count.py
    st.subheader("Bus-Level Utilization & Estimated Trips")
    capacity_map = get_bus_mapping()
    
    # Simple trip calculation based on HC (55) if type unknown
    bus_summary = filtered_df.groupby(['busID', 'routeName', 'date']).size().reset_index(name='ridership')
    bus_summary['est_trips'] = (bus_summary['ridership'] / 55).round(2) # Defaulting to HC capacity
    
    st.dataframe(bus_summary.sort_values(by='ridership', ascending=False), use_container_width=True)

st.markdown("---")
st.caption(f"Data Source: {ONEDRIVE_LINK} | System Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
