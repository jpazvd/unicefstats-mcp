"""Input validation for UNICEF Stats MCP tools."""

from __future__ import annotations

MAX_COUNTRIES = 30
MAX_LIMIT = 500
MIN_QUERY_LEN = 2

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


def validate_countries(countries: list[str]) -> str | None:
    """Return error message if countries list is invalid, else None."""
    if not countries:
        return "At least one country ISO3 code is required."
    if len(countries) > MAX_COUNTRIES:
        return (
            f"Too many countries ({len(countries)}). "
            f"Maximum is {MAX_COUNTRIES} per call. "
            "Split into multiple calls or use list_countries() to find a region filter."
        )
    for code in countries:
        if len(code) != 3 or not code.isalpha():
            return f"Invalid ISO3 code: '{code}'. Use list_countries() to find valid codes."
    return None


def validate_limit(limit: int, max_limit: int = MAX_LIMIT) -> str | None:
    """Return error message if limit is out of range, else None."""
    if not 1 <= limit <= max_limit:
        return f"limit must be between 1 and {max_limit}."
    return None


def validate_query(query: str) -> str | None:
    """Return error message if query is too short, else None."""
    if len(query.strip()) < MIN_QUERY_LEN:
        return f"Query must be at least {MIN_QUERY_LEN} characters."
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
    """Return error message if wealth_quintile filter is invalid, else None."""
    if wq not in VALID_WEALTH_QUINTILE:
        return (
            f"Invalid wealth_quintile: '{wq}'. "
            f"Valid values: {', '.join(sorted(VALID_WEALTH_QUINTILE))}"
        )
    return None
