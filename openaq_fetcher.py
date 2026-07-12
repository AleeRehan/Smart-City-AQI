"""
openaq_fetcher.py  —  Stage 1B
Pulls REAL air-quality reference data for Pakistan from the OpenAQ V3 API
and loads it into Snowflake RAW.OPENAQ_RAW (Bronze).

Flow (matches the brief):
  Step 1: find Pakistan locations       GET /v3/locations
  Step 2: get sensors per location      GET /v3/locations/{id}/sensors
  Step 3: get latest measurements       GET /v3/locations/{id}/latest

Run:  python src/openaq_fetcher.py
Needs OPENAQ_API_KEY in your .env file.
"""

import os
import time

import requests
from dotenv import load_dotenv

from db import get_connection

load_dotenv()

API_KEY = os.environ.get("OPENAQ_API_KEY")
if not API_KEY:
    raise SystemExit("OPENAQ_API_KEY missing. Add it to your .env file.")

BASE_URL = "https://api.openaq.org/v3"
HEADERS = {"X-API-Key": API_KEY}

# Keep well under the free-tier limit (60/min). 1s pause between calls.
PAUSE = 1.0

INSERT_SQL = """
    INSERT INTO RAW.OPENAQ_RAW
    (location_id, station_name, city, country_code, latitude, longitude,
     pollutant_type, pollutant_value, unit, recorded_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TO_TIMESTAMP_NTZ(%s, 'YYYY-MM-DD HH24:MI:SS'))
"""


def get(url: str, params: dict = None) -> dict:
    """GET a V3 endpoint with the auth header and basic error handling."""
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    time.sleep(PAUSE)  # respect the rate limit
    if resp.status_code != 200:
        print(f"  ! {resp.status_code} on {url} -> {resp.text[:120]}")
        return {}
    return resp.json()


def get_pakistan_locations() -> list:
    """Step 1 — all OpenAQ monitoring stations in Pakistan."""
    # The brief calls the filter country_id=PK; the live V3 API uses iso=PK.
    data = get(f"{BASE_URL}/locations", params={"iso": "PK", "limit": 25})
    results = data.get("results", [])
    print(f"Step 1: found {len(results)} Pakistan locations")
    return results


def get_sensor_map(location_id: int) -> dict:
    """Step 2 — map each sensorId to its pollutant name + units."""
    data = get(f"{BASE_URL}/locations/{location_id}/sensors")
    sensor_map = {}
    for s in data.get("results", []):
        param = s.get("parameter", {}) or {}
        sensor_map[s.get("id")] = {
            "name": param.get("name"),      # pm25 / pm10 / co2 ...
            "units": param.get("units"),
        }
    return sensor_map


def get_latest(location_id: int) -> list:
    """Step 3 — most recent value from each sensor at this location."""
    data = get(f"{BASE_URL}/locations/{location_id}/latest")
    return data.get("results", [])


def build_rows(location: dict, sensor_map: dict, latest: list) -> list:
    """Map the V3 JSON into RAW.OPENAQ_RAW columns."""
    coords = location.get("coordinates") or {}
    country = location.get("country") or {}
    rows = []
    for m in latest:
        sinfo = sensor_map.get(m.get("sensorsId"), {})
        dt = (m.get("datetime") or {}).get("utc")
        rows.append((
            location.get("id"),
            location.get("name"),
            location.get("locality") or location.get("name"),  # city
            country.get("code", "PK"),
            coords.get("latitude"),
            coords.get("longitude"),
            sinfo.get("name"),                                  # pollutant_type
            m.get("value"),                                     # pollutant_value
            sinfo.get("units"),                                 # unit
            dt.replace("T", " ").replace("Z", "").split(".")[0].split("+")[0].strip() if dt else None,  # recorded_at (UTC)
        ))
    return rows


def main():
    locations = get_pakistan_locations()
    if not locations:
        print("No locations returned. Check your API key / network and retry.")
        return

    all_rows = []
    for loc in locations:
        loc_id = loc.get("id")
        sensor_map = get_sensor_map(loc_id)
        latest = get_latest(loc_id)
        rows = build_rows(loc, sensor_map, latest)
        all_rows.extend(rows)
        print(f"  location {loc_id} ({loc.get('locality') or loc.get('name')}): "
              f"{len(rows)} measurements")

    if not all_rows:
        print("No measurements collected.")
        return

    conn = get_connection(schema="RAW")
    cur = conn.cursor()
    cur.executemany(INSERT_SQL, all_rows)
    conn.commit()
    cur.close()
    conn.close()
    print(f"\nLoaded {len(all_rows)} rows into RAW.OPENAQ_RAW.")


if __name__ == "__main__":
    main()
