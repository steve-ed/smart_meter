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
