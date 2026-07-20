"""
Electricity-based occupancy detector.

Infers OCCUPIED / VACANT / UNKNOWN labels from half-hourly electricity
consumption using an always-on floor approach. Slots into the Tier 3
signal fusion stack at positions 4.5 (OCCUPIED) and 6.5 (VACANT).

See docs/superpowers/specs/2026-07-20-occupancy-electricity-design.md
"""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OVERNIGHT_PERIODS    = frozenset(range(2, 11))  # 01:00–05:30 (period indices 2–10)
FLOOR_PERCENTILE     = 20
MIN_NIGHTS           = 14
COLD_START_FLOOR_KWH = 0.030

OCCUPIED_EXCESS_KWH  = 0.05
OCCUPIED_SOFT_KWH    = 0.025

VACANT_RATIO         = 1.40
VACANT_MIN_PERIODS   = 6

HEATING_GUARD_KWH    = 0.50
HEATING_GUARD_TEMP_C = 7.0

FLOOR_STABILITY_PCT  = 0.25
FLOOR_STEP_WEEKS     = 3
ROLLING_WEEKS        = 8

_SOFT_PENDING = '_soft_pending'  # internal marker, cleaned up before returning

# ---------------------------------------------------------------------------
# Floor computation
# ---------------------------------------------------------------------------

def compute_floor(samples):
    """Return (floor_kwh at P20, floor_mad) from a list of kWh readings."""
    if not samples:
        return (0.0, 0.0)
    s = sorted(samples)
    n = len(s)
    idx = max(0, int(n * FLOOR_PERCENTILE / 100))
    floor = s[idx]
    raw_mad = sorted(abs(v - floor) for v in s)[n // 2]
    return (floor, max(raw_mad, 0.005))
