import streamlit as st
import pandas as pd
import requests
import json
import pytz
from datetime import datetime, timedelta
import time

# --- CONFIGURATION FROM SECRETS ---
# These are pulled from the 'Advanced Settings > Secrets' in Streamlit Cloud
STEM = "https://rahq.tapdev.site:3443/"
USERNAME = st.secrets["USERNAME"]
PASSWORD = st.secrets["PASSWORD"]
BATCH_SIZE_V = 50000

# Page Setup
st.set_page_config(page_title="LAMATA Live Ops", layout="wide", page_icon="🚌")

# --- CORE FUNCTIONS ---

@st.cache_data(ttl=3600)  # Refresh token once per hour
def get_token(user, pwd):
    try:
        payload = json.dumps({"data": {"username": user, "password": pwd}})
        headers = {'Content-Type': 'application/json'}
        response = requests.post(f"{STEM}v1/api/auth", headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        return response.json()['content']['token']
    except Exception as e:
        st.error(f"Authentication Failed: {e}")
        return None

def fetch_validator_data(token, start_dt, end_dt):
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}
    # Using the v3 endpoint from your scraper
    query = f"{STEM}v3/admin/get/bustransactions/-/-/{int(start_dt.timestamp())}/{int(end_dt.timestamp())}/{BATCH_SIZE_V}/0"
    
    try:
        response = requests.get(query, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data['content']['data'])
        
        if not df.empty:
            # Convert timestamps to Lagos time immediately
            df['transDate_NG'] = df.transDate.apply(
                lambda x: datetime.fromtimestamp(int(x), pytz.timezone("Africa/Lagos"))
            )
            # Basic cleaning for display
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        return df
    except Exception as e:
        st.sidebar.error(f"Fetch Error: {e}")
        return pd.DataFrame()

# --- DASHBOARD UI ---

st.title("🚌 LAMATA Live Transaction Monitor")
st.markdown(f"**Status:** Connected to `{STEM}`")

# Sidebar Controls
st.sidebar.header("Operations Control")
refresh_rate = st.sidebar.select_slider("Auto-Refresh Interval", options=[30, 60, 300, 600], value=60, help="Seconds")
manual_btn = st.sidebar.button("Force Refresh Now")

# Main Dashboard logic
token = get_token(USERNAME, PASSWORD)

if token:
    # Set time window for "Today" in Lagos
    tz = pytz.timezone("Africa/Lagos")
    now = datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Fetch Data
    df = fetch_validator_data(token, start_of_day, now)

    if not df.empty:
        # 1. Top Level Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Today's Transactions", f"{len(df):,}")
        m2.metric("Total Revenue", f"₦{df['amount'].sum():,.2f}")
        m3.metric("Last Updated", now.strftime("%H:%M:%S"))

        # 2. Visualizations
        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.subheader("Transaction Trend (Today)")
            df['hour'] = df['transDate_NG'].dt.hour
            hourly_data = df.groupby('hour').size()
            st.area_chart(hourly_data, color="#007bff")

        with col_right:
            st.subheader("Top Routes")
            top_routes = df['routeName'].value_counts().head(5)
            st.bar_chart(top_routes)

        # 3. Raw Data Table
        st.subheader("Live Transaction Stream")
        st.dataframe(
            df[['transDate_NG', 'busID', 'routeName', 'amount']].sort_values(by='transDate_NG', ascending=False),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No transaction data found for today yet.")
else:
    st.error("Could not initialize token. Check your Secrets configuration.")

# Handle the auto-refresh loop
time.sleep(refresh_rate)
st.rerun()