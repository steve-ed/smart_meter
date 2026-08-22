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

group_bg   = {"EPC & Compliance": "#daeef9", "Financial": "#d6f0d6",
              "Risk & Safety": "#fde8cc",    "Fabric & Diagnosis": "#ead5f5",
              "Electrification": "#fdf5cc"}
group_hdr  = {"EPC & Compliance": "#1a6fa8", "Financial": "#2a7a2a",
              "Risk & Safety": "#b85c00",    "Fabric & Diagnosis": "#6a1f8e",
              "Electrification": "#8a6e00"}
dot_colour = {"EPC & Compliance": "#1a6fa8", "Financial": "#2a7a2a",
              "Risk & Safety": "#b85c00",    "Fabric & Diagnosis": "#6a1f8e",
              "Electrification": "#8a6e00"}

# Build row list: (type, label, group)  type = "header" | "feature"
rows = []
for group, feats in feature_groups.items():
    rows.append(("header", group, group))
    for f in feats:
        rows.append(("feature", f, group))

n_rows   = len(rows)
n_actors = len(actors)

cell   = 0.72          # inches per cell (square)
lpad   = 3.6           # left label column width
fig_w  = lpad + n_actors * cell
fig_h  = 1.4 + n_rows * cell   # 1.4 for top actor label area

fig = plt.figure(figsize=(fig_w, fig_h))

# Axes: x = 0..n_actors, y = 0..n_rows (inverted so row 0 is top)
ax = fig.add_axes([lpad / fig_w, 0.02, (n_actors * cell) / fig_w, (n_rows * cell) / fig_h])
ax.set_xlim(-0.5, n_actors - 0.5)
ax.set_ylim(n_rows - 0.5, -0.5)   # inverted
ax.set_aspect("equal")
ax.axis("off")

for row_i, (rtype, label, group) in enumerate(rows):
    bg = group_bg[group]
    hdr_c = group_hdr[group]

    if rtype == "header":
        # Full-width coloured header band
        ax.add_patch(mpatches.FancyBboxPatch(
            (-0.5, row_i - 0.45), n_actors, 0.9,
            boxstyle="square,pad=0", fc=hdr_c, ec="none", zorder=1))
        ax.text(-0.5, row_i, f"  {label}", va="center", ha="left",
                fontsize=8.5, fontweight="bold", color="white", zorder=3)
    else:
        # Feature row background
        ax.add_patch(mpatches.FancyBboxPatch(
            (-0.5, row_i - 0.45), n_actors, 0.9,
            boxstyle="square,pad=0", fc=bg, ec="none", zorder=1))
        # Vertical grid lines
        for col_i in range(n_actors):
            ax.axvline(col_i - 0.5, color="white", lw=1.0, zorder=2)
        # Dots
        vals = connectivity[label]
        for col_i, v in enumerate(vals):
            if v:
                ax.plot(col_i, row_i, "o", ms=10,
                        color=dot_colour[group],
                        mec="white", mew=1.0, zorder=4)

# Horizontal separators between groups
grp_rows = [i for i, (t, _, _) in enumerate(rows) if t == "header"]
for gr in grp_rows:
    ax.axhline(gr - 0.5, color="#888", lw=1.2, zorder=3)

# Feature labels — placed in figure coords to the left of the axes
ax_l = lpad / fig_w
ax_b = 0.02
ax_h = (n_rows * cell) / fig_h
row_h = ax_h / n_rows

for row_i, (rtype, label, group) in enumerate(rows):
    if rtype == "feature":
        # y position in figure coords (inverted axis: row 0 at top)
        y_fig = ax_b + ax_h - (row_i + 0.5) * row_h
        fig.text(ax_l - 0.008, y_fig, label,
                 ha="right", va="center", fontsize=8.0,
                 transform=fig.transFigure)

# Actor labels — rotated 45°, placed above the axes
ax_top = ax_b + ax_h
col_w  = (n_actors * cell) / fig_w / n_actors

for col_i, actor in enumerate(actors):
    x_fig = ax_l + (col_i + 0.5) * col_w
    fig.text(x_fig, ax_top + 0.008, actor,
             ha="left", va="bottom", fontsize=8.0, fontweight="bold",
             rotation=40, rotation_mode="anchor",
             transform=fig.transFigure)

fig.text(0.01, 0.99,
         "Smart Meter Analytics — Value-Added Features by Actor",
         ha="left", va="top", fontsize=10.5, fontweight="bold",
         transform=fig.transFigure)

out = "data/value_features_matrix.png"
plt.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
print(f"Written: {out}")
