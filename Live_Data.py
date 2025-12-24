import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import pytz
from datetime import datetime, timedelta

# =========================
# CONFIGURATION
# =========================
STEM = "https://rahq.tapdev.site:3443/"
USERNAME = st.secrets["USERNAME"]
PASSWORD = st.secrets["PASSWORD"]

BATCH_SIZE_V = 50000
BATCH_SIZE_H = 2000

st.set_page_config(
    page_title="LAMATA Ops Center",
    layout="wide",
    page_icon="📊"
)

# =========================
# AUTH
# =========================
@st.cache_data(ttl=3600)
def get_token(user, pwd):
    payload = json.dumps({"data": {"username": user, "password": pwd}})
    headers = {'Content-Type': 'application/json'}
    res = requests.post(f"{STEM}v1/api/auth", headers=headers, data=payload)
    return res.json()['content']['token']

# =========================
# DATA FETCHER (SCOPED)
# =========================
def fetch_data(token, start_dt, end_dt, mode, operators=None, routes=None):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }

    frames = []
    page = 0 if mode == "Validator" else "-"
    _action = "-"

    while True:
        if mode == "Validator":
            query = f"{STEM}v3/admin/get/bustransactions/-/-/{int(start_dt.timestamp())}/{int(end_dt.timestamp())}/{BATCH_SIZE_V}/{page}"
        else:
            query = f"{STEM}v2/admin/get/transactions/6/-/-/-/-/{int(start_dt.timestamp())}/{int(end_dt.timestamp())}/{BATCH_SIZE_H}/{page}/{_action}"

        res = requests.get(query, headers=headers).json()
        batch = res["content"]["data"]

        if not batch:
            break

        df = pd.DataFrame(batch)

        # ---- EARLY FILTERING ----
        if operators and "issuerName" in df:
            df = df[df["issuerName"].isin(operators)]

        if routes and "routeName" in df:
            df = df[df["routeName"].isin(routes)]

        frames.append(df)

        if mode == "Validator":
            if len(batch) < BATCH_SIZE_V:
                break
            page += 1
        else:
            if len(batch) < BATCH_SIZE_H:
                break
            page = res["content"]["lastPage"]
            _action = 0

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

# =========================
# ANALYTICS / NORMALIZATION
# =========================
def process_analytics(df):
    if df.empty:
        return df

    df["transDate_NG"] = (
        pd.to_datetime(df["transDate"], unit="s")
        .dt.tz_localize("UTC")
        .dt.tz_convert("Africa/Lagos")
    )
    df["date"] = df["transDate_NG"].dt.date
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    return df

# =========================
# CAPACITY & TRIP LOGIC
# =========================
def prepare_bus_mapping():
    capacity = {
        "FLM X30": 7,
        "FLM X30L": 10,
        "Midi": 40,
        "HC": 55
    }

    issuer_to_type = {
        # abbreviated — extend freely
        "APEC INTEGRATED - FLM": "FLM X30",
        "CITY CRUISE & LOGISTICS LTD - X30L - FLM": "FLM X30L",
        "TSL Metroline Limited - MIDI": "Midi",
        "Primero Transport Services Limited - HC": "HC"
    }

    return issuer_to_type, capacity

def add_trip_calculations(df):
    issuer_map, cap_map = prepare_bus_mapping()

    df["bus_type"] = df["issuerName"].map(issuer_map).fillna("Unknown")
    df["seat_capacity"] = df["bus_type"].map(cap_map).fillna(0)

    df["trips"] = np.divide(
        df["ridership"],
        df["seat_capacity"],
        out=np.zeros_like(df["ridership"], dtype=float),
        where=df["seat_capacity"] != 0
    ).round(2)

    return df

# =========================
# SIDEBAR CONTROLS
# =========================
st.sidebar.title("🎮 Command Center")

module = st.sidebar.selectbox(
    "Data Source",
    ["Validator", "Handheld", "Both"]
)

output_type = st.sidebar.selectbox(
    "Output Type",
    ["Raw Transactions", "Operator Summary", "Trip Summary"]
)

tz = pytz.timezone("Africa/Lagos")
today = datetime.now(tz)

date_range = st.sidebar.date_input(
    "Date Range",
    [today - timedelta(days=1), today]
)

# =========================
# MAIN EXECUTION
# =========================
token = get_token(USERNAME, PASSWORD)

start_ts = tz.localize(datetime.combine(date_range[0], datetime.min.time()))
end_ts = tz.localize(datetime.combine(date_range[1], datetime.max.time()))

with st.spinner("Fetching data from API..."):
    dfs = []

    if module in ["Validator", "Both"]:
        dfs.append(fetch_data(token, start_ts, end_ts, "Validator"))

    if module in ["Handheld", "Both"]:
        dfs.append(fetch_data(token, start_ts, end_ts, "Handheld"))

    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    df = process_analytics(df)

if df.empty:
    st.warning("No data found for selected options.")
    st.stop()

# =========================
# GLOBAL FILTERS
# =========================
operators = st.multiselect(
    "Filter Operator",
    options=sorted(df["issuerName"].dropna().unique())
)

routes = st.multiselect(
    "Filter Route",
    options=sorted(df["routeName"].dropna().unique())
)

if operators:
    df = df[df["issuerName"].isin(operators)]

if routes:
    df = df[df["routeName"].isin(routes)]

# =========================
# OUTPUT VIEWS
# =========================
if output_type == "Raw Transactions":
    st.header("📄 Raw Transactions")
    st.dataframe(df, use_container_width=True)

elif output_type == "Operator Summary":
    st.header("📊 Operator Summary")

    summary = (
        df.groupby(["issuerName", "routeName", "date"])
          .agg(
              revenue=("amount", "sum"),
              ridership=("id", "count"),
              buses=("busID", "nunique")
          )
          .reset_index()
    )

    st.dataframe(summary, use_container_width=True)
    st.download_button(
        "Download CSV",
        summary.to_csv(index=False),
        "operator_summary.csv"
    )

elif output_type == "Trip Summary":
    st.header("🚌 Trip & Capacity Summary")

    trip_df = (
        df.groupby(["issuerName", "routeName", "date"])
          .agg(
              revenue=("amount", "sum"),
              ridership=("id", "count"),
              buses=("busID", "nunique")
          )
          .reset_index()
    )

    trip_df = add_trip_calculations(trip_df)

    st.dataframe(trip_df, use_container_width=True)
    st.bar_chart(trip_df.groupby("routeName")["trips"].sum())

    st.download_button(
        "Download CSV",
        trip_df.to_csv(index=False),
        "trip_summary.csv"
    )
