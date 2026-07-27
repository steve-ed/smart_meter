"""
Shared configuration for all analysis scripts.
"""

# ---------------------------------------------------------------------------
# Meters
# ---------------------------------------------------------------------------

METERS = {
    1:  "1234567891000",
    2:  "2234567891000",
    3:  "5330642497188",
    4:  "1099999999981",
    5:  "1099999999990",
    6:  "1234567891004",
    7:  "1234567891006",
    8:  "1234567891012",
    9:  "1234567891014",
    10: "1234567891020",
    11: "1234567891022",
    12: "1234567891028",
    13: "1234567891036",
    14: "1234567891038",
    # M15 has no gas meter
}

METER_MPANS = list(METERS.values())

# ---------------------------------------------------------------------------
# Location (West Yorkshire — used for weather API and PVGIS)
# ---------------------------------------------------------------------------

LAT = 53.6
LON = -1.32

# ---------------------------------------------------------------------------
# Analysis windows
#
# WINTER_START / WINTER_END  — single 6-month comparison window.
#   All 5 meters have complete gas + electricity data across this period.
#   Use for cross-meter analysis, HDD regression, and Tier 4 decay profiling.
#
# REGRESSION_START / REGRESSION_END  — two full heating seasons.
#   Better for HDD regression (averages out year-to-year weather variability).
#   Preferred for Tier 2 services #5, #6, #7.
# ---------------------------------------------------------------------------

WINTER_START = "2024-10-01"   # Oct 2024
WINTER_END   = "2025-03-31"   # Mar 2025

REGRESSION_START = "2023-10-01"   # Oct 2023
REGRESSION_END   = "2025-03-31"   # Mar 2025

# ---------------------------------------------------------------------------
# Energy constants
# ---------------------------------------------------------------------------

GAS_KWH_PER_M3   = 11.2   # calorific value conversion (standard UK)
GAS_RATE_P_KWH   = 6.0    # pence/kWh (Ofgem price cap — update as needed)
ELEC_RATE_P_KWH  = 24.0   # pence/kWh (Ofgem price cap — update as needed)

GAS_CAP_M3       = 2.0    # m³/half-hour — sentinel value filter
ELEC_CAP_KWH     = 15.0   # kWh/half-hour — above any plausible domestic reading

# ---------------------------------------------------------------------------
# Carbon intensity API
# ---------------------------------------------------------------------------

CARBON_REGION_ID = 12   # West Yorkshire DNO region (National Grid ESO)

# ---------------------------------------------------------------------------
# Meter metadata (property type / build era for HDD benchmarking)
# ---------------------------------------------------------------------------

METER_META = {
    1:  {"property_type": "semi",     "build_era": "1945_1980"},
    2:  {"property_type": "semi",     "build_era": "post_1980"},
    3:  {"property_type": "detached", "build_era": "post_1980"},
    4:  {"property_type": "terraced", "build_era": "pre_1945"},
    5:  {"property_type": "semi",     "build_era": "post_1980"},
    6:  {"property_type": "semi", "build_era": "1945_1980", "build_year": 1975},
    7:  {"property_type": "semi", "build_era": "1945_1980", "build_year": 1980},
    8:  {"property_type": "semi", "build_era": "post_1980", "build_year": 1985},
    9:  {"property_type": "semi", "build_era": "post_1980", "build_year": 1990},
    10: {"property_type": "semi", "build_era": "post_1980", "build_year": 1995},
    11: {"property_type": "semi", "build_era": "post_1980", "build_year": 2000},
    12: {"property_type": "semi", "build_era": "post_1980", "build_year": 2005},
    13: {"property_type": "semi", "build_era": "post_1980", "build_year": 2010},
    14: {"property_type": "semi", "build_era": "post_1980", "build_year": 2015},
    15: {"property_type": "semi", "build_era": "post_1980", "build_year": 2020},
}

# ---------------------------------------------------------------------------
# Electricity MPANs (separate from gas MPXNs in METERS)
# ---------------------------------------------------------------------------

ELEC_METERS = {
    1:  "1234567891000",
    2:  "1234567891002",
    3:  "1234567891008",
    4:  "1234567891010",
    5:  "1234567891024",
    6:  "1234567891004",
    7:  "1234567891006",
    8:  "1234567891012",
    9:  "1234567891014",
    10: "1234567891020",
    11: "1234567891022",
    12: "1234567891028",
    13: "1234567891036",
    14: "1234567891038",
    15: "0061448158717",
}

# ---------------------------------------------------------------------------
# Solar generation meter MPXNs (separate generation meter per household)
# ---------------------------------------------------------------------------

SOLAR_METERS = {
    2:  "2234567891000",
    3:  "5330642497188",
    14: "1234567891038",
}

SEG_RATE_P_KWH = 15.0   # Smart Export Guarantee pence/kWh
