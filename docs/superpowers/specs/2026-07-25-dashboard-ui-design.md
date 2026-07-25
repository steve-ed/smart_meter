# Smart Meter Dashboard UI — Design Spec

**Date:** 2026-07-25  
**Status:** Approved

## Goal

A Streamlit dashboard that lets the user select a meter, run pytest tests and all 11 service scripts for that meter, and view/edit configuration files via structured form fields.

---

## Layout

**Sidebar + Tabs** (Streamlit layout A):

- **Sidebar:** meter dropdown, Run All button, last-run status summary
- **Main area tabs:** Tier 1 | Tier 2 | Tier 3 | Tests | Config

---

## Meter Selection

- Dropdown: M1–M5, labelled with property type and build era from `METER_META` in `config.py`
- Selecting a meter does not auto-run anything — user must press Run All
- All services run **only for the selected meter** (not all meters)

---

## Run All Flow

1. Press **Run All** in the sidebar
2. Run `pytest.main(["-q", "tests/"])` — capture stdout, parse pass/fail counts
3. If any tests fail: show failure summary, stop — do not run services
4. If all tests pass: run all 11 services for the selected meter in sequence
5. Update sidebar status summary (tests passed, services completed, timestamp)

---

## Tab: Tier 1 (S01–S04)

Each service shown as a collapsible expander:
- Header: service name + status (idle / running / done / failed)
- Expanded: CSV output rendered as a dataframe table
- Services: S01 Tariff Matching, S02 Battery Sizing, S03 Disaggregation, S04 Heat Pump

---

## Tab: Tier 2 (S05–S10)

Same pattern as Tier 1.  
Services: S05 Boiler Trending, S06 Heating Efficiency, S07 Budget Forecast, S08 Carbon Shifting, S09 Pre-Warm, S10 Leak & Frost

---

## Tab: Tier 3 (S11)

Same pattern. Single service: S11 Anomaly Suppression.

---

## Tab: Tests

- Three metric boxes: passed count (green), failed count (red), duration
- Scrollable log of pytest stdout output below

---

## Tab: Config

Two-column layout:

**Left column — `config.py` fields:**
- Gas Rate (p/kWh) — number input
- Electricity Rate (p/kWh) — number input
- Winter Start — date input
- Winter End — date input
- Regression Start — date input
- Regression End — date input

**Right column — `data/eon_tariffs.json`:**
- One collapsible expander per product (Fixed, Drive, Flex)
- Fixed: standing p/day + unit rate p/kWh
- Drive: standing p/day + night rate + day rate (two bands)
- Flex: read-only label ("uses actual meter rates")

**Save Changes button:** rewrites both files atomically. Streamlit reruns to reload values.

---

## Implementation

**File:** `app.py` at project root (~300 lines)

**Key decisions:**
- Imports `analyse_meter()` directly from each service module (not subprocess) — enables per-meter runs without modifying existing scripts
- `sys.path.insert(0, "py")` at top of `app.py` to resolve service imports
- pytest run via `pytest.main()` with stdout captured using `io.StringIO` redirect
- Config save: parse and rewrite `config.py` using regex substitution on known constant lines; rewrite `eon_tariffs.json` with `json.dump`
- State (results, last-run timestamp) stored in `st.session_state`

**New dependency:** `streamlit` only. No pandas required (use `st.table()` with plain dicts).

---

## Out of Scope

- Running individual services independently (always run all 11 as a batch)
- Editing meter MPANs or METER_META property types
- Historical run comparison
- Authentication
