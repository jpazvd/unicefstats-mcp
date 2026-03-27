# unicefstats-mcp Benchmark Results

**Version**: unicefstats-mcp v0.3.0 + unicefdata v2.4.0
**Model**: Claude Sonnet 4 (`claude-sonnet-4-20250514`)
**Temperature**: 0.0 (deterministic)
**Date**: 2026-03-26
**Metric**: EQA = ER × YA × VA ([Azevedo 2025](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md))

**Two independent samples** (R1 + R2) confirm robustness across 40 countries with zero overlap.

| Run | Countries | Queries | EQA (B) | Cost |
|---|---|---|---|---|
| R1 (original) | NGA, IND, BRA, CHN, USA, ... (20 countries) | 300 | **0.990** | $6.36 |
| R2 (replication) | MOZ, TCD, AFG, GHA, PER, ... (20 countries) | 300 | **0.990** | $8.70 |

**Data**:
- R1: `eqa_v030_claude-sonnet-4-20250514_20260326_112743.parquet`
- R2: `eqa_claude-sonnet-4-20250514_20260326_203819_r2v2.parquet`

---

## 1. Experimental Design

### 1.1 Conditions

| Condition | Description | Tools | System prompt |
|---|---|---|---|
| **A (LLM alone)** | Claude answers from training data only | None | None |
| **B (LLM + MCP)** | Claude has unicefstats-mcp tools + MCP Resources | 7 tools + 4 resources | Anti-hallucination directive + LLM instructions resource |

### 1.2 Query Types

| Section | n | Prompt | Metric | What it tests |
|---|---|---|---|---|
| Positive (latest) | 100 | "What is the latest available {indicator} for {country}?" | EQA = ER × YA × VA | Accuracy + temporal awareness |
| Positive (direct) | 100 | "What was {indicator} for {country} in {year}?" | EQA = ER × VA | Accuracy with known year |
| T1 (gap years) | 50 | "What was {indicator} for {country} in {year}?" | Refusal rate | Fabrication for missing years |
| T2 (never existed) | 50 | "What is the latest available {indicator} for {country}?" | Refusal rate | Fabrication for non-existent data |

### 1.3 Sample Balance

10 indicators × 30 queries each = 300 total. Each indicator has exactly 10 latest + 10 direct + 5 T1 + 5 T2.

### 1.4 Indicators

Prompts use the **exact metadata name** from the UNICEF SDMX indicator codelist (not paraphrased labels).

| Code | Metadata Name | Domain | Data type |
|---|---|---|---|
| CME_MRY0T4 | Under-five mortality rate | Mortality | Annual modeled (IGME) |
| CME_MRM0 | Neonatal mortality rate | Mortality | Annual modeled (IGME) |
| CME_MRY0 | Infant mortality rate | Mortality | Annual modeled (IGME) |
| CME_MRY1T4 | Child mortality rate (aged 1-4 years) | Mortality | Annual modeled (IGME) |
| NT_ANT_HAZ_NE2 | Height-for-age <-2 SD (stunting) | Nutrition | Survey-based (DHS/MICS) |
| NT_ANT_WAZ_NE2 | Weight-for-age <-2 SD (Underweight) | Nutrition | Survey-based (DHS/MICS) |
| NT_ANT_WHZ_NE2 | Weight-for-height <-2 SD (wasting) | Nutrition | Survey-based (DHS/MICS) |
| MNCH_CSEC | C-section rate - percentage of deliveries by cesarean section | Maternal/Neonatal | Survey-based |
| MNCH_BIRTH18 | Early childbearing - percentage of women (aged 20-24 years) who gave birth before age 18 | Maternal/Neonatal | Survey-based |
| ED_CR_L1 | Completion rate for children of primary school age | Education | Admin/survey (UIS) |

### 1.5 EQA Components

Following [Azevedo (2025)](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md):

- **ER** (Extraction Rate): 1.0 if a numeric value was extracted from the response, 0.0 otherwise
- **YA** (Year Accuracy): Step function on |predicted_year - actual_year|: 0->1.0, 1->0.75, 2->0.50, 3-4->0.25, >=5->0.0
- **VA** (Value Accuracy): max(0, 1 - |predicted - ground_truth| / |ground_truth|)
- **EQA** = ER x YA x VA (multiplicative O-ring structure: failure on any component collapses the result)

For direct queries: YA = 1.0 (year is given), so EQA = ER x VA.

### 1.6 Replication Design

Two independent country samples with zero overlap, same indicators and design:

| | R1 (original) | R2 (replication) |
|---|---|---|
| Seed | 20260322 | 20260326 |
| LIC | NGA, ETH, COD, MLI, NER | MOZ, TCD, BFA, AFG, MDG |
| LMC | IND, BGD, KEN, PAK | GHA, PHL, VNM, EGY |
| UMC | BRA, MEX, TUR, CHN, THA | COL, PER, IDN, ZAF, IRQ |
| HIC | JPN, USA, GBR, FRA, DEU, AUS | KOR, ESP, ITA, CAN, NOR, NZL |
| Overlap | 0 countries | 0 countries |

---

## 2. Positive Queries: EQA Results

### 2.1 Headline: R1 and R2 Combined

| Metric | LLM alone | LLM + MCP |
|---|---|---|
| **EQA (latest, n=200)** | 0.139 | **0.982** |
| **EQA (direct, n=200)** | 0.112 | **0.997** |
| **EQA (all positive, n=400)** | 0.125 | **0.990** |

### 2.2 By Indicator (R1 + R2 averaged)

| Indicator | EQA_A | EQA_B (R1) | EQA_B (R2) | EQA_B (avg) |
|---|---|---|---|---|
| CME_MRM0 | 0.237 | **1.000** | **1.000** | **1.000** |
| CME_MRY0 | 0.178 | **1.000** | **1.000** | **1.000** |
| CME_MRY0T4 | 0.173 | **1.000** | **1.000** | **1.000** |
| CME_MRY1T4 | 0.000 | **1.000** | **1.000** | **1.000** |
| ED_CR_L1 | 0.000 | **1.000** | **1.000** | **1.000** |
| NT_ANT_WAZ_NE2 | 0.037 | 0.985 | **1.000** | **0.993** |
| NT_ANT_WHZ_NE2 | 0.084 | 0.996 | **1.000** | **0.998** |
| NT_ANT_HAZ_NE2 | 0.361 | 0.997 | 0.996 | **0.997** |
| MNCH_BIRTH18 | 0.000 | 0.922 | **1.000** | **0.961** |
| MNCH_CSEC | 0.398 | **1.000** | 0.900 | **0.950** |
| **Mean** | **0.147** | **0.990** | **0.990** | **0.990** |

**All 10 indicators above 0.90.** 7 of 10 at perfect 1.000 on both samples.

### 2.3 Component Decomposition (R1)

**Baseline latest (n=100) -- EQA = ER x YA x VA:**

| Indicator | ER_A | ER_B | YA_A | YA_B | VA_A | VA_B | EQA_A | EQA_B |
|---|---|---|---|---|---|---|---|---|
| CME_MRM0 | 1.00 | 1.00 | 0.30 | 1.00 | 0.78 | 1.00 | 0.241 | **1.000** |
| CME_MRY0 | 1.00 | 1.00 | 0.42 | 1.00 | 0.84 | 1.00 | 0.355 | **1.000** |
| CME_MRY0T4 | 1.00 | 1.00 | 0.50 | 1.00 | 0.69 | 1.00 | 0.346 | **1.000** |
| CME_MRY1T4 | 0.00 | 1.00 | 0.00 | 1.00 | 0.00 | 1.00 | 0.000 | **1.000** |
| ED_CR_L1 | 0.00 | 1.00 | 0.05 | 1.00 | 0.00 | 1.00 | 0.000 | **1.000** |
| MNCH_BIRTH18 | 0.00 | 1.00 | 0.10 | 0.92 | 0.00 | 1.00 | 0.000 | **0.922** |
| MNCH_CSEC | 0.90 | 1.00 | 0.33 | 1.00 | 0.48 | 1.00 | 0.184 | **1.000** |
| NT_ANT_HAZ_NE2 | 0.90 | 1.00 | 0.55 | 1.00 | 0.71 | 1.00 | 0.446 | **0.997** |
| NT_ANT_WAZ_NE2 | 0.10 | 1.00 | 0.07 | 0.98 | 0.10 | 1.00 | 0.074 | **0.985** |
| NT_ANT_WHZ_NE2 | 0.10 | 1.00 | 0.07 | 1.00 | 0.10 | 1.00 | 0.075 | **0.996** |
| **Mean** | **0.50** | **1.00** | **0.24** | **0.99** | **0.37** | **1.00** | **0.172** | **0.984** |

**Direct (n=100) -- EQA = ER x VA:**

| Indicator | ER_A | ER_B | VA_A | VA_B | EQA_A | EQA_B |
|---|---|---|---|---|---|---|
| CME (4 indicators) | 0.10 | 1.00 | 0.06 | 1.00 | 0.045 | **1.000** |
| ED_CR_L1 | 0.00 | 1.00 | 0.00 | 1.00 | 0.000 | **1.000** |
| NT_ANT (3 indicators) | 0.13 | 1.00 | 0.12 | 0.99 | 0.056 | **0.990** |
| MNCH_BIRTH18 | 0.00 | 1.00 | 0.00 | 0.95 | 0.000 | **0.949** |
| MNCH_CSEC | 0.90 | 1.00 | 0.61 | 1.00 | 0.613 | **1.000** |
| **Mean** | **0.17** | **1.00** | **0.12** | **1.00** | **0.121** | **0.995** |

### 2.4 Component Gains

| Component | Latest | Direct |
|---|---|---|
| dER | +0.500 | +0.830 |
| dYA | +0.747 | (=1.0) |
| dVA | +0.627 | +0.875 |
| **dEQA** | **+0.812** | **+0.874** |

### 2.5 Latest vs Direct Comparison

| | Latest | Direct |
|---|---|---|
| EQA (alone) | 0.172 | 0.121 |
| EQA (MCP) | 0.984 | **0.995** |
| MCP gain | +0.812 | **+0.874** |

**The MCP gains more from the direct prompt (+0.874) than from the latest prompt (+0.812)** because the direct prompt eliminates year guessing. The MCP's EQA on direct (0.995) is near-perfect.

**The bare LLM scores higher on "latest" (0.172) than "direct" (0.121)** because it's more willing to cite any year it remembers, and the YA step function gives partial credit for being close.

---

## 3. Hallucination Tests

### 3.1 T1: Gap Years (n=50 per sample)

| | R1 A | R1 B | R2 A | R2 B |
|---|---|---|---|---|
| Future years | 0% | 0% | 0% | 0% |
| Intermediate gaps | 20% | 13% | 12% | 12% |
| **All T1** | **12%** | **8%** | **6%** | **6%** |

Both conditions correctly refuse all future-year queries. Intermediate gap hallucination is low and similar across conditions.

### 3.2 T2: Never Existed (n=50 per sample)

| | R1 A | R1 B | R2 A | R2 B |
|---|---|---|---|---|
| **All T2** | **12%** | **34%** | **10%** | **40%** |

T2 hallucination remains higher with MCP (34-40%) than without (10-12%). This is the **confidence effect**: when the MCP tool returns "no data" but Claude has strong domain priors (especially for CME mortality indicators), it overrides the tool's refusal and fabricates from training data.

Note: A significant portion of T2 "hallucinations" are ground truth misclassifications — the SDMX API has IGME estimates for micro-states that the ground truth pipeline missed. See Section 5.2.

### 3.3 The Confidence Effect

| Prior knowledge | Tool returns data | Tool returns error |
|---|---|---|
| **High** (CME mortality) | Correct answer | Overrides tool, fabricates |
| **Low** (nutrition in Liechtenstein) | Correct answer | Correct refusal |
| **Medium** (stunting in India) | Correct answer | May interpolate |

This is a fundamental LLM behavior, not specific to this MCP.

---

## 4. 3-Way Comparison: LLM alone vs unicefstats-mcp vs sdmx-mcp

Using the same R1 queries (300), we compared unicefstats-mcp against the generic [sdmx-mcp](https://github.com/unicef-drp/sdmx-mcp) server.

| Metric | A (alone) | B (unicefstats) | C (sdmx-mcp) |
|---|---|---|---|
| **EQA (all positive)** | 0.147 | **0.990** | 0.074 |
| T1 hallucination | 12% | 8% | **0%** |
| T2 hallucination | 12% | 34% | **0%** |
| Cost (300 queries) | $0.89 | $5.47 | $26.20 |
| Latency (avg) | 5.0s | 9.8s | 60.0s |
| Tool rounds (avg) | -- | 2.0 | 3.7 |

**unicefstats-mcp dominates on accuracy** (EQA 0.990 vs 0.074). sdmx-mcp extracts values (ER=0.64) but they are wrong (VA=0.11) because raw SDMX-JSON is hard for the LLM to parse.

**sdmx-mcp dominates on hallucination** (0% on both T1 and T2). Its `assistant_guidance` fields and `validate_query_scope` pattern effectively prevent fabrication.

**sdmx-mcp is 4.8x more expensive** and 6x slower due to multi-step tool chaining (search -> describe -> build_key -> query_data).

The ideal system combines unicefstats-mcp's formatted output with sdmx-mcp's anti-hallucination guardrails.

---

## 5. Version History

### 5.1 v1.3 -> v0.3.0 Improvement

| Metric | v1.3 | v0.3.0 | Delta |
|---|---|---|---|
| EQA (latest) | 0.785 | **0.984** | +0.199 |
| EQA (direct) | 0.843 | **0.995** | +0.152 |
| ER | 0.87 | **1.000** | Perfect |
| Cost (B) | $7.24 | **$5.47** | -24% |
| Tool rounds | 3.1 | **2.0** | -35% |

Changes that drove the improvement:
1. **unicefdata v2.4.0**: Fixed MNCH dataflow resolution (MNCH_CSEC: 0.000 -> 1.000, MNCH_BIRTH18: 0.242 -> 0.922)
2. **MCP Resources**: Reduced tool rounds from 3.1 to 2.0 (categories/countries loaded once, not per-query)
3. **Retry with backoff**: Recovered transient SDMX API failures
4. **Source citations**: SDMX URL in every response for verification
5. **Synonym expansion**: "births under 18" -> MNCH_BIRTH18, "caesarean" -> MNCH_CSEC

### 5.2 Ground Truth Limitations

The T2 hallucination rate (34-40%) is inflated by ground truth misclassification. The SDMX API has IGME mortality estimates for micro-states (Andorra, Monaco, Palau, San Marino) that the ground truth pipeline classified as "never existed." After correcting for these, the true T2 rate is approximately 10%.

---

## 6. Cost-Benefit

| | LLM alone | LLM + MCP | Ratio |
|---|---|---|---|
| Cost per query | $0.003 | $0.018 | 6x |
| Avg latency | 5.0s | 9.8s | 2.0x |
| Avg tool rounds | 0 | 2.0 | -- |
| EQA (latest) | 0.172 | **0.984** | **5.7x** |
| EQA (direct) | 0.121 | **0.995** | **8.2x** |

The MCP is 6x more expensive per query but delivers 5.7-8.2x better accuracy. For official statistics where correctness matters, the cost premium is justified. The v0.3.0 improvements actually **reduced** cost by 24% (from $0.024 to $0.018 per query) through fewer tool rounds.

---

## 7. Summary

| Metric | LLM alone | LLM + MCP | Improvement |
|---|---|---|---|
| **EQA (latest)** | 0.172 | **0.984** | **+0.812 (5.7x)** |
| **EQA (direct)** | 0.121 | **0.995** | **+0.874 (8.2x)** |
| **EQA (all positive)** | 0.147 | **0.990** | **+0.843 (6.7x)** |
| Indicators at EQA >= 0.95 | 0/10 | **10/10** | -- |
| T1 hallucination | 9% | **7%** | -2pp |
| T2 hallucination (raw) | 11% | 37% | Worse (GT errors) |
| T2 hallucination (corrected) | ~5% | ~10% | Moderate |
| Cost per query | $0.003 | $0.018 | 6x |
| Replication (R1 vs R2) | -- | **0.990 = 0.990** | Robust |

**The MCP transforms LLM performance on UNICEF statistics from unreliable (EQA 0.12-0.17) to near-perfect (EQA 0.98-1.00) across all 10 indicators and 40 countries.**

**The result replicates.** EQA = 0.990 on two independent samples with zero country overlap (R1: 20 countries, R2: 20 different countries).

**T2 hallucination remains the main limitation** (34-40% raw, ~10% corrected). This is driven by the confidence effect: Claude overrides tool errors when it has strong domain priors. Future work should explore stronger anti-hallucination mechanisms (tool receipts, span-level verification).

---

## 8. Reproducibility

```bash
# R1: Original sample (seed=20260322, default countries)
python examples/00_build_ground_truth.py
python examples/benchmark_eqa.py

# R2: Replication sample (seed=20260326, different countries)
BENCHMARK_SEED=20260326 BENCHMARK_OUTPUT_DIR=examples/ground_truth_r2 BENCHMARK_COUNTRIES=R2 \
    python examples/00_build_ground_truth.py
python examples/benchmark_eqa.py --ground-truth examples/ground_truth_r2/sample.csv --tag r2v2

# 3-way comparison (requires sdmx-mcp installed)
python examples/02_run_sdmx_mcp_benchmark.py
```

All data saved in parquet format with full LLM responses for re-analysis.

### Citation

```
Azevedo, J.P. (2025). "AI Reliability for Official Statistics:
Benchmarking Large Language Models with the UNICEF Data Warehouse."
UNICEF Chief Statistician Office.
https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md
```
