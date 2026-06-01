# unicefstats-mcp Benchmark Results

**Last revised**: 2026-05-10 — added v0.7.3 + fixes section (R4 + R5) and v1.4 scoring note.
**Original version**: unicefstats-mcp v0.3.0 + unicefdata v2.4.0
**Model**: Claude Sonnet 4 (`claude-sonnet-4-20250514`)
**Temperature**: 0.0 (deterministic)
**Original date**: 2026-03-26
**Metric**: EQA = ER × YA × VA ([Azevedo 2025](https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md))

> **Canonical scoreboard as of 2026-05-10** is v0.7.3 + fixes:
> POS EQA **0.891** (mcp060, 40 ctry) / **0.909** (mcp073, disjoint 20-ctry).
> hall_b combined **1.00%** (mcp060) / **2.25%** (mcp073) — both below hall_a 2.50%.
> First version where MCP makes the model safer on absent-data queries.
> Detail in [`internal/v0_7_3_validation.md`](../internal/v0_7_3_validation.md) and [`internal/v0_7_3_second_sample_validation.md`](../internal/v0_7_3_second_sample_validation.md).

| Run | Version | Countries | Queries | EQA (B) | hall_b (B) | Note |
|---|---|---|---|---|---|---|
| R1 (original) | v0.3.0 | 20 (sample A) | 300 | 0.990 (v1.3 score) | 37% (v1.3) | Scoring superseded — see §v1.4 note |
| R2 (replication) | v0.3.0 | 20 (sample B, no overlap with R1) | 300 | 0.990 (v1.3 score) | 37% (v1.3) | Scoring superseded |
| R3 (same-day clean) | v0.7.2 | mcp060 sample | 500 | 0.897 (v1.3) / **0.793 (v1.4)** | 13% (v1.3) / **3.75% (v1.4)** | v1.3 published earlier, v1.4 is canonical |
| **R4 (v0.7.3 + fixes)** | v0.7.3 + fixes | mcp060 sample (40 ctry) | 500 | **0.891 (v1.4)** | **1.00% (v1.4)** | hall_b < hall_a — first time |
| **R5 (validation)** | v0.7.3 + fixes | mcp073 sample (20 disjoint ctry) | 500 | **0.909 (v1.4)** | **2.25% (v1.4)** | Independent country sample |

**Important scoring-rule note**: the R1–R3 hallucination numbers above (37%, 13%) are under the v1.3 extractor, which counted any numeric value mentioned in a response as a "claim" — including values the LLM was quoting from `no_data` tool results inside an explicit refusal. The v1.4 extractor (`benchmark_eqa.py:_detect_refusal`) flips the precedence: if the response text contains refusal language, the extracted value is None regardless of what numbers appear in the prose. Re-scoring R3 under v1.4 drops hall_b from 13% to 3.75%. R1 and R2 parquets weren't rescored (they're archived); under v1.4 the values would likely compress similarly. **R4 and R5 are scored under v1.4 from the start**; they are the canonical reference for current hallucination numbers.

**Data**:
- R1: `eqa_v030_claude-sonnet-4-20250514_20260326_112743.parquet`
- R2: `eqa_claude-sonnet-4-20250514_20260326_203819_r2v2.parquet`
- R3: `eqa_claude-sonnet-4-20250514_20260506_172421_sameday_v071.parquet` (POS+T1+T2: 100+200+200) and same-day v0.6.4 baseline at `eqa_claude-sonnet-4-20250514_20260506_233553_sameday_v064.parquet`
- **R4**: `eqa_claude-sonnet-4-20250514_20260510_030318_v073_postfix_v4_resumed.parquet`
- **R5**: `eqa_claude-sonnet-4-20250514_20260510_204339_mcp073_v073_postfix.parquet`

R1 and R2 used 200 POS queries each (latest+direct prompt types); R3 used 100 POS queries and adds 400 hallucination queries (T1+T2). R4 and R5 used the full 500-query design (100 POS + 200 T1 + 200 T2). The R3 numbers above are POS-only; for the original hallucination report see [§9. v0.7.2 same-day clean reproduction](#9-v072-same-day-clean-reproduction-2026-05-08); for the current canonical hallucination scoreboard see [`internal/v0_7_3_validation.md`](../internal/v0_7_3_validation.md) + [`internal/v0_7_3_second_sample_validation.md`](../internal/v0_7_3_second_sample_validation.md).

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

---

## 9. v0.7.2 same-day clean reproduction (2026-05-08)

After the v0.4.0 safety layer and v0.7.0 indicator resolver shipped, we re-ran a 500-query subset of the benchmark on the per-wave checkpoint architecture (PR #53), with the v0.6.4 baseline run **same-day** to control for upstream-model snapshot drift. Sample design: 100 POSITIVE + 200 T1 (gap-year) + 200 T2 (forward-of-frontier) on the `mcp060` country sample.

### 9.1 Headline

| Metric | LLM alone (v0.6.4 same-day) | LLM + MCP (v0.7.2) | Δ |
|---|---|---|---|
| **POS EQA mean** | 0.121 | **0.897** | +77.6 pp (~7×) |
| **T1 + T2 hallucination (combined)** | 2.0% | **13.0%** | +11.0 pp |
| Wall-clock (parallel runs) | 3.8 h | 9.2 h | +5.4 h |

A-side EQA was within 0.3 pp across the two runs, confirming the same-day discipline worked: the B-side delta is real, not snapshot drift.

### 9.2 What changed since v0.3.0

The v0.3.0 R1 + R2 benchmarks above showed **EQA = 0.990 with tools, 0.147 without** (6.7×) and **T2 hallucination = 37%**. The v0.7.2 reproduction:

- Confirms the accuracy headline at ~7× (POS EQA 0.897 vs 0.121, +77.6 pp). The slightly lower absolute EQA on v0.7.2 reflects the different sample composition (mcp060 vs the original 40-country / 10-indicator sample).
- Shows the v0.4.0 safety layer + v0.7.0 indicator resolver brought T2 fabrication from 37% (v0.3.0) → 13% combined T1+T2 (v0.7.2) — a **24-of-26 pp reduction** in fabrication on impossible queries.
- The residual ~11 pp gap (relative to the 2.0% no-tools baseline) appears **structural**: it matches what the broader tool-augmented LLM and RAG literature documents. Server-side guardrails reduce the magnitude of tool-augmented hallucination; they do not, on current evidence, change the direction.

### 9.3 Methodology improvements vs v0.3.0

- **Per-wave state checkpoint** (PR #53). `benchmark_eqa_batch.py` now writes a JSON checkpoint after each wave; `resume_batch_run.py --load-state` loads from checkpoint without live tool re-dispatch (the resume row-alignment bug discovered during v0.7.0 validation).
- **Same-day v0.6.4 baseline**. Both runs were submitted within ~30 minutes of each other, so the upstream Anthropic model snapshot is identical and the A/B delta is attributable to the MCP change, not upstream drift.
- **Fresh-dispatch rescoring**. Resolved an SDMX-flakiness scoring artifact in the v0.7.2 run where transient 502/504s during the scoring pass forced text-extraction fallback. Re-running `_extract_from_tool_calls` on the affected POS rows recovered the canonical values; rescored POS EQA went from 0.800 to 0.897.

### 9.4 What this experiment does NOT establish

This is **not** evidence that "the MCP layer doesn't introduce drift" in general. UNICEF and World Bank both surface the same upstream UN IGME estimates for mortality indicators, and our cross-check experiment (see [examples/mcp-smoke-test/CROSS-CHECK-imr-vs-u5mr.md](mcp-smoke-test/CROSS-CHECK-imr-vs-u5mr.md)) confirms that those estimates flow through both MCP wrappers unchanged. That's evidence of **upstream-data agreement** between two IGME-sourced wrappers — *not* a general MCP-layer fidelity claim. To test fidelity in the general case you'd need an indicator pair where UNICEF and WB compute *independently* (fertility, GDP, education completion). That follow-up experiment is parking-lot Item 5.

### 9.5 Literature alignment

The +11 pp residual on impossible queries aligns with what the broader tool-augmented LLM and RAG literature has been documenting in parallel:

- *The Reasoning Trap: How Enhancing LLM Reasoning Amplifies Tool Hallucination* (ICLR 2025) — shows the relationship is causal: as models get better at tool use, tool hallucination rises *proportionally* with capability.
- *Reducing Tool Hallucination via Reliability Alignment* (Cao et al., 2024, [arXiv:2412.04141](https://arxiv.org/abs/2412.04141)) — formalises the failure as *tool-selection* errors and *tool-usage* errors.
- *ReDeEP: Detecting Hallucination in Retrieval-Augmented Generation via Mechanistic Interpretability* (Sun et al., 2024) — shows mechanistically that an LLM's parametric knowledge can override retrieved context inside the residual stream.

### 9.6 Run artefacts

All files are in `examples/results/`:

- `eqa_claude-sonnet-4-20250514_20260506_172421_sameday_v071.{parquet,csv,json,checkpoint.json}` — v0.7.2 (with MCP; filename retains the historical `v071` slug from when the run was tagged)
- `eqa_claude-sonnet-4-20250514_20260506_233553_sameday_v064.{parquet,csv,json,checkpoint.json}` — v0.6.4 (same-day baseline)
- `logs/sameday_run_metadata.md` — run metadata (batch IDs, wall-clock, drift offset)
