import streamlit as st
import pandas as pd
import requests
import json
import pytz
from datetime import datetime
import time

# --- CONFIGURATION FROM SECRETS ---
STEM = "https://rahq.tapdev.site:3443/"
USERNAME = st.secrets["USERNAME"]
PASSWORD = st.secrets["PASSWORD"]
BATCH_SIZE_V = 50000

# Page Setup
st.set_page_config(page_title="LAMATA Live Ops", layout="wide", page_icon="🚌")

# --- CORE FUNCTIONS (API & AUTH) ---

@st.cache_data(ttl=3600)  # Re-auth only once per hour to save server resources
def get_token(user, pwd):
    try:
        payload = json.dumps({"data": {"username": user, "password": pwd}})
        headers = {'Content-Type': 'application/json'}
        response = requests.post(f"{STEM}v1/api/auth", headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        return response.json()['content']['token']
    except Exception as e:
        st.error(f"Auth Error: {e}")
        return None

def fetch_validator_data(token, start_dt, end_dt):
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}
    query = f"{STEM}v3/admin/get/bustransactions/-/-/{int(start_dt.timestamp())}/{int(end_dt.timestamp())}/{BATCH_SIZE_V}/0"
    
    try:
        response = requests.get(query, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data['content']['data'])
        
        if not df.empty:
            df['transDate_NG'] = df.transDate.apply(
                lambda x: datetime.fromtimestamp(int(x), pytz.timezone("Africa/Lagos"))
            )
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        return df
    except Exception as e:
        st.sidebar.warning(f"Fetch failed at {datetime.now().strftime('%H:%M:%S')}")
        return pd.DataFrame()

# --- SIDEBAR & CONTROL LOGIC ---

st.sidebar.header("📡 API & Refresh Control")

# 1. Manual Refresh - Always available
manual_refresh = st.sidebar.button("Manual Data Pull", help="Click to fetch data once right now.")

# 2. Auto-Refresh Toggle - Disabled by default to be safe
auto_on = st.sidebar.toggle("Enable Live Auto-Refresh", value=False)

if auto_on:
    refresh_rate = st.sidebar.select_slider(
        "Polling Interval (Seconds)", 
        options=[60, 300, 600, 1800], # 1min, 5min, 10min, 30min
        value=300,
        help="Higher values reduce server load."
    )
    st.sidebar.info(f"🔄 Auto-refreshing every {refresh_rate}s")
else:
    refresh_rate = None
    st.sidebar.write("⏸️ Auto-refresh is currently **OFF**.")

# --- DASHBOARD FRAGMENT ---
# This decorator ensures only the data part of the app reruns, saving resources
@st.fragment(run_every=refresh_rate)
def render_dashboard():
    st.title("🚌 LAMATA Live Transaction Monitor")
    
    token = get_token(USERNAME, PASSWORD)
    if not token:
        st.error("Invalid API credentials. Check Streamlit Secrets.")
        return

    # Set time window for 'Today' in Lagos
    tz = pytz.timezone("Africa/Lagos")
    now = datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Fetch data
    with st.spinner("Fetching latest data..."):
        df = fetch_validator_data(token, start_of_day, now)

    if not df.empty:
        # Top Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Today's Transactions", f"{len(df):,}")
        m2.metric("Total Revenue", f"₦{df['amount'].sum():,.2f}")
        m3.metric("Last API Call", now.strftime("%H:%M:%S"))

        # Visuals
        st.subheader("Recent Activity Stream")
        st.dataframe(
            df[['transDate_NG', 'busID', 'routeName', 'amount']].sort_values(by='transDate_NG', ascending=False).head(50),
            use_container_width=True,
            hide_index=True
        )
        
        # Hourly Trend Chart
        df['hour'] = df['transDate_NG'].dt.hour
        hourly_counts = df.groupby('hour').size()
        st.area_chart(hourly_counts, color="#007bff")
    else:
        st.info("No transaction data received for today yet.")

# Main Execution
render_dashboard()
