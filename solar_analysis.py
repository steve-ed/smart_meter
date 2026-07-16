import os
from datetime import date

import numpy as np
import pandas as pd

from solar_battery_simulator import simulate_day_solar
from solar_profile import get_pvgis_profile, get_measured_profile

# ── Meter configuration ───────────────────────────────────────────────────────
MPAN         = "1234567891024"
METER_NUMBER = 5
LAT          = 53.60    # WF9 2UW — South Elmsall
LON          = -1.32

# ── System parameters ─────────────────────────────────────────────────────────
PANEL_SIZES_KWP      = [2, 4, 6, 8, 10, 12]
BATTERY_SIZES_KWH    = [0, 2, 5, 7, 10, 13, 15]
SOLAR_COST_PER_KWP   = 900      # GBP/kWp
BATTERY_COST_PER_KWH = 500      # GBP/kWh
EXPORT_RATE_P        = 15.0     # p/kWh Smart Export Guarantee
PANEL_TILT           = 35
PANEL_AZIMUTH        = 180
WARRANTY_YEARS       = 15
MIN_SOC              = 0.20
BATTERY_CONFIGS = [
    {"label": "0.5C", "max_c_rate": 0.5, "rte": 0.92},
    {"label": "1C",   "max_c_rate": 1.0, "rte": 0.88},
]

DATA_DIR    = "data"
OUTPUT_FILE = f"data/m{METER_NUMBER}-solar-results.txt"
WEEK_START  = pd.Timestamp("2026-07-06")
WEEK_END    = pd.Timestamp("2026-07-12")
PLOT_PANEL_KWP   = 6
PLOT_BATTERY_KWH = 5


def load_data():
    consumption = pd.read_csv(f"{DATA_DIR}/consumption.csv")
    consumption = consumption[
        (consumption["mpxn"] == int(MPAN)) & (consumption["utility"] == "electricity")
    ][["timestamp", "value"]].copy()
    consumption["timestamp"] = pd.to_datetime(consumption["timestamp"])
    consumption = consumption.rename(columns={"value": "consumption_kwh"})
    consumption = consumption.drop_duplicates(subset="timestamp", keep="first")

    tariff_raw = pd.read_csv(f"{DATA_DIR}/tariff.csv")
    tariff_raw = tariff_raw[
        (tariff_raw["mpan"] == int(MPAN))
        & (tariff_raw["energy_type"] == "electricity")
        & (tariff_raw["type"] == "unit_rate")
    ][["timestamp", "value"]].copy()
    tariff_raw["timestamp"] = pd.to_datetime(tariff_raw["timestamp"])
    tariff_raw["time_of_day"] = tariff_raw["timestamp"].dt.time
    tod_rate = tariff_raw.groupby("time_of_day")["value"].first().to_dict()

    consumption["time_of_day"] = consumption["timestamp"].dt.time
    consumption["rate_p"] = consumption["time_of_day"].map(tod_rate)
    merged = consumption.dropna(subset=["rate_p"]).drop(columns=["time_of_day"])
    merged["date"] = merged["timestamp"].dt.date
    return merged


def build_daily_arrays(merged):
    days = []
    for d, group in merged.groupby("date"):
        group = group.sort_values("timestamp")
        if len(group) != 48:
            continue
        days.append((d, group["consumption_kwh"].tolist(), group["rate_p"].tolist()))
    return days


def to_profile_date(d):
    """Map any simulation date to its 2020 equivalent for solar profile lookup."""
    return date(2020, d.month, d.day)


def run_sweep(days, solar_profile, config):
    """
    Sweep all panel × battery combinations.
    Returns (savings_gbp, paybacks) as 2D numpy arrays shaped
    (len(PANEL_SIZES_KWP), len(BATTERY_SIZES_KWH)).
    """
    rte = config["rte"]
    max_c_rate = config["max_c_rate"]
    n_panels = len(PANEL_SIZES_KWP)
    n_batts = len(BATTERY_SIZES_KWH)
    savings = np.zeros((n_panels, n_batts))
    paybacks = np.full((n_panels, n_batts), np.inf)

    for pi, panel_kwp in enumerate(PANEL_SIZES_KWP):
        # Pre-scale solar profile for this panel size
        solar_per_day = {
            d: [v * panel_kwp for v in solar_profile.get(to_profile_date(d), [0.0] * 48)]
            for d, _, _ in days
        }
        for bi, battery_kwh in enumerate(BATTERY_SIZES_KWH):
            results = [
                simulate_day_solar(
                    c, t, solar_per_day[d],
                    battery_kwh, rte, max_c_rate, MIN_SOC, EXPORT_RATE_P,
                )
                for d, c, t in days
            ]
            avg_daily_p = sum(r["daily_saving_p"] for r in results) / len(days)
            annual_gbp = avg_daily_p * 365 / 100
            installed = panel_kwp * SOLAR_COST_PER_KWP + battery_kwh * BATTERY_COST_PER_KWH
            paybacks[pi][bi] = installed / annual_gbp if annual_gbp > 0 else np.inf
            savings[pi][bi] = annual_gbp

    return savings, paybacks


def build_text_table(days, savings, paybacks, profile_label, config):
    col_w = 16
    header = f"{'Panel':>8} | " + " | ".join(
        f"{b:>3} kWh".center(col_w) for b in BATTERY_SIZES_KWH
    )
    divider = "-" * 8 + "-+-" + ("-" * col_w + "-+-") * len(BATTERY_SIZES_KWH)

    lines = [
        f"-- {profile_label} Profile | {config['label']} Battery --",
        header,
        divider,
    ]
    for pi, panel_kwp in enumerate(PANEL_SIZES_KWP):
        cells = []
        for bi in range(len(BATTERY_SIZES_KWH)):
            s = savings[pi][bi]
            p = paybacks[pi][bi]
            flag = "*" if p > WARRANTY_YEARS else " "
            cells.append(f"£{s:>5,.0f}/yr {p:>4.1f}y{flag}".center(col_w))
        lines.append(f"{panel_kwp:>5} kWp | " + " | ".join(cells))

    lines.append(divider)
    if any(paybacks[pi][bi] > WARRANTY_YEARS
           for pi in range(len(PANEL_SIZES_KWP))
           for bi in range(len(BATTERY_SIZES_KWH))):
        lines.append(f"* Payback exceeds {WARRANTY_YEARS}-year warranty period.")
    return lines


import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import matplotlib.dates as mdates


def plot_heatmap(savings, paybacks, profile_label, config_label):
    n_panels = len(PANEL_SIZES_KWP)
    n_batts = len(BATTERY_SIZES_KWH)
    data = np.clip(paybacks, 0, 20)

    fig, ax = plt.subplots(figsize=(13, 7))
    cmap = plt.cm.RdYlGn_r
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=20, aspect="auto")
    plt.colorbar(im, ax=ax, label="Payback period (years)")

    # Contour at 10 years
    if data.min() < 10 < data.max():
        ax.contour(data, levels=[10], colors=["#032147"], linewidths=[1.5])

    # Cell annotations
    for pi in range(n_panels):
        for bi in range(n_batts):
            p = paybacks[pi][bi]
            s = savings[pi][bi]
            text = f"{p:.1f}yr\n£{s:.0f}/yr" if p < np.inf else f">20yr\n£{s:.0f}/yr"
            color = "white" if p > 15 or p < 4 else "black"
            ax.text(bi, pi, text, ha="center", va="center", fontsize=8.5, color=color)
            if p > WARRANTY_YEARS:
                ax.add_patch(mpatches.Rectangle(
                    (bi - 0.5, pi - 0.5), 1, 1,
                    fill=False, hatch="////", edgecolor="gray", linewidth=0,
                ))

    ax.set_xticks(range(n_batts))
    ax.set_xticklabels([f"{b} kWh" for b in BATTERY_SIZES_KWH])
    ax.set_yticks(range(n_panels))
    ax.set_yticklabels([f"{p} kWp" for p in PANEL_SIZES_KWP])
    ax.set_xlabel("Battery size (kWh)", fontsize=11)
    ax.set_ylabel("Panel size (kWp)", fontsize=11)
    ax.set_title(
        f"Meter {METER_NUMBER} (MPAN {MPAN}) — Solar + Battery Payback\n"
        f"{profile_label} profile | {config_label} battery | "
        f"Export {EXPORT_RATE_P}p/kWh | Solar £{SOLAR_COST_PER_KWP}/kWp | "
        f"Battery £{BATTERY_COST_PER_KWH}/kWh",
        fontsize=11,
    )
    plt.tight_layout()
    out = f"{DATA_DIR}/m{METER_NUMBER}-solar-heatmap-{profile_label.lower()}-{config_label}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Heatmap saved to {out}")


def simulate_week_solar(week_df, solar_profile, panel_kwp, battery_kwh, config):
    rte = config["rte"]
    max_c_rate = config["max_c_rate"]
    max_hh = battery_kwh * max_c_rate * 0.5
    min_e = battery_kwh * MIN_SOC
    soc = min_e

    solar_list, self_consumed_list, exported_list = [], [], []
    charge_list, discharge_list, soc_list = [], [], []

    for d, group in week_df.groupby(week_df["timestamp"].dt.date):
        group = group.sort_values("timestamp")
        cons = group["consumption_kwh"].tolist()
        rates = group["rate_p"].tolist()
        solar_hh = [v * panel_kwp for v in solar_profile.get(to_profile_date(d), [0.0] * 48)]
        off_peak = min(rates)
        peak = max(rates)

        for i in range(48):
            rate = rates[i]
            solar = solar_hh[i]
            consumption = cons[i]

            self_c = min(solar, consumption)
            surplus = solar - self_c
            net_load = consumption - self_c

            charge_solar = 0.0
            if surplus > 0 and battery_kwh > 0:
                space = battery_kwh - soc
                charge_solar = min(max_hh, space, surplus)
                soc += charge_solar
                surplus -= charge_solar

            exported = surplus

            charge_grid = 0.0
            discharge = 0.0
            if rate <= off_peak and battery_kwh > 0:
                remaining = max_hh - charge_solar
                space = battery_kwh - soc
                charge_grid = min(remaining, space)
                soc += charge_grid
                net_load += charge_grid
            elif rate >= peak and battery_kwh > 0 and net_load > 0:
                available = soc - min_e
                draw = min(max_hh, available, net_load / rte)
                draw = max(0.0, draw)
                soc -= draw
                discharge = draw * rte
                net_load -= discharge

            solar_list.append(solar)
            self_consumed_list.append(self_c)
            exported_list.append(exported)
            charge_list.append(charge_solar + charge_grid)
            discharge_list.append(discharge)
            soc_list.append(soc)

    return (
        np.array(solar_list),
        np.array(self_consumed_list),
        np.array(exported_list),
        np.array(charge_list),
        np.array(discharge_list),
        np.array(soc_list),
    )


def plot_solar_week(merged, solar_profile, panel_kwp, battery_kwh, config):
    full_index = pd.date_range(
        WEEK_START, WEEK_END + pd.Timedelta(hours=23, minutes=30), freq="30min"
    )
    week = pd.DataFrame({"timestamp": full_index})
    week = week.merge(
        merged[["timestamp", "consumption_kwh", "rate_p"]], on="timestamp", how="left"
    )
    week["consumption_kwh"] = week["consumption_kwh"].fillna(0.0)
    week["rate_p"] = week["rate_p"].ffill()

    solar, self_c, exported, charge, discharge, soc = simulate_week_solar(
        week, solar_profile, panel_kwp, battery_kwh, config
    )

    ts = week["timestamp"].values
    consumption = week["consumption_kwh"].values
    tariff = week["rate_p"].values
    net_grid = consumption + charge - discharge

    week_num = WEEK_START.isocalendar()[1]
    fig, axes = plt.subplots(4, 1, figsize=(16, 13), sharex=True,
                             gridspec_kw={"height_ratios": [2, 2, 1, 1]})
    fig.suptitle(
        f"Meter {METER_NUMBER} (MPAN {MPAN}) — Week {week_num} "
        f"({WEEK_START.strftime('%d %b')}–{WEEK_END.strftime('%d %b %Y')})  |  "
        f"{panel_kwp} kWp Solar + {battery_kwh} kWh Battery ({config['label']})",
        fontsize=13, fontweight="bold",
    )

    # Panel 0: solar generation
    ax = axes[0]
    ax.fill_between(ts, 0, solar, step="post", color="#ecad0a", alpha=0.6, label="Solar generation")
    ax.step(ts, solar, where="post", color="#ecad0a", linewidth=1)
    ax.fill_between(ts, 0, self_c, step="post", color="#209dd7", alpha=0.4, label="Self-consumed")
    ax.set_ylabel("Energy (kWh / hh)", fontsize=10)
    ax.set_title("Solar Generation", fontsize=10, loc="left")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_ylim(bottom=0)

    # Panel 1: consumption vs net grid
    ax = axes[1]
    ax.step(ts, consumption, where="post", color="#209dd7", linewidth=1.5,
            label="Consumption", zorder=3)
    ax.step(ts, net_grid, where="post", color="#753991", linewidth=1.5,
            label="Net grid draw", zorder=3)
    ax.fill_between(ts, consumption, net_grid,
                    where=(net_grid > consumption), step="post",
                    color="#ecad0a", alpha=0.4, label="Grid charging battery")
    ax.fill_between(ts, consumption, net_grid,
                    where=(net_grid < consumption), step="post",
                    color="#032147", alpha=0.4, label="Solar/battery saving")
    ax.set_ylabel("Energy (kWh / hh)", fontsize=10)
    ax.set_title("Consumption vs Net Grid Draw", fontsize=10, loc="left")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_ylim(bottom=-0.05)

    # Panel 2: battery SOC
    ax = axes[2]
    ax.fill_between(ts, 0, soc, step="post", color="#032147", alpha=0.5)
    ax.step(ts, soc, where="post", color="#032147", linewidth=1)
    ax.axhline(battery_kwh * MIN_SOC, color="red", linestyle="--", linewidth=0.8, alpha=0.7,
               label=f"Min SOC ({battery_kwh * MIN_SOC:.1f} kWh)")
    ax.axhline(battery_kwh, color="#888888", linestyle=":", linewidth=0.8, alpha=0.7,
               label=f"Full ({battery_kwh} kWh)")
    ax.set_ylabel("SOC (kWh)", fontsize=10)
    ax.set_ylim(0, battery_kwh * 1.1)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)

    # Panel 3: tariff
    ax = axes[3]
    ax.step(ts, tariff, where="post", color="red", linewidth=1)
    ax.fill_between(ts, 0, tariff, step="post", color="red", alpha=0.2)
    ax.set_ylabel("Tariff (p/kWh)", fontsize=10)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%d %b"))

    plt.tight_layout()
    out = f"{DATA_DIR}/m{METER_NUMBER}-solar-wk{week_num}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Week plot saved to {out}")


def main():
    print("Loading data...")
    merged = load_data()
    days = build_daily_arrays(merged)
    date_min = min(d for d, _, _ in days)
    date_max = max(d for d, _, _ in days)
    off_peak = min(merged["rate_p"])
    peak = max(merged["rate_p"])

    # Baseline: no solar, no battery
    baseline_daily_cost_p = sum(
        sum(c[i] * t[i] for i in range(48)) for _, c, t in days
    ) / len(days)
    baseline_annual_gbp = baseline_daily_cost_p * 365 / 100

    print("Fetching PVGIS profile...")
    pvgis_profile = get_pvgis_profile(LAT, LON, PANEL_TILT, PANEL_AZIMUTH,
                                      year=2020, cache_dir=DATA_DIR)

    print("Building measured profile...")
    measured_profile = get_measured_profile(DATA_DIR)

    profiles = [("PVGIS", pvgis_profile), ("Measured", measured_profile)]

    lines = [
        f"Solar + Battery Analysis - MPAN {MPAN}",
        f"Tariff: {off_peak}p off-peak / {peak}p peak  |  "
        f"Solar: £{SOLAR_COST_PER_KWP}/kWp  |  Battery: £{BATTERY_COST_PER_KWH}/kWh  |  "
        f"Export: {EXPORT_RATE_P}p/kWh SEG",
        f"Days simulated: {len(days):,} ({date_min} to {date_max})  |  Min SOC: {MIN_SOC*100:.0f}%",
        f"Baseline (no solar, no battery): £{baseline_annual_gbp:,.2f}/yr",
        "",
    ]

    all_results = {}  # (profile_label, config_label) → (savings, paybacks)

    for profile_label, solar_profile in profiles:
        for config in BATTERY_CONFIGS:
            print(f"Sweeping {profile_label} / {config['label']}...")
            savings, paybacks = run_sweep(days, solar_profile, config)
            all_results[(profile_label, config["label"])] = (savings, paybacks)
            lines.extend(build_text_table(days, savings, paybacks, profile_label, config))
            lines.append("")

    output = "\n".join(lines)
    print(output)
    with open(OUTPUT_FILE, "w") as f:
        f.write(output + "\n")
    print(f"\nResults saved to {OUTPUT_FILE}")

    print("Generating heatmaps...")
    for profile_label, _ in profiles:
        for config in BATTERY_CONFIGS:
            savings, paybacks = all_results[(profile_label, config["label"])]
            plot_heatmap(savings, paybacks, profile_label, config["label"])

    print("Generating week plot...")
    plot_config = BATTERY_CONFIGS[0]  # 0.5C
    plot_solar_week(merged, pvgis_profile, PLOT_PANEL_KWP, PLOT_BATTERY_KWH, plot_config)

    return days, merged, all_results, profiles


if __name__ == "__main__":
    main()
