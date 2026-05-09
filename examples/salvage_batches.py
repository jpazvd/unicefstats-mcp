#!/usr/bin/env python3
"""Salvage a parquet from already-completed Anthropic batch results.

Use case: an EQA benchmark crashed mid-flight, the legacy
`resume_batch_run.py --batch-ids` path produced a row-misaligned parquet
(see `internal/BUG_resume_batch_row_alignment.md`), but the underlying
batch results are still on Anthropic's side and keyed correctly by
`custom_id`. This script rebuilds the parquet directly from those
batches WITHOUT live tool re-dispatch — bypassing the divergence
source that caused the misalignment.

Differences vs `resume_batch_run.py`:

  * No `dispatch_tool` calls. We don't need tool *results* for scoring
    (we only need the model's final response text + the list of tool
    calls it made). The legacy resume re-dispatched live, and the
    drift between original and re-dispatch results corrupted state.
  * No `state.messages` reconstruction. Salvage doesn't continue with
    new waves — it only scores what already exists.
  * No checkpoint dependency. Works on any batch-IDs from any prior
    run, including pre-checkpoint runs.

Cost: $0 (re-fetching batch results is free; results stay retrievable
for ~29 days post-completion).

Usage:
    python examples/salvage_batches.py \\
        --ground-truth examples/ground_truth_mcp060/sample.csv \\
        --tag mcp070_salvaged \\
        --batch-ids msgbatch_aaa,msgbatch_bbb,...

If alignment after salvage is poor (<95% of B-side responses mention
the row's target country), the live-re-dispatch hypothesis is wrong
and the bug is elsewhere — re-running the benchmark from scratch is
the safe fallback.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import anthropic  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from benchmark_eqa import (  # noqa: E402
    DEFAULT_MODEL,
    load_sample,
)
from benchmark_eqa_batch import (  # noqa: E402
    QueryState,
)
from resume_batch_run import (  # noqa: E402
    _fetch_batch_results_with_retry,
    score_and_serialise,
)


def replay_without_dispatch(client, batch_id, states_by_id) -> tuple[int, int]:
    """Replay one already-completed batch WITHOUT live tool re-dispatch.

    Updates state.final_text, state.tool_calls, state.tokens_*, state.rounds,
    state.done. Does NOT update state.messages — this script doesn't continue
    with new waves, so messages history doesn't need to be reconstructed.

    Returns (n_processed, n_errored).
    """
    n_proc = 0
    n_err = 0
    results = _fetch_batch_results_with_retry(client, batch_id)
    for entry in results:
        cid = entry.custom_id
        state = states_by_id.get(cid)
        if state is None:
            continue  # batch result for a custom_id we don't know about
        # NOTE: unlike the legacy replay_existing_wave, we do NOT skip done
        # states here. A later wave's response is the canonical "final"
        # answer for that query; let it overwrite earlier waves' final_text.
        # state.done is only meaningful for "should we submit another wave"
        # logic, which salvage doesn't run.

        result = entry.result
        if result.type == "errored":
            err = result.error
            state.final_text = f"[batch error: {getattr(err, 'type', '?')}]"
            state.done = True
            n_err += 1
            continue
        if result.type != "succeeded":
            state.done = True
            continue

        msg = result.message
        usage = msg.usage
        state.tokens_input += usage.input_tokens
        state.tokens_output += usage.output_tokens
        state.cache_creation += getattr(usage, "cache_creation_input_tokens", 0) or 0
        state.cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0
        state.rounds += 1
        n_proc += 1

        if state.condition == "A":
            # A-side: no tools, single-turn — final_text is the response.
            text_blocks = [b.text for b in msg.content if hasattr(b, "text")]
            state.final_text = "\n".join(text_blocks)
            state.done = True
            continue

        tool_uses = [b for b in msg.content if b.type == "tool_use"]

        # Record tool calls for scoring (extracts values from get_data calls).
        # We do NOT dispatch them — that's the bug that misaligned rows in
        # the legacy resume path.
        for tu in tool_uses:
            state.tool_calls.append({"tool": tu.name, "input": tu.input})

        # Update final_text from this wave's text blocks. The model's
        # terminal response is the wave with no tool_uses; intermediate
        # waves may also have text alongside tool_uses, which is captured
        # here (and overwritten by the next wave if there is one).
        text_blocks = [b.text for b in msg.content if hasattr(b, "text")]
        if text_blocks:
            state.final_text = "\n".join(text_blocks)

        if not tool_uses:
            state.done = True

    return n_proc, n_err


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--batch-ids",
        required=True,
        help="Comma-separated batch IDs in wave order (oldest first).",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip _extract_from_tool_calls live re-dispatch during scoring. "
             "Falls back to text-based extraction. ~100x faster for alignment "
             "verification; values may be slightly less accurate (model rounds "
             "in prose). Recommended for first pass; re-run without --fast to "
             "get final scoring once alignment is confirmed good.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    if args.fast:
        # Monkey-patch _extract_from_tool_calls so scoring uses text-only
        # extraction. Score_and_serialise checks `if tool_value is not None
        # else b_text_value` — returning (None, None) forces the text path.
        import benchmark_eqa as _be
        _be._extract_from_tool_calls = lambda tool_calls: (None, None)
        # Re-import the resume-side reference so it picks up the patched fn.
        # (resume_batch_run.py imports _extract_from_tool_calls at module
        # load; the patch replaces it on the benchmark_eqa module, but
        # resume_batch_run holds the old reference.)
        import resume_batch_run as _rb
        _rb._extract_from_tool_calls = lambda tool_calls: (None, None)
        print("[--fast] Skipping live tool re-dispatch; text-based extraction.",
              flush=True)

    # line_buffering=True so progress prints land in stdout immediately even
    # when this script is run with output captured to a file.
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

    import benchmark_eqa
    benchmark_eqa.SAMPLE_CSV = args.ground_truth
    benchmark_eqa.GT_VALUES_CSV = os.path.join(
        os.path.dirname(args.ground_truth), "ground_truth_values.csv"
    )

    # Use the canonical helper from benchmark_eqa rather than reimplementing
    # the pos+T1+T2 reorder. See load_sample_in_benchmark_order's docstring
    # for the historical bug this prevents.
    from benchmark_eqa import load_sample_in_benchmark_order
    cases = load_sample_in_benchmark_order()
    pos_n = sum(1 for c in cases if c.query_type == "POSITIVE")
    t1_n = sum(1 for c in cases if c.query_type == "HALLUCINATION_T1")
    t2_n = sum(1 for c in cases if c.query_type == "HALLUCINATION_T2")
    print(f"Loaded {len(cases)} test cases ({pos_n} POS + {t1_n} T1 + {t2_n} T2)")

    states_by_id: dict[str, QueryState] = {}
    for idx, tc in enumerate(cases):
        for cond in ("A", "B"):
            s = QueryState(idx, tc, cond)
            states_by_id[s.custom_id] = s

    client = anthropic.Anthropic()
    batch_ids = [b.strip() for b in args.batch_ids.split(",") if b.strip()]
    print(f"\nSalvaging from {len(batch_ids)} batch(es)...")
    for i, batch_id in enumerate(batch_ids, 1):
        print(f"\nWave {i}: {batch_id}")
        n_proc, n_err = replay_without_dispatch(client, batch_id, states_by_id)
        n_done = sum(1 for s in states_by_id.values() if s.done)
        print(
            f"  Processed: {n_proc}  Errors: {n_err}  "
            f"Total done: {n_done}/{len(states_by_id)}"
        )

    n_unfinished = sum(1 for s in states_by_id.values() if not s.done)
    n_with_text = sum(1 for s in states_by_id.values() if s.final_text)
    print(f"\nFinal state: {n_unfinished} unfinished, {n_with_text} have final_text")

    # Score using the existing helper (same shape as the legacy resume
    # output, so downstream analysis tooling reads it identically).
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_slug = args.model.replace("/", "_").replace(":", "_")
    run_id = f"{model_slug}_{ts}_{args.tag}"
    df = score_and_serialise(states_by_id, cases, args.model, run_id, ts)
    print(f"\nScored {len(df)} queries")

    # Quick alignment check — does the B-side response mention the row's
    # target country name? Compares against the v0.6.4 baseline of 98.8%.
    def _aligned(row) -> bool:
        cn = (row.get("country_name") or "").split()[:1]
        if not cn:
            return False
        first_word = cn[0].lower()
        resp = (row.get("b_response_full") or "").lower()
        return first_word in resp

    df_with_resp = df[df["b_response_full"].notna() & (df["b_response_full"] != "")]
    if len(df_with_resp) > 0:
        align_rate = df_with_resp.apply(_aligned, axis=1).mean()
        print(
            f"\nB-side alignment check: {align_rate * 100:.1f}% of "
            f"{len(df_with_resp)} responses mention the target country "
            f"(v0.6.4 baseline: 98.8%)"
        )
        if align_rate < 0.85:
            print(
                "  WARNING: alignment below 85%. The live-re-dispatch "
                "hypothesis may be wrong; consider re-running benchmark "
                "from scratch instead of trusting these numbers.",
                flush=True,
            )

    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    pq = os.path.join(out_dir, f"eqa_{run_id}.parquet")
    csv = os.path.join(out_dir, f"eqa_{run_id}.csv")
    js = os.path.join(out_dir, f"eqa_{run_id}.json")
    df.to_parquet(pq, index=False, engine="pyarrow")
    df.to_csv(csv, index=False)

    summary = {
        "run_id": run_id,
        "model": args.model,
        "n_queries": len(df),
        "ground_truth_source": args.ground_truth,
        "batch_ids_used": batch_ids,
        "salvage": True,
        "queries_unfinished": n_unfinished,
    }
    if len(df) > 0:
        pos = df[df["query_type"] == "POSITIVE"]
        if len(pos) > 0:
            summary["positive_metrics"] = {
                "n": len(pos),
                "mean_eqa_a": round(float(pos["eqa_a"].mean()), 4),
                "mean_eqa_b": round(float(pos["eqa_b"].mean()), 4),
            }
        hall = df[df["query_type"].isin(["HALLUCINATION_T1", "HALLUCINATION_T2"])]
        if len(hall) > 0:
            summary["hallucination_metrics"] = {
                "n": len(hall),
                "rate_a": round(float(hall["hall_a"].mean()), 4),
                "rate_b": round(float(hall["hall_b"].mean()), 4),
            }

    with open(js, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nWrote {pq}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
