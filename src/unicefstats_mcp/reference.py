"""Bundled API reference for the unicefdata package (Python, R, Stata).

This module provides authoritative function signatures and examples extracted
from the unicefdata source code. Used by the get_api_reference tool and the
write_code prompt to generate correct code for any platform.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Python API reference
# ---------------------------------------------------------------------------

PYTHON_REFERENCE: dict[str, Any] = {
    "install": "pip install unicefdata",
    "import": "import unicefdata as ud",
    "functions": {
        "unicefData": {
            "signature": (
                "ud.unicefData(\n"
                "    indicator,              # str or list[str] — indicator code(s)\n"
                "    countries=None,          # list[str] — ISO3 codes, None = all\n"
                "    year=None,               # int, str ('2015:2023'), list, tuple, None = all\n"
                "    dataflow=None,           # str — auto-detected from indicator code\n"
                "    sex='_T',                # str — '_T', 'M', 'F'\n"
                "    totals=False,            # bool — only return aggregate totals\n"
                "    tidy=True,               # bool — standardize column names\n"
                "    country_names=True,      # bool — add country name column\n"
                "    format='long',           # str — 'long', 'wide', 'wide_indicators'\n"
                "    latest=False,            # bool — most recent value per country\n"
                "    circa=False,             # bool — closest available year\n"
                "    add_metadata=None,       # list[str] — e.g. ['region', 'income_group']\n"
                "    dropna=False,            # bool — drop rows with missing values\n"
                "    simplify=False,          # bool — minimal columns\n"
                "    mrv=None,                # int — most recent N values per country\n"
                "    raw=False,               # bool — all disaggregations, no filtering\n"
                ") -> pd.DataFrame"
            ),
            "returns": (
                "pandas DataFrame with columns: iso3, country, period,"
                " indicator, value, sex, age, wealth_quintile, residence, ..."
            ),
            "examples": [
                {
                    "description": "Under-5 mortality for Brazil, India, Nigeria (2015–2023)",
                    "code": (
                        'df = ud.unicefData("CME_MRY0T4",'
                        ' countries=["BRA", "IND", "NGA"],'
                        ' year="2015:2023")'
                    ),
                },
                {
                    "description": "Latest stunting data for all countries",
                    "code": 'df = ud.unicefData("NT_ANT_HAZ_NE2", latest=True)',
                },
                {
                    "description": "Exclusive breastfeeding by wealth quintile (raw disaggregation)",
                    "code": 'df = ud.unicefData("NT_BF_EXBF", countries=["ETH", "KEN"], raw=True)',
                },
            ],
        },
        "search_indicators": {
            "signature": (
                "ud.search_indicators(\n"
                '    query=None,              # str — search term (e.g. "mortality")\n'
                '    category=None,           # str — filter by dataflow (e.g. "CME", "NUTRITION")\n'
                "    limit=50,                # int — max results to display\n"
                "    show_description=True,   # bool — include description column\n"
                ") -> None  # prints formatted table"
            ),
            "returns": "None — prints a formatted table to stdout",
            "examples": [
                {
                    "description": "Search for stunting indicators",
                    "code": 'ud.search_indicators("stunting")',
                },
                {
                    "description": "List all child mortality indicators",
                    "code": 'ud.search_indicators(category="CME")',
                },
            ],
        },
        "list_indicators": {
            "signature": (
                "ud.list_indicators(\n"
                "    dataflow=None,           # str — filter by dataflow\n"
                "    name_contains=None,      # str — filter by name substring\n"
                ") -> dict[str, dict]"
            ),
            "returns": "Dictionary mapping indicator codes to metadata dicts {code, name, description, category}",
            "examples": [
                {
                    "description": "Get all nutrition indicators programmatically",
                    "code": 'indicators = ud.list_indicators(dataflow="NUTRITION")',
                },
            ],
        },
        "get_sdmx": {
            "signature": (
                "ud.get_sdmx(\n"
                '    agency="UNICEF",         # str — data agency\n'
                "    flow=None,               # str or list[str] — dataflow ID(s)\n"
                "    key=None,                # str or list[str] — SDMX key filter\n"
                "    start_period=None,       # int — start year\n"
                "    end_period=None,         # int — end year\n"
                '    labels="both",           # str — "id", "both", "none"\n'
                "    tidy=True,               # bool\n"
                "    page_size=100000,        # int\n"
                ") -> pd.DataFrame"
            ),
            "returns": "pandas DataFrame with raw SDMX response columns",
            "examples": [
                {
                    "description": "Low-level fetch from CME dataflow",
                    "code": 'df = ud.get_sdmx(flow="CME", key="CME_MRY0T4", start_period=2015, end_period=2023)',
                },
            ],
        },
    },
}


# ---------------------------------------------------------------------------
# R API reference
# ---------------------------------------------------------------------------

R_REFERENCE: dict[str, Any] = {
    "install": 'install.packages("unicefdata")  # or devtools::install_github("unicef-drp/unicefData", subdir="r")',
    "import": "library(unicefdata)",
    "functions": {
        "unicefData": {
            "signature": (
                "unicefData(\n"
                "    indicator = NULL,        # character — indicator code(s)\n"
                "    countries = NULL,         # character vector — ISO3 codes, NULL = all\n"
                '    year = NULL,              # numeric, character ("2015:2023"), or vector\n'
                '    sex = "_T",               # character — "_T", "M", "F"\n'
                "    totals = FALSE,           # logical — only return aggregate totals\n"
                "    tidy = TRUE,              # logical — standardize column names\n"
                "    country_names = TRUE,     # logical — add country name column\n"
                '    format = "long",          # character — "long", "wide", "wide_indicators"\n'
                "    latest = FALSE,           # logical — most recent value per country\n"
                "    circa = FALSE,            # logical — closest available year\n"
                "    add_metadata = NULL,      # character vector — e.g. c('region', 'income_group')\n"
                "    dropna = FALSE,           # logical — drop rows with missing values\n"
                "    simplify = FALSE,         # logical — minimal columns\n"
                "    mrv = NULL,               # integer — most recent N values per country\n"
                "    raw = FALSE,              # logical — all disaggregations, no filtering\n"
                ")"
            ),
            "returns": "tibble with columns: indicator_code, iso3, country, period, value, sex, age, wealth_quintile, residence, ...",
            "examples": [
                {
                    "description": "Under-5 mortality for Brazil, India, Nigeria (2015–2023)",
                    "code": 'df <- unicefData("CME_MRY0T4", countries = c("BRA", "IND", "NGA"), year = "2015:2023")',
                },
                {
                    "description": "Latest stunting data for all countries",
                    "code": 'df <- unicefData("NT_ANT_HAZ_NE2", latest = TRUE)',
                },
                {
                    "description": "Wide format with region metadata",
                    "code": 'df <- unicefData("CME_MRY0T4", format = "wide", add_metadata = c("region", "income_group"))',
                },
            ],
        },
        "search_indicators": {
            "signature": (
                "search_indicators(\n"
                '    query = NULL,             # character — search term\n'
                '    category = NULL,          # character — filter by dataflow\n'
                "    limit = 50,               # integer — max results\n"
                "    show_description = TRUE   # logical — include description\n"
                ")"
            ),
            "returns": "Prints formatted table; invisibly returns data.frame",
            "examples": [
                {
                    "description": "Search for stunting indicators",
                    "code": 'search_indicators("stunting")',
                },
            ],
        },
        "list_indicators": {
            "signature": (
                "list_indicators(\n"
                "    dataflow = NULL,          # character — filter by dataflow\n"
                "    name_contains = NULL      # character — filter by name substring\n"
                ")"
            ),
            "returns": "Named list of indicator metadata",
            "examples": [
                {
                    "description": "Get all nutrition indicators",
                    "code": 'indicators <- list_indicators(dataflow = "NUTRITION")',
                },
            ],
        },
    },
}


# ---------------------------------------------------------------------------
# Stata API reference
# ---------------------------------------------------------------------------

STATA_REFERENCE: dict[str, Any] = {
    "install": "ssc install unicefdata",
    "import": "// No import needed — unicefdata is a command",
    "functions": {
        "unicefdata": {
            "signature": (
                "unicefdata, indicator(code) [countries(iso3 list) year(range)\n"
                "    sex(string) age(string) wealth(string) residence(string)\n"
                "    wide wide_indicators latest circa mrv(integer)\n"
                "    dropna simplify raw addmeta(varlist)\n"
                "    clear verbose]"
            ),
            "returns": "Dataset loaded in memory with variables: iso3, country, indicator, period, value, sex, age, wealth_quintile, residence, ...",
            "examples": [
                {
                    "description": "Under-5 mortality for Brazil, India, Nigeria (2015–2023)",
                    "code": "unicefdata, indicator(CME_MRY0T4) countries(BRA IND NGA) year(2015:2023) clear",
                },
                {
                    "description": "Latest stunting data for all countries",
                    "code": "unicefdata, indicator(NT_ANT_HAZ_NE2) latest clear",
                },
                {
                    "description": "Search for mortality indicators",
                    "code": "unicefdata, search(mortality)",
                },
                {
                    "description": "List all child mortality indicators",
                    "code": "unicefdata, indicators(CME)",
                },
                {
                    "description": "Get info about a specific indicator",
                    "code": "unicefdata, info(CME_MRY0T4)",
                },
            ],
        },
        "search": {
            "signature": "unicefdata, search(query)",
            "returns": "Prints matching indicators to Results window",
            "examples": [
                {
                    "description": "Search for stunting indicators",
                    "code": "unicefdata, search(stunting)",
                },
            ],
        },
    },
}

# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

REFERENCES: dict[str, dict[str, Any]] = {
    "python": PYTHON_REFERENCE,
    "r": R_REFERENCE,
    "stata": STATA_REFERENCE,
}

VALID_LANGUAGES = set(REFERENCES.keys())
