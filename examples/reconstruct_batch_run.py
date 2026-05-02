#!/usr/bin/env python3
"""Reconstruct mcp060_full batch run from already-completed batch IDs.

The Wave 1-5 batches all finished on the Anthropic side but the local Python
process died before serialising results. This script pulls the messages from
each batch, replays the wave-by-wave state evolution locally, scores, and
writes the parquet/CSV/JSON in the same schema as benchmark_eqa_batch.py.

No new API calls are billed — Anthropic retains batch results for ~29 days.
"""

from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

import anthropic
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from benchmark_eqa import (  # noqa: E402
    DEFAULT_MODEL, EXTRACTOR_VERSION, TEMPERATURE,
    TestCase, _compute_cost, _detect_refusal, _extract_from_tool_calls,
    compute_er, compute_va, compute_ya, dispatch_tool,
    extract_numeric, extract_year, load_sample,
)
from benchmark_eqa_batch import BATCH_DISCOUNT, QueryState  # noqa: E402

# Wave batch IDs in order, captured from the API list.
WAVE_BATCH_IDS = [
    "msgbatch_01H1HqyYgJ1L2jNf9yNFzUB8",  # Wave 1: 1000 entries (A + B for all 500)
    "msgbatch_018MkxWr2GV64KwmeJy7KsC2",  # Wave 2: 500 entries (B-only follow-ups)
    "msgbatch_01BYQvZW7YZBExGfQzkU7Ykb",  # Wave 3: 500 entries
    "msgbatch_01CLuGrb3pmbeTJF4cmD9oVq",  # Wave 4: 253 entries
    "msgbatch_01BSrGBN2VuJL9vbpeQG5Ri3",  # Wave 5: 243 entries
]

GROUND_TRUTH = "examples/ground_truth_mcp060/sample.csv"
TAG = "mcp060_full"
MODEL = DEFAULT_MODEL


def replay_wave(client, batch_id, states_by_id):
    """Pull batch results and update query states (mirrors collect_wave_results)."""
    n_processed = 0
    n_errors = 0
    for entry in client.messages.batches.results(batch_id):
        cid = entry.custom_id
        state = states_by_id.get(cid)
        if state is None or state.done:
            continue
        result = entry.result
        if result.type == "errored":
            err = result.error
            state.done = True
            state.final_text = f"[batch error: {getattr(err, 'type', '?')}]"
            n_errors += 1
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
        n_processed += 1

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

        # Re-dispatch tools locally to populate tool_calls (we don't need the
        # next-wave message history any more since later waves will reuse
        # the cached batch results).
        for tu in tool_uses:
            result_str = dispatch_tool(tu.name, tu.input)
            state.tool_calls.append({"tool": tu.name, "input": tu.input})
            try:
                parsed = json.loads(result_str)
                if parsed.get("data_status") == "confirmed_absent":
                    state.tool_error = parsed.get("error", "confirmed_absent")
            except (json.JSONDecodeError, AttributeError):
                pass

        # If the model is still calling tools at the last wave, capture the
        # text we *did* see (often empty) and let the scorer fall back to
        # tool-call extraction.
        text_blocks = [b.text for b in msg.content if hasattr(b, "text")]
        state.final_text = "\n".join(text_blocks)
    return n_processed, n_errors


def score_and_serialise(states_by_id, cases, model, run_id, ts, gt_path):
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
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    import benchmark_eqa
    benchmark_eqa.SAMPLE_CSV = GROUND_TRUTH
    benchmark_eqa.GT_VALUES_CSV = os.path.join(
        os.path.dirname(GROUND_TRUTH), "ground_truth_values.csv"
    )

    cases = load_sample()
    print(f"Loaded {len(cases)} test cases from {GROUND_TRUTH}")

    states_by_id: dict[str, QueryState] = {}
    for idx, tc in enumerate(cases):
        for cond in ("A", "B"):
            s = QueryState(idx, tc, cond)
            states_by_id[s.custom_id] = s

    client = anthropic.Anthropic()
    for i, batch_id in enumerate(WAVE_BATCH_IDS, 1):
        print(f"\nWave {i}: {batch_id}")
        n_proc, n_err = replay_wave(client, batch_id, states_by_id)
        n_done = sum(1 for s in states_by_id.values() if s.done)
        print(f"  Processed: {n_proc}  Errors: {n_err}  Total done: {n_done}/{len(states_by_id)}")

    n_unfinished = sum(1 for s in states_by_id.values() if not s.done)
    print(f"\nUnfinished after 5 waves: {n_unfinished}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_slug = MODEL.replace("/", "_").replace(":", "_")
    run_id = f"{model_slug}_{ts}_{TAG}"
    df = score_and_serialise(states_by_id, cases, MODEL, run_id, ts, GROUND_TRUTH)
    print(f"\nScored {len(df)} queries")

    out_dir = "examples/results"
    os.makedirs(out_dir, exist_ok=True)
    pq = os.path.join(out_dir, f"eqa_{run_id}.parquet")
    csv = os.path.join(out_dir, f"eqa_{run_id}.csv")
    js  = os.path.join(out_dir, f"eqa_{run_id}.json")
    df.to_parquet(pq, index=False, engine="pyarrow")
    df.to_csv(csv, index=False)

    summary = {
        "run_id": run_id, "model": MODEL, "temperature": TEMPERATURE,
        "timestamp": ts, "n_queries": len(df),
        "ground_truth_source": GROUND_TRUTH,
        "batch_pricing_discount": BATCH_DISCOUNT,
        "batch_ids": WAVE_BATCH_IDS,
        "queries_unfinished_at_wave5": n_unfinished,
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
    summary["token_summary"] = {
        "b_input_total": int(df["b_tokens_input"].sum()),
        "b_output_total": int(df["b_tokens_output"].sum()),
        "b_cache_creation_total": int(df["b_cache_creation_input_tokens"].sum()),
        "b_cache_read_total": int(df["b_cache_read_input_tokens"].sum()),
    }
    with open(js, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nWrote:")
    print(f"  {pq}")
    print(f"  {csv}")
    print(f"  {js}")
    print(f"\n--- HALLUCINATION ---")
    if len(hall) > 0:
        print(json.dumps(summary["hallucination_metrics"], indent=2))
    print(f"\n--- COST ---")
    print(json.dumps(summary["cost_summary"], indent=2))


if __name__ == "__main__":
    main()
