# Statistical Analysis of Benchmark Results

Parquet: `eqa_claude-sonnet-4-20250514_20260323_174311.parquet` | n=300 queries | Bootstrap: 10000 iterations
Seed: 20260322

## 1. Positive queries: baseline_latest (n=100) -- EQA = ER x YA x VA

| Metric | LLM alone (A) | LLM + MCP (B) |
|--------|---------------|---------------|
| Mean EQA | 0.172 [0.127, 0.220] | 0.785 [0.701, 0.860] |
| Mean difference (B - A) | +0.613 [+0.521, +0.701] | |
| Wilcoxon signed-rank | W=110.0, p=1.64e-14 | |
| Cohen's d | 1.34 | |
| Effect size interpretation | large | |

### Component contribution to EQA gain (baseline_latest)
- dER: +0.340 [+0.210, +0.460]
- dYA: +0.547 [+0.450, +0.642]
- dVA: +0.442 [+0.339, +0.542]

## 1. Positive queries: direct (n=100) -- EQA = ER x VA

| Metric | LLM alone (A) | LLM + MCP (B) |
|--------|---------------|---------------|
| Mean EQA | 0.121 [0.065, 0.182] | 0.843 [0.773, 0.906] |
| Mean difference (B - A) | +0.722 [+0.616, +0.822] | |
| Wilcoxon signed-rank | W=147.0, p=5.30e-17 | |
| Cohen's d | 1.34 | |
| Effect size interpretation | large | |

### Component contribution to EQA gain (direct)
- dER: +0.730 [+0.600, +0.840]
- dVA: +0.722 [+0.611, +0.822]

## 2. Hallucination analysis

### HALLUCINATION_T1 (n=50)
- A hallucination rate: 12% (6/50)
- B hallucination rate: 14% (7/50)
- McNemar's test: chi2=0.00, p=1.0000
- Discordant pairs: A-only=4, B-only=5
- Significant at alpha=0.05: No

  Fisher's exact by indicator:
  - CME_MRM0: A=0/5, B=0/5, Fisher p=1.000
  - CME_MRY0: A=0/5, B=0/5, Fisher p=1.000
  - CME_MRY0T4: A=0/5, B=0/5, Fisher p=1.000
  - CME_MRY1T4: A=0/5, B=0/5, Fisher p=1.000
  - ED_CR_L1: A=0/5, B=0/5, Fisher p=1.000
  - MNCH_BIRTH18: A=0/5, B=3/5, Fisher p=0.167
  - MNCH_CSEC: A=3/5, B=0/5, Fisher p=0.167
  - NT_ANT_HAZ_NE2: A=2/5, B=3/5, Fisher p=1.000
  - NT_ANT_WAZ_NE2: A=0/5, B=1/5, Fisher p=1.000
  - NT_ANT_WHZ_NE2: A=1/5, B=0/5, Fisher p=1.000

### HALLUCINATION_T2 (n=50)
- A hallucination rate: 12% (6/50)
- B hallucination rate: 38% (19/50)
- McNemar's test: chi2=9.60, p=0.0019
- Discordant pairs: A-only=1, B-only=14
- Significant at alpha=0.05: Yes

  Fisher's exact by indicator:
  - CME_MRM0: A=1/5, B=4/5, Fisher p=0.206
  - CME_MRY0: A=4/5, B=4/5, Fisher p=1.000
  - CME_MRY0T4: A=0/5, B=4/5, Fisher p=0.048
  - CME_MRY1T4: A=0/5, B=4/5, Fisher p=0.048
  - ED_CR_L1: A=0/5, B=0/5, Fisher p=1.000
  - MNCH_BIRTH18: A=0/5, B=1/5, Fisher p=1.000
  - MNCH_CSEC: A=1/5, B=0/5, Fisher p=1.000
  - NT_ANT_HAZ_NE2: A=0/5, B=0/5, Fisher p=1.000
  - NT_ANT_WAZ_NE2: A=0/5, B=2/5, Fisher p=0.444
  - NT_ANT_WHZ_NE2: A=0/5, B=0/5, Fisher p=1.000

## 3. Component correlation matrix (positive queries, B condition)

| | ER_B | YA_B | VA_B | EQA_B |
|---|---|---|---|---|
| er_b | 1.000 | 0.646 | 0.887 | 0.839 |
| ya_b | 0.646 | 1.000 | 0.675 | 0.745 |
| va_b | 0.887 | 0.675 | 1.000 | 0.966 |
| eqa_b | 0.839 | 0.745 | 0.966 | 1.000 |

## 4. Per-indicator EQA_B with 95% bootstrap CI

| Indicator | n | EQA_B mean | 95% CI | Significant vs A? |
|-----------|---|-----------|--------|-------------------|
| CME_MRM0 | 10 | 1.000 | [1.000, 1.000] | Yes (p=1.953e-03) |
| CME_MRY0 | 10 | 1.000 | [1.000, 1.000] | Yes (p=1.953e-03) |
| CME_MRY0T4 | 10 | 1.000 | [1.000, 1.000] | Yes (p=1.953e-03) |
| CME_MRY1T4 | 10 | 1.000 | [1.000, 1.000] | Yes (p=1.953e-03) |
| ED_CR_L1 | 10 | 1.000 | [1.000, 1.000] | Yes (p=1.953e-03) |
| MNCH_BIRTH18 | 10 | 0.004 | [0.000, 0.011] | No (p=1.000e+00) |
| MNCH_CSEC | 10 | 0.000 | [0.000, 0.000] | No (p=6.250e-02) |
| NT_ANT_HAZ_NE2 | 10 | 0.850 | [0.649, 1.000] | No (p=6.055e-02) |
| NT_ANT_WAZ_NE2 | 10 | 1.000 | [1.000, 1.000] | Yes (p=1.953e-03) |
| NT_ANT_WHZ_NE2 | 10 | 1.000 | [1.000, 1.000] | Yes (p=1.953e-03) |