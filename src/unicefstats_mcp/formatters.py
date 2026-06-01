"""Output formatting for UNICEF Stats MCP tools."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

# unicefdata uses iso3/country/indicator; we normalize to these canonical names
COMPACT_COLUMNS = ["iso3", "country", "period", "indicator", "value"]

# Alternative column names that unicefdata may use. The first three are
# from the v0.x simplified path (`simplify=True`); the v1.2.0 raw=True
# path returns SDMX-grade uppercase names (`REF_AREA`, `TIME_PERIOD`,
# `OBS_VALUE`, …) which need the same renaming. Keeping both shapes here
# means `to_compact` / `to_full` work transparently for either path.
COLUMN_ALIASES = {
    "country_code": "iso3",
    "country_name": "country",
    "indicator_code": "indicator",
    # v1.2.0 — raw=True / SDMX shape
    "REF_AREA": "iso3",
    "TIME_PERIOD": "period",
    "OBS_VALUE": "value",
    "INDICATOR": "indicator",
}

DISAGGREGATION_COLUMNS = ["sex", "age", "wealth_quintile", "residence"]

# v1.2.0 Commit 7: canonical lowercase shape used by every downstream
# helper (`summarize_data`, `summarize_disaggregations`, `compute_trend`,
# `_seed_data_frontier_cache`, `_max_year_from_periods`, the sparse-year
# warning, `countries_returned_with_names`, `to_compact`, `to_full`).
# `unicefdata.unicefData(simplify=True)` returns these names; the v1.2.0
# `raw=True` path returns SDMX-grade uppercase names. `normalize_columns`
# (below) renames the raw shape to the canonical shape exactly once so
# every helper sees one consistent vocabulary.
RAW_TO_CANONICAL = {
    "REF_AREA": "iso3",
    "TIME_PERIOD": "period",
    "OBS_VALUE": "value",
    "INDICATOR": "indicator",
    "SEX": "sex",
    "AGE": "age",
    "WEALTH_QUINTILE": "wealth_quintile",
    "RESIDENCE": "residence",
    "DATA_SOURCE": "data_source",
    "HEAD_OF_HOUSE": "head_of_house",
    "MATERNAL_EDU_LVL": "maternal_edu_lvl",
    "EDUCATION_LEVEL": "education_level",
    "DISABILITY_STATUS": "disability_status",
    "SDG_INDICATOR": "sdg_indicator",
    "SKILL_TYPE": "skill_type",
    "OBS_STATUS": "obs_status",
    "OBS_CONF": "obs_conf",
    "LOWER_BOUND": "lower_bound",
    "UPPER_BOUND": "upper_bound",
    "UNIT_MEASURE": "unit_measure",
    "UNIT_MULTIPLIER": "unit_multiplier",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename SDMX-shape uppercase columns to canonical lowercase.

    Idempotent. Already-canonical DataFrames pass through unchanged.
    Apply once in ``get_data`` right after the fetch + post-filter
    pipeline so every downstream helper (summary, trend, frontier
    cache seed, sparse-year warning, country-name lookup) and every
    formatter (`to_compact`, `to_full`) sees one consistent column
    vocabulary regardless of which fetch path produced the data.
    """
    rename = {a: c for a, c in RAW_TO_CANONICAL.items() if a in df.columns}
    return df.rename(columns=rename) if rename else df


def country_col(df: pd.DataFrame) -> str:
    """Detect the country column name in a unicefdata DataFrame."""
    if "iso3" in df.columns:
        return "iso3"
    if "country_code" in df.columns:
        return "country_code"
    # v1.2.0 — raw=True / SDMX shape
    if "REF_AREA" in df.columns:
        return "REF_AREA"
    return "country_code"  # legacy fallback


def _clean_nans(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace NaN/inf floats with None for valid JSON serialization."""
    return [
        {
            k: (
                None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v
            )
            for k, v in record.items()
        }
        for record in records
    ]


def to_compact(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Reduce DataFrame to 5 core columns.

    Accepts either the v0.x simplified shape (`iso3`/`country_code` etc.)
    or the v1.2.0 raw=True / SDMX shape (`REF_AREA`/`OBS_VALUE` etc.).
    Columns are renamed to the canonical names before emission so the
    LLM-facing keys (`iso3`, `period`, `value`, …) stay consistent
    across paths.
    """
    cols: list[str] = []
    rename: dict[str, str] = {}
    for c in COMPACT_COLUMNS:
        if c in df.columns:
            cols.append(c)
        else:
            for alias, canonical in COLUMN_ALIASES.items():
                if canonical == c and alias in df.columns:
                    cols.append(alias)
                    rename[alias] = canonical
                    break
    sub = df[cols]
    if rename:
        sub = sub.rename(columns=rename)
    return _clean_nans(sub.to_dict(orient="records"))


def to_full(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Return all columns as list of dicts.

    Raw=True / SDMX-shape columns are renamed to canonical names where
    the alias is unambiguous so the LLM sees `iso3`/`period`/`value`
    rather than `REF_AREA`/`TIME_PERIOD`/`OBS_VALUE`. Other dim columns
    (SEX, AGE, WEALTH_QUINTILE, …) keep their SDMX casing — they are
    inherent SDMX vocabulary and don't have a simplified counterpart.
    """
    rename = {a: c for a, c in COLUMN_ALIASES.items() if a in df.columns}
    sub = df.rename(columns=rename) if rename else df
    return _clean_nans(sub.to_dict(orient="records"))


def truncate_description(text: str | None, max_len: int = 150) -> str:
    """Shorten description with ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "\u2026"


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
    """Generate summary statistics for the data.

    v1.2.0 Commit 7 — safe-coerces the `value` column to numeric before
    aggregation. The `raw=True` SDMX path returns string-shaped values
    (`"0.35"`, `"<0.01"`, etc.); censored / below-detection cells like
    `"<0.01"` become NaN under `pd.to_numeric(errors='coerce')` and are
    excluded from the summary stats. The original string is preserved
    in the `data` records (callers cite the verbatim cell).
    """
    summary: dict[str, Any] = {}

    if "value" in df.columns:
        import pandas as pd
        values = pd.to_numeric(df["value"], errors="coerce").dropna()
        if len(values) > 0:
            summary["value_range"] = {
                "min": round(float(values.min()), 2),
                "max": round(float(values.max()), 2),
                "mean": round(float(values.mean()), 2),
            }

    if "period" in df.columns:
        periods = df["period"].dropna()
        if len(periods) > 0:
            # Tolerate non-numeric periods (e.g. SDMX quarterly "2019-Q1") by
            # falling back to the four-character year prefix when astype(int)
            # rejects the value. Without this, a quarterly indicator's response
            # would crash here and lose the otherwise-successful payload.
            try:
                earliest = int(periods.min())
                latest = int(periods.max())
            except (ValueError, TypeError):
                try:
                    years = periods.astype(str).str[:4].astype(int)
                    earliest = int(years.min())
                    latest = int(years.max())
                except (ValueError, TypeError):
                    earliest = latest = 0
            if earliest or latest:
                summary["year_range"] = {"earliest": earliest, "latest": latest}

    countries_col = country_col(df)
    if countries_col in df.columns:
        summary["countries_in_result"] = int(df[countries_col].nunique())

    return summary


def _period_as_year(value: Any) -> float | None:
    """Coerce a period cell to a float year, tolerating SDMX quarterly forms."""
    try:
        return float(value)
    except (ValueError, TypeError):
        try:
            return float(str(value)[:4])
        except (ValueError, TypeError):
            return None


def compute_trend(df: pd.DataFrame, window: int = 5) -> dict[str, Any] | None:
    """Compute annualized rate of change from the most recent `window` years.

    Uses compound annual growth rate (CAGR) formula:
        AARC = (V_end / V_start)^(1/years) - 1

    Returns per-country trends if multiple countries, or single trend if one.
    Periods that can't be coerced to a year (e.g. malformed strings) are skipped.

    v1.2.0 Commit 7 — safe-coerces the `value` column. The `raw=True` SDMX
    path returns string-shaped values; censored cells like `"<0.01"` become
    NaN under `pd.to_numeric(errors='coerce')` and are dropped before the
    CAGR computation runs (preserves the docstring's per-period skipping
    promise and stops a single `<0.01` from crashing the whole call).
    """
    if "period" not in df.columns or "value" not in df.columns:
        return None

    countries_col = country_col(df)
    if countries_col not in df.columns:
        return None

    import pandas as pd
    df = df.copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    trends: dict[str, Any] = {}

    for country, group in df.groupby(countries_col):
        group = group.dropna(subset=["value", "period"]).sort_values("period")
        if len(group) < 2:
            continue

        latest = group.iloc[-1]
        latest_year = _period_as_year(latest["period"])
        if latest_year is None:
            continue
        # Find the observation closest to `window` years before latest. Coerce
        # each period through `_period_as_year` so quarterly strings sort as
        # their year prefix (good enough for AARC over multi-year windows).
        years_series = group["period"].map(_period_as_year)
        # Drop rows whose period couldn't be coerced — the docstring promises
        # per-period skipping, not whole-country skipping. The previously
        # validated `latest` (latest_year is not None) survives this filter.
        parseable = years_series.notna()
        years_series = years_series[parseable]
        group = group.loc[parseable]
        if len(group) < 2:
            continue
        target_year = latest_year - window
        mask = years_series <= target_year + 0.5
        earlier_row = group.iloc[0] if not mask.any() else group[mask].iloc[-1]
        earlier_year = _period_as_year(earlier_row["period"])
        if earlier_year is None:
            continue

        v_start = float(earlier_row["value"])
        v_end = float(latest["value"])
        n_years = latest_year - earlier_year

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
            "start_year": int(earlier_year),
            "end_year": int(latest_year),
            "start_value": round(v_start, 2),
            "end_value": round(v_end, 2),
            "aarc": round(aarc * 100, 2),  # as percentage
            "direction": direction,
        }

    if not trends:
        return None
    return trends


def ok(
    data: dict[str, Any],
    *,
    warnings: list[str] | None = None,
    data_completeness: str = "complete",
    requires_confirmation: bool | None = None,
    recommended: dict[str, Any] | None = None,
    assistant_guidance: str | None = None,
    next_step: str | None = None,
) -> dict[str, Any]:
    """Wrap a successful response with status, source, and optional warnings.

    Args:
        data: The response payload.
        warnings: Optional list of human-readable caveats about the data.
        data_completeness: One of "complete", "partial", "truncated".
            - "complete": all requested data was returned
            - "partial": some countries/years had no data, or dimensions are missing
            - "truncated": row limit was hit, more data exists
        requires_confirmation: (v1.1.0+) True = assistant MUST stop and ask the
            user to disambiguate. False = safe to proceed with `recommended`.
            None (default) = field absent from response (v1.0.0-compatible).
        recommended: (v1.1.0+) Dict with keys "code", "dataflow_id", "why".
            Present only when requires_confirmation is False.
        assistant_guidance: (v1.1.0+) Plain-English directive, English-only,
            <200 chars, no markdown. Tells the assistant what to do next.
        next_step: (v1.1.0+) Literal string naming the next tool invocation,
            e.g. "get_indicator_info(code='ED_ANAR_L1')".
    """
    result: dict[str, Any] = {
        "status": "ok",
        "source": "UNICEF Data Warehouse via SDMX API",
        "data_completeness": data_completeness,
        **data,
    }
    if warnings:
        result["warnings"] = warnings
    if requires_confirmation is not None:
        result["requires_confirmation"] = requires_confirmation
    if recommended:
        result["recommended"] = recommended
    if assistant_guidance:
        result["assistant_guidance"] = assistant_guidance
    if next_step:
        result["next_step"] = next_step
    return result


def error(
    message: str,
    tip: str | None = None,
    no_data: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap an error response with optional tip.

    When no_data=True, returns a structured no-data envelope with concrete
    behavioral rules rather than abstract "do not estimate" guidance — the
    LLM must produce specific user-visible text and avoid specific phrases.
    This is the v0.6.0 strengthening: the instruction names the user-visible
    behavior the response must contain instead of asking the model to
    interpret an abstract directive.

    `extra` is a dict merged into the result for callers that want to add
    structured fields (e.g. `data_frontier` for out-of-frontier refusals).
    """
    result: dict[str, Any] = {"status": "error", "error": message}
    if tip:
        result["tip"] = tip
    if no_data:
        result["status"] = "no_data"
        result["data_completeness"] = "empty"
        result["instruction"] = (
            "This result is authoritative: the UNICEF Data Warehouse was queried "
            "and confirmed this data does not exist. Your response MUST contain "
            "the literal text 'No data is available' for this query and MUST NOT "
            "contain any numeric value attributed to it, including phrases like "
            "'approximately X', 'around X', 'projected X', 'based on the trend X', "
            "or 'extrapolating from recent data X'. Suggest the user check "
            "data.unicef.org or the relevant national statistics office."
        )
    if extra:
        # Merge extras WITHOUT clobbering core envelope keys. Without this,
        # a caller could accidentally overwrite `status`/`error`/`tip`/
        # `instruction`/`data_completeness` and break the response contract.
        # Reserved keys win; collisions are silently dropped (keep the
        # signature simple — extra is internal-use only for now).
        for k, v in extra.items():
            if k not in result:
                result[k] = v
    return result
