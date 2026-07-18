import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

MPAN = "1234567891000"
METER_NUMBER = 1
DATA_DIR = "data"
GAS_CAP = 2.0          # m³/half-hour — excludes sentinel variants (16 777.215 and 16 777 215)
GAS_KWH_PER_M3 = 11.2  # calorific value conversion
GAS_RATE_P_KWH = 6.0   # pence per kWh (Ofgem cap — verify current rate)


def gas_cost_gbp(m3):
    return m3 * GAS_KWH_PER_M3 * GAS_RATE_P_KWH / 100

# Set to a date string like "2026-01-15" to plot the week containing that date,
# or None to use the last full week with data.
TARGET_DATE = None


def find_week(df, target_date=None):
    df["date"] = df["timestamp"].dt.normalize()
    if target_date is None:
        anchor = df["date"].max()
        while anchor.day_of_week != 6:
            anchor -= pd.Timedelta(days=1)
    else:
        anchor = pd.Timestamp(target_date)
        days_to_sunday = (6 - anchor.day_of_week) % 7
        anchor += pd.Timedelta(days=days_to_sunday)
    return anchor - pd.Timedelta(days=6), anchor


def load_elec_tariff():
    tariff = pd.read_csv(f"{DATA_DIR}/tariff.csv")
    tariff = tariff[
        (tariff["mpan"] == int(MPAN)) &
        (tariff["energy_type"] == "electricity") &
        (tariff["type"] == "unit_rate")
    ][["timestamp", "value"]].copy()
    tariff["timestamp"] = pd.to_datetime(tariff["timestamp"])
    tariff["time_of_day"] = tariff["timestamp"].dt.time
    return tariff.groupby("time_of_day")["value"].first().to_dict()


def load_week(utility, week_start, week_end, all_data=None, elec_tariff=None):
    if all_data is None:
        all_data = pd.read_csv(f"{DATA_DIR}/consumption.csv")
    df = all_data[(all_data["mpxn"] == int(MPAN)) & (all_data["utility"] == utility)][["timestamp", "value"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if utility == "gas":
        df = df[df["value"] <= GAS_CAP]
    df = df.drop_duplicates(subset="timestamp", keep="first")

    full_index = pd.date_range(
        week_start, week_end + pd.Timedelta(hours=23, minutes=30), freq="30min"
    )
    week = pd.DataFrame({"timestamp": full_index})
    week = week.merge(df[["timestamp", "value"]], on="timestamp", how="left")
    week["value"] = week["value"].fillna(0.0)

    if utility == "electricity" and elec_tariff:
        week["rate_p"] = week["timestamp"].dt.time.map(elec_tariff).fillna(0.0)
        week["cost_gbp"] = week["value"] * week["rate_p"] / 100

    return week


def make_pivot(week):
    week = week.copy()
    week["date"] = week["timestamp"].dt.date
    week["slot"] = week["timestamp"].dt.hour * 2 + week["timestamp"].dt.minute // 30
    return week.pivot(index="slot", columns="date", values="value")


def draw_heatmap(ax, pivot, cmap, vmax, unit_label, daily_fmt, cost_pivot=None):
    im = ax.imshow(
        pivot.values,
        aspect="auto",
        origin="upper",
        cmap=cmap,
        vmin=0,
        vmax=vmax,
        interpolation="nearest",
    )
    daily_totals = pivot.sum(axis=0)
    daily_costs = cost_pivot.sum(axis=0) if cost_pivot is not None else {}
    day_labels = []
    for d, total in daily_totals.items():
        label = f"{pd.Timestamp(d).strftime('%a')}\n{pd.Timestamp(d).strftime('%d %b')}\n{daily_fmt(total)}"
        if cost_pivot is not None:
            label += f"\n£{daily_costs[d]:.2f}"
        day_labels.append(label)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(day_labels, fontsize=9)
    ax.set_yticks(range(0, 48, 4))
    ax.set_yticklabels([f"{h:02d}:00" for h in range(0, 24, 2)], fontsize=9)

    week_total = daily_totals.sum()
    summary = f"Week total: {daily_fmt(week_total)}"
    if cost_pivot is not None:
        summary += f" / £{cost_pivot.values.sum():.2f}"
    ax.text(
        0.99, 0.01, summary,
        transform=ax.transAxes, ha="right", va="bottom", fontsize=10,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
    )
    return im


def main():
    raw = pd.read_csv(f"{DATA_DIR}/consumption.csv")
    raw["timestamp"] = pd.to_datetime(raw["timestamp"])

    gas_df = raw[(raw["mpxn"] == int(MPAN)) & (raw["utility"] == "gas")].copy()
    gas_df = gas_df[gas_df["value"] <= GAS_CAP]
    gas_df["timestamp"] = pd.to_datetime(gas_df["timestamp"])

    week_start, week_end = find_week(gas_df, TARGET_DATE)
    week_num = week_start.isocalendar()[1]

    elec_tariff = load_elec_tariff()
    elec_week = load_week("electricity", week_start, week_end, all_data=raw, elec_tariff=elec_tariff)
    gas_week = load_week("gas", week_start, week_end, all_data=raw)

    elec_pivot = make_pivot(elec_week)
    gas_pivot = make_pivot(gas_week)
    elec_cost_week = elec_week[["timestamp", "cost_gbp"]].rename(columns={"cost_gbp": "value"})
    elec_cost_pivot = make_pivot(elec_cost_week)

    elec_vals = elec_pivot.values
    gas_vals = gas_pivot.values
    elec_vmax = np.percentile(elec_vals[elec_vals > 0], 97) if (elec_vals > 0).any() else 1.0
    gas_vmax = np.percentile(gas_vals[gas_vals > 0], 97) if (gas_vals > 0).any() else 1.0

    # Blended rate label for title
    peak_rate = max(elec_tariff.values())
    offpeak_rate = min(elec_tariff.values())

    fig, (ax_e, ax_g) = plt.subplots(1, 2, figsize=(18, 8))
    fig.suptitle(
        f"Meter {METER_NUMBER} (MPAN {MPAN})  —  Week {week_num}: "
        f"{week_start.strftime('%d %b')}–{week_end.strftime('%d %b %Y')}",
        fontsize=14, fontweight="bold",
    )

    im_e = draw_heatmap(ax_e, elec_pivot, plt.cm.Blues, elec_vmax,
                        "kWh", lambda v: f"{v:.1f} kWh",
                        cost_pivot=elec_cost_pivot)
    ax_e.set_title(f"Electricity consumption  ({offpeak_rate:.2f}p / {peak_rate:.2f}p per kWh)", fontsize=12)
    ax_e.set_ylabel("Time of day", fontsize=11)
    cb_e = fig.colorbar(im_e, ax=ax_e, shrink=0.8, pad=0.02)
    cb_e.set_label("kWh / half-hour", fontsize=10)

    im_g = draw_heatmap(ax_g, gas_pivot, plt.cm.YlOrRd, gas_vmax,
                        "m³", lambda v: f"{v:.1f} m³\n{v * GAS_KWH_PER_M3:.1f} kWh\n£{gas_cost_gbp(v):.2f}")
    ax_g.set_title(f"Gas consumption  (@ {GAS_RATE_P_KWH:.0f}p/kWh)", fontsize=12)
    ax_g.set_ylabel("Time of day", fontsize=11)
    cb_g = fig.colorbar(im_g, ax=ax_g, shrink=0.8, pad=0.02)
    cb_g.set_label("m³ / half-hour", fontsize=10)

    plt.tight_layout()
    out = f"{DATA_DIR}/m{METER_NUMBER}-elec-gas-wk{week_num}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Plot saved to {out}")


if __name__ == "__main__":
    main()
