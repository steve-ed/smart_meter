"""
Annual pattern analysis for Meter 1 (MPAN 1234567891000).

Produces a 2x2 figure:
  Top row    — "typical week" heatmap (mean consumption per day-of-week × half-hour slot)
  Bottom row — weekly totals bar chart (one bar per ISO week)

Covers the last 52 complete Mon–Sun weeks of available data.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

MPAN = "1234567891000"
METER_NUMBER = 1
DATA_DIR = "data"

GAS_CAP = 2.0          # m³/half-hour — excludes both sentinel variants (16 777.215 and 16 777 215)
ELEC_CAP = 15.0        # kWh/half-hour — above any plausible UK domestic reading
GAS_KWH_PER_M3 = 11.2  # calorific value conversion
GAS_RATE_P_KWH = 6.0   # pence per kWh (Ofgem cap — verify current rate)


def gas_cost_gbp(m3):
    return m3 * GAS_KWH_PER_M3 * GAS_RATE_P_KWH / 100


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def last_complete_week_bounds(series_of_dates, n_weeks=52):
    """Return (start, end) for the last n_weeks complete Mon–Sun weeks."""
    latest = series_of_dates.max()
    # Roll back to the most recent Sunday
    end = latest - pd.Timedelta(days=(latest.day_of_week + 1) % 7)
    end = end.normalize()
    start = end - pd.Timedelta(weeks=n_weeks) + pd.Timedelta(days=1)
    return start, end


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


def load_and_clean(utility, cap, elec_tariff=None):
    raw = pd.read_csv(f"{DATA_DIR}/consumption.csv")
    df = raw[(raw["mpxn"] == int(MPAN)) & (raw["utility"] == utility)][
        ["timestamp", "value"]
    ].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df[df["value"] <= cap]
    df = df.drop_duplicates(subset="timestamp", keep="first")
    df = df.sort_values("timestamp")

    if utility == "electricity" and elec_tariff:
        df["rate_p"] = df["timestamp"].dt.time.map(elec_tariff).fillna(0.0)
        df["cost_gbp"] = df["value"] * df["rate_p"] / 100
    elif utility == "gas":
        df["cost_gbp"] = df["value"].apply(gas_cost_gbp)

    return df


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def add_time_features(df):
    df = df.copy()
    df["date"] = df["timestamp"].dt.normalize()
    df["iso_year"] = df["timestamp"].dt.isocalendar().year.astype(int)
    df["week"] = df["timestamp"].dt.isocalendar().week.astype(int)
    df["dow"] = df["timestamp"].dt.day_of_week          # 0=Mon … 6=Sun
    df["slot"] = df["timestamp"].dt.hour * 2 + df["timestamp"].dt.minute // 30
    return df


def restrict_to_year(df, start, end):
    return df[(df["timestamp"] >= start) & (df["timestamp"] <= end + pd.Timedelta(hours=23, minutes=30))]


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TIME_LABELS = [f"{h:02d}:00" for h in range(0, 24, 2)]   # every 2 h


def draw_typical_week(ax, df, cmap, unit_label, title, kwh_per_unit=None):
    pivot = df.groupby(["slot", "dow"])["value"].mean().unstack(level="dow")
    pivot = pivot.reindex(columns=range(7))

    has_cost = "cost_gbp" in df.columns
    if has_cost:
        cost_pivot = df.groupby(["slot", "dow"])["cost_gbp"].mean().unstack(level="dow")
        cost_pivot = cost_pivot.reindex(columns=range(7))

    im = ax.imshow(
        pivot.values,
        aspect="auto",
        origin="upper",
        cmap=cmap,
        vmin=0,
        vmax=np.nanpercentile(pivot.values, 97),
        interpolation="nearest",
    )
    daily_means = pivot.sum(axis=0)
    unit = unit_label.split("/")[0].strip()
    xtick_labels = []
    for d in range(7):
        v = daily_means.get(d, 0)
        label = f"{DOW_LABELS[d]}\n{v:.2f} {unit}"
        if kwh_per_unit:
            label += f"\n{v * kwh_per_unit:.1f} kWh"
        if has_cost:
            label += f"\n£{cost_pivot.sum(axis=0).get(d, 0):.2f}"
        xtick_labels.append(label)

    ax.set_xticks(range(7))
    ax.set_xticklabels(xtick_labels, fontsize=9)
    ax.set_yticks(range(0, 48, 4))
    ax.set_yticklabels(TIME_LABELS, fontsize=9)
    ax.set_ylabel("Time of day", fontsize=10)
    ax.set_title(title, fontsize=11)

    week_total = daily_means.sum()
    summary = f"Avg week total: {week_total:.2f} {unit}"
    if kwh_per_unit:
        summary += f" / {week_total * kwh_per_unit:.1f} kWh"
    if has_cost:
        summary += f"  /  £{cost_pivot.values.sum():.2f}"
    ax.text(0.99, 0.01, summary,
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    cb = ax.get_figure().colorbar(im, ax=ax, shrink=0.85, pad=0.02)
    cb.set_label(unit_label, fontsize=9)
    return pivot


def draw_weekly_totals(ax, df, color, unit_label, title, year_label, kwh_per_unit=None):
    has_cost = "cost_gbp" in df.columns
    agg = {"value": "sum"}
    if has_cost:
        agg["cost_gbp"] = "sum"

    weekly = (
        df.groupby(["iso_year", "week"])
        .agg(agg)
        .reset_index()
        .sort_values(["iso_year", "week"])
    )
    xs = list(range(len(weekly)))
    ax.bar(xs, weekly["value"], color=color, alpha=0.75, width=0.8)

    unit = unit_label.split("/")[0].strip()
    for i, (_, row) in enumerate(weekly.iterrows()):
        label = f"{row['value']:.0f} {unit}"
        if kwh_per_unit:
            label += f"\n{row['value'] * kwh_per_unit:.0f} kWh"
        if has_cost:
            label += f"\n£{row['cost_gbp']:.0f}"
        ax.text(xs[i], row["value"] + weekly["value"].max() * 0.01, label,
                ha="center", va="bottom", fontsize=6, rotation=90, color="#333333")

    tick_pos = list(range(0, len(weekly), 4))
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(
        [f"Wk {weekly.iloc[i]['week']:.0f}" for i in tick_pos],
        fontsize=8, rotation=45, ha="right",
    )
    ax.set_ylabel(unit_label, fontsize=10)
    ax.set_title(title, fontsize=11)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(0, weekly["value"].max() * 1.45)

    mean_val = weekly["value"].mean()
    year_total = weekly["value"].sum()
    legend_text = f"Mean {mean_val:.1f} {unit}/wk  |  Year total {year_total:.0f} {unit}"
    if kwh_per_unit:
        legend_text += f" / {year_total * kwh_per_unit:.0f} kWh"
    if has_cost:
        legend_text += f"  /  £{weekly['cost_gbp'].sum():.0f}"
    ax.axhline(mean_val, color="#032147", linewidth=1.2, linestyle="--", alpha=0.7,
               label=legend_text)
    ax.legend(fontsize=9)

    ax.text(0.99, 0.97, year_label, transform=ax.transAxes,
            ha="right", va="top", fontsize=9, color="#888888")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    elec_tariff = load_elec_tariff()
    peak_rate = max(elec_tariff.values())
    offpeak_rate = min(elec_tariff.values())

    elec = load_and_clean("electricity", ELEC_CAP, elec_tariff=elec_tariff)
    gas  = load_and_clean("gas",         GAS_CAP)

    # Use electricity range to anchor the year window (gas has same coverage)
    start, end = last_complete_week_bounds(elec["timestamp"])
    year_label = f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"
    week_num = end.isocalendar()[1]

    elec = add_time_features(restrict_to_year(elec, start, end))
    gas  = add_time_features(restrict_to_year(gas,  start, end))

    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle(
        f"Meter {METER_NUMBER} (MPAN {MPAN})  —  Annual Pattern Analysis\n{year_label}",
        fontsize=14, fontweight="bold",
    )

    gas_rate_note = f"@ {GAS_RATE_P_KWH:.0f}p/kWh"
    elec_rate_note = f"{offpeak_rate:.2f}p / {peak_rate:.2f}p per kWh"

    draw_typical_week(axes[0, 0], elec, plt.cm.Blues,
                      "kWh / half-hour", f"Electricity — typical week (mean)  [{elec_rate_note}]")
    draw_typical_week(axes[0, 1], gas,  plt.cm.YlOrRd,
                      "m³ / half-hour",  f"Gas — typical week (mean)  [{gas_rate_note}]",
                      kwh_per_unit=GAS_KWH_PER_M3)

    draw_weekly_totals(axes[1, 0], elec, "#209dd7",
                       "kWh / week", f"Electricity — weekly totals  [{elec_rate_note}]", year_label)
    draw_weekly_totals(axes[1, 1], gas,  "#e05c00",
                       "m³ / week",  f"Gas — weekly totals  [{gas_rate_note}]", year_label,
                       kwh_per_unit=GAS_KWH_PER_M3)

    plt.tight_layout()
    out = f"{DATA_DIR}/m{METER_NUMBER}-annual-wk{week_num}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Plot saved to {out}")


if __name__ == "__main__":
    main()
