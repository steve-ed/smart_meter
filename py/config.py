"""
Shared configuration for all analysis scripts.
"""

# ---------------------------------------------------------------------------
# Meters
# ---------------------------------------------------------------------------

METERS = {
    1: "1234567891000",
    2: "2234567891000",
    3: "5330642497188",
    4: "1099999999981",
    5: "1099999999990",
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
