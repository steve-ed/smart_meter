# Electricity-Based Occupancy Detector — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `py/occupancy_elec.py` — an always-on-floor-based occupancy detector that labels each 30-min period OCCUPIED / VACANT / UNKNOWN from electricity data alone, slotting into the Tier 3 signal fusion stack.

**Architecture:** Pure functions (`compute_floor`, `is_heating_contaminated`, `compute_thresholds`, `label_sequence`) plus a stateful `ElecOccupancyDetector` class that maintains a rolling 8-week overnight sample, updates the floor weekly, and handles cold-start. A validation script runs all five synthetic meters and reports label distributions and comfort score deltas.

**Tech Stack:** Python 3.11+, pytest, stdlib only (no numpy/pandas — matches all existing analysis scripts in this repo)

**Spec:** `docs/superpowers/specs/2026-07-20-occupancy-electricity-design.md`

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `py/occupancy_elec.py` | Create | Constants, pure functions, ElecOccupancyDetector class |
| `tests/conftest.py` | Create | Add `py/` to sys.path so imports work |
| `tests/test_occupancy_elec.py` | Create | Unit tests for all functions and the detector class |
| `py/validate_occupancy.py` | Create | End-to-end run across all 5 synthetic meters |

---

## Task 1: Test infrastructure

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_occupancy_elec.py`

- [ ] **Step 1: Create conftest.py**

```python
# tests/conftest.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'py'))
```

- [ ] **Step 2: Create test file with a placeholder test**

```python
# tests/test_occupancy_elec.py
def test_placeholder():
    assert 1 + 1 == 2
```

- [ ] **Step 3: Verify pytest runs from the project root**

```
python -m pytest tests/test_occupancy_elec.py -v
```

Expected:
```
tests/test_occupancy_elec.py::test_placeholder PASSED
1 passed in 0.00s
```

If pytest is not installed: `pip install pytest`

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_occupancy_elec.py
git commit -m "test: add test infrastructure for occupancy_elec"
```

---

## Task 2: `compute_floor()`

**Files:**
- Create: `py/occupancy_elec.py`
- Modify: `tests/test_occupancy_elec.py`

- [ ] **Step 1: Write failing tests**

Replace the contents of `tests/test_occupancy_elec.py`:

```python
# tests/test_occupancy_elec.py
import pytest
from occupancy_elec import compute_floor


def test_compute_floor_returns_p20():
    # 10 values sorted: [0.02,0.02,0.03,0.04,0.05,0.06,0.10,0.15,0.20,0.30]
    # P20 = index int(10*0.20)=2 → 0.03
    samples = [0.02, 0.02, 0.03, 0.04, 0.05, 0.06, 0.10, 0.15, 0.20, 0.30]
    floor, _ = compute_floor(samples)
    assert floor == pytest.approx(0.03)


def test_compute_floor_mad_minimum_enforced():
    # All identical → raw MAD = 0 → clamped to 0.005
    floor, mad = compute_floor([0.05] * 20)
    assert mad == pytest.approx(0.005)


def test_compute_floor_mad_reflects_spread():
    samples = [0.02, 0.02, 0.03, 0.04, 0.05, 0.06, 0.10, 0.15, 0.20, 0.30]
    _, mad = compute_floor(samples)
    assert mad > 0.005


def test_compute_floor_empty_returns_zeros():
    floor, mad = compute_floor([])
    assert floor == 0.0
    assert mad == 0.0


def test_compute_floor_single_value():
    floor, mad = compute_floor([0.04])
    assert floor == pytest.approx(0.04)
    assert mad == pytest.approx(0.005)
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest tests/test_occupancy_elec.py -v
```

Expected: all 5 FAIL with `ImportError`.

- [ ] **Step 3: Create `py/occupancy_elec.py` with constants and `compute_floor()`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_occupancy_elec.py -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add py/occupancy_elec.py tests/test_occupancy_elec.py
git commit -m "feat: add compute_floor() — P20 and MAD from overnight samples"
```

---

## Task 3: `is_heating_contaminated()` and `compute_thresholds()`

**Files:**
- Modify: `py/occupancy_elec.py`
- Modify: `tests/test_occupancy_elec.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_occupancy_elec.py`:

```python
from occupancy_elec import is_heating_contaminated, compute_thresholds


# --- is_heating_contaminated ---

def test_heating_contaminated_when_both_conditions_met():
    assert is_heating_contaminated(0.6, 5.0) is True


def test_heating_not_contaminated_warm_outdoor():
    # outdoor temp above threshold → not contaminated even with high load
    assert is_heating_contaminated(0.6, 8.0) is False


def test_heating_not_contaminated_low_overnight_load():
    # load below threshold → not contaminated even when cold
    assert is_heating_contaminated(0.4, 5.0) is False


def test_heating_not_contaminated_at_exact_boundaries():
    # strictly greater / strictly less required — boundary values are not contaminated
    assert is_heating_contaminated(0.50, 7.0) is False


# --- compute_thresholds ---

def test_compute_thresholds_minimum_excess_dominates():
    # floor_mad = 0.005 → 3×MAD = 0.015 < 0.05, so hard = floor + 0.05
    hard, soft = compute_thresholds(floor_kwh=0.03, floor_mad=0.005)
    assert hard == pytest.approx(0.03 + 0.05)    # 0.08
    assert soft == pytest.approx(0.03 + 0.025)   # 0.055


def test_compute_thresholds_mad_dominates():
    # floor_mad = 0.02 → 3×MAD = 0.06 > 0.05
    hard, soft = compute_thresholds(floor_kwh=0.03, floor_mad=0.02)
    assert hard == pytest.approx(0.03 + 0.06)    # 0.09
    assert soft == pytest.approx(0.03 + 0.03)    # 0.06


def test_compute_thresholds_hard_always_exceeds_soft():
    for mad in [0.005, 0.01, 0.02, 0.05]:
        hard, soft = compute_thresholds(floor_kwh=0.05, floor_mad=mad)
        assert hard > soft, f"hard {hard} should exceed soft {soft} at mad={mad}"
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest tests/test_occupancy_elec.py -v -k "heating or thresholds"
```

Expected: all FAIL with `ImportError`.

- [ ] **Step 3: Add both functions to `py/occupancy_elec.py`**

Add after `compute_floor()`:

```python
# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def is_heating_contaminated(overnight_median_kwh, outdoor_temp_c):
    """True when electric heating is likely corrupting the overnight floor."""
    return overnight_median_kwh > HEATING_GUARD_KWH and outdoor_temp_c < HEATING_GUARD_TEMP_C


def compute_thresholds(floor_kwh, floor_mad):
    """Return (hard_threshold_kwh, soft_threshold_kwh) for OCCUPIED detection."""
    hard = floor_kwh + max(OCCUPIED_EXCESS_KWH, 3.0 * floor_mad)
    soft = floor_kwh + max(OCCUPIED_SOFT_KWH,  1.5 * floor_mad)
    return (hard, soft)
```

- [ ] **Step 4: Run all tests**

```
python -m pytest tests/test_occupancy_elec.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add py/occupancy_elec.py tests/test_occupancy_elec.py
git commit -m "feat: add is_heating_contaminated() and compute_thresholds()"
```

---

## Task 4: `label_sequence()` — OCCUPIED logic

Implement `label_sequence()` with hard and soft OCCUPIED thresholds. VACANT is not yet implemented — at-floor periods return UNKNOWN. Task 5 extends this.

**Files:**
- Modify: `py/occupancy_elec.py`
- Modify: `tests/test_occupancy_elec.py`

- [ ] **Step 1: Write failing OCCUPIED tests**

Append to `tests/test_occupancy_elec.py`:

```python
from occupancy_elec import label_sequence, COLD_START_FLOOR_KWH, OCCUPIED_EXCESS_KWH


def _periods(value, count=48):
    return [value] * count


def test_hard_threshold_single_period_occupied():
    # floor=0.03, hard=0.08; one period at 0.10 → immediate OCCUPIED
    kwh = _periods(0.02)
    kwh[10] = 0.10
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert labels[10]['occupied_label'] == 'OCCUPIED'
    assert labels[10]['label_source'] == 'elec_above_floor_hard'


def test_soft_threshold_single_period_is_unknown():
    # One period above soft (0.055) but below hard (0.08) → UNKNOWN (pending)
    kwh = _periods(0.02)
    kwh[10] = 0.06
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert labels[10]['occupied_label'] == 'UNKNOWN'
    assert labels[10]['label_source'] is None  # pending marker cleaned up


def test_soft_threshold_two_consecutive_both_occupied():
    # Two consecutive above-soft → both back-labelled OCCUPIED
    kwh = _periods(0.02)
    kwh[10] = 0.06
    kwh[11] = 0.06
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert labels[10]['occupied_label'] == 'OCCUPIED'
    assert labels[11]['occupied_label'] == 'OCCUPIED'
    assert labels[10]['label_source'] == 'elec_above_floor_soft'
    assert labels[11]['label_source'] == 'elec_above_floor_soft'


def test_soft_threshold_resets_after_non_soft_period():
    # above-soft, gap, above-soft — each individual soft period is UNKNOWN
    kwh = _periods(0.02)
    kwh[10] = 0.06
    # kwh[11] stays at 0.02 (gap)
    kwh[12] = 0.06
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert labels[10]['occupied_label'] == 'UNKNOWN'
    assert labels[12]['occupied_label'] == 'UNKNOWN'


def test_cold_start_hard_threshold_uses_population_floor():
    # During cold start: hard = COLD_START_FLOOR_KWH + OCCUPIED_EXCESS_KWH = 0.08
    kwh = _periods(0.02)
    kwh[10] = 0.09  # above population hard (0.08)
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005, in_cold_start=True)
    assert labels[10]['occupied_label'] == 'OCCUPIED'


def test_cold_start_no_soft_threshold():
    # Cold start disables soft threshold; two above-soft periods → still UNKNOWN
    kwh = _periods(0.02)
    kwh[10] = 0.06  # above household soft but below population hard (0.08)
    kwh[11] = 0.06
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005, in_cold_start=True)
    assert labels[10]['occupied_label'] == 'UNKNOWN'
    assert labels[11]['occupied_label'] == 'UNKNOWN'


def test_output_contains_required_fields():
    kwh = _periods(0.02)
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert len(labels) == 48
    required = {
        'period_index', 'elec_kwh', 'floor_kwh', 'floor_mad_kwh',
        'floor_source', 'floor_stable', 'heating_contaminated',
        'at_floor', 'occupied_label', 'label_source', 'sustained_run',
    }
    assert required <= labels[0].keys()
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest tests/test_occupancy_elec.py -v -k "hard or soft or cold_start or fields"
```

Expected: all FAIL with `ImportError`.

- [ ] **Step 3: Implement `label_sequence()` in `py/occupancy_elec.py`**

Add after `compute_thresholds()`:

```python
# ---------------------------------------------------------------------------
# Sequence labeller
# ---------------------------------------------------------------------------

def label_sequence(elec_kwh, floor_kwh, floor_mad,
                   heating_contaminated=False, in_cold_start=False):
    """
    Label 48 half-hourly periods as OCCUPIED / VACANT / UNKNOWN.

    floor_source and floor_stable in output are placeholder values
    ('overnight_bootstrap', True) — overwrite them from ElecOccupancyDetector.
    """
    if in_cold_start:
        hard_thresh = COLD_START_FLOOR_KWH + OCCUPIED_EXCESS_KWH
        soft_thresh = None
    else:
        hard_thresh, soft_thresh = compute_thresholds(floor_kwh, floor_mad)

    results = []
    soft_run = 0
    floor_run = 0
    floor_run_start = -1
    vacant_active = False

    for i, kwh in enumerate(elec_kwh):
        is_overnight = i in OVERNIGHT_PERIODS
        above_hard = kwh >= hard_thresh
        above_soft = (not in_cold_start) and (soft_thresh is not None) and (kwh >= soft_thresh)
        at_floor_raw = kwh <= floor_kwh * VACANT_RATIO
        # Suppress at-floor vacancy overnight when electric heating is contaminating the floor
        at_floor = at_floor_raw and not (heating_contaminated and is_overnight)

        label = 'UNKNOWN'
        label_source = None

        if above_hard:
            label = 'OCCUPIED'
            label_source = 'elec_above_floor_hard'
            soft_run = 0
            floor_run = 0
            floor_run_start = -1
            vacant_active = False

        elif above_soft:
            soft_run += 1
            floor_run = 0
            floor_run_start = -1
            if soft_run >= 2:
                label = 'OCCUPIED'
                label_source = 'elec_above_floor_soft'
                vacant_active = False
                if results and results[-1]['label_source'] == _SOFT_PENDING:
                    results[-1]['occupied_label'] = 'OCCUPIED'
                    results[-1]['label_source'] = 'elec_above_floor_soft'
            else:
                label = 'UNKNOWN'
                label_source = _SOFT_PENDING

        elif at_floor:
            soft_run = 0
            if floor_run_start == -1:
                floor_run_start = i
            floor_run += 1
            if vacant_active:
                label = 'VACANT'
                label_source = 'elec_at_floor'
            elif floor_run >= VACANT_MIN_PERIODS:
                label = 'VACANT'
                label_source = 'elec_at_floor'
                vacant_active = True
                for j in range(floor_run_start, i):
                    results[j]['occupied_label'] = 'VACANT'
                    results[j]['label_source'] = 'elec_at_floor'
            else:
                label = 'UNKNOWN'

        else:
            soft_run = 0
            floor_run = 0
            floor_run_start = -1
            vacant_active = False

        results.append({
            'period_index':         i,
            'elec_kwh':             kwh,
            'floor_kwh':            floor_kwh,
            'floor_mad_kwh':        floor_mad,
            'floor_source':         'overnight_bootstrap',
            'floor_stable':         True,
            'heating_contaminated': heating_contaminated,
            'at_floor':             at_floor_raw,
            'occupied_label':       label,
            'label_source':         label_source,
            'sustained_run':        floor_run if at_floor else (soft_run if above_soft else 0),
        })

    for r in results:
        if r['label_source'] == _SOFT_PENDING:
            r['label_source'] = None

    return results
```

- [ ] **Step 4: Run all tests**

```
python -m pytest tests/test_occupancy_elec.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add py/occupancy_elec.py tests/test_occupancy_elec.py
git commit -m "feat: add label_sequence() with OCCUPIED detection"
```

---

## Task 5: `label_sequence()` — VACANT tests

The VACANT logic is already present in the implementation from Task 4. This task writes the tests that verify it.

**Files:**
- Modify: `tests/test_occupancy_elec.py`

- [ ] **Step 1: Write VACANT tests**

Append to `tests/test_occupancy_elec.py`:

```python
from occupancy_elec import OVERNIGHT_PERIODS


def test_fewer_than_6_at_floor_periods_are_unknown():
    # 5 consecutive at-floor periods → all UNKNOWN (not enough for VACANT)
    # floor=0.03, at_floor threshold = 0.03 × 1.40 = 0.042
    kwh = _periods(0.10)   # all above floor
    for i in range(20, 25):
        kwh[i] = 0.03      # 5 at-floor periods
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    for i in range(20, 25):
        assert labels[i]['occupied_label'] == 'UNKNOWN', f"period {i} should be UNKNOWN"


def test_six_consecutive_at_floor_back_labels_all_vacant():
    kwh = _periods(0.10)
    for i in range(20, 26):
        kwh[i] = 0.03      # 6 at-floor periods
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    for i in range(20, 26):
        assert labels[i]['occupied_label'] == 'VACANT', f"period {i} should be VACANT"
        assert labels[i]['label_source'] == 'elec_at_floor'


def test_vacant_continues_after_6_periods():
    kwh = _periods(0.10)
    for i in range(20, 38):
        kwh[i] = 0.03      # 18 at-floor periods
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    for i in range(20, 38):
        assert labels[i]['occupied_label'] == 'VACANT'


def test_hard_threshold_breaks_vacant_run_and_requires_new_accumulation():
    # All at floor → VACANT from period 5. Hard spike at 20 → breaks.
    # Must re-accumulate 6 more at-floor periods before VACANT re-asserts.
    kwh = _periods(0.03)
    kwh[20] = 0.10         # hard OCCUPIED during VACANT
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert labels[20]['occupied_label'] == 'OCCUPIED'
    assert labels[21]['occupied_label'] == 'UNKNOWN'   # run reset, only 1 at-floor
    assert labels[26]['occupied_label'] == 'VACANT'    # 6 at-floor periods after break


def test_single_soft_period_does_not_break_vacant():
    # One above-soft (but below hard) period during VACANT: that period is UNKNOWN
    # but VACANT resumes immediately on the next at-floor period (vacant_active stays True)
    # floor=0.03, soft=0.055, hard=0.08
    kwh = _periods(0.03)
    kwh[20] = 0.06         # above soft, single period
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert labels[20]['occupied_label'] == 'UNKNOWN'
    assert labels[21]['occupied_label'] == 'VACANT'    # VACANT resumes


def test_two_consecutive_soft_breaks_vacant():
    # Two consecutive soft periods during VACANT → OCCUPIED asserted, VACANT terminates
    kwh = _periods(0.03)   # all at floor → VACANT from period 5
    kwh[20] = 0.06
    kwh[21] = 0.06
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert labels[20]['occupied_label'] == 'OCCUPIED'
    assert labels[21]['occupied_label'] == 'OCCUPIED'
    assert labels[22]['occupied_label'] == 'UNKNOWN'   # run reset, 1 at-floor only
    assert labels[27]['occupied_label'] == 'VACANT'    # re-asserts after 6 new at-floor


def test_heating_contaminated_suppresses_overnight_vacant():
    # All periods at floor, but overnight periods (2–10) don't count toward floor run
    kwh = _periods(0.03)
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005, heating_contaminated=True)
    for i in range(2, 11):
        assert labels[i]['occupied_label'] == 'UNKNOWN', f"overnight period {i} must not be VACANT"
    # Periods 0–1 accumulate (run=2), reset at period 2
    # Period 11 starts fresh: run reaches 6 at period 16 → back-labels 11–15
    for i in range(11, 17):
        assert labels[i]['occupied_label'] == 'VACANT'


def test_at_floor_field_reflects_raw_value_regardless_of_contamination():
    # at_floor in output is the raw boolean (elec ≤ floor × VACANT_RATIO),
    # independent of whether VACANT is asserted
    kwh = _periods(0.03)
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005, heating_contaminated=True)
    for i in range(2, 11):
        assert labels[i]['at_floor'] is True   # raw condition is True even when VACANT suppressed
```

- [ ] **Step 2: Run all tests**

```
python -m pytest tests/test_occupancy_elec.py -v
```

Expected: all PASS. If any fail, inspect the trace — the VACANT logic in Task 4's implementation should handle all these cases correctly.

- [ ] **Step 3: Commit**

```bash
git add tests/test_occupancy_elec.py
git commit -m "test: add VACANT detection tests for label_sequence()"
```

---

## Task 6: `ElecOccupancyDetector` class

**Files:**
- Modify: `py/occupancy_elec.py`
- Modify: `tests/test_occupancy_elec.py`

- [ ] **Step 1: Write failing detector tests**

Append to `tests/test_occupancy_elec.py`:

```python
from occupancy_elec import ElecOccupancyDetector, MIN_NIGHTS


def test_detector_is_in_cold_start_initially():
    det = ElecOccupancyDetector()
    assert det.in_cold_start is True


def test_detector_exits_cold_start_after_min_nights():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-10-01', _periods(0.03), outdoor_temp_c=10.0)
    assert det.in_cold_start is False


def test_detector_floor_computed_at_cold_start_end():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-10-01', _periods(0.04), outdoor_temp_c=10.0)
    assert det.floor_kwh > 0.0


def test_detector_cold_start_labels_non_triggered_as_unknown():
    det = ElecOccupancyDetector()
    # During cold start, only population-floor OCCUPIED fires; all other periods → UNKNOWN
    labels = det.add_day('2024-10-01', _periods(0.03), outdoor_temp_c=10.0)
    non_occupied = [r for r in labels if r['occupied_label'] != 'OCCUPIED']
    assert all(r['occupied_label'] == 'UNKNOWN' for r in non_occupied)


def test_detector_returns_48_periods():
    det = ElecOccupancyDetector()
    labels = det.add_day('2024-10-01', _periods(0.04), outdoor_temp_c=10.0)
    assert len(labels) == 48


def test_detector_unstable_floor_holds_previous_value():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-10-01', _periods(0.04), outdoor_temp_c=10.0)
    stable_floor = det.floor_kwh
    # Feed 7 days of very different overnight values → triggers weekly update with big jump
    for _ in range(7):
        det.add_day('2024-10-15', _periods(0.20), outdoor_temp_c=10.0)
    assert det.floor_stable is False
    assert det.floor_kwh == pytest.approx(stable_floor)


def test_detector_step_change_accepted_after_3_unstable_weeks():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-10-01', _periods(0.04), outdoor_temp_c=10.0)
    original_floor = det.floor_kwh
    # 3 × 7 = 21 days of very different overnight values → 3 weekly updates → step change
    for _ in range(21):
        det.add_day('2024-10-15', _periods(0.20), outdoor_temp_c=10.0)
    assert det.floor_step_change is True
    assert det.floor_kwh > original_floor


def test_detector_sensor_calibrated_floor_source():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-10-01', _periods(0.04), outdoor_temp_c=10.0)
    confirmed = [(i, 0.02) for i in range(48)]
    # Floor updates at MIN_NIGHTS (day 14) and then every 7 days.
    # 7 more days with confirmed_vacant → update triggers at day 21 → sensor_calibrated
    for _ in range(7):
        det.add_day('2024-10-15', _periods(0.04), outdoor_temp_c=10.0,
                    confirmed_vacant=confirmed)
    assert det.floor_source == 'sensor_calibrated'


def test_detector_heating_contamination_activates():
    det = ElecOccupancyDetector()
    # High overnight load + cold outdoor → heating guard triggers
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-01-01', _periods(0.60), outdoor_temp_c=3.0)
    assert det.heating_contaminated is True


def test_detector_heating_contamination_does_not_activate_when_warm():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-07-01', _periods(0.10), outdoor_temp_c=18.0)
    assert det.heating_contaminated is False
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest tests/test_occupancy_elec.py -v -k "detector"
```

Expected: all FAIL with `ImportError`.

- [ ] **Step 3: Implement `ElecOccupancyDetector` in `py/occupancy_elec.py`**

Add at the end of the file:

```python
# ---------------------------------------------------------------------------
# Stateful detector
# ---------------------------------------------------------------------------

class ElecOccupancyDetector:
    """Maintains a rolling always-on floor and labels periods day by day."""

    def __init__(self):
        self._overnight_samples = []
        self._days_accumulated = 0
        self._prior_floor = None
        self._unstable_weeks = 0
        self._outdoor_temps = []

        self.floor_kwh = 0.0
        self.floor_mad = 0.005
        self.floor_source = 'overnight_bootstrap'
        self.floor_stable = True
        self.floor_step_change = False
        self.heating_contaminated = False

    @property
    def in_cold_start(self):
        return self._days_accumulated < MIN_NIGHTS

    def add_day(self, date_str, elec_kwh_48, outdoor_temp_c, confirmed_vacant=None):
        """
        Process one day of 48 half-hourly readings.

        date_str: 'YYYY-MM-DD'
        elec_kwh_48: list of 48 floats
        outdoor_temp_c: daily outdoor temperature
        confirmed_vacant: list of (period_index, kwh) from higher-priority sensor signals
        Returns: list of 48 period dicts matching the output schema.
        """
        for p in OVERNIGHT_PERIODS:
            self._overnight_samples.append(elec_kwh_48[p])
        self._days_accumulated += 1

        max_samples = ROLLING_WEEKS * 7 * len(OVERNIGHT_PERIODS)
        if len(self._overnight_samples) > max_samples:
            self._overnight_samples = self._overnight_samples[-max_samples:]

        # Update floor at cold-start exit and every 7 days thereafter
        if (self._days_accumulated == MIN_NIGHTS or
                (not self.in_cold_start and self._days_accumulated % 7 == 0)):
            self._update_floor(confirmed_vacant)

        # Rolling 14-day outdoor temperature for heating guard
        self._outdoor_temps.append(outdoor_temp_c)
        if len(self._outdoor_temps) > 14:
            self._outdoor_temps = self._outdoor_temps[-14:]

        if len(self._outdoor_temps) >= 7 and self._overnight_samples:
            n_recent = 7 * len(OVERNIGHT_PERIODS)
            recent_overnight = self._overnight_samples[-n_recent:]
            overnight_med = sorted(recent_overnight)[len(recent_overnight) // 2]
            outdoor_med = sorted(self._outdoor_temps)[len(self._outdoor_temps) // 2]
            self.heating_contaminated = is_heating_contaminated(overnight_med, outdoor_med)

        labels = label_sequence(
            elec_kwh=elec_kwh_48,
            floor_kwh=self.floor_kwh,
            floor_mad=self.floor_mad,
            heating_contaminated=self.heating_contaminated,
            in_cold_start=self.in_cold_start,
        )
        for r in labels:
            r['floor_source'] = self.floor_source
            r['floor_stable'] = self.floor_stable

        return labels

    def _update_floor(self, confirmed_vacant=None):
        if confirmed_vacant:
            samples = [kwh for _, kwh in confirmed_vacant]
            self.floor_source = 'sensor_calibrated'
        else:
            samples = self._overnight_samples
            self.floor_source = 'overnight_bootstrap'

        new_floor, new_mad = compute_floor(samples)

        if self._prior_floor is not None:
            change = abs(new_floor - self._prior_floor) / max(self._prior_floor, 1e-6)
            if change > FLOOR_STABILITY_PCT:
                self._unstable_weeks += 1
                self.floor_stable = False
                if self._unstable_weeks >= FLOOR_STEP_WEEKS:
                    self.floor_kwh = new_floor
                    self.floor_mad = new_mad
                    self.floor_step_change = True
                    self._unstable_weeks = 0
                    self.floor_stable = True
                    self._prior_floor = new_floor
                return   # hold previous value until step change confirmed
            else:
                self._unstable_weeks = 0
                self.floor_stable = True

        self.floor_kwh = new_floor
        self.floor_mad = new_mad
        self._prior_floor = new_floor
```

- [ ] **Step 4: Run all tests**

```
python -m pytest tests/test_occupancy_elec.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add py/occupancy_elec.py tests/test_occupancy_elec.py
git commit -m "feat: add ElecOccupancyDetector class with rolling floor and cold-start"
```

---

## Task 7: Validation script

**Files:**
- Create: `py/validate_occupancy.py`

Run the detector across all five synthetic meters and report label distributions and floor statistics. No ground-truth comparison is required — the synthetic model's occupancy schedules are implicit in its heating patterns, and the primary validation target is that (a) cold-start completes cleanly, (b) UNKNOWN drops after week 2, and (c) OCCUPIED / VACANT shares are plausible for a residential property.

- [ ] **Step 1: Create `py/validate_occupancy.py`**

```python
"""
Validate electricity-based occupancy detector across all 5 synthetic meters.

Run from project root:
    python py/validate_occupancy.py

Reports per-meter label distribution, floor statistics, and comfort score
delta (fixed 07:00-22:30 window vs occupancy-corrected window).
"""

import csv
from collections import defaultdict

from config import METERS, REGRESSION_START, REGRESSION_END
from occupancy_elec import ElecOccupancyDetector

ELEC_UTILITY = 'electricity'
OCCUPIED_WINDOW = frozenset(range(14, 45))   # 07:00-22:30 fixed window
COMFORT_LOWER_C = 18.0


def load_elec_by_date(mpan, start, end):
    """Return {date_str: [48 floats]} for electricity kWh."""
    by_date_period = defaultdict(dict)
    with open('data/consumption.csv', newline='') as f:
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
    with open('data/weather.csv', newline='') as f:
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
    print(f"  Periods: {total} | "
          f"OCCUPIED {counts['OCCUPIED']/total:.1%} | "
          f"VACANT   {counts['VACANT']/total:.1%} | "
          f"UNKNOWN  {counts['UNKNOWN']/total:.1%}")
    print(f"  Floor: {det.floor_kwh:.3f} kWh  MAD: {det.floor_mad:.4f}  "
          f"source={det.floor_source}  stable={det.floor_stable}  "
          f"step_change={det.floor_step_change}")
    print(f"  heating_contaminated={det.heating_contaminated}")


def main():
    print(f"Occupancy detector validation  {REGRESSION_START} → {REGRESSION_END}")
    weather = load_outdoor_temp_by_date(REGRESSION_START, REGRESSION_END)
    for meter_num, mpan in METERS.items():
        elec = load_elec_by_date(mpan, REGRESSION_START, REGRESSION_END)
        if not elec:
            print(f"\nM{meter_num}: no electricity data found")
            continue
        run_meter(meter_num, mpan, elec, weather)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run the validation script**

```
python py/validate_occupancy.py
```

Expected output shape (values will vary by meter):
```
Occupancy detector validation  2023-10-01 → 2025-03-31

M1 (1234567891000)
  Periods: NNNNN | OCCUPIED XX.X% | VACANT   XX.X% | UNKNOWN  XX.X%
  Floor: 0.0XX kWh  MAD: 0.00XX  source=overnight_bootstrap  stable=True  step_change=False
  heating_contaminated=False

M2 ...
```

Sanity checks to verify manually:
- UNKNOWN should be highest in the first 2 weeks of data, then drop
- OCCUPIED + VACANT + UNKNOWN = 100%
- Floor values should be low (< 0.10 kWh) for all meters — these are synthetic dwellings with no always-on EV charging

If a meter shows `no electricity data found`, check that `METERS` MPANs match those in `consumption.csv`.

- [ ] **Step 3: Commit**

```bash
git add py/validate_occupancy.py
git commit -m "feat: add validate_occupancy.py — end-to-end detector validation across all meters"
```

---

## Self-review

**Spec coverage check:**

| Spec section | Covered by |
|---|---|
| Always-on floor — bootstrap P20 from overnight | Task 2 (`compute_floor`), Task 6 (`ElecOccupancyDetector._update_floor`) |
| Always-on floor — sensor refinement | Task 6 (`confirmed_vacant` parameter) |
| Floor stability tracking — 25% threshold, hold | Task 6 (`_update_floor` stability block), test `test_detector_unstable_floor_holds_previous_value` |
| Floor step change after 3 weeks | Task 6 (`FLOOR_STEP_WEEKS`), test `test_detector_step_change_accepted_after_3_unstable_weeks` |
| Electric heating guard | Task 3 (`is_heating_contaminated`), Task 6 (guard applied in `add_day`) |
| Cold-start 14 nights, population floor | Task 4 (`in_cold_start` path in `label_sequence`), Task 6 (`MIN_NIGHTS`) |
| OCCUPIED hard threshold (1 period) | Task 4, test `test_hard_threshold_single_period_occupied` |
| OCCUPIED soft threshold (2 consecutive) | Task 4, tests `test_soft_threshold_two_consecutive_both_occupied` and `test_soft_threshold_resets_after_non_soft_period` |
| VACANT — 6-period run, back-labelling | Task 4 (implementation), Task 5 (tests) |
| VACANT — hard threshold breaks run | Task 5, test `test_hard_threshold_breaks_vacant_run_and_requires_new_accumulation` |
| Single soft period does not break VACANT | Task 5, test `test_single_soft_period_does_not_break_vacant` |
| Heating contamination suppresses overnight VACANT | Task 4 (implementation), Task 5 test `test_heating_contaminated_suppresses_overnight_vacant` |
| Output schema — all fields present | Task 4, test `test_output_contains_required_fields` |
| floor_source / floor_stable annotated by detector | Task 6 (`add_day` annotates labels after `label_sequence`) |
| Validation against synthetic meters | Task 7 |

No gaps identified.
