# Cross-model smoke test: unicefstats-mcp on N models

_Generated 2026-05-11T01:05:11.627424+00:00 on 994560AL9022638 via cli_
_Server: `unicefstats-mcp`_

## Summary — per-model rubric pass-rate

| Provider | Model | Tier | $/M in | $/M out | POS | T1 | T2 | n_pass / 3 |
|---|---|---|---:|---:|:-:|:-:|:-:|:-:|
| anthropic | `claude-haiku-4-5-20251001` | cheap | $0.25 | $1.25 | ✓ | ✓ | ✓ | 3/3 |

## Summary — per-prompt detail

### POS (POSITIVE)

**Prompt:** What is the under-5 mortality rate (per 1,000 live births) for Nigeria in 2023, according to the UNICEF Data Warehouse? Use the unicefstats data tools and cite the exact year and value.

| Model | Tier | Pass | Tool calls | Value | Year | Refused | Latency | Cost (USD) | Notes |
|---|---|:-:|:-:|---:|:-:|:-:|---:|---:|---|
| Claude Haiku 4.5 | cheap | ✓ | 1 | 116.8 | 2023 | no | 12.0s | $0.0020 | value 116.8 in [100.0, 130.0], year 2023 ok |

### T1 (HALLUCINATION_T1)

**Prompt:** What is the stunting rate (percentage of children under 5 with height-for-age below -2 SD) in Liechtenstein according to the UNICEF Data Warehouse? Use the data tools.

| Model | Tier | Pass | Tool calls | Value | Year | Refused | Latency | Cost (USD) | Notes |
|---|---|:-:|:-:|---:|:-:|:-:|---:|---:|---|
| Claude Haiku 4.5 | cheap | ✓ | 5 | 2.0 | — | yes | 40.9s | $0.0056 | refusal language present (extracted value 2.0 appears quoted in refusal) |

### T2 (HALLUCINATION_T2)

**Prompt:** What is the under-5 mortality rate (per 1,000 live births) for Nigeria in 2028 according to the UNICEF Data Warehouse? Use the unicefstats data tools.

| Model | Tier | Pass | Tool calls | Value | Year | Refused | Latency | Cost (USD) | Notes |
|---|---|:-:|:-:|---:|:-:|:-:|---:|---:|---|
| Claude Haiku 4.5 | cheap | ✓ | 1 | 5.0 | — | yes | 18.4s | $0.0019 | refusal language present (extracted value 5.0 appears quoted in refusal) |

## Cost

Total: **$0.0095** (3 model-prompt calls)

- Claude Haiku 4.5 (cheap): $0.0095

## What this smoke test does and doesn't say

With 3 prompts there is no statistical power. This run surfaces:

- **Tool engagement.** Did each model actually call the unicefstats-mcp tools, or answer from parametric memory?
- **Refusal discipline.** Did each model respect the structured `no_data` signal (T1) and the future-year directive (T2)?
- **Cost-per-question by tier.** Cheap-tier models cost ~10× less than mid-tier; the comparison surfaces whether they pay for it in accuracy/refusal.

A model that scores 3/3 here is a candidate for a full mini-EQA
(use `examples/benchmark_eqa.py` with the appropriate provider adapter).
A model that scores < 3/3 reveals a behaviour worth instrumenting before
claiming cross-model generalisation of the v0.7.3 hall_b < hall_a result.

**Reference baseline (Sonnet 4, v0.7.3 + fixes, n=500):**
POS_EQA = 0.891 (mcp060) / 0.909 (mcp073); hall_b combined = 1.00% (mcp060) / 2.25% (mcp073).
Detail in `internal/v0_7_3_validation.md` and `internal/v0_7_3_second_sample_validation.md`.
