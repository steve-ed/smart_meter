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
