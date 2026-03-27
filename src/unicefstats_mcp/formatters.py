"""Output formatting for UNICEF Stats MCP tools."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

# unicefdata uses iso3/country/indicator; we normalize to these canonical names
COMPACT_COLUMNS = ["iso3", "country", "period", "indicator", "value"]

# Alternative column names that unicefdata may use
COLUMN_ALIASES = {
    "country_code": "iso3",
    "country_name": "country",
    "indicator_code": "indicator",
}

DISAGGREGATION_COLUMNS = ["sex", "age", "wealth_quintile", "residence"]


def country_col(df: pd.DataFrame) -> str:
    """Detect the country column name in a unicefdata DataFrame."""
    return "iso3" if "iso3" in df.columns else "country_code"


def _clean_nans(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace NaN/inf floats with None for valid JSON serialization."""
    return [
        {k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
         for k, v in record.items()}
        for record in records
    ]


def to_compact(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Reduce DataFrame to 5 core columns."""
    # Try canonical names first, then aliases
    cols = []
    for c in COMPACT_COLUMNS:
        if c in df.columns:
            cols.append(c)
        else:
            # Check if an alias exists in the DataFrame
            for alias, canonical in COLUMN_ALIASES.items():
                if canonical == c and alias in df.columns:
                    cols.append(alias)
                    break
    return _clean_nans(df[cols].to_dict(orient="records"))


def to_full(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Return all columns as list of dicts."""
    return _clean_nans(df.to_dict(orient="records"))


def truncate_description(text: str | None, max_len: int = 150) -> str:
    """Shorten description with ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len].rstrip() + "\u2026"


def apply_limit(
    records: list[dict[str, Any]], limit: int
) -> tuple[list[dict[str, Any]], bool]:
    """Apply row limit. Returns (records, was_truncated)."""
    if len(records) <= limit:
        return records, False
    return records[:limit], True


def summarize_disaggregations(df: pd.DataFrame) -> dict[str, Any]:
    """Summarize disaggregation dimensions present in the data.

    Returns a dict of dimension → unique values found, for non-trivial dimensions.
    """
    summary: dict[str, Any] = {}
    for col in DISAGGREGATION_COLUMNS:
        if col in df.columns:
            unique = sorted(df[col].dropna().unique().tolist())
            # Only report if there's actual disaggregation (more than just _T/total)
            if len(unique) > 1 or (len(unique) == 1 and unique[0] != "_T"):
                summary[col] = unique
    return summary


def summarize_data(df: pd.DataFrame) -> dict[str, Any]:
    """Generate summary statistics for the data."""
    summary: dict[str, Any] = {}

    if "value" in df.columns:
        values = df["value"].dropna()
        if len(values) > 0:
            summary["value_range"] = {
                "min": round(float(values.min()), 2),
                "max": round(float(values.max()), 2),
                "mean": round(float(values.mean()), 2),
            }

    if "period" in df.columns:
        periods = df["period"].dropna()
        if len(periods) > 0:
            summary["year_range"] = {
                "earliest": int(periods.min()),
                "latest": int(periods.max()),
            }

    countries_col = country_col(df)
    if countries_col in df.columns:
        summary["countries_in_result"] = int(df[countries_col].nunique())

    return summary


def compute_trend(df: pd.DataFrame, window: int = 5) -> dict[str, Any] | None:
    """Compute annualized rate of change from the most recent `window` years.

    Uses compound annual growth rate (CAGR) formula:
        AARC = (V_end / V_start)^(1/years) - 1

    Returns per-country trends if multiple countries, or single trend if one.
    """
    if "period" not in df.columns or "value" not in df.columns:
        return None

    countries_col = country_col(df)
    if countries_col not in df.columns:
        return None

    trends: dict[str, Any] = {}

    for country, group in df.groupby(countries_col):
        group = group.dropna(subset=["value", "period"]).sort_values("period")
        if len(group) < 2:
            continue

        latest = group.iloc[-1]
        # Find the observation closest to `window` years before latest
        target_year = float(latest["period"]) - window
        earlier = group[group["period"] <= target_year + 0.5]
        earlier_row = group.iloc[0] if earlier.empty else earlier.iloc[-1]

        v_start = float(earlier_row["value"])
        v_end = float(latest["value"])
        n_years = float(latest["period"]) - float(earlier_row["period"])

        if n_years < 1 or v_start <= 0:
            continue

        # Annualized rate of change (AARC)
        aarc = (v_end / v_start) ** (1.0 / n_years) - 1.0

        # Direction
        if aarc < -0.005:
            direction = "declining"
        elif aarc > 0.005:
            direction = "increasing"
        else:
            direction = "flat"

        trends[str(country)] = {
            "start_year": int(earlier_row["period"]),
            "end_year": int(latest["period"]),
            "start_value": round(v_start, 2),
            "end_value": round(v_end, 2),
            "aarc": round(aarc * 100, 2),  # as percentage
            "direction": direction,
        }

    if not trends:
        return None
    return trends


def ok(data: dict[str, Any]) -> dict[str, Any]:
    """Wrap a successful response with explicit status field."""
    return {"status": "ok", **data}


def error(message: str, tip: str | None = None, no_data: bool = False) -> dict[str, Any]:
    """Wrap an error response with optional tip.

    When no_data=True, includes an explicit anti-hallucination directive.
    This tells the LLM that the absence of data is authoritative — the
    UNICEF Data Warehouse was queried and confirmed the data does not exist.
    The LLM should NOT attempt to answer from training data.
    """
    result: dict[str, Any] = {"status": "error", "error": message}
    if tip:
        result["tip"] = tip
    if no_data:
        result["data_status"] = "confirmed_absent"
        result["instruction"] = (
            "This result is authoritative: the UNICEF Data Warehouse was queried "
            "and confirmed this data does not exist. Do NOT provide an estimate "
            "from training data, other sources, or approximation. Instead, tell the "
            "user that this specific data point is not available in the UNICEF "
            "database and suggest how they might find it (e.g., national statistics "
            "office, DHS/MICS survey reports, or alternative indicator codes)."
        )
    return result
