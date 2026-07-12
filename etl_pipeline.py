"""
etl_pipeline.py  —  Stage 2 (Pandas)
Reads both Bronze tables from Snowflake, cleans + enriches them into one
unified shape, and loads Silver = CLEAN.AQI_CLEAN.

After this runs, execute sql/02_gold_aggregate.sql to build Gold.

Run:  python src/etl_pipeline.py
"""

import pandas as pd
from snowflake.connector.pandas_tools import write_pandas

from aqi_utils import calculate_aqi, aqi_category, health_risk
from db import get_connection

# Target Silver columns (order matters for write_pandas)
SILVER_COLS = [
    "SOURCE", "CITY", "SENSOR_ID", "PM25", "PM10", "CO2_PPM",
    "AQI_VALUE", "AQI_CATEGORY", "HEALTH_RISK",
    "LATITUDE", "LONGITUDE", "RECORDED_AT",
]


def read_bronze(conn):
    """Pull both raw tables into pandas DataFrames."""
    iot = pd.read_sql("SELECT * FROM RAW.IOT_READINGS", conn)
    openaq = pd.read_sql("SELECT * FROM RAW.OPENAQ_RAW", conn)
    iot.columns = [c.upper() for c in iot.columns]
    openaq.columns = [c.upper() for c in openaq.columns]
    print(f"Bronze read: {len(iot)} IoT rows, {len(openaq)} OpenAQ rows")
    return iot, openaq


def transform_iot(df: pd.DataFrame) -> pd.DataFrame:
    """Clean + enrich the simulated IoT readings."""
    if df.empty:
        return pd.DataFrame(columns=SILVER_COLS)

    # Drop rows with no pm25 or aqi
    df = df.dropna(subset=["PM25", "AQI_VALUE"])

    # Validate physical ranges
    df = df[
        df["PM25"].between(0, 500)
        & df["CO2_PPM"].between(400, 2000)
        & df["HUMIDITY_PCT"].between(0, 100)
    ].copy()

    # Enrich
    df["AQI_CATEGORY"] = df["PM25"].apply(aqi_category)
    df["HEALTH_RISK"] = df["AQI_CATEGORY"].apply(health_risk)
    df["SOURCE"] = "iot_simulator"
    df["LATITUDE"] = None
    df["LONGITUDE"] = None

    # Deduplicate on (sensor, timestamp)
    df = df.drop_duplicates(subset=["SENSOR_ID", "RECORDED_AT"])

    return df[SILVER_COLS]


def transform_openaq(df: pd.DataFrame) -> pd.DataFrame:
    """Clean OpenAQ, pivot pollutants to columns, enrich to match Silver."""
    if df.empty:
        return pd.DataFrame(columns=SILVER_COLS)

    # Keep only pm25 / pm10 and drop non-positive values
    df = df[df["POLLUTANT_TYPE"].isin(["pm25", "pm10"])].copy()
    df = df[df["POLLUTANT_VALUE"] > 0]
    if df.empty:
        return pd.DataFrame(columns=SILVER_COLS)

    # One row per (location, time) with pm25 & pm10 as columns
    idx = ["LOCATION_ID", "CITY", "LATITUDE", "LONGITUDE", "RECORDED_AT"]
    wide = (
        df.pivot_table(index=idx, columns="POLLUTANT_TYPE",
                       values="POLLUTANT_VALUE", aggfunc="mean")
        .reset_index()
    )
    if "pm25" not in wide:
        wide["pm25"] = None
    if "pm10" not in wide:
        wide["pm10"] = None

    wide["RECORDED_AT"] = pd.to_datetime(wide["RECORDED_AT"], utc=True).dt.tz_localize(None)
    wide["PM25"] = wide["pm25"]
    wide["PM10"] = wide["pm10"]
    wide["CO2_PPM"] = None
    wide["AQI_VALUE"] = wide["PM25"].apply(calculate_aqi)
    wide["AQI_CATEGORY"] = wide["PM25"].apply(aqi_category)
    wide["HEALTH_RISK"] = wide["AQI_CATEGORY"].apply(health_risk)
    wide["SOURCE"] = "openaq_v3"
    wide["SENSOR_ID"] = None

    return wide[SILVER_COLS]


def main():
    conn = get_connection(schema="CLEAN")
    iot_raw, openaq_raw = read_bronze(conn)

    iot_clean = transform_iot(iot_raw)
    openaq_clean = transform_openaq(openaq_raw)
    silver = pd.concat([iot_clean, openaq_clean], ignore_index=True)

    silver["PROCESSED_AT"] = pd.Timestamp.utcnow().tz_localize(None)
    print(f"Silver ready: {len(iot_clean)} IoT + {len(openaq_clean)} OpenAQ "
          f"= {len(silver)} rows")

    # Load into CLEAN.AQI_CLEAN
    success, _nchunks, nrows, _ = write_pandas(
        conn, silver, table_name="AQI_CLEAN", schema="CLEAN",
    )
    conn.close()
    print(f"write_pandas success={success}, rows loaded={nrows}")
    print("Next: run sql/02_gold_aggregate.sql in Snowflake to build Gold.")


if __name__ == "__main__":
    main()
