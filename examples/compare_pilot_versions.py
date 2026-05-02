#!/usr/bin/env python3
"""Compare hallucination decomposition across server versions.

Reads parquet outputs from multiple pilot runs and prints a side-by-side
breakdown of:
  - hallucination rate (Condition A vs B, by tier)
  - country-substitution rate (B called get_data with wrong country)
  - tool-call success/failure rates
  - cost per query

Usage:
    python examples/compare_pilot_versions.py \\
        --runs v0.6.0=examples/results/eqa_*_mcp060_full.parquet \\
               v0.6.1=examples/results/eqa_*_mcp061_full_partial.parquet \\
               v0.6.2=examples/results/eqa_*_mcp062_corrected_resumed.parquet
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sys

import pandas as pd

# Ensure refined_extractor is importable when this script is invoked directly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refined_extractor import classify_response  # noqa: E402


def _call_country_match(call: dict, target_iso: str, target_name: str) -> bool:
    """True iff this get_data call mentions the target (by ISO3 or name)."""
    ctries = call.get("input", {}).get("countries", [])
    target_iso = (target_iso or "").upper()
    target_name = (target_name or "").upper()
    for ctry in ctries:
        if not isinstance(ctry, str):
            continue
        upper = ctry.upper()
        if target_iso and target_iso in upper:
            return True
        if target_name and target_name in upper:
            return True
    return False


def country_correctness(row) -> tuple[bool | None, bool | None]:
    """Returns (first_call_correct, any_call_correct).

    Each is None if no get_data call was made.
    first_call_correct: did the FIRST get_data call use the right country?
    any_call_correct:   did ANY get_data call (across all retries) hit the right country?
    """
    raw = row.get("b_tool_calls_json")
    if not raw or pd.isna(raw):
        return (None, None)
    try:
        calls = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return (None, None)
    target_iso = row.get("country_code", "")
    target_name = row.get("country_name", "") or ""
    get_calls = [c for c in calls if c.get("tool") == "get_data"]
    if not get_calls:
        return (None, None)
    first = _call_country_match(get_calls[0], target_iso, target_name)
    any_match = any(_call_country_match(c, target_iso, target_name) for c in get_calls)
    return (first, any_match)


def country_correct(row, target_col: str = "country_code") -> bool | None:
    """Backwards-compat wrapper: returns ANY-call correctness."""
    _, any_match = country_correctness(row)
    return any_match


def apply_refined_classifier(df: pd.DataFrame) -> pd.DataFrame:
    """Apply refined_extractor.classify_response to each row, adding columns:
    refined_atype, refined_true_fab, refined_fallback, refined_substitution.
    """
    classifications = []
    for _, row in df.iterrows():
        cr = classify_response(
            target_country_iso=row.get("country_code", ""),
            target_country_name=row.get("country_name", ""),
            target_year=int(row["year"]) if pd.notna(row.get("year")) else None,
            response_text=row.get("b_response_full", "") or "",
            tool_calls_json=row.get("b_tool_calls_json", "[]"),
            query_type=row.get("query_type", ""),
            prompt_type=row.get("prompt_type", "direct"),
        )
        classifications.append({
            "refined_atype": cr.assertion_type,
            "refined_true_fab": cr.is_true_fabrication,
            "refined_fallback": cr.is_graceful_fallback,
            "refined_substitution": cr.is_country_substitution,
            "refined_asserted_value": cr.asserted_value,
            "refined_asserted_year": cr.asserted_year,
        })
    return df.assign(**pd.DataFrame(classifications, index=df.index).to_dict("series"))


def analyse(df: pd.DataFrame, label: str):
    df = apply_refined_classifier(df)
    print(f"\n{'='*80}")
    print(f"Run: {label} — n={len(df)}")
    print(f"{'='*80}")

    if "b_rounds" in df.columns:
        df = df.copy()
        df["b_finished"] = df["b_rounds"] < df["b_rounds"].max() if df["b_rounds"].max() > 0 else True

    # Hallucination summary
    hall = df[df["query_type"].str.startswith("HALLUCINATION")]
    if len(hall) > 0:
        n = len(hall)
        h_a = hall["hall_a"].sum()
        h_b = hall["hall_b"].sum()
        print(f"\nHALLUCINATION ALL (n={n}):  A={h_a}/{n} ({h_a/n*100:.1f}%)   B={h_b}/{n} ({h_b/n*100:.1f}%)")
        for qt in ["HALLUCINATION_T1", "HALLUCINATION_T2"]:
            s = hall[hall["query_type"] == qt]
            if len(s):
                print(f"  {qt:<22s} (n={len(s)})  A={s['hall_a'].sum():3d}/{len(s)} ({s['hall_a'].mean()*100:5.1f}%)   B={s['hall_b'].sum():3d}/{len(s)} ({s['hall_b'].mean()*100:5.1f}%)")

        # REFINED metric: decompose Condition B "hallucinations" into
        # true fabrication / graceful fallback / country substitution
        print(f"\nREFINED B-side decomposition (hallucination tier, n={n}):")
        print(f"  TRUE fabrication       (model claims value for asked year): "
              f"{int(hall['refined_true_fab'].sum())}  ({hall['refined_true_fab'].mean()*100:.1f}%)")
        print(f"  Graceful fallback (T1) (refused asked year, offers other): "
              f"{int(hall['refined_fallback'].sum())}  ({hall['refined_fallback'].mean()*100:.1f}%)")
        print(f"  Country substitution   (called with wrong country, reports it): "
              f"{int(hall['refined_substitution'].sum())}  ({hall['refined_substitution'].mean()*100:.1f}%)")
        # Refused / unknown rates round out the picture
        refused = (hall["refined_atype"] == "refused").sum()
        unknown = (hall["refined_atype"] == "unknown").sum()
        print(f"  Clean refusal          (no number asserted): "
              f"{int(refused)}  ({refused/n*100:.1f}%)")
        print(f"  Unknown                (couldn't classify confidently): "
              f"{int(unknown)}  ({unknown/n*100:.1f}%)")

    # Country-correctness decomposition (Condition B) — track both first-call
    # and any-call correctness. v0.6.2's resolver allows the model to recover
    # from a wrong first guess, so the gap between first-call and any-call
    # quantifies how often the resolver enables retry-recovery.
    correctness = df.apply(country_correctness, axis=1, result_type="expand")
    df["country_first_correct"] = correctness[0]
    df["country_any_correct"] = correctness[1]
    df["country_correct"] = df["country_any_correct"]  # backwards-compat alias
    no_call = (df["country_any_correct"].isna()).sum()
    first_correct = (df["country_first_correct"] == True).sum()
    any_correct = (df["country_any_correct"] == True).sum()
    n_with_call = len(df) - no_call
    print(f"\nCondition B get_data country call (n_with_call={n_with_call}):")
    print(f"  FIRST-call correct: {first_correct}/{n_with_call} ({first_correct/max(n_with_call,1)*100:.1f}%)")
    print(f"  ANY-call correct:   {any_correct}/{n_with_call} ({any_correct/max(n_with_call,1)*100:.1f}%)")
    print(f"  No get_data call:   {no_call}/{len(df)} ({no_call/len(df)*100:.1f}%)")
    correct = any_correct
    wrong = n_with_call - any_correct

    # Hallucination conditional on correct country
    hall_correct = df[(df["country_correct"] == True) & df["query_type"].str.startswith("HALLUCINATION")]
    if len(hall_correct):
        h_b = hall_correct["hall_b"].sum()
        print(f"\nHallucination rate among correct-country queries: B={h_b}/{len(hall_correct)} ({h_b/len(hall_correct)*100:.1f}%)")
    hall_wrong = df[(df["country_correct"] == False) & df["query_type"].str.startswith("HALLUCINATION")]
    if len(hall_wrong):
        h_b = hall_wrong["hall_b"].sum()
        print(f"Hallucination rate among WRONG-country queries:    B={h_b}/{len(hall_wrong)} ({h_b/len(hall_wrong)*100:.1f}%)")

    # (The crude "year >= requested" fab check was here in earlier versions
    # but it overcounts because the regex picks an arbitrary year from
    # multi-year context lists. The refined classifier above replaces it
    # with a proper "model asserts value for the asked year" check.)

    # POSITIVE EQA
    pos = df[df["query_type"] == "POSITIVE"]
    if len(pos):
        print(f"\nPositive EQA (n={len(pos)}):  A={pos['eqa_a'].mean():.3f}   B={pos['eqa_b'].mean():.3f}")

    # Cost
    print(f"\nCost: A_total=${df['a_cost_usd'].sum():.4f}  B_total=${df['b_cost_usd'].sum():.4f}")
    print(f"      per-query  A=${df['a_cost_usd'].mean():.4f}  B=${df['b_cost_usd'].mean():.4f}")

    # Rounds (Condition B)
    if "b_rounds" in df.columns:
        rounds = df["b_rounds"].value_counts().sort_index().to_dict()
        print(f"\nB rounds distribution: {rounds}")

    return {
        "label": label,
        "n": len(df),
        "hall_b_rate_overall": float(hall["hall_b"].mean()) if len(hall) else None,
        "first_call_correct_pct": float(first_correct / max(n_with_call, 1) * 100),
        "any_call_correct_pct": float(any_correct / max(n_with_call, 1) * 100),
        "hall_b_given_correct_country": float(hall_correct["hall_b"].mean()) if len(hall_correct) else None,
        "hall_b_given_wrong_country": float(hall_wrong["hall_b"].mean()) if len(hall_wrong) else None,
        "pos_eqa_b": float(pos["eqa_b"].mean()) if len(pos) else None,
        "cost_b_per_query": float(df["b_cost_usd"].mean()),
        # Refined-metric counts (hallucination tier only)
        "refined_true_fab_pct": float(hall["refined_true_fab"].mean() * 100) if len(hall) else None,
        "refined_fallback_pct": float(hall["refined_fallback"].mean() * 100) if len(hall) else None,
        "refined_substitution_pct": float(hall["refined_substitution"].mean() * 100) if len(hall) else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True,
                        help="label=path pairs; path can be a glob")
    args = parser.parse_args()

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    summaries = []
    for spec in args.runs:
        if "=" not in spec:
            print(f"Skipping malformed --runs entry: {spec}")
            continue
        label, pattern = spec.split("=", 1)
        matches = sorted(glob.glob(pattern))
        if not matches:
            print(f"  WARN: no files match for {label}: {pattern}")
            continue
        # Take latest match
        path = matches[-1]
        df = pd.read_parquet(path)
        print(f"Loaded {path}  ({len(df)} rows)")
        summaries.append(analyse(df, label))

    print(f"\n{'='*80}")
    print("CROSS-RUN COMPARISON")
    print(f"{'='*80}\n")
    print(f"{'Run':<22s} {'OldHall':>8s} {'TrueFab':>8s} {'Fallbk':>7s} {'Subst':>7s} {'POS EQA':>9s} {'1st OK':>7s} {'Any OK':>7s} {'$/q':>8s}")
    print("-" * 95)
    for s in summaries:
        h_b = f"{s['hall_b_rate_overall']*100:.1f}%" if s['hall_b_rate_overall'] is not None else "—"
        tf = f"{s['refined_true_fab_pct']:.1f}%" if s.get('refined_true_fab_pct') is not None else "—"
        fb = f"{s['refined_fallback_pct']:.1f}%" if s.get('refined_fallback_pct') is not None else "—"
        sb = f"{s['refined_substitution_pct']:.1f}%" if s.get('refined_substitution_pct') is not None else "—"
        eqa = f"{s['pos_eqa_b']:.3f}" if s['pos_eqa_b'] is not None else "—"
        print(f"{s['label']:<22s} {h_b:>8s} {tf:>8s} {fb:>7s} {sb:>7s} {eqa:>9s} {s['first_call_correct_pct']:>6.1f}% {s['any_call_correct_pct']:>6.1f}% ${s['cost_b_per_query']:>6.4f}")


if __name__ == "__main__":
    main()
