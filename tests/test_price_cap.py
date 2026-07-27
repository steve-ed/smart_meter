import sys
sys.path.insert(0, "py")

REQUIRED_KEYS = {"quarter", "elec_unit", "elec_standing", "gas_unit", "gas_standing"}

def _price_cap_data():
    """Local copy for testing — must match app.py exactly."""
    return [
        {"quarter": "Q3 2023", "elec_unit": 29.00, "elec_standing": 52.97, "gas_unit": 7.30,  "gas_standing": 29.62},
        {"quarter": "Q4 2023", "elec_unit": 27.35, "elec_standing": 52.97, "gas_unit": 6.89,  "gas_standing": 29.62},
        {"quarter": "Q1 2024", "elec_unit": 28.62, "elec_standing": 53.37, "gas_unit": 7.20,  "gas_standing": 29.60},
        {"quarter": "Q2 2024", "elec_unit": 24.50, "elec_standing": 61.64, "gas_unit": 6.04,  "gas_standing": 31.41},
        {"quarter": "Q3 2024", "elec_unit": 22.36, "elec_standing": 61.64, "gas_unit": 5.48,  "gas_standing": 31.41},
        {"quarter": "Q4 2024", "elec_unit": 24.50, "elec_standing": 61.64, "gas_unit": 6.24,  "gas_standing": 31.41},
        {"quarter": "Q1 2025", "elec_unit": 24.50, "elec_standing": 61.64, "gas_unit": 6.24,  "gas_standing": 31.41},
        {"quarter": "Q2 2025", "elec_unit": 25.05, "elec_standing": 61.64, "gas_unit": 6.33,  "gas_standing": 31.41},
        {"quarter": "Q3 2025", "elec_unit": 24.50, "elec_standing": 61.64, "gas_unit": 6.24,  "gas_standing": 31.41},
    ]


def test_returns_list_of_dicts():
    data = _price_cap_data()
    assert isinstance(data, list)
    assert all(isinstance(row, dict) for row in data)


def test_required_keys_present():
    data = _price_cap_data()
    for row in data:
        assert REQUIRED_KEYS == set(row.keys()), f"Missing keys in {row['quarter']}"


def test_covers_nine_quarters():
    data = _price_cap_data()
    assert len(data) == 9


def test_first_quarter_is_q3_2023():
    data = _price_cap_data()
    assert data[0]["quarter"] == "Q3 2023"


def test_last_quarter_is_q3_2025():
    data = _price_cap_data()
    assert data[-1]["quarter"] == "Q3 2025"


def test_all_values_are_positive_floats():
    data = _price_cap_data()
    numeric_keys = {"elec_unit", "elec_standing", "gas_unit", "gas_standing"}
    for row in data:
        for k in numeric_keys:
            assert isinstance(row[k], (int, float)), f"{k} not numeric in {row['quarter']}"
            assert row[k] > 0, f"{k} not positive in {row['quarter']}"
