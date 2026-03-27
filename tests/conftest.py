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
