import streamlit as st
import pandas as pd
import numpy as np
import base64
import requests  # <--- THIS WAS MISSING
import io
import pytz

# --- CONFIGURATION ---
ONEDRIVE_PARQUET_LINK = "https://lamatang-my.sharepoint.com/:u:/g/personal/shassan_lamata-ng_com/IQAD9TAa_S16RYQ5nBiopzHyAX8BnYrKjhMdZaf3TE2b4qI?e=PIFVQR"

st.set_page_config(page_title="LAMATA Master Analytics", layout="wide")

def get_onedrive_direct(sharing_url):
    try:
        encoded = base64.b64encode(bytes(sharing_url, 'utf-8'))
        encoded_str = encoded.decode('utf-8').replace('/','_').replace('+','-').rstrip("=")
        return f"https://api.onedrive.com/v1.0/shares/u!{encoded_str}/root/content"
    except: return None

@st.cache_data(ttl=3600)
def load_data(link):
    direct_url = get_onedrive_direct(link)
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    with st.spinner("Streaming & Optimizing 600MB File..."):
        response = requests.get(direct_url, headers=headers, stream=True)
        response.raise_for_status()
        
        # Load into memory buffer
        f = io.BytesIO(response.content)
        
        # OPTIMIZATION: Only load necessary columns to save RAM 
        # This prevents the 600MB file from becoming 3GB in memory
        needed_cols = ['issuerName', 'routeName', 'transDate_NG', 'amount', 'busID', 'id']
        df = pd.read_parquet(f, columns=needed_cols, engine='pyarrow')
    
    # Logic from trip_count.py: Clean Bus IDs
    df['busID'] = df['busID'].astype(str).str.replace(r'^(FM|PM|C|F|G)(\d+.*)', r'0\2', regex=True)
    
    # Logic from Combined_Summary.py: Date formatting
    df['transDate_NG'] = pd.to_datetime(df['transDate_NG'])
    df['date'] = df['transDate_NG'].dt.date
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    
    return df

# --- MAIN APP ---
st.title("🚌 LAMATA Unified Operations Dashboard")

if ONEDRIVE_PARQUET_LINK != "PASTE_YOUR_PARQUET_LINK_HERE":
    df = load_data(ONEDRIVE_PARQUET_LINK)

    # Multi-Metric Summary (Logic from your py files)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Ridership", f"{len(df):,}")
    m2.metric("Total Revenue", f"₦{df['amount'].sum():,.2f}")
    m3.metric("Buses Active", f"{df['busID'].nunique()}")

    tab1, tab2 = st.tabs(["Performance", "Trip Analytics"])
    
    with tab1:
        # Combined_Summary logic
        summary = df.groupby(['issuerName', 'routeName', 'date']).agg({
            'amount': 'sum', 'id': 'count'
        }).reset_index()
        st.dataframe(summary, use_container_width=True)

    with tab2:
        # trip_count logic
        bus_trips = df.groupby(['busID', 'date']).size().reset_index(name='trips')
        st.dataframe(bus_trips, use_container_width=True)
else:
    st.info("Please enter your OneDrive Parquet link.")
