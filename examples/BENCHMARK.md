# Benchmark replicability guide

How to clone this repo and reproduce the unicefstats-mcp accuracy +
hallucination benchmark end-to-end. Designed so a new contributor —
or a future-you returning to this code six months from now — can run
the benchmark without scripts breaking on missing dependencies,
missing data files, or undocumented configuration.

If you only want to read the *results*, see
[`RESULTS.md`](RESULTS.md). This file covers *how to produce* them.

## What the benchmark measures

| Test category | What it asks | How it's scored |
|---|---|---|
| **POSITIVE** (n=100–400 depending on sample) | "What is the under-five mortality rate in Nigeria in 2023?" — known-real query | EQA = Extraction × Year × Value Accuracy. Ground truth is the SDMX API value at run time. |
| **HALLUCINATION_T1** (gap-year, n=100–200) | "What is the value for indicator-X in country-Y in year-Z" where the indicator-country pair has data but not for year Z | Did the model fabricate a number for a year that doesn't exist? |
| **HALLUCINATION_T2** (forward-of-frontier, n=100–200) | Same as T1 but year is past the data frontier (e.g. 2027 when data ends 2024) | Did the model produce a future-year value? |

Two conditions per query: **A** (LLM alone, no tools) vs **B** (LLM
with `unicefstats-mcp` tools). The benchmark compares the two.

The metric is **EQA = Extraction Rate × Year Accuracy × Value
Accuracy** — multiplicative O-ring structure where failure on any
component collapses the result. See [`RESULTS.md`](RESULTS.md) §1
for the full metric definition.

## Quick start (fresh clone, end-to-end)

```bash
# 1. Clone the repo
git clone https://github.com/jpazvd/unicefstats-mcp-dev.git
cd unicefstats-mcp-dev

# 2. Install editable + all benchmark dependencies
pip install -e ".[benchmark]"
# This installs: fastmcp, unicefdata, pyyaml (runtime); plus
# anthropic, python-dotenv, pandas, pyarrow, numpy, matplotlib,
# scipy (benchmark extras).

# 3. Set the only required secret
export ANTHROPIC_API_KEY=sk-ant-...
# (or put it in a .env file — load_dotenv() picks it up)

# 4. Run the smallest benchmark variant (~$2, ~10 min)
#    — uses the existing mcp060 ground truth, n=500
python examples/benchmark_eqa_batch.py \
    --ground-truth examples/ground_truth_mcp060/sample.csv \
    --tag my_first_run

# 5. View the headline numbers
cat examples/results/eqa_*_my_first_run.json
```

If step 4 succeeds, you have:

- A parquet file with all per-query data: `examples/results/eqa_<model>_<ts>_my_first_run.parquet`
- A CSV view of the same: `eqa_..._my_first_run.csv`
- A JSON summary with mean EQA and hallucination rates: `eqa_..._my_first_run.json`

For the analysis pipeline (cross-version tables and figures):

```bash
pip install -r analysis/requirements.txt
python -m analysis.cross_version_analysis
```

## File map — what each script does

### Setup

| Script | Purpose | When you run it |
|---|---|---|
| [`00_build_ground_truth.py`](00_build_ground_truth.py) | Generate ground truth from UNICEF SDMX API. Picks indicators × countries, calls SDMX, writes `sample.csv` + `ground_truth_values.csv`. | First time, or when adding new indicators/countries. |
| [`04_replication_sample.py`](04_replication_sample.py) | Build a *replication* ground truth (different countries, zero overlap with the original) for R2. | When you want a sample-independence test like R1+R2 in `RESULTS.md`. |
| [`06_mcp060_sample.py`](06_mcp060_sample.py) | Build the v0.6.0+ canonical sample (mcp060). | Already-built sample is in `examples/ground_truth_mcp060/`; only re-run if you change the sample design. |

### Run the benchmark

| Script | Purpose | Cost (n=500) | Time |
|---|---|---|---|
| [`benchmark_eqa.py`](benchmark_eqa.py) | Live (sync) benchmark. Submits queries one at a time. Best for development; expensive at scale. | ~$15 | ~30 min |
| [`benchmark_eqa_batch.py`](benchmark_eqa_batch.py) | **Recommended.** Uses Anthropic's Message Batches API (50% discount). Wave-batches multi-turn tool use. Per-wave checkpoint architecture (PR #53) so a crash is recoverable. | ~$10 | ~30–90 min wall-clock; up to 24 h if Anthropic is busy |
| [`benchmark_live.py`](benchmark_live.py) | Older sync variant kept for archaeology. Use `benchmark_eqa.py` instead. | n/a | n/a |
| [`02_run_sdmx_mcp_benchmark.py`](02_run_sdmx_mcp_benchmark.py) | 3-way comparison: LLM alone vs unicefstats-mcp vs `sdmx-mcp` (generic SDMX). | ~$30 | ~1 h |

### Recover from crashes

| Script | Purpose | When you need it |
|---|---|---|
| [`resume_batch_run.py`](resume_batch_run.py) | Resume a crashed `benchmark_eqa_batch.py` run from its checkpoint. Use `--load-state` flag (PR #53) to skip live tool re-dispatch. | If `benchmark_eqa_batch.py` died mid-wave. |
| [`salvage_batches.py`](salvage_batches.py) | Rebuild a parquet from already-completed Anthropic batches (without re-spending money). | If checkpoint is gone but you have batch IDs from a prior run. Anthropic keeps batch results retrievable for ~29 days. |
| [`reconstruct_batch_run.py`](reconstruct_batch_run.py) | Older reconstruction path. Superseded by `resume_batch_run.py --load-state`. | Archaeology only. |

### Score and analyse

| Script | Purpose |
|---|---|
| [`refined_extractor.py`](refined_extractor.py) | The canonical hallucination classifier (true_fab / fallback / substitution / clean_refusal / unknown). |
| [`compare_pilot_versions.py`](compare_pilot_versions.py) | Helpers built on top of `refined_extractor`: per-DataFrame classification, country-correctness checks, etc. |
| [`statistical_analysis.py`](statistical_analysis.py) | Wilcoxon, bootstrap CI, McNemar tests on benchmark results. Produces the statistical-significance numbers cited in the LinkedIn series. |
| [`plot_results.py`](plot_results.py) | Renders the per-indicator and per-condition matplotlib figures. |
| [`benchmark.py`](benchmark.py) | Catch-all utilities for metric computation; imported by other scripts. |
| [`benchmark.ipynb`](benchmark.ipynb) | Jupyter notebook for interactive exploration of benchmark results. Not required for headless replication. |
| [`03_rerun_condition_b.py`](03_rerun_condition_b.py) | Re-run only Condition B (LLM + MCP) on an existing parquet. Useful when you want to test a new MCP version without re-paying for Condition A. |
| [`01_run_direct_supplement.py`](01_run_direct_supplement.py) | Add 100 direct-prompt queries to an existing run. |

The cross-version analysis (`analysis/cross_version_analysis.py`) is
documented separately in [`../analysis/README.md`](../analysis/README.md).

## Required environment

### Python

- Python ≥ 3.10 (declared in `pyproject.toml`).
- Editable install of this repo: `pip install -e ".[benchmark]"`.

The `[benchmark]` extra installs all third-party deps the scripts
need: `anthropic`, `python-dotenv`, `pandas`, `pyarrow`, `numpy`,
`matplotlib`, `scipy`. The base install (no extras) covers the
runtime MCP server but is *not enough* to run the benchmark — extras
are required.

### Secrets

Only one is mandatory:

| Variable | Where to get it | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | <https://console.anthropic.com/settings/keys> | All `benchmark_eqa*.py` and `02_run_sdmx_mcp_benchmark.py` |

Set in shell or in a `.env` file at repo root (`.env` is gitignored).

The benchmark does NOT use OpenAI or any other LLM provider keys —
the harness is Anthropic-only today (see parking-lot Item 5 in
`internal/PARKED_post_v0_7_review_concerns.md` for the
cross-provider survey deferred to v0.8.0+).

### Data dependencies

All input data is tracked in regular git (not LFS). A fresh clone
gives you:

```
examples/ground_truth_mcp060/   ← 500-query mcp060 sample (used by R3 in RESULTS.md)
  sample.csv                    ← 500 query specs
  ground_truth_values.csv       ← canonical answers
  query_universe.csv            ← all candidate queries before sampling
  metadata.json                 ← sample metadata (seed, indicators, countries)

examples/ground_truth_r2/       ← 600-query R2 replication sample
  (same four files)
```

You do NOT need to re-run `00_build_ground_truth.py` to use these.
Only re-run if you want to extend or modify the sample design.

### Output / run artefacts

Run artefacts go to `examples/results/`:

```
examples/results/
  eqa_<model>_<timestamp>_<tag>.parquet       ← all per-query data (LFS, dev-only)
  eqa_<model>_<timestamp>_<tag>.csv           ← human-readable view (LFS, dev-only)
  eqa_<model>_<timestamp>_<tag>.json          ← summary metrics (regular git, public)
  eqa_<model>_<timestamp>_<tag>.checkpoint.json  ← per-wave checkpoint (LFS, dev-only)
```

**Storage convention:**

- `*.parquet` and `*.csv` files are tracked in **Git LFS** (per
  `.gitattributes`) and are excluded from the public-mirror sync.
- `*.json` summaries stay in regular git and DO sync to public —
  they're small (~1 KB each) and carry the headline numbers a
  public visitor would care about.
- `*.checkpoint.json` files are dev-only (their content includes
  intermediate state and tool-call args; not for public).

If you clone the **public** mirror, you get the JSON summaries but
not the raw parquets. To get the raw data, clone the dev repo or
re-run the benchmark.

## Common workflows

### "I want to test a new MCP server version"

```bash
# 1. Run v0.6.4 baseline same-day (controls for upstream model drift)
git stash
git checkout v0.6.4
pip install -e ".[benchmark]"
python examples/benchmark_eqa_batch.py \
    --ground-truth examples/ground_truth_mcp060/sample.csv \
    --tag baseline_v064_$(date +%Y%m%d)

# 2. Switch back to your branch and run the new version
git stash pop  # or `git checkout your-branch`
pip install -e ".[benchmark]"  # reinstall with your new src/
python examples/benchmark_eqa_batch.py \
    --ground-truth examples/ground_truth_mcp060/sample.csv \
    --tag mybranch_$(date +%Y%m%d)

# 3. Compare A-side EQA. If within 0.3 pp, your B-side delta is
#    real; if A-side drifted >2 pp, model snapshot drifted between
#    runs and you need to re-run baseline same-day.
```

This is the **same-day discipline** that produced the v0.7.2
clean-baseline numbers in `RESULTS.md` §9. It's the only way to
attribute a B-side delta to your code change vs. upstream model
drift. The cost: you pay for two runs (~$20 instead of $10), but
the result is interpretable.

See `internal/PARKED_post_v0_7_review_concerns.md` and
`analysis/CROSS_VERSION_ANALYSIS.md` Part D for the full
methodological argument.

### "I want to extend the benchmark to new indicators"

```bash
# 1. Edit examples/00_build_ground_truth.py (or 06_mcp060_sample.py)
#    to add the new indicators. Both scripts have an INDICATORS list
#    near the top.

# 2. Build the new ground truth
python examples/00_build_ground_truth.py

# 3. Verify the new sample
python -c "
import pandas as pd
gt = pd.read_csv('examples/ground_truth_mcp060/sample.csv')
print(gt.groupby('indicator_code').size())
"

# 4. Run benchmark against new sample
python examples/benchmark_eqa_batch.py \
    --ground-truth examples/ground_truth_mcp060/sample.csv \
    --tag extended_$(date +%Y%m%d)
```

### "I want to recover a crashed run"

```bash
# Option A: Resume from checkpoint (preferred)
python examples/resume_batch_run.py \
    --load-state examples/results/eqa_..._<tag>.checkpoint.json \
    --ground-truth examples/ground_truth_mcp060/sample.csv \
    --tag <same-tag>

# Option B: Salvage from Anthropic batch IDs (if checkpoint is lost)
python examples/salvage_batches.py \
    --ground-truth examples/ground_truth_mcp060/sample.csv \
    --tag <new-tag>_salvaged \
    --batch-ids msgbatch_aaa,msgbatch_bbb,...
```

If alignment after salvage is poor (<95% of B-side responses
mention the row's target country), the salvage approach is
unreliable — re-run the benchmark from scratch instead. See
`internal/BUG_resume_batch_row_alignment.md` for the failure mode.

## Cost and time

For an n=500 benchmark on Claude Sonnet 4 with the batch API:

| Phase | Cost | Wall-clock |
|---|---|---|
| Anthropic API (1000 messages × 4–5 rounds) | ~$10 | depends on Anthropic queue (typically 30–90 min/wave; up to 24 h SLA) |
| SDMX API calls (free; UNICEF Data Warehouse) | $0 | embedded in tool dispatch; ~30 sec per query |
| Local compute (scoring, parquet write) | $0 | ~5 min |

For a paired same-day v0.6.x vs v0.7.x A/B (the canonical "did my
change work" pattern), double the API cost (~$20) and run both
batches in parallel — the wall-clock is the longer of the two.

## Cost optimisation: batch vs live

Why `benchmark_eqa_batch.py` is the recommended path and how the
cost savings actually work — useful when planning a budget for a
new run or deciding whether sync is acceptable for a development
loop.

### The 50% Anthropic batch discount

Anthropic's [Message Batches API](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing)
charges a flat 50% of the standard rate on **both input and output
tokens** (and on cache-creation / cache-read tokens too). For an
n=500 benchmark with mean 11,408 input tokens × ~5 rounds, the
arithmetic is:

| Mode | Per-query input cost | Per-query output cost | Total (n=500) |
|---|---|---|---|
| Sync (`benchmark_eqa.py`) | ~$0.029 | ~$0.005 | **~$15** |
| Batch (`benchmark_eqa_batch.py`) | ~$0.014 | ~$0.0025 | **~$10** |

The discount is real money at scale. For one same-day v0.6.4 vs
v0.7.x A/B (the canonical "did my change work" pattern), batch
saves ~$10 over sync.

### Wave-batching for multi-turn tool use

The naïve Batch API submits one prompt and waits for one response.
Our queries are 4–5 rounds of `tools/call` interleaved with
`tool_results`, so a single batch request can't capture the whole
conversation. The harness solves this with **wave-batching**:

```
Wave 1: 1000 user prompts → batch returns 1000 first-turn responses
Local : dispatch tool calls against unicefstats_mcp.server
Wave 2: 500 messages (turn-1 response + tool_results) → batch returns turn-2
Wave 3: 250 (queries still emitting tool_use blocks) → ...
... up to MAX_WAVES = 8
```

Two consequences worth knowing:

1. **Each wave gets the 50% discount independently.** All N waves
   are batched, all N enjoy the rebate. Wave-batching does not
   forfeit the discount.
2. **Convergence is fast.** Most queries finish in 2–3 rounds —
   the model gets its data and writes a final response. Later
   waves are progressively smaller (fewer pending queries),
   which keeps total cost close to the n=500 baseline rather
   than n × MAX_WAVES.

The mean B-side rounds in our benchmarks is **4.21–4.56** per
query (v0.7.2 vs v0.6.4 same-day clean), with ~12% of queries
hitting MAX_WAVES = 8 without converging. The MAX_WAVES cap is
the only safety brake against pathological loops; tune it via
the constant in `benchmark_eqa_batch.py:MAX_WAVES`.

### When sync is the right call

`benchmark_eqa.py` (the sync variant) is **not** strictly worse
than batch — the trade-off is wall-clock vs cost:

| Use case | Recommend | Why |
|---|---|---|
| Production benchmark (n ≥ 50) | **Batch** | 50% discount; you can wait 30–90 min for results |
| Development loop, single query | **Sync** | See a response in seconds; debug a misbehaving prompt without batching ceremony |
| Testing a new tool/server change on n=5 | **Sync** | The discount on $0.10 isn't worth the wall-clock |
| Crash recovery on a partial run | **Batch resume** | `resume_batch_run.py --load-state` keeps the discount; no need to re-pay for completed waves |
| Salvage from already-completed batches | **Salvage** | $0 — batch results stay retrievable for ~29 days post-completion |

### Per-wave checkpoint as cost insurance

Anthropic's batch SLA is 24 h. In practice waves complete in
10–60 min, but during incident windows a wave can time out or
return partial errors. Without checkpointing, a 5-wave run that
died on wave 4 would cost ~5× to recover from scratch. With the
**per-wave checkpoint architecture** (PR #53):

- After each wave completes, the harness writes
  `eqa_<run_id>.checkpoint.json` next to the parquet.
- If the run dies mid-flight, `resume_batch_run.py --load-state
  <checkpoint>` picks up at the next pending wave — without
  re-dispatching tools (which was the bug class fixed in PR #53)
  and without re-paying for completed waves.
- If Anthropic returns batch results but the local script crashed
  before scoring, `salvage_batches.py --batch-ids <ids>` rebuilds
  the parquet at $0 cost (re-fetching batch results is free).

The checkpoint architecture turns "expensive cascading failure"
into "re-submit the failed wave." For the v0.7.2 same-day clean
run we did Tuesday (2026-05-08), this was load-bearing — wave 5
hit a transient SDMX outage during scoring; we recovered without
re-spending API credits.

### Worked example: v0.7.2 same-day clean (2026-05-08)

The actual numbers from our most recent run, for calibration:

| Run | n | Waves | Mean rounds | Wall-clock | Cost |
|---|---|---|---|---|---|
| v0.6.4 baseline | 500 | 8 (cap) | 4.56 | 3.8 h | ~$10 |
| v0.7.x current | 500 | 8 (cap) | 4.21 | 9.2 h | ~$10 |
| **A/B total** | 1000 | — | — | **9.2 h parallel** | **~$20** |

Both runs hit MAX_WAVES = 8 (the convergence cap), meaning ~12%
of queries didn't fully resolve in 8 rounds. The wall-clock
asymmetry (3.8 h vs 9.2 h) was upstream queue depth at Anthropic,
not a code-side property — the v0.7.x run launched ~26 min later
and hit a busier batch queue. Total spend matched expectation:
~$10 per run × 2 runs = ~$20 for the A/B.

The full run-summary JSONs are in `examples/results/` (the only
files that sync to public; raw parquets stay in -dev per
`.gitattributes`):

- `eqa_claude-sonnet-4-20250514_20260506_172421_sameday_v071.json`
- `eqa_claude-sonnet-4-20250514_20260506_233553_sameday_v064.json`

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'scipy'` | `[benchmark]` extra not installed (or installed before this CHANGELOG entry's pyproject.toml fix landed) | `pip install -e ".[benchmark]"` |
| `Indicator '...' not found in any dataflow` from `unicefdata` | Indicator code may have moved between dataflows; SDMX upstream change | Run with `dataflow="GLOBAL_DATAFLOW"` (see `feedback_unicefdata_r_global_dataflow_workaround.md`) |
| Benchmark hangs at "WAVE N (X pending queries)" | Anthropic batch API queue depth | Check <https://status.anthropic.com>; the per-wave SLA is 24 h. |
| `Indicator 'under-5 mortality' not found` | Resolver synonym-table gap (the hyphen variant isn't in `_SYNONYMS`) | Use `"under five mortality"` (no hyphen) or pass the canonical code `CME_MRY0T4` |
| Resume produces row-misaligned parquet | Pre-PR-53 bug; live tool re-dispatch races with the original wave | Use `resume_batch_run.py --load-state` (the checkpoint path); never the legacy `--batch-ids` path |
| 502/504 errors during scoring | Transient SDMX API outage during `_extract_from_tool_calls` re-dispatch | Re-run scoring after SDMX recovers; values are recoverable on fresh dispatch |

## Reproducibility checklist (before publishing benchmark numbers)

- [ ] Same-day baseline. If comparing version A vs version B, both runs ran on the same calendar day, same model snapshot.
- [ ] A-side EQA within 0.3 pp across the two runs (confirms model snapshot didn't drift).
- [ ] Ground-truth `metadata.json` checked into git so the indicators/countries/year-range are preserved.
- [ ] Run summary JSON committed to git so the headline numbers are versioned with the code.
- [ ] Raw parquet/csv preserved (in dev-repo LFS or local backup). For public reproducibility, share the run-summary JSON; the raw data can be regenerated by anyone with $10 of Anthropic credits.
- [ ] Cited version is the current one, not a pre-release tag (per Option C labelling — see `CHANGELOG.md` headers).
- [ ] If hallucination numbers are claimed, the safety stack (v0.4.0 system prompt + v0.5.0 anti-extrapolation + v0.7.0 indicator resolver) is loaded. See README §Hallucination risks.

## Citation

If you use this benchmark in research:

```
Azevedo, J.P. (2025). "AI Reliability for Official Statistics:
Benchmarking Large Language Models with the UNICEF Data Warehouse."
UNICEF Chief Statistician Office.
https://github.com/jpazvd/unicefstats-mcp/blob/main/examples/RESULTS.md
```

Independent research — not an official UNICEF product.
