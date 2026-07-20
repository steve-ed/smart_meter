# tests/test_occupancy_elec.py
import pytest
from occupancy_elec import compute_floor, is_heating_contaminated, compute_thresholds


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


def test_soft_threshold_three_consecutive_all_occupied():
    """Three consecutive soft periods: all three must be OCCUPIED (back-label chain)."""
    floor_kwh = 0.10
    floor_mad = 0.005
    soft_thresh = floor_kwh + max(0.025, 1.5 * floor_mad)
    hard_thresh = floor_kwh + max(0.05, 3.0 * floor_mad)
    soft_val = (soft_thresh + hard_thresh) / 2  # between soft and hard
    kwh = [floor_kwh * 0.5, soft_val, soft_val, soft_val, floor_kwh * 0.5]
    results = label_sequence(kwh, floor_kwh, floor_mad)
    # Period 0: at floor → UNKNOWN (not enough floor run for VACANT)
    assert results[0]['occupied_label'] == 'UNKNOWN'
    # Period 1: first soft, back-labelled OCCUPIED when period 2 confirms the run
    assert results[1]['occupied_label'] == 'OCCUPIED'
    assert results[1]['label_source'] == 'elec_above_floor_soft'
    # Period 2: second soft — triggers back-label; itself OCCUPIED
    assert results[2]['occupied_label'] == 'OCCUPIED'
    # Period 3: third soft — still OCCUPIED (soft_run >= 2)
    assert results[3]['occupied_label'] == 'OCCUPIED'
    assert results[3]['label_source'] == 'elec_above_floor_soft'


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


def test_heating_contamination_overnight_not_labelled_vacant():
    """Overnight periods block floor-run accumulation when heating_contaminated=True."""
    floor_kwh = 0.10
    floor_mad = 0.005
    # Build a 48-period sequence where indices 1-8 are at-floor (overnight 2-8 + one daytime)
    # Without contamination, 8 consecutive at-floor periods would back-label all 8 as VACANT
    full_kwh = [floor_kwh * 3.0] * 48  # default: above floor
    for i in range(1, 9):  # periods 1-8, overlapping overnight indices 2-8
        full_kwh[i] = floor_kwh * 0.5
    results = label_sequence(
        full_kwh, floor_kwh, floor_mad,
        heating_contaminated=True, in_cold_start=False
    )
    # Overnight periods (2-8) should not be labelled VACANT because heating contamination
    # suppresses at-floor accumulation during overnight periods
    overnight_labels = [results[i]['occupied_label'] for i in range(2, 9)]
    assert all(lbl != 'VACANT' for lbl in overnight_labels), (
        f"Overnight periods should not be VACANT when heating_contaminated=True, got {overnight_labels}"
    )


# --- VACANT detection ---


def test_fewer_than_6_at_floor_periods_are_unknown():
    kwh = _periods(0.10)
    for i in range(20, 25):
        kwh[i] = 0.03
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    for i in range(20, 25):
        assert labels[i]['occupied_label'] == 'UNKNOWN', f"period {i} should be UNKNOWN"


def test_six_consecutive_at_floor_back_labels_all_vacant():
    kwh = _periods(0.10)
    for i in range(20, 26):
        kwh[i] = 0.03
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    for i in range(20, 26):
        assert labels[i]['occupied_label'] == 'VACANT', f"period {i} should be VACANT"
        assert labels[i]['label_source'] == 'elec_at_floor'


def test_vacant_continues_after_6_periods():
    kwh = _periods(0.10)
    for i in range(20, 38):
        kwh[i] = 0.03
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    for i in range(20, 38):
        assert labels[i]['occupied_label'] == 'VACANT'


def test_hard_threshold_breaks_vacant_run_and_requires_new_accumulation():
    # Use a short sequence: 10 at-floor (establishes VACANT), 1 hard spike, then
    # exactly 5 at-floor (not enough to re-establish VACANT → all UNKNOWN).
    kwh = [0.03] * 10 + [0.10] + [0.03] * 5
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert labels[10]['occupied_label'] == 'OCCUPIED'   # hard spike
    for i in range(11, 16):
        assert labels[i]['occupied_label'] == 'UNKNOWN', f"period {i} should be UNKNOWN (only 5 new at-floor)"


def test_single_soft_period_does_not_break_vacant():
    kwh = _periods(0.03)
    kwh[20] = 0.06
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert labels[20]['occupied_label'] == 'UNKNOWN'
    assert labels[21]['occupied_label'] == 'VACANT'


def test_two_consecutive_soft_breaks_vacant():
    # 10 at-floor (VACANT established), 2 soft (triggers OCCUPIED + resets vacant_active),
    # then 5 at-floor (not enough to re-establish VACANT).
    kwh = [0.03] * 10 + [0.06, 0.06] + [0.03] * 5
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005)
    assert labels[10]['occupied_label'] == 'OCCUPIED'
    assert labels[11]['occupied_label'] == 'OCCUPIED'
    for i in range(12, 17):
        assert labels[i]['occupied_label'] == 'UNKNOWN', f"period {i} should be UNKNOWN (only 5 new at-floor)"


def test_heating_contaminated_suppresses_overnight_vacant():
    kwh = _periods(0.03)
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005, heating_contaminated=True)
    for i in range(2, 11):
        assert labels[i]['occupied_label'] == 'UNKNOWN', f"overnight period {i} must not be VACANT"
    for i in range(11, 17):
        assert labels[i]['occupied_label'] == 'VACANT'


def test_at_floor_field_reflects_raw_value_regardless_of_contamination():
    kwh = _periods(0.03)
    labels = label_sequence(kwh, floor_kwh=0.03, floor_mad=0.005, heating_contaminated=True)
    for i in range(2, 11):
        assert labels[i]['at_floor'] is True


# ---------------------------------------------------------------------------
# ElecOccupancyDetector tests
# ---------------------------------------------------------------------------

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
    labels = det.add_day('2024-10-01', _periods(0.03), outdoor_temp_c=10.0)
    assert all(r['occupied_label'] == 'UNKNOWN' for r in labels)


def test_detector_returns_48_periods():
    det = ElecOccupancyDetector()
    labels = det.add_day('2024-10-01', _periods(0.04), outdoor_temp_c=10.0)
    assert len(labels) == 48


def test_detector_unstable_floor_holds_previous_value():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-10-01', _periods(0.04), outdoor_temp_c=10.0)
    stable_floor = det.floor_kwh
    for _ in range(7):
        det.add_day('2024-10-15', _periods(0.20), outdoor_temp_c=10.0)
    assert det.floor_stable is False
    assert det.floor_kwh == pytest.approx(stable_floor)


def test_detector_step_change_accepted_after_3_unstable_weeks():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-10-01', _periods(0.04), outdoor_temp_c=10.0)
    original_floor = det.floor_kwh
    for _ in range(21):
        det.add_day('2024-10-15', _periods(0.20), outdoor_temp_c=10.0)
    assert det.floor_step_change is True
    assert det.floor_kwh > original_floor


def test_detector_sensor_calibrated_floor_source():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-10-01', _periods(0.04), outdoor_temp_c=10.0)
    confirmed = [(i, 0.02) for i in range(48)]
    for _ in range(7):
        det.add_day('2024-10-15', _periods(0.04), outdoor_temp_c=10.0,
                    confirmed_vacant=confirmed)
    assert det.floor_source == 'sensor_calibrated'


def test_detector_heating_contamination_activates():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-01-01', _periods(0.60), outdoor_temp_c=3.0)
    assert det.heating_contaminated is True


def test_detector_heating_contamination_does_not_activate_when_warm():
    det = ElecOccupancyDetector()
    for _ in range(MIN_NIGHTS):
        det.add_day('2024-07-01', _periods(0.10), outdoor_temp_c=18.0)
    assert det.heating_contaminated is False
