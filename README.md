# Smart City Air Quality Monitoring System

End-to-end data engineering pipeline for the Data Engineering Hackathon (Batch 05).
It simulates IoT air-quality sensors across 5 Pakistani cities, pulls real reference
data from the OpenAQ V3 API, transforms both with a Python ETL, stores everything in
Snowflake using a medallion architecture (Bronze → Silver → Gold), and serves a live
Streamlit dashboard.

## Architecture

For the system design and diagram, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Project layout

```
smart-city-aqi/
├── aqi_utils.py            # EPA AQI formula + category + risk (shared)
├── db.py                   # Snowflake connection from .env
├── iot_simulator.py        # Stage 1A — sensor simulator
├── openaq_fetcher.py       # Stage 1B — OpenAQ V3 fetcher
├── etl_pipeline.py         # Stage 2 — Bronze → Silver ETL
├── build_gold.py           # Stage 3 — Silver → Gold (run after ETL)
├── streamlit_app.py        # Stage 4 — live dashboard
├── 01_schema.sql           # create DB, schemas, all tables (run first)
├── 02_gold_aggregate.sql   # Silver → Gold aggregation (SQL alternative)
├── make_diagram.py         # regenerates docs/architecture.png
├── data/                   # iot_readings.csv (simulator output)
├── docs/                   # architecture.png + diagram code
├── requirements.txt
├── .env.example
├── ARCHITECTURE.md
└── README.md
```

## Setup

1. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   ```
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Get an OpenAQ API key** — register free at explore.openaq.org/register and copy
   your key from account settings.
4. **Configure credentials** — copy `.env.example` to `.env` and fill in your Snowflake
   details and OpenAQ key. `.env` is git-ignored, so nothing secret is committed.

## How to run (in order)

| Step | Command | What it does |
|------|---------|--------------|
| 1 | Run `01_schema.sql` in a Snowflake worksheet | Creates DB, schemas, tables |
| 2 | `python openaq_fetcher.py` | Loads OpenAQ data → Bronze |
| 3 | `python iot_simulator.py --minutes 30` | Streams sensor data → CSV + Bronze |
| 4 | `python etl_pipeline.py` | Bronze → Silver (clean + enrich) |
| 5 | `python build_gold.py` | Silver → Gold daily KPIs |
| 6 | `streamlit run streamlit_app.py` | Opens the live dashboard |

Run the simulator (step 3) in its own terminal so it keeps streaming while you work.
Step 5 can also be done by running `02_gold_aggregate.sql` in a Snowflake worksheet.

## Deliverables checklist

- **D1** IoT simulator — `src/iot_simulator.py`
- **D2** OpenAQ fetched — `src/openaq_fetcher.py`
- **D3** ETL done — `src/etl_pipeline.py`
- **D4** Bronze loaded — Snowflake `RAW.*` tables
- **D5** Silver + Gold done — `CLEAN.AQI_CLEAN`, `ANALYTICS.CITY_DAILY`
- **D6** Dashboard live — `dashboard/streamlit_app.py`

## Notes

- ETL tool: Pandas (fine for this data volume; swap to Polars if preferred).
- Dashboard: Streamlit (all-Python, easy live demo). Power BI is an equally valid
  alternative — connect it to `ANALYTICS.CITY_DAILY` via the Snowflake connector.
- The OpenAQ V3 locations filter uses `iso=PK`. Pakistan stations are mostly in
  Karachi and Lahore; that is expected — the OpenAQ data is for comparison, not an
  exact per-city match.
