"""Unit tests for `unicefstats_mcp.dimensions` (v1.2.0 Commit 1).

Tests run against the LIVE unicefdata-shipped YAMLs — no mocking — so they
also serve as a smoke test that the metadata snapshot has not drifted
incompatibly. Same discipline as ``test_v111_scoring.py``.

The high-value invariants pinned here:

- 122-indicator string-vs-list ``dataflows`` coercion (``primary_dataflow``).
- Tier-2 indicators return ``{}`` from ``dimensions_for_indicator`` (not raises).
- Routing dims (REF_AREA, INDICATOR, TIME_PERIOD) are filtered out.
- v1.1.1 forensic finding: ``CME_MRY0T4`` does not advertise AGE.
- ``HVA_EPI_INF_RT`` advertises AGE (HIV_AIDS dataflow has it).
- ``dimension_supported`` correctly rejects unsupported dims and values.
"""

from __future__ import annotations

from unicefstats_mcp import dimensions as d

# ---------------------------------------------------------------------------
# primary_dataflow — the 122-indicator silent-corruption fix
# ---------------------------------------------------------------------------


def test_primary_dataflow_handles_list() -> None:
    # HVA_EPI_INF_RT stores dataflows as a LIST in metadata
    assert d.primary_dataflow("HVA_EPI_INF_RT") == "HIV_AIDS"


def test_primary_dataflow_handles_bare_string() -> None:
    # HVA_PMTCT_ART_CVG stores dataflows as a BARE STRING in metadata —
    # without coercion, dataflows[0] would return 'H'.
    assert d.primary_dataflow("HVA_PMTCT_ART_CVG") == "HIV_AIDS"


def test_primary_dataflow_returns_none_for_tier2() -> None:
    # CME is a tier-2 family code with no dataflows field
    assert d.primary_dataflow("CME") is None


def test_primary_dataflow_returns_none_for_unknown_code() -> None:
    assert d.primary_dataflow("BOGUS_NONEXISTENT_CODE") is None


# ---------------------------------------------------------------------------
# dimensions_for_indicator — graceful tier-2, routing-dim filtering,
# and the v1.1.1 forensic AGE assertion
# ---------------------------------------------------------------------------


def test_dimensions_for_indicator_returns_expected_dims_for_hva() -> None:
    dims = d.dimensions_for_indicator("HVA_EPI_INF_RT")
    # HIV_AIDS dataflow has AGE, SEX, WEALTH_QUINTILE, RESIDENCE
    # (plus REF_AREA + INDICATOR which are routing dims and excluded).
    assert "AGE" in dims
    assert "SEX" in dims
    assert "WEALTH_QUINTILE" in dims
    assert "RESIDENCE" in dims


def test_dimensions_for_indicator_filters_routing_dims() -> None:
    dims = d.dimensions_for_indicator("HVA_EPI_INF_RT")
    assert "REF_AREA" not in dims
    assert "INDICATOR" not in dims
    assert "TIME_PERIOD" not in dims


def test_dimensions_for_indicator_returns_empty_for_tier2() -> None:
    # The structured tier-2 signal — callers branch on dict-equality with {}
    assert d.dimensions_for_indicator("CME") == {}


def test_dimensions_for_indicator_returns_empty_for_unknown() -> None:
    assert d.dimensions_for_indicator("BOGUS_NONEXISTENT_CODE") == {}


def test_u5mr_does_not_advertise_age() -> None:
    """Pins the v1.1.1 forensic finding as a regression test.

    CME_MRY0T4 is the under-five mortality rate — by code construction,
    it's already age-restricted to 0-4. The indicator's own metadata
    does NOT list AGE in its disaggregations, so dimensions_for_indicator
    must not surface AGE in the envelope. The v1.1.2 hardcoded triple
    falsely advertised it.
    """
    dims = d.dimensions_for_indicator("CME_MRY0T4")
    assert "AGE" not in dims, (
        "CME_MRY0T4 (U5MR) must not advertise AGE — pins v1.1.1 "
        "forensic finding."
    )


def test_hva_pmtct_art_cvg_dimensions_via_bare_string_path() -> None:
    """Cross-validates the string-vs-list fix end-to-end.

    HVA_PMTCT_ART_CVG.dataflows is a BARE STRING. Without coercion the
    primary_dataflow call would return 'H' and dimensions_for_indicator
    would return {} (no dataflow YAML at 'H.yaml'). With coercion, we
    get the full HIV_AIDS dim set.
    """
    dims = d.dimensions_for_indicator("HVA_PMTCT_ART_CVG")
    assert "AGE" in dims
    assert "SEX" in dims


# ---------------------------------------------------------------------------
# dimension_supported — the gate for get_data pre-flight validation
# ---------------------------------------------------------------------------


def test_dimension_supported_true_for_supported_dim() -> None:
    assert d.dimension_supported("HVA_EPI_INF_RT", "AGE") is True


def test_dimension_supported_true_for_supported_value() -> None:
    # Y15T19 is in HIV_AIDS CL_AGE codelist
    assert d.dimension_supported("HVA_EPI_INF_RT", "AGE", "Y15T19") is True


def test_dimension_supported_false_for_unsupported_dim() -> None:
    # EDUCATION_LEVEL is not in HIV_AIDS dataflow dimensions
    assert d.dimension_supported("HVA_EPI_INF_RT", "EDUCATION_LEVEL") is False


def test_dimension_supported_false_for_invalid_value() -> None:
    assert (
        d.dimension_supported("HVA_EPI_INF_RT", "AGE", "BOGUS_AGE_VALUE")
        is False
    )


def test_dimension_supported_false_for_tier2() -> None:
    assert d.dimension_supported("CME", "AGE") is False


# ---------------------------------------------------------------------------
# build_disaggregation_filters — get_indicator_info envelope
# ---------------------------------------------------------------------------


def test_build_disaggregation_filters_hva_has_age() -> None:
    out = d.build_disaggregation_filters("HVA_EPI_INF_RT")
    assert isinstance(out, dict)
    assert "AGE" in out
    assert "SEX" in out


def test_build_disaggregation_filters_u5mr_lacks_age() -> None:
    """Pins the v1.1.1 forensic finding at the envelope-construction layer."""
    out = d.build_disaggregation_filters("CME_MRY0T4")
    assert "AGE" not in out


def test_build_disaggregation_filters_tier2_returns_fallback() -> None:
    out = d.build_disaggregation_filters("CME")
    assert out == {"_source": "fallback_unknown", "dimensions": None}


# ---------------------------------------------------------------------------
# is_first_class_dim — the AGE-routing decision in get_data Commit 2
# ---------------------------------------------------------------------------


def test_first_class_dim_sex_only_in_2_4_x() -> None:
    """In unicefdata 2.4.x, only SEX is a first-class kwarg."""
    assert d.is_first_class_dim("SEX") is True
    assert d.is_first_class_dim("AGE") is False
    assert d.is_first_class_dim("WEALTH_QUINTILE") is False
    assert d.is_first_class_dim("RESIDENCE") is False


# ---------------------------------------------------------------------------
# filter_by_dimensions — the raw=True post-filter path
# ---------------------------------------------------------------------------


def test_filter_by_dimensions_empty_or_none_passthrough() -> None:
    import pandas as pd

    df = pd.DataFrame({"AGE": ["Y0T4", "Y5T9", "_T"], "value": [1, 2, 3]})

    # Empty filters dict → identity
    assert len(d.filter_by_dimensions(df, {})) == len(df)
    # None value → no-op for that dim (caller chose not to filter).
    assert len(d.filter_by_dimensions(df, {"AGE": None})) == len(df)


def test_filter_by_dimensions_T_is_a_real_filter_value() -> None:
    """v1.2.0 Commit 8 — '_T' is the SDMX totals code, not a sentinel
    for "no filter needed". The raw=True payload contains rows for
    every AGE / SEX / WQ value including '_T'; filtering to '_T' is
    how you request the totals slice. Earlier drafts treated '_T' as
    a no-op (Bug F), which caused sex='_T' default + age='Y15T19' to
    silently return all SEX values rather than only totals rows.
    """
    import pandas as pd

    df = pd.DataFrame({"AGE": ["Y0T4", "Y5T9", "_T"], "value": [1, 2, 3]})
    out = d.filter_by_dimensions(df, {"AGE": "_T"})
    assert len(out) == 1
    assert out["AGE"].iloc[0] == "_T"


def test_filter_by_dimensions_single_value() -> None:
    import pandas as pd

    df = pd.DataFrame(
        {"AGE": ["Y0T4", "Y5T9", "Y15T19"], "value": [1, 2, 3]}
    )
    out = d.filter_by_dimensions(df, {"AGE": "Y15T19"})
    assert len(out) == 1
    assert out["AGE"].iloc[0] == "Y15T19"


def test_filter_by_dimensions_list_value() -> None:
    import pandas as pd

    df = pd.DataFrame(
        {"AGE": ["Y0T4", "Y5T9", "Y15T19"], "value": [1, 2, 3]}
    )
    out = d.filter_by_dimensions(df, {"AGE": ["Y0T4", "Y15T19"]})
    assert len(out) == 2
    assert set(out["AGE"]) == {"Y0T4", "Y15T19"}


def test_filter_by_dimensions_case_insensitive_column() -> None:
    """unicefdata sometimes lowercases columns — the helper must cope."""
    import pandas as pd

    df = pd.DataFrame(
        {"age": ["Y0T4", "Y5T9", "Y15T19"], "value": [1, 2, 3]}
    )
    out = d.filter_by_dimensions(df, {"AGE": "Y15T19"})
    assert len(out) == 1
    assert out["age"].iloc[0] == "Y15T19"


def test_filter_by_dimensions_unknown_dim_skipped() -> None:
    """Unknown dims are silently skipped — caller validates first."""
    import pandas as pd

    df = pd.DataFrame(
        {"AGE": ["Y0T4", "Y5T9"], "value": [1, 2]}
    )
    out = d.filter_by_dimensions(df, {"EDUCATION_LEVEL": "ISCED11_2"})
    assert len(out) == 2


# ---------------------------------------------------------------------------
# indicators_supporting — foundation for v1.3.0 dimension_mismatch
# ---------------------------------------------------------------------------


def test_indicators_supporting_age_includes_hva() -> None:
    codes = d.indicators_supporting("AGE")
    # Many indicators support AGE; HVA_EPI_INF_RT must be among them.
    assert "HVA_EPI_INF_RT" in codes


def test_indicators_supporting_value_restricts_to_codelist() -> None:
    """Indicators whose AGE codelist contains Y15T19."""
    codes = d.indicators_supporting("AGE", "Y15T19")
    # HIV_AIDS dataflow has Y15T19; CME_MRY0T4 doesn't even surface AGE.
    assert "HVA_EPI_INF_RT" in codes


# ---------------------------------------------------------------------------
# Startup self-test
# ---------------------------------------------------------------------------


def test_indicator_metadata_loaded_at_import() -> None:
    """Pre-warm at module import must succeed against the shipped YAMLs."""
    meta = d.load_indicator_metadata()
    # 738 in unicefdata 2.4.x; tolerate minor drift across patches.
    assert len(meta) > 500
    # Sanity: required schema is present (the self-test would have raised
    # at import time if not — this is a belt-and-suspenders check).
    assert "code" in meta["HVA_EPI_INF_RT"]
    assert "tier" in meta["HVA_EPI_INF_RT"]
