"""UNICEF Stats MCP Server — query child development indicators via Model Context Protocol.

Seven tools in a 4-step workflow:
  Step 1 (Discovery):  search_indicators, list_categories, list_countries
  Step 2 (Metadata):   get_indicator_info, get_temporal_coverage
  Step 3 (Data):       get_data
  Step 4 (Code):       get_api_reference

Plus two MCP prompts:
  compare_indicators     — pre-built analysis workflow (discovery → data → comparison)
  write_unicefdata_code  — generate Python/R/Stata code using the unicefdata package

Data source: UNICEF SDMX REST API (https://sdmx.data.unicef.org/ws/public/sdmxapi/rest)
No API key required. 790+ child-focused indicators, 200+ countries,
disaggregations by sex/age/wealth/residence.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time as _time
import types
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal, TypeVar

from fastmcp import FastMCP

from unicefstats_mcp.country_resolver import resolve_countries
from unicefstats_mcp.formatters import (
    apply_limit,
    compute_trend,
    country_col,
    error,
    ok,
    summarize_data,
    summarize_disaggregations,
    to_compact,
    to_full,
    truncate_description,
)
from unicefstats_mcp.indicator_context import get_indicator_context
from unicefstats_mcp.reference import REFERENCES, VALID_LANGUAGES
from unicefstats_mcp.validators import (
    MAX_COUNTRIES,
    validate_indicator,
    validate_limit,
    validate_query,
    validate_residence,
    validate_sex,
    validate_wealth_quintile,
    validate_year,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)


def _retry(
    fn: Callable[[], T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
) -> T:
    """Call fn with exponential backoff on transient failures."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            exc_str = str(exc).lower()
            # Don't retry on client errors (invalid indicator, 404, etc.)
            if "404" in exc_str or "not found" in exc_str or "does not exist" in exc_str:
                raise
            if attempt < max_attempts - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.info("Retry %d/%d after %.1fs: %s", attempt + 1, max_attempts, delay, exc)
                _time.sleep(delay)
    raise last_exc  # type: ignore[misc]

mcp = FastMCP(
    name="unicefstats-mcp",
    version="0.6.2",
    instructions=(
        "Query UNICEF child development statistics for 200+ countries. "
        "No API key required. 790+ child-focused indicators (mortality, nutrition, "
        "education, protection, WASH, HIV/AIDS, and more) with disaggregations "
        "by sex, age, wealth quintile, and residence. "
        "Data sourced from UNICEF SDMX API (sdmx.data.unicef.org)."
    ),
)

# ---------------------------------------------------------------------------
# Lazy import helpers — defer heavy unicefdata import until first tool call
# ---------------------------------------------------------------------------

_ud: types.ModuleType | None = None
_indicators_cache: dict[str, dict[str, Any]] | None = None
_countries_cache: dict[str, str] | None = None


def _get_ud() -> types.ModuleType:
    """Lazy-import unicefdata."""
    global _ud
    if _ud is None:
        import unicefdata as ud

        _ud = ud
    return _ud


def _get_indicators() -> dict[str, dict[str, Any]]:
    """Load and cache the full indicator registry."""
    global _indicators_cache
    if _indicators_cache is None:
        ud = _get_ud()
        _indicators_cache = ud.list_indicators()
    return _indicators_cache


def _get_countries() -> dict[str, str]:
    """Load and cache country code → name mapping."""
    global _countries_cache
    if _countries_cache is None:
        ud = _get_ud()
        _countries_cache = ud.load_country_codes()
    return _countries_cache


# ---------------------------------------------------------------------------
# Synonym expansion for search
# ---------------------------------------------------------------------------

_SYNONYMS: dict[str, str] = {
    # MNCH indicators
    "caesarean": "cesarean c-section",
    "caesarean section": "cesarean c-section",
    "c-section": "cesarean c-section",
    "c section": "cesarean c-section",
    "cesarean section": "cesarean c-section",
    "births under 18": "early childbearing birth before age 18",
    "births to women under 18": "early childbearing birth before age 18",
    "teenage pregnancy": "early childbearing adolescent birth",
    "adolescent birth": "early childbearing birth before age",
    "teen birth": "early childbearing adolescent birth",
    # Nutrition
    "stunting": "stunting height-for-age",
    "wasting": "wasting weight-for-height",
    "underweight": "underweight weight-for-age",
    "malnutrition": "stunting wasting underweight nutrition",
    # Mortality
    "child mortality": "under-five mortality",
    "infant mortality": "infant mortality rate",
    "neonatal mortality": "neonatal mortality rate",
    "under-5 mortality": "under-five mortality",
    "u5mr": "under-five mortality",
    # Education
    "primary school": "primary education completion",
    "school completion": "education completion rate",
    "out of school": "out-of-school",
}


def _expand_synonyms(query: str) -> str:
    """Expand query with synonyms for better indicator matching."""
    expanded = query
    for term, expansion in _SYNONYMS.items():
        if term in query:
            expanded = f"{expanded} {expansion}"
            break  # one expansion per query to avoid noise
    return expanded


# ---------------------------------------------------------------------------
# Step 1: Discovery tools (local, instant, no API call)
# ---------------------------------------------------------------------------


@mcp.tool()
def search_indicators(query: str, limit: int = 20) -> dict[str, Any]:
    """Search UNICEF child development indicators by keyword.

    Returns indicator codes, names, and categories. Use the returned `code`
    values with get_indicator_info() or get_data().
    Always start here if you don't know the indicator code.

    Examples: "mortality", "breastfeeding", "education", "child labour", "stunting"
    """
    if err := validate_query(query):
        return error(err, tip="Provide a search term like 'mortality' or 'education'.")
    if err := validate_limit(limit, max_limit=100):
        return error(err)

    try:
        all_indicators = _get_indicators()
    except Exception as exc:
        return error(f"Failed to load indicator registry: {exc}")

    query_lower = query.lower()
    # Expand synonyms so common terms find the right indicators
    query_expanded = _expand_synonyms(query_lower)
    query_tokens = set(query_expanded.split())
    matches: list[dict[str, Any]] = []

    for code, meta in all_indicators.items():
        name = meta.get("name", "")
        desc = meta.get("description", "")
        cat = meta.get("category", "")
        searchable = f"{code} {name} {desc} {cat}".lower()

        # Score: exact code match > code contains > full phrase > token overlap > category
        score = 0
        if query_lower == code.lower():
            score = 100
        elif query_lower in code.lower():
            score = 90
        elif query_expanded in name.lower() or query_lower in name.lower():
            score = 80
        elif query_expanded in desc.lower() or query_lower in desc.lower():
            score = 40
        elif query_lower in cat.lower():
            score = 60
        else:
            # Token-level matching: what fraction of query tokens appear?
            if len(query_tokens) >= 2:
                hits = sum(1 for t in query_tokens if len(t) > 2 and t in searchable)
                frac = hits / len(query_tokens)
                if frac >= 0.5:
                    score = int(30 + 40 * frac)  # 50-70 range

        if score > 0:
            matches.append(
                {
                    "code": code,
                    "name": name,
                    "description": truncate_description(desc),
                    "category": cat,
                    "relevance": score,
                }
            )

    # Sort by relevance descending, then alphabetically
    matches.sort(key=lambda m: (-m["relevance"], m["code"]))
    results = matches[:limit]

    # Drop relevance score from output (internal use only)
    for r in results:
        del r["relevance"]

    if not results:
        return error(
            f"No indicators match '{query}'.",
            tip="Try broader terms like 'health', 'education', 'nutrition', "
            "or use list_categories() to browse topics.",
            no_data=True,
        )

    return ok(
        {
            "query": query,
            "total_matches": len(matches),
            "showing": len(results),
            "results": results,
            "tip": (
                f"Use get_indicator_info('{results[0]['code']}') for full details "
                "including available disaggregations."
            ),
        }
    )


@mcp.tool()
def list_categories() -> dict[str, Any]:
    """List all UNICEF indicator categories (thematic groups).

    Categories correspond to SDMX dataflows: CME (child mortality), NUTRITION,
    EDUCATION, CHILD_PROTECTION, WASH, HIV_AIDS, etc.
    Use this to browse available topics before searching for specific indicators.
    """
    try:
        all_indicators = _get_indicators()
    except Exception as exc:
        return error(f"Failed to load indicator registry: {exc}")

    # Build category → indicator count mapping
    categories: dict[str, int] = {}
    for meta in all_indicators.values():
        cat = meta.get("category", "Uncategorized")
        categories[cat] = categories.get(cat, 0) + 1

    cat_list = [
        {"name": name, "indicator_count": count}
        for name, count in sorted(categories.items())
    ]

    return ok(
        {
            "total_categories": len(cat_list),
            "total_indicators": sum(c["indicator_count"] for c in cat_list),
            "categories": cat_list,
            "tip": (
                "Use search_indicators(query='mortality', limit=10)"
                " to find indicators in a category."
            ),
        }
    )


@mcp.tool()
def list_countries(region: str | None = None) -> dict[str, Any]:
    """List countries available in the UNICEF database with ISO3 codes.

    Optionally filter by region name (case-insensitive partial match).
    Use the iso3 values in get_data().
    """
    try:
        country_map = _get_countries()
    except Exception as exc:
        return error(f"Failed to load country codes: {exc}")

    countries = [
        {"iso3": code, "name": name} for code, name in sorted(country_map.items())
    ]

    if region:
        region_lower = region.lower()
        countries = [c for c in countries if region_lower in c["name"].lower()]

    return ok(
        {
            "total": len(countries),
            "region_filter": region,
            "countries": countries,
        }
    )


# ---------------------------------------------------------------------------
# Step 2: Metadata tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_indicator_info(code: str) -> dict[str, Any]:
    """Get full metadata for a UNICEF indicator.

    Returns description, category, dataflow, and SDMX API details.
    Use this before calling get_data() to understand what the indicator measures
    and which disaggregation filters (sex, age, wealth_quintile, residence) apply.
    """
    try:
        ud = _get_ud()
        info = ud.get_indicator_info(code)
    except Exception as exc:
        return error(f"Failed to retrieve indicator info: {exc}")

    if info is None:
        return error(
            f"Indicator '{code}' not found in the UNICEF Data Warehouse.",
            tip="Use search_indicators('your topic') to find valid indicator codes.",
            no_data=True,
        )

    # Try to get dataflow for the indicator
    dataflow = None
    with contextlib.suppress(Exception):
        dataflow = ud.get_dataflow_for_indicator(code)

    result: dict[str, Any] = {
        "code": code,
        "name": info.get("name", ""),
        "description": info.get("description", ""),
        "category": info.get("category", ""),
        "dataflow": dataflow,
        "sdmx_api": (
            f"https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/data/"
            f"UNICEF,{dataflow or 'GLOBAL_DATAFLOW'},1.0/.{code}?format=csv"
        )
        if dataflow
        else None,
        "disaggregation_filters": {
            "sex": ["_T (Total)", "M (Male)", "F (Female)"],
            "wealth_quintile": ["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"],
            "residence": ["_T (Total)", "U (Urban)", "R (Rural)"],
        },
        "tip": f"Use get_data(indicator='{code}', countries=['BRA','IND']) to fetch observations.",
    }

    # Add semantic context (related indicators, disambiguation, SDG targets, methodology)
    context = get_indicator_context(code)
    if context:
        result.update(context)

    return ok(
        result,
        warnings=[
            "Disaggregation filters listed above are the POSSIBLE dimensions. "
            "Not all countries or years have data for every disaggregation. "
            "Actual availability varies — check the data response for what was returned.",
        ],
    )


@mcp.tool()
def get_temporal_coverage(code: str) -> dict[str, Any]:
    """Check what years of data are available for a UNICEF indicator.

    Fetches a small sample to determine the time range. Lightweight — does not
    fetch all observations. Use before get_data() to pick a year range.
    """
    try:
        ud = _get_ud()
        # Fetch a minimal sample: totals only, all countries, to get year range
        df = _retry(lambda: ud.unicefData(
            indicator=code,
            sex="_T",
            totals=True,
            tidy=True,
            country_names=False,
            simplify=True,
        ))
    except Exception as exc:
        return error(
            f"Failed to fetch temporal coverage for '{code}': {exc}",
            tip="Check that the indicator code is correct with search_indicators().",
        )

    if df.empty:
        return error(
            f"No data found for indicator '{code}' in the UNICEF Data Warehouse.",
            tip="Use search_indicators() to verify the indicator code.",
            no_data=True,
        )

    periods = df["period"].dropna()
    try:
        years = periods.astype(float).astype(int)
        start_yr = int(years.min())
        end_yr = int(years.max())
    except (ValueError, TypeError):
        # Non-numeric periods (e.g. "2019-Q1") — try to extract year prefix
        try:
            years = periods.astype(str).str[:4].astype(int)
            start_yr = int(years.min())
            end_yr = int(years.max())
        except (ValueError, TypeError):
            start_yr = 0
            end_yr = 0

    countries_col = country_col(df)
    n_countries = df[countries_col].nunique() if countries_col in df.columns else 0

    # Detect if this looks like a survey-based indicator (sparse years)
    warnings: list[str] = [
        "Not all countries have data for all years. Coverage varies by country.",
    ]
    if start_yr and end_yr:
        year_span = end_yr - start_yr + 1
        unique_years = len(set(years.unique())) if len(years) > 0 else 0
        if year_span > 5 and unique_years < year_span * 0.5:
            warnings.append(
                "This indicator appears to be survey-based (DHS/MICS) — "
                "data is collected every 3-5 years, not annually. "
                "Year gaps are normal and do NOT mean the data is missing."
            )

    return ok(
        {
            "code": code,
            "start_year": start_yr,
            "end_year": end_yr,
            "latest_year": end_yr,
            "countries_with_data": n_countries,
        },
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Step 3: Data retrieval
# ---------------------------------------------------------------------------


# Per-session cache of data frontier (max year observed) per indicator.
# Cleared at process restart. Avoids repeated coverage calls during the same
# session — typical use accesses 1-3 indicators, so the cache pays for itself
# within a few `get_data` calls. Bounded by indicator count (790 max).
_data_frontier_cache: dict[str, int] = {}


def _get_data_frontier(indicator: str) -> int | None:
    """Return the max year observed for `indicator` in the UNICEF Data
    Warehouse, or None if it can't be determined.

    Used by `get_data` for pre-flight year-frontier checks (v0.6.0+). Cached
    per session — lookup cost is amortized across all `get_data` calls for the
    same indicator.

    Implementation: calls the existing `get_temporal_coverage` machinery, which
    fetches a minimal totals-only sample to learn the year range. Returns the
    `end_year` field from that sample. None on lookup failure (treated as "no
    frontier check possible" — falls through to the API rather than blocking).
    """
    if indicator in _data_frontier_cache:
        return _data_frontier_cache[indicator]
    try:
        cov = get_temporal_coverage(indicator)
    except Exception:
        return None
    if not isinstance(cov, dict) or cov.get("status") != "ok":
        return None
    data_block = cov.get("data") if isinstance(cov.get("data"), dict) else None
    end_year = data_block.get("end_year") if data_block else cov.get("end_year")
    if isinstance(end_year, int) and end_year > 0:
        _data_frontier_cache[indicator] = end_year
        return end_year
    return None


@mcp.tool()
def get_data(
    indicator: str,
    countries: list[str],
    start_year: int | None = None,
    end_year: int | None = None,
    sex: str = "_T",
    wealth_quintile: str | None = None,
    residence: str | None = None,
    format: Literal["compact", "full"] = "compact",
    limit: int = 200,
) -> dict[str, Any]:
    """Fetch UNICEF data for an indicator and one or more countries.

    Returns annual observations from the UNICEF SDMX API. Use format="compact"
    (default) for a clean 5-column table; use format="full" for all columns
    including disaggregation details and confidence bounds.

    **`countries` accepts BOTH ISO3 codes AND country names** (v0.6.2). Pass
    whichever you have from the user's question — the server resolves country
    names to canonical ISO3 codes for you. Examples:
      countries=['Burundi']            → resolves to ['BDI']
      countries=['BDI', 'Belgium']     → resolves to ['BDI', 'BEL']
      countries=['Cote d\\'Ivoire']     → resolves to ['CIV']
      countries=['USA', 'UK']          → resolves to ['USA', 'GBR']
    Common synonyms accepted: 'USA'/'United States', 'UK'/'Great Britain',
    'Ivory Coast'/'Cote d\\'Ivoire', 'South Korea', 'DRC', 'Czech Republic',
    'Burma', 'Vatican', etc. The response echoes the resolution under
    `country_resolutions` and the canonical name+code pairs under
    `countries_returned_with_names` so you can confirm intent matched.

    **Prefer passing the user's country name verbatim over guessing the ISO3
    code from memory** — that's where v0.6.0 had a documented failure mode.

    **v0.6.0 server-side hardening**: this tool also performs a pre-flight
    year-frontier check. If `start_year` or `end_year` exceeds the indicator's
    data frontier (max year observed), the call is refused server-side without
    issuing the SDMX request — preventing the silent-truncation pattern where
    a range like 2020-2027 returns 2020-2024 and the model extrapolates the
    missing years. Successful responses include a `data_frontier` field
    naming the max year and an explicit no-extrapolation directive.

    Disaggregation filters:
      sex: "_T" (total, default), "M" (male), "F" (female)
      wealth_quintile: "Q1" (lowest) through "Q5" (highest), or "_T" (total)
      residence: "U" (urban), "R" (rural), or "_T" (total)

    Limit defaults to 200 rows — narrow your country/year filters or
    increase limit (max 500) if you need more data.
    """
    # Validate inputs
    if err := validate_indicator(indicator):
        return error(err)

    # v0.6.2 country-name resolver: accept ISO3 codes OR country names. The
    # model often calls get_data with the wrong ISO3 ("Burundi" → 'BEL')
    # because it's resolving the name from memory. Letting the server do the
    # canonical name → ISO3 mapping eliminates that failure mode entirely.
    if not countries:
        return error("At least one country (ISO3 code or name) is required.")
    if len(countries) > MAX_COUNTRIES:
        return error(
            f"Too many countries ({len(countries)}). Maximum is {MAX_COUNTRIES} per call. "
            "Split into multiple calls or use list_countries() to find a region filter."
        )
    resolved_codes, country_resolutions, unresolved = resolve_countries(countries)
    if unresolved:
        return error(
            f"Could not resolve country/countries: {', '.join(repr(u) for u in unresolved)}. "
            "Pass either the ISO3 code (e.g. 'BDI') or the country name (e.g. 'Burundi'). "
            "Common alternates accepted: 'USA'/'United States', 'UK'/'United Kingdom', "
            "'Ivory Coast'/'Cote d\\'Ivoire', 'South Korea', 'DRC', etc.",
            tip="Use list_countries() to enumerate valid codes and names.",
        )
    # Replace caller's input with canonical ISO3 codes for downstream use.
    # Keep the original `countries` list for echoing back to the caller.
    countries_input = countries
    countries = resolved_codes

    if err := validate_limit(limit):
        return error(err)
    if err := validate_year(start_year, "start_year"):
        return error(err)
    if err := validate_year(end_year, "end_year"):
        return error(err)
    if err := validate_sex(sex):
        return error(err)
    if wealth_quintile and (err := validate_wealth_quintile(wealth_quintile)):
        return error(err)
    if residence and (err := validate_residence(residence)):
        return error(err)

    # v0.6.0 pre-flight year-frontier check.
    # Refuse calls where requested year(s) exceed the indicator's data frontier,
    # WITHOUT issuing the SDMX request. The "silent retry" hallucination pattern
    # (model asks 2027 → no_data → asks 2020-2027 → API returns 2020-2024 → model
    # extrapolates) is broken because the broader range is now refused too.
    if start_year is not None or end_year is not None:
        max_year = _get_data_frontier(indicator)
        if max_year is not None:
            target_start = start_year if start_year is not None else end_year
            target_end = end_year if end_year is not None else start_year
            if target_start is not None and target_start > max_year:
                return error(
                    f"Year {target_start} exceeds the data frontier ({max_year}) "
                    f"for indicator '{indicator}'. The UNICEF Data Warehouse does "
                    f"not have observations beyond {max_year} for this indicator.",
                    tip=f"Narrow start_year to {max_year} or earlier.",
                    no_data=True,
                    extra={
                        "data_frontier": {
                            "max_year_observed": max_year,
                            "indicator": indicator,
                        },
                        "out_of_frontier": True,
                    },
                )
            if target_end is not None and target_end > max_year:
                return error(
                    f"Requested range {start_year or '...'}-{target_end} extends "
                    f"past the data frontier ({max_year}) for indicator "
                    f"'{indicator}'. The API will not silently truncate to "
                    f"{max_year} on your behalf — that pattern is a known "
                    f"source of forward-of-frontier extrapolation.",
                    tip=f"Narrow end_year to {max_year} or earlier.",
                    no_data=True,
                    extra={
                        "data_frontier": {
                            "max_year_observed": max_year,
                            "indicator": indicator,
                        },
                        "out_of_frontier": True,
                    },
                )

    # Build year argument (unicefdata accepts "start:end" range syntax)
    year_arg = None
    if start_year is not None and end_year is not None:
        year_arg = f"{start_year}:{end_year}"
    elif start_year is not None:
        year_arg = f"{start_year}:2099"
    elif end_year is not None:
        year_arg = f"1900:{end_year}"

    try:
        ud = _get_ud()
        df = _retry(lambda: ud.unicefData(
            indicator=indicator,
            countries=[c.upper() for c in countries],
            year=year_arg,
            sex=sex,
            tidy=True,
            country_names=True,
            simplify=True,
        ))
    except Exception as exc:
        exc_str = str(exc)
        is_not_found = "404" in exc_str or "Not Found" in exc_str or "does not exist" in exc_str
        return error(
            f"Data fetch failed: {exc}",
            tip=(
                "Check indicator code with search_indicators() "
                "and country codes with list_countries()."
            ),
            no_data=is_not_found,
        )

    if df.empty:
        return error(
            "No data exists in the UNICEF Data Warehouse for this indicator, "
            "country, and year combination.",
            tip="Try broader filters: remove year range or add more countries.",
            no_data=True,
        )

    # Generate summary before formatting (uses full DataFrame)
    data_summary = summarize_data(df)
    disagg_summary = summarize_disaggregations(df)

    # Apply format
    if format == "compact":
        records = to_compact(df)
        columns = ["iso3", "country", "period", "indicator", "value"]
    else:
        records = to_full(df)
        columns = list(df.columns)

    total_rows = len(records)
    records, truncated = apply_limit(records, limit)

    # --- Detect warnings and data completeness ---
    warnings: list[str] = []
    completeness = "complete"

    # Check for missing countries (requested but not in results)
    countries_col = country_col(df)
    if countries_col in df.columns:
        returned_countries = set(df[countries_col].str.upper().unique())
        requested_upper = {c.upper() for c in countries}
        missing_countries = requested_upper - returned_countries
        if missing_countries:
            missing_str = ", ".join(sorted(missing_countries))
            warnings.append(
                f"No data returned for: {missing_str}. "
                "These countries may lack data for this indicator, year range, "
                "or disaggregation. Do NOT estimate values for missing countries."
            )
            completeness = "partial"

    if truncated:
        completeness = "truncated"
        filter_tip = ""
        if disagg_summary:
            dims = ", ".join(disagg_summary.keys())
            filter_tip = f" Data contains disaggregations by {dims} — filter to reduce rows."
        warnings.append(
            f"Results truncated: showing {len(records)} of {total_rows} rows.{filter_tip}"
            f" Increase limit (max 500) or narrow filters to see all data."
        )

    # Check for sparse year coverage (gaps in time series)
    if "period" in df.columns and start_year is not None and end_year is not None:
        expected_years = set(range(start_year, end_year + 1))
        actual_years = set(df["period"].dropna().astype(int).unique())
        missing_years = expected_years - actual_years
        if len(missing_years) > len(expected_years) * 0.5 and len(missing_years) > 2:
            warnings.append(
                "Sparse year coverage — this indicator may be survey-based "
                "(DHS/MICS, collected every 3-5 years). Year gaps are expected "
                "and do NOT indicate missing data. Do NOT interpolate."
            )
            if completeness == "complete":
                completeness = "partial"

    # v0.6.1 — extract resolved country names so the model sees the human-readable
    # name of every country returned. Mitigates the country-substitution failure
    # mode revealed at n=500 (model calls get_data with the wrong ISO3 code and
    # the response had no prominent name to flag the mismatch).
    countries_returned_with_names: dict[str, str] = {}
    if countries_col in df.columns:
        # Find the country-name column. unicefdata uses "country" with
        # country_names=True; tests simulate "country_name". Accept either.
        name_col = next(
            (c for c in ("country", "country_name") if c in df.columns), None
        )
        if name_col:
            unique_pairs = df[[countries_col, name_col]].drop_duplicates()
            for code, name in unique_pairs.itertuples(index=False):
                if isinstance(code, str) and isinstance(name, str):
                    countries_returned_with_names[code.upper()] = name

    result: dict[str, Any] = {
        "indicator": indicator,
        "countries_requested": countries_input,
        "countries_resolved_to": countries,
        # v0.6.2: name → ISO3 resolutions performed server-side. Empty if the
        # caller passed only ISO3 codes. If non-empty, the model can confirm
        # "Burundi → BDI" and proceed without worrying about its own ISO3 memory.
        "country_resolutions": country_resolutions,
        "countries_returned_with_names": countries_returned_with_names,
        "verify_country_directive": (
            "Country resolution: see `country_resolutions` and "
            "`countries_returned_with_names`. If the names there match what "
            "the user asked about, proceed. If you passed an ISO3 code and "
            "the returned country name doesn't match the user's question, "
            "retry with the country NAME instead of the code — the server "
            "will resolve it canonically."
        ),
        "total_rows_available": total_rows,
        "rows_returned": len(records),
        "rows_truncated": truncated,
        "format": format,
        "columns": columns,
        "summary": data_summary,
        "data": records,
    }

    # Include disaggregation summary if there are non-trivial dimensions
    if disagg_summary:
        result["disaggregations_in_data"] = disagg_summary

    # Compute annualized rate of change (trend over last 5 years)
    trend = compute_trend(df, window=5)
    if trend:
        result["trend_5yr"] = trend

    # Source citation — verifiable SDMX API URL
    country_str = "+".join(c.upper() for c in countries)
    result["citation"] = {
        "provider": "UNICEF Data Warehouse",
        "api_url": (
            f"https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/data/"
            f"UNICEF,GLOBAL_DATAFLOW,1.0/{country_str}.{indicator}"
            f"?format=csv&startPeriod={start_year or ''}&endPeriod={end_year or ''}"
        ),
        "web_url": "https://data.unicef.org/",
        "note": "Verify values at the URLs above before citing in publications.",
    }

    # v0.6.0 — embed data frontier in successful responses so the model has
    # the boundary in context at the moment it composes its answer (not just
    # on the failure path). Computed from the response itself when possible
    # (most accurate); falls back to the cached frontier from the indicator's
    # full coverage. The directive names the user-visible behavior to enforce.
    max_year_in_response: int | None
    try:
        max_year_in_response = int(df["period"].astype(float).max())
    except (ValueError, TypeError, KeyError):
        max_year_in_response = _get_data_frontier(indicator)
    if max_year_in_response:
        result["data_frontier"] = {
            "max_year_observed": max_year_in_response,
            "indicator": indicator,
            "directive": (
                f"Data does not exist beyond {max_year_in_response} for this "
                f"indicator. Do not extrapolate, project, or estimate values "
                f"for years > {max_year_in_response}. If the user asked about "
                f"a year > {max_year_in_response}, respond 'No data is available "
                f"for [year]' and do not provide a numeric answer."
            ),
        }

    if not truncated:
        result["tip"] = None

    return ok(result, warnings=warnings or None, data_completeness=completeness)


# ---------------------------------------------------------------------------
# Step 4: Code reference (local, no API call)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_api_reference(
    language: str = "python",
    function: str | None = None,
) -> dict[str, Any]:
    """Get the unicefdata package API reference for Python, R, or Stata.

    Returns function signatures, parameter descriptions, and usage examples.
    Use this when you need to write code that uses the unicefdata package,
    or when the user wants to move from conversational exploration to
    reproducible scripts.

    Args:
        language: "python", "r", or "stata"
        function: Specific function name (e.g. "unicefData", "search_indicators").
                  If None, returns all functions for the language.
    """
    lang = language.lower()
    if lang not in VALID_LANGUAGES:
        return error(
            f"Unknown language: '{language}'. Valid: python, r, stata",
            tip="Use get_api_reference(language='python') for the Python API.",
        )

    ref = REFERENCES[lang]

    if function:
        func_ref = ref["functions"].get(function)
        if func_ref is None:
            available = ", ".join(ref["functions"].keys())
            return error(
                f"Function '{function}' not found for {lang}.",
                tip=f"Available functions: {available}",
            )
        return ok(
            {
                "language": lang,
                "install": ref["install"],
                "import": ref["import"],
                "function": function,
                **func_ref,
            }
        )

    # Return all functions for the language
    return ok(
        {
            "language": lang,
            "install": ref["install"],
            "import": ref["import"],
            "functions": {
                name: {
                    "signature": f["signature"],
                    "returns": f["returns"],
                    "example_count": len(f["examples"]),
                }
                for name, f in ref["functions"].items()
            },
            "tip": (
                f"Use get_api_reference(language='{lang}',"
                f" function='unicefData') for full details + examples."
            ),
        }
    )


# ---------------------------------------------------------------------------
# MCP Prompts
# ---------------------------------------------------------------------------


# --- compare_indicators ---


@mcp.prompt()
def compare_indicators(
    indicator: str,
    countries: str,
    start_year: str = "2015",
    end_year: str = "2023",
) -> str:
    """Compare a UNICEF indicator across countries over time.

    Pre-built analysis workflow: fetches indicator metadata and data, then asks
    for a structured comparison including trends, regional patterns, and caveats.

    Args:
        indicator: Indicator code (e.g. "CME_MRY0T4")
        countries: Comma-separated ISO3 codes (e.g. "BRA,IND,NGA")
        start_year: Start year for comparison (default "2015")
        end_year: End year for comparison (default "2023")
    """
    country_list = [c.strip().upper() for c in countries.split(",")]
    country_display = ", ".join(country_list)

    return (
        f"I need to compare the UNICEF indicator {indicator} across "
        f"{country_display} from {start_year} to {end_year}.\n\n"
        f"Please:\n"
        f"1. Call get_indicator_info('{indicator}') to understand what this indicator measures\n"
        f"2. Call get_data(indicator='{indicator}', "
        f"countries={country_list}, "
        f"start_year={start_year}, end_year={end_year}, format='compact') "
        f"to fetch the data\n"
        f"3. Analyze the results:\n"
        f"   - Show a summary table of values by country and year\n"
        f"   - Identify trends (improving, worsening, stagnant) per country\n"
        f"   - Highlight the best and worst performers\n"
        f"   - Note any data gaps or caveats\n"
        f"   - If relevant, suggest related indicators to explore\n"
    )


# --- write_unicefdata_code ---


@mcp.prompt()
def write_unicefdata_code(
    task: str,
    language: str = "python",
) -> str:
    """Generate unicefdata code for a data analysis task.

    Takes a plain-language description of what the user wants to do and
    generates runnable code in Python, R, or Stata using the unicefdata package.

    Args:
        task: What the user wants to do (e.g. "Compare under-5 mortality for
              Brazil and India from 2015 to 2023, then plot the trends")
        language: "python", "r", or "stata"
    """
    lang = language.lower()
    if lang not in VALID_LANGUAGES:
        lang = "python"

    ref = REFERENCES[lang]

    return (
        f"The user wants to write {lang} code using the unicefdata package.\n\n"
        f"**Task:** {task}\n\n"
        f"**Instructions:**\n"
        f"1. Call get_api_reference(language='{lang}', function='unicefData') to get "
        f"the exact function signature, parameters, and examples\n"
        f"2. If you need to find indicator codes, call search_indicators() first\n"
        f"3. Write complete, runnable {lang} code that accomplishes the task\n"
        f"4. Include the install/import lines:\n"
        f"   - Install: `{ref['install']}`\n"
        f"   - Import: `{ref['import']}`\n"
        f"5. Add brief comments explaining each step\n"
        f"6. If the task involves visualization, use the standard plotting library "
        f"for the language (matplotlib for Python, ggplot2 for R, twoway for Stata)\n\n"
        f"**Important:** Use the exact parameter names and syntax from the API reference. "
        f"Do not guess — the reference is authoritative.\n"
    )


# --- trend_analysis ---


@mcp.prompt()
def trend_analysis(
    indicator: str,
    country: str,
    start_year: str = "2000",
    end_year: str = "2024",
) -> str:
    """Analyze the trend of a UNICEF indicator for a single country over time.

    Fetches the full time series and produces a structured trend assessment
    with annualized rate of change, inflection points, and policy context.

    Args:
        indicator: Indicator code (e.g. "CME_MRY0T4") or name (e.g. "under-five mortality")
        country: ISO3 code (e.g. "NGA") or country name (e.g. "Nigeria")
        start_year: Start year (default "2000")
        end_year: End year (default "2024")
    """
    return (
        f"Analyze the trend for UNICEF indicator '{indicator}' in {country} "
        f"from {start_year} to {end_year}.\n\n"
        f"Steps:\n"
        f"1. If '{indicator}' is not an indicator code, call search_indicators('{indicator}') "
        f"to find the code\n"
        f"2. Call get_indicator_info(code) to understand the indicator, its unit, and SDG target\n"
        f"3. Call get_data(indicator=code, countries=['{country}'], "
        f"start_year={start_year}, end_year={end_year}, format='compact') to fetch the series\n"
        f"4. Analyze:\n"
        f"   - Report the value at start, end, and any notable inflection points\n"
        f"   - Calculate the annualized rate of change (AARC)\n"
        f"   - Classify the trend: rapid improvement, slow improvement, stagnant, worsening\n"
        f"   - Compare to the SDG target (if available from indicator info)\n"
        f"   - Note data gaps (years with no observation)\n"
        f"   - Suggest what might explain changes (conflicts, policy shifts, data revisions)\n"
        f"5. If the indicator has disaggregations (sex, residence), suggest fetching "
        f"disaggregated data to check for equity gaps\n"
    )


# --- country_profile ---


@mcp.prompt()
def country_profile(
    country: str,
) -> str:
    """Generate a child development profile for a country using key UNICEF indicators.

    Fetches the latest values for a curated set of child health, nutrition,
    education, and protection indicators and presents them as a country brief.

    Args:
        country: ISO3 code (e.g. "NGA") or country name (e.g. "Nigeria")
    """
    core_indicators = [
        ("CME_MRY0T4", "Under-five mortality rate"),
        ("CME_MRM0", "Neonatal mortality rate"),
        ("NT_ANT_HAZ_NE2", "Stunting prevalence"),
        ("NT_ANT_WHZ_NE2", "Wasting prevalence"),
        ("ED_CR_L1", "Primary education completion rate"),
        ("MNCH_CSEC", "C-section rate"),
    ]
    indicator_list = "\n".join(
        f"   - {code} ({name})" for code, name in core_indicators
    )

    return (
        f"Create a child development profile for {country}.\n\n"
        f"Steps:\n"
        f"1. For each of these core indicators, call get_data() to fetch the latest value:\n"
        f"{indicator_list}\n"
        f"2. Present a structured country brief:\n"
        f"   - **Country**: {country} (include region and income group)\n"
        f"   - **Child Survival**: U5MR + neonatal mortality, trend direction\n"
        f"   - **Nutrition**: stunting + wasting, prevalence and severity classification\n"
        f"   - **Education**: primary completion rate\n"
        f"   - **Maternal Health**: C-section rate (too low = underserved, too high = overuse)\n"
        f"3. For each indicator, note:\n"
        f"   - The latest value and year\n"
        f"   - Whether it's above/below regional and global averages\n"
        f"   - The trend (improving/worsening) if data spans multiple years\n"
        f"4. Conclude with 2-3 key takeaways about the country's child development status\n"
        f"5. Cite the SDMX source URLs from the tool responses\n"
    )


# --- sdg_progress ---


@mcp.prompt()
def sdg_progress(
    country: str,
) -> str:
    """Assess a country's progress on child-related SDG targets using UNICEF data.

    Maps UNICEF indicators to SDG targets (3.2, 2.2, 4.1) and reports
    whether the country is on track, needs acceleration, or is off-track.

    Args:
        country: ISO3 code (e.g. "NGA") or country name (e.g. "Nigeria")
    """
    sdg_map = [
        ("SDG 3.2.1", "CME_MRY0T4", "Under-five mortality", "<=25 per 1,000 by 2030"),
        ("SDG 3.2.2", "CME_MRM0", "Neonatal mortality", "<=12 per 1,000 by 2030"),
        ("SDG 2.2.1", "NT_ANT_HAZ_NE2", "Stunting", "Reduce by 40% from 2012 baseline"),
        ("SDG 2.2.2", "NT_ANT_WHZ_NE2", "Wasting", "<=3% by 2030"),
        ("SDG 4.1", "ED_CR_L1", "Primary completion", "100% by 2030"),
    ]
    map_text = "\n".join(
        f"   - {sdg}: {name} ({code}) — target: {target}"
        for sdg, code, name, target in sdg_map
    )

    return (
        f"Assess {country}'s progress on child-related SDG targets.\n\n"
        f"SDG indicator mapping:\n{map_text}\n\n"
        f"Steps:\n"
        f"1. For each SDG indicator, call get_data() to fetch the latest value and "
        f"a 2015-latest time series\n"
        f"2. For each target, assess:\n"
        f"   - **Current value** and year\n"
        f"   - **2015 baseline** (or earliest available)\n"
        f"   - **Required annual rate of reduction** to meet the 2030 target\n"
        f"   - **Actual annual rate of change** (from the time series)\n"
        f"   - **Status**: On track / Needs acceleration / Off track / Achieved\n"
        f"3. Present as a summary table:\n"
        f"   | SDG | Indicator | Latest | Target | Status |\n"
        f"4. Highlight which targets are achievable and which require urgent intervention\n"
        f"5. Note data limitations (survey gaps, model estimates vs survey data)\n"
    )


# ---------------------------------------------------------------------------
# MCP Resources — preloaded reference data, no tool call needed
# ---------------------------------------------------------------------------

LLM_INSTRUCTIONS = """\
# UNICEF Stats MCP — Instructions for AI Assistants

## Workflow
1. **search_indicators(query)** → find indicator codes
2. **get_indicator_info(code)** → check metadata, disaggregations, SDMX details
3. **get_temporal_coverage(code)** → check year range before fetching
4. **get_data(indicator, countries, ...)** → fetch observations
5. **get_api_reference(language)** → get code template for reproducible scripts

## Epistemic safety — CRITICAL

Every response from this MCP includes structured metadata you MUST respect:

- **status**: "ok", "no_data", or "error"
  - "no_data" means the UNICEF database was queried and confirmed absent — do NOT substitute
  - "error" means the query failed — do NOT guess what the result would have been
- **data_completeness**: "complete", "partial", "truncated", or "empty"
  - "partial" means some countries or years had no data — report ONLY what was returned
  - "truncated" means more rows exist — tell the user and suggest narrowing filters
  - "empty" means nothing was found — do NOT provide values from training data
- **warnings[]**: read every warning and relay relevant ones to the user

When data_completeness is "partial" or "truncated", explicitly state what is missing.
When a country has no data, say "no data available for [country]" — do NOT estimate.

## DO
- Always start with search_indicators if you don't know the indicator code
- Use the EXACT indicator code returned by search (e.g., "CME_MRY0T4", not "under-5 mortality")
- Use ISO3 country codes (BRA, IND, NGA) — use list_countries() if unsure
- Report the EXACT numeric value from the tool response — do not round or paraphrase
- Include the year when reporting a value (e.g., "14.4 per 1,000 live births in 2023")
- Check the "warnings" field and relay relevant caveats to the user
- Distinguish between "no data returned" (indicator exists but no observations) and \
"indicator not found" (code is wrong)

## DO NOT
- **Never fabricate or estimate a value** when a tool returns "no_data", "error", or empty results
- **Never use training data** to answer when a tool has already been called and returned no results
- **Never interpolate** between data points for survey-based indicators (year gaps are normal)
- Never confuse similar indicators: stunting (HAZ), wasting (WHZ), underweight (WAZ)
- Never assume the latest year — always check with get_temporal_coverage() or look at the data
- Never cite a source other than UNICEF Data Warehouse for values retrieved through this MCP
- **Never report a value for a country that was not in the response**, even if you \
"know" the value from training

## Forward-of-frontier queries — server-enforced

In v0.6.0+ the server itself refuses `get_data` calls whose year(s) exceed the indicator's data
frontier. You will receive `status: "no_data"` with `out_of_frontier: true` and a `data_frontier`
field naming the max year. You CANNOT bypass this by asking for a broader range — a request like
`start_year=2020, end_year=2027` will also be refused if 2027 > frontier (no silent truncation).

Successful `get_data` responses also include a `data_frontier` field with `max_year_observed` and
a `directive`. Read it. If the user asked about a year > max_year_observed, your final answer
MUST contain the literal text *"No data is available for [year]"* and MUST NOT contain any
numeric value attributed to that year. The server returned data for years it has; the user's
question, if it exceeded the frontier, was not answered by that data.

## Common mistakes
- Wrong: `get_data("under-5 mortality", ...)` → use the CODE: `get_data("CME_MRY0T4", ...)`
- Wrong: `get_data("CME_MRY0T4", ["Brazil"])` → use ISO3: `get_data("CME_MRY0T4", ["BRA"])`
- Wrong: reporting "approximately 15" when tool returned 14.42 → report "14.42"
- Wrong: "data is not available" then providing an estimate from memory → just say "not available"
- Wrong: data returned for BRA and IND but not NGA → reporting a value for NGA anyway
- Wrong: data shows years 2014, 2018, 2022 → reporting values for 2015-2017 by interpolation

## Indicator families (commonly confused)
- CME_MRY0T4 = Under-5 mortality (birth to age 5)
- CME_MRY0 = Infant mortality (birth to age 1)
- CME_MRM0 = Neonatal mortality (birth to 28 days)
- CME_MRY1T4 = Child mortality (age 1 to 4)
- NT_ANT_HAZ_NE2 = Stunting (chronic malnutrition — height-for-age)
- NT_ANT_WHZ_NE2 = Wasting (acute malnutrition — weight-for-height)
- NT_ANT_WAZ_NE2 = Underweight (composite — weight-for-age)
"""


@mcp.resource("unicef://llm-instructions")
def llm_instructions_resource() -> str:
    """Workflow guide, DO/DON'T rules, and common mistakes for AI assistants."""
    return LLM_INSTRUCTIONS


@mcp.resource("unicef://categories")
def categories_resource() -> str:
    """All indicator categories with counts."""
    indicators = _get_indicators()
    cats: dict[str, int] = {}
    for info in indicators.values():
        cat = info.get("category", "Uncategorized")
        cats[cat] = cats.get(cat, 0) + 1
    n_cats, n_inds = len(cats), len(indicators)
    lines = [f"# UNICEF Indicator Categories ({n_cats} categories, {n_inds} indicators)\n"]
    for cat in sorted(cats):
        lines.append(f"- {cat}: {cats[cat]} indicators")
    return "\n".join(lines)


@mcp.resource("unicef://countries")
def countries_resource() -> str:
    """All country ISO3 codes and names."""
    countries = _get_countries()
    lines = [f"# UNICEF Countries ({len(countries)} entries)\n"]
    lines.append("| ISO3 | Country |")
    lines.append("|------|---------|")
    for iso3 in sorted(countries):
        lines.append(f"| {iso3} | {countries[iso3]} |")
    return "\n".join(lines)


SYSTEM_PROMPT = """\
# UNICEF Stats MCP — System Prompt (v0.6.0+)

You are a tool-using assistant for UNICEF child development statistics, covering 790+ indicators
across 200+ countries from the UNICEF Data Warehouse.

## How forward-of-frontier protection works in v0.6.0+

**The server enforces this structurally — you don't have to police it yourself.** When the user
asks about a year beyond the data frontier:

- `get_data` with `start_year` or `end_year` > frontier returns `status: "no_data"` with
  `out_of_frontier: true` server-side. No SDMX call is made.
- A range that crosses the frontier (e.g. 2020–2027 when frontier is 2024) is also refused —
  the server will not silently truncate to 2020–2024. Narrow the end_year explicitly.
- Successful `get_data` responses include a `data_frontier` field with `max_year_observed` and
  a `directive`. Read both. If the user's requested year > max_year_observed, your answer MUST
  contain the literal text "No data is available for [year]" — even though you have data for
  earlier years, that data does not answer the user's question about a future year.

## Operating loop

1. **Indicator** — if you don't know the code, call `search_indicators(query)` and pick the
   single best match.
2. **Data** — call `get_data(indicator, countries, ...)` directly. The server's frontier check
   makes a separate `get_temporal_coverage` call optional (the server already calls it internally
   when it needs to).
3. **Answer** — report exact numeric values from the response. Always include the year. If the
   response carries a `data_frontier.directive`, follow it.

## Output behavior

- When a tool is needed, call it. Do not narrate the plan first.
- Only produce a final user-facing answer when no further tool calls are required.
- Always include the year alongside any reported value.
- Read the response's `status` field. `no_data` and `out_of_frontier` are authoritative.

## For client implementers — prompt-cache recommendation

This system prompt and the tool definitions are stable across tool-use rounds. Apply Anthropic's
`cache_control: {"type": "ephemeral"}` to (a) this system prompt block and (b) the last tool
definition in your tool list. The cache covers everything up to and including the marked block
and reduces input cost ~10× on cache hits. Within a multi-round tool-use query (system prompt +
tool defs are re-sent each round), this typically saves 60-70% of input tokens.

## Reference resources

- `unicef://llm-instructions` — full DO/DON'T rules
- `unicef://context` — runtime current_date / current_year
- `unicef://categories` — indicator categories
- `unicef://countries` — ISO3 codes and country names (200+ entries)
- `unicef://glossary` — disaggregation codes + indicator-prefix legend
"""


@mcp.resource("unicef://system-prompt")
def system_prompt_resource() -> str:
    """Recommended system prompt for AI assistants connecting to this MCP server.

    Loads at session start. Establishes the operating loop, the temporal-frontier
    check, and the anti-extrapolation directive that addresses the T2 hallucination
    failure mode (fabrication when the requested year is beyond the data frontier).

    Pattern adopted from the World Bank data360-mcp `data360://system-prompt`
    resource — same enforcement layer (skill / system prompt) where structural
    guardrails sit, not the tool-description layer (which is advisory).
    """
    return SYSTEM_PROMPT


@mcp.resource("unicef://context")
def context_resource() -> str:
    """Runtime context — current date and year.

    The model needs to know what year "now" is to evaluate temporal queries. Without
    this, the model cannot reliably tell whether a user-requested year is forward of
    the data frontier (the T2 hallucination failure mode in the unicefstats-mcp
    benchmark — model fabricates values for future years 36% of the time when this
    context is missing).

    Pattern adopted from the World Bank data360-mcp `data360://context` resource.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_year": now.year,
        "timezone": "UTC",
        "note": (
            "Use current_year to sanity-check temporal queries. If a user asks about "
            "a year > current_year, the data cannot exist yet — respond with "
            "'No data is available for [year]' and DO NOT extrapolate."
        ),
    }
    return json.dumps(payload, indent=2)


@mcp.resource("unicef://glossary")
def glossary_resource() -> str:
    """Key terms and abbreviations used in UNICEF data."""
    return """\
# UNICEF Data Glossary

## Disaggregation codes
- _T = Total (all groups combined)
- M / F = Male / Female
- U / R = Urban / Rural
- Q1–Q5 = Wealth quintiles (Q1=poorest, Q5=richest)
- B20 / T20 = Bottom 20% / Top 20%

## Indicator prefixes
- CME = Child Mortality Estimates (IGME inter-agency group)
- NT_ANT = Nutrition anthropometric measures
- ED = Education
- PT = Child Protection
- MNCH = Maternal, Newborn and Child Health
- WASH = Water, Sanitation and Hygiene

## Data notes
- Values are typically rates (per 1,000 live births for mortality, % for nutrition/education)
- CME indicators have annual modeled estimates (no year gaps)
- Nutrition indicators are survey-based (DHS/MICS every 3-5 years, expect year gaps)
- Period = calendar year of the observation
- OBS_STATUS: blank = final, P = provisional, E = estimate
"""


# ---------------------------------------------------------------------------
# Server metadata (machine-readable identity and provenance)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_server_metadata() -> dict[str, Any]:
    """Return machine-readable identity, provenance, and version information for this MCP server.

    Use this to verify you are connected to the authentic unicefstats-mcp server
    and to inspect its canonical identity, data source, and publisher information.
    No API call — returns local metadata only.
    """
    from unicefstats_mcp import __version__

    return ok({
        "name": "io.github.jpazvd/unicefstats-mcp",
        "title": "UNICEF Stats MCP",
        "version": __version__,
        "publisher": {
            "name": "Joao Pedro Azevedo",
            "github": "jpazvd",
            "status": "Experimental — not an official UNICEF product",
        },
        "canonical_source": "https://github.com/jpazvd/unicefstats-mcp",
        "pypi_package": "https://pypi.org/project/unicefstats-mcp/",
        "registry_identity": "io.github.jpazvd/unicefstats-mcp",
        "data_source": {
            "name": "UNICEF Data Warehouse",
            "protocol": "SDMX REST v2.1",
            "endpoint": "https://sdmx.data.unicef.org/ws/public/sdmxapi/rest",
            "access": "public",
            "authentication": "none",
        },
        "license": "MIT",
        "provenance_doc": "https://github.com/jpazvd/unicefstats-mcp/blob/main/PROVENANCE.md",
    })


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the UNICEF Stats MCP server.

    Supports stdio (default) and SSE transport:
        unicefstats-mcp                          # stdio (local, Claude Code)
        unicefstats-mcp --transport sse --port 8000  # SSE (remote, Smithery)
    """
    import argparse

    parser = argparse.ArgumentParser(description="UNICEF Stats MCP Server")
    parser.add_argument(
        "--transport", choices=["stdio", "sse"], default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
