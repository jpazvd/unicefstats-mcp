"""Input validation for UNICEF Stats MCP tools."""

from __future__ import annotations

MAX_COUNTRIES = 30
MAX_LIMIT = 500
MIN_QUERY_LEN = 2
# Upper bounds on free-text inputs at the MCP boundary. Generous but bounded —
# stops a 1MB blob from landing in log lines / cost amplification while leaving
# room for any plausible legitimate query.
MAX_QUERY_LEN = 200
MAX_REGION_LEN = 100
MAX_COUNTRY_NAME_LEN = 100

# Valid SDMX disaggregation values
VALID_SEX = {"_T", "M", "F"}
VALID_RESIDENCE = {"_T", "U", "R"}
VALID_WEALTH_QUINTILE = {"_T", "Q1", "Q2", "Q3", "Q4", "Q5", "B20", "B40", "B60", "B80", "T20"}


def validate_indicator(code: str) -> str | None:
    """Return error message if indicator code is invalid, else None."""
    if not code or not code.strip():
        return "Indicator code is required. Use search_indicators() to find valid codes."
    if len(code) > 50:
        return (
            f"Indicator code too long ({len(code)} chars)."
            " Use search_indicators() to find valid codes."
        )
    return None


def validate_year(year: int | None, param_name: str) -> str | None:
    """Return error message if year is out of range, else None."""
    if year is not None and not (1900 <= year <= 2100):
        return f"{param_name} must be between 1900 and 2100, got {year}."
    return None


def validate_limit(limit: int, max_limit: int = MAX_LIMIT) -> str | None:
    """Return error message if limit is out of range, else None."""
    if not 1 <= limit <= max_limit:
        return f"limit must be between 1 and {max_limit}."
    return None


def validate_query(query: str) -> str | None:
    """Return error message if query is too short or too long, else None."""
    if len(query.strip()) < MIN_QUERY_LEN:
        return f"Query must be at least {MIN_QUERY_LEN} characters."
    if len(query) > MAX_QUERY_LEN:
        return f"Query too long ({len(query)} chars). Maximum is {MAX_QUERY_LEN}."
    return None


def validate_region(region: str | None) -> str | None:
    """Return error message if region filter is too long, else None."""
    if region is not None and len(region) > MAX_REGION_LEN:
        return f"region too long ({len(region)} chars). Maximum is {MAX_REGION_LEN}."
    return None


def validate_country_inputs(countries: list[str]) -> str | None:
    """Return error message if any country input is too long, else None.

    The MAX_COUNTRIES list-length check stays in the caller. This bounds each
    individual entry so a 1 MB string can't land in log lines / be passed
    downstream to the resolver.
    """
    for c in countries:
        if not isinstance(c, str):
            return f"Country entries must be strings, got {type(c).__name__}."
        if len(c) > MAX_COUNTRY_NAME_LEN:
            return (
                f"Country entry too long ({len(c)} chars). "
                f"Maximum is {MAX_COUNTRY_NAME_LEN}. Pass an ISO3 code or short name."
            )
    return None


def validate_sex(sex: str) -> str | None:
    """Return error message if sex filter is invalid, else None."""
    if sex not in VALID_SEX:
        return f"Invalid sex filter: '{sex}'. Valid values: {', '.join(sorted(VALID_SEX))}"
    return None


def validate_residence(residence: str) -> str | None:
    """Return error message if residence filter is invalid, else None."""
    if residence not in VALID_RESIDENCE:
        return (
            f"Invalid residence filter: '{residence}'. "
            f"Valid values: {', '.join(sorted(VALID_RESIDENCE))}"
        )
    return None


def validate_wealth_quintile(wq: str) -> str | None:
    """Return error message if wealth_quintile filter is invalid, else None.

    Retained for backward-compat with any caller that imports it directly.
    The ``get_data`` tool no longer routes WEALTH_QUINTILE through a typed
    kwarg as of v1.2.0; callers pass it via the ``filters`` dict instead.
    """
    if wq not in VALID_WEALTH_QUINTILE:
        return (
            f"Invalid wealth_quintile: '{wq}'. "
            f"Valid values: {', '.join(sorted(VALID_WEALTH_QUINTILE))}"
        )
    return None


def validate_age(age: str | None) -> str | None:
    """Shape-validate the v1.2.0 ``age=`` kwarg on ``get_data``.

    Semantic validation against the indicator's AGE codelist happens in
    ``dimensions.dimension_supported`` — that's where the pre-flight
    ``failed_validation`` envelope is built. This stops obvious garbage
    (non-string, oversized) before it reaches that layer.
    """
    if age is None:
        return None
    if not isinstance(age, str):
        return (
            f"age must be a string SDMX code (e.g. 'Y15T19'); "
            f"got {type(age).__name__}."
        )
    if len(age) > 30:
        return (
            f"age too long ({len(age)} chars). Pass a single SDMX AGE code "
            "like 'Y15T19' or 'Y0T4'."
        )
    return None


def validate_filters(filters: object) -> str | None:
    """Shape-validate the v1.2.0 ``filters=`` dict on ``get_data``.

    Per-(dim, value) semantic validation against the indicator's actual
    dataflow happens inside ``get_data`` via ``dimensions.dimension_supported``.
    This catches obvious type errors at the MCP boundary so they don't
    crash deeper in the pre-flight check.
    """
    if filters is None:
        return None
    if not isinstance(filters, dict):
        return (
            f"filters must be a dict[str, str | None]; "
            f"got {type(filters).__name__}."
        )
    if len(filters) > 20:
        return (
            f"filters dict too large ({len(filters)} entries). "
            "A single indicator's primary dataflow exposes at most ~10 dims."
        )
    for k, v in filters.items():
        if not isinstance(k, str):
            return f"filter keys must be strings; got {type(k).__name__}={k!r}."
        if len(k) > 50:
            return f"filter key '{k[:20]}...' too long; SDMX dim ids are <50 chars."
        if v is not None and not isinstance(v, str):
            return (
                f"filter value for {k!r} must be str or None; "
                f"got {type(v).__name__}."
            )
        if isinstance(v, str) and len(v) > 50:
            return f"filter value for {k!r} too long; SDMX codes are <50 chars."
    return None
