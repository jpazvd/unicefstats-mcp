"""Build the FIFTH independent sample, for second-sample validation of v0.7.3 + fixes.

Same 10 indicators as R1/R2/mcp051/mcp060, n=500, with a FIFTH-set of countries
fully disjoint from all prior rounds. Purpose: validate the v0.7.3 + fixes
benchmark result (POS_EQA=0.891, hall_b=1.00%) does not depend on the specific
country picks in `mcp060`.

Sample composition:
  - 100 POSITIVE       (5 latest + 5 direct per 10 indicators)
  - 200 HALLUCINATION_T1 (20 per indicator)
  - 200 HALLUCINATION_T2 (20 per indicator)

Seed independence:
  R1:     20260322 (00_build_ground_truth.py default)
  R2:     20260326 (04_replication_sample.py hardcoded)
  mcp051: 20260501 (05_mcp051_sample.py)
  mcp060: 20260502 (06_mcp060_sample.py)
  mcp073: 20260510 (this file)

All five POSITIVE country pools are mutually disjoint. T2 fallback reuses
mcp060's list — fallback countries are by-construction empty for these 10
indicators, so reuse doesn't affect statistical independence of the
POSITIVE/T1 sample (the actual measurement surface).

Usage:
    python examples/07_mcp073_sample.py
    python examples/benchmark_eqa_batch.py \\
        --ground-truth examples/ground_truth_mcp073/sample.csv --tag mcp073_v073_postfix

Output:
    examples/ground_truth_mcp073/
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
# Same 10 indicators as R1 + R2 + mcp051 + mcp060 (controlled comparison surface)
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
# FIFTH-SET countries — zero overlap with R1, R2, mcp051, or mcp060.
# Used so far across rounds (80 countries):
#   R1:     NGA ETH COD MLI NER IND BGD KEN PAK BRA MEX TUR CHN THA JPN USA GBR FRA DEU AUS
#   R2:     TCD MOZ BFA AFG MDG GHA VNM EGY PHL PER COL ZAF IDN IRQ KOR CAN ITA ESP NOR NZL
#   mcp051: SDN SOM GIN RWA TGO NPL KHM LKA MMR UGA ECU DOM JAM TUN MYS SGP ARE CHE AUT SWE
#   mcp060: MWI BDI ERI LBR SLE SEN CIV TZA HND BOL JOR CRI NAM GTM PRY SAU QAT ISR BEL NLD
# Balanced 5 LIC + 5 LMC + 5 UMC + 5 HIC.
# ---------------------------------------------------------------------------

COUNTRIES = [
    # LIC (5) — Sub-Saharan Africa + Yemen
    {"iso3": "YEM", "name": "Yemen",             "region": "MNA", "income": "LIC"},
    {"iso3": "CAF", "name": "Central African Republic", "region": "WCA", "income": "LIC"},
    {"iso3": "GNB", "name": "Guinea-Bissau",     "region": "WCA", "income": "LIC"},
    {"iso3": "COM", "name": "Comoros",           "region": "ESA", "income": "LIC"},
    {"iso3": "ZMB", "name": "Zambia",            "region": "ESA", "income": "LIC"},
    # LMC (5) — North Africa + Central Asia + SE Asia
    {"iso3": "MAR", "name": "Morocco",           "region": "MNA", "income": "LMC"},
    {"iso3": "DZA", "name": "Algeria",           "region": "MNA", "income": "LMC"},
    {"iso3": "LAO", "name": "Laos",              "region": "EAP", "income": "LMC"},
    {"iso3": "KGZ", "name": "Kyrgyzstan",        "region": "ECA", "income": "LMC"},
    {"iso3": "TJK", "name": "Tajikistan",        "region": "ECA", "income": "LMC"},
    # UMC (5) — Central Asia + Caucasus + Eastern Europe
    {"iso3": "IRN", "name": "Iran",              "region": "MNA", "income": "UMC"},
    {"iso3": "AZE", "name": "Azerbaijan",        "region": "ECA", "income": "UMC"},
    {"iso3": "GEO", "name": "Georgia",           "region": "ECA", "income": "UMC"},
    {"iso3": "ALB", "name": "Albania",           "region": "ECA", "income": "UMC"},
    {"iso3": "BLR", "name": "Belarus",           "region": "ECA", "income": "UMC"},
    # HIC (5) — Gulf + Mediterranean
    {"iso3": "KWT", "name": "Kuwait",            "region": "MNA", "income": "HIC"},
    {"iso3": "BHR", "name": "Bahrain",           "region": "MNA", "income": "HIC"},
    {"iso3": "OMN", "name": "Oman",              "region": "MNA", "income": "HIC"},
    {"iso3": "CYP", "name": "Cyprus",            "region": "ECA", "income": "HIC"},
    {"iso3": "MLT", "name": "Malta",             "region": "ECA", "income": "HIC"},
]

# ---------------------------------------------------------------------------
# T2 fallback — reuses mcp060's list. Fallback countries are territories
# where the 10 indicators have no data by construction (validated at runtime
# by fetch_t2_fallback_data()), so reuse across rounds is fine.
# ---------------------------------------------------------------------------

T2_FALLBACK_COUNTRIES = [
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
    {"iso3": "SXM", "name": "Sint Maarten"},
    {"iso3": "CYM", "name": "Cayman Islands"},
    {"iso3": "FLK", "name": "Falkland Islands"},
    {"iso3": "IOT", "name": "British Indian Ocean Territory"},
    {"iso3": "PCN", "name": "Pitcairn"},
    {"iso3": "SGS", "name": "South Georgia"},
    {"iso3": "NFK", "name": "Norfolk Island"},
    {"iso3": "CXR", "name": "Christmas Island"},
    {"iso3": "CCK", "name": "Cocos Islands"},
    {"iso3": "HMD", "name": "Heard and McDonald Islands"},
    {"iso3": "BVT", "name": "Bouvet Island"},
    {"iso3": "ATA", "name": "Antarctica"},
    {"iso3": "UMI", "name": "United States Minor Outlying Islands"},
    {"iso3": "ESH", "name": "Western Sahara"},
]

YEAR_START = 2000
YEAR_END = 2024
SEED = 20260510  # five rounds: R1=20260322, R2=20260326, mcp051=20260501, mcp060=20260502, mcp073=20260510

N_POSITIVE_LATEST_PER_INDICATOR = 5
N_POSITIVE_DIRECT_PER_INDICATOR = 5
N_T1_PER_INDICATOR = 20
N_T2_PER_INDICATOR = 20
CME_FUTURE_YEARS = [2025, 2026, 2027, 2028, 2029]

OUTPUT_DIR = "examples/ground_truth_mcp073"


# ---------------------------------------------------------------------------
# Pipeline functions — re-use mcp060's implementation by import to avoid
# duplicating ~300 lines that are bit-identical.
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util as _u  # noqa: E402

_spec = _u.spec_from_file_location("_mcp060",
                                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "06_mcp060_sample.py"))
_mcp060 = _u.module_from_spec(_spec)
_spec.loader.exec_module(_mcp060)

# Re-bind the constants the imported module uses
_mcp060.INDICATORS = INDICATORS
_mcp060.COUNTRIES = COUNTRIES
_mcp060.T2_FALLBACK_COUNTRIES = T2_FALLBACK_COUNTRIES
_mcp060.SEED = SEED
_mcp060.OUTPUT_DIR = OUTPUT_DIR
_mcp060.YEAR_START = YEAR_START
_mcp060.YEAR_END = YEAR_END

fetch_all_data = _mcp060.fetch_all_data
fetch_t2_fallback_data = _mcp060.fetch_t2_fallback_data
classify_queries = _mcp060.classify_queries
sample_queries = _mcp060.sample_queries
add_latest_values = _mcp060.add_latest_values


def main():
    import unicefdata
    print("=" * 80)
    print("v0.7.3 second-sample validation (mcp073) — Fifth Independent Round")
    print("=" * 80)
    print(f"  Indicators:        {len(INDICATORS)} (same 10 as R1, R2, mcp051, mcp060)")
    print(f"  Main countries:    {len(COUNTRIES)} (NEW — zero overlap with R1/R2/mcp051/mcp060)")
    print(f"  T2 fallback:       {len(T2_FALLBACK_COUNTRIES)} (reused from mcp060 — empty by construction)")
    print(f"  Years:             {YEAR_START}-{YEAR_END}")
    print(f"  Seed:              {SEED}")
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
        print(f"  Found {len(t2_invalid)} (indicator, country) pairs in T2_FALLBACK that have data — excluded.")
    else:
        print("  All T2 fallback countries clean.")

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
        "purpose": "v0.7.3 + fixes second-sample validation",
        "round_label": "mcp073",
        "previous_seeds": {"R1": 20260322, "R2": 20260326, "mcp051": 20260501, "mcp060": 20260502},
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
    print("  python examples/benchmark_eqa_batch.py \\")
    print(f"    --ground-truth {OUTPUT_DIR}/sample.csv --tag mcp073_v073_postfix")


if __name__ == "__main__":
    main()
