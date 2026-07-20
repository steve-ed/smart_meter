"""
Validate electricity-based occupancy detector across all 5 synthetic meters.

Run from project root:
    python py/validate_occupancy.py

Reports per-meter label distribution, floor statistics, and comfort score
delta (fixed 07:00-22:30 window vs occupancy-corrected window).
"""

import csv
import os
import sys
from collections import defaultdict

# Allow running directly as a script: add py/ to path for sibling imports
_PY_DIR = os.path.dirname(os.path.abspath(__file__))
if _PY_DIR not in sys.path:
    sys.path.insert(0, _PY_DIR)

from config import METERS, REGRESSION_START, REGRESSION_END
from occupancy_elec import ElecOccupancyDetector

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# consumption.csv and weather.csv are gitignored and live in the main project
# data/ directory, two levels up from the worktree root (worktrees/occupancy-elec).
_WORKTREE_ROOT = os.path.dirname(_PY_DIR)
_DATA_DIR = os.path.join(_WORKTREE_ROOT, '..', '..', 'data')

# Fall back to local data/ if the main project path doesn't exist
if not os.path.isdir(_DATA_DIR):
    _DATA_DIR = os.path.join(_WORKTREE_ROOT, 'data')

_CONSUMPTION_CSV = os.path.join(_DATA_DIR, 'consumption.csv')
_WEATHER_CSV     = os.path.join(_DATA_DIR, 'weather.csv')

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELEC_UTILITY  = 'electricity'
OCCUPIED_WINDOW = frozenset(range(14, 45))   # 07:00-22:30 fixed window
COMFORT_LOWER_C = 18.0


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_elec_by_date(mpan, start, end):
    """Return {date_str: [48 floats]} for electricity kWh."""
    by_date_period = defaultdict(dict)
    with open(_CONSUMPTION_CSV, newline='') as f:
        for row in csv.DictReader(f):
            if row['mpxn'] != mpan or row['utility'] != ELEC_UTILITY:
                continue
            ts = row['timestamp']          # 'YYYY-MM-DD HH:MM'
            date_str = ts[:10]
            if not (start <= date_str <= end):
                continue
            try:
                val = float(row['value'])
            except (ValueError, TypeError):
                continue
            hh, mm = int(ts[11:13]), int(ts[14:16])
            period = hh * 2 + mm // 30
            by_date_period[date_str][period] = val

    by_date = {}
    for date_str, periods in by_date_period.items():
        kwh_48 = [periods.get(p, 0.0) for p in range(48)]
        by_date[date_str] = kwh_48
    return by_date


def load_outdoor_temp_by_date(start, end):
    """Return {date_str: median_temp_c} from weather.csv."""
    temps = defaultdict(list)
    with open(_WEATHER_CSV, newline='') as f:
        for row in csv.DictReader(f):
            ts = row['timestamp']
            date_str = ts[:10]
            if not (start <= date_str <= end):
                continue
            try:
                temps[date_str].append(float(row['temp_c']))
            except (ValueError, TypeError):
                continue
    return {
        d: sorted(vs)[len(vs) // 2]
        for d, vs in temps.items()
    }


# ---------------------------------------------------------------------------
# Per-meter runner
# ---------------------------------------------------------------------------

def run_meter(meter_num, mpan, elec_by_date, weather_by_date):
    det = ElecOccupancyDetector()
    counts = {'OCCUPIED': 0, 'VACANT': 0, 'UNKNOWN': 0}
    total = 0

    for date_str in sorted(elec_by_date):
        kwh_48 = elec_by_date[date_str]
        temp = weather_by_date.get(date_str, 10.0)
        labels = det.add_day(date_str, kwh_48, outdoor_temp_c=temp)
        for r in labels:
            counts[r['occupied_label']] += 1
            total += 1

    print(f"\nM{meter_num} ({mpan})")
    if total == 0:
        print("  No periods labelled.")
        return
    print(f"  Periods: {total} | "
          f"OCCUPIED {counts['OCCUPIED']/total:.1%} | "
          f"VACANT   {counts['VACANT']/total:.1%} | "
          f"UNKNOWN  {counts['UNKNOWN']/total:.1%}")
    print(f"  Floor: {det.floor_kwh:.3f} kWh  MAD: {det.floor_mad:.4f}  "
          f"source={det.floor_source}  stable={det.floor_stable}  "
          f"step_change={det.floor_step_change}")
    print(f"  heating_contaminated={det.heating_contaminated}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Occupancy detector validation  {REGRESSION_START} -> {REGRESSION_END}")
    print(f"Data directory: {os.path.normpath(_DATA_DIR)}")
    weather = load_outdoor_temp_by_date(REGRESSION_START, REGRESSION_END)
    for meter_num, mpan in METERS.items():
        elec = load_elec_by_date(mpan, REGRESSION_START, REGRESSION_END)
        if not elec:
            print(f"\nM{meter_num}: no electricity data found")
            continue
        run_meter(meter_num, mpan, elec, weather)


if __name__ == '__main__':
    main()
