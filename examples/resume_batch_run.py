#!/usr/bin/env python3
"""Resume a wave-batch run from existing batch IDs (no double-spending).

Use case: a batch run crashed mid-poll due to a transient network error.
The batches keep processing on Anthropic's side; this script reconstructs
state from the batches that already ran AND submits new waves for queries
still in tool-loop. Avoids re-paying for the waves that already completed.

Usage:
    python examples/resume_batch_run.py \\
        --ground-truth examples/ground_truth_mcp060/sample.csv \\
        --tag mcp061_full_resumed \\
        --batch-ids msgbatch_xxxx,msgbatch_yyyy,msgbatch_zzzz

The --batch-ids list should be in WAVE ORDER (oldest first).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

import anthropic
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from benchmark_eqa import (  # noqa: E402
    DEFAULT_MODEL, EXTRACTOR_VERSION, TEMPERATURE,
    _compute_cost, _detect_refusal, _extract_from_tool_calls,
    compute_er, compute_va, compute_ya, dispatch_tool,
    extract_numeric, extract_year, load_sample,
)
from benchmark_eqa_batch import (  # noqa: E402
    BATCH_DISCOUNT, MAX_WAVES, QueryState,
    build_batch_request, collect_wave_results, poll_until_done, submit_wave,
)


def _fetch_batch_results_with_retry(client, batch_id, max_attempts=6):
    """Stream all results from a batch into a list with retry-on-network-error.

    The Anthropic SDK's `batches.results()` returns an iterator over JSONL.
    On flaky networks the stream can die mid-iteration; we retry the whole
    fetch up to N times with exponential backoff.
    """
    import anthropic
    attempt = 0
    backoff = 5.0
    while True:
        try:
            results = list(client.messages.batches.results(batch_id))
            return results
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
            attempt += 1
            if attempt >= max_attempts:
                raise
            print(f"  [retry {attempt}/{max_attempts} after {backoff:.0f}s] results-fetch failed: {type(exc).__name__}", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
        except Exception as exc:
            # httpx.RemoteProtocolError, httpx.ReadError, etc.
            attempt += 1
            if attempt >= max_attempts:
                raise
            name = type(exc).__name__
            if "Error" not in name and "Exception" not in name:
                raise
            print(f"  [retry {attempt}/{max_attempts} after {backoff:.0f}s] results-fetch failed: {name}", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


def replay_existing_wave(client, batch_id, states_by_id):
    """Replay one already-completed batch, updating query states.

    Re-dispatches tool calls locally (slow but necessary so that the next
    wave's `messages` history contains the right tool_results).
    """
    n_proc = 0
    n_err = 0
    results = _fetch_batch_results_with_retry(client, batch_id)
    for entry in results:
        cid = entry.custom_id
        state = states_by_id.get(cid)
        if state is None or state.done:
            continue
        result = entry.result
        if result.type == "errored":
            err = result.error
            state.done = True
            state.final_text = f"[batch error: {getattr(err, 'type', '?')}]"
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
            text_blocks = [b.text for b in msg.content if hasattr(b, "text")]
            state.final_text = "\n".join(text_blocks)
            state.done = True
            continue

        tool_uses = [b for b in msg.content if b.type == "tool_use"]
        if not tool_uses:
            text_blocks = [b.text for b in msg.content if hasattr(b, "text")]
            state.final_text = "\n".join(text_blocks)
            state.done = True
            continue

        # Need tool_results for this state's next-wave message history.
        # Re-dispatch locally with the same args Claude used.
        tool_results = []
        for tu in tool_uses:
            result_str = dispatch_tool(tu.name, tu.input)
            state.tool_calls.append({"tool": tu.name, "input": tu.input})
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

        # Reconstruct assistant block list for the next-wave message
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

        # Capture the latest text we did see (helps fast-extraction even if
        # state never reaches a final answer).
        text_blocks = [b.text for b in msg.content if hasattr(b, "text")]
        if text_blocks:
            state.final_text = "\n".join(text_blocks)

    return n_proc, n_err


def score_and_serialise(states_by_id, cases, model, run_id, ts):
    rows = []
    for idx, tc in enumerate(cases):
        sa = states_by_id.get(f"q{idx:04d}_A")
        sb = states_by_id.get(f"q{idx:04d}_B")
        if sa is None or sb is None:
            continue

        is_positive = tc.query_type == "POSITIVE"
        use_ya = tc.prompt_type == "baseline_latest" and is_positive
        gt_val = tc.ground_truth_value
        gt_year = tc.ground_truth_latest_year if tc.prompt_type == "baseline_latest" else tc.year

        a_text = sa.final_text
        a_value = extract_numeric(a_text)
        a_year = extract_year(a_text)
        a_refused = _detect_refusal(a_text)
        a_cost = _compute_cost(model, sa.tokens_input, sa.tokens_output,
                               cache_read=sa.cache_read,
                               cache_creation=sa.cache_creation) * BATCH_DISCOUNT

        b_text = sb.final_text
        tool_value, tool_year = _extract_from_tool_calls(sb.tool_calls)
        b_text_value = extract_numeric(b_text)
        b_text_year = extract_year(b_text)
        b_value = tool_value if tool_value is not None else b_text_value
        b_year = tool_year if tool_year is not None else b_text_year
        b_refused = _detect_refusal(b_text) and tool_value is None
        b_cost = _compute_cost(model, sb.tokens_input, sb.tokens_output,
                               cache_read=sb.cache_read,
                               cache_creation=sb.cache_creation) * BATCH_DISCOUNT

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
            "run_id": run_id, "query_id": query_id, "model": model,
            "temperature": TEMPERATURE, "timestamp": ts,
            "extractor_version": EXTRACTOR_VERSION,
            "indicator_code": tc.indicator_code, "indicator_name": tc.indicator_name,
            "unit": tc.unit, "country_code": tc.country_code,
            "country_name": tc.country_name, "year": tc.year,
            "query_type": tc.query_type, "prompt_type": tc.prompt_type,
            "prompt_text": tc.prompt_text,
            "gt_value": gt_val, "gt_year": gt_year,
            "gt_latest_year": tc.ground_truth_latest_year,
            "gt_latest_value": tc.ground_truth_value,
            "a_response_full": a_text,
            "a_tokens_input": sa.tokens_input,
            "a_tokens_output": sa.tokens_output,
            "a_cost_usd": a_cost,
            "a_latency_ms": 0,
            "a_refused": a_refused,
            "a_extracted_value": a_value,
            "a_extracted_year": a_year,
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
            "er_a": er_a, "ya_a": ya_a, "va_a": va_a, "eqa_a": eqa_a,
            "er_b": er_b, "ya_b": ya_b, "va_b": va_b, "eqa_b": eqa_b,
            "hall_a": hall_a, "hall_b": hall_b,
            "batch_pricing_discount": BATCH_DISCOUNT,
            "b_rounds": sb.rounds,
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--batch-ids", required=True,
                        help="comma-separated batch IDs in wave order (oldest first)")
    parser.add_argument("--continue-waves", action="store_true",
                        help="Submit new waves for unfinished queries until all done or MAX_WAVES")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    import benchmark_eqa
    benchmark_eqa.SAMPLE_CSV = args.ground_truth
    benchmark_eqa.GT_VALUES_CSV = os.path.join(
        os.path.dirname(args.ground_truth), "ground_truth_values.csv"
    )

    cases = load_sample()
    print(f"Loaded {len(cases)} test cases")

    states_by_id: dict[str, QueryState] = {}
    for idx, tc in enumerate(cases):
        for cond in ("A", "B"):
            s = QueryState(idx, tc, cond)
            states_by_id[s.custom_id] = s

    client = anthropic.Anthropic()
    batch_ids = [b.strip() for b in args.batch_ids.split(",") if b.strip()]
    print(f"\nReplaying {len(batch_ids)} existing batch(es)...")
    waves_used = 0
    for i, batch_id in enumerate(batch_ids, 1):
        print(f"\nWave {i}: {batch_id}")
        n_proc, n_err = replay_existing_wave(client, batch_id, states_by_id)
        n_done = sum(1 for s in states_by_id.values() if s.done)
        print(f"  Processed: {n_proc}  Errors: {n_err}  Total done: {n_done}/{len(states_by_id)}")
        waves_used = i

    n_unfinished = sum(1 for s in states_by_id.values() if not s.done)
    print(f"\nAfter replay: {n_unfinished} queries unfinished")

    # Optionally continue with new waves
    if args.continue_waves and n_unfinished > 0 and waves_used < MAX_WAVES:
        print("\nContinuing with new waves...")
        wave = waves_used
        while wave < MAX_WAVES:
            pending = [s for s in states_by_id.values() if not s.done]
            if not pending:
                break
            wave += 1
            print(f"\n{'='*80}\nWAVE {wave}  ({len(pending)} pending queries)\n{'='*80}")
            new_batch_id = submit_wave(client, states_by_id, args.model)
            poll_until_done(client, new_batch_id)
            n_next = collect_wave_results(client, new_batch_id, states_by_id)
            print(f"  Wave {wave} complete; {n_next} need another wave")

    n_unfinished = sum(1 for s in states_by_id.values() if not s.done)
    print(f"\nFinal unfinished: {n_unfinished}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_slug = args.model.replace("/", "_").replace(":", "_")
    run_id = f"{model_slug}_{ts}_{args.tag}"
    df = score_and_serialise(states_by_id, cases, args.model, run_id, ts)
    print(f"\nScored {len(df)} queries")

    out_dir = "examples/results"
    os.makedirs(out_dir, exist_ok=True)
    pq = os.path.join(out_dir, f"eqa_{run_id}.parquet")
    csv = os.path.join(out_dir, f"eqa_{run_id}.csv")
    js  = os.path.join(out_dir, f"eqa_{run_id}.json")
    df.to_parquet(pq, index=False, engine="pyarrow")
    df.to_csv(csv, index=False)

    summary = {
        "run_id": run_id, "model": args.model, "n_queries": len(df),
        "ground_truth_source": args.ground_truth,
        "batch_pricing_discount": BATCH_DISCOUNT,
        "batch_ids_used": batch_ids,
        "queries_unfinished": n_unfinished,
    }
    pos = df[df["query_type"] == "POSITIVE"]
    if len(pos) > 0:
        summary["positive_metrics"] = {
            "n": int(len(pos)),
            "mean_eqa_a": round(float(pos["eqa_a"].mean()), 4),
            "mean_eqa_b": round(float(pos["eqa_b"].mean()), 4),
        }
    hall = df[df["query_type"].str.startswith("HALLUCINATION")]
    if len(hall) > 0:
        summary["hallucination_metrics"] = {
            "rate_a": round(float(hall["hall_a"].mean()), 4),
            "rate_b": round(float(hall["hall_b"].mean()), 4),
            "n": int(len(hall)),
            "by_tier": {
                t: {
                    "n": int(len(hall[hall["query_type"] == t])),
                    "rate_a": round(float(hall[hall["query_type"] == t]["hall_a"].mean()), 4),
                    "rate_b": round(float(hall[hall["query_type"] == t]["hall_b"].mean()), 4),
                }
                for t in ["HALLUCINATION_T1", "HALLUCINATION_T2"]
            },
        }
    summary["cost_summary"] = {
        "condition_a_total": round(float(df["a_cost_usd"].sum()), 4),
        "condition_b_total": round(float(df["b_cost_usd"].sum()), 4),
        "condition_a_per_query": round(float(df["a_cost_usd"].mean()), 6),
        "condition_b_per_query": round(float(df["b_cost_usd"].mean()), 6),
    }
    with open(js, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {pq}")
    print(json.dumps(summary, indent=2)[:2000])


if __name__ == "__main__":
    main()
