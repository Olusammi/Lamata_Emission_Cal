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
BATCH_SIZE_V = 50000  # The limit per request

# Page Setup
st.set_page_config(page_title="LAMATA Live Ops", layout="wide", page_icon="🚌")

# --- CORE FUNCTIONS (API & AUTH) ---

@st.cache_data(ttl=3600)
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
    """
    Fetches ALL transactions by looping through pages if data exceeds BATCH_SIZE_V.
    """
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}
    all_data = []
    page = 0
    fetching = True

    while fetching:
        # Construct query with the current page
        query = f"{STEM}v3/admin/get/bustransactions/-/-/{int(start_dt.timestamp())}/{int(end_dt.timestamp())}/{BATCH_SIZE_V}/{page}"
        
        try:
            response = requests.get(query, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()
            batch = data['content']['data']
            
            if not batch:
                fetching = False # Stop if no data is returned
            else:
                all_data.extend(batch)
                # If we got a full batch, there's likely more data on the next page
                if len(batch) == BATCH_SIZE_V:
                    page += 1
                else:
                    fetching = False # Stop if this batch was smaller than the limit
        except Exception as e:
            st.sidebar.error(f"Error on Page {page}: {e}")
            fetching = False

    if not all_data:
        return pd.DataFrame()

    # Process final combined dataset
    df = pd.DataFrame(all_data)
    df['transDate_NG'] = df.transDate.apply(
        lambda x: datetime.fromtimestamp(int(x), pytz.timezone("Africa/Lagos"))
    )
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    return df

# --- SIDEBAR & CONTROL LOGIC ---
st.sidebar.header("📡 API & Refresh Control")
manual_refresh = st.sidebar.button("Manual Data Pull")
auto_on = st.sidebar.toggle("Enable Live Auto-Refresh", value=False)

if auto_on:
    refresh_rate = st.sidebar.select_slider("Polling Interval (Seconds)", options=[60, 300, 600], value=300)
    st.sidebar.info(f"🔄 Auto-refreshing every {refresh_rate}s")
else:
    refresh_rate = None

# --- DASHBOARD FRAGMENT ---
@st.fragment(run_every=refresh_rate)
def render_dashboard():
    st.title("🚌 LAMATA Live Transaction Monitor")
    
    token = get_token(USERNAME, PASSWORD)
    if not token: return

    tz = pytz.timezone("Africa/Lagos")
    now = datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    with st.spinner("Fetching all pages from API..."):
        df = fetch_validator_data(token, start_of_day, now)

    if not df.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Transactions (All Pages)", f"{len(df):,}")
        m2.metric("Total Revenue", f"₦{df['amount'].sum():,.2f}")
        m3.metric("Last API Call", now.strftime("%H:%M:%S"))

        st.subheader("Live Activity Stream")
        st.dataframe(df[['transDate_NG', 'busID', 'routeName', 'amount']].sort_values(by='transDate_NG', ascending=False).head(100), use_container_width=True)
    else:
        st.info("No data found for today.")

render_dashboard()
