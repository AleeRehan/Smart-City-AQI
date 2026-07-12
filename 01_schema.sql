-- ============================================================
-- Smart City AQI — Snowflake Medallion Schema
-- Run this ENTIRE file in a Snowflake worksheet BEFORE loading data.
-- Bronze = RAW, Silver = CLEAN, Gold = ANALYTICS
-- ============================================================

-- 1. Database + three schemas (the medallion layers)
CREATE DATABASE IF NOT EXISTS SMART_CITY_AQI;
CREATE SCHEMA IF NOT EXISTS SMART_CITY_AQI.RAW;        -- Bronze
CREATE SCHEMA IF NOT EXISTS SMART_CITY_AQI.CLEAN;      -- Silver
CREATE SCHEMA IF NOT EXISTS SMART_CITY_AQI.ANALYTICS;  -- Gold

USE DATABASE SMART_CITY_AQI;

-- ============================================================
-- BRONZE — raw data exactly as it arrives
-- ============================================================

CREATE OR REPLACE TABLE RAW.IOT_READINGS (
    reading_id      NUMBER AUTOINCREMENT PRIMARY KEY,
    sensor_id       VARCHAR(30),
    city            VARCHAR(100),
    zone_type       VARCHAR(30),
    pm25            FLOAT,
    pm10            FLOAT,
    co2_ppm         FLOAT,
    temperature_c   FLOAT,
    humidity_pct    FLOAT,
    wind_speed_kmh  FLOAT,
    aqi_value       FLOAT,
    severity        VARCHAR(30),
    recorded_at     TIMESTAMP_NTZ,
    ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE RAW.OPENAQ_RAW (
    raw_id          NUMBER AUTOINCREMENT PRIMARY KEY,
    location_id     INTEGER,
    station_name    VARCHAR(200),
    city            VARCHAR(100),
    country_code    VARCHAR(5),
    latitude        FLOAT,
    longitude       FLOAT,
    pollutant_type  VARCHAR(20),   -- pm25 / pm10 / co2
    pollutant_value FLOAT,
    unit            VARCHAR(20),
    recorded_at     TIMESTAMP_NTZ,
    ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- SILVER — validated, enriched, both sources in one shape
-- ============================================================

CREATE OR REPLACE TABLE CLEAN.AQI_CLEAN (
    clean_id        NUMBER AUTOINCREMENT PRIMARY KEY,
    source          VARCHAR(20),   -- iot_simulator OR openaq_v3
    city            VARCHAR(100),
    sensor_id       VARCHAR(30),   -- NULL for OpenAQ rows
    pm25            FLOAT,
    pm10            FLOAT,
    co2_ppm         FLOAT,
    aqi_value       FLOAT,
    aqi_category    VARCHAR(40),
    health_risk     VARCHAR(10),   -- LOW / MEDIUM / HIGH / CRITICAL
    latitude        FLOAT,
    longitude       FLOAT,
    recorded_at     TIMESTAMP_NTZ,
    processed_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- GOLD — daily aggregates per city (dashboard KPIs)
-- ============================================================

CREATE OR REPLACE TABLE ANALYTICS.CITY_DAILY (
    daily_id        NUMBER AUTOINCREMENT PRIMARY KEY,
    city            VARCHAR(100),
    report_date     DATE,
    avg_aqi         FLOAT,
    max_aqi         FLOAT,
    min_aqi         FLOAT,
    avg_pm25        FLOAT,
    avg_co2         FLOAT,
    dominant_risk   VARCHAR(10),
    reading_count   NUMBER,
    created_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Quick check
SHOW TABLES IN DATABASE SMART_CITY_AQI;
