"""
streamlit_app.py  —  Stage 4 (Option A)  [polished dark theme]
Live dashboard reading the Snowflake Gold + Silver layers.
Data refreshes every 30s via st.cache_data(ttl=30); the page can also
auto-reload from the sidebar toggle.

Run from the project root:  streamlit run dashboard/streamlit_app.py
"""

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Smart City AQI", page_icon="🌫️", layout="wide")

# ---- Palette ---------------------------------------------------
BG = "#0e1117"
CARD = "#161b22"
BORDER = "#262d38"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#22d3ee"

# Risk level -> colour (green / amber / red / purple)
RISK_COLORS = {"LOW": "#22c55e", "MEDIUM": "#eab308",
               "HIGH": "#ef4444", "CRITICAL": "#a855f7"}

# ---- Global CSS ------------------------------------------------
st.markdown(f"""
<style>
    .stApp {{ background: {BG}; color: {TEXT}; }}
    #MainMenu, footer {{ visibility: hidden; }}
    .block-container {{ padding-top: 2rem; }}

    .hero-title {{
        font-size: 2.3rem; font-weight: 800; margin: 0;
        background: linear-gradient(90deg, {ACCENT}, #818cf8);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .hero-sub {{ color: {MUTED}; font-size: 0.95rem; margin-top: 2px; }}

    .kpi {{
        background: {CARD}; border: 1px solid {BORDER};
        border-left: 4px solid {ACCENT}; border-radius: 14px;
        padding: 18px 20px; height: 100%;
    }}
    .kpi-label {{ color: {MUTED}; font-size: 0.8rem; text-transform: uppercase;
                  letter-spacing: .05em; }}
    .kpi-value {{ font-size: 1.9rem; font-weight: 700; margin-top: 6px; color: {TEXT}; }}

    .panel-title {{ font-size: 1.1rem; font-weight: 700; margin: 8px 0 4px; color: {TEXT}; }}

    table.riskboard {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    table.riskboard th {{ text-align: left; color: {MUTED}; font-weight: 600;
        padding: 10px 12px; border-bottom: 1px solid {BORDER}; }}
    table.riskboard td {{ padding: 10px 12px; border-bottom: 1px solid {BORDER}; color: {TEXT}; }}
    table.riskboard tr:hover td {{ background: #1c2230; }}
    .badge {{ padding: 3px 12px; border-radius: 999px; color: #0b0e14;
        font-weight: 700; font-size: 0.78rem; }}
</style>
""", unsafe_allow_html=True)


# ---- Snowflake -------------------------------------------------
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


def style_fig(fig):
    """Apply the dark theme to any plotly figure (all text forced light)."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, size=13),
        title_font=dict(color=TEXT),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT),
                    title_font=dict(color=TEXT)),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    fig.update_xaxes(gridcolor=BORDER, zeroline=False,
                     title_font=dict(color=TEXT), tickfont=dict(color=TEXT))
    fig.update_yaxes(gridcolor=BORDER, zeroline=False,
                     title_font=dict(color=TEXT), tickfont=dict(color=TEXT))
    return fig


# ---- Sidebar controls ------------------------------------------
with st.sidebar:
    st.markdown(f"<h3 style='color:{ACCENT}'>Controls</h3>", unsafe_allow_html=True)
    window_h = st.slider("Trend window (hours)", 1, 48, 24,
                         help="How far back the sensor trend chart looks. "
                              "Widen it if the chart looks empty (timezone offset).")
    auto = st.toggle("Auto-refresh (30s)", value=False)
    st.caption("Data cache refreshes every 30s regardless.")

if auto:
    st.markdown("<meta http-equiv='refresh' content='30'>", unsafe_allow_html=True)

# ---- Header ----------------------------------------------------
st.markdown(
    "<div class='hero-title'>Smart City Air Quality Monitoring</div>"
    "<div class='hero-sub'>Pakistan · IoT sensors vs OpenAQ reference · "
    f"updated {datetime.now().strftime('%H:%M:%S')}</div>",
    unsafe_allow_html=True,
)
st.write("")

# ---- Load data -------------------------------------------------
daily = run_query("""
    SELECT city, avg_aqi, max_aqi, avg_pm25, dominant_risk, reading_count
    FROM ANALYTICS.CITY_DAILY
    WHERE report_date = CURRENT_DATE()
    ORDER BY avg_aqi DESC
""")

trend = run_query(f"""
    SELECT TO_VARCHAR(recorded_at) AS recorded_at, sensor_id, aqi_value
    FROM CLEAN.AQI_CLEAN
    WHERE source = 'iot_simulator'
      AND recorded_at >= DATEADD(hour, -{window_h}, CURRENT_TIMESTAMP())
      AND recorded_at BETWEEN '2000-01-01' AND '2100-01-01'
    ORDER BY recorded_at
""")
if not trend.empty:
    trend["RECORDED_AT"] = pd.to_datetime(trend["RECORDED_AT"], errors="coerce")
    trend = trend.dropna(subset=["RECORDED_AT"])

risk_counts = run_query("""
    SELECT health_risk, COUNT(*) AS n
    FROM CLEAN.AQI_CLEAN
    WHERE health_risk IS NOT NULL
    GROUP BY health_risk
""")

source_cmp = run_query("""
    SELECT city, source, ROUND(AVG(aqi_value),1) AS avg_aqi
    FROM CLEAN.AQI_CLEAN
    WHERE aqi_value IS NOT NULL AND city IS NOT NULL
    GROUP BY city, source
""")

# ---- Sidebar city filter (needs data first) --------------------
if not daily.empty:
    cities = sorted(daily["CITY"].dropna().unique().tolist())
    with st.sidebar:
        picked = st.multiselect("Cities", cities, default=cities)
    daily = daily[daily["CITY"].isin(picked)]
    source_cmp = source_cmp[source_cmp["CITY"].isin(picked)]

# ---- KPI cards -------------------------------------------------
total_readings = int(risk_counts["N"].sum()) if not risk_counts.empty else 0
critical = int(risk_counts.loc[risk_counts["HEALTH_RISK"] == "CRITICAL", "N"].sum()) \
    if not risk_counts.empty else 0
pct_critical = round(100 * critical / total_readings, 1) if total_readings else 0.0
worst_city = daily.iloc[0]["CITY"] if not daily.empty else "—"
peak_aqi = int(daily["MAX_AQI"].max()) if not daily.empty else 0


def kpi(label, value):
    return (f"<div class='kpi'><div class='kpi-label'>{label}</div>"
            f"<div class='kpi-value'>{value}</div></div>")


k1, k2, k3, k4 = st.columns(4)
k1.markdown(kpi("Highest AQI city", worst_city), unsafe_allow_html=True)
k2.markdown(kpi("Peak AQI today", peak_aqi), unsafe_allow_html=True)
k3.markdown(kpi("Total readings", f"{total_readings:,}"), unsafe_allow_html=True)
k4.markdown(kpi("% Critical", f"{pct_critical}%"), unsafe_allow_html=True)

st.write("")

# ---- Row: bar (avg AQI per city) + donut (risk mix) ------------
left, right = st.columns([2, 1])

with left:
    st.markdown("<div class='panel-title'>Average AQI per city — today</div>",
                unsafe_allow_html=True)
    if daily.empty:
        st.info("No Gold data yet. Run the ETL and build_gold.py first.")
    else:
        fig = px.bar(daily, x="CITY", y="AVG_AQI", color="DOMINANT_RISK",
                     color_discrete_map=RISK_COLORS, text="AVG_AQI")
        fig.update_traces(textposition="outside")
        fig.update_layout(legend_title_text="Dominant risk")
        st.plotly_chart(style_fig(fig), use_container_width=True)

with right:
    st.markdown("<div class='panel-title'>Reading mix by risk</div>",
                unsafe_allow_html=True)
    if risk_counts.empty:
        st.info("No Silver data yet.")
    else:
        order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        rc = risk_counts.set_index("HEALTH_RISK").reindex(order).dropna().reset_index()
        fig = go.Figure(go.Pie(
            labels=rc["HEALTH_RISK"], values=rc["N"], hole=0.6,
            marker=dict(colors=[RISK_COLORS[r] for r in rc["HEALTH_RISK"]]),
        ))
        fig.update_traces(textinfo="percent", textfont=dict(color="#0b0e14", size=14))
        st.plotly_chart(style_fig(fig), use_container_width=True)

# ---- Row: trend line (full width) ------------------------------
st.markdown(f"<div class='panel-title'>AQI trend per sensor — last {window_h} hours</div>",
            unsafe_allow_html=True)
if trend.empty:
    st.info("No recent sensor readings in this window. Start the simulator, "
            "or widen the trend window in the sidebar.")
else:
    fig = px.line(trend, x="RECORDED_AT", y="AQI_VALUE", color="SENSOR_ID")
    fig.update_layout(legend_title_text="Sensor")
    st.plotly_chart(style_fig(fig), use_container_width=True)

# ---- Row: source comparison (the assignment's whole point) -----
st.markdown("<div class='panel-title'>Simulated sensors vs OpenAQ reference — "
            "avg AQI by city</div>", unsafe_allow_html=True)
if source_cmp.empty:
    st.info("No comparison data yet.")
else:
    fig = px.bar(source_cmp, x="CITY", y="AVG_AQI", color="SOURCE",
                 barmode="group",
                 color_discrete_map={"iot_simulator": ACCENT, "openaq_v3": "#818cf8"})
    fig.update_layout(legend_title_text="Source")
    st.plotly_chart(style_fig(fig), use_container_width=True)

# ---- Risk board table ------------------------------------------
st.markdown("<div class='panel-title'>City risk board — today</div>",
            unsafe_allow_html=True)
if daily.empty:
    st.info("No data to show yet.")
else:
    def badge(risk):
        c = RISK_COLORS.get(risk, "#666")
        return f"<span class='badge' style='background:{c}'>{risk}</span>"

    rows = ""
    for _, r in daily.iterrows():
        rows += (f"<tr><td>{r['CITY']}</td><td>{r['AVG_AQI']}</td>"
                 f"<td>{r['MAX_AQI']}</td><td>{r['AVG_PM25']}</td>"
                 f"<td>{badge(r['DOMINANT_RISK'])}</td>"
                 f"<td>{int(r['READING_COUNT'])}</td></tr>")
    st.markdown(
        "<table class='riskboard'><tr><th>City</th><th>Avg AQI</th><th>Max AQI</th>"
        "<th>Avg PM2.5</th><th>Dominant risk</th><th>Readings</th></tr>"
        f"{rows}</table>", unsafe_allow_html=True)