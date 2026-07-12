"""
streamlit_app.py  —  Stage 4 (Option A)
Live dashboard reading the Snowflake Gold + Silver layers.
Auto-refreshes its data every 30 seconds via st.cache_data(ttl=30).

Run from the project root:  streamlit run dashboard/streamlit_app.py
"""

import os
import sys

import pandas as pd
import plotly.express as px
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Smart City AQI", layout="wide")

# Colours for the 4 risk levels
RISK_COLORS = {"LOW": "#2ecc71", "MEDIUM": "#f1c40f",
               "HIGH": "#e74c3c", "CRITICAL": "#8e44ad"}


@st.cache_resource
def get_conn():
    return snowflake.connector.connect(
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "SMART_CITY_AQI"),
    )


@st.cache_data(ttl=30)
def run_query(sql: str) -> pd.DataFrame:
    df = pd.read_sql(sql, get_conn())
    df.columns = [c.upper() for c in df.columns]
    return df


st.title("Smart City Air Quality Monitoring")
st.caption("Live view of Pakistan air quality — refreshes every 30 seconds")

# ---- Load data -------------------------------------------------
daily = run_query("""
    SELECT city, avg_aqi, max_aqi, avg_pm25, dominant_risk, reading_count
    FROM ANALYTICS.CITY_DAILY
    WHERE report_date = CURRENT_DATE()
    ORDER BY avg_aqi DESC
""")

trend = run_query("""
    SELECT TO_VARCHAR(recorded_at) AS recorded_at, sensor_id, aqi_value
    FROM CLEAN.AQI_CLEAN
    WHERE source = 'iot_simulator'
      AND recorded_at >= DATEADD(hour, -6, CURRENT_TIMESTAMP())
      AND recorded_at BETWEEN '2000-01-01' AND '2100-01-01'
    ORDER BY recorded_at
""")
if not trend.empty:
    trend["RECORDED_AT"] = pd.to_datetime(trend["RECORDED_AT"], errors="coerce")
    trend = trend.dropna(subset=["RECORDED_AT"])

risk_counts = run_query("""
    SELECT health_risk, COUNT(*) AS n
    FROM CLEAN.AQI_CLEAN
    GROUP BY health_risk
""")

# ---- Metric cards ----------------------------------------------
total_readings = int(risk_counts["N"].sum()) if not risk_counts.empty else 0
critical = int(risk_counts.loc[risk_counts["HEALTH_RISK"] == "CRITICAL", "N"].sum()) \
    if not risk_counts.empty else 0
pct_critical = round(100 * critical / total_readings, 1) if total_readings else 0.0
worst_city = daily.iloc[0]["CITY"] if not daily.empty else "—"

c1, c2, c3 = st.columns(3)
c1.metric("Highest AQI city (today)", worst_city)
c2.metric("Total readings", f"{total_readings:,}")
c3.metric("% CRITICAL readings", f"{pct_critical}%")

st.divider()

# ---- Bar chart: avg AQI per city today -------------------------
left, right = st.columns(2)
with left:
    st.subheader("Average AQI per city — today")
    if daily.empty:
        st.info("No Gold data yet. Run the ETL and gold SQL first.")
    else:
        fig = px.bar(daily, x="CITY", y="AVG_AQI", color="AVG_AQI",
                     color_continuous_scale="RdYlGn_r", text="AVG_AQI")
        st.plotly_chart(fig, use_container_width=True)

# ---- Line chart: AQI trend per sensor (last 6h) ----------------
with right:
    st.subheader("AQI trend per sensor — last 6 hours")
    if trend.empty:
        st.info("No recent IoT readings yet. Start the simulator.")
    else:
        fig = px.line(trend, x="RECORDED_AT", y="AQI_VALUE", color="SENSOR_ID")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---- Color-coded severity table --------------------------------
st.subheader("City risk board — today")
if daily.empty:
    st.info("No data to show yet.")
else:
    def badge(risk):
        color = RISK_COLORS.get(risk, "#888")
        return (f'<span style="background:{color};color:white;padding:3px 10px;'
                f'border-radius:10px;font-weight:600">{risk}</span>')

    rows_html = ""
    for _, r in daily.iterrows():
        rows_html += (
            f"<tr><td>{r['CITY']}</td>"
            f"<td>{r['AVG_AQI']}</td>"
            f"<td>{r['MAX_AQI']}</td>"
            f"<td>{r['AVG_PM25']}</td>"
            f"<td>{badge(r['DOMINANT_RISK'])}</td>"
            f"<td>{int(r['READING_COUNT'])}</td></tr>"
        )
    st.markdown(
        "<table style='width:100%;text-align:left'>"
        "<tr><th>City</th><th>Avg AQI</th><th>Max AQI</th>"
        "<th>Avg PM2.5</th><th>Dominant risk</th><th>Readings</th></tr>"
        f"{rows_html}</table>",
        unsafe_allow_html=True,
    )
