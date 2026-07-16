import pandas as pd
from battery_simulator import simulate_day

COST_PER_KWH_INSTALLED = 500        # GBP/kWh installed
BATTERY_SIZES_KWH = [2, 5, 7, 10, 13, 15]
ROUND_TRIP_EFFICIENCY = 0.90
MAX_C_RATE = 0.5
MIN_SOC = 0.20
WARRANTY_YEARS = 15

MPAN = "1234567891000"
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


def format_row(size, installed_cost, avg_daily_p, annual_gbp, payback, flagged):
    flag = " *" if flagged else "  "
    return (
        f"{size:>10} | "
        f"GBP{installed_cost:>12,.0f} | "
        f"{avg_daily_p:>14.1f}p | "
        f"GBP{annual_gbp:>11,.2f} | "
        f"{payback:>11.1f}{flag}"
    )


def main():
    merged = load_data()
    days = build_daily_arrays(merged)

    off_peak = min(merged["rate_p"])
    peak = max(merged["rate_p"])
    date_min = min(d for d, _, _ in days)
    date_max = max(d for d, _, _ in days)

    print(f"Battery Size Analysis - MPAN {MPAN}")
    print(f"Tariff: {off_peak}p off-peak / {peak}p peak  |  Installed cost: GBP{COST_PER_KWH_INSTALLED}/kWh")
    print(
        f"Days simulated: {len(days):,} ({date_min} to {date_max})  |  "
        f"Efficiency: {ROUND_TRIP_EFFICIENCY * 100:.0f}%  |  "
        f"Min SOC: {MIN_SOC * 100:.0f}%  |  "
        f"Max C-rate: {MAX_C_RATE}C"
    )
    print()

    header = (
        f"{'Size (kWh)':>10} | "
        f"{'Installed Cost':>15} | "
        f"{'Avg Daily Saving':>16} | "
        f"{'Annual Saving':>14} | "
        f"{'Payback (yrs)':>13}"
    )
    divider = "-" * 10 + "-+-" + "-" * 15 + "-+-" + "-" * 16 + "-+-" + "-" * 14 + "-+-" + "-" * 13
    print(header)
    print(divider)

    any_flagged = False
    for size in BATTERY_SIZES_KWH:
        total_saving_p = sum(
            simulate_day(c, t, size, ROUND_TRIP_EFFICIENCY, MAX_C_RATE, MIN_SOC)["daily_saving_p"]
            for _, c, t in days
        )
        avg_daily_p = total_saving_p / len(days)
        annual_gbp = avg_daily_p * 365 / 100
        installed_cost = size * COST_PER_KWH_INSTALLED
        payback = installed_cost / annual_gbp if annual_gbp > 0 else float("inf")
        flagged = payback > WARRANTY_YEARS
        if flagged:
            any_flagged = True
        print(format_row(size, installed_cost, avg_daily_p, annual_gbp, payback, flagged))

    if any_flagged:
        print()
        print(f"* Payback exceeds {WARRANTY_YEARS}-year battery warranty period.")


if __name__ == "__main__":
    main()
