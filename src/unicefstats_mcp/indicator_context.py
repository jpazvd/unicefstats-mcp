"""Semantic context for UNICEF indicators.

Provides related indicators, disambiguation notes, SDG targets, and
data collection methodology context for the 10 benchmark indicators
and their siblings. This information helps prevent LLM errors like
indicator confusion, missing context, and fabrication for sparse data.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# SDG targets with threshold values
# ---------------------------------------------------------------------------

SDG_TARGETS: dict[str, dict[str, Any]] = {
    "CME_MRY0T4": {
        "goal": "3.2",
        "target": "3.2.1",
        "description": "By 2030, end preventable deaths of newborns and children under 5",
        "target_value": 25,
        "target_unit": "per 1,000 live births",
        "target_year": 2030,
    },
    "CME_MRM0": {
        "goal": "3.2",
        "target": "3.2.2",
        "description": "By 2030, end preventable deaths of newborns",
        "target_value": 12,
        "target_unit": "per 1,000 live births",
        "target_year": 2030,
    },
    "CME_MRY0": {
        "goal": "3.2",
        "target": "3.2.1",
        "description": "By 2030, end preventable deaths of newborns and children under 5",
        "target_value": None,
        "target_unit": "per 1,000 live births",
        "target_year": 2030,
        "note": "No explicit SDG target for infant mortality; tracked under 3.2.1",
    },
    "CME_MRY1T4": {
        "goal": "3.2",
        "target": "3.2.1",
        "description": "By 2030, end preventable deaths of children under 5",
        "target_value": None,
        "target_unit": "per 1,000 children aged 1",
        "target_year": 2030,
        "note": "No explicit SDG target for child (1-4) mortality; tracked under 3.2.1",
    },
    "NT_ANT_HAZ_NE2": {
        "goal": "2.2",
        "target": "2.2.1",
        "description": "By 2030, end all forms of malnutrition",
        "target_value": None,
        "target_unit": "percentage",
        "target_year": 2030,
        "note": "WHA target: 40% reduction from 2012 baseline by 2025",
    },
    "NT_ANT_WAZ_NE2": {
        "goal": "2.2",
        "target": "2.2.1",
        "description": "By 2030, end all forms of malnutrition",
        "target_value": None,
        "target_unit": "percentage",
        "target_year": 2030,
    },
    "NT_ANT_WHZ_NE2": {
        "goal": "2.2",
        "target": "2.2.1",
        "description": "By 2030, end all forms of malnutrition",
        "target_value": 5,
        "target_unit": "percentage",
        "target_year": 2030,
        "note": "WHA target: reduce and maintain wasting below 5%",
    },
    "MNCH_CSEC": {
        "goal": "3.1",
        "target": "3.1.1",
        "description": "Reduce the global maternal mortality ratio",
        "target_value": None,
        "target_unit": "percentage",
        "target_year": 2030,
        "note": "WHO recommended range: 10-15%. Both too low and too high rates indicate problems.",
    },
    "MNCH_BIRTH18": {
        "goal": "3.7",
        "target": "3.7.2",
        "description": "Ensure universal access to sexual and reproductive health-care services",
        "target_value": None,
        "target_unit": "percentage",
        "target_year": 2030,
    },
    "ED_CR_L1": {
        "goal": "4.1",
        "target": "4.1.2",
        "description": "All girls and boys complete free, equitable and quality primary education",
        "target_value": 100,
        "target_unit": "percentage",
        "target_year": 2030,
    },
}


# ---------------------------------------------------------------------------
# Related indicators and disambiguation
# ---------------------------------------------------------------------------

RELATED_INDICATORS: dict[str, dict[str, Any]] = {
    "CME_MRY0T4": {
        "related": ["CME_MRM0", "CME_MRY0", "CME_MRY1T4"],
        "disambiguation": (
            "Under-5 mortality (0-59 months) is the broadest child mortality measure. "
            "It encompasses neonatal (0-28 days), post-neonatal (1-11 months), "
            "and child (1-4 years) mortality. "
            "CME_MRY0T4 ≈ CME_MRM0 + post-neonatal + CME_MRY1T4."
        ),
    },
    "CME_MRM0": {
        "related": ["CME_MRY0T4", "CME_MRY0", "CME_MRY1T4"],
        "disambiguation": (
            "Neonatal mortality covers the first 28 days of life only. "
            "It is a SUBSET of infant mortality (CME_MRY0, 0-12 months) "
            "and under-5 mortality (CME_MRY0T4, 0-59 months). "
            "Neonatal deaths account for ~47% of under-5 deaths globally."
        ),
    },
    "CME_MRY0": {
        "related": ["CME_MRM0", "CME_MRY0T4", "CME_MRY1T4"],
        "disambiguation": (
            "Infant mortality covers 0-12 months. "
            "It includes neonatal (CME_MRM0, 0-28 days) plus post-neonatal (1-11 months). "
            "Do NOT confuse with under-5 mortality (CME_MRY0T4) which extends to 59 months."
        ),
    },
    "CME_MRY1T4": {
        "related": ["CME_MRY0T4", "CME_MRY0", "CME_MRM0"],
        "disambiguation": (
            "Child mortality (1-4 years) excludes the first year of life. "
            "Expressed per 1,000 children surviving to age 1 (not per 1,000 live births). "
            "Different denominator than neonatal/infant/under-5 rates."
        ),
    },
    "NT_ANT_HAZ_NE2": {
        "related": ["NT_ANT_WAZ_NE2", "NT_ANT_WHZ_NE2", "NT_ANT_HAZ_NE3"],
        "disambiguation": (
            "Stunting (height-for-age <-2 SD) reflects CHRONIC malnutrition. "
            "Different from wasting (weight-for-height, ACUTE) and "
            "underweight (weight-for-age, COMPOSITE of both). "
            "Data comes from household surveys (DHS/MICS) conducted every 3-5 years — "
            "NOT available annually for most countries."
        ),
    },
    "NT_ANT_WAZ_NE2": {
        "related": ["NT_ANT_HAZ_NE2", "NT_ANT_WHZ_NE2"],
        "disambiguation": (
            "Underweight (weight-for-age <-2 SD) is a COMPOSITE measure — "
            "reflects both chronic (stunting) and acute (wasting) malnutrition. "
            "Survey-based: not available annually."
        ),
    },
    "NT_ANT_WHZ_NE2": {
        "related": ["NT_ANT_HAZ_NE2", "NT_ANT_WAZ_NE2"],
        "disambiguation": (
            "Wasting (weight-for-height <-2 SD) reflects ACUTE malnutrition. "
            "Can change rapidly (seasonal, crisis). Different from stunting (chronic). "
            "Survey-based: not available annually."
        ),
    },
    "MNCH_CSEC": {
        "related": ["MNCH_BIRTH18"],
        "disambiguation": (
            "C-section rate. Both too low (<10%) and too high (>15%) rates "
            "indicate health system problems. High-income countries often have "
            "rates >30% (over-medicalization), while low-income countries may "
            "be <5% (lack of access to emergency obstetric care)."
        ),
    },
    "MNCH_BIRTH18": {
        "related": ["MNCH_CSEC"],
        "disambiguation": (
            "Percentage of births to women under 18. "
            "Reflects adolescent pregnancy prevalence. "
            "Survey-based: not available annually."
        ),
    },
    "ED_CR_L1": {
        "related": [],
        "disambiguation": (
            "Primary education completion rate. "
            "Measured as percentage of children 3-5 years above intended age "
            "for last grade of primary who have completed that grade. "
            "Data from UIS (UNESCO Institute for Statistics)."
        ),
    },
}


# ---------------------------------------------------------------------------
# Data collection methodology (affects data availability)
# ---------------------------------------------------------------------------

DATA_METHODOLOGY: dict[str, dict[str, str]] = {
    "CME": {
        "source": "UN Inter-agency Group for Child Mortality Estimation (IGME)",
        "frequency": "Annual modeled estimates based on all available data",
        "availability": "Annual time series for most countries",
        "note": "Modeled estimates — available annually even if no new survey",
    },
    "NUTRITION": {
        "source": "UNICEF/WHO/World Bank Joint Malnutrition Estimates (JME)",
        "frequency": "Survey-based (DHS, MICS) — every 3-5 years per country",
        "availability": "Sparse — most countries have only 2-5 data points across 20 years",
        "note": "Data gaps are expected. Do NOT fabricate values for missing years.",
    },
    "MNCH": {
        "source": "UNICEF global databases (DHS, MICS, other surveys)",
        "frequency": "Survey-based — every 3-5 years per country",
        "availability": "Sparse — similar to nutrition indicators",
        "note": "C-section data may also come from health facility records.",
    },
    "EDUCATION": {
        "source": "UNESCO Institute for Statistics (UIS)",
        "frequency": "Annual for countries with functioning EMIS",
        "availability": "Varies widely by country income level",
        "note": "Low-income countries may have significant gaps.",
    },
}


# ---------------------------------------------------------------------------
# Aggregation groups for benchmarking
# ---------------------------------------------------------------------------

# UNICEF regions (ISO3 codes for aggregate queries)
UNICEF_REGIONS: dict[str, str] = {
    "EAP": "East Asia and Pacific",
    "ECA": "Europe and Central Asia",
    "ESA": "Eastern and Southern Africa",
    "LAC": "Latin America and Caribbean",
    "MNA": "Middle East and North Africa",
    "NAM": "North America",
    "SAR": "South Asia",
    "SSA": "Sub-Saharan Africa",
    "WCA": "West and Central Africa",
    "WLD": "World",
}

# World Bank income groups
INCOME_GROUPS: dict[str, str] = {
    "LIC": "Low-income countries",
    "LMC": "Lower-middle-income countries",
    "UMC": "Upper-middle-income countries",
    "HIC": "High-income countries",
}


def get_indicator_context(code: str) -> dict[str, Any]:
    """Return full semantic context for an indicator."""
    context: dict[str, Any] = {}

    if code in RELATED_INDICATORS:
        ri = RELATED_INDICATORS[code]
        context["related_indicators"] = ri["related"]
        context["disambiguation"] = ri["disambiguation"]

    if code in SDG_TARGETS:
        context["sdg_target"] = SDG_TARGETS[code]

    # Determine dataflow category for methodology
    prefix = code.split("_")[0] if "_" in code else code
    for cat, meth in DATA_METHODOLOGY.items():
        if cat in prefix or code.startswith(cat):
            context["data_methodology"] = meth
            break

    return context
