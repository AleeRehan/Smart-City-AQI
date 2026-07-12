-- ============================================================
-- GOLD — populate ANALYTICS.CITY_DAILY from Silver (CLEAN.AQI_CLEAN)
-- Aggregates every reading (both sources) to one row per city per day.
-- Re-runnable: we truncate first so re-runs don't duplicate days.
-- ============================================================

USE DATABASE SMART_CITY_AQI;

TRUNCATE TABLE ANALYTICS.CITY_DAILY;

INSERT INTO ANALYTICS.CITY_DAILY
    (city, report_date, avg_aqi, max_aqi, min_aqi,
     avg_pm25, avg_co2, dominant_risk, reading_count)
SELECT
    city,
    CAST(recorded_at AS DATE)      AS report_date,
    ROUND(AVG(aqi_value), 1)       AS avg_aqi,
    MAX(aqi_value)                 AS max_aqi,
    MIN(aqi_value)                 AS min_aqi,
    ROUND(AVG(pm25), 1)            AS avg_pm25,
    ROUND(AVG(co2_ppm), 1)         AS avg_co2,
    MODE(health_risk)              AS dominant_risk,   -- most common risk that day
    COUNT(*)                       AS reading_count    -- rows from BOTH sources
FROM CLEAN.AQI_CLEAN
WHERE city IS NOT NULL
GROUP BY city, CAST(recorded_at AS DATE);

-- Verify
SELECT * FROM ANALYTICS.CITY_DAILY ORDER BY report_date DESC, avg_aqi DESC;
