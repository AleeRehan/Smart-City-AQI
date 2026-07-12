"""
etl_pipeline.py  —  Stage 2 (Pandas)
Reads both Bronze tables from Snowflake, cleans + enriches them into one
unified shape, and loads Silver = CLEAN.AQI_CLEAN.

Uses executemany + TO_TIMESTAMP_NTZ for the load (NOT write_pandas), because
write_pandas mangles TIMESTAMP columns on some Windows/connector versions.

After this runs:  python build_gold.py

Run:  python etl_pipeline.py
"""

import pandas as pd

from aqi_utils import calculate_aqi, aqi_category, health_risk
from db import get_connection

# Target Silver columns, in the exact order the INSERT expects.
SILVER_COLS = [
    "SOURCE", "CITY", "SENSOR_ID", "PM25", "PM10", "CO2_PPM",
    "AQI_VALUE", "AQI_CATEGORY", "HEALTH_RISK",
    "LATITUDE", "LONGITUDE", "RECORDED_AT",
]

INSERT_SQL = """
    INSERT INTO CLEAN.AQI_CLEAN
    (source, city, sensor_id, pm25, pm10, co2_ppm, aqi_value,
     aqi_category, health_risk, latitude, longitude, recorded_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            TO_TIMESTAMP_NTZ(%s, 'YYYY-MM-DD HH24:MI:SS'))
"""


def read_bronze(conn):
    """Pull both raw tables, reading recorded_at as a clean TEXT timestamp."""
    iot = pd.read_sql("""
        SELECT sensor_id, city, zone_type, pm25, pm10, co2_ppm,
               temperature_c, humidity_pct, wind_speed_kmh, aqi_value, severity,
               TO_CHAR(recorded_at, 'YYYY-MM-DD HH24:MI:SS') AS recorded_at
        FROM RAW.IOT_READINGS
    """, conn)
    openaq = pd.read_sql("""
        SELECT location_id, station_name, city, country_code, latitude, longitude,
               pollutant_type, pollutant_value, unit,
               TO_CHAR(recorded_at, 'YYYY-MM-DD HH24:MI:SS') AS recorded_at
        FROM RAW.OPENAQ_RAW
    """, conn)
    iot.columns = [c.upper() for c in iot.columns]
    openaq.columns = [c.upper() for c in openaq.columns]
    print(f"Bronze read: {len(iot)} IoT rows, {len(openaq)} OpenAQ rows")
    return iot, openaq


def transform_iot(df: pd.DataFrame) -> pd.DataFrame:
    """Clean + enrich the simulated IoT readings."""
    if df.empty:
        return pd.DataFrame(columns=SILVER_COLS)

    df = df.dropna(subset=["PM25", "AQI_VALUE"])
    df = df[
        df["PM25"].between(0, 500)
        & df["CO2_PPM"].between(400, 2000)
        & df["HUMIDITY_PCT"].between(0, 100)
    ].copy()

    df["AQI_CATEGORY"] = df["PM25"].apply(aqi_category)
    df["HEALTH_RISK"] = df["AQI_CATEGORY"].apply(health_risk)
    df["SOURCE"] = "iot_simulator"
    df["LATITUDE"] = None
    df["LONGITUDE"] = None

    df = df.drop_duplicates(subset=["SENSOR_ID", "RECORDED_AT"])
    return df[SILVER_COLS]


def transform_openaq(df: pd.DataFrame) -> pd.DataFrame:
    """Clean OpenAQ, pivot pollutants to columns, enrich to match Silver."""
    if df.empty:
        return pd.DataFrame(columns=SILVER_COLS)

    df = df[df["POLLUTANT_TYPE"].isin(["pm25", "pm10"])].copy()
    df = df[df["POLLUTANT_VALUE"] > 0]
    if df.empty:
        return pd.DataFrame(columns=SILVER_COLS)

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

    # RECORDED_AT is already clean text 'YYYY-MM-DD HH24:MI:SS' from read_bronze
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

    # Guard: keep only valid timestamp strings
    silver["RECORDED_AT"] = pd.to_datetime(
        silver["RECORDED_AT"], errors="coerce"
    ).dt.strftime("%Y-%m-%d %H:%M:%S")
    silver = silver.dropna(subset=["RECORDED_AT"])

    print(f"Silver ready: {len(iot_clean)} IoT + {len(openaq_clean)} OpenAQ "
          f"= {len(silver)} rows")

    # Build row tuples in column order; turn pandas NaN into real NULLs.
    rows = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in silver[SILVER_COLS].itertuples(index=False, name=None)
    ]

    cur = conn.cursor()
    cur.executemany(INSERT_SQL, rows)
    conn.commit()
    cur.close()
    conn.close()
    print(f"Loaded {len(rows)} rows into CLEAN.AQI_CLEAN.")
    print("Next: python build_gold.py")


if __name__ == "__main__":
    main()