import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

MPAN = "1234567891000"
DATA_DIR = "data"
BATTERY_CAPACITY = 5.0
ROUND_TRIP_EFFICIENCY = 0.90
MAX_C_RATE = 0.5
MIN_SOC = 0.20
OUTPUT_FILE = "data/battery_week_plot.png"

WEEK_START = pd.Timestamp("2026-07-06")
WEEK_END   = pd.Timestamp("2026-07-12")


def load_week():
    consumption = pd.read_csv(f"{DATA_DIR}/consumption.csv")
    consumption = consumption[
        (consumption["mpxn"] == int(MPAN)) & (consumption["utility"] == "electricity")
    ][["timestamp", "value"]].copy()
    consumption["timestamp"] = pd.to_datetime(consumption["timestamp"])
    consumption = consumption.rename(columns={"value": "consumption_kwh"})
    consumption = consumption.drop_duplicates(subset="timestamp", keep="first")

    # Build time-of-day tariff lookup
    tariff_raw = pd.read_csv(f"{DATA_DIR}/tariff.csv")
    tariff_raw = tariff_raw[
        (tariff_raw["mpan"] == int(MPAN))
        & (tariff_raw["energy_type"] == "electricity")
        & (tariff_raw["type"] == "unit_rate")
    ][["timestamp", "value"]].copy()
    tariff_raw["timestamp"] = pd.to_datetime(tariff_raw["timestamp"])
    tariff_raw["time_of_day"] = tariff_raw["timestamp"].dt.time
    tod_rate = tariff_raw.groupby("time_of_day")["value"].first().to_dict()

    # Full 48-slot index for the week
    full_index = pd.date_range(WEEK_START, WEEK_END + pd.Timedelta(hours=23, minutes=30), freq="30min")
    week = pd.DataFrame({"timestamp": full_index})
    week = week.merge(consumption[["timestamp", "consumption_kwh"]], on="timestamp", how="left")
    week["consumption_kwh"] = week["consumption_kwh"].fillna(0.0)
    week["time_of_day"] = week["timestamp"].dt.time
    week["rate_p"] = week["time_of_day"].map(tod_rate)
    week = week.drop(columns=["time_of_day"])
    return week


def simulate_week(week):
    charge_list, discharge_list, soc_list = [], [], []

    for date, group in week.groupby(week["timestamp"].dt.date):
        group = group.sort_values("timestamp")
        cons = group["consumption_kwh"].tolist()
        rates = group["rate_p"].tolist()

        off_peak = min(rates)
        peak = max(rates)
        max_hh = BATTERY_CAPACITY * MAX_C_RATE * 0.5
        min_e = BATTERY_CAPACITY * MIN_SOC
        soc = min_e

        for c, r in zip(cons, rates):
            if r <= off_peak:
                charge = min(max_hh, BATTERY_CAPACITY - soc)
                soc += charge
                charge_list.append(charge)
                discharge_list.append(0.0)
            elif r >= peak:
                draw = min(max_hh, soc - min_e, c / ROUND_TRIP_EFFICIENCY)
                draw = max(0.0, draw)
                soc -= draw
                charge_list.append(0.0)
                discharge_list.append(draw * ROUND_TRIP_EFFICIENCY)
            else:
                charge_list.append(0.0)
                discharge_list.append(0.0)
            soc_list.append(soc)

    return np.array(charge_list), np.array(discharge_list), np.array(soc_list)


def main():
    week = load_week()
    charge, discharge, soc = simulate_week(week)

    ts = week["timestamp"].values
    consumption = week["consumption_kwh"].values
    tariff = week["rate_p"].values
    net_grid = consumption + charge - discharge

    fig, (ax0, ax1, ax2) = plt.subplots(
        3, 1, figsize=(16, 11), sharex=True,
        gridspec_kw={"height_ratios": [2, 2, 1]}
    )
    fig.suptitle(
        f"Meter 1 (MPAN {MPAN}) - Week 6-12 Jul 2026  |  5 kWh Battery Simulation",
        fontsize=13, fontweight="bold"
    )

    # --- Panel 0: raw consumption ---
    ax0.step(ts, consumption, where="post", color="#209dd7", linewidth=1.2)
    ax0.fill_between(ts, 0, consumption, step="post", color="#209dd7", alpha=0.25)
    ax0_r = ax0.twinx()
    ax0_r.step(ts, tariff, where="post", color="red", linewidth=1,
               linestyle="--", alpha=0.6, label="Tariff")
    ax0_r.set_ylabel("Tariff (p/kWh)", color="red", fontsize=10)
    ax0_r.tick_params(axis="y", colors="red")
    ax0_r.set_ylim(0, tariff.max() * 3)
    ax0.set_ylabel("Energy (kWh / half-hour)", fontsize=10)
    ax0.set_title("Actual Consumption", fontsize=10, loc="left")
    y_max0 = np.percentile(consumption, 99) * 1.2
    ax0.set_ylim(bottom=0, top=y_max0)
    ax0.grid(True, alpha=0.25)
    ax0.legend(["Consumption"], loc="upper left", fontsize=8)
    ax0_r.legend(loc="upper right", fontsize=8)

    # --- Panel 1: battery simulation ---
    ax1.step(ts, consumption, where="post", color="#209dd7", linewidth=1.5,
             label="Actual consumption", zorder=3)
    ax1.step(ts, net_grid, where="post", color="#753991", linewidth=1.5,
             label="Net grid draw (with battery)", zorder=3)
    ax1.fill_between(ts, consumption, net_grid,
                     where=(net_grid > consumption),
                     step="post", color="#ecad0a", alpha=0.45,
                     label="Battery charging (extra grid draw)")
    ax1.fill_between(ts, consumption, net_grid,
                     where=(net_grid < consumption),
                     step="post", color="#032147", alpha=0.45,
                     label="Battery discharging (grid saving)")

    ax1_r = ax1.twinx()
    ax1_r.step(ts, tariff, where="post", color="red", linewidth=1,
               linestyle="--", alpha=0.6, label="Tariff")
    ax1_r.set_ylabel("Tariff (p/kWh)", color="red", fontsize=10)
    ax1_r.tick_params(axis="y", colors="red")
    ax1_r.set_ylim(0, tariff.max() * 3)

    ax1.set_ylabel("Energy (kWh / half-hour)", fontsize=10)
    ax1.set_title("With Battery", fontsize=10, loc="left")
    y_max1 = np.percentile(net_grid, 99) * 1.2
    ax1.set_ylim(bottom=-0.05, top=y_max1)
    ax1.grid(True, alpha=0.25)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_r.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=8)

    # --- Panel 2: battery SOC ---
    ax2.fill_between(ts, 0, soc, step="post", color="#032147", alpha=0.5)
    ax2.step(ts, soc, where="post", color="#032147", linewidth=1)
    ax2.axhline(BATTERY_CAPACITY * MIN_SOC, color="red", linestyle="--",
                linewidth=0.8, alpha=0.7,
                label=f"Min SOC ({MIN_SOC * 100:.0f}% = {BATTERY_CAPACITY * MIN_SOC} kWh)")
    ax2.axhline(BATTERY_CAPACITY, color="#888888", linestyle=":",
                linewidth=0.8, alpha=0.7, label=f"Full ({BATTERY_CAPACITY} kWh)")
    ax2.set_ylabel("Battery SOC (kWh)", fontsize=10)
    ax2.set_ylim(0, BATTERY_CAPACITY * 1.1)
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(True, alpha=0.25)

    ax2.xaxis.set_major_locator(mdates.DayLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%d %b"))

    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches="tight")
    print(f"Plot saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
