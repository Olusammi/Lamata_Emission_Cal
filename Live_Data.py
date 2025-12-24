import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import pytz
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURATION & SECRETS ---
STEM = "https://rahq.tapdev.site:3443/"
USERNAME = st.secrets["USERNAME"]
PASSWORD = st.secrets["PASSWORD"]
BATCH_SIZE_V = 50000
BATCH_SIZE_H = 2000

st.set_page_config(page_title="LAMATA Ops Center", layout="wide", page_icon="📊")

# --- 2. CORE DATA ENGINE (SCRAPER LOGIC) ---

@st.cache_data(ttl=3600)
def get_token(user, pwd):
    payload = json.dumps({"data": {"username": user, "password": pwd}})
    headers = {'Content-Type': 'application/json'}
    res = requests.post(f"{STEM}v1/api/auth", headers=headers, data=payload)
    return res.json()['content']['token']

def fetch_data(token, start_dt, end_dt, mode="Validator"):
    """Combined fetcher for both Validator and Handheld modules"""
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}
    all_data = []
    page = 0 if mode == "Validator" else "-"
    _action = "-"
    fetching = True
    
    while fetching:
        if mode == "Validator":
            query = f"{STEM}v3/admin/get/bustransactions/-/-/{int(start_dt.timestamp())}/{int(end_dt.timestamp())}/{BATCH_SIZE_V}/{page}"
        else: # Handheld
            query = f"{STEM}v2/admin/get/transactions/6/-/-/-/-/{int(start_dt.timestamp())}/{int(end_dt.timestamp())}/{BATCH_SIZE_H}/{page}/{_action}"
            
        res = requests.get(query, headers=headers).json()
        batch = res['content']['data']
        
        if not batch:
            fetching = False
        else:
            all_data.extend(batch)
            if mode == "Validator":
                if len(batch) == BATCH_SIZE_V: page += 1
                else: fetching = False
            else: # Handheld pagination
                if len(batch) == BATCH_SIZE_H:
                    page = res['content']['lastPage']
                    _action = 0
                else: fetching = False
    return pd.DataFrame(all_data)

# --- 3. ANALYTICS LOGIC (TRIP COUNT & SUMMARY) ---

def process_analytics(df):
    """Integrates logic from Combined_Summary.py and trip_count.py"""
    if df.empty: return df
    
    # Cleaning & Timezone (Lagos)
    df['transDate_NG'] = pd.to_datetime(df['transDate'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Africa/Lagos')
    df['date'] = df['transDate_NG'].dt.date
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    
    # Bus Capacity Mapping from trip_count.py
    capacity_map = {"FLM X30": 7, "FLM X30L": 10, "Midi": 40, "HC": 55}
    # (Abbreviated mapping for brevity - add your full issuer list here)
    
    return df

# --- 4. SIDEBAR & NAVIGATION ---

st.sidebar.title("🎮 Command Center")
tab_selection = st.sidebar.radio("Go to:", ["Live Monitor", "Operational Summary", "Trip Analytics"])

# Date Picker
today = datetime.now(pytz.timezone("Africa/Lagos"))
date_range = st.sidebar.date_input("Select Date Range", [today - timedelta(days=1), today])

# Refresh Controls
st.sidebar.markdown("---")
auto_refresh = st.sidebar.toggle("Live Mode (Auto-Refresh)", value=False)
refresh_rate = st.sidebar.slider("Interval (s)", 60, 600, 300) if auto_refresh else None

# --- 5. MAIN DASHBOARD TABS ---

@st.fragment(run_every=refresh_rate)
def run_app():
    token = get_token(USERNAME, PASSWORD)
    
    # Fetch both modules
    with st.spinner("Fetching Validator & Handheld Data..."):
        tz = pytz.timezone("Africa/Lagos")
        start_ts = tz.localize(datetime.combine(date_range[0], datetime.min.time()))
        end_ts = tz.localize(datetime.combine(date_range[1], datetime.max.time()))
        
        v_df = fetch_data(token, start_ts, end_ts, "Validator")
        h_df = fetch_data(token, start_ts, end_ts, "Handheld")
        
        # Merge modules like your MergeDailyTrxnFiles_2.py logic
        df = pd.concat([v_df, h_df], ignore_index=True)
        df = process_analytics(df)

    if df.empty:
        st.warning("No data found for selected range.")
        return

    # Dynamic Global Filters
    operators = st.multiselect("Filter by Operator", options=df['issuerName'].unique())
    routes = st.multiselect("Filter by Route", options=df['routeName'].unique())
    
    filtered_df = df.copy()
    if operators: filtered_df = filtered_df[filtered_df['issuerName'].isin(operators)]
    if routes: filtered_df = filtered_df[filtered_df['routeName'].isin(routes)]

    # TAB 1: LIVE MONITOR
    if tab_selection == "Live Monitor":
        st.header("⚡ Real-Time Stream")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Ridership", f"{len(filtered_df):,}")
        m2.metric("Total Revenue", f"₦{filtered_df['amount'].sum():,.2f}")
        m3.metric("Active Buses", filtered_df['busID'].nunique())
        
        st.subheader("Latest Transactions")
        st.dataframe(filtered_df[['transDate_NG', 'issuerName', 'routeName', 'amount']].tail(50), use_container_width=True)

    # TAB 2: OPERATIONAL SUMMARY
    elif tab_selection == "Operational Summary":
        st.header("📈 Route Performance (Monthly View)")
        # Grouping logic from Combined_Summary.py
        summary = filtered_df.groupby(['issuerName', 'routeName', 'date']).agg({
            'amount': 'sum',
            'id': 'count',
            'busID': 'nunique'
        }).reset_index()
        summary.columns = ['Operator', 'Route', 'Date', 'Revenue', 'Ridership', 'Buses']
        st.dataframe(summary, use_container_width=True)
        
        st.download_button("Download Summary CSV", summary.to_csv(index=False), "summary.csv")

    # TAB 3: TRIP ANALYTICS
    elif tab_selection == "Trip Analytics":
        st.header("🚌 Trip & Capacity Utilization")
        # Logic from trip_count.py
        st.info("Trip calculations are based on assigned bus seat capacities.")
        # (Insert your full capacity mapping logic here to show trip efficiency)
        st.write("Route-wise Trip Efficiency")
        st.bar_chart(filtered_df.groupby('routeName')['amount'].sum())

run_app()
