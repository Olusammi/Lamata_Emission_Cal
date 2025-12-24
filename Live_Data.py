import streamlit as st
import pandas as pd
import numpy as np
import base64
import io

# --- CONFIGURATION ---
# Replace with your NEW OneDrive link for the .parquet file
ONEDRIVE_PARQUET_LINK = "https://lamatang-my.sharepoint.com/:u:/g/personal/shassan_lamata-ng_com/IQAD9TAa_S16RYQ5nBiopzHyAX8BnYrKjhMdZaf3TE2b4qI?e=PIFVQR"

st.set_page_config(page_title="LAMATA High-Volume Ops", layout="wide")

def get_onedrive_direct(sharing_url):
    """Encodes the link for direct API access"""
    try:
        encoded = base64.b64encode(bytes(sharing_url, 'utf-8'))
        encoded_str = encoded.decode('utf-8').replace('/','_').replace('+','-').rstrip("=")
        return f"https://api.onedrive.com/v1.0/shares/u!{encoded_str}/root/content"
    except: return None

@st.cache_data(ttl=3600)
def load_data(link):
    """Streams Parquet data which is much lighter than CSV"""
    direct_url = get_onedrive_direct(link)
    # Using engine='fastparquet' or 'pyarrow'
    df = pd.read_parquet(direct_url)
    
    # 1. Clean Bus IDs (Logic from trip_count.py)
    df['busID'] = df['busID'].astype(str).str.replace(r'^(FM|PM|C|F|G)(\d+.*)', r'0\2', regex=True)
    
    # 2. Date Formatting (Logic from Combined_Summary.py)
    df['transDate_NG'] = pd.to_datetime(df['transDate_NG'])
    df['date'] = df['transDate_NG'].dt.date
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    return df

# --- DASHBOARD UI ---
st.title("🚌 LAMATA Master Analytics (High-Volume)")

if ONEDRIVE_PARQUET_LINK == "PASTE_YOUR_PARQUET_LINK_HERE":
    st.info("Please convert your 600MB CSV to Parquet and paste the link to avoid memory crashes.")
    st.stop()

df = load_data(ONEDRIVE_PARQUET_LINK)

# --- MULTI-METRIC SUMMARY ---
m1, m2, m3 = st.columns(3)
m1.metric("Total Ridership", f"{len(df):,}") # Summary logic
m2.metric("Total Revenue", f"₦{df['amount'].sum():,.2f}") # Summary logic
m3.metric("Buses Active", df['busID'].nunique()) # Summary logic

tab1, tab2 = st.tabs(["Route Performance", "Trip Calculations"])

with tab1:
    # Aggregation from Combined_Summary.py
    st.subheader("Revenue & Ridership Summary")
    summary = df.groupby(['issuerName', 'routeName', 'date']).agg({
        'amount': 'sum',
        'id': 'size',
        'busID': 'nunique'
    }).reset_index()
    summary.columns = ['Operator', 'Route', 'Date', 'Revenue', 'Ridership', 'Buses']
    st.dataframe(summary, use_container_width=True)

with tab2:
    # Trip Count Logic from trip_count.py
    st.subheader("Calculated Trips (Capacity Based)")
    # Defaulting to HC (55) for general view, but you can apply the full mapping
    bus_summary = df.groupby(['busID', 'date']).size().reset_index(name='ridership')
    bus_summary['est_trips'] = (bus_summary['ridership'] / 55).round(2) 
    st.dataframe(bus_summary.sort_values(by='ridership', ascending=False), use_container_width=True)
