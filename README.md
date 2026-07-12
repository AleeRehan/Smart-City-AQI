# Smart City Air Quality Monitoring System

End-to-end data engineering pipeline for the Data Engineering Hackathon (Batch 05).
It simulates IoT air-quality sensors across 5 Pakistani cities, pulls real reference
data from the OpenAQ V3 API, transforms both with a Python ETL, stores everything in
Snowflake using a medallion architecture (Bronze → Silver → Gold), and serves a live
Streamlit dashboard.

## Architecture

```
IoT simulator (Python) ─┐
                        ├─► Bronze (RAW.IOT_READINGS, RAW.OPENAQ_RAW)
OpenAQ V3 API ──────────┘        │
                                 ▼  Python ETL (Pandas)
                          Silver (CLEAN.AQI_CLEAN)   ← validated + enriched, both sources
                                 │
                                 ▼  Snowflake SQL (INSERT ... SELECT)
                          Gold (ANALYTICS.CITY_DAILY) ← daily KPIs per city
                                 │
                                 ▼
                          Streamlit dashboard
```

## Project layout

```
smart-city-aqi/
├── sql/
│   ├── 01_schema.sql          # create DB, schemas, all tables (run first)
│   └── 02_gold_aggregate.sql  # Silver → Gold aggregation
├── src/
│   ├── aqi_utils.py           # EPA AQI formula + category + risk (shared)
│   ├── db.py                  # Snowflake connection from .env
│   ├── iot_simulator.py       # Stage 1A — sensor simulator
│   ├── openaq_fetcher.py      # Stage 1B — OpenAQ V3 fetcher
│   └── etl_pipeline.py        # Stage 2 — Bronze → Silver ETL
├── dashboard/
│   └── streamlit_app.py       # Stage 4 — live dashboard
├── data/                      # CSV output from the simulator
├── requirements.txt
├── .env.example
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
| 1 | Run `sql/01_schema.sql` in a Snowflake worksheet | Creates DB, schemas, tables |
| 2 | `python src/openaq_fetcher.py` | Loads OpenAQ data → Bronze |
| 3 | `python src/iot_simulator.py --minutes 30` | Streams sensor data → CSV + Bronze |
| 4 | `python src/etl_pipeline.py` | Bronze → Silver (clean + enrich) |
| 5 | Run `sql/02_gold_aggregate.sql` in Snowflake | Silver → Gold daily KPIs |
| 6 | `streamlit run dashboard/streamlit_app.py` | Opens the live dashboard |

Run the simulator (step 3) in its own terminal so it keeps streaming while you work.

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
```
