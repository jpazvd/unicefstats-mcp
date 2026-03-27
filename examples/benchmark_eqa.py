#!/usr/bin/env python3
"""EQA benchmark: LLM alone vs. LLM + unicefstats-mcp.

Implements the Expected Query Accuracy (EQA) metric from:

    Azevedo, J.P. (2025). "AI Reliability for Official Statistics:
    Benchmarking Large Language Models with the UNICEF Data Warehouse."
    UNICEF Chief Statistician Office.
    Repository: https://github.com/jpazvd/unicef-sdg-llm-benchmark-dev

    EQA = ER × YA × VA

    Where:
      ER = 1.0 if a numeric value was extracted, 0.0 otherwise
      YA = step function on |year_error|: 0→1.0, 1→0.75, 2→0.50, 3-4→0.25, ≥5→0.0
      VA = max(0, 1 - |predicted - ground_truth| / |ground_truth|)

Two experimental conditions (both use the Anthropic Claude API):

    Condition A — LLM alone:
        Claude answers from training data only. No tools.
    Condition B — LLM + MCP:
        Claude has access to unicefstats-mcp tools (get_data, search_indicators, etc.)
        and can use them to answer the question.

Three benchmark sections:
    Section 1 — baseline_latest: "What is the latest available {indicator} for {country}?"
                Full EQA = ER × YA × VA (year accuracy matters)
    Section 2 — direct: "What was {indicator} for {country} in {year}?"
                EQA = ER × VA (YA = 1.0 since year is given)
    Section 3 — hallucination: queries for country-indicator combos with NO data
                Measures fabrication rate

Ground truth: UNICEF SDMX API (https://sdmx.data.unicef.org)

Requirements:
    pip install anthropic unicefstats-mcp
    export ANTHROPIC_API_KEY=sk-ant-...

Usage:
    python examples/benchmark_eqa.py
    python examples/benchmark_eqa.py --model claude-sonnet-4-20250514
    python examples/benchmark_eqa.py --dry-run   # skip API calls, show test cases only
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import sys
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone

warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.disable(logging.INFO)

from dotenv import load_dotenv
load_dotenv()  # loads ANTHROPIC_API_KEY from .env

import anthropic
import pandas as pd

from unicefstats_mcp.server import (
    get_data,
    get_indicator_info,
    get_temporal_coverage,
    search_indicators,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024
TEMPERATURE = 0.0  # deterministic for reproducibility

# MCP tools exposed to Claude in Condition B
MCP_TOOLS = [
    {
        "name": "search_indicators",
        "description": "Search UNICEF child development indicators by keyword. Returns indicator codes and names.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term (e.g. 'mortality', 'stunting')"},
                "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_indicator_info",
        "description": "Get full metadata for a UNICEF indicator including description, SDG target, and available disaggregations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Indicator code (e.g. 'CME_MRY0T4')"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "get_data",
        "description": "Fetch UNICEF data for an indicator and one or more countries. Returns observations with values, years, and summary statistics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "indicator": {"type": "string", "description": "Indicator code"},
                "countries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ISO3 country codes (e.g. ['BRA', 'IND'])",
                },
                "start_year": {"type": "integer", "description": "Start year filter"},
                "end_year": {"type": "integer", "description": "End year filter"},
                "format": {"type": "string", "enum": ["compact", "full"], "default": "compact"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["indicator", "countries"],
        },
    },
    {
        "name": "get_temporal_coverage",
        "description": "Check what years of data are available for a UNICEF indicator. Returns start/end year and country count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Indicator code"},
            },
            "required": ["code"],
        },
    },
]


# ---------------------------------------------------------------------------
# MCP tool dispatcher (handles tool_use blocks from the API)
# ---------------------------------------------------------------------------

def dispatch_tool(name: str, input_args: dict) -> str:
    """Call the actual MCP tool and return JSON result."""
    if name == "search_indicators":
        result = search_indicators(**input_args)
    elif name == "get_indicator_info":
        result = get_indicator_info(**input_args)
    elif name == "get_data":
        result = get_data(**input_args)
    elif name == "get_temporal_coverage":
        result = get_temporal_coverage(**input_args)
    else:
        result = {"error": f"Unknown tool: {name}"}
    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# EQA components (from Azevedo 2025)
# ---------------------------------------------------------------------------


def compute_er(value: float | None) -> float:
    return 1.0 if value is not None else 0.0


def compute_ya(predicted_year: int | None, actual_year: int | None) -> float:
    if predicted_year is None or actual_year is None:
        return 0.0
    diff = abs(predicted_year - actual_year)
    if diff == 0:
        return 1.00
    elif diff == 1:
        return 0.75
    elif diff == 2:
        return 0.50
    elif diff <= 4:
        return 0.25
    else:
        return 0.00


def compute_va(predicted: float | None, actual: float | None) -> float:
    if predicted is None or actual is None:
        return 0.0
    if abs(actual) < 1e-10:
        return 1.0 if abs(predicted) < 1e-10 else 0.0
    return max(0.0, 1.0 - min(1.0, abs(predicted - actual) / abs(actual)))


# ---------------------------------------------------------------------------
# Value/year extraction from LLM response (regex, from Azevedo 2025 Phase 1)
# ---------------------------------------------------------------------------

def extract_numeric(text: str) -> float | None:
    """Extract the primary numeric value from an LLM response.

    Follows the extraction pipeline from the benchmark paper:
    1. Check for refusal/no-data language — if found, return None
    2. Look for explicit value patterns (e.g., "is 14.4", "rate of 35.5%")
    3. Skip 4-digit numbers in 1900-2099 range (likely years)
    4. Return first valid candidate.
    """
    if not text:
        return None

    # Check for refusal language — do NOT extract numbers from refusals
    refusal_patterns = [
        r"not available",
        r"no data",
        r"does not exist",
        r"not found",
        r"cannot (find|provide|verify)",
        r"don.t have .*(data|information)",
        r"unable to (find|provide)",
        r"I apologize.*not available",
        r"confirmed.*absent",
        r"data.status.*confirmed_absent",
    ]
    text_lower = text.lower()
    for pattern in refusal_patterns:
        if re.search(pattern, text_lower):
            # Double-check: if text also contains explicit value language, extract anyway
            has_value = re.search(r"(?:is|was|rate of|approximately)\s+\d+\.?\d*\s*(?:%|per)", text, re.IGNORECASE)
            if not has_value:
                return None

    # Try JSON extraction first (for structured responses)
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "value" in data:
            v = data["value"]
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str) and v.replace(".", "").replace("-", "").isdigit():
                return float(v)
    except (json.JSONDecodeError, ValueError):
        pass

    # Pattern: "is X", "was X", "rate of X", "approximately X", "around X"
    patterns = [
        r"(?:is|was|at|of|approximately|around|about|roughly|estimated at)\s+([\d,]+\.?\d*)\s*(?:%|percent|per\s+1[,.]?000)?",
        r"([\d,]+\.?\d*)\s*(?:per\s+1[,.]?000\s+live\s+births|deaths\s+per|%|percent)",
        r"(?:value|rate|prevalence|proportion)[:\s]+([\d,]+\.?\d*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val_str = match.group(1).replace(",", "")
            try:
                val = float(val_str)
                # Skip if it looks like a year
                if 1900 <= val <= 2099 and val == int(val):
                    continue
                return val
            except ValueError:
                continue

    # Fallback: any number that isn't a year and has reasonable context
    # (skip single digits that are likely from indicator codes like "L1" or "SD")
    for match in re.finditer(r"(?<![A-Z_])(\d{2,}\.?\d*)(?![A-Z_])", text):
        val = float(match.group(1))
        if not (1900 <= val <= 2099 and val == int(val)):
            return val

    return None


def extract_year(text: str) -> int | None:
    """Extract the data year from an LLM response."""
    if not text:
        return None

    # Try JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "year" in data:
            y = data["year"]
            if isinstance(y, int):
                return y
            if isinstance(y, str) and y.isdigit():
                return int(y)
    except (json.JSONDecodeError, ValueError):
        pass

    # Pattern: "in 2023", "as of 2022", "2023 estimate", "(2022)"
    patterns = [
        r"(?:in|as of|for|from|year)\s+(20[12]\d)",
        r"(20[12]\d)\s*(?:estimate|data|figure|value|report)",
        r"\((20[12]\d)\)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    # Fallback: most recent 4-digit year
    years = [int(m) for m in re.findall(r"(20[12]\d)", text)]
    return max(years) if years else None


# ---------------------------------------------------------------------------
# API call functions
# ---------------------------------------------------------------------------


# Model pricing (input/output per 1M tokens) — for cost calculation
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
    "claude-opus-4-20250514": (15.0, 75.0),
}
DEFAULT_PRICING = (3.0, 15.0)  # fallback

EXTRACTOR_VERSION = "v1.3"  # bump when extraction logic changes

# System prompt for Condition B: report exact values, no rounding
CONDITION_B_SYSTEM = (
    "You have access to UNICEF data tools. When reporting values from tool results, "
    "report the EXACT numeric value returned by the tool — do not round, approximate, "
    "or paraphrase. If a tool returns data_status='confirmed_absent', say 'This data "
    "is not available in the UNICEF database' and do NOT provide any estimate."
)


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost from token counts."""
    in_rate, out_rate = MODEL_PRICING.get(model, DEFAULT_PRICING)
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


def _detect_refusal(text: str) -> bool:
    """Check if the response is a refusal to answer."""
    refusal_kw = [
        "not available", "no data", "does not exist", "not found",
        "cannot find", "cannot provide", "don't have", "unable to find",
        "not reported", "no reliable", "confirmed_absent",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in refusal_kw)


def _extract_from_tool_calls(tool_calls: list[dict]) -> tuple[float | None, int | None]:
    """Extract value and year from get_data tool call results.

    Parses the actual JSON returned by the MCP tool, not Claude's prose.
    This avoids rounding and extraction failures from text parsing.
    """
    # The dispatcher stored tool call info but not the result.
    # We need to re-dispatch to get the result. However, the tool_calls
    # list only has {"tool": name, "input": args}. The actual result
    # was passed back to Claude but not stored.
    #
    # Instead: re-call the tool with the same args to get the exact value.
    # This is fast (cached by unicefdata) and guarantees exact match.
    for tc in reversed(tool_calls):  # latest call first
        if tc["tool"] == "get_data":
            try:
                result = json.loads(dispatch_tool("get_data", tc["input"]))
                if "data" in result and result["data"]:
                    # Take the row with the LATEST period (not first row)
                    rows = result["data"]
                    best = max(rows, key=lambda r: r.get("period", 0))
                    value = best.get("value")
                    period = best.get("period")
                    year = int(period) if period is not None else None
                    return (float(value) if value is not None else None, year)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass
    return (None, None)


def call_llm_alone(client: anthropic.Anthropic, model: str, prompt: str) -> dict:
    """Condition A: LLM alone, no tools."""
    t0 = time.time()
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    latency = time.time() - t0
    text = response.content[0].text if response.content else ""
    input_tok = response.usage.input_tokens
    output_tok = response.usage.output_tokens
    return {
        "response": text,
        "value": extract_numeric(text),
        "year": extract_year(text),
        "refused": _detect_refusal(text),
        "latency_ms": int(latency * 1000),
        "tokens_input": input_tok,
        "tokens_output": output_tok,
        "cost_usd": _compute_cost(model, input_tok, output_tok),
    }


def call_llm_with_mcp(client: anthropic.Anthropic, model: str, prompt: str) -> dict:
    """Condition B: LLM with MCP tools. Handles tool_use loop."""
    t0 = time.time()
    messages = [{"role": "user", "content": prompt}]
    total_input = 0
    total_output = 0
    tool_calls = []
    tool_error = None

    # Multi-turn tool-use loop (max 5 rounds)
    for _ in range(5):
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=CONDITION_B_SYSTEM,
            tools=MCP_TOOLS,
            messages=messages,
        )
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens

        # Check if response contains tool_use blocks
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            break  # Final answer, no more tool calls

        # Process each tool call
        tool_results = []
        for tu in tool_uses:
            result_str = dispatch_tool(tu.name, tu.input)
            tool_calls.append({"tool": tu.name, "input": tu.input})
            # Check for tool error (confirmed_absent)
            try:
                result_parsed = json.loads(result_str)
                if result_parsed.get("data_status") == "confirmed_absent":
                    tool_error = result_parsed.get("error", "confirmed_absent")
            except (json.JSONDecodeError, AttributeError):
                pass
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result_str,
            })

        # Add assistant response + tool results to conversation
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    latency = time.time() - t0

    # Extract final text from last response
    text_blocks = [b.text for b in response.content if hasattr(b, "text")]
    text = "\n".join(text_blocks)

    # Fix 1: Extract value/year from tool call results first (JSON),
    # fall back to text extraction only if tool extraction fails.
    tool_value, tool_year = _extract_from_tool_calls(tool_calls)
    text_value = extract_numeric(text)
    text_year = extract_year(text)

    return {
        "response": text,
        "value": tool_value if tool_value is not None else text_value,
        "year": tool_year if tool_year is not None else text_year,
        "refused": _detect_refusal(text) and tool_value is None,
        "tool_error": tool_error,
        "latency_ms": int(latency * 1000),
        "tokens_input": total_input,
        "tokens_output": total_output,
        "cost_usd": _compute_cost(model, total_input, total_output),
        "tool_calls": tool_calls,
    }


# ---------------------------------------------------------------------------
# Load test cases from ground truth CSV (produced by 00_build_ground_truth.py)
# ---------------------------------------------------------------------------

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "ground_truth", "sample.csv")
GT_VALUES_CSV = os.path.join(os.path.dirname(__file__), "ground_truth", "ground_truth_values.csv")


@dataclass
class TestCase:
    indicator_code: str
    indicator_name: str
    unit: str
    country_code: str
    country_name: str
    year: int | None       # None for baseline_latest
    query_type: str        # POSITIVE, HALLUCINATION_T1, HALLUCINATION_T2
    prompt_type: str       # baseline_latest or direct
    prompt_text: str
    ground_truth_value: float | None
    ground_truth_latest_year: int | None  # for baseline_latest positive queries


def load_sample() -> list[TestCase]:
    """Load test cases from sample.csv."""
    if not os.path.exists(SAMPLE_CSV):
        print(f"ERROR: {SAMPLE_CSV} not found.")
        print("Run: python examples/00_build_ground_truth.py")
        sys.exit(1)

    df = pd.read_csv(SAMPLE_CSV)
    cases = []
    for _, row in df.iterrows():
        year = int(row["year"]) if pd.notna(row["year"]) else None
        gt_val = float(row["ground_truth_value"]) if pd.notna(row.get("ground_truth_value")) else None
        gt_latest_yr = int(row["ground_truth_latest_year"]) if pd.notna(row.get("ground_truth_latest_year")) else None
        # For baseline_latest positive queries, ground truth is the latest value
        if row["query_type"] == "POSITIVE" and row["prompt_type"] == "baseline_latest":
            gt_val = float(row["ground_truth_latest_value"]) if pd.notna(row.get("ground_truth_latest_value")) else gt_val

        cases.append(TestCase(
            indicator_code=row["indicator_code"],
            indicator_name=row["indicator_name"],
            unit=row["unit"],
            country_code=row["country_code"],
            country_name=row["country_name"],
            year=year,
            query_type=row["query_type"],
            prompt_type=row["prompt_type"],
            prompt_text=row["prompt_text"],
            ground_truth_value=gt_val,
            ground_truth_latest_year=gt_latest_yr,
        ))
    return cases


# ---------------------------------------------------------------------------
# Run benchmark
# ---------------------------------------------------------------------------


def run_queries(
    client: anthropic.Anthropic,
    model: str,
    cases: list[TestCase],
    dry_run: bool = False,
) -> list[dict]:
    """Run all benchmark queries for both conditions."""
    results = []

    for i, tc in enumerate(cases, 1):
        is_positive = tc.query_type == "POSITIVE"
        use_ya = tc.prompt_type == "baseline_latest" and is_positive
        label = f"{tc.indicator_code} x {tc.country_code} ({tc.query_type[:4]})"
        print(f"  [{i:3d}/{len(cases)}] {label:<40s}", end="", flush=True)

        # Ground truth from CSV (already verified by 00_build_ground_truth.py)
        gt_val = tc.ground_truth_value
        gt_year = tc.ground_truth_latest_year if tc.prompt_type == "baseline_latest" else tc.year

        if dry_run:
            gt_s = f"GT={gt_val:.1f}" if gt_val is not None else "GT=N/A"
            print(f"  {gt_s} yr={gt_year}  [dry run]")
            results.append({"tc": tc, "gt_val": gt_val, "gt_year": gt_year, "dry_run": True})
            continue

        # --- Condition A: LLM alone ---
        resp_a = call_llm_alone(client, model, tc.prompt_text)

        # --- Condition B: LLM + MCP tools ---
        resp_b = call_llm_with_mcp(client, model, tc.prompt_text)

        # --- Score ---
        er_a = compute_er(resp_a["value"])
        er_b = compute_er(resp_b["value"])

        if use_ya:
            ya_a = compute_ya(resp_a["year"], gt_year)
            ya_b = compute_ya(resp_b["year"], gt_year)
        else:
            ya_a = 1.0
            ya_b = 1.0

        va_a = compute_va(resp_a["value"], gt_val) if is_positive else 0.0
        va_b = compute_va(resp_b["value"], gt_val) if is_positive else 0.0

        eqa_a = er_a * ya_a * va_a
        eqa_b = er_b * ya_b * va_b

        # For hallucination cases: did it fabricate a value?
        hall_a = resp_a["value"] is not None and not is_positive
        hall_b = resp_b["value"] is not None and not is_positive

        row = {
            "tc": tc,
            "query_type": tc.query_type,
            "prompt_type": tc.prompt_type,
            "gt_val": gt_val, "gt_year": gt_year,
            # Condition A
            "a_value": resp_a["value"], "a_year": resp_a["year"],
            "a_response_full": resp_a["response"],
            "a_refused": resp_a["refused"],
            "a_tokens_input": resp_a["tokens_input"],
            "a_tokens_output": resp_a["tokens_output"],
            "a_cost_usd": resp_a["cost_usd"],
            "a_latency": resp_a["latency_ms"],
            # Condition B
            "b_value": resp_b["value"], "b_year": resp_b["year"],
            "b_response_full": resp_b["response"],
            "b_refused": resp_b["refused"],
            "b_tool_error": resp_b.get("tool_error"),
            "b_tokens_input": resp_b["tokens_input"],
            "b_tokens_output": resp_b["tokens_output"],
            "b_cost_usd": resp_b["cost_usd"],
            "b_latency": resp_b["latency_ms"],
            "b_tool_calls": resp_b.get("tool_calls", []),
            # Scoring
            "er_a": er_a, "ya_a": ya_a, "va_a": va_a, "eqa_a": eqa_a,
            "er_b": er_b, "ya_b": ya_b, "va_b": va_b, "eqa_b": eqa_b,
            "hall_a": hall_a, "hall_b": hall_b,
        }
        results.append(row)

        # Print inline
        if is_positive and gt_val is not None:
            v_a = f"{resp_a['value']:.1f}" if resp_a["value"] else "???"
            v_b = f"{resp_b['value']:.1f}" if resp_b["value"] else "???"
            tools_used = len(resp_b.get("tool_calls", []))
            print(f"  GT={gt_val:7.1f}  A={v_a:>7s}(EQA={eqa_a:.3f})  B={v_b:>7s}(EQA={eqa_b:.3f}) [{tools_used} tools]")
        elif not is_positive:
            h_a = "HALLUCINATED" if hall_a else "refused"
            h_b = "HALLUCINATED" if hall_b else "refused"
            print(f"  [no data]  A: {h_a:<15s}  B: {h_b}")
        else:
            print("  no ground truth")

    return results


def print_summary(name: str, results: list[dict], use_ya: bool):
    scored = [r for r in results if not r.get("dry_run") and r["tc"].query_type == "POSITIVE" and r["gt_val"] is not None]
    if not scored:
        return

    n = len(scored)
    metrics = {
        "Mean EQA": ("eqa_a", "eqa_b"),
        "Mean ER": ("er_a", "er_b"),
    }
    if use_ya:
        metrics["Mean YA"] = ("ya_a", "ya_b")
    metrics["Mean VA"] = ("va_a", "va_b")

    print(f"\n  {name} SUMMARY (n={n})")
    print(f"  {'Metric':<20s} {'LLM alone':>12s} {'LLM + MCP':>12s} {'Gain':>10s}")
    print(f"  {'-' * 57}")
    for label, (ka, kb) in metrics.items():
        ma = sum(r[ka] for r in scored) / n
        mb = sum(r[kb] for r in scored) / n
        print(f"  {label:<20s} {ma:>12.3f} {mb:>12.3f} {mb - ma:>+10.3f}")

    # Latency, tokens, cost
    avg_lat_a = sum(r["a_latency"] for r in scored) / n
    avg_lat_b = sum(r["b_latency"] for r in scored) / n
    avg_tok_a = sum(r["a_tokens_input"] + r["a_tokens_output"] for r in scored) / n
    avg_tok_b = sum(r["b_tokens_input"] + r["b_tokens_output"] for r in scored) / n
    total_cost_a = sum(r["a_cost_usd"] for r in scored)
    total_cost_b = sum(r["b_cost_usd"] for r in scored)
    print(f"  {'Avg latency (ms)':<20s} {avg_lat_a:>12.0f} {avg_lat_b:>12.0f}")
    print(f"  {'Avg tokens':<20s} {avg_tok_a:>12.0f} {avg_tok_b:>12.0f}")
    print(f"  {'Total cost (USD)':<20s} {total_cost_a:>11.4f}$ {total_cost_b:>11.4f}$")


def print_hallucination_summary(results: list[dict]):
    hall_cases = [r for r in results if not r.get("dry_run") and r["tc"].query_type != "POSITIVE"]
    if not hall_cases:
        return
    n = len(hall_cases)
    h_a = sum(1 for r in hall_cases if r["hall_a"])
    h_b = sum(1 for r in hall_cases if r["hall_b"])
    print(f"\n  HALLUCINATION SUMMARY (n={n})")
    print(f"  {'Metric':<30s} {'LLM alone':>12s} {'LLM + MCP':>12s}")
    print(f"  {'-' * 56}")
    print(f"  {'Fabrications':<30s} {h_a:>12d} {h_b:>12d}")
    print(f"  {'Correct refusals':<30s} {n - h_a:>12d} {n - h_b:>12d}")
    print(f"  {'Hallucination rate':<30s} {h_a / n * 100:>11.0f}% {h_b / n * 100:>11.0f}%")


def main():
    parser = argparse.ArgumentParser(description="EQA benchmark: LLM alone vs. LLM + MCP")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Anthropic model (default: {DEFAULT_MODEL})")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, show test cases only")
    parser.add_argument("--limit", type=int, default=0, help="Limit queries per section (0=all)")
    parser.add_argument("--ground-truth", default=None, help="Path to sample.csv (default: examples/ground_truth/sample.csv)")
    parser.add_argument("--tag", default="", help="Tag appended to output filenames (e.g. 'r2')")
    args = parser.parse_args()

    # Override ground truth path if specified
    if args.ground_truth:
        global SAMPLE_CSV, GT_VALUES_CSV
        SAMPLE_CSV = args.ground_truth
        gt_dir = os.path.dirname(args.ground_truth)
        GT_VALUES_CSV = os.path.join(gt_dir, "ground_truth_values.csv")

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    # Load test cases from ground truth CSV
    all_cases = load_sample()

    # Split into sections
    positive_cases = [c for c in all_cases if c.query_type == "POSITIVE"]
    hall_t1_cases = [c for c in all_cases if c.query_type == "HALLUCINATION_T1"]
    hall_t2_cases = [c for c in all_cases if c.query_type == "HALLUCINATION_T2"]

    if args.limit > 0:
        positive_cases = positive_cases[:args.limit]
        hall_t1_cases = hall_t1_cases[:args.limit]
        hall_t2_cases = hall_t2_cases[:args.limit]

    total = len(positive_cases) + len(hall_t1_cases) + len(hall_t2_cases)

    print("=" * 90)
    print("UNICEF Stats MCP — EQA Benchmark")
    print("=" * 90)
    print()
    print("Metric: EQA = ER x YA x VA  (Azevedo 2025)")
    print("  Azevedo, J.P. (2025). 'AI Reliability for Official Statistics:")
    print("  Benchmarking LLMs with the UNICEF Data Warehouse.'")
    print("  https://github.com/jpazvd/unicef-sdg-llm-benchmark-dev")
    print()
    print(f"Model:            {args.model}")
    print(f"Temperature:      {TEMPERATURE}")
    print(f"Timestamp:        {datetime.now(timezone.utc).isoformat()}")
    print(f"Condition A:      LLM alone (no tools)")
    print(f"Condition B:      LLM + unicefstats-mcp tools")
    print(f"Ground truth:     {SAMPLE_CSV}")
    print(f"Total queries:    {total} (positive={len(positive_cases)}, T1={len(hall_t1_cases)}, T2={len(hall_t2_cases)})")
    print()

    if args.dry_run:
        print("[DRY RUN — no API calls]\n")
        client = None
    else:
        client = anthropic.Anthropic()
        if not client.api_key:
            print("ERROR: ANTHROPIC_API_KEY not set.")
            print("  Option 1: export ANTHROPIC_API_KEY=sk-ant-...")
            print("  Option 2: create .env file with ANTHROPIC_API_KEY=...")
            print("  Option 3: --dry-run to verify test cases without API calls")
            sys.exit(1)

    all_results = []

    # --- Section 1: POSITIVE queries ---
    print("=" * 90)
    print(f"SECTION 1: POSITIVE queries (n={len(positive_cases)})")
    print("  baseline_latest: EQA = ER x YA x VA")
    print("=" * 90)
    s1 = run_queries(client, args.model, positive_cases, dry_run=args.dry_run)
    # Split summary by prompt type
    s1_latest = [r for r in s1 if not r.get("dry_run") and r.get("prompt_type") == "baseline_latest"]
    if s1_latest:
        print_summary("POSITIVE (baseline_latest)", s1_latest, use_ya=True)
    all_results.extend(s1)

    # --- Section 2: HALLUCINATION_T1 (gap years) ---
    if hall_t1_cases:
        print("\n" + "=" * 90)
        print(f"SECTION 2: HALLUCINATION_T1 — gap years (n={len(hall_t1_cases)})")
        print("  Country-indicator pair exists but specific year has no data.")
        print("=" * 90)
        s2 = run_queries(client, args.model, hall_t1_cases, dry_run=args.dry_run)
        print_hallucination_summary(s2)
        all_results.extend(s2)

    # --- Section 3: HALLUCINATION_T2 (never existed) ---
    if hall_t2_cases:
        print("\n" + "=" * 90)
        print(f"SECTION 3: HALLUCINATION_T2 — never existed (n={len(hall_t2_cases)})")
        print("  Country-indicator pair has never been reported in the Data Warehouse.")
        print("=" * 90)
        s3 = run_queries(client, args.model, hall_t2_cases, dry_run=args.dry_run)
        print_hallucination_summary(s3)
        all_results.extend(s3)

    # --- Overall ---
    print("\n" + "=" * 90)
    print("OVERALL SUMMARY")
    print("=" * 90)

    scored = [r for r in all_results if not r.get("dry_run") and r.get("query_type") == "POSITIVE" and r.get("gt_val") is not None]
    if scored:
        n = len(scored)
        mean_a = sum(r["eqa_a"] for r in scored) / n
        mean_b = sum(r["eqa_b"] for r in scored) / n
        print(f"\n  Positive queries EQA (n={n})")
        print(f"  {'':>25s} {'LLM alone':>12s} {'LLM + MCP':>12s}")
        print(f"  {'-' * 51}")
        print(f"  {'Mean EQA':<25s} {mean_a:>12.3f} {mean_b:>12.3f}")

    hall_all = [r for r in all_results if not r.get("dry_run") and r.get("query_type", "").startswith("HALLUCINATION")]
    if hall_all:
        print()
        print_hallucination_summary(hall_all)
        # Also by type
        for htype in ["HALLUCINATION_T1", "HALLUCINATION_T2"]:
            subset = [r for r in hall_all if r.get("query_type") == htype]
            if subset:
                n = len(subset)
                h_a = sum(1 for r in subset if r["hall_a"])
                h_b = sum(1 for r in subset if r["hall_b"])
                print(f"    {htype}: A={h_a}/{n} ({h_a/n*100:.0f}%)  B={h_b}/{n} ({h_b/n*100:.0f}%)")

    # --- Save results ---
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_slug = args.model.replace("/", "_").replace(":", "_")
    tag = f"_{args.tag}" if args.tag else ""
    run_id = f"{model_slug}_{ts}{tag}"

    # Build flat rows with everything
    rows = []
    for r in all_results:
        if r.get("dry_run"):
            continue
        tc = r["tc"]
        query_id = f"{tc.indicator_code}_{tc.country_code}_{tc.year}_{tc.prompt_type}"
        rows.append({
            # --- Run metadata ---
            "run_id": run_id,
            "query_id": query_id,
            "model": args.model,
            "temperature": TEMPERATURE,
            "timestamp": ts,
            "extractor_version": EXTRACTOR_VERSION,
            # --- Query identity ---
            "indicator_code": tc.indicator_code,
            "indicator_name": tc.indicator_name,
            "unit": tc.unit,
            "country_code": tc.country_code,
            "country_name": tc.country_name,
            "year": tc.year,
            "query_type": tc.query_type,
            "prompt_type": tc.prompt_type,
            "prompt_text": tc.prompt_text,
            # --- Ground truth (from verified CSV) ---
            "gt_value": r["gt_val"],
            "gt_year": r["gt_year"],
            "gt_latest_year": tc.ground_truth_latest_year,
            "gt_latest_value": tc.ground_truth_value,
            # --- Condition A: LLM alone (raw) ---
            "a_response_full": r.get("a_response_full", ""),
            "a_tokens_input": r["a_tokens_input"],
            "a_tokens_output": r["a_tokens_output"],
            "a_cost_usd": r["a_cost_usd"],
            "a_latency_ms": r["a_latency"],
            "a_refused": r["a_refused"],
            # --- Condition A: extraction ---
            "a_extracted_value": r["a_value"],
            "a_extracted_year": r["a_year"],
            # --- Condition B: LLM + MCP (raw) ---
            "b_response_full": r.get("b_response_full", ""),
            "b_tokens_input": r["b_tokens_input"],
            "b_tokens_output": r["b_tokens_output"],
            "b_cost_usd": r["b_cost_usd"],
            "b_latency_ms": r["b_latency"],
            "b_refused": r["b_refused"],
            "b_tool_error": r.get("b_tool_error"),
            "b_tool_calls_json": json.dumps(r.get("b_tool_calls", []), default=str),
            "b_n_tool_calls": len(r.get("b_tool_calls", [])),
            # --- Condition B: extraction ---
            "b_extracted_value": r["b_value"],
            "b_extracted_year": r["b_year"],
            # --- EQA scoring ---
            "er_a": r["er_a"], "ya_a": r["ya_a"], "va_a": r["va_a"], "eqa_a": r["eqa_a"],
            "er_b": r["er_b"], "ya_b": r["ya_b"], "va_b": r["va_b"], "eqa_b": r["eqa_b"],
            # --- Hallucination ---
            "hall_a": r["hall_a"],
            "hall_b": r["hall_b"],
        })

    df = pd.DataFrame(rows)

    if df.empty:
        print("\n  No results to save (dry run or all queries failed).")
        return

    # Save parquet (full archive — primary output)
    parquet_file = os.path.join(out_dir, f"eqa_{run_id}.parquet")
    df.to_parquet(parquet_file, index=False, engine="pyarrow")

    # Save CSV (same data, for quick inspection)
    csv_file = os.path.join(out_dir, f"eqa_{run_id}.csv")
    df.to_csv(csv_file, index=False)

    # Save JSON (metadata + summary, no full responses)
    json_file = os.path.join(out_dir, f"eqa_{run_id}.json")
    summary = {
        "run_id": run_id,
        "model": args.model,
        "temperature": TEMPERATURE,
        "timestamp": ts,
        "n_queries": len(df),
        "n_positive": len(df[df["query_type"] == "POSITIVE"]),
        "n_hallucination_t1": len(df[df["query_type"] == "HALLUCINATION_T1"]),
        "n_hallucination_t2": len(df[df["query_type"] == "HALLUCINATION_T2"]),
        "ground_truth_source": SAMPLE_CSV,
    }
    # Add aggregate metrics
    pos = df[df["query_type"] == "POSITIVE"]
    if len(pos) > 0:
        summary["positive_metrics"] = {
            "mean_eqa_a": round(float(pos["eqa_a"].mean()), 4),
            "mean_eqa_b": round(float(pos["eqa_b"].mean()), 4),
            "mean_er_a": round(float(pos["er_a"].mean()), 4),
            "mean_ya_a": round(float(pos["ya_a"].mean()), 4),
            "mean_va_a": round(float(pos["va_a"].mean()), 4),
        }
    hall = df[df["query_type"].str.startswith("HALLUCINATION")]
    if len(hall) > 0:
        summary["hallucination_metrics"] = {
            "rate_a": round(float(hall["hall_a"].mean()), 4),
            "rate_b": round(float(hall["hall_b"].mean()), 4),
        }
    with open(json_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Results saved:")
    print(f"    Parquet: {parquet_file} ({os.path.getsize(parquet_file) / 1024:.0f} KB)")
    print(f"    CSV:     {csv_file}")
    print(f"    JSON:    {json_file} (summary only)")


if __name__ == "__main__":
    main()
