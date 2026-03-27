"""Generate publication-quality benchmark visualizations from parquet results."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

# --- Config ---
PARQUET = Path(__file__).parent / "results" / "eqa_claude-sonnet-4-20250514_20260323_174311.parquet"
OUTDIR = Path(__file__).parent / "figures"
OUTDIR.mkdir(exist_ok=True)

DOMAIN_MAP = {
    "CME_MRM0": "CME", "CME_MRY0": "CME", "CME_MRY0T4": "CME", "CME_MRY1T4": "CME",
    "NT_ANT_HAZ_NE2": "Nutrition", "NT_ANT_WAZ_NE2": "Nutrition", "NT_ANT_WHZ_NE2": "Nutrition",
    "MNCH_CSEC": "MNCH", "MNCH_BIRTH18": "MNCH",
    "ED_CR_L1": "Education",
}
DOMAIN_COLORS = {"CME": "#2171b5", "Nutrition": "#238b45", "MNCH": "#d94801", "Education": "#6a3d9a"}
SHORT_NAMES = {
    "CME_MRM0": "Neonatal\nmortality",
    "CME_MRY0": "Infant\nmortality",
    "CME_MRY0T4": "Under-5\nmortality",
    "CME_MRY1T4": "Child 1-4\nmortality",
    "ED_CR_L1": "Primary\ncompletion",
    "MNCH_BIRTH18": "Births\nunder 18",
    "MNCH_CSEC": "C-section\nrate",
    "NT_ANT_HAZ_NE2": "Stunting",
    "NT_ANT_WAZ_NE2": "Underweight",
    "NT_ANT_WHZ_NE2": "Wasting",
}
IND_ORDER = [
    "CME_MRM0", "CME_MRY0", "CME_MRY0T4", "CME_MRY1T4",
    "ED_CR_L1",
    "MNCH_BIRTH18", "MNCH_CSEC",
    "NT_ANT_HAZ_NE2", "NT_ANT_WAZ_NE2", "NT_ANT_WHZ_NE2",
]

# --- Style ---
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


def load_data() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["domain"] = df["indicator_code"].map(DOMAIN_MAP)
    df["short_name"] = df["indicator_code"].map(SHORT_NAMES)
    return df


def save(fig: plt.Figure, name: str) -> None:
    for fmt in ["png", "svg"]:
        fig.savefig(OUTDIR / f"{name}.{fmt}")
    plt.close(fig)
    print(f"  Saved: {name}.png, {name}.svg")


def fig1_eqa_by_indicator(df: pd.DataFrame) -> None:
    """Grouped bar chart: EQA by indicator, A vs B, baseline_latest."""
    pos = df[(df.query_type == "POSITIVE") & (df.prompt_type == "baseline_latest")]
    means = pos.groupby("indicator_code")[["eqa_a", "eqa_b"]].mean().reindex(IND_ORDER)

    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(IND_ORDER))
    w = 0.35

    bars_a = ax.bar(x - w / 2, means["eqa_a"], w, label="LLM alone", color="#bdbdbd", edgecolor="white")
    for i, ind in enumerate(IND_ORDER):
        c = DOMAIN_COLORS[DOMAIN_MAP[ind]]
        ax.bar(x[i] + w / 2, means.loc[ind, "eqa_b"], w, color=c, edgecolor="white")

    # Legend for domains
    from matplotlib.patches import Patch
    handles = [Patch(facecolor="#bdbdbd", label="LLM alone")]
    for d in ["CME", "Nutrition", "MNCH", "Education"]:
        handles.append(Patch(facecolor=DOMAIN_COLORS[d], label=f"LLM + MCP ({d})"))
    ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels([SHORT_NAMES[i] for i in IND_ORDER], fontsize=8)
    ax.set_ylabel("Mean EQA")
    ax.set_ylim(0, 1.1)
    ax.set_title("Figure 1: EQA by Indicator — baseline_latest prompt (n=10 per indicator)")
    ax.axhline(y=1.0, color="#cccccc", linewidth=0.5, linestyle="--")

    save(fig, "fig1_eqa_by_indicator")


def fig2_component_decomposition(df: pd.DataFrame) -> None:
    """Stacked bar: ER, YA, VA for MCP condition, baseline_latest."""
    pos = df[(df.query_type == "POSITIVE") & (df.prompt_type == "baseline_latest")]
    means = pos.groupby("indicator_code")[["er_b", "ya_b", "va_b"]].mean().reindex(IND_ORDER)

    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(IND_ORDER))
    w = 0.6

    # EQA = ER × YA × VA, but for visualization show as grouped bars (not stacked, since they multiply)
    ax.bar(x - w / 3, means["er_b"], w / 3, label="ER (extraction)", color="#4292c6")
    ax.bar(x, means["ya_b"], w / 3, label="YA (year accuracy)", color="#41ab5d")
    ax.bar(x + w / 3, means["va_b"], w / 3, label="VA (value accuracy)", color="#ef6548")

    ax.legend(loc="lower right", frameon=False, fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([SHORT_NAMES[i] for i in IND_ORDER], fontsize=8)
    ax.set_ylabel("Component Score")
    ax.set_ylim(0, 1.1)
    ax.set_title("Figure 2: EQA Component Decomposition — LLM + MCP, baseline_latest")
    ax.axhline(y=1.0, color="#cccccc", linewidth=0.5, linestyle="--")

    save(fig, "fig2_component_decomposition")


def fig3_latest_vs_direct(df: pd.DataFrame) -> None:
    """2x1 panel: latest vs direct EQA for A and B."""
    pos = df[df.query_type == "POSITIVE"]
    latest = pos[pos.prompt_type == "baseline_latest"].groupby("indicator_code")[["eqa_a", "eqa_b"]].mean().reindex(IND_ORDER)
    direct = pos[pos.prompt_type == "direct"].groupby("indicator_code")[["eqa_a", "eqa_b"]].mean().reindex(IND_ORDER)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    x = np.arange(len(IND_ORDER))
    w = 0.35

    for ax, data, title in [
        (ax1, latest, "baseline_latest (EQA = ER × YA × VA)"),
        (ax2, direct, "direct (EQA = ER × VA)"),
    ]:
        ax.bar(x - w / 2, data["eqa_a"], w, label="LLM alone", color="#bdbdbd", edgecolor="white")
        for i, ind in enumerate(IND_ORDER):
            ax.bar(x[i] + w / 2, data.loc[ind, "eqa_b"], w, color=DOMAIN_COLORS[DOMAIN_MAP[ind]], edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels([SHORT_NAMES[i] for i in IND_ORDER], fontsize=7, rotation=45, ha="right")
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, 1.1)
        ax.axhline(y=1.0, color="#cccccc", linewidth=0.5, linestyle="--")

    ax1.set_ylabel("Mean EQA")
    fig.suptitle("Figure 3: Latest vs Direct Prompt Comparison", fontsize=12, y=1.02)
    fig.tight_layout()

    save(fig, "fig3_latest_vs_direct")


def fig4_hallucination(df: pd.DataFrame) -> None:
    """Grouped bar: hallucination rates for T1 and T2."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    for ax, qt, title in [
        (ax1, "HALLUCINATION_T1", "T1: Gap Years (n=50)"),
        (ax2, "HALLUCINATION_T2", "T2: Never Existed (n=50)"),
    ]:
        h = df[df.query_type == qt]
        rates = h.groupby("indicator_code")[["hall_a", "hall_b"]].mean().reindex(IND_ORDER).fillna(0)

        x = np.arange(len(IND_ORDER))
        w = 0.35
        ax.bar(x - w / 2, rates["hall_a"] * 100, w, label="LLM alone", color="#bdbdbd", edgecolor="white")
        for i, ind in enumerate(IND_ORDER):
            ax.bar(x[i] + w / 2, rates.loc[ind, "hall_b"] * 100, w, color=DOMAIN_COLORS[DOMAIN_MAP[ind]], edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels([SHORT_NAMES[i] for i in IND_ORDER], fontsize=7, rotation=45, ha="right")
        ax.set_ylabel("Hallucination Rate (%)")
        ax.set_ylim(0, 105)
        ax.set_title(title, fontsize=10)

    from matplotlib.patches import Patch
    handles = [Patch(facecolor="#bdbdbd", label="LLM alone")]
    for d in ["CME", "Nutrition", "MNCH", "Education"]:
        handles.append(Patch(facecolor=DOMAIN_COLORS[d], label=f"LLM + MCP ({d})"))
    ax2.legend(handles=handles, loc="upper right", frameon=False, fontsize=8)

    fig.suptitle("Figure 4: Hallucination Rates by Indicator", fontsize=12, y=1.02)
    fig.tight_layout()

    save(fig, "fig4_hallucination")


def fig5_cost_accuracy(df: pd.DataFrame) -> None:
    """Scatter: cost per query vs EQA, by indicator and condition."""
    pos = df[(df.query_type == "POSITIVE") & (df.prompt_type == "baseline_latest")]

    fig, ax = plt.subplots(figsize=(8, 6))

    for ind in IND_ORDER:
        sub = pos[pos.indicator_code == ind]
        domain = DOMAIN_MAP[ind]
        c = DOMAIN_COLORS[domain]

        # Condition A
        cost_a = sub["a_cost_usd"].mean() * 1000  # millicents → cents
        eqa_a = sub["eqa_a"].mean()
        ax.scatter(cost_a, eqa_a, color="#bdbdbd", s=60, zorder=2, edgecolors="white")

        # Condition B
        cost_b = sub["b_cost_usd"].mean() * 1000
        eqa_b = sub["eqa_b"].mean()
        ax.scatter(cost_b, eqa_b, color=c, s=80, zorder=3, edgecolors="white")

        # Connect A → B with arrow
        ax.annotate("", xy=(cost_b, eqa_b), xytext=(cost_a, eqa_a),
                     arrowprops=dict(arrowstyle="->", color=c, alpha=0.4, lw=1))

        # Label B point
        ax.annotate(SHORT_NAMES[ind].replace("\n", " "), (cost_b, eqa_b),
                     textcoords="offset points", xytext=(5, 5), fontsize=7, color=c)

    ax.set_xlabel("Cost per query (millicents)")
    ax.set_ylabel("Mean EQA")
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Figure 5: Cost–Accuracy Tradeoff (baseline_latest)")

    from matplotlib.patches import Patch
    handles = [Patch(facecolor="#bdbdbd", label="LLM alone")]
    for d in ["CME", "Nutrition", "MNCH", "Education"]:
        handles.append(Patch(facecolor=DOMAIN_COLORS[d], label=f"LLM + MCP ({d})"))
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=8)

    save(fig, "fig5_cost_accuracy")


if __name__ == "__main__":
    print("Loading data...")
    df = load_data()
    print(f"  {len(df)} queries from {PARQUET.name}")

    print("\nGenerating figures...")
    fig1_eqa_by_indicator(df)
    fig2_component_decomposition(df)
    fig3_latest_vs_direct(df)
    fig4_hallucination(df)
    fig5_cost_accuracy(df)

    print(f"\nDone. All figures saved to {OUTDIR}/")
