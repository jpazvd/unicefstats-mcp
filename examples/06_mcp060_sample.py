"""Build a fourth independent sample for the v0.6.0 server-side hardening pilot.

Same 10 indicators as R1/R2/mcp051, n=500, with a FOURTH-set of countries fully
disjoint from R1, R2, and mcp051. Purpose: empirically test whether v0.6.0's
server-side pre-flight (frontier check + structured no_data envelope + prompt
caching) reduces hallucination rate AND token cost vs the v0.5.1 skill-side
approach.

Sample composition (per design doc internal/v0_5_1_validation_design.md):
  - 100 POSITIVE       (5 latest + 5 direct per 10 indicators)
  - 200 HALLUCINATION_T1 (20 per indicator)
  - 200 HALLUCINATION_T2 (20 per indicator)

Seed independence: this run uses SEED=20260502.
  R1:     20260322 (00_build_ground_truth.py default)
  R2:     20260326 (04_replication_sample.py hardcoded)
  mcp051: 20260501 (05_mcp051_sample.py)
  mcp060: 20260502 (this file)

All four seeds and country pools are mutually disjoint, ensuring statistical
independence across rounds.

Usage:
    python examples/06_mcp060_sample.py
    python examples/benchmark_eqa.py \\
        --ground-truth examples/ground_truth_mcp060/sample.csv --tag mcp060

Output:
    examples/ground_truth_mcp060/
      ├─ sample.csv          (~500 queries to run)
      ├─ ground_truth_values.csv
      ├─ query_universe.csv
      └─ metadata.json
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
# Same 10 indicators as R1 + R2 + mcp051
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
# FOURTH-SET countries — zero overlap with R1, R2, or mcp051.
# Used so far across rounds:
#   R1:     NGA ETH COD MLI NER IND BGD KEN PAK BRA MEX TUR CHN THA JPN USA GBR FRA DEU AUS
#   R2:     TCD MOZ BFA AFG MDG GHA VNM EGY PHL PER COL ZAF IDN IRQ KOR CAN ITA ESP NOR NZL
#   mcp051: SDN SOM GIN RWA TGO NPL KHM LKA MMR UGA ECU DOM JAM TUN MYS SGP ARE CHE AUT SWE
# ---------------------------------------------------------------------------

COUNTRIES = [
    # LIC (5) — Sub-Saharan Africa, fresh
    {"iso3": "MWI", "name": "Malawi",            "region": "ESA", "income": "LIC"},
    {"iso3": "BDI", "name": "Burundi",           "region": "ESA", "income": "LIC"},
    {"iso3": "ERI", "name": "Eritrea",           "region": "ESA", "income": "LIC"},
    {"iso3": "LBR", "name": "Liberia",           "region": "WCA", "income": "LIC"},
    {"iso3": "SLE", "name": "Sierra Leone",      "region": "WCA", "income": "LIC"},
    # LMC (5) — fresh
    {"iso3": "SEN", "name": "Senegal",           "region": "WCA", "income": "LMC"},
    {"iso3": "CIV", "name": "Cote d'Ivoire",     "region": "WCA", "income": "LMC"},
    {"iso3": "TZA", "name": "Tanzania",          "region": "ESA", "income": "LMC"},
    {"iso3": "HND", "name": "Honduras",          "region": "LAC", "income": "LMC"},
    {"iso3": "BOL", "name": "Bolivia",           "region": "LAC", "income": "LMC"},
    # UMC (5) — fresh
    {"iso3": "JOR", "name": "Jordan",            "region": "MNA", "income": "UMC"},
    {"iso3": "CRI", "name": "Costa Rica",        "region": "LAC", "income": "UMC"},
    {"iso3": "NAM", "name": "Namibia",           "region": "ESA", "income": "UMC"},
    {"iso3": "GTM", "name": "Guatemala",         "region": "LAC", "income": "UMC"},
    {"iso3": "PRY", "name": "Paraguay",          "region": "LAC", "income": "UMC"},
    # HIC (5) — fresh
    {"iso3": "SAU", "name": "Saudi Arabia",      "region": "MNA", "income": "HIC"},
    {"iso3": "QAT", "name": "Qatar",             "region": "MNA", "income": "HIC"},
    {"iso3": "ISR", "name": "Israel",            "region": "MNA", "income": "HIC"},
    {"iso3": "BEL", "name": "Belgium",           "region": "ECA", "income": "HIC"},
    {"iso3": "NLD", "name": "Netherlands",       "region": "ECA", "income": "HIC"},
]

# ---------------------------------------------------------------------------
# FOURTH-SET T2 fallback — territories/microstates not in any prior fallback set.
# Used so far:
#   R1: MCO SMR LIE AND PLW
#   R2: MHL NRU TUV KNA DMA
#   mcp051: VAT COK NIU TKL ASM GUM MNP VIR PRI AIA BMU MSR TCA VGB FRO GRL ALA GIB SHN IMN JEY GGY SJM BES CUW
#
# Post-validation in fetch_t2_fallback_data() drops any (indicator, ctry) pair
# where data is actually present, so over-inclusion is harmless.
# ---------------------------------------------------------------------------

T2_FALLBACK_COUNTRIES = [
    # French overseas departments / collectivities
    {"iso3": "MTQ", "name": "Martinique"},
    {"iso3": "GLP", "name": "Guadeloupe"},
    {"iso3": "GUF", "name": "French Guiana"},
    {"iso3": "REU", "name": "Reunion"},
    {"iso3": "MYT", "name": "Mayotte"},
    {"iso3": "MAF", "name": "Saint Martin (French)"},
    {"iso3": "BLM", "name": "Saint Barthelemy"},
    {"iso3": "WLF", "name": "Wallis and Futuna"},
    {"iso3": "PYF", "name": "French Polynesia"},
    {"iso3": "NCL", "name": "New Caledonia"},
    {"iso3": "ATF", "name": "French Southern Territories"},
    # Dutch Caribbean
    {"iso3": "SXM", "name": "Sint Maarten"},
    # British Overseas Territories
    {"iso3": "CYM", "name": "Cayman Islands"},
    {"iso3": "FLK", "name": "Falkland Islands"},
    {"iso3": "IOT", "name": "British Indian Ocean Territory"},
    {"iso3": "PCN", "name": "Pitcairn"},
    {"iso3": "SGS", "name": "South Georgia"},
    # Australian dependencies
    {"iso3": "NFK", "name": "Norfolk Island"},
    {"iso3": "CXR", "name": "Christmas Island"},
    {"iso3": "CCK", "name": "Cocos Islands"},
    {"iso3": "HMD", "name": "Heard and McDonald Islands"},
    # Other small territories / disputed / uninhabited
    {"iso3": "BVT", "name": "Bouvet Island"},
    {"iso3": "ATA", "name": "Antarctica"},
    {"iso3": "UMI", "name": "United States Minor Outlying Islands"},
    {"iso3": "ESH", "name": "Western Sahara"},
]

YEAR_START = 2000
YEAR_END = 2024
SEED = 20260502  # different from R1 (20260322), R2 (20260326), mcp051 (20260501)

N_POSITIVE_LATEST_PER_INDICATOR = 5
N_POSITIVE_DIRECT_PER_INDICATOR = 5
N_T1_PER_INDICATOR = 20
N_T2_PER_INDICATOR = 20
CME_FUTURE_YEARS = [2025, 2026, 2027, 2028, 2029]

OUTPUT_DIR = "examples/ground_truth_mcp060"


# ---------------------------------------------------------------------------
# Pipeline functions (duplicated from 05_mcp051_sample.py for independence)
# ---------------------------------------------------------------------------


def fetch_all_data() -> pd.DataFrame:
    """Fetch all data for 10 indicators x 20 fourth-set countries."""
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


def fetch_t2_fallback_data() -> pd.DataFrame:
    """Probe T2_FALLBACK_COUNTRIES for actual data presence and return pairs to exclude."""
    import unicefdata as ud

    rows = []
    for ind in INDICATORS:
        code = ind["code"]
        try:
            df = ud.unicefData(
                indicator=code,
                countries=[c["iso3"] for c in T2_FALLBACK_COUNTRIES],
                year=f"{YEAR_START}:{YEAR_END}",
                sex="_T",
                totals=True,
                tidy=True,
                country_names=False,
                simplify=False,
            )
            if df is None or df.empty:
                continue
            if "iso3" in df.columns:
                country_col = "iso3"
            elif "country_code" in df.columns:
                country_col = "country_code"
            else:
                continue
            for ctry in df[country_col].unique():
                rows.append({"indicator_code": code, "country_code": ctry})
        except Exception:
            pass

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["indicator_code", "country_code"])


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


def sample_queries(universe: pd.DataFrame, t2_invalid: pd.DataFrame) -> pd.DataFrame:
    """Draw stratified sample with mcp060 seed."""
    import numpy as np
    rng = np.random.RandomState(SEED)

    invalid_pairs = set()
    if not t2_invalid.empty:
        invalid_pairs = set(zip(t2_invalid["indicator_code"], t2_invalid["country_code"]))

    valid_fallback = lambda code: [c for c in T2_FALLBACK_COUNTRIES if (code, c["iso3"]) not in invalid_pairs]

    positive = universe[universe["query_type"] == "POSITIVE"]
    hall_t1 = universe[universe["query_type"] == "HALLUCINATION_T1"]
    hall_t2 = universe[universe["query_type"] == "HALLUCINATION_T2"]

    print(f"\n  Universe: POSITIVE={len(positive)}, T1={len(hall_t1)}, T2={len(hall_t2)}")
    print(f"  T2 fallback validation: {len(invalid_pairs)} (indicator, country) pairs have data and will be excluded")

    samples = []
    for ind in INDICATORS:
        code = ind["code"]
        name, unit, domain, data_type = ind["name"], ind["unit"], ind["domain"], ind["data_type"]

        pool = positive[positive["indicator_code"] == code]

        # POSITIVE latest (5)
        if len(pool) > 0:
            recent = pool.sort_values("year", ascending=False).head(30)
            n = min(N_POSITIVE_LATEST_PER_INDICATOR, len(recent))
            s = recent.sample(n=n, random_state=rng).copy()
            s["prompt_type"] = "baseline_latest"
            samples.append(s)

        # POSITIVE direct (5)
        if len(pool) > 0:
            already_idx = samples[-1].index if samples else pd.Index([])
            remaining = pool.drop(already_idx, errors="ignore")
            if len(remaining) < N_POSITIVE_DIRECT_PER_INDICATOR:
                remaining = pool
            recent2 = remaining.sort_values("year", ascending=False).head(30)
            n = min(N_POSITIVE_DIRECT_PER_INDICATOR, len(recent2))
            s = recent2.sample(n=n, random_state=rng).copy()
            s["prompt_type"] = "direct"
            samples.append(s)

        # T1 (20) — mix intermediate gaps + future years
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
            pool_inter = inter_recent if len(inter_recent) >= 6 else inter_df
        else:
            pool_inter = pd.DataFrame()

        target_inter = max(0, int(0.30 * N_T1_PER_INDICATOR))
        n_inter = min(target_inter, len(pool_inter))
        n_future = N_T1_PER_INDICATOR - n_inter

        if n_inter > 0:
            samples.append(pool_inter.sample(n=n_inter, random_state=rng))
        if n_future > 0:
            n_pick = min(n_future, len(COUNTRIES))
            t1_countries = rng.choice([c["iso3"] for c in COUNTRIES], size=n_pick, replace=False)
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

        # T2 (20) — natural pool first, then fallback
        pool_t2_raw = hall_t2[hall_t2["indicator_code"] == code].drop_duplicates(subset=["indicator_code", "country_code"])
        n_t2_natural = min(N_T2_PER_INDICATOR, len(pool_t2_raw))
        if n_t2_natural > 0:
            samples.append(pool_t2_raw.sample(n=n_t2_natural, random_state=rng))

        n_t2_fallback_needed = N_T2_PER_INDICATOR - n_t2_natural
        if n_t2_fallback_needed > 0:
            valid = valid_fallback(code)
            if len(valid) >= n_t2_fallback_needed:
                indices = rng.choice(len(valid), size=n_t2_fallback_needed, replace=False)
                picked = [valid[i] for i in indices]
            else:
                picked = valid
                if not picked:
                    print(f"  WARNING: indicator {code} has 0 valid T2 cases — all fallback countries have data")

            for fb in picked:
                samples.append(pd.DataFrame([{
                    "indicator_code": code, "indicator_name": name, "unit": unit,
                    "domain": domain, "data_type": data_type,
                    "country_code": fb["iso3"], "country_name": fb["name"],
                    "region": "OTHER", "income": "HIC",
                    "year": 2023, "query_type": "HALLUCINATION_T2", "ground_truth_value": None,
                }]))

    sample = pd.concat(samples, ignore_index=True)

    sample.loc[(sample["query_type"] == "HALLUCINATION_T1") & (sample["prompt_type"].isna()), "prompt_type"] = "direct"
    sample.loc[(sample["query_type"] == "HALLUCINATION_T2") & (sample["prompt_type"].isna()), "prompt_type"] = "baseline_latest"
    sample["prompt_type"] = sample["prompt_type"].fillna("baseline_latest")

    def build_prompt(row):
        # Prompts MUST use country NAMES (not ISO3 codes). The whole pilot
        # series tests how the model handles human-readable country names —
        # if a prompt accidentally embeds an ISO3 code, it short-circuits
        # the country-name → code resolution we're trying to measure.
        if row["prompt_type"] == "baseline_latest":
            return f"What is the latest available {row['indicator_name']} for {row['country_name']}?"
        return f"What was {row['indicator_name']} for {row['country_name']} in {int(row['year'])}?"

    sample["prompt_text"] = sample.apply(build_prompt, axis=1)

    # Guardrail: prompts must use country LABELS and indicator LABELS only —
    # never country ISO3 codes ("BDI", "BEL") or indicator codes ("CME_MRY0T4",
    # "NT_ANT_HAZ_NE2"). Either kind would short-circuit exactly the
    # name-resolution failure mode we're testing. The regex catches both:
    # any token of length ≥3 that starts uppercase and is composed only of
    # uppercase letters / digits / underscores.
    code_pattern = sample["prompt_text"].str.contains(
        r"\b[A-Z][A-Z0-9_]{2,}\b", regex=True
    )
    if code_pattern.any():
        offenders = sample.loc[code_pattern, "prompt_text"].head(5).tolist()
        raise AssertionError(
            f"Prompts must use country names AND indicator names only — "
            f"never ISO3 codes or indicator codes. "
            f"{code_pattern.sum()} prompt(s) contain an uppercase-code-like token. "
            f"First offenders: {offenders}"
        )

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
    print("v0.6.0 Validation Sample (mcp060) — Fourth Independent Round")
    print("=" * 80)
    print(f"  Indicators:        {len(INDICATORS)} (same as R1, R2, mcp051)")
    print(f"  Main countries:    {len(COUNTRIES)} (NEW — zero overlap with R1+R2+mcp051)")
    print(f"  T2 fallback:       {len(T2_FALLBACK_COUNTRIES)} (NEW — zero overlap with prior fallback sets)")
    print(f"  Years:             {YEAR_START}-{YEAR_END}")
    print(f"  Seed:              {SEED} (R1: 20260322, R2: 20260326, mcp051: 20260501)")
    print(f"  Per-indicator n:   {N_POSITIVE_LATEST_PER_INDICATOR + N_POSITIVE_DIRECT_PER_INDICATOR} POS + {N_T1_PER_INDICATOR} T1 + {N_T2_PER_INDICATOR} T2 = 50")
    print(f"  Total target:      500 (100 POS + 200 T1 + 200 T2)")
    print(f"  unicefdata:        {unicefdata.__version__}")
    print(f"  Output:            {OUTPUT_DIR}/")
    print()

    print("Fetching main-country data...")
    gt_df = fetch_all_data()
    print(f"\n  Total observations: {len(gt_df):,d}")

    print("\nValidating T2 fallback country list (probing for accidental data)...")
    t2_invalid = fetch_t2_fallback_data()
    if not t2_invalid.empty:
        print(f"  Found {len(t2_invalid)} (indicator, country) pairs in T2_FALLBACK that have data:")
        for _, row in t2_invalid.iterrows():
            print(f"    - {row['indicator_code']:<20s} x {row['country_code']}")
        print("  These will be excluded from T2 sampling.")
    else:
        print("  All T2 fallback countries are clean — no accidental data found.")

    print("\nClassifying universe...")
    universe = classify_queries(gt_df)

    print("\nSampling...")
    sample = sample_queries(universe, t2_invalid)
    sample = add_latest_values(sample, gt_df)

    print(f"\n  Sample composition:")
    for qt in ["POSITIVE", "HALLUCINATION_T1", "HALLUCINATION_T2"]:
        print(f"    {qt:<25s} {len(sample[sample['query_type'] == qt]):>4d}")
    print(f"    {'TOTAL':<25s} {len(sample):>4d}")

    print(f"\n  Countries used: {sorted(sample['country_code'].unique())}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    gt_df.to_csv(f"{OUTPUT_DIR}/ground_truth_values.csv", index=False)
    universe.to_csv(f"{OUTPUT_DIR}/query_universe.csv", index=False)
    sample.to_csv(f"{OUTPUT_DIR}/sample.csv", index=False)

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "purpose": "v0.6.0 server-side hardening + prompt caching pilot",
        "design_doc": "internal/v0_5_1_validation_design.md",
        "round_label": "mcp060",
        "previous_seeds": {"R1": 20260322, "R2": 20260326, "mcp051": 20260501},
        "indicators": [i["code"] for i in INDICATORS],
        "countries": [c["iso3"] for c in COUNTRIES],
        "t2_fallback_countries": [c["iso3"] for c in T2_FALLBACK_COUNTRIES],
        "t2_fallback_excluded_pairs": (
            [{"indicator_code": r["indicator_code"], "country_code": r["country_code"]}
             for _, r in t2_invalid.iterrows()]
            if not t2_invalid.empty else []
        ),
        "year_range": [YEAR_START, YEAR_END],
        "sample_rows": len(sample),
        "sample_counts": sample["query_type"].value_counts().to_dict(),
        "unicefdata_version": unicefdata.__version__,
    }
    with open(f"{OUTPUT_DIR}/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n  Saved:  {OUTPUT_DIR}/")
    print(f"    sample.csv             ({len(sample)} rows)")
    print(f"    ground_truth_values.csv")
    print(f"    query_universe.csv")
    print(f"    metadata.json")
    print("\nNext step:")
    print("  python examples/benchmark_eqa.py \\")
    print(f"    --ground-truth {OUTPUT_DIR}/sample.csv --tag mcp060")


if __name__ == "__main__":
    main()
