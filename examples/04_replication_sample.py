"""Build a second independent sample for replication.

Same 10 indicators, same 300-query structure (100 latest + 100 direct + 50 T1 + 50 T2),
but DIFFERENT countries. Uses a new seed for reproducibility.

Reuses the design from 00_build_ground_truth.py but with:
  - 20 different developing/middle-income countries for positive queries
  - 5 different micro-states/HICs for T2 hallucination fallback
  - New seed (20260326)

Outputs to examples/ground_truth_r2/ (separate from the original sample).

Usage:
    python examples/04_replication_sample.py
    python examples/benchmark_eqa.py --ground-truth examples/ground_truth_r2/sample.csv --tag r2
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
logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Same indicators as original
# ---------------------------------------------------------------------------

INDICATORS = [
    {"code": "CME_MRY0T4", "name": "Under-five mortality rate", "unit": "per 1,000 live births", "domain": "CME", "data_type": "annual_modeled"},
    {"code": "CME_MRM0",   "name": "Neonatal mortality rate",   "unit": "per 1,000 live births", "domain": "CME", "data_type": "annual_modeled"},
    {"code": "CME_MRY0",   "name": "Infant mortality rate",     "unit": "per 1,000 live births", "domain": "CME", "data_type": "annual_modeled"},
    {"code": "CME_MRY1T4", "name": "Child mortality rate (1-4)", "unit": "per 1,000 children aged 1", "domain": "CME", "data_type": "annual_modeled"},
    {"code": "NT_ANT_HAZ_NE2", "name": "Stunting prevalence",   "unit": "percentage", "domain": "NUTRITION", "data_type": "survey_based"},
    {"code": "NT_ANT_WAZ_NE2", "name": "Underweight prevalence", "unit": "percentage", "domain": "NUTRITION", "data_type": "survey_based"},
    {"code": "NT_ANT_WHZ_NE2", "name": "Wasting prevalence",    "unit": "percentage", "domain": "NUTRITION", "data_type": "survey_based"},
    {"code": "MNCH_CSEC",  "name": "C-section delivery rate",   "unit": "percentage", "domain": "MNCH", "data_type": "survey_based"},
    {"code": "MNCH_BIRTH18", "name": "Births to women under 18", "unit": "percentage", "domain": "MNCH", "data_type": "survey_based"},
    {"code": "ED_CR_L1",   "name": "Education completion rate (primary)", "unit": "percentage", "domain": "EDUCATION", "data_type": "admin_survey"},
]

# ---------------------------------------------------------------------------
# DIFFERENT countries — no overlap with original sample
# ---------------------------------------------------------------------------
# Original: NGA, ETH, COD, MLI, NER, IND, BGD, KEN, PAK, BRA, MEX, TUR, CHN, THA, JPN, USA, GBR, FRA, DEU, AUS
# Replication: different countries, same income/region stratification

COUNTRIES = [
    # LIC (5) — different from NGA, ETH, COD, MLI, NER
    {"iso3": "TCD", "name": "Chad",            "region": "WCA", "income": "LIC"},
    {"iso3": "MOZ", "name": "Mozambique",      "region": "ESA", "income": "LIC"},
    {"iso3": "BFA", "name": "Burkina Faso",    "region": "WCA", "income": "LIC"},
    {"iso3": "AFG", "name": "Afghanistan",     "region": "SAR", "income": "LIC"},
    {"iso3": "MDG", "name": "Madagascar",      "region": "ESA", "income": "LIC"},
    # LMC (4) — different from IND, BGD, KEN, PAK
    {"iso3": "GHA", "name": "Ghana",           "region": "WCA", "income": "LMC"},
    {"iso3": "VNM", "name": "Viet Nam",        "region": "EAP", "income": "LMC"},
    {"iso3": "EGY", "name": "Egypt",           "region": "MNA", "income": "LMC"},
    {"iso3": "PHL", "name": "Philippines",     "region": "EAP", "income": "LMC"},
    # UMC (5) — different from BRA, MEX, TUR, CHN, THA
    {"iso3": "PER", "name": "Peru",            "region": "LAC", "income": "UMC"},
    {"iso3": "COL", "name": "Colombia",        "region": "LAC", "income": "UMC"},
    {"iso3": "ZAF", "name": "South Africa",    "region": "ESA", "income": "UMC"},
    {"iso3": "IDN", "name": "Indonesia",       "region": "EAP", "income": "UMC"},
    {"iso3": "IRQ", "name": "Iraq",            "region": "MNA", "income": "UMC"},
    # HIC (6) — different from JPN, USA, GBR, FRA, DEU, AUS
    {"iso3": "KOR", "name": "Republic of Korea", "region": "EAP", "income": "HIC"},
    {"iso3": "CAN", "name": "Canada",          "region": "NAM", "income": "HIC"},
    {"iso3": "ITA", "name": "Italy",           "region": "ECA", "income": "HIC"},
    {"iso3": "ESP", "name": "Spain",           "region": "ECA", "income": "HIC"},
    {"iso3": "NOR", "name": "Norway",          "region": "ECA", "income": "HIC"},
    {"iso3": "NZL", "name": "New Zealand",     "region": "EAP", "income": "HIC"},
]

# Different micro-states for T2 fallback (original: MCO, SMR, LIE, AND, PLW)
T2_FALLBACK_COUNTRIES = [
    {"iso3": "MHL", "name": "Marshall Islands"},
    {"iso3": "NRU", "name": "Nauru"},
    {"iso3": "TUV", "name": "Tuvalu"},
    {"iso3": "KNA", "name": "Saint Kitts and Nevis"},
    {"iso3": "DMA", "name": "Dominica"},
]

YEAR_START = 2000
YEAR_END = 2024
SEED = 20260326  # different from original (20260322)

N_POSITIVE_LATEST_PER_INDICATOR = 10
N_POSITIVE_DIRECT_PER_INDICATOR = 10
N_T1_PER_INDICATOR = 5
N_T2_PER_INDICATOR = 5
CME_FUTURE_YEARS = [2025, 2026, 2027, 2028, 2029]

OUTPUT_DIR = "examples/ground_truth_r2"


# ---------------------------------------------------------------------------
# Import the pipeline functions from the original script
# ---------------------------------------------------------------------------

# Add examples/ to path so we can import from 00_build_ground_truth
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# We reuse the functions but with our own config. Import the module and
# monkey-patch the config, or just duplicate the core logic inline.
# For clarity and independence, we duplicate the core functions here.

def fetch_all_data() -> pd.DataFrame:
    """Fetch all data for 10 indicators × 20 NEW countries."""
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
                simplify=False,
            )
            if not df.empty:
                df["indicator_code"] = code
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
        print("FATAL: No data fetched.")
        sys.exit(1)

    return pd.concat(all_frames, ignore_index=True)


def classify_queries(gt_df: pd.DataFrame) -> pd.DataFrame:
    """Classify all (indicator, country, year) tuples."""
    if "country_code" not in gt_df.columns:
        gt_df = gt_df.rename(columns={"iso3": "country_code"})

    existing_pairs = set(zip(gt_df["indicator_code"], gt_df["country_code"]))
    gt_df["year"] = gt_df["period"].astype(float).astype(int)
    existing_tuples = set(zip(gt_df["indicator_code"], gt_df["country_code"], gt_df["year"]))

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

                gt_value = None
                if tuple_exists:
                    mask = ((gt_df["indicator_code"] == code) & (gt_df["country_code"] == iso3) & (gt_df["year"] == year))
                    vals = gt_df.loc[mask, "value"]
                    if not vals.empty:
                        gt_value = float(vals.iloc[0])

                rows.append({
                    "indicator_code": code, "indicator_name": ind["name"],
                    "unit": ind["unit"], "domain": ind["domain"], "data_type": ind["data_type"],
                    "country_code": iso3, "country_name": cty["name"],
                    "region": cty["region"], "income": cty["income"],
                    "year": year, "query_type": query_type, "ground_truth_value": gt_value,
                })

    return pd.DataFrame(rows)


def sample_queries(universe: pd.DataFrame) -> pd.DataFrame:
    """Draw balanced stratified sample — same design as original."""
    import numpy as np
    rng = np.random.RandomState(SEED)

    positive = universe[universe["query_type"] == "POSITIVE"]
    hall_t1 = universe[universe["query_type"] == "HALLUCINATION_T1"]
    hall_t2 = universe[universe["query_type"] == "HALLUCINATION_T2"]

    print(f"\n  Universe: POSITIVE={len(positive)}, T1={len(hall_t1)}, T2={len(hall_t2)}")

    samples = []
    for ind in INDICATORS:
        code = ind["code"]
        name, unit, domain, data_type = ind["name"], ind["unit"], ind["domain"], ind["data_type"]

        pool = positive[positive["indicator_code"] == code]

        # POSITIVE latest (10)
        if len(pool) >= N_POSITIVE_LATEST_PER_INDICATOR:
            recent = pool.sort_values("year", ascending=False).head(30)
            s = recent.sample(n=min(N_POSITIVE_LATEST_PER_INDICATOR, len(recent)), random_state=rng).copy()
            s["prompt_type"] = "baseline_latest"
            samples.append(s)
        elif len(pool) > 0:
            s = pool.head(N_POSITIVE_LATEST_PER_INDICATOR).copy()
            s["prompt_type"] = "baseline_latest"
            samples.append(s)

        # POSITIVE direct (10)
        if len(pool) >= N_POSITIVE_DIRECT_PER_INDICATOR:
            already = samples[-1].index if samples else pd.Index([])
            remaining = pool.drop(already, errors="ignore")
            if len(remaining) < N_POSITIVE_DIRECT_PER_INDICATOR:
                remaining = pool
            recent2 = remaining.sort_values("year", ascending=False).head(30)
            s = recent2.sample(n=min(N_POSITIVE_DIRECT_PER_INDICATOR, len(recent2)), random_state=rng).copy()
            s["prompt_type"] = "direct"
            samples.append(s)
        elif len(pool) > 0:
            s = pool.tail(N_POSITIVE_DIRECT_PER_INDICATOR).copy()
            s["prompt_type"] = "direct"
            samples.append(s)

        # T1 (5) — mix intermediate gaps + future years
        pool_t1 = hall_t1[hall_t1["indicator_code"] == code]
        intermediate_gaps = []
        if len(pool_t1) > 0:
            for cty_code, cty_group in pool_t1.groupby("country_code"):
                pos_years = positive[(positive["indicator_code"] == code) & (positive["country_code"] == cty_code)]["year"]
                if len(pos_years) >= 2:
                    gaps = cty_group[(cty_group["year"] > pos_years.min()) & (cty_group["year"] < pos_years.max())]
                    if len(gaps) > 0:
                        intermediate_gaps.append(gaps)

        if intermediate_gaps:
            inter_df = pd.concat(intermediate_gaps)
            inter_recent = inter_df[inter_df["year"] >= 2010]
            pool_inter = inter_recent if len(inter_recent) >= 3 else inter_df
        else:
            pool_inter = pd.DataFrame()

        n_inter = min(3, len(pool_inter))
        n_future = N_T1_PER_INDICATOR - n_inter

        if n_inter > 0:
            samples.append(pool_inter.sample(n=n_inter, random_state=rng))
        if n_future > 0:
            t1_countries = rng.choice([c["iso3"] for c in COUNTRIES], size=n_future, replace=False)
            for j, iso3 in enumerate(t1_countries):
                cty = next(c for c in COUNTRIES if c["iso3"] == iso3)
                samples.append(pd.DataFrame([{
                    "indicator_code": code, "indicator_name": name, "unit": unit,
                    "domain": domain, "data_type": data_type,
                    "country_code": iso3, "country_name": cty["name"],
                    "region": cty["region"], "income": cty["income"],
                    "year": CME_FUTURE_YEARS[j % len(CME_FUTURE_YEARS)],
                    "query_type": "HALLUCINATION_T1", "ground_truth_value": None,
                }]))

        # T2 (5)
        pool_t2 = hall_t2[hall_t2["indicator_code"] == code].drop_duplicates(subset=["indicator_code", "country_code"])
        if len(pool_t2) >= N_T2_PER_INDICATOR:
            samples.append(pool_t2.sample(n=N_T2_PER_INDICATOR, random_state=rng))
        elif len(pool_t2) > 0:
            samples.append(pool_t2.head(N_T2_PER_INDICATOR))
            for fb in T2_FALLBACK_COUNTRIES[:N_T2_PER_INDICATOR - len(pool_t2)]:
                samples.append(pd.DataFrame([{
                    "indicator_code": code, "indicator_name": name, "unit": unit,
                    "domain": domain, "data_type": data_type,
                    "country_code": fb["iso3"], "country_name": fb["name"],
                    "region": "OTHER", "income": "HIC",
                    "year": 2023, "query_type": "HALLUCINATION_T2", "ground_truth_value": None,
                }]))
        else:
            for fb in T2_FALLBACK_COUNTRIES[:N_T2_PER_INDICATOR]:
                samples.append(pd.DataFrame([{
                    "indicator_code": code, "indicator_name": name, "unit": unit,
                    "domain": domain, "data_type": data_type,
                    "country_code": fb["iso3"], "country_name": fb["name"],
                    "region": "OTHER", "income": "HIC",
                    "year": 2023, "query_type": "HALLUCINATION_T2", "ground_truth_value": None,
                }]))

    sample = pd.concat(samples, ignore_index=True)

    # Assign prompt types for hallucination
    sample.loc[(sample["query_type"] == "HALLUCINATION_T1") & (sample["prompt_type"].isna()), "prompt_type"] = "direct"
    sample.loc[(sample["query_type"] == "HALLUCINATION_T2") & (sample["prompt_type"].isna()), "prompt_type"] = "baseline_latest"
    sample["prompt_type"] = sample["prompt_type"].fillna("baseline_latest")

    # Build prompt text
    def build_prompt(row):
        if row["prompt_type"] == "baseline_latest":
            return f"What is the latest available {row['indicator_name']} for {row['country_name']}?"
        else:
            return f"What was {row['indicator_name']} for {row['country_name']} in {int(row['year'])}?"

    sample["prompt_text"] = sample.apply(build_prompt, axis=1)
    return sample.sort_values(["indicator_code", "query_type", "country_code", "year"]).reset_index(drop=True)


def add_latest_values(sample: pd.DataFrame, gt_df: pd.DataFrame) -> pd.DataFrame:
    """Add latest value/year for positive baseline_latest queries."""
    gt_df = gt_df.copy()
    if "year" not in gt_df.columns:
        gt_df["year"] = gt_df["period"].astype(float).astype(int)
    if "country_code" not in gt_df.columns and "iso3" in gt_df.columns:
        gt_df = gt_df.rename(columns={"iso3": "country_code"})

    latest_rows = []
    for _, row in sample.iterrows():
        if row["query_type"] == "POSITIVE" and row["prompt_type"] == "baseline_latest":
            mask = (gt_df["indicator_code"] == row["indicator_code"]) & (gt_df["country_code"] == row["country_code"])
            subset = gt_df.loc[mask].sort_values("year", ascending=False)
            if not subset.empty:
                latest = subset.iloc[0]
                latest_rows.append({"idx": row.name, "latest_year": int(latest["year"]), "latest_value": float(latest["value"])})

    if latest_rows:
        latest_df = pd.DataFrame(latest_rows).set_index("idx")
        sample.loc[latest_df.index, "ground_truth_latest_year"] = latest_df["latest_year"]
        sample.loc[latest_df.index, "ground_truth_latest_value"] = latest_df["latest_value"]

    return sample


def main():
    import unicefdata
    print("=" * 80)
    print("Replication Sample (R2) — Different Countries, Same Design")
    print("=" * 80)
    print(f"  Indicators:    {len(INDICATORS)} (same as original)")
    print(f"  Countries:     {len(COUNTRIES)} (NEW — zero overlap with original)")
    print(f"  Years:         {YEAR_START}-{YEAR_END}")
    print(f"  Seed:          {SEED} (original: 20260322)")
    print(f"  unicefdata:    {unicefdata.__version__}")
    print(f"  Output:        {OUTPUT_DIR}/")
    print()

    print("Fetching data...")
    gt_df = fetch_all_data()
    print(f"\n  Total observations: {len(gt_df):,d}")

    print("\nClassifying...")
    universe = classify_queries(gt_df)

    print("\nSampling...")
    sample = sample_queries(universe)
    sample = add_latest_values(sample, gt_df)

    print(f"\n  Sample composition:")
    for qt in ["POSITIVE", "HALLUCINATION_T1", "HALLUCINATION_T2"]:
        print(f"    {qt:<25s} {len(sample[sample['query_type'] == qt]):>4d}")
    print(f"    {'TOTAL':<25s} {len(sample):>4d}")

    print(f"\n  Countries: {sorted(sample['country_code'].unique())}")

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    gt_df.to_csv(f"{OUTPUT_DIR}/ground_truth_values.csv", index=False)
    universe.to_csv(f"{OUTPUT_DIR}/query_universe.csv", index=False)
    sample.to_csv(f"{OUTPUT_DIR}/sample.csv", index=False)

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "original_seed": 20260322,
        "replication": "R2",
        "indicators": [i["code"] for i in INDICATORS],
        "countries": [c["iso3"] for c in COUNTRIES],
        "original_countries": ["NGA","ETH","COD","MLI","NER","IND","BGD","KEN","PAK","BRA","MEX","TUR","CHN","THA","JPN","USA","GBR","FRA","DEU","AUS"],
        "t2_fallback_countries": [c["iso3"] for c in T2_FALLBACK_COUNTRIES],
        "year_range": [YEAR_START, YEAR_END],
        "sample_rows": len(sample),
        "sample_counts": sample["query_type"].value_counts().to_dict(),
        "unicefdata_version": unicefdata.__version__,
    }
    with open(f"{OUTPUT_DIR}/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n  Saved to {OUTPUT_DIR}/")
    print(f"\nNext: python examples/benchmark_eqa.py --ground-truth {OUTPUT_DIR}/sample.csv --tag r2")


if __name__ == "__main__":
    main()
