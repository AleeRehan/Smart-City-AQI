"""
iot_simulator.py  —  Stage 1A
Behaves like 10 physical IoT air-quality sensors across 5 Pakistani cities.
Every 10 seconds it produces one reading per sensor, then:
  1. appends them to data/iot_readings.csv
  2. inserts them into Snowflake RAW.IOT_READINGS (Bronze)

Run:  python src/iot_simulator.py --minutes 30
"""

import argparse
import csv
import math
import os
import random
import time
from datetime import datetime, timezone

from aqi_utils import calculate_aqi, severity_label
from db import get_connection

# ---------------------------------------------------------------
# Sensor network (from the brief)
# ---------------------------------------------------------------
SENSORS = [
    {"sensor_id": "PKS_KHI_IND_01", "city": "Karachi",    "zone_type": "industrial"},
    {"sensor_id": "PKS_KHI_TRF_02", "city": "Karachi",    "zone_type": "traffic"},
    {"sensor_id": "PKS_LHR_RES_01", "city": "Lahore",     "zone_type": "residential"},
    {"sensor_id": "PKS_LHR_IND_02", "city": "Lahore",     "zone_type": "industrial"},
    {"sensor_id": "PKS_ISB_PRK_01", "city": "Islamabad",  "zone_type": "park"},
    {"sensor_id": "PKS_ISB_TRF_02", "city": "Islamabad",  "zone_type": "traffic"},
    {"sensor_id": "PKS_PEW_IND_01", "city": "Peshawar",   "zone_type": "industrial"},
    {"sensor_id": "PKS_PEW_RES_02", "city": "Peshawar",   "zone_type": "residential"},
    {"sensor_id": "PKS_MUL_TRF_01", "city": "Multan",     "zone_type": "traffic"},
    {"sensor_id": "PKS_MUL_PRK_02", "city": "Multan",     "zone_type": "park"},
]

# Base ranges per zone: (pm25_low, pm25_high, co2_low, co2_high, temp_low, temp_high)
ZONE_BASE = {
    "industrial":  (80, 120, 600, 900, 30, 42),
    "traffic":     (55,  80, 500, 700, 28, 40),
    "residential": (25,  50, 420, 500, 25, 38),
    "park":        (8,   20, 400, 430, 22, 35),
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CSV_PATH = os.path.join(DATA_DIR, "iot_readings.csv")

CSV_COLUMNS = [
    "sensor_id", "city", "zone_type", "pm25", "pm10", "co2_ppm",
    "temperature_c", "humidity_pct", "wind_speed_kmh", "aqi_value",
    "severity", "recorded_at",
]

INSERT_SQL = """
    INSERT INTO RAW.IOT_READINGS
    (sensor_id, city, zone_type, pm25, pm10, co2_ppm, temperature_c,
     humidity_pct, wind_speed_kmh, aqi_value, severity, recorded_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TO_TIMESTAMP_NTZ(%s, 'YYYY-MM-DD HH24:MI:SS'))
"""


def noise(value: float, pct: float = 0.15) -> float:
    """Apply +/- pct random noise to a value."""
    return value * (1 + random.uniform(-pct, pct))


def time_of_day_factor(hour: int) -> float:
    """Rush-hour style multiplier from the brief."""
    return 1.0 + 0.3 * math.sin((hour - 8) * math.pi / 12)


def generate_reading(sensor: dict) -> dict:
    """Produce one realistic reading for one sensor."""
    pm25_lo, pm25_hi, co2_lo, co2_hi, t_lo, t_hi = ZONE_BASE[sensor["zone_type"]]
    hour = datetime.now().hour
    tod = time_of_day_factor(hour)

    # Base values scaled by time of day, then noised
    pm25 = noise(random.uniform(pm25_lo, pm25_hi) * tod)
    co2 = noise(random.uniform(co2_lo, co2_hi) * tod)
    temp = noise(random.uniform(t_lo, t_hi))

    # 15% chance of a pollution-event spike
    if random.random() < 0.15:
        pm25 *= random.uniform(2.5, 4.0)

    # Clamp to allowed field ranges
    pm25 = round(min(pm25, 500.0), 1)
    pm10 = round(min(max(pm25 * random.uniform(1.2, 1.6), pm25), 600.0), 1)  # always >= pm25
    co2 = round(min(max(co2, 400.0), 2000.0), 1)
    temp = round(min(max(temp, 15.0), 45.0), 1)

    aqi = calculate_aqi(pm25)

    return {
        "sensor_id": sensor["sensor_id"],
        "city": sensor["city"],
        "zone_type": sensor["zone_type"],
        "pm25": pm25,
        "pm10": pm10,
        "co2_ppm": co2,
        "temperature_c": temp,
        "humidity_pct": round(random.uniform(10, 90), 1),
        "wind_speed_kmh": round(random.uniform(0, 60), 1),
        "aqi_value": aqi,
        "severity": severity_label(aqi),
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }


def ensure_csv_header():
    """Write the CSV header once if the file is new."""
    os.makedirs(DATA_DIR, exist_ok=True)
    new_file = not os.path.exists(CSV_PATH)


def main(minutes: int):
    ensure_csv_header()
    conn = get_connection(schema="RAW")
    cur = conn.cursor()
    print(f"Connected to Snowflake. Simulating for {minutes} minutes "
          f"({len(SENSORS)} sensors, one batch / 10s)...\n")

    end_time = time.time() + minutes * 60
    batch_no = 0
    try:
        while time.time() < end_time:
            batch_no += 1
            readings = [generate_reading(s) for s in SENSORS]

            # 1. append to CSV
            with open(CSV_PATH, "a", newline="") as f:
                csv.DictWriter(f, fieldnames=CSV_COLUMNS).writerows(readings)

            # 2. insert into Snowflake Bronze
            rows = [tuple(r[c] for c in CSV_COLUMNS) for r in readings]
            cur.executemany(INSERT_SQL, rows)
            conn.commit()

            # 3. print alerts for bad air
            for r in readings:
                if r["severity"] in ("UNHEALTHY", "HAZARDOUS"):
                    print(f"  [ALERT] {r['sensor_id']} {r['city']:<10} "
                          f"AQI={r['aqi_value']:<5} {r['severity']}")

            print(f"batch {batch_no}: {len(readings)} readings written -> CSV + Snowflake")
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        cur.close()
        conn.close()
        print("Connection closed. Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=30,
                        help="How long to run (default 30, the hackathon minimum)")
    args = parser.parse_args()
    main(args.minutes)
