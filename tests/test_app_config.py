import sys
sys.path.insert(0, ".")
from app import parse_pytest_summary


def test_parse_all_passed():
    output = "223 passed in 4.74s"
    passed, failed = parse_pytest_summary(output)
    assert passed == 223
    assert failed == 0


def test_parse_with_failures():
    output = "220 passed, 3 failed in 5.10s"
    passed, failed = parse_pytest_summary(output)
    assert passed == 220
    assert failed == 3


def test_parse_empty_output():
    passed, failed = parse_pytest_summary("")
    assert passed == 0
    assert failed == 0


from app import _rewrite_constant


def test_rewrite_float_constant():
    content = 'GAS_RATE_P_KWH   = 6.0    # pence/kWh\n'
    result = _rewrite_constant(content, "GAS_RATE_P_KWH", 7.5)
    assert "GAS_RATE_P_KWH   = 7.5" in result
    assert "# pence/kWh" in result   # comment preserved


def test_rewrite_string_constant():
    content = 'WINTER_START = "2024-10-01"   # Oct 2024\n'
    result = _rewrite_constant(content, "WINTER_START", "2025-10-01")
    assert '"2025-10-01"' in result
    assert "# Oct 2024" in result


def test_rewrite_leaves_other_lines_unchanged():
    content = 'GAS_RATE_P_KWH = 6.0\nELEC_RATE_P_KWH = 24.0\n'
    result = _rewrite_constant(content, "GAS_RATE_P_KWH", 7.0)
    assert "ELEC_RATE_P_KWH = 24.0" in result
