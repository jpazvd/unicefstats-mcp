# TAINTED — v0.7.3 pre-fix benchmark artifacts

**DO NOT USE THESE FILES FOR ANALYSIS, REPORTS, OR DOWNSTREAM TABLES.**

## Why these are tainted

These artifacts were produced by the v0.7.3 release-prep MCP code **before**
commit `01fe6cb` ("fix(server): seed_data_frontier_cache must not lower the
cached frontier") was applied. The pre-fix `_seed_data_frontier_cache()` in
`8e073a1` unconditionally overwrote the per-session frontier cache with
`df["period"].max()` of the response. Because `df` is filtered by
`start_year`/`end_year`/country list, that max reflects "max year present in
the bounded slice the user asked for" — not the indicator's true frontier.

In benchmark sessions where many queries share one MCP process, a single
year-bounded query early in the session permanently poisoned the cache for
any later query whose true year exceeded the bounded slice. This caused the
v0.6.0 anti-extrapolation refusal at `server.py:782` to fire on phantom-low
frontiers, refusing valid queries with "Year YYYY exceeds the data frontier".

The headline impact in this run:

  | Metric          | v0.7.1 baseline | v0.7.3 pre-fix (these files) |
  |-----------------|----------------:|-----------------------------:|
  | POS EQA_b       | 0.8000          | 0.6388                       |
  | POS refused_b   | 1%              | 14%                          |
  | Hallucination_b | 13%             | 3%                           |

About 16 of 100 POSITIVE queries flipped from EQA>0.5 → EQA<0.5 in this
run **purely** due to the cache-contamination bug — not from any real
model or MCP behavior change. See `internal/v0_7_3_validation.md` for the
full investigation.

## What to use instead

After the post-fix re-run completes (run id
`claude-sonnet-4-20250514_20260509_213327_v073_postfix_n500`), the clean
artifacts will appear at `examples/results/eqa_*_213327_v073_postfix_n500.*`
and `analysis/registry.py` will be updated to point at them.

Until then:
- For **v0.7.x EQA reporting**, treat v0.7.3 as "pending re-validation".
- For **v0.6.x and v0.7.0–v0.7.2 numbers**, those runs are unaffected (the
  buggy `_seed_data_frontier_cache` did not exist in those versions). See
  `internal/v0_7_3_validation.md` §"What this proves" for the version
  matrix.

## Files in this directory

  | File pattern                                  | Description |
  |-----------------------------------------------|-------------|
  | `eqa_*_162442_smoke_v073.{csv,json,parquet}` | n=9 smoke test |
  | `eqa_*_163731_v073_full_n500.checkpoint.json` | first n=500 attempt; aborted partial |
  | `eqa_*_172059_v073_full_n500_retry.{csv,json,parquet,checkpoint.json}` | n=500 retry; the file most likely to be referenced downstream |

## Why kept on disk rather than deleted

Audit trail. Anyone reproducing the pre-fix → post-fix delta (Δ POS EQA ≈
+0.16 expected) will need both versions side-by-side to verify the cache
fix actually recovers the right queries.
