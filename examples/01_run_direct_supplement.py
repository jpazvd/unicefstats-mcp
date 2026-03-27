#!/usr/bin/env python3
"""Supplement: run 100 direct positive queries for existing indicator-country-year combos.

Takes the existing 200-query parquet (baseline_latest + T1 + T2) and runs the
same 100 positive (indicator, country, year) combos with the direct prompt:
  "What was {indicator} for {country} in {year}?"

Then merges into a combined 300-row parquet.

Usage:
    python examples/01_run_direct_supplement.py [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import warnings
from datetime import datetime, timezone

warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.disable(logging.INFO)

from dotenv import load_dotenv
load_dotenv()

import anthropic
import pandas as pd

# Reuse benchmark machinery
from benchmark_eqa import (
    DEFAULT_MODEL,
    EXTRACTOR_VERSION,
    MAX_TOKENS,
    MCP_TOOLS,
    TEMPERATURE,
    call_llm_alone,
    call_llm_with_mcp,
    compute_er,
    compute_va,
    extract_numeric,
    extract_year,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing", default=None, help="Path to existing 200-query parquet")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    # Find existing parquet
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if args.existing:
        existing_path = args.existing
    else:
        parquets = sorted(
            [f for f in os.listdir(results_dir) if f.endswith(".parquet")],
            reverse=True,
        )
        if not parquets:
            print("ERROR: No existing parquet found in examples/results/")
            sys.exit(1)
        existing_path = os.path.join(results_dir, parquets[0])

    print("=" * 90)
    print("Direct Positive Supplement — 100 queries")
    print("=" * 90)
    print(f"Existing parquet: {existing_path}")

    existing = pd.read_parquet(existing_path)
    print(f"Existing rows: {len(existing)}")

    # Extract positive cases to re-query with direct prompt
    pos = existing[existing["query_type"] == "POSITIVE"].copy()
    print(f"Positive cases to supplement: {len(pos)}")

    if args.limit > 0:
        pos = pos.head(args.limit)
        print(f"Limited to: {len(pos)}")

    print(f"Model: {args.model}")
    print(f"Temperature: {TEMPERATURE}")
    print()

    if args.dry_run:
        print("[DRY RUN]\n")
        for i, (_, row) in enumerate(pos.iterrows(), 1):
            year = int(row["year"]) if pd.notna(row["year"]) else int(row.get("gt_year", 2023))
            prompt = f"What was {row['indicator_name']} for {row['country_name']} in {year}?"
            print(f"  [{i:3d}/{len(pos)}] {row['indicator_code']} x {row['country_code']} x {year}  [dry run]")
        return

    client = anthropic.Anthropic()
    if not client.api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_slug = args.model.replace("/", "_").replace(":", "_")
    run_id = f"{model_slug}_{ts}_direct_supplement"

    new_rows = []

    for i, (_, row) in enumerate(pos.iterrows(), 1):
        year = int(row["year"]) if pd.notna(row["year"]) else int(row.get("gt_year", 2023))
        gt_val = row.get("gt_value") or row.get("gt_latest_value")
        if pd.isna(gt_val):
            gt_val = None
        else:
            gt_val = float(gt_val)

        prompt = f"What was {row['indicator_name']} for {row['country_name']} in {year}?"
        label = f"{row['indicator_code']} x {row['country_code']} x {year}"
        print(f"  [{i:3d}/{len(pos)}] {label:<40s}", end="", flush=True)

        # Condition A
        resp_a = call_llm_alone(client, args.model, prompt)
        # Condition B
        resp_b = call_llm_with_mcp(client, args.model, prompt)

        # Score (direct: YA = 1.0)
        er_a = compute_er(resp_a["value"])
        er_b = compute_er(resp_b["value"])
        va_a = compute_va(resp_a["value"], gt_val) if gt_val else 0.0
        va_b = compute_va(resp_b["value"], gt_val) if gt_val else 0.0
        eqa_a = er_a * va_a  # YA = 1.0
        eqa_b = er_b * va_b

        query_id = f"{row['indicator_code']}_{row['country_code']}_{year}_direct"

        new_rows.append({
            "run_id": run_id,
            "query_id": query_id,
            "model": args.model,
            "temperature": TEMPERATURE,
            "timestamp": ts,
            "extractor_version": EXTRACTOR_VERSION,
            "indicator_code": row["indicator_code"],
            "indicator_name": row["indicator_name"],
            "unit": row["unit"],
            "country_code": row["country_code"],
            "country_name": row["country_name"],
            "year": year,
            "query_type": "POSITIVE",
            "prompt_type": "direct",
            "prompt_text": prompt,
            "gt_value": gt_val,
            "gt_year": float(year),
            "gt_latest_year": row.get("gt_latest_year"),
            "gt_latest_value": row.get("gt_latest_value"),
            "a_response_full": resp_a["response"],
            "a_tokens_input": resp_a["tokens_input"],
            "a_tokens_output": resp_a["tokens_output"],
            "a_cost_usd": resp_a["cost_usd"],
            "a_latency_ms": resp_a["latency_ms"],
            "a_refused": resp_a["refused"],
            "a_extracted_value": resp_a["value"],
            "a_extracted_year": resp_a["year"],
            "b_response_full": resp_b["response"],
            "b_tokens_input": resp_b["tokens_input"],
            "b_tokens_output": resp_b["tokens_output"],
            "b_cost_usd": resp_b["cost_usd"],
            "b_latency_ms": resp_b["latency_ms"],
            "b_refused": resp_b["refused"],
            "b_tool_error": resp_b.get("tool_error"),
            "b_tool_calls_json": json.dumps(resp_b.get("tool_calls", []), default=str),
            "b_n_tool_calls": len(resp_b.get("tool_calls", [])),
            "b_extracted_value": resp_b["value"],
            "b_extracted_year": resp_b["year"],
            "er_a": er_a, "ya_a": 1.0, "va_a": va_a, "eqa_a": eqa_a,
            "er_b": er_b, "ya_b": 1.0, "va_b": va_b, "eqa_b": eqa_b,
            "hall_a": False,
            "hall_b": False,
        })

        if gt_val:
            v_a = f"{resp_a['value']:.1f}" if resp_a["value"] else "???"
            v_b = f"{resp_b['value']:.1f}" if resp_b["value"] else "???"
            n_tools = len(resp_b.get("tool_calls", []))
            print(f"  GT={gt_val:7.1f}  A={v_a:>7s}(EQA={eqa_a:.3f})  B={v_b:>7s}(EQA={eqa_b:.3f}) [{n_tools} tools]")
        else:
            print("  no GT")

    # Build supplement DataFrame
    supplement = pd.DataFrame(new_rows)

    # Save supplement separately
    supp_parquet = os.path.join(results_dir, f"eqa_{run_id}.parquet")
    supplement.to_parquet(supp_parquet, index=False, engine="pyarrow")

    # Merge with existing
    combined = pd.concat([existing, supplement], ignore_index=True)
    combined_path = os.path.join(results_dir, f"eqa_combined_{model_slug}_{ts}.parquet")
    combined.to_parquet(combined_path, index=False, engine="pyarrow")
    combined.to_csv(combined_path.replace(".parquet", ".csv"), index=False)

    # Summary
    print(f"\n{'='*90}")
    print("SUMMARY")
    print(f"{'='*90}")
    print(f"  New direct queries: {len(supplement)}")
    print(f"  Combined total: {len(combined)}")

    pos_latest = combined[(combined.query_type == "POSITIVE") & (combined.prompt_type == "baseline_latest")]
    pos_direct = combined[(combined.query_type == "POSITIVE") & (combined.prompt_type == "direct")]

    if len(pos_latest) > 0:
        print(f"\n  POSITIVE (baseline_latest, n={len(pos_latest)}):")
        print(f"    EQA = ER × YA × VA")
        print(f"    Mean EQA  (A): {pos_latest.eqa_a.mean():.3f}   (B): {pos_latest.eqa_b.mean():.3f}")
        print(f"    Mean YA   (A): {pos_latest.ya_a.mean():.3f}   (B): {pos_latest.ya_b.mean():.3f}")

    if len(pos_direct) > 0:
        print(f"\n  POSITIVE (direct, n={len(pos_direct)}):")
        print(f"    EQA = ER × VA (YA=1.0)")
        print(f"    Mean EQA  (A): {pos_direct.eqa_a.mean():.3f}   (B): {pos_direct.eqa_b.mean():.3f}")
        print(f"    Mean VA   (A): {pos_direct.va_a.mean():.3f}   (B): {pos_direct.va_b.mean():.3f}")

    if len(pos_latest) > 0 and len(pos_direct) > 0:
        print(f"\n  YA penalty (baseline_latest only):")
        print(f"    A: EQA_latest={pos_latest.eqa_a.mean():.3f} vs EQA_direct={pos_direct.eqa_a.mean():.3f}  delta={pos_latest.eqa_a.mean()-pos_direct.eqa_a.mean():+.3f}")
        print(f"    B: EQA_latest={pos_latest.eqa_b.mean():.3f} vs EQA_direct={pos_direct.eqa_b.mean():.3f}  delta={pos_latest.eqa_b.mean()-pos_direct.eqa_b.mean():+.3f}")

    cost_a = supplement.a_cost_usd.sum()
    cost_b = supplement.b_cost_usd.sum()
    print(f"\n  Supplement cost: A=${cost_a:.2f}  B=${cost_b:.2f}  Total=${cost_a+cost_b:.2f}")

    print(f"\n  Saved:")
    print(f"    Supplement: {supp_parquet}")
    print(f"    Combined:   {combined_path}")


if __name__ == "__main__":
    main()
