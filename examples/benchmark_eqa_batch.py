#!/usr/bin/env python3
"""EQA benchmark — batched version using Anthropic Message Batches API.

Same experiment as benchmark_eqa.py (LLM alone vs LLM+MCP, scored by ER×YA×VA),
but submits all queries via the Batch API for a flat 50% discount on input
and output tokens. Tool-use multi-turn is implemented as "wave batching":

    Wave 1: 500 user prompts → batch returns 500 first-turn responses
    Local : dispatch tool calls against unicefstats_mcp.server
    Wave 2: 500 messages (turn-1 response + tool_results) → batch returns turn-2
    Wave 3+: repeat for queries still emitting tool_use blocks (max 5 rounds)
    Final : extract values, compute EQA, write parquet/CSV/JSON

Wall-clock: dominated by batch SLA (10 min – 24 h per wave). Cost: ~$0.014/q
on v0.6.0 (vs $0.028/q sync).

Usage:
    python examples/benchmark_eqa_batch.py \\
        --ground-truth examples/ground_truth_mcp060/sample.csv \\
        --tag mcp060_full

Output schema matches benchmark_eqa.py exactly (drop-in replacement for
downstream analysis).
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import time
import warnings
from dataclasses import asdict
from datetime import datetime, timezone

warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.disable(logging.INFO)

from dotenv import load_dotenv
load_dotenv()

import anthropic
import pandas as pd

# Reuse helpers from the synchronous benchmark.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from benchmark_eqa import (  # noqa: E402
    CONDITION_B_SYSTEM,
    DEFAULT_MODEL,
    EXTRACTOR_VERSION,
    MAX_TOKENS,
    MCP_TOOLS,
    TEMPERATURE,
    TestCase,
    _compute_cost,
    _detect_refusal,
    _extract_from_tool_calls,
    compute_er,
    compute_va,
    compute_ya,
    dispatch_tool,
    extract_numeric,
    extract_year,
    load_sample,
)

BATCH_DISCOUNT = 0.5  # Anthropic Message Batches: 50% off all token rates
MAX_WAVES = 8  # bumped from 5 — v0.6.0 mcp060_full had 243/500 hit the cap
POLL_INTERVAL_SEC = 30  # how often to check batch status


# ---------------------------------------------------------------------------
# Per-query rolling state across waves
# ---------------------------------------------------------------------------


class QueryState:
    """Per-query state that evolves across waves."""

    __slots__ = (
        "query_idx", "tc", "condition",
        "messages", "done", "final_text", "tool_error",
        "tool_calls", "rounds",
        "tokens_input", "tokens_output",
        "cache_creation", "cache_read",
        "first_wave_started_at",
    )

    def __init__(self, query_idx: int, tc: TestCase, condition: str):
        self.query_idx = query_idx
        self.tc = tc
        self.condition = condition  # "A" or "B"
        self.messages: list[dict] = [{"role": "user", "content": tc.prompt_text}]
        self.done = False
        self.final_text = ""
        self.tool_error = None
        self.tool_calls: list[dict] = []
        self.rounds = 0
        self.tokens_input = 0
        self.tokens_output = 0
        self.cache_creation = 0
        self.cache_read = 0
        self.first_wave_started_at = None

    @property
    def custom_id(self) -> str:
        return f"q{self.query_idx:04d}_{self.condition}"


# ---------------------------------------------------------------------------
# Checkpoint serialization
# ---------------------------------------------------------------------------
#
# Persisting per-wave state to disk lets `resume_batch_run.py --load-state`
# skip the live `dispatch_tool` replay path that caused the row-misalignment
# bug documented in `internal/BUG_resume_batch_row_alignment.md`. The
# checkpoint is the source of truth for the resume; the original Anthropic
# batches still need to exist (so newly-submitted continuation waves can
# finish), but their results are NOT re-fetched or re-dispatched.
#
# Schema is bumped if the dict shape changes incompatibly. v1 = the v0.7.2
# era — query_idx + condition are the lookup keys (TestCase reconstructed
# from cases at load time).

CHECKPOINT_SCHEMA_VERSION = 1


def state_to_dict(state: QueryState) -> dict:
    """Serialise a QueryState to a JSON-safe dict.

    `tc` is intentionally NOT serialised — it's reconstructed from the
    same `load_sample()` call at load time using `query_idx`. This keeps
    checkpoints small and ensures the test case is always sourced from
    the canonical CSV rather than a frozen-in-time copy.
    """
    return {
        "query_idx": state.query_idx,
        "condition": state.condition,
        "messages": state.messages,
        "done": state.done,
        "final_text": state.final_text,
        "tool_error": state.tool_error,
        "tool_calls": state.tool_calls,
        "rounds": state.rounds,
        "tokens_input": state.tokens_input,
        "tokens_output": state.tokens_output,
        "cache_creation": state.cache_creation,
        "cache_read": state.cache_read,
        "first_wave_started_at": state.first_wave_started_at,
    }


def state_from_dict(d: dict, tc: TestCase) -> QueryState:
    """Reconstruct a QueryState from a checkpoint dict + the matching TestCase."""
    state = QueryState(d["query_idx"], tc, d["condition"])
    state.messages = d.get("messages", [])
    state.done = d.get("done", False)
    state.final_text = d.get("final_text", "")
    state.tool_error = d.get("tool_error")
    state.tool_calls = d.get("tool_calls", [])
    state.rounds = d.get("rounds", 0)
    state.tokens_input = d.get("tokens_input", 0)
    state.tokens_output = d.get("tokens_output", 0)
    state.cache_creation = d.get("cache_creation", 0)
    state.cache_read = d.get("cache_read", 0)
    state.first_wave_started_at = d.get("first_wave_started_at")
    return state


def save_checkpoint(
    states_by_id: dict[str, QueryState],
    path: str,
    batch_ids: list[str],
) -> None:
    """Atomically write a checkpoint snapshot.

    Writes to `<path>.tmp` first then renames over the target — survives
    a crash mid-write without leaving a half-written file that would
    poison the next resume.
    """
    payload = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "batch_ids": batch_ids,
        "n_states": len(states_by_id),
        "states": [state_to_dict(s) for s in states_by_id.values()],
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, default=str)
    os.replace(tmp, path)


def load_checkpoint(
    path: str,
    cases: list[TestCase],
) -> tuple[dict[str, QueryState], list[str]]:
    """Load a checkpoint and reconstruct states_by_id.

    Returns:
      - states_by_id: same shape as a fresh-built dict
      - batch_ids: the batch IDs already submitted at checkpoint time
        (caller can use these to verify against existing Anthropic batches
        if continuing with new waves)

    Raises ValueError if schema is unsupported or `cases` length is
    inconsistent with the checkpoint's referenced indices (which would
    indicate the sample CSV changed between save and load).
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    sv = payload.get("schema_version")
    if sv != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported checkpoint schema_version {sv!r}; "
            f"expected {CHECKPOINT_SCHEMA_VERSION}"
        )
    states_by_id: dict[str, QueryState] = {}
    for d in payload.get("states", []):
        idx = d["query_idx"]
        if idx >= len(cases):
            raise ValueError(
                f"Checkpoint references query_idx={idx} but only "
                f"{len(cases)} test cases loaded — sample CSV likely "
                "changed between save and load."
            )
        state = state_from_dict(d, cases[idx])
        states_by_id[state.custom_id] = state
    return states_by_id, payload.get("batch_ids", [])


# ---------------------------------------------------------------------------
# Wave dispatcher
# ---------------------------------------------------------------------------


def build_batch_request(state: QueryState, model: str) -> dict:
    """Build a single Anthropic Message Batches request entry."""
    if state.condition == "A":
        # LLM alone — no system prompt, no tools
        params = {
            "model": model,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "messages": state.messages,
        }
    else:
        # LLM + MCP — same caching as sync version
        cached_system = [{"type": "text", "text": CONDITION_B_SYSTEM,
                          "cache_control": {"type": "ephemeral"}}]
        cached_tools = list(MCP_TOOLS)
        cached_tools[-1] = {**cached_tools[-1], "cache_control": {"type": "ephemeral"}}
        params = {
            "model": model,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "system": cached_system,
            "tools": cached_tools,
            "messages": state.messages,
        }
    return {
        "custom_id": state.custom_id,
        "params": params,
    }


def submit_wave(client, states_by_id: dict[str, QueryState], model: str) -> str:
    """Submit a batch wave for all not-done queries. Returns batch_id."""
    pending = [s for s in states_by_id.values() if not s.done]
    if not pending:
        return ""
    requests = [build_batch_request(s, model) for s in pending]
    print(f"  Submitting batch with {len(requests)} requests...")
    batch = client.messages.batches.create(requests=requests)
    print(f"  Batch ID: {batch.id}  status: {batch.processing_status}")
    return batch.id


def poll_until_done(client, batch_id: str) -> None:
    """Poll the batch every POLL_INTERVAL_SEC until ended.

    Resilient to transient network errors (DNS, connection reset, etc.) — the
    batch keeps processing on Anthropic's side regardless of whether we can
    reach the API. Retries with exponential backoff for up to 6 attempts
    (~6 minutes) before re-raising.
    """
    import anthropic
    t0 = time.time()
    while True:
        attempt = 0
        backoff = 5.0
        while True:
            try:
                b = client.messages.batches.retrieve(batch_id)
                break
            except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
                attempt += 1
                if attempt > 6:
                    raise
                print(f"  [retry {attempt}/6 after {backoff:.0f}s] poll failed: {type(exc).__name__}", flush=True)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
        elapsed = int(time.time() - t0)
        rc = b.request_counts
        print(
            f"  [{elapsed:>5d}s] status={b.processing_status:<14s}  "
            f"processing={rc.processing}  succeeded={rc.succeeded}  "
            f"errored={rc.errored}  expired={rc.expired}",
            flush=True,
        )
        if b.processing_status == "ended":
            return
        time.sleep(POLL_INTERVAL_SEC)


def _fetch_batch_results(client, batch_id: str, max_attempts: int = 6) -> list:
    """Fetch all results into a list with retry on transient network errors."""
    import anthropic
    attempt = 0
    backoff = 5.0
    while True:
        try:
            return list(client.messages.batches.results(batch_id))
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
            attempt += 1
            if attempt >= max_attempts:
                raise
            print(f"  [retry {attempt}/{max_attempts} after {backoff:.0f}s] results-fetch failed: {type(exc).__name__}", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
        except Exception as exc:
            attempt += 1
            if attempt >= max_attempts:
                raise
            name = type(exc).__name__
            if "Error" not in name and "Exception" not in name:
                raise
            print(f"  [retry {attempt}/{max_attempts} after {backoff:.0f}s] results-fetch failed: {name}", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


def collect_wave_results(client, batch_id: str, states_by_id: dict[str, QueryState]) -> int:
    """Read batch results and update query states. Returns count needing another wave."""
    next_wave_count = 0
    n_errors = 0
    results = _fetch_batch_results(client, batch_id)
    for entry in results:
        cid = entry.custom_id
        state = states_by_id.get(cid)
        if state is None:
            continue
        result = entry.result

        if result.type == "errored":
            err = result.error
            print(f"    {cid}: ERROR {getattr(err, 'type', '?')} — {getattr(err, 'message', '?')[:120]}")
            state.done = True
            state.final_text = f"[batch error: {getattr(err, 'type', '?')}]"
            n_errors += 1
            continue
        if result.type != "succeeded":
            print(f"    {cid}: result.type={result.type}  (treating as done)")
            state.done = True
            continue

        msg = result.message
        # Accumulate token usage
        usage = msg.usage
        state.tokens_input += usage.input_tokens
        state.tokens_output += usage.output_tokens
        state.cache_creation += getattr(usage, "cache_creation_input_tokens", 0) or 0
        state.cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0
        state.rounds += 1

        # Condition A is always single-turn (no tools wired up)
        if state.condition == "A":
            text_blocks = [b.text for b in msg.content if hasattr(b, "text")]
            state.final_text = "\n".join(text_blocks)
            state.done = True
            continue

        # Condition B: check for tool_use blocks
        tool_uses = [b for b in msg.content if b.type == "tool_use"]
        if not tool_uses:
            text_blocks = [b.text for b in msg.content if hasattr(b, "text")]
            state.final_text = "\n".join(text_blocks)
            state.done = True
            continue

        # Dispatch tools locally and append to messages history.
        # Persist the tool result alongside name+input so that
        # `_extract_from_tool_calls` can read the exact value at analysis
        # time without re-invoking the live MCP — see the inverse fix in
        # benchmark_eqa.py. Without persistence, post-run re-dispatch is
        # at the mercy of upstream UNICEF SDMX availability and rate
        # limits, which surfaces as bogus EQA regressions when the
        # benchmark itself is fine.
        tool_results = []
        for tu in tool_uses:
            result_str = dispatch_tool(tu.name, tu.input)
            state.tool_calls.append({"tool": tu.name, "input": tu.input, "result": result_str})
            try:
                parsed = json.loads(result_str)
                if parsed.get("data_status") == "confirmed_absent":
                    state.tool_error = parsed.get("error", "confirmed_absent")
            except (json.JSONDecodeError, AttributeError):
                pass
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result_str,
            })

        # Serialise the assistant content blocks for the next-wave message
        # history. The Anthropic SDK accepts dicts or model objects, but for
        # cross-wave persistence we keep dicts.
        assistant_blocks = []
        for b in msg.content:
            if b.type == "text":
                assistant_blocks.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                assistant_blocks.append({
                    "type": "tool_use",
                    "id": b.id,
                    "name": b.name,
                    "input": b.input,
                })
        state.messages.append({"role": "assistant", "content": assistant_blocks})
        state.messages.append({"role": "user", "content": tool_results})
        next_wave_count += 1

    if n_errors:
        print(f"  Wave finished with {n_errors} errored queries (marked done).")
    return next_wave_count


def run_batch_waves(
    client,
    states_by_id: dict[str, QueryState],
    model: str,
    checkpoint_path: str | None = None,
    initial_batch_ids: list[str] | None = None,
) -> list[str]:
    """Run wave batching loop until all queries are done or MAX_WAVES reached.

    If `checkpoint_path` is set, writes a checkpoint snapshot after each
    wave's `collect_wave_results` completes. Subsequent runs can use
    `load_checkpoint(path, cases)` to resume without re-fetching batch
    results or re-dispatching tools — eliminates the
    live-dispatch-divergence misalignment bug in `resume_batch_run.py`'s
    `replay_existing_wave` path.

    Returns the accumulated list of batch IDs submitted during this run
    (prepended with `initial_batch_ids` if given, so a checkpoint loaded
    from a prior partial run can keep its history).
    """
    batch_ids: list[str] = list(initial_batch_ids or [])
    wave = 0
    while wave < MAX_WAVES:
        pending = [s for s in states_by_id.values() if not s.done]
        if not pending:
            print(f"\nAll queries complete after {wave} wave(s).")
            return batch_ids
        wave += 1
        print(f"\n{'=' * 80}\nWAVE {wave}  ({len(pending)} pending queries)\n{'=' * 80}")
        batch_id = submit_wave(client, states_by_id, model)
        if batch_id:
            batch_ids.append(batch_id)
        poll_until_done(client, batch_id)
        print(f"\n  Wave {wave} complete. Collecting results...")
        n_next = collect_wave_results(client, batch_id, states_by_id)
        print(f"  {n_next} queries need another wave.")
        if checkpoint_path:
            try:
                save_checkpoint(states_by_id, checkpoint_path, batch_ids)
            except OSError as exc:
                # Don't crash the run on a checkpoint write failure — print
                # a warning so the user can still recover from Anthropic's
                # batches if they survive. The next wave's checkpoint
                # write may succeed.
                print(f"  WARNING: checkpoint write failed: {exc}", flush=True)
    if wave == MAX_WAVES:
        n_pending = sum(1 for s in states_by_id.values() if not s.done)
        if n_pending:
            print(f"\nMAX_WAVES={MAX_WAVES} reached, {n_pending} queries left unfinished.")
    return batch_ids


# ---------------------------------------------------------------------------
# Score and write output
# ---------------------------------------------------------------------------


def score_and_serialise(states_by_id: dict[str, QueryState], cases: list[TestCase],
                        model: str, run_id: str, ts: str, ground_truth_path: str) -> pd.DataFrame:
    """Score per-query and build the output DataFrame matching benchmark_eqa.py schema."""
    # Group states by query_idx so A and B for the same query are paired
    rows = []
    for idx, tc in enumerate(cases):
        sa = states_by_id.get(f"q{idx:04d}_A")
        sb = states_by_id.get(f"q{idx:04d}_B")
        if sa is None or sb is None:
            continue

        is_positive = tc.query_type == "POSITIVE"
        use_ya = tc.prompt_type == "baseline_latest" and is_positive

        # Ground truth
        gt_val = tc.ground_truth_value
        gt_year = tc.ground_truth_latest_year if tc.prompt_type == "baseline_latest" else tc.year

        # --- Condition A ---
        a_text = sa.final_text
        a_value = extract_numeric(a_text)
        a_year = extract_year(a_text)
        a_refused = _detect_refusal(a_text)
        a_cost = _compute_cost(model, sa.tokens_input, sa.tokens_output,
                               cache_read=sa.cache_read,
                               cache_creation=sa.cache_creation) * BATCH_DISCOUNT

        # --- Condition B ---
        b_text = sb.final_text
        tool_value, tool_year = _extract_from_tool_calls(sb.tool_calls)
        b_text_value = extract_numeric(b_text)
        b_text_year = extract_year(b_text)
        # v1.4: trust the model's stated refusal over tool-call data. When the
        # response text contains explicit refusal language ("no data is
        # available", "not available"), the model has correctly verdicted
        # there's no answer — even if a get_data tool call returned data for
        # a neighbouring year/country that the model offered as conversational
        # context. The previous behaviour pulled context-capture values as
        # the answer, scoring 45 of 49 refusals as hallucinations in the v4
        # post-fix run when the model had refused correctly.
        b_text_refused = _detect_refusal(b_text)
        if b_text_refused:
            b_value = None
            b_year = None
        else:
            b_value = tool_value if tool_value is not None else b_text_value
            b_year = tool_year if tool_year is not None else b_text_year
        b_refused = b_text_refused
        b_cost = _compute_cost(model, sb.tokens_input, sb.tokens_output,
                               cache_read=sb.cache_read,
                               cache_creation=sb.cache_creation) * BATCH_DISCOUNT

        # --- Scoring ---
        er_a = compute_er(a_value)
        er_b = compute_er(b_value)
        ya_a = compute_ya(a_year, gt_year) if use_ya else 1.0
        ya_b = compute_ya(b_year, gt_year) if use_ya else 1.0
        va_a = compute_va(a_value, gt_val) if is_positive else 0.0
        va_b = compute_va(b_value, gt_val) if is_positive else 0.0
        eqa_a = er_a * ya_a * va_a
        eqa_b = er_b * ya_b * va_b
        hall_a = a_value is not None and not is_positive
        hall_b = b_value is not None and not is_positive

        query_id = f"{tc.indicator_code}_{tc.country_code}_{tc.year}_{tc.prompt_type}"
        rows.append({
            "run_id": run_id,
            "query_id": query_id,
            "model": model,
            "temperature": TEMPERATURE,
            "timestamp": ts,
            "extractor_version": EXTRACTOR_VERSION,
            "indicator_code": tc.indicator_code,
            "indicator_name": tc.indicator_name,
            "unit": tc.unit,
            "country_code": tc.country_code,
            "country_name": tc.country_name,
            "year": tc.year,
            "query_type": tc.query_type,
            "prompt_type": tc.prompt_type,
            "prompt_text": tc.prompt_text,
            "gt_value": gt_val,
            "gt_year": gt_year,
            "gt_latest_year": tc.ground_truth_latest_year,
            "gt_latest_value": tc.ground_truth_value,
            # Condition A
            "a_response_full": a_text,
            "a_tokens_input": sa.tokens_input,
            "a_tokens_output": sa.tokens_output,
            "a_cost_usd": a_cost,
            "a_latency_ms": 0,  # batch — no per-query latency
            "a_refused": a_refused,
            "a_extracted_value": a_value,
            "a_extracted_year": a_year,
            # Condition B
            "b_response_full": b_text,
            "b_tokens_input": sb.tokens_input,
            "b_tokens_output": sb.tokens_output,
            "b_cache_creation_input_tokens": sb.cache_creation,
            "b_cache_read_input_tokens": sb.cache_read,
            "b_cost_usd": b_cost,
            "b_latency_ms": 0,
            "b_refused": b_refused,
            "b_tool_error": sb.tool_error,
            "b_tool_calls_json": json.dumps(sb.tool_calls, default=str),
            "b_n_tool_calls": len(sb.tool_calls),
            "b_extracted_value": b_value,
            "b_extracted_year": b_year,
            # Scoring
            "er_a": er_a, "ya_a": ya_a, "va_a": va_a, "eqa_a": eqa_a,
            "er_b": er_b, "ya_b": ya_b, "va_b": va_b, "eqa_b": eqa_b,
            "hall_a": hall_a, "hall_b": hall_b,
            # Batch-specific
            "batch_pricing_discount": BATCH_DISCOUNT,
            "b_rounds": sb.rounds,
        })

    return pd.DataFrame(rows)


def print_summary(df: pd.DataFrame) -> None:
    print()
    print("=" * 90)
    print("OVERALL SUMMARY (batch run)")
    print("=" * 90)
    pos = df[df["query_type"] == "POSITIVE"]
    if len(pos) > 0:
        print(f"\n  Positive queries EQA (n={len(pos)})")
        print(f"  {'':>25s} {'LLM alone':>12s} {'LLM + MCP':>12s}")
        print(f"  {'-' * 51}")
        print(f"  {'Mean EQA':<25s} {pos['eqa_a'].mean():>12.3f} {pos['eqa_b'].mean():>12.3f}")
    hall = df[df["query_type"].str.startswith("HALLUCINATION")]
    if len(hall) > 0:
        n = len(hall)
        h_a = hall["hall_a"].sum()
        h_b = hall["hall_b"].sum()
        print(f"\n  HALLUCINATION SUMMARY (n={n})")
        print(f"  {'':>25s} {'LLM alone':>12s} {'LLM + MCP':>12s}")
        print(f"  {'-' * 51}")
        print(f"  {'Fabrications':<25s} {h_a:>12d} {h_b:>12d}")
        print(f"  {'Hallucination rate':<25s} {h_a / n * 100:>11.0f}% {h_b / n * 100:>11.0f}%")
        for htype in ["HALLUCINATION_T1", "HALLUCINATION_T2"]:
            subset = hall[hall["query_type"] == htype]
            if len(subset):
                print(f"    {htype}: A={subset['hall_a'].sum()}/{len(subset)}  B={subset['hall_b'].sum()}/{len(subset)}")
    print()
    a_total = df["a_cost_usd"].sum()
    b_total = df["b_cost_usd"].sum()
    print(f"  Total cost (batch-discounted):")
    print(f"    Condition A: ${a_total:.4f}  ({a_total / max(len(df), 1):.4f}/query)")
    print(f"    Condition B: ${b_total:.4f}  ({b_total / max(len(df), 1):.4f}/query)")


def main():
    parser = argparse.ArgumentParser(description="EQA benchmark via Anthropic Message Batches API")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=0, help="Limit queries per section (0=all)")
    parser.add_argument("--ground-truth", required=True, help="Path to sample.csv")
    parser.add_argument("--tag", default="batch", help="Tag appended to output filenames")
    args = parser.parse_args()

    # Override the load_sample CSV path (load_sample reads benchmark_eqa.SAMPLE_CSV)
    import benchmark_eqa
    benchmark_eqa.SAMPLE_CSV = args.ground_truth
    benchmark_eqa.GT_VALUES_CSV = os.path.join(
        os.path.dirname(args.ground_truth), "ground_truth_values.csv"
    )

    # line_buffering=True so progress prints land in stdout immediately even
    # when this script is run with output captured to a file. Without it,
    # the wrapper silently overrides `python -u` and background tasks
    # appear to hang at 0 bytes for tens of minutes.
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

    # Use the canonical helper from benchmark_eqa rather than reimplementing
    # the pos+T1+T2 reorder inline. See load_sample_in_benchmark_order's
    # docstring for why this matters.
    from benchmark_eqa import load_sample_in_benchmark_order
    cases = load_sample_in_benchmark_order(limit_per_section=args.limit)
    positive_cases = [c for c in cases if c.query_type == "POSITIVE"]
    hall_t1_cases = [c for c in cases if c.query_type == "HALLUCINATION_T1"]
    hall_t2_cases = [c for c in cases if c.query_type == "HALLUCINATION_T2"]
    n_queries = len(cases)

    print("=" * 90)
    print("UNICEF Stats MCP — EQA Benchmark (BATCHED)")
    print("=" * 90)
    print(f"  Model:           {args.model}")
    print(f"  Sample:          {args.ground_truth}")
    print(f"  Queries:         {n_queries} ({len(positive_cases)} POS + {len(hall_t1_cases)} T1 + {len(hall_t2_cases)} T2)")
    print(f"  Conditions:      A (LLM alone) + B (LLM + MCP)")
    print(f"  Total batch reqs: {n_queries * 2} per wave (×{MAX_WAVES} max waves)")
    print(f"  Pricing:         {BATCH_DISCOUNT:.0%} of standard (Message Batches API)")
    print(f"  Wall-clock SLA:  up to 24h per wave (typically 10–60 min)")
    print()

    client = anthropic.Anthropic()

    # Build initial state for both conditions
    states_by_id: dict[str, QueryState] = {}
    for idx, tc in enumerate(cases):
        for cond in ("A", "B"):
            s = QueryState(idx, tc, cond)
            states_by_id[s.custom_id] = s

    # Compute output naming up-front so the per-wave checkpoint shares the
    # same ts/tag/run_id stem as the final parquet — makes recovery
    # mechanical (look for `eqa_<run_id>.checkpoint.json` next to where
    # the parquet would land).
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_slug = args.model.replace("/", "_").replace(":", "_")
    tag = f"_{args.tag}" if args.tag else ""
    run_id = f"{model_slug}_{ts}{tag}"
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    checkpoint_path = os.path.join(out_dir, f"eqa_{run_id}.checkpoint.json")
    print(f"  Checkpoint:      {checkpoint_path}")

    # Run wave loop with per-wave checkpoint writes. If the run dies
    # mid-flight (network, OOM, exit 127), the checkpoint is the source of
    # truth for `resume_batch_run.py --load-state` to pick up — no live
    # tool re-dispatch, so no row-misalignment.
    t_start = time.time()
    run_batch_waves(client, states_by_id, args.model, checkpoint_path=checkpoint_path)
    elapsed = int(time.time() - t_start)
    print(f"\n  Total wall-clock: {elapsed}s ({elapsed/60:.1f} min)")

    df = score_and_serialise(states_by_id, cases, args.model, run_id, ts, args.ground_truth)
    print_summary(df)

    if df.empty:
        print("\n  No results to save.")
        return

    parquet_file = os.path.join(out_dir, f"eqa_{run_id}.parquet")
    csv_file = os.path.join(out_dir, f"eqa_{run_id}.csv")
    json_file = os.path.join(out_dir, f"eqa_{run_id}.json")
    df.to_parquet(parquet_file, index=False, engine="pyarrow")
    df.to_csv(csv_file, index=False)

    summary = {
        "run_id": run_id,
        "model": args.model,
        "temperature": TEMPERATURE,
        "timestamp": ts,
        "n_queries": len(df),
        "ground_truth_source": args.ground_truth,
        "batch_pricing_discount": BATCH_DISCOUNT,
        "wall_clock_sec": elapsed,
    }
    pos = df[df["query_type"] == "POSITIVE"]
    if len(pos) > 0:
        summary["positive_metrics"] = {
            "mean_eqa_a": round(float(pos["eqa_a"].mean()), 4),
            "mean_eqa_b": round(float(pos["eqa_b"].mean()), 4),
        }
    hall = df[df["query_type"].str.startswith("HALLUCINATION")]
    if len(hall) > 0:
        summary["hallucination_metrics"] = {
            "rate_a": round(float(hall["hall_a"].mean()), 4),
            "rate_b": round(float(hall["hall_b"].mean()), 4),
            "n": int(len(hall)),
        }
    with open(json_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Results saved:")
    print(f"    Parquet: {parquet_file}")
    print(f"    CSV:     {csv_file}")
    print(f"    JSON:    {json_file}")


if __name__ == "__main__":
    main()
