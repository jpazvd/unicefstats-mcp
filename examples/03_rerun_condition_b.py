"""Re-run Condition B only (LLM + MCP) on the same 300 queries.

Reuses Condition A responses from the v1.3 parquet. Only runs new B
calls with the updated unicefstats-mcp v0.3.0 + unicefdata v2.4.0.

Produces a combined parquet with old A + new B for direct comparison.

Usage:
    python examples/03_rerun_condition_b.py
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import time
import warnings
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.disable(logging.INFO)

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent / ".env")

import anthropic
import pandas as pd

from unicefstats_mcp.server import (
    get_data,
    get_indicator_info,
    get_temporal_coverage,
    search_indicators,
    list_categories,
    list_countries,
    get_api_reference,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2048
TEMPERATURE = 0.0
MAX_TOOL_ROUNDS = 5

BASE_PARQUET = Path(__file__).parent / "results" / "eqa_claude-sonnet-4-20250514_20260323_174311.parquet"

SYSTEM_PROMPT_B = (
    "You are a data analyst with access to UNICEF statistics tools. "
    "Use the tools to answer questions about child development indicators. "
    "Report the EXACT numeric value from the tool response — do NOT round or approximate. "
    "If a tool returns no data or an error with data_status='confirmed_absent', "
    "say 'Data not available in the UNICEF Data Warehouse' — do NOT estimate from memory."
)

MCP_TOOLS = [
    {
        "name": "search_indicators",
        "description": "Search UNICEF child development indicators by keyword. Returns codes and names. Always start here if you don't know the indicator code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword (e.g. 'mortality', 'stunting')"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_indicator_info",
        "description": "Get full metadata for a UNICEF indicator: description, disaggregations, SDMX details, related indicators, SDG targets.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Indicator code (e.g. 'CME_MRY0T4')"}},
            "required": ["code"],
        },
    },
    {
        "name": "get_temporal_coverage",
        "description": "Check what years of data are available for a UNICEF indicator. Use before get_data() to pick a year range.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
    },
    {
        "name": "get_data",
        "description": (
            "Fetch UNICEF data for an indicator and countries. Returns observations with optional "
            "disaggregation filters. Use format='compact' (default) for a clean 5-column table."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "indicator": {"type": "string", "description": "Indicator code"},
                "countries": {"type": "array", "items": {"type": "string"}, "description": "ISO3 codes (max 30)"},
                "start_year": {"type": "integer"},
                "end_year": {"type": "integer"},
                "sex": {"type": "string", "default": "_T"},
                "format": {"type": "string", "default": "compact", "enum": ["compact", "full"]},
                "limit": {"type": "integer", "default": 200},
            },
            "required": ["indicator", "countries"],
        },
    },
    {
        "name": "list_countries",
        "description": "List all countries with ISO3 codes.",
        "input_schema": {
            "type": "object",
            "properties": {"region": {"type": "string"}},
        },
    },
    {
        "name": "get_api_reference",
        "description": "Get the unicefdata package API reference for Python, R, or Stata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "default": "python"},
                "function": {"type": "string"},
            },
        },
    },
]

TOOL_DISPATCH = {
    "search_indicators": search_indicators,
    "get_indicator_info": get_indicator_info,
    "get_temporal_coverage": get_temporal_coverage,
    "get_data": get_data,
    "list_categories": list_categories,
    "list_countries": list_countries,
    "get_api_reference": get_api_reference,
}


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_numeric(text: str) -> tuple[float | None, int | None, bool]:
    """Extract value and year from LLM response."""
    refusal_patterns = [
        r"not available", r"no data", r"cannot find", r"don't have",
        r"unable to", r"does not exist", r"not found", r"confirmed.absent",
        r"data is not available", r"couldn't find", r"not .* available",
    ]
    for pat in refusal_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return None, None, True

    value = None
    year = None

    year_match = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", text)
    if year_match:
        year = int(year_match.group(1))

    val_patterns = [
        r"\*\*(\d+\.?\d*)\*\*",
        r"(?:is|was|rate.*?)\s*\**(\d+\.?\d*)\**",
        r"(\d+\.?\d*)\s*(?:deaths|per\s+1[,.]?000|percent|%)",
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


def extract_from_tool_json(tool_calls_log: list[dict]) -> tuple[float | None, int | None]:
    """Extract value and year directly from tool call results (more accurate than text parsing)."""
    for entry in reversed(tool_calls_log):
        if entry.get("name") != "get_data":
            continue
        result = entry.get("result")
        if not isinstance(result, dict):
            continue
        data = result.get("data", [])
        if not data:
            continue
        # Take the row with the latest period
        latest = max(data, key=lambda r: r.get("period", 0))
        value = latest.get("value")
        period = latest.get("period")
        year = int(float(period)) if period is not None else None
        return (float(value) if value is not None else None), year
    return None, None


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_condition_b(row: pd.Series, client: anthropic.Anthropic) -> dict:
    """Run a single Condition B query."""
    indicator = row["indicator_code"]
    country = row["country_code"]
    country_name = row.get("country_name", country)
    year = row.get("year")
    prompt_type = row.get("prompt_type", "baseline_latest")
    query_type = row.get("query_type", "POSITIVE")

    if prompt_type == "direct" and pd.notna(year):
        prompt = f"What was the value of UNICEF indicator {indicator} for {country_name} ({country}) in {int(year)}? Give the exact number."
    else:
        prompt = f"What is the latest available value of UNICEF indicator {indicator} for {country_name} ({country})? Give the exact number and the year."

    t0 = time.time()
    messages = [{"role": "user", "content": prompt}]
    tokens_in = 0
    tokens_out = 0
    n_tool_calls = 0
    tool_calls_log = []
    tool_errors = []
    resp = None

    for _round in range(MAX_TOOL_ROUNDS):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT_B,
                tools=MCP_TOOLS,
                messages=messages,
                temperature=TEMPERATURE,
            )
        except Exception as exc:
            tool_errors.append(str(exc))
            break

        tokens_in += resp.usage.input_tokens
        tokens_out += resp.usage.output_tokens

        if resp.stop_reason == "end_turn":
            break

        if resp.stop_reason == "tool_use":
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    n_tool_calls += 1
                    fn = TOOL_DISPATCH.get(block.name)
                    if fn is None:
                        result_str = json.dumps({"error": f"Unknown tool: {block.name}"})
                    else:
                        try:
                            result = fn(**block.input)
                            tool_calls_log.append({"name": block.name, "args": block.input, "result": result})
                            result_str = json.dumps(result, default=str, ensure_ascii=False)
                        except Exception as exc:
                            result_str = json.dumps({"error": str(exc)})
                            tool_errors.append(str(exc))

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str[:8000],
                    })

            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    latency_ms = int((time.time() - t0) * 1000)

    final_text = ""
    if resp and resp.content:
        for block in resp.content:
            if hasattr(block, "text"):
                final_text += block.text

    # Try tool JSON extraction first, fall back to text extraction
    b_value, b_year = extract_from_tool_json(tool_calls_log)
    b_refused = False
    if b_value is None:
        b_value, b_year, b_refused = extract_numeric(final_text)

    return {
        "b_extracted_value": b_value,
        "b_extracted_year": b_year,
        "b_refused": b_refused,
        "b_response_full": final_text[:500],
        "b_tokens_input": tokens_in,
        "b_tokens_output": tokens_out,
        "b_latency_ms": latency_ms,
        "b_n_tool_calls": n_tool_calls,
        "b_tool_error": "; ".join(tool_errors) if tool_errors else None,
    }


def score_eqa(row: pd.Series) -> dict:
    """Score a single row's B condition with EQA metric."""
    extracted = row["b_extracted_value"]
    ext_year = row["b_extracted_year"]
    gt_val = row["gt_latest_value"] if pd.notna(row.get("gt_latest_value")) else row.get("gt_value")
    gt_yr = row["gt_latest_year"] if pd.notna(row.get("gt_latest_year")) else row.get("gt_year")
    qt = row["query_type"]

    if qt.startswith("HALLUCINATION"):
        hall = 1 if pd.notna(extracted) and not row["b_refused"] else 0
        return {"er_b": 0, "ya_b": 0, "va_b": 0, "eqa_b": 0, "hall_b": hall}

    er = 1.0 if pd.notna(extracted) else 0.0

    if row.get("prompt_type") == "direct":
        ya = 1.0
    elif pd.notna(ext_year) and pd.notna(gt_yr):
        diff = abs(int(ext_year) - int(gt_yr))
        ya = {0: 1.0, 1: 0.75, 2: 0.50}.get(diff, 0.25 if diff <= 4 else 0.0)
    else:
        ya = 0.0

    if pd.notna(extracted) and pd.notna(gt_val) and gt_val != 0:
        va = max(0.0, 1.0 - abs(extracted - gt_val) / abs(gt_val))
    else:
        va = 0.0

    return {"er_b": er, "ya_b": ya, "va_b": va, "eqa_b": er * ya * va, "hall_b": 0}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    client = anthropic.Anthropic()
    if not client.api_key:
        print("ERROR: ANTHROPIC_API_KEY not found")
        return

    if not BASE_PARQUET.exists():
        print(f"ERROR: {BASE_PARQUET} not found")
        return

    base = pd.read_parquet(BASE_PARQUET)
    print(f"Loaded {len(base)} queries from {BASE_PARQUET.name}")
    print(f"  Reusing Condition A from this parquet (extractor: {base.extractor_version.iloc[0]})")

    import unicefdata
    print(f"  unicefdata version: {unicefdata.__version__}")
    import unicefstats_mcp
    print(f"  unicefstats-mcp version: {unicefstats_mcp.__version__}")
    print(f"  Model: {MODEL}")
    print(f"  Running Condition B only (300 queries)")

    print(f"\n{'='*70}")
    print("CONDITION B: LLM + unicefstats-mcp v0.3.0 + unicefdata v2.4.0")
    print(f"{'='*70}")

    new_b_rows = []
    total = len(base)

    for idx, row in base.iterrows():
        i = len(new_b_rows) + 1
        print(f"  [{i:>3d}/{total}] {row['indicator_code']} x {row['country_code']} ({row['query_type'][:4]}) ", end="", flush=True)

        b_result = run_condition_b(row, client)
        b_scores = score_eqa(pd.Series({**row.to_dict(), **b_result}))

        new_b_rows.append({**b_result, **b_scores})
        print(f"({b_result['b_latency_ms']}ms, {b_result['b_n_tool_calls']} calls) val={b_result['b_extracted_value']} yr={b_result['b_extracted_year']}")

    # Merge new B into base (keep old A, replace B)
    new_b_df = pd.DataFrame(new_b_rows)
    combined = base.copy()
    b_cols = ["b_extracted_value", "b_extracted_year", "b_refused", "b_response_full",
              "b_tokens_input", "b_tokens_output", "b_latency_ms", "b_n_tool_calls",
              "b_tool_error", "er_b", "ya_b", "va_b", "eqa_b", "hall_b"]
    for col in b_cols:
        combined[col] = new_b_df[col].values

    combined["b_cost_usd"] = new_b_df["b_tokens_input"] * 3e-6 + new_b_df["b_tokens_output"] * 15e-6
    combined["extractor_version"] = "v2.0"

    # Save
    ts = time.strftime("%Y%m%d_%H%M%S")
    outdir = Path(__file__).parent / "results"
    parquet_path = outdir / f"eqa_v030_claude-sonnet-4-20250514_{ts}.parquet"
    csv_path = outdir / f"eqa_v030_claude-sonnet-4-20250514_{ts}.csv"

    combined.to_parquet(parquet_path, index=False)
    combined.to_csv(csv_path, index=False)

    # Report
    print(f"\n{'='*70}")
    print("RESULTS: v1.3 B (old) vs v0.3.0 B (new)")
    print(f"{'='*70}")

    for prompt in ["baseline_latest", "direct"]:
        pos = combined[(combined.query_type == "POSITIVE") & (combined.prompt_type == prompt)]
        if len(pos) == 0:
            continue
        old_pos = base[(base.query_type == "POSITIVE") & (base.prompt_type == prompt)]
        formula = "ER x YA x VA" if prompt == "baseline_latest" else "ER x VA"
        print(f"\nPositive {prompt} (n={len(pos)}) -- EQA = {formula}")
        print(f"  {'Metric':<12s} {'A (alone)':>12s} {'B (v1.3)':>12s} {'B (v0.3.0)':>12s} {'Delta':>10s}")
        print(f"  {'-'*58}")
        print(f"  {'Mean EQA':<12s} {pos.eqa_a.mean():>12.3f} {old_pos.eqa_b.mean():>12.3f} {pos.eqa_b.mean():>12.3f} {pos.eqa_b.mean()-old_pos.eqa_b.mean():>+10.3f}")

    print(f"\nHallucination:")
    for qt in ["HALLUCINATION_T1", "HALLUCINATION_T2"]:
        h = combined[combined.query_type == qt]
        old_h = base[base.query_type == qt]
        if len(h) > 0:
            print(f"  {qt}: A={h.hall_a.mean()*100:.0f}%  B(v1.3)={old_h.hall_b.mean()*100:.0f}%  B(v0.3.0)={h.hall_b.mean()*100:.0f}%")

    print(f"\nBy indicator (EQA, positive queries):")
    pos_all = combined[combined.query_type == "POSITIVE"]
    old_pos_all = base[base.query_type == "POSITIVE"]
    print(f"  {'Indicator':<20s} {'A':>8s} {'B(v1.3)':>8s} {'B(v0.3)':>8s} {'Delta':>8s}")
    print(f"  {'-'*56}")
    for ind in sorted(pos_all.indicator_code.unique()):
        sub = pos_all[pos_all.indicator_code == ind]
        old_sub = old_pos_all[old_pos_all.indicator_code == ind]
        d = sub.eqa_b.mean() - old_sub.eqa_b.mean()
        print(f"  {ind:<20s} {sub.eqa_a.mean():>8.3f} {old_sub.eqa_b.mean():>8.3f} {sub.eqa_b.mean():>8.3f} {d:>+8.3f}")

    print(f"\nCost: B(v0.3.0)=${combined.b_cost_usd.sum():.2f}")
    print(f"\nSaved:")
    print(f"  {parquet_path}")
    print(f"  {csv_path}")


if __name__ == "__main__":
    main()
