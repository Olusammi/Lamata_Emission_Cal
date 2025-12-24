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
    direct_url = get_onedrive_direct(link)
    
    # Custom headers to make the request look like a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    with st.spinner("Streaming large data file from cloud..."):
        # Stream the content to avoid connection timeouts
        response = requests.get(direct_url, headers=headers, stream=True)
        response.raise_for_status()
        
        # Wrap the content in a BytesIO buffer so Pandas can read it as a file
        f = io.BytesIO(response.content)
        df = pd.read_parquet(f, engine='pyarrow') # 'pyarrow' is faster for large files
    
    # Process using your existing cleaning logic
    df['busID'] = df['busID'].astype(str).str.replace(r'^(FM|PM|C|F|G)(\d+.*)', r'0\2', regex=True)
    df['transDate_NG'] = pd.to_datetime(df['transDate_NG'])
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

