#!/usr/bin/env python3
"""Step 0: Build ground truth database from unicefdata.

Fetches ALL available data for 10 indicators × a broad country set,
then classifies every possible (indicator, country, year) tuple into:

  - POSITIVE:           data exists in the UNICEF Data Warehouse
  - HALLUCINATION_T1:   country-indicator pair exists, but specific year has no data (gap year)
  - HALLUCINATION_T2:   country-indicator pair has NEVER been reported

Outputs:
  examples/ground_truth/
    ground_truth_values.csv   — all actual observations
    query_universe.csv        — classified (indicator, country, year, query_type)
    sample.csv                — stratified sample for benchmarking
    metadata.json             — run metadata for reproducibility

Requirements:
    pip install unicefdata pandas

Usage:
    python examples/00_build_ground_truth.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from datetime import datetime, timezone

import pandas as pd

warnings.filterwarnings("ignore", category=DeprecationWarning)

# unicefdata is verbose — suppress INFO
logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INDICATORS = [
    {"code": "CME_MRY0T4", "name": "Under-five mortality rate", "unit": "per 1,000 live births", "domain": "CME", "data_type": "annual_modeled"},
    {"code": "CME_MRM0",   "name": "Neonatal mortality rate",   "unit": "per 1,000 live births", "domain": "CME", "data_type": "annual_modeled"},
    {"code": "CME_MRY0",   "name": "Infant mortality rate",     "unit": "per 1,000 live births", "domain": "CME", "data_type": "annual_modeled"},
    {"code": "CME_MRY1T4", "name": "Child mortality rate (aged 1-4 years)", "unit": "per 1,000 children aged 1", "domain": "CME", "data_type": "annual_modeled"},
    {"code": "NT_ANT_HAZ_NE2", "name": "Height-for-age <-2 SD (stunting)",   "unit": "percentage", "domain": "NUTRITION", "data_type": "survey_based"},
    {"code": "NT_ANT_WAZ_NE2", "name": "Weight-for-age <-2 SD (Underweight)", "unit": "percentage", "domain": "NUTRITION", "data_type": "survey_based"},
    {"code": "NT_ANT_WHZ_NE2", "name": "Weight-for-height <-2 SD (wasting)",    "unit": "percentage", "domain": "NUTRITION", "data_type": "survey_based"},
    {"code": "MNCH_CSEC",  "name": "C-section rate - percentage of deliveries by cesarean section",   "unit": "percentage", "domain": "MNCH", "data_type": "survey_based"},
    {"code": "MNCH_BIRTH18", "name": "Early childbearing - percentage of women (aged 20-24 years) who gave birth before age 18", "unit": "percentage", "domain": "MNCH", "data_type": "survey_based"},
    {"code": "ED_CR_L1",   "name": "Completion rate for children of primary school age", "unit": "percentage", "domain": "EDUCATION", "data_type": "admin_survey"},
]

# Countries: 20 diverse countries spanning all UNICEF regions and income groups
COUNTRIES = [
    {"iso3": "NGA", "name": "Nigeria",       "region": "WCA", "income": "LIC"},
    {"iso3": "ETH", "name": "Ethiopia",      "region": "ESA", "income": "LIC"},
    {"iso3": "COD", "name": "DR Congo",      "region": "WCA", "income": "LIC"},
    {"iso3": "MLI", "name": "Mali",          "region": "WCA", "income": "LIC"},
    {"iso3": "NER", "name": "Niger",         "region": "WCA", "income": "LIC"},
    {"iso3": "IND", "name": "India",         "region": "SAR", "income": "LMC"},
    {"iso3": "BGD", "name": "Bangladesh",    "region": "SAR", "income": "LMC"},
    {"iso3": "KEN", "name": "Kenya",         "region": "ESA", "income": "LMC"},
    {"iso3": "PAK", "name": "Pakistan",      "region": "SAR", "income": "LMC"},
    {"iso3": "BRA", "name": "Brazil",        "region": "LAC", "income": "UMC"},
    {"iso3": "MEX", "name": "Mexico",        "region": "LAC", "income": "UMC"},
    {"iso3": "TUR", "name": "Turkiye",       "region": "ECA", "income": "UMC"},
    {"iso3": "CHN", "name": "China",         "region": "EAP", "income": "UMC"},
    {"iso3": "THA", "name": "Thailand",      "region": "EAP", "income": "UMC"},
    {"iso3": "JPN", "name": "Japan",         "region": "EAP", "income": "HIC"},
    {"iso3": "USA", "name": "United States", "region": "NAM", "income": "HIC"},
    {"iso3": "GBR", "name": "United Kingdom","region": "ECA", "income": "HIC"},
    {"iso3": "FRA", "name": "France",        "region": "ECA", "income": "HIC"},
    {"iso3": "DEU", "name": "Germany",       "region": "ECA", "income": "HIC"},
    {"iso3": "AUS", "name": "Australia",     "region": "EAP", "income": "HIC"},
]

# Alternative country pool for replication (R2) — no overlap with R1
COUNTRIES_R2 = [
    {"iso3": "MOZ", "name": "Mozambique",   "region": "ESA", "income": "LIC"},
    {"iso3": "TCD", "name": "Chad",         "region": "WCA", "income": "LIC"},
    {"iso3": "BFA", "name": "Burkina Faso", "region": "WCA", "income": "LIC"},
    {"iso3": "AFG", "name": "Afghanistan",  "region": "SAR", "income": "LIC"},
    {"iso3": "MDG", "name": "Madagascar",   "region": "ESA", "income": "LIC"},
    {"iso3": "GHA", "name": "Ghana",        "region": "WCA", "income": "LMC"},
    {"iso3": "PHL", "name": "Philippines",  "region": "EAP", "income": "LMC"},
    {"iso3": "VNM", "name": "Viet Nam",     "region": "EAP", "income": "LMC"},
    {"iso3": "EGY", "name": "Egypt",        "region": "MNA", "income": "LMC"},
    {"iso3": "COL", "name": "Colombia",     "region": "LAC", "income": "UMC"},
    {"iso3": "PER", "name": "Peru",         "region": "LAC", "income": "UMC"},
    {"iso3": "IDN", "name": "Indonesia",    "region": "EAP", "income": "UMC"},
    {"iso3": "ZAF", "name": "South Africa", "region": "ESA", "income": "UMC"},
    {"iso3": "IRQ", "name": "Iraq",         "region": "MNA", "income": "UMC"},
    {"iso3": "KOR", "name": "South Korea",  "region": "EAP", "income": "HIC"},
    {"iso3": "ESP", "name": "Spain",        "region": "ECA", "income": "HIC"},
    {"iso3": "ITA", "name": "Italy",        "region": "ECA", "income": "HIC"},
    {"iso3": "CAN", "name": "Canada",       "region": "NAM", "income": "HIC"},
    {"iso3": "NOR", "name": "Norway",       "region": "ECA", "income": "HIC"},
    {"iso3": "NZL", "name": "New Zealand",  "region": "EAP", "income": "HIC"},
]

# Select country pool: R1 (default) or R2 via environment variable
_country_pool = os.environ.get("BENCHMARK_COUNTRIES", "R1")
if _country_pool.upper() == "R2":
    COUNTRIES = COUNTRIES_R2

# Year range for the benchmark
YEAR_START = 2000
YEAR_END = 2024

# Sampling parameters
SEED = int(os.environ.get("BENCHMARK_SEED", "20260322"))
# Balanced design: 30 queries per indicator = 300 total
# 10 positive_latest + 10 positive_direct + 5 T1 + 5 T2 per indicator
N_POSITIVE_LATEST_PER_INDICATOR = 10  # baseline_latest prompt, EQA = ER × YA × VA
N_POSITIVE_DIRECT_PER_INDICATOR = 10  # direct prompt (specific year), EQA = ER × VA
N_T1_PER_INDICATOR = 5
N_T2_PER_INDICATOR = 5

# Future years for CME T1 (IGME doesn't have 2025+ estimates yet)
CME_FUTURE_YEARS = [2025, 2026, 2027, 2028, 2029]

# Countries that should NOT have data for any indicator (for CME T2)
# These are very small states / territories not in IGME database
T2_FALLBACK_COUNTRIES = [
    {"iso3": "MCO", "name": "Monaco"},
    {"iso3": "SMR", "name": "San Marino"},
    {"iso3": "LIE", "name": "Liechtenstein"},
    {"iso3": "AND", "name": "Andorra"},
    {"iso3": "PLW", "name": "Palau"},
]

OUTPUT_DIR = os.environ.get("BENCHMARK_OUTPUT_DIR", "examples/ground_truth")


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def fetch_all_data() -> pd.DataFrame:
    """Fetch all available data for 10 indicators × 20 countries."""
    import unicefdata as ud

    all_frames = []
    n_indicators = len(INDICATORS)

    for i, ind in enumerate(INDICATORS, 1):
        code = ind["code"]
        print(f"  [{i:2d}/{n_indicators}] Fetching {code:<20s} ... ", end="", flush=True)

        try:
            df = ud.unicefData(
                indicator=code,
                countries=[c["iso3"] for c in COUNTRIES],
                year=f"{YEAR_START}:{YEAR_END}",
                sex="_T",
                totals=True,
                tidy=True,
                country_names=True,
                simplify=False,  # keep all columns for proper classification
            )
            if not df.empty:
                df["indicator_code"] = code
                # Normalize column names
                if "iso3" in df.columns:
                    df = df.rename(columns={"iso3": "country_code", "country": "country_name"})
                if "indicator" in df.columns and "indicator_code" not in df.columns:
                    df = df.rename(columns={"indicator": "indicator_code"})
                all_frames.append(df)
                n_rows = len(df)
                n_countries = df["country_code"].nunique() if "country_code" in df.columns else 0
                print(f"{n_rows:>5d} obs, {n_countries:>3d} countries")
            else:
                print("no data")
        except Exception as exc:
            print(f"ERROR: {exc}")

    if not all_frames:
        print("FATAL: No data fetched for any indicator.")
        sys.exit(1)

    combined = pd.concat(all_frames, ignore_index=True)
    return combined


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_queries(gt_df: pd.DataFrame) -> pd.DataFrame:
    """Build the full query universe and classify each tuple.

    For every (indicator, country, year) in the cross product:
      - If data exists in gt_df → POSITIVE
      - If country-indicator pair exists but year is missing → HALLUCINATION_T1
      - If country-indicator pair never appears → HALLUCINATION_T2
    """
    # Find which (indicator, country) pairs have ANY data
    if "country_code" not in gt_df.columns:
        print("WARNING: country_code column missing, trying iso3")
        gt_df = gt_df.rename(columns={"iso3": "country_code"})

    existing_pairs = set(
        zip(gt_df["indicator_code"], gt_df["country_code"])
    )

    # Find which (indicator, country, year) tuples have data
    gt_df["year"] = gt_df["period"].astype(float).astype(int)
    existing_tuples = set(
        zip(gt_df["indicator_code"], gt_df["country_code"], gt_df["year"])
    )

    # Build the universe
    rows = []
    for ind in INDICATORS:
        code = ind["code"]
        for cty in COUNTRIES:
            iso3 = cty["iso3"]
            pair_exists = (code, iso3) in existing_pairs

            for year in range(YEAR_START, YEAR_END + 1):
                tuple_exists = (code, iso3, year) in existing_tuples

                if tuple_exists:
                    query_type = "POSITIVE"
                elif pair_exists:
                    query_type = "HALLUCINATION_T1"
                else:
                    query_type = "HALLUCINATION_T2"

                # Get ground truth value if it exists
                gt_value = None
                if tuple_exists:
                    mask = (
                        (gt_df["indicator_code"] == code)
                        & (gt_df["country_code"] == iso3)
                        & (gt_df["year"] == year)
                    )
                    vals = gt_df.loc[mask, "value"]
                    if not vals.empty:
                        gt_value = float(vals.iloc[0])

                rows.append({
                    "indicator_code": code,
                    "indicator_name": ind["name"],
                    "unit": ind["unit"],
                    "domain": ind["domain"],
                    "data_type": ind["data_type"],
                    "country_code": iso3,
                    "country_name": cty["name"],
                    "region": cty["region"],
                    "income": cty["income"],
                    "year": year,
                    "query_type": query_type,
                    "ground_truth_value": gt_value,
                })

    universe = pd.DataFrame(rows)
    return universe


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def sample_queries(universe: pd.DataFrame) -> pd.DataFrame:
    """Draw balanced stratified sample: equal queries per indicator.

    Target per indicator:
      10 POSITIVE (baseline_latest) — EQA = ER × YA × VA
      10 POSITIVE (direct, specific year) — EQA = ER × VA
       5 HALLUCINATION_T1 (gap years, direct prompt) — refusal rate
       5 HALLUCINATION_T2 (never existed, baseline_latest) — refusal rate
      = 30 per indicator × 10 indicators = 300 total

    For indicators with no natural T1/T2 cases (CME annual modeled),
    we construct synthetic cases:
      T1: mix of intermediate gaps + future years (2025-2029)
      T2: micro-states (MCO, SMR, LIE, AND, PLW)
    """
    import numpy as np
    rng = np.random.RandomState(SEED)

    positive = universe[universe["query_type"] == "POSITIVE"]
    hall_t1 = universe[universe["query_type"] == "HALLUCINATION_T1"]
    hall_t2 = universe[universe["query_type"] == "HALLUCINATION_T2"]

    print(f"\n  Universe counts:")
    print(f"    POSITIVE:          {len(positive):>7,d}")
    print(f"    HALLUCINATION_T1:  {len(hall_t1):>7,d}")
    print(f"    HALLUCINATION_T2:  {len(hall_t2):>7,d}")
    print(f"    Total:             {len(universe):>7,d}")

    samples = []

    for ind in INDICATORS:
        code = ind["code"]
        name = ind["name"]
        unit = ind["unit"]
        domain = ind["domain"]
        data_type = ind["data_type"]

        # --- POSITIVE (baseline_latest): 10 per indicator ---
        pool = positive[positive["indicator_code"] == code]
        if len(pool) >= N_POSITIVE_LATEST_PER_INDICATOR:
            pool_recent = pool.sort_values("year", ascending=False)
            sampled = pool_recent.head(30).sample(
                n=min(N_POSITIVE_LATEST_PER_INDICATOR, len(pool_recent.head(30))),
                random_state=rng,
            )
            # Mark as baseline_latest
            sampled = sampled.copy()
            sampled["prompt_type"] = "baseline_latest"
            samples.append(sampled)
        elif len(pool) > 0:
            chunk = pool.head(N_POSITIVE_LATEST_PER_INDICATOR).copy()
            chunk["prompt_type"] = "baseline_latest"
            samples.append(chunk)

        # --- POSITIVE (direct): 10 per indicator ---
        # Sample different rows than baseline_latest for diversity
        if len(pool) >= N_POSITIVE_DIRECT_PER_INDICATOR:
            # Exclude rows already sampled for baseline_latest
            already = samples[-1].index if samples else pd.Index([])
            pool_remaining = pool.drop(already, errors="ignore")
            if len(pool_remaining) < N_POSITIVE_DIRECT_PER_INDICATOR:
                pool_remaining = pool  # fallback: allow overlap
            pool_recent2 = pool_remaining.sort_values("year", ascending=False)
            sampled = pool_recent2.head(30).sample(
                n=min(N_POSITIVE_DIRECT_PER_INDICATOR, len(pool_recent2.head(30))),
                random_state=rng,
            )
            sampled = sampled.copy()
            sampled["prompt_type"] = "direct"
            samples.append(sampled)
        elif len(pool) > 0:
            chunk = pool.tail(N_POSITIVE_DIRECT_PER_INDICATOR).copy()
            chunk["prompt_type"] = "direct"
            samples.append(chunk)

        # --- T1 (gap years): 5 per indicator ---
        # Mix of intermediate gap years (real gaps between surveys) and future years.
        # Survey-based: prefer intermediate gaps; CME: must use future years.
        pool_t1 = hall_t1[hall_t1["indicator_code"] == code]

        # Prefer intermediate gaps (years between actual data points)
        intermediate_gaps = []
        if len(pool_t1) > 0:
            # Find true intermediate gaps: year is between min and max year for that country
            for cty_code, cty_group in pool_t1.groupby("country_code"):
                pos_years = positive[
                    (positive["indicator_code"] == code) &
                    (positive["country_code"] == cty_code)
                ]["year"]
                if len(pos_years) >= 2:
                    min_yr, max_yr = pos_years.min(), pos_years.max()
                    gaps = cty_group[(cty_group["year"] > min_yr) & (cty_group["year"] < max_yr)]
                    if len(gaps) > 0:
                        intermediate_gaps.append(gaps)

        if intermediate_gaps:
            inter_df = pd.concat(intermediate_gaps)
            # Prefer recent intermediate gaps
            inter_recent = inter_df[inter_df["year"] >= 2010]
            pool_inter = inter_recent if len(inter_recent) >= 3 else inter_df
        else:
            pool_inter = pd.DataFrame()

        n_inter = min(3, len(pool_inter))  # up to 3 intermediate gaps
        n_future = N_T1_PER_INDICATOR - n_inter  # rest from future years

        # Sample intermediate gaps
        if n_inter > 0:
            sampled_inter = pool_inter.sample(n=n_inter, random_state=rng)
            samples.append(sampled_inter)

        # Fill remaining with future years (or all 5 if no intermediate gaps)
        if n_future > 0:
            t1_countries = rng.choice(
                [c["iso3"] for c in COUNTRIES], size=n_future, replace=False
            )
            for i, iso3 in enumerate(t1_countries):
                cty = next(c for c in COUNTRIES if c["iso3"] == iso3)
                future_year = CME_FUTURE_YEARS[i % len(CME_FUTURE_YEARS)]
                samples.append(pd.DataFrame([{
                    "indicator_code": code, "indicator_name": name,
                    "unit": unit, "domain": domain, "data_type": data_type,
                    "country_code": iso3, "country_name": cty["name"],
                    "region": cty["region"], "income": cty["income"],
                    "year": future_year, "query_type": "HALLUCINATION_T1",
                    "ground_truth_value": None,
                }]))

        # --- T2 (never existed): 5 per indicator ---
        pool_t2 = hall_t2[hall_t2["indicator_code"] == code]
        # Deduplicate to one row per country-indicator pair
        pool_t2_unique = pool_t2.drop_duplicates(subset=["indicator_code", "country_code"])
        if len(pool_t2_unique) >= N_T2_PER_INDICATOR:
            sampled = pool_t2_unique.sample(n=N_T2_PER_INDICATOR, random_state=rng)
            samples.append(sampled)
        elif len(pool_t2_unique) > 0:
            samples.append(pool_t2_unique.head(N_T2_PER_INDICATOR))
            # Fill remaining with micro-states
            remaining = N_T2_PER_INDICATOR - len(pool_t2_unique)
            for fb in T2_FALLBACK_COUNTRIES[:remaining]:
                samples.append(pd.DataFrame([{
                    "indicator_code": code, "indicator_name": name,
                    "unit": unit, "domain": domain, "data_type": data_type,
                    "country_code": fb["iso3"], "country_name": fb["name"],
                    "region": "OTHER", "income": "HIC",
                    "year": 2023, "query_type": "HALLUCINATION_T2",
                    "ground_truth_value": None,
                }]))
        else:
            # No natural T2 at all — use micro-states
            for fb in T2_FALLBACK_COUNTRIES[:N_T2_PER_INDICATOR]:
                samples.append(pd.DataFrame([{
                    "indicator_code": code, "indicator_name": name,
                    "unit": unit, "domain": domain, "data_type": data_type,
                    "country_code": fb["iso3"], "country_name": fb["name"],
                    "region": "OTHER", "income": "HIC",
                    "year": 2023, "query_type": "HALLUCINATION_T2",
                    "ground_truth_value": None,
                }]))

    sample = pd.concat(samples, ignore_index=True)

    # --- Assign prompt types for hallucination queries ---
    # Positive queries already have prompt_type set during sampling above.
    # T1 (gap years) → direct (tests specific year hallucination)
    # T2 (never existed) → baseline_latest (tests fabrication of non-existent data)
    sample.loc[
        (sample["query_type"] == "HALLUCINATION_T1") & (sample["prompt_type"].isna()),
        "prompt_type",
    ] = "direct"
    sample.loc[
        (sample["query_type"] == "HALLUCINATION_T2") & (sample["prompt_type"].isna()),
        "prompt_type",
    ] = "baseline_latest"
    # Fill any remaining NaN prompt_type (shouldn't happen, but safety)
    sample["prompt_type"] = sample["prompt_type"].fillna("baseline_latest")

    # --- Build prompt text ---
    def build_prompt(row):
        if row["prompt_type"] == "baseline_latest":
            return f"What is the latest available {row['indicator_name']} for {row['country_name']}?"
        else:
            return f"What was {row['indicator_name']} for {row['country_name']} in {int(row['year'])}?"

    sample["prompt_text"] = sample.apply(build_prompt, axis=1)

    return sample.sort_values(
        ["indicator_code", "query_type", "country_code", "year"]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Latest value lookup (for positive baseline_latest queries)
# ---------------------------------------------------------------------------


def add_latest_values(sample: pd.DataFrame, gt_df: pd.DataFrame) -> pd.DataFrame:
    """For POSITIVE baseline_latest queries, find the actual latest value and year."""
    gt_df = gt_df.copy()
    if "year" not in gt_df.columns:
        gt_df["year"] = gt_df["period"].astype(float).astype(int)
    if "country_code" not in gt_df.columns and "iso3" in gt_df.columns:
        gt_df = gt_df.rename(columns={"iso3": "country_code"})

    latest_rows = []
    for _, row in sample.iterrows():
        if row["query_type"] == "POSITIVE" and row["prompt_type"] == "baseline_latest":
            mask = (
                (gt_df["indicator_code"] == row["indicator_code"])
                & (gt_df["country_code"] == row["country_code"])
            )
            subset = gt_df.loc[mask].sort_values("year", ascending=False)
            if not subset.empty:
                latest = subset.iloc[0]
                latest_rows.append({
                    "idx": row.name,
                    "latest_year": int(latest["year"]),
                    "latest_value": float(latest["value"]),
                })

    if latest_rows:
        latest_df = pd.DataFrame(latest_rows).set_index("idx")
        sample.loc[latest_df.index, "ground_truth_latest_year"] = latest_df["latest_year"]
        sample.loc[latest_df.index, "ground_truth_latest_value"] = latest_df["latest_value"]

    return sample


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("=" * 80)
    print("Step 0: Build Ground Truth Database")
    print("=" * 80)
    print(f"  Indicators: {len(INDICATORS)}")
    print(f"  Countries:  {len(COUNTRIES)}")
    print(f"  Years:      {YEAR_START}-{YEAR_END}")
    print(f"  Seed:       {SEED}")
    print()

    # --- Fetch ---
    print("Fetching data from UNICEF SDMX API via unicefdata...")
    gt_df = fetch_all_data()
    print(f"\n  Total observations: {len(gt_df):,d}")
    print(f"  Indicators with data: {gt_df['indicator_code'].nunique()}")
    if "country_code" in gt_df.columns:
        print(f"  Countries with data: {gt_df['country_code'].nunique()}")
    elif "iso3" in gt_df.columns:
        print(f"  Countries with data: {gt_df['iso3'].nunique()}")

    # --- Classify ---
    print("\nClassifying query universe...")
    universe = classify_queries(gt_df)

    # --- Sample ---
    print("\nSampling benchmark queries...")
    sample = sample_queries(universe)
    sample = add_latest_values(sample, gt_df)

    # --- Print summary ---
    print(f"\n  Sample composition:")
    for qt in ["POSITIVE", "HALLUCINATION_T1", "HALLUCINATION_T2"]:
        n = len(sample[sample["query_type"] == qt])
        print(f"    {qt:<25s} {n:>4d}")
    print(f"    {'TOTAL':<25s} {len(sample):>4d}")

    print(f"\n  By indicator:")
    for code in sorted(sample["indicator_code"].unique()):
        n = len(sample[sample["indicator_code"] == code])
        types = sample[sample["indicator_code"] == code]["query_type"].value_counts().to_dict()
        print(f"    {code:<20s} {n:>3d}  ({types})")

    print(f"\n  By country:")
    for iso3 in sorted(sample["country_code"].unique()):
        n = len(sample[sample["country_code"] == iso3])
        print(f"    {iso3:<6s} {n:>3d}")

    # --- Save ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    gt_path = f"{OUTPUT_DIR}/ground_truth_values.csv"
    gt_df.to_csv(gt_path, index=False)
    print(f"\n  Saved: {gt_path} ({len(gt_df):,d} rows)")

    universe_path = f"{OUTPUT_DIR}/query_universe.csv"
    universe.to_csv(universe_path, index=False)
    print(f"  Saved: {universe_path} ({len(universe):,d} rows)")

    sample_path = f"{OUTPUT_DIR}/sample.csv"
    sample.to_csv(sample_path, index=False)
    print(f"  Saved: {sample_path} ({len(sample)} rows)")

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "indicators": [i["code"] for i in INDICATORS],
        "countries": [c["iso3"] for c in COUNTRIES],
        "year_range": [YEAR_START, YEAR_END],
        "n_positive_latest_per_indicator": N_POSITIVE_LATEST_PER_INDICATOR,
        "n_positive_direct_per_indicator": N_POSITIVE_DIRECT_PER_INDICATOR,
        "n_t1_per_indicator": N_T1_PER_INDICATOR,
        "n_t2_per_indicator": N_T2_PER_INDICATOR,
        "ground_truth_rows": len(gt_df),
        "universe_rows": len(universe),
        "sample_rows": len(sample),
        "universe_counts": universe["query_type"].value_counts().to_dict(),
        "sample_counts": sample["query_type"].value_counts().to_dict(),
    }
    meta_path = f"{OUTPUT_DIR}/metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Saved: {meta_path}")

    print(f"\nDone. Next step: python examples/benchmark_eqa.py")


if __name__ == "__main__":
    main()
