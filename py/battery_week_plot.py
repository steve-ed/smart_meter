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
METER_NUMBER = 1

WEEK_START = pd.Timestamp("2026-07-06")
WEEK_END   = pd.Timestamp("2026-07-12")

WEEK_NUMBER = WEEK_START.isocalendar()[1]
OUTPUT_FILE = (
    f"data/m{METER_NUMBER}-{int(BATTERY_CAPACITY)}KW-wk{WEEK_NUMBER}.png"
)


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


def simulate_week(week, capacity=BATTERY_CAPACITY):
    charge_list, discharge_list, soc_list = [], [], []

    for date, group in week.groupby(week["timestamp"].dt.date):
        group = group.sort_values("timestamp")
        cons = group["consumption_kwh"].tolist()
        rates = group["rate_p"].tolist()

        off_peak = min(rates)
        peak = max(rates)
        max_hh = capacity * MAX_C_RATE * 0.5
        min_e = capacity * MIN_SOC
        soc = min_e

        for c, r in zip(cons, rates):
            if r <= off_peak:
                charge = min(max_hh, capacity - soc)
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


BATTERY_SIZES_KWH = [2, 5, 7, 10, 13, 15]


def stats_box(total, peak, offpeak):
    return (
        f"Total:          {total:.2f} kWh\n"
        f"High rate:   {peak:.2f} kWh\n"
        f"Low rate:    {offpeak:.2f} kWh"
    )


def plot_battery_size(week, capacity):
    charge, discharge, soc = simulate_week(week, capacity)

    ts = week["timestamp"].values
    consumption = week["consumption_kwh"].values
    tariff = week["rate_p"].values
    net_grid = consumption + charge - discharge

    is_peak    = tariff >= tariff.max()
    is_offpeak = tariff <= tariff.min()

    no_batt_total   = consumption.sum()
    no_batt_peak    = consumption[is_peak].sum()
    no_batt_offpeak = consumption[is_offpeak].sum()
    batt_total      = net_grid.sum()
    batt_peak       = net_grid[is_peak].sum()
    batt_offpeak    = net_grid[is_offpeak].sum()

    fig, (ax0, ax1, ax2) = plt.subplots(
        3, 1, figsize=(16, 11), sharex=True,
        gridspec_kw={"height_ratios": [2, 2, 1]}
    )
    fig.suptitle(
        f"Meter {METER_NUMBER} (MPAN {MPAN}) - Week {WEEK_NUMBER} ({WEEK_START.strftime('%d %b')}–{WEEK_END.strftime('%d %b %Y')})  |  {int(capacity)} kWh Battery Simulation",
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
    ax0.set_ylim(bottom=0, top=np.percentile(consumption, 99) * 1.2)
    ax0.grid(True, alpha=0.25)
    ax0_r.legend(loc="upper right", fontsize=8)
    ax0.text(0.01, 0.97, stats_box(no_batt_total, no_batt_peak, no_batt_offpeak),
             transform=ax0.transAxes, fontsize=10, verticalalignment="top",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.8))

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
    ax1.set_title(f"With {int(capacity)} kWh Battery", fontsize=10, loc="left")
    ax1.set_ylim(bottom=-0.05, top=np.percentile(net_grid, 99) * 1.2)
    ax1.grid(True, alpha=0.25)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_r.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=8)
    ax1.text(0.01, 0.97, stats_box(batt_total, batt_peak, batt_offpeak),
             transform=ax1.transAxes, fontsize=10, verticalalignment="top",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.8))

    # --- Panel 2: battery SOC ---
    ax2.fill_between(ts, 0, soc, step="post", color="#032147", alpha=0.5)
    ax2.step(ts, soc, where="post", color="#032147", linewidth=1)
    ax2.axhline(capacity * MIN_SOC, color="red", linestyle="--", linewidth=0.8,
                alpha=0.7, label=f"Min SOC ({MIN_SOC*100:.0f}% = {capacity*MIN_SOC} kWh)")
    ax2.axhline(capacity, color="#888888", linestyle=":", linewidth=0.8,
                alpha=0.7, label=f"Full ({capacity} kWh)")
    ax2.set_ylabel("Battery SOC (kWh)", fontsize=10)
    ax2.set_ylim(0, capacity * 1.1)
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(True, alpha=0.25)
    ax2.xaxis.set_major_locator(mdates.DayLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%d %b"))

    plt.tight_layout()
    out = f"{DATA_DIR}/m{METER_NUMBER}-{int(capacity)}KW-wk{WEEK_NUMBER}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Plot saved to {out}")


def main():
    week = load_week()
    for capacity in BATTERY_SIZES_KWH:
        plot_battery_size(week, capacity)


if __name__ == "__main__":
    main()
