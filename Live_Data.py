import streamlit as st
import pandas as pd
import base64

# This link is from your "Anyone with link" share
ONEDRIVE_LINK = "PASTE_YOUR_LINK_HERE"

def get_onedrive_direct(sharing_url):
    """Encodes the OneDrive link for direct pandas reading"""
    encoded = base64.b64encode(bytes(sharing_url, 'utf-8'))
    encoded_str = encoded.decode('utf-8').replace('/','_').replace('+','-').rstrip("=")
    return f"https://api.onedrive.com/v1.0/shares/u!{encoded_str}/root/content"

@st.cache_data(ttl=3600)
def load_large_data():
    direct_url = get_onedrive_direct(ONEDRIVE_LINK)
    # Pandas can read large files directly from a URL stream
    return pd.read_csv(direct_url, low_memory=False)

st.title("🚌 LAMATA Master Cloud Dashboard")
if st.button("Sync Data"):
    df = load_large_data()
    st.write(f"📊 Loaded {len(df):,} rows from the cloud.")
    # Add your trip_count.py analysis here
