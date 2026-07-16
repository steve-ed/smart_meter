import pandas as pd
from battery_simulator import simulate_day

COST_PER_KWH_INSTALLED = 500        # GBP/kWh installed
BATTERY_SIZES_KWH = [2, 5, 7, 10, 13, 15]
ROUND_TRIP_EFFICIENCY = 0.90
MAX_C_RATE = 0.5
MIN_SOC = 0.20
WARRANTY_YEARS = 15

MPAN = "1234567891000"
METER_NUMBER = 1
DATA_DIR = "data"


def load_data():
    consumption = pd.read_csv(f"{DATA_DIR}/consumption.csv")
    consumption = consumption[
        (consumption["mpxn"] == int(MPAN)) & (consumption["utility"] == "electricity")
    ][["timestamp", "value"]].copy()
    consumption["timestamp"] = pd.to_datetime(consumption["timestamp"])
    consumption = consumption.rename(columns={"value": "consumption_kwh"})
    consumption = consumption.drop_duplicates(subset="timestamp", keep="first")

    # Build time-of-day → rate lookup (rates are constant across all dates)
    tariff_raw = pd.read_csv(f"{DATA_DIR}/tariff.csv")
    tariff_raw = tariff_raw[
        (tariff_raw["mpan"] == int(MPAN))
        & (tariff_raw["energy_type"] == "electricity")
        & (tariff_raw["type"] == "unit_rate")
    ][["timestamp", "value"]].copy()
    tariff_raw["timestamp"] = pd.to_datetime(tariff_raw["timestamp"])
    tariff_raw["time_of_day"] = tariff_raw["timestamp"].dt.time
    tod_rate = tariff_raw.groupby("time_of_day")["value"].first().to_dict()

    # Apply tariff by time-of-day to all consumption timestamps
    consumption["time_of_day"] = consumption["timestamp"].dt.time
    consumption["rate_p"] = consumption["time_of_day"].map(tod_rate)
    merged = consumption.dropna(subset=["rate_p"]).drop(columns=["time_of_day"])
    merged["date"] = merged["timestamp"].dt.date
    return merged


def build_daily_arrays(merged):
    """Return list of (date, consumption_48, tariff_48) for complete 48-slot days only."""
    days = []
    for date, group in merged.groupby("date"):
        group = group.sort_values("timestamp")
        if len(group) != 48:
            continue
        days.append((
            date,
            group["consumption_kwh"].tolist(),
            group["rate_p"].tolist(),
        ))
    return days


OUTPUT_FILE = f"data/m{METER_NUMBER}-KWh-results.txt"


def main():
    merged = load_data()
    days = build_daily_arrays(merged)

    off_peak = min(merged["rate_p"])
    peak = max(merged["rate_p"])
    date_min = min(d for d, _, _ in days)
    date_max = max(d for d, _, _ in days)

    # Base consumption totals (no battery)
    base_total    = sum(sum(c) for _, c, _ in days)
    base_high     = sum(sum(c[i] for i in range(48) if t[i] >= peak)    for _, c, t in days)
    base_low      = sum(sum(c[i] for i in range(48) if t[i] <= off_peak) for _, c, t in days)

    lines = []
    lines.append(f"Battery Size Analysis - MPAN {MPAN}")
    lines.append(f"Tariff: {off_peak}p off-peak / {peak}p peak  |  Installed cost: GBP{COST_PER_KWH_INSTALLED}/kWh")
    lines.append(
        f"Days simulated: {len(days):,} ({date_min} to {date_max})  |  "
        f"Efficiency: {ROUND_TRIP_EFFICIENCY * 100:.0f}%  |  "
        f"Min SOC: {MIN_SOC * 100:.0f}%  |  "
        f"Max C-rate: {MAX_C_RATE}C"
    )
    lines.append("")

    header = (
        f"{'Size (kWh)':>10} | "
        f"{'Total (kWh)':>11} | "
        f"{'High Rate (kWh)':>15} | "
        f"{'Low Rate (kWh)':>14} | "
        f"{'Installed Cost':>15} | "
        f"{'Avg Daily Saving':>16} | "
        f"{'Annual Saving':>14} | "
        f"{'Payback (yrs)':>13} | "
        f"{'High Rate (7yr)':>15}"
    )
    divider = (
        "-" * 10 + "-+-" + "-" * 11 + "-+-" + "-" * 15 + "-+-" +
        "-" * 14 + "-+-" + "-" * 15 + "-+-" + "-" * 16 + "-+-" +
        "-" * 14 + "-+-" + "-" * 13 + "-+-" + "-" * 15
    )
    lines.append(header)
    lines.append(divider)

    # No-battery baseline row
    lines.append(
        f"{'No battery':>10} | "
        f"{base_total:>11.1f} | "
        f"{base_high:>15.1f} | "
        f"{base_low:>14.1f} | "
        f"{'N/A':>15} | "
        f"{'N/A':>16} | "
        f"{'N/A':>14} | "
        f"{'N/A':>13} | "
        f"{'N/A':>15}"
    )
    lines.append(divider)

    any_flagged = False
    for size in BATTERY_SIZES_KWH:
        results = [
            simulate_day(c, t, size, ROUND_TRIP_EFFICIENCY, MAX_C_RATE, MIN_SOC)
            for _, c, t in days
        ]
        total_saving_p  = sum(r["daily_saving_p"]     for r in results)
        total_displaced = sum(r["peak_kwh_displaced"]  for r in results)
        total_charged   = sum(r["charge_cycled_kwh"]   for r in results)

        grid_total = base_total - total_displaced + total_charged
        grid_high  = base_high  - total_displaced
        grid_low   = base_low   + total_charged

        avg_daily_p  = total_saving_p / len(days)
        annual_gbp   = avg_daily_p * 365 / 100
        installed_cost = size * COST_PER_KWH_INSTALLED
        payback = installed_cost / annual_gbp if annual_gbp > 0 else float("inf")
        flagged = payback > WARRANTY_YEARS
        if flagged:
            any_flagged = True

        # Peak rate required for 7-year payback, holding off-peak rate fixed
        annual_displaced = total_displaced * 365 / len(days)
        if annual_displaced > 0:
            required_peak_p = (installed_cost / 7 * 100 / annual_displaced) + off_peak / ROUND_TRIP_EFFICIENCY
            required_peak_str = f"{required_peak_p:>13.1f}p"
        else:
            required_peak_str = f"{'N/A':>14}"

        flag = " *" if flagged else "  "
        lines.append(
            f"{size:>10} | "
            f"{grid_total:>11.1f} | "
            f"{grid_high:>15.1f} | "
            f"{grid_low:>14.1f} | "
            f"GBP{installed_cost:>12,.0f} | "
            f"{avg_daily_p:>14.1f}p | "
            f"GBP{annual_gbp:>11,.2f} | "
            f"{payback:>11.1f}{flag} | "
            f"{required_peak_str}"
        )

    if any_flagged:
        lines.append("")
        lines.append(f"* Payback exceeds {WARRANTY_YEARS}-year battery warranty period.")

    output = "\n".join(lines)
    print(output)
    with open(OUTPUT_FILE, "w") as f:
        f.write(output + "\n")
    print(f"\nResults saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
