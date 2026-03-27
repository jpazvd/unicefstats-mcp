# Benchmark Design Issues and Fixes

## Problem 1: Severely unbalanced indicator distribution

The current sample has:
- CME indicators: 10 queries each, **zero hallucination tests** (no T1 or T2 possible — annual modeled data has no gaps and exists for all 20 countries)
- ED_CR_L1: 40 queries (10 positive + 3 T1 + 27 T2) — **20% of total benchmark is one education indicator**
- MNCH_BIRTH18: 43 queries (10 positive + 4 T1 + 29 T2) — **21.5% of total**
- NT_ANT_WHZ_NE2: 13 queries — underrepresented

**Impact**: The benchmark results are dominated by MNCH_BIRTH18 (which had the ground truth misclassification) and ED_CR_L1 (which had SDMX API issues). The four CME indicators contribute zero hallucination signal.

## Problem 2: CME indicators cannot contribute to hallucination testing

CME indicators (CME_MRY0T4, CME_MRM0, CME_MRY0, CME_MRY1T4) have:
- Annual modeled estimates from IGME for ALL 20 countries
- Continuous 2000–2024 coverage with no gaps
- Zero T1 cases (no gap years) and zero T2 cases (exists for all countries)

They contribute **only** positive queries. This means 40% of our indicators can only test accuracy, not hallucination.

## Problem 3: T2 is concentrated in HIC countries

T2 (never-existed pairs) only occurs for high-income countries that don't have DHS/MICS surveys. The T2 sample is 100% from: AUS, BRA, CHN, DEU, FRA, GBR, JPN, USA. This means T2 tests a very specific pattern: "Does the LLM know that rich countries don't have nutrition surveys?"

## Problem 4: Ground truth misclassification

The `00_build_ground_truth.py` script uses `totals=True` and `sex="_T"` when fetching, which filters out disaggregated data. Some indicators (MNCH_BIRTH18) have data at different disaggregation levels that the script missed. This led to 29 queries being classified as T2 when the SDMX API actually had data.

## Problem 5: Unequal total queries per indicator

| Indicator | Total queries | % of benchmark |
|---|---|---|
| MNCH_BIRTH18 | 43 | 21.5% |
| ED_CR_L1 | 40 | 20.0% |
| MNCH_CSEC | 27 | 13.5% |
| NT_ANT_HAZ_NE2 | 20 | 10.0% |
| NT_ANT_WAZ_NE2 | 17 | 8.5% |
| NT_ANT_WHZ_NE2 | 13 | 6.5% |
| CME (4 indicators) | 10 each | 5% each |

Two indicators account for 41.5% of all queries.

---

## Fix: Balanced sampling design

### Principle: Equal representation per indicator across all query types

Target: **20 queries per indicator = 200 total** (same budget)

| Indicator | Positive | T1 (gap) | T2 (never) | Total |
|---|---|---|---|---|
| CME_MRY0T4 | 10 | 5 | 5 | 20 |
| CME_MRM0 | 10 | 5 | 5 | 20 |
| CME_MRY0 | 10 | 5 | 5 | 20 |
| CME_MRY1T4 | 10 | 5 | 5 | 20 |
| NT_ANT_HAZ_NE2 | 10 | 5 | 5 | 20 |
| NT_ANT_WAZ_NE2 | 10 | 5 | 5 | 20 |
| NT_ANT_WHZ_NE2 | 10 | 5 | 5 | 20 |
| MNCH_CSEC | 10 | 5 | 5 | 20 |
| MNCH_BIRTH18 | 10 | 5 | 5 | 20 |
| ED_CR_L1 | 10 | 5 | 5 | 20 |
| **Total** | **100** | **50** | **50** | **200** |

### How to get T1/T2 for CME indicators

CME indicators have no natural T1/T2 cases (data exists for all countries/years). Solutions:

**T1 (gap years)**: Use future years (2025, 2026, 2027, 2028, 2029) — these are years where IGME has not yet published estimates. The country-indicator pair exists, but the specific year does not.

**T2 (never existed)**: Use aggregate/regional codes (SSA, WLD, EAP) or fictional ISO3 codes. Alternatively, use very old years (1950s) before data collection began, or use countries that didn't exist (e.g., South Sudan pre-2011 for indicators starting before 2011). The cleanest approach: use the SDMX API to verify which ISO3 codes return 404 for each CME indicator.

### Additional fixes

1. **Fetch with `raw=True`**: In `00_build_ground_truth.py`, use `raw=True` instead of `totals=True` to capture all disaggregation levels and avoid misclassifying existing data as absent.

2. **Verify T2 at query time**: After building the sample, re-query the SDMX API for every T2 case to confirm the data truly doesn't exist. Any case where data is found gets reclassified.

3. **Stratify countries within each indicator**: Ensure each indicator has a mix of LIC/LMC/UMC/HIC countries in its positive sample.

4. **Add a "data found but unexpected" category**: For cases where the MCP returns data that the ground truth classified as absent, track these separately instead of scoring them as hallucinations.
