"""
Timeline: MCP ecosystem for official statistics — three waves (v3, April 2026).
Updated from original (lost) script. Adds Wave 3 servers from landscape_v3 article.

Outputs: timeline_landscape_v3.{png,svg} (alongside this script by default)
Run:     python examples/generate_timeline_v3.py
Requires: matplotlib
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

# ── Palette (matches generate_visuals_v3.py) ─────────────────────────────────
BG      = "#FAFAFA"
DARK    = "#1E293B"
MID     = "#475569"
LIGHT   = "#94A3B8"
BLUE    = "#2563EB"
GREEN   = "#059669"
ORANGE  = "#D97706"
LBLUE   = "#DBEAFE"
LGREEN  = "#D1FAE5"
LORANGE = "#FEF3C7"

# ── Timeline data ─────────────────────────────────────────────────────────────
# Date as float year: 2025.5 = July 2025, 2026.25 = April 2026, etc.
# wave: 1=economic, 2=NSO/institutional, 3=UN/global
# row: 0=bottom, 1=middle, 2=top (within wave lane — for staggering)
# bold: highlight as notable entry


def q(year, quarter):
    """Convert year+quarter to float (midpoint of quarter)."""
    return year + (quarter - 1) * 0.25 + 0.125


SERVERS = [
    # Wave 1 — Economic data (late 2024)
    # official=False: community developers
    dict(label="FRED\n(stefanoamorelli)", date=2024.88,  wave=1, row=1, bold=False, official=False),
    dict(label="World Bank",              date=2024.96,  wave=1, row=0, bold=False, official=False),

    # Wave 2 — National and international statistics offices (2025-2026)
    dict(label="Netherlands CBS\nAustralia ABS",       date=q(2025,1), wave=2, row=2, bold=False, official=False),
    dict(label="Eurostat",                             date=q(2025,2), wave=2, row=0, bold=False, official=False),
    dict(label="IMF (PyPI)",                           date=2025.45,   wave=2, row=1, bold=False, official=False),
    dict(label="Ukraine",                              date=2025.50,   wave=2, row=2, bold=False, official=False),
    dict(label="Italy ISTAT",                          date=q(2025,3), wave=2, row=0, bold=False, official=False),
    dict(label="Brazil IBGE\n227 tests",               date=2025.63,   wave=2, row=2, bold=True,  official=False),
    dict(label="OECD\n9 tools + 7 resources",          date=2025.70,   wave=2, row=1, bold=True,  official=False),
    dict(label="US Census\n(official, CC0)",           date=q(2026,1), wave=2, row=2, bold=True,  official=True),
    dict(label="US GovInfo\n(GPO)",                    date=2026.04,   wave=2, row=0, bold=False, official=True),
    dict(label="France\ndata.gouv.fr",                 date=2026.12,   wave=2, row=2, bold=True,  official=True),
    dict(label="India MoSPI\n(first dev-country NSO)", date=2026.15,   wave=2, row=1, bold=True,  official=True),

    # Wave 3 — UN agencies and global aggregators (2025-2026)
    dict(label="Google Data\nCommons",            date=2025.71,  wave=3, row=1, bold=True,  official=True),
    dict(label="UNICEF\nsdmx-mcp",               date=2026.05,  wave=3, row=0, bold=False, official=True),
    dict(label="unicefstats-mcp\n(EQA = 0.990)", date=2026.12,  wave=3, row=2, bold=True,  official=False),
    dict(label="World Bank\ndata360-mcp",         date=2026.18,  wave=3, row=1, bold=False, official=True),
    dict(label="MacroNorm\n(IMF+WB+FRED)",        date=2026.23,  wave=3, row=0, bold=False, official=False),
    dict(label="FAO FAOSTAT\n245 countries",      date=2026.30,  wave=3, row=2, bold=True,  official=False),
]

# ── Layout constants ──────────────────────────────────────────────────────────
WAVE_CONFIG = {
    1: dict(y_center=8.5, y_height=1.8, color=ORANGE, bg=LORANGE, label="Wave 1\nEconomic data"),
    2: dict(y_center=5.0, y_height=3.2, color=BLUE,   bg=LBLUE,   label="Wave 2\nNational & international\nstatistics offices"),
    3: dict(y_center=1.3, y_height=2.2, color=GREEN,  bg=LGREEN,  label="Wave 3\nUN agencies & global aggregators"),
}
ROW_OFFSETS = {0: -0.5, 1: 0.0, 2: 0.5}  # vertical nudge within wave lane

X_MIN, X_MAX = 2024.75, 2026.50


def date_to_x(d):
    """Normalize date to [0, 1]."""
    return (d - X_MIN) / (X_MAX - X_MIN)


def main(out_dir: Path | None = None) -> None:
    """Render the timeline to {out_dir}/timeline_landscape_v3.{png,svg}.

    out_dir defaults to the directory containing this script.
    """
    if out_dir is None:
        out_dir = Path(__file__).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Build figure ──────────────────────────────────────────────────────────
    fig_w, fig_h = 14, 8.5  # wider for readability
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xlim(X_MIN, X_MAX)
    ax.set_ylim(-0.3, 10.8)
    ax.tick_params(left=False, labelleft=False)

    # ── Wave background bands ─────────────────────────────────────────────────
    for w, cfg in WAVE_CONFIG.items():
        yc, yh = cfg["y_center"], cfg["y_height"]
        rect = mpatches.FancyBboxPatch(
            (X_MIN + 0.01, yc - yh / 2), X_MAX - X_MIN - 0.02, yh,
            boxstyle="round,pad=0.02",
            facecolor=cfg["bg"], edgecolor=cfg["color"],
            linewidth=1.0, alpha=0.5, zorder=1,
        )
        ax.add_patch(rect)
        # Wave label on left
        ax.text(X_MIN + 0.02, yc, cfg["label"],
                va="center", ha="left", fontsize=9,
                color=cfg["color"], fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.25", facecolor=BG,
                          edgecolor=cfg["color"], linewidth=0.8, alpha=0.9),
                zorder=5)

    # ── Protocol release milestone ────────────────────────────────────────────
    mcp_x = 2024.88
    ax.axvline(mcp_x, color=DARK, linewidth=1.2, linestyle="--", alpha=0.4, zorder=2)
    ax.text(mcp_x, 10.2, "MCP protocol\nreleased\nNov 2024",
            ha="center", va="bottom", fontsize=8, color=MID, style="italic")

    # ── Server dots and labels ────────────────────────────────────────────────
    for s in SERVERS:
        w = s["wave"]
        cfg = WAVE_CONFIG[w]
        x = s["date"]
        y = cfg["y_center"] + ROW_OFFSETS[s["row"]]
        color = cfg["color"]
        size = 110 if s["bold"] else 65
        marker = "^" if s["official"] else "o"   # triangle=official, circle=community
        zorder = 5

        ax.scatter(x, y, s=size, color=color, marker=marker,
                   zorder=zorder + 1, edgecolors=DARK, linewidths=0.8)

        # Label — alternate above/below based on row
        label_dy = 0.38 if s["row"] == 2 else (-0.38 if s["row"] == 0 else 0.38)
        va = "bottom" if label_dy > 0 else "top"
        fw = "bold" if s["bold"] else "normal"
        ax.annotate(
            s["label"],
            xy=(x, y), xytext=(x, y + label_dy),
            ha="center", va=va, fontsize=7.5, color=DARK, fontweight=fw,
            arrowprops=dict(arrowstyle="-", color=color, lw=0.7, alpha=0.6),
            zorder=zorder,
        )

    # ── Legend: shape + size ──────────────────────────────────────────────────
    legend_handles = [
        plt.scatter([], [], marker="^", s=80, color=MID, edgecolors=DARK,
                    linewidths=0.8, label="Official (agency/government)"),
        plt.scatter([], [], marker="o", s=80, color=MID, edgecolors=DARK,
                    linewidths=0.8, label="Community"),
        plt.scatter([], [], marker="o", s=110, color=DARK, edgecolors=DARK,
                    linewidths=0.8, label="Notable design contribution (bold)"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", fontsize=8,
              framealpha=0.85, labelcolor=MID,
              bbox_to_anchor=(0.01, 0.98), borderpad=0.8)

    # ── X axis: quarterly tick marks ──────────────────────────────────────────
    ax.tick_params(bottom=True, labelbottom=True, labelsize=8.5, colors=MID)
    ticks = [2024.75, 2025.0, 2025.25, 2025.5, 2025.75, 2026.0, 2026.25, 2026.5]
    labels = ["Q4\n2024", "Q1\n2025", "Q2\n2025", "Q3\n2025",
              "Q4\n2025", "Q1\n2026", "Q2\n2026", "Q3\n2026"]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, color=MID)
    ax.xaxis.grid(True, color=LIGHT, linewidth=0.4, linestyle="--", alpha=0.5, zorder=0)

    # ── Count annotation ──────────────────────────────────────────────────────
    ax.text(X_MAX - 0.02, 10.4,
            "30+ servers\nin 18 months",
            ha="right", va="top", fontsize=11, color=DARK, fontweight="bold")

    # ── Title ─────────────────────────────────────────────────────────────────
    fig.suptitle(
        "MCP servers for official statistics: from protocol to ecosystem in 18 months",
        fontsize=13, fontweight="bold", color=DARK, y=0.98
    )
    ax.text(0.01, -0.07,
            "Notes:  Triangle = official agency/government server. Circle = community server. "
            "Bold = notable design contribution. Data: landscape review, April 2026.",
            transform=ax.transAxes, ha="left", fontsize=8.5, color=MID)

    # ── Save ──────────────────────────────────────────────────────────────────
    for fmt in ("png", "svg"):
        path = out_dir / f"timeline_landscape_v3.{fmt}"
        fig.savefig(path, dpi=100, bbox_inches="tight", facecolor=BG)
        print(f"  saved: {path}")

    plt.close(fig)
    print("Done.")


if __name__ == "__main__":
    main()
