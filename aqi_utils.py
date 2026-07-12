"""
aqi_utils.py
Shared air-quality math so the simulator, ETL and OpenAQ enrichment
all use the SAME formula. Import from here everywhere.
"""

# EPA PM2.5 breakpoints:
# (PM2.5 low, PM2.5 high, AQI low, AQI high, category label)
BREAKPOINTS = [
    (0.0,   12.0,   0,   50,  "Good"),
    (12.1,  35.4,   51,  100, "Moderate"),
    (35.5,  55.4,   101, 150, "Unhealthy for Sensitive"),
    (55.5,  150.4,  151, 200, "Unhealthy"),
    (150.5, 250.4,  201, 300, "Very Unhealthy"),
    (250.5, 500.4,  301, 500, "Hazardous"),
]


def calculate_aqi(pm25: float) -> float:
    """
    Convert a PM2.5 concentration (ug/m3) into an AQI value using the
    EPA piecewise-linear formula:
        AQI = ((I_hi - I_lo) / (C_hi - C_lo)) * (PM2.5 - C_lo) + I_lo
    """
    if pm25 is None:
        return None
    pm25 = max(0.0, float(pm25))
    for c_lo, c_hi, i_lo, i_hi, _label in BREAKPOINTS:
        if c_lo <= pm25 <= c_hi:
            return round(((i_hi - i_lo) / (c_hi - c_lo)) * (pm25 - c_lo) + i_lo, 1)
    # Above the top breakpoint -> cap at 500
    return 500.0


def aqi_category(pm25: float) -> str:
    """Return the full EPA category label (6 levels) for a PM2.5 value."""
    if pm25 is None:
        return None
    pm25 = max(0.0, float(pm25))
    for c_lo, c_hi, _i_lo, _i_hi, label in BREAKPOINTS:
        if c_lo <= pm25 <= c_hi:
            return label
    return "Hazardous"


def severity_label(aqi: float) -> str:
    """
    Coarse 4-level label stored in the Bronze IoT table
    (GOOD / MODERATE / UNHEALTHY / HAZARDOUS).
    """
    if aqi is None:
        return None
    if aqi <= 50:
        return "GOOD"
    if aqi <= 100:
        return "MODERATE"
    if aqi <= 200:
        return "UNHEALTHY"
    return "HAZARDOUS"


def health_risk(category: str) -> str:
    """
    Map the EPA category to the 4 risk buckets used in Silver:
      LOW      = Good / Moderate
      MEDIUM   = Unhealthy for Sensitive
      HIGH     = Unhealthy / Very Unhealthy
      CRITICAL = Hazardous
    """
    if category is None:
        return None
    mapping = {
        "Good": "LOW",
        "Moderate": "LOW",
        "Unhealthy for Sensitive": "MEDIUM",
        "Unhealthy": "HIGH",
        "Very Unhealthy": "HIGH",
        "Hazardous": "CRITICAL",
    }
    return mapping.get(category, "LOW")
