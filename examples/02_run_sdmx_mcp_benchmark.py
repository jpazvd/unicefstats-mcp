"""Benchmark Condition C: LLM + sdmx-mcp tools.

Runs the same queries as the main benchmark but with sdmx-mcp tool definitions.
Appends results to a combined parquet for 3-way comparison (A vs B vs C).

Requires:
  - ANTHROPIC_API_KEY in .env
  - sdmx-mcp server.py accessible (for tool execution)
  - Existing parquet from benchmark_eqa.py (for Conditions A+B)

Usage:
  python examples/02_run_sdmx_mcp_benchmark.py
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path(os.path.expanduser("~")) / "GitHub" / "others" / "unicef-sdg-llm-benchmark-dev" / ".env")

import anthropic
import pandas as pd

# ---------------------------------------------------------------------------
# sdmx-mcp tool definitions for the Anthropic API
# ---------------------------------------------------------------------------

SDMX_MCP_TOOLS = [
    {
        "name": "search_dataflows",
        "description": "Search SDMX dataflows by keyword. Returns matching dataflows with their IDs, names, and agencies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "find_indicator_candidates",
        "description": "Search for indicator codes across dataflows. Returns matching indicators with their codes, names, and parent dataflows.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Indicator search keyword"},
                "flowRef": {"type": "string", "description": "Optional: limit to a specific dataflow"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_indicators",
        "description": "Alias for find_indicator_candidates. Search indicators by keyword.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "flowRef": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "describe_flow",
        "description": "Get metadata for an SDMX dataflow: dimensions, attributes, and structure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flowRef": {"type": "string", "description": "Dataflow reference (e.g. 'GLOBAL_DATAFLOW')"},
            },
            "required": ["flowRef"],
        },
    },
    {
        "name": "list_dimensions",
        "description": "List all dimensions of a dataflow with their names and positions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flowRef": {"type": "string"},
            },
            "required": ["flowRef"],
        },
    },
    {
        "name": "list_codes",
        "description": "List valid codes for a dimension in a dataflow.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flowRef": {"type": "string"},
                "dimension": {"type": "string", "description": "Dimension ID (e.g. 'INDICATOR', 'REF_AREA')"},
                "query": {"type": "string", "description": "Optional filter keyword"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["flowRef", "dimension"],
        },
    },
    {
        "name": "build_key",
        "description": "Build an SDMX key string from dimension selections for use in query_data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flowRef": {"type": "string"},
                "selections": {
                    "type": "object",
                    "description": "Dimension selections, e.g. {'INDICATOR': 'CME_MRY0T4', 'REF_AREA': 'NGA'}",
                },
            },
            "required": ["flowRef"],
        },
    },
    {
        "name": "query_data",
        "description": "Query SDMX data. Requires flowRef, key or filters, and a time window.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flowRef": {"type": "string", "description": "Dataflow reference"},
                "key": {"type": "string", "description": "SDMX key string (from build_key)"},
                "startPeriod": {"type": "string", "description": "Start year, e.g. '2020'"},
                "endPeriod": {"type": "string", "description": "End year, e.g. '2024'"},
                "format": {"type": "string", "default": "csv", "description": "Response format: csv or sdmx-json"},
                "labels": {"type": "string", "default": "both", "description": "Label mode: id, name, or both"},
                "filters": {
                    "type": "object",
                    "description": "Alternative to key: dict of dimension selections",
                },
                "lastNObservations": {"type": "integer", "description": "Get last N observations per series"},
            },
            "required": ["flowRef"],
        },
    },
    {
        "name": "get_flow_structure",
        "description": "Get the full structure of a dataflow including all dimensions, their codelists, and attributes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flowRef": {"type": "string"},
            },
            "required": ["flowRef"],
        },
    },
    {
        "name": "validate_query_scope",
        "description": "Pre-validate whether a query is within the allowed scope before fetching data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flowRef": {"type": "string"},
                "key": {"type": "string"},
            },
            "required": ["flowRef"],
        },
    },
]

# ---------------------------------------------------------------------------
# sdmx-mcp tool execution (import and call async functions)
# ---------------------------------------------------------------------------

# Add sdmx-mcp to path
SDMX_MCP_DIR = Path("f:/GitHub/mcps/sdmx-mcp")
sys.path.insert(0, str(SDMX_MCP_DIR))

_sdmx_server = None


def _get_sdmx_server():
    """Lazy import sdmx-mcp server module."""
    global _sdmx_server
    if _sdmx_server is None:
        # Suppress logging from sdmx-mcp
        import logging
        logging.getLogger().setLevel(logging.WARNING)
        import server as sdmx_server
        _sdmx_server = sdmx_server
    return _sdmx_server


def call_sdmx_tool(name: str, args: dict) -> str:
    """Call an sdmx-mcp tool function and return JSON result."""
    srv = _get_sdmx_server()
    func = getattr(srv, name, None)
    if func is None:
        return json.dumps({"error": f"Tool '{name}' not found in sdmx-mcp"})
    try:
        result = asyncio.run(func(**args))
        return json.dumps(result, default=str, ensure_ascii=False)[:8000]  # truncate for context
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_C = (
    "You are a data analyst with access to SDMX MCP tools for querying the UNICEF Data Warehouse. "
    "Use the tools to find and retrieve data. Report the EXACT numeric value from the tool response. "
    "Do NOT round, approximate, or use training data. If a tool returns no data, say 'Data not available'. "
    "When asked for the latest value, use lastNObservations=1 or a recent time window."
)

MODEL = "claude-sonnet-4-20250514"
MAX_TOOL_ROUNDS = 8  # sdmx-mcp may need more rounds (search → describe → build_key → query)


def extract_numeric(text: str) -> tuple[float | None, int | None, bool]:
    """Extract a numeric value and year from LLM response text."""
    refusal_patterns = [
        r"not available", r"no data", r"cannot find", r"don't have",
        r"unable to", r"does not exist", r"not found", r"no .* data",
        r"data is not available", r"couldn't find", r"not .* available",
    ]
    for pat in refusal_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return None, None, True

    # Try to find a bolded or clearly stated value
    value = None
    year = None

    # Year extraction
    year_match = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", text)
    if year_match:
        year = int(year_match.group(1))

    # Value extraction — look for numbers near keywords
    val_patterns = [
        r"(?:is|was|rate.*?)\s*\**(\d+\.?\d*)\**",
        r"(\d+\.?\d*)\s*(?:deaths|per\s+1[,.]?000|percent|%)",
        r"\*\*(\d+\.?\d*)\*\*",
    ]
    for pat in val_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                value = float(m.group(1))
                break
            except ValueError:
                continue

    return value, year, False


def run_condition_c(
    sample: pd.DataFrame,
    client: anthropic.Anthropic,
) -> list[dict]:
    """Run Condition C: LLM + sdmx-mcp tools."""
    results = []
    total = len(sample)

    for idx, row in sample.iterrows():
        i = len(results) + 1
        indicator = row["indicator_code"]
        country = row["country_code"]
        country_name = row.get("country_name", country)
        year = row.get("year", None)
        prompt_type = row.get("prompt_type", "baseline_latest")

        if prompt_type == "direct" and year:
            prompt = f"What was the value of UNICEF indicator {indicator} for {country_name} ({country}) in {int(year)}? Give the exact number."
        else:
            prompt = f"What is the latest available value of UNICEF indicator {indicator} for {country_name} ({country})? Give the exact number and the year."

        print(f"  [{i:>3d}/{total}] {indicator} x {country} ", end="", flush=True)
        t0 = time.time()

        messages = [{"role": "user", "content": prompt}]
        tokens_in = 0
        tokens_out = 0
        n_tool_calls = 0
        tool_errors = []

        # Multi-turn tool loop
        for _round in range(MAX_TOOL_ROUNDS):
            try:
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=2048,
                    system=SYSTEM_PROMPT_C,
                    tools=SDMX_MCP_TOOLS,
                    messages=messages,
                    temperature=0.0,
                )
            except Exception as exc:
                tool_errors.append(str(exc))
                break

            tokens_in += resp.usage.input_tokens
            tokens_out += resp.usage.output_tokens

            if resp.stop_reason == "end_turn":
                break

            if resp.stop_reason == "tool_use":
                # Process tool calls
                tool_results = []
                for block in resp.content:
                    if block.type == "tool_use":
                        n_tool_calls += 1
                        tool_name = block.name
                        tool_args = block.input
                        try:
                            result_str = call_sdmx_tool(tool_name, tool_args)
                        except Exception as exc:
                            result_str = json.dumps({"error": str(exc)})
                            tool_errors.append(str(exc))
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })

                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        latency_ms = int((time.time() - t0) * 1000)

        # Extract final text response
        final_text = ""
        if resp and resp.content:
            for block in resp.content:
                if hasattr(block, "text"):
                    final_text += block.text

        c_value, c_year, c_refused = extract_numeric(final_text)

        print(f"({latency_ms}ms, {n_tool_calls} calls) val={c_value} yr={c_year} ref={c_refused}")

        results.append({
            "indicator_code": indicator,
            "country_code": country,
            "country_name": country_name,
            "year": year,
            "query_type": row.get("query_type", "POSITIVE"),
            "prompt_type": prompt_type,
            "gt_value": row.get("gt_value", None),
            "gt_year": row.get("gt_year", None),
            "gt_latest_year": row.get("gt_latest_year", None),
            "gt_latest_value": row.get("gt_latest_value", None),
            "c_extracted_value": c_value,
            "c_extracted_year": c_year,
            "c_refused": c_refused,
            "c_response_full": final_text[:500],
            "c_tokens_input": tokens_in,
            "c_tokens_output": tokens_out,
            "c_latency_ms": latency_ms,
            "c_n_tool_calls": n_tool_calls,
            "c_tool_error": "; ".join(tool_errors) if tool_errors else None,
        })

    return results


def score_results(results: list[dict]) -> pd.DataFrame:
    """Score Condition C results with EQA metric."""
    df = pd.DataFrame(results)

    # EQA scoring
    for prefix in ["c"]:
        er = []
        ya = []
        va = []
        hall = []

        for _, row in df.iterrows():
            extracted = row[f"{prefix}_extracted_value"]
            ext_year = row[f"{prefix}_extracted_year"]
            gt_val = row.get("gt_latest_value") or row.get("gt_value")
            gt_yr = row.get("gt_latest_year") or row.get("gt_year")
            qt = row["query_type"]

            if qt.startswith("HALLUCINATION"):
                er.append(0)
                ya.append(0)
                va.append(0)
                hall.append(1 if extracted is not None and not row[f"{prefix}_refused"] else 0)
                continue

            # ER
            er_val = 1.0 if extracted is not None else 0.0
            er.append(er_val)

            # YA
            if row["prompt_type"] == "direct":
                ya_val = 1.0  # year is given
            elif ext_year is not None and gt_yr is not None:
                diff = abs(ext_year - gt_yr)
                ya_val = {0: 1.0, 1: 0.75, 2: 0.50}.get(diff, 0.25 if diff <= 4 else 0.0)
            else:
                ya_val = 0.0
            ya.append(ya_val)

            # VA
            if extracted is not None and gt_val is not None and gt_val != 0:
                va_val = max(0.0, 1.0 - abs(extracted - gt_val) / abs(gt_val))
            else:
                va_val = 0.0
            va.append(va_val)

            hall.append(0)

        df[f"er_{prefix}"] = er
        df[f"ya_{prefix}"] = ya
        df[f"va_{prefix}"] = va
        df[f"eqa_{prefix}"] = [e * y * v for e, y, v in zip(er, ya, va)]
        df[f"hall_{prefix}"] = hall

    # Cost (Sonnet pricing)
    df["c_cost_usd"] = df["c_tokens_input"] * 3e-6 + df["c_tokens_output"] * 15e-6

    return df


def main():
    client = anthropic.Anthropic()
    if not client.api_key:
        print("ERROR: ANTHROPIC_API_KEY not found")
        return

    # Load the SAME 300 queries from the v1.3 parquet (which has A + B already)
    base_parquet = Path(__file__).parent / "results" / "eqa_claude-sonnet-4-20250514_20260323_174311.parquet"
    if not base_parquet.exists():
        print(f"ERROR: {base_parquet} not found. Run benchmark_eqa.py first.")
        return

    base = pd.read_parquet(base_parquet)
    print(f"Loaded {len(base)} queries from {base_parquet.name}")
    print(f"  Conditions A+B already scored (extractor: {base.extractor_version.iloc[0]})")
    print(f"  Query types: {base.query_type.value_counts().to_dict()}")
    print(f"Model: {MODEL}")
    print(f"Max tool rounds: {MAX_TOOL_ROUNDS}")

    # Run Condition C on the same queries
    print(f"\n{'='*70}")
    print("CONDITION C: LLM + sdmx-mcp (same 300 queries)")
    print(f"{'='*70}")

    results = run_condition_c(base, client)
    df_c = score_results(results)

    # Merge C columns into the base parquet
    c_cols = [c for c in df_c.columns if c.startswith("c_") or c.startswith("er_c") or c.startswith("ya_c") or c.startswith("va_c") or c.startswith("eqa_c") or c.startswith("hall_c")]
    # Include the scoring columns too
    score_cols = ["er_c", "ya_c", "va_c", "eqa_c", "hall_c"]
    all_c_cols = [c for c in df_c.columns if c.endswith("_c") or c.startswith("c_")]

    combined = base.copy()
    for col in all_c_cols:
        if col in df_c.columns:
            combined[col] = df_c[col].values

    # Save
    ts = time.strftime("%Y%m%d_%H%M%S")
    outdir = Path(__file__).parent / "results"

    # Save C-only parquet
    c_parquet = outdir / f"eqa_sdmx-mcp_{MODEL}_{ts}.parquet"
    df_c.to_parquet(c_parquet, index=False)

    # Save combined 3-way parquet
    combined_parquet = outdir / f"eqa_3way_{MODEL}_{ts}.parquet"
    combined_csv = outdir / f"eqa_3way_{MODEL}_{ts}.csv"
    combined.to_parquet(combined_parquet, index=False)
    combined.to_csv(combined_csv, index=False)

    # Report
    print(f"\n{'='*70}")
    print("3-WAY COMPARISON: A (alone) vs B (unicefstats-mcp) vs C (sdmx-mcp)")
    print(f"{'='*70}")

    for prompt in ["baseline_latest", "direct"]:
        pos = combined[(combined.query_type == "POSITIVE") & (combined.prompt_type == prompt)]
        if len(pos) == 0:
            continue
        formula = "ER x YA x VA" if prompt == "baseline_latest" else "ER x VA"
        print(f"\nPositive {prompt} (n={len(pos)}) -- EQA = {formula}")
        print(f"  {'Metric':<12s} {'A (alone)':>12s} {'B (unicef)':>12s} {'C (sdmx)':>12s}")
        print(f"  {'-'*50}")
        print(f"  {'Mean EQA':<12s} {pos.eqa_a.mean():>12.3f} {pos.eqa_b.mean():>12.3f} {pos.eqa_c.mean():>12.3f}")
        print(f"  {'Mean ER':<12s} {pos.er_a.mean():>12.3f} {pos.er_b.mean():>12.3f} {pos.er_c.mean():>12.3f}")
        if prompt == "baseline_latest":
            print(f"  {'Mean YA':<12s} {pos.ya_a.mean():>12.3f} {pos.ya_b.mean():>12.3f} {pos.ya_c.mean():>12.3f}")
        print(f"  {'Mean VA':<12s} {pos.va_a.mean():>12.3f} {pos.va_b.mean():>12.3f} {pos.va_c.mean():>12.3f}")

    print(f"\nHallucination:")
    for qt in ["HALLUCINATION_T1", "HALLUCINATION_T2"]:
        h = combined[combined.query_type == qt]
        if len(h) > 0:
            print(f"  {qt} (n={len(h)}): A={h.hall_a.mean()*100:.0f}%  B={h.hall_b.mean()*100:.0f}%  C={h.hall_c.mean()*100:.0f}%")

    print(f"\nCost:")
    print(f"  A: ${combined.a_cost_usd.sum():.2f}  B: ${combined.b_cost_usd.sum():.2f}  C: ${df_c.c_cost_usd.sum():.2f}")
    print(f"  Avg tool calls B: {combined.b_n_tool_calls.mean():.1f}  C: {df_c.c_n_tool_calls.mean():.1f}")

    print(f"\nBy indicator (EQA, positive queries):")
    pos_all = combined[combined.query_type == "POSITIVE"]
    print(f"  {'Indicator':<20s} {'EQA_A':>8s} {'EQA_B':>8s} {'EQA_C':>8s}")
    print(f"  {'-'*48}")
    for ind in sorted(pos_all.indicator_code.unique()):
        sub = pos_all[pos_all.indicator_code == ind]
        print(f"  {ind:<20s} {sub.eqa_a.mean():>8.3f} {sub.eqa_b.mean():>8.3f} {sub.eqa_c.mean():>8.3f}")

    print(f"\nSaved:")
    print(f"  C-only:   {c_parquet}")
    print(f"  Combined: {combined_parquet}")
    print(f"  CSV:      {combined_csv}")


if __name__ == "__main__":
    main()
