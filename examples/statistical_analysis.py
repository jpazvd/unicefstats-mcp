"""Statistical analysis of benchmark results with CIs, significance tests, and effect sizes."""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

PARQUET = Path(__file__).parent / "results" / "eqa_claude-sonnet-4-20250514_20260323_174311.parquet"
OUTDIR = Path(__file__).parent / "results"
N_BOOT = 10_000
SEED = 20260322
rng = np.random.default_rng(SEED)


def bootstrap_ci(data: np.ndarray, n_boot: int = N_BOOT, ci: float = 0.95) -> tuple:
    """Bootstrap percentile CI for the mean."""
    means = np.array([rng.choice(data, size=len(data), replace=True).mean() for _ in range(n_boot)])
    alpha = (1 - ci) / 2
    return float(np.percentile(means, alpha * 100)), float(np.percentile(means, (1 - alpha) * 100))


def bootstrap_diff_ci(a: np.ndarray, b: np.ndarray, n_boot: int = N_BOOT) -> tuple:
    """Bootstrap CI for paired mean difference (B - A)."""
    diffs = b - a
    means = np.array([rng.choice(diffs, size=len(diffs), replace=True).mean() for _ in range(n_boot)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d for paired samples."""
    diff = b - a
    return float(diff.mean() / diff.std(ddof=1)) if diff.std(ddof=1) > 0 else 0.0


def mcnemar_test(a: np.ndarray, b: np.ndarray) -> dict:
    """McNemar's test for paired binary outcomes."""
    # a, b are boolean arrays (True = hallucinated)
    b01 = ((~a) & b).sum()  # A correct, B hallucinated
    b10 = (a & (~b)).sum()  # A hallucinated, B correct
    n = b01 + b10
    if n == 0:
        return {"chi2": 0, "p": 1.0, "b01": int(b01), "b10": int(b10)}
    chi2 = (abs(b01 - b10) - 1) ** 2 / n  # continuity correction
    p = float(stats.chi2.sf(chi2, df=1))
    return {"chi2": float(chi2), "p": p, "b01": int(b01), "b10": int(b10)}


def main():
    df = pd.read_parquet(PARQUET)
    lines = []

    def pr(s=""):
        print(s)
        lines.append(s)

    pr("# Statistical Analysis of Benchmark Results")
    pr(f"\nParquet: `{PARQUET.name}` | n={len(df)} queries | Bootstrap: {N_BOOT} iterations")
    pr(f"Seed: {SEED}")

    # ========== 1. PAIRED TESTS FOR POSITIVE QUERIES ==========
    for prompt, formula in [("baseline_latest", "EQA = ER x YA x VA"), ("direct", "EQA = ER x VA")]:
        pos = df[(df.query_type == "POSITIVE") & (df.prompt_type == prompt)]
        a = pos["eqa_a"].values
        b = pos["eqa_b"].values

        wilcoxon = stats.wilcoxon(a, b, alternative="two-sided")
        d = cohens_d(a, b)
        ci_diff = bootstrap_diff_ci(a, b)
        ci_a = bootstrap_ci(a)
        ci_b = bootstrap_ci(b)

        pr(f"\n## 1. Positive queries: {prompt} (n={len(pos)}) -- {formula}")
        pr(f"\n| Metric | LLM alone (A) | LLM + MCP (B) |")
        pr(f"|--------|---------------|---------------|")
        pr(f"| Mean EQA | {a.mean():.3f} [{ci_a[0]:.3f}, {ci_a[1]:.3f}] | {b.mean():.3f} [{ci_b[0]:.3f}, {ci_b[1]:.3f}] |")
        pr(f"| Mean difference (B - A) | {(b-a).mean():+.3f} [{ci_diff[0]:+.3f}, {ci_diff[1]:+.3f}] | |")
        pr(f"| Wilcoxon signed-rank | W={wilcoxon.statistic:.1f}, p={wilcoxon.pvalue:.2e} | |")
        pr(f"| Cohen's d | {d:.2f} | |")
        pr(f"| Effect size interpretation | {'large' if abs(d) >= 0.8 else 'medium' if abs(d) >= 0.5 else 'small'} | |")

        # Component analysis
        pr(f"\n### Component contribution to EQA gain ({prompt})")
        for comp in ["er", "ya", "va"] if prompt == "baseline_latest" else ["er", "va"]:
            ca = pos[f"{comp}_a"].values
            cb = pos[f"{comp}_b"].values
            diff_mean = (cb - ca).mean()
            ci = bootstrap_diff_ci(ca, cb)
            pr(f"- d{comp.upper()}: {diff_mean:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]")

    # ========== 2. HALLUCINATION TESTS ==========
    pr("\n## 2. Hallucination analysis")

    for qt in ["HALLUCINATION_T1", "HALLUCINATION_T2"]:
        h = df[df.query_type == qt]
        a_hall = h["hall_a"].values.astype(bool)
        b_hall = h["hall_b"].values.astype(bool)
        mc = mcnemar_test(a_hall, b_hall)

        pr(f"\n### {qt} (n={len(h)})")
        pr(f"- A hallucination rate: {a_hall.mean()*100:.0f}% ({a_hall.sum()}/{len(h)})")
        pr(f"- B hallucination rate: {b_hall.mean()*100:.0f}% ({b_hall.sum()}/{len(h)})")
        pr(f"- McNemar's test: chi2={mc['chi2']:.2f}, p={mc['p']:.4f}")
        pr(f"- Discordant pairs: A-only={mc['b10']}, B-only={mc['b01']}")
        pr(f"- Significant at alpha=0.05: {'Yes' if mc['p'] < 0.05 else 'No'}")

        # Fisher's exact by indicator group
        pr(f"\n  Fisher's exact by indicator:")
        for ind in sorted(h.indicator_code.unique()):
            sub = h[h.indicator_code == ind]
            sa = sub["hall_a"].values.astype(bool)
            sb = sub["hall_b"].values.astype(bool)
            # 2x2 table: [A_hall, A_ok], [B_hall, B_ok]
            table = [[sa.sum(), (~sa).sum()], [sb.sum(), (~sb).sum()]]
            _, p_fisher = stats.fisher_exact(table)
            pr(f"  - {ind}: A={sa.sum()}/{len(sub)}, B={sb.sum()}/{len(sub)}, Fisher p={p_fisher:.3f}")

    # ========== 3. CORRELATION MATRIX ==========
    pr("\n## 3. Component correlation matrix (positive queries, B condition)")
    pos_all = df[df.query_type == "POSITIVE"]
    corr_cols = ["er_b", "ya_b", "va_b", "eqa_b"]
    corr = pos_all[corr_cols].corr()
    pr(f"\n| | ER_B | YA_B | VA_B | EQA_B |")
    pr(f"|---|---|---|---|---|")
    for row in corr_cols:
        vals = " | ".join(f"{corr.loc[row, c]:.3f}" for c in corr_cols)
        pr(f"| {row} | {vals} |")

    # ========== 4. PER-INDICATOR CIs ==========
    pr("\n## 4. Per-indicator EQA_B with 95% bootstrap CI")
    pr(f"\n| Indicator | n | EQA_B mean | 95% CI | Significant vs A? |")
    pr(f"|-----------|---|-----------|--------|-------------------|")

    pos_latest = df[(df.query_type == "POSITIVE") & (df.prompt_type == "baseline_latest")]
    p_values = []
    for ind in sorted(pos_latest.indicator_code.unique()):
        sub = pos_latest[pos_latest.indicator_code == ind]
        a = sub["eqa_a"].values
        b = sub["eqa_b"].values
        ci = bootstrap_ci(b)
        try:
            w = stats.wilcoxon(a, b, alternative="two-sided")
            p = w.pvalue
        except ValueError:
            p = 1.0  # all zeros
        p_values.append((ind, len(sub), b.mean(), ci, p))

    # Holm-Bonferroni correction
    sorted_pvals = sorted(p_values, key=lambda x: x[4])
    m = len(sorted_pvals)
    for rank, (ind, n, mean_b, ci, p) in enumerate(sorted_pvals):
        adjusted_alpha = 0.05 / (m - rank)
        sig = "Yes" if p < adjusted_alpha else "No"
        for item in p_values:
            if item[0] == ind:
                p_values[p_values.index(item)] = (ind, n, mean_b, ci, p, sig)

    for ind, n, mean_b, ci, p, sig in sorted(p_values, key=lambda x: x[0]):
        pr(f"| {ind} | {n} | {mean_b:.3f} | [{ci[0]:.3f}, {ci[1]:.3f}] | {sig} (p={p:.3e}) |")

    # ========== SAVE ==========
    outfile = OUTDIR / "statistical_summary.md"
    outfile.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved: {outfile}")


if __name__ == "__main__":
    main()
