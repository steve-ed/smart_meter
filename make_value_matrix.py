"""Generate value features matrix graphic — features (rows) vs actors (columns)."""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

actors = [
    "BTL Landlord",
    "HMO Landlord",
    "Seller",
    "Buyer",
    "Estate Agent",
    "Mortgage Broker",
    "EPC Assessor",
    "Heating Engineer",
    "Insulation Installer",
    "Solar Installer",
]

feature_groups = {
    "EPC & Compliance": [
        "Living EPC & performance gap",
        "Green mortgage evidence",
        "Indoor environment report",
        "Retrofit verification",
    ],
    "Financial": [
        "Verified running costs",
        "Peer benchmarking",
        "Tariff optimisation",
        "Battery size optimisation",
    ],
    "Risk & Safety": [
        "Frost & vacancy alerts",
        "Humidity & mould alerts",
        "Boiler efficiency trending",
        "Phantom load detection",
    ],
    "Fabric & Diagnosis": [
        "Thermal imaging",
        "Moisture mapping & CWI endoscope",
        "Flue gas analysis",
        "Retrofit readiness pack",
    ],
    "Electrification": [
        "Heat pump feasibility & radiator audit",
        "Solar monitoring & inverter API",
        "Carbon-aware demand shifting",
        "Per-room temperature sensors",
    ],
}

connectivity = {
    "Living EPC & performance gap":           [1, 1, 1, 1, 1, 1, 1, 0, 1, 0],
    "Green mortgage evidence":                [0, 0, 1, 1, 1, 1, 1, 0, 0, 0],
    "Indoor environment report":              [0, 1, 1, 0, 1, 0, 1, 0, 1, 0],
    "Retrofit verification":                  [0, 0, 1, 1, 0, 1, 1, 1, 1, 1],
    "Verified running costs":                 [0, 0, 1, 1, 1, 1, 0, 0, 0, 0],
    "Peer benchmarking":                      [1, 0, 1, 1, 0, 1, 0, 0, 0, 0],
    "Tariff optimisation":                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    "Battery size optimisation":              [0, 0, 1, 1, 0, 0, 0, 0, 0, 1],
    "Frost & vacancy alerts":                 [1, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    "Humidity & mould alerts":                [0, 1, 1, 1, 0, 0, 1, 0, 1, 0],
    "Boiler efficiency trending":             [1, 1, 1, 1, 1, 0, 1, 1, 0, 0],
    "Phantom load detection":                 [0, 1, 0, 0, 0, 0, 0, 0, 0, 1],
    "Thermal imaging":                        [0, 0, 1, 1, 1, 0, 1, 0, 1, 0],
    "Moisture mapping & CWI endoscope":       [0, 0, 1, 1, 1, 0, 1, 0, 1, 0],
    "Flue gas analysis":                      [0, 0, 0, 1, 0, 0, 1, 1, 0, 0],
    "Retrofit readiness pack":                [1, 1, 1, 1, 1, 0, 1, 0, 1, 0],
    "Heat pump feasibility & radiator audit": [1, 0, 1, 1, 0, 0, 1, 1, 0, 1],
    "Solar monitoring & inverter API":        [0, 0, 1, 1, 0, 0, 0, 0, 0, 1],
    "Carbon-aware demand shifting":           [0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    "Per-room temperature sensors":           [0, 1, 0, 0, 0, 0, 0, 0, 1, 0],
}

group_bg  = {"EPC & Compliance": "#daeef9", "Financial": "#d6f0d6",
             "Risk & Safety": "#fde8cc",    "Fabric & Diagnosis": "#ead5f5",
             "Electrification": "#fdf5cc"}
group_hdr = {"EPC & Compliance": "#1a6fa8", "Financial": "#2a7a2a",
             "Risk & Safety": "#b85c00",    "Fabric & Diagnosis": "#6a1f8e",
             "Electrification": "#8a6e00"}
dot_col   = {"EPC & Compliance": "#1a6fa8", "Financial": "#2a7a2a",
             "Risk & Safety": "#b85c00",    "Fabric & Diagnosis": "#6a1f8e",
             "Electrification": "#8a6e00"}

# Font sizes
FS_TITLE  = 40
FS_HDR    = 34
FS_FEAT   = 31
FS_ACTOR  = 31
DOT_MS    = 28

# Build row list
rows = []
for group, feats in feature_groups.items():
    rows.append(("header", group, group))
    for f in feats:
        rows.append(("feature", f, group))

n_rows   = len(rows)
n_actors = len(actors)

cell  = 2.3    # inches per cell
lpad  = 11.5   # left label area
rpad  = 0.9    # right padding to avoid clipping
fig_w = lpad + n_actors * cell + rpad
fig_h = 5.5 + n_rows * cell

fig = plt.figure(figsize=(fig_w, fig_h))

ax_l = lpad / fig_w
ax_b = 0.02
ax_w = (n_actors * cell) / fig_w
ax_h = (n_rows * cell) / fig_h

ax = fig.add_axes([ax_l, ax_b, ax_w, ax_h])
ax.set_xlim(-0.5, n_actors - 0.5)
ax.set_ylim(n_rows - 0.5, -0.5)
ax.set_aspect("equal")
ax.axis("off")

# Pass 1 — background patches (full width for every row)
for row_i, (rtype, label, group) in enumerate(rows):
    fc = group_hdr[group] if rtype == "header" else group_bg[group]
    ax.add_patch(mpatches.FancyBboxPatch(
        (-0.5, row_i - 0.49), n_actors, 0.98,
        boxstyle="square,pad=0", fc=fc, ec="none", zorder=1))

# Pass 2 — white column dividers on feature rows only (line segments, not axvline)
for row_i, (rtype, label, group) in enumerate(rows):
    if rtype == "feature":
        for col_i in range(n_actors + 1):
            x = col_i - 0.5
            ax.plot([x, x], [row_i - 0.49, row_i + 0.49],
                    color="white", lw=1.5, zorder=2, solid_capstyle="butt")

# Pass 3 — group divider lines between sections
for row_i, (rtype, _, _) in enumerate(rows):
    if rtype == "header" and row_i > 0:
        ax.plot([-0.5, n_actors - 0.5], [row_i - 0.5, row_i - 0.5],
                color="#666", lw=1.5, zorder=5)

# Pass 4 — header labels (centred in band) and dots
for row_i, (rtype, label, group) in enumerate(rows):
    if rtype == "header":
        ax.text((n_actors - 1) / 2, row_i, label,
                va="center", ha="center",
                fontsize=FS_HDR, fontweight="bold", color="white", zorder=3)
    else:
        for col_i, v in enumerate(connectivity[label]):
            if v:
                ax.plot(col_i, row_i, "o", ms=DOT_MS,
                        color=dot_col[group], mec="white", mew=1.5, zorder=4)

# Feature labels — left-aligned in left margin
row_h_fig = ax_h / n_rows
for row_i, (rtype, label, group) in enumerate(rows):
    if rtype == "feature":
        y_fig = ax_b + ax_h - (row_i + 0.5) * row_h_fig
        fig.text(0.01, y_fig, label,
                 ha="left", va="center", fontsize=FS_FEAT,
                 transform=fig.transFigure)

# Actor labels — rotated above axes
col_w_fig = ax_w / n_actors
ax_top = ax_b + ax_h
for col_i, actor in enumerate(actors):
    x_fig = ax_l + (col_i + 0.5) * col_w_fig
    fig.text(x_fig, ax_top + 0.006, actor,
             ha="left", va="bottom",
             fontsize=FS_ACTOR, fontweight="bold",
             rotation=40, rotation_mode="anchor",
             transform=fig.transFigure)

# Title
fig.text(0.01, 0.995,
         "Smart Meter Analytics — Value-Added Features by Actor",
         ha="left", va="top", fontsize=FS_TITLE, fontweight="bold",
         transform=fig.transFigure)

out = "data/value_features_matrix.png"
plt.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
print(f"Written: {out}")
