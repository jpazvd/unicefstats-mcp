"""Shared fixtures for UNICEF Stats MCP tests."""

from __future__ import annotations

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Mock indicator registry (subset of real indicators)
# ---------------------------------------------------------------------------

MOCK_INDICATORS: dict[str, dict] = {
    "CME_MRY0T4": {
        "code": "CME_MRY0T4",
        "name": "Under-five mortality rate",
        "description": (
            "Probability of dying between birth and exactly 5 years of age, "
            "expressed per 1,000 live births."
        ),
        "category": "CME",
        "parent": None,
    },
    "CME_MRY0": {
        "code": "CME_MRY0",
        "name": "Neonatal mortality rate",
        "description": (
            "Probability of dying during the first 28 days of life, "
            "expressed per 1,000 live births."
        ),
        "category": "CME",
        "parent": None,
    },
    "NT_BF_EXBF": {
        "code": "NT_BF_EXBF",
        "name": "Exclusive breastfeeding",
        "description": "Percentage of infants 0-5 months of age exclusively breastfed.",
        "category": "NUTRITION",
        "parent": None,
    },
    "ED_ANAR_L1": {
        "code": "ED_ANAR_L1",
        "name": "Net attendance rate, primary education",
        "description": "Adjusted net attendance rate for primary school age children.",
        "category": "EDUCATION",
        "parent": None,
    },
    "PT_CHLD_1-14_LBR": {
        "code": "PT_CHLD_1-14_LBR",
        "name": "Child labour",
        "description": "Percentage of children aged 5-17 engaged in child labour.",
        "category": "CHILD_PROTECTION",
        "parent": None,
    },
}

# Extended fixture covering the indicator-resolver edge cases tracked in
# issue #64 (Indicator resolver picks wrong variant for 3 prompts).
# These reproduce the real-data shape: tier-2 category codes have NO
# `parent` field; tier-1 indicators do; derived metrics (national
# targets, annual-rate-of-reduction variants) carry the same name tokens
# as their canonical indicator but live in TRGT_* / *_ARR_* codes.
MOCK_INDICATORS_ISSUE_64: dict[str, dict] = {
    # Tier-2 category code — should be filtered out of search.
    "CME": {
        "code": "CME",
        "name": "Child mortality",
        "description": "Child mortality",
        # No `parent` field: this is a category, not an indicator.
    },
    # Tier-1: canonical mortality variants.
    "CME_MRY0T4": {
        "code": "CME_MRY0T4",
        "name": "Under-five mortality rate",
        "description": "Probability of dying before exact age 5 per 1,000 live births.",
        "category": "CME",
        "parent": "CME",
    },
    "CME_MRY0": {
        "code": "CME_MRY0",
        "name": "Infant mortality rate",
        "description": "Probability of dying before exact age 1 per 1,000 live births.",
        "category": "CME",
        "parent": "CME",
    },
    "CME_MRM0": {
        "code": "CME_MRM0",
        "name": "Neonatal mortality rate",
        "description": "Probability of dying within the first 28 days per 1,000 live births.",
        "category": "CME",
        "parent": "CME",
    },
    "CME_MRY1T4": {
        "code": "CME_MRY1T4",
        "name": "Child mortality rate (aged 1-4 years)",
        "description": "Probability of dying between exact ages 1 and 5.",
        "category": "CME",
        "parent": "CME",
    },
    # Derived metric: shares "U5MR" acronym with the canonical CME_MRY0T4.
    "CME_ARR_U5MR": {
        "code": "CME_ARR_U5MR",
        "name": "Annual Rate of Reduction in Under-five mortality rate",
        "description": "AARC for under-five mortality.",
        "category": "CME",
        "parent": "CME",
    },
    # Derived metric: national target shares the canonical name.
    "TRGT_2030_CME_MRY0T4": {
        "code": "TRGT_2030_CME_MRY0T4",
        "name": "National target (Year 2030) for Under-five mortality rate",
        "description": "Country-level 2030 target for U5MR.",
        "category": "TRGT",
        "parent": "TRGT_CME",
    },
    # Tier-1: early childbearing (the canonical MNCH_BIRTH18 indicator).
    "MNCH_BIRTH18": {
        "code": "MNCH_BIRTH18",
        "name": (
            "Early childbearing - percentage of women (aged 20-24 years) "
            "who gave birth before age 18"
        ),
        "description": (
            "Percentage of women aged 20-24 who reported a first birth "
            "before age 18."
        ),
        "category": "MNCH",
        "parent": "MNCH",
    },
    # Tier-1: confusable adolescent-fertility variant (population 15-19).
    "MNCH_ABR": {
        "code": "MNCH_ABR",
        "name": (
            "Adolescent birth rate (number of live births to adolescent "
            "women per 1,000 adolescent women)"
        ),
        "description": "Live births per 1,000 women aged 15-19.",
        "category": "MNCH",
        "parent": "MNCH",
    },
}


MOCK_COUNTRIES: dict[str, str] = {
    "AFG": "Afghanistan",
    "ALB": "Albania",
    "ARG": "Argentina",
    "BRA": "Brazil",
    "CHN": "China",
    "IND": "India",
    "MEX": "Mexico",
    "NGA": "Nigeria",
    "USA": "United States",
    "ZWE": "Zimbabwe",
}


@pytest.fixture
def mock_indicators():
    return MOCK_INDICATORS.copy()


@pytest.fixture
def mock_countries():
    return MOCK_COUNTRIES.copy()


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """A small DataFrame mimicking unicefData() output."""
    return pd.DataFrame(
        {
            "country_code": ["BRA", "BRA", "BRA", "ARG", "ARG", "ARG"],
            "country_name": [
                "Brazil", "Brazil", "Brazil",
                "Argentina", "Argentina", "Argentina",
            ],
            "indicator_code": ["CME_MRY0T4"] * 6,
            "period": [2019, 2020, 2021, 2019, 2020, 2021],
            "value": [14.5, 14.2, 13.8, 9.9, 9.8, 9.5],
            "sex": ["_T"] * 6,
            "age": ["Y0T4"] * 6,
            "wealth_quintile": ["_T"] * 6,
            "residence": ["_T"] * 6,
            "obs_status": ["A"] * 6,
            "data_source": ["IGME"] * 6,
            "lower_bound": [13.0, 12.8, 12.2, 8.5, 8.3, 8.1],
            "upper_bound": [16.0, 15.7, 15.4, 11.3, 11.2, 10.9],
        }
    )


@pytest.fixture
def disaggregated_dataframe() -> pd.DataFrame:
    """DataFrame with sex disaggregation for testing summaries."""
    return pd.DataFrame(
        {
            "country_code": ["BRA"] * 6,
            "country_name": ["Brazil"] * 6,
            "indicator_code": ["CME_MRY0T4"] * 6,
            "period": [2020, 2020, 2020, 2021, 2021, 2021],
            "value": [16.1, 12.3, 14.2, 15.5, 11.8, 13.8],
            "sex": ["M", "F", "_T", "M", "F", "_T"],
            "age": ["Y0T4"] * 6,
            "wealth_quintile": ["_T"] * 6,
            "residence": ["_T"] * 6,
            "obs_status": ["A"] * 6,
            "data_source": ["IGME"] * 6,
            "lower_bound": [14.0] * 6,
            "upper_bound": [18.0] * 6,
        }
    )
