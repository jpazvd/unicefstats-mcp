"""v1.2.0 Commit 2 tests — get_data `age` + `filters` dict + `mode='raw_filtered'`.

The high-value invariants pinned here, matched 1:1 to the Verification gate
2 checklist in the v1.2.0 plan:

  - Silent-drop fix observable: filters={WEALTH_QUINTILE: Q1} returns
    mode='raw_filtered' (v1.1.2 silently returned totals).
  - AGE rerouting: age='Y15T19' engages raw=True + post-filter.
  - Tier-2 refusal: get_data('CME', ...) refuses with tier_reason.
  - Pre-flight validation: unsupported dim → failed_validation envelope.
  - Multi-dataflow routing: HVA → HIV_AIDS (not GLOBAL_DATAFLOW).
  - v1.1.x backward compat: sex='F' alone surfaces no mode field /
    same DataFrame shape.
  - Removed-kwarg trip-wire: wealth_quintile='Q1' as a kwarg refuses with
    migration error (NOT a silent acceptance, NOT a silent drop).

Tests mock `_get_ud` so unicefData() returns a controlled DataFrame; the
filtering / routing / envelope-construction logic in get_data is what's
under test, NOT the upstream SDMX call.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from unicefstats_mcp.server import get_data


@pytest.fixture(autouse=True)
def _isolate_frontier_cache(monkeypatch):
    monkeypatch.setattr("unicefstats_mcp.server._data_frontier_cache", {})


# Common DataFrame shape for the mocked unicefData() return — covers the
# columns the raw-filter path needs to slice on.
def _make_hva_df_with_age() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "country_code": ["THA"] * 6,
            "country_name": ["Thailand"] * 6,
            "indicator_code": ["HVA_EPI_INF_RT"] * 6,
            "period": [2020] * 3 + [2021] * 3,
            "value": [0.05, 0.08, 0.04, 0.06, 0.09, 0.05],
            "sex": ["_T"] * 6,
            "AGE": ["Y0T14", "Y15T19", "Y15T49"] * 2,
            "WEALTH_QUINTILE": ["_T"] * 6,
            "RESIDENCE": ["_T"] * 6,
        }
    )


def _make_nt_df_with_wq() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "country_code": ["BDI"] * 4,
            "country_name": ["Burundi"] * 4,
            "indicator_code": ["NT_BF_EXBF"] * 4,
            "period": [2019, 2019, 2020, 2020],
            "value": [82.1, 71.3, 83.0, 70.2],
            "sex": ["_T"] * 4,
            "AGE": ["Y0T5"] * 4,
            "WEALTH_QUINTILE": ["Q1", "Q5", "Q1", "Q5"],
            "RESIDENCE": ["_T"] * 4,
        }
    )


# ---------------------------------------------------------------------------
# Silent-drop fix observable + auto-engage mode='raw_filtered'
# ---------------------------------------------------------------------------


@patch("unicefstats_mcp.server._get_ud")
def test_filters_wealth_quintile_engages_raw_filtered_mode(mock_ud):
    """v1.1.2 silently dropped wealth_quintile; v1.2.0 surfaces mode."""
    ud = MagicMock()
    ud.unicefData.return_value = _make_nt_df_with_wq()
    mock_ud.return_value = ud

    result = get_data(
        indicator="NT_BF_EXBF",
        countries=["BDI"],
        filters={"WEALTH_QUINTILE": "Q1"},
    )

    assert "error" not in result, result
    assert result["mode"] == "raw_filtered"
    # The underlying unicefData() call must have been routed with raw=True.
    call_kwargs = ud.unicefData.call_args.kwargs
    assert call_kwargs.get("raw") is True
    # And the dataflow must be the indicator's primary, not GLOBAL_DATAFLOW.
    assert call_kwargs.get("dataflow") == "NUTRITION"
    # The applied_filters envelope field exposes what was post-filtered.
    # v1.2.0 Commit 8 — sex='_T' (default) folded into the post-filter
    # on raw_filtered mode since unicefdata's raw=True bypasses the
    # sex= kwarg; without this the response would silently include all
    # SEX values rather than just totals.
    assert result.get("applied_filters") == {"WEALTH_QUINTILE": "Q1", "SEX": "_T"}
    assert result.get("dataflow_used") == "NUTRITION"


# ---------------------------------------------------------------------------
# AGE rerouting via raw=True + post-filter
# ---------------------------------------------------------------------------


@patch("unicefstats_mcp.server._get_ud")
def test_age_engages_raw_filtered_mode_with_hiv_aids_dataflow(mock_ud):
    """age='Y15T19' on HVA_EPI_INF_RT engages raw_filtered + routes to HIV_AIDS."""
    ud = MagicMock()
    ud.unicefData.return_value = _make_hva_df_with_age()
    mock_ud.return_value = ud

    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="Y15T19",
    )

    assert "error" not in result, result
    assert result["mode"] == "raw_filtered"
    call_kwargs = ud.unicefData.call_args.kwargs
    assert call_kwargs.get("raw") is True
    assert call_kwargs.get("dataflow") == "HIV_AIDS"
    # v1.2.0 Commit 8 — when raw_filtered mode engages, the post-filter
    # also applies the requested sex value (default '_T' = totals) so
    # the response respects the user's intended slice. unicefdata's
    # raw=True bypasses the sex= kwarg, so the MCP-side filter is the
    # only one in play.
    assert result.get("applied_filters") == {"AGE": "Y15T19", "SEX": "_T"}
    assert result.get("dataflow_used") == "HIV_AIDS"


# ---------------------------------------------------------------------------
# Pre-flight validation — unsupported dim refuses with failed_validation
# ---------------------------------------------------------------------------


def test_unsupported_dim_refuses_with_failed_validation_envelope():
    """HVA_EPI_INF_RT does not expose EDUCATION_LEVEL — the call must refuse
    BEFORE any SDMX request, with structured `failed_validation` listing
    `available_dimensions` so the LLM can recover in one wave.
    """
    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        filters={"EDUCATION_LEVEL": "ISCED11_2"},
    )

    assert "error" in result
    assert "Pre-flight filter validation failed" in result["error"]
    failed = result.get("failed_validation")
    assert failed is not None
    assert failed["dataflow_used"] == "HIV_AIDS"
    assert any(
        r["dim"] == "EDUCATION_LEVEL" and r["reason"] == "unsupported_dim"
        for r in failed["rejected"]
    )
    # available_dimensions surfaces the actual dim set so the LLM picks one.
    assert "AGE" in failed["available_dimensions"]
    assert "SEX" in failed["available_dimensions"]


def test_unsupported_value_in_supported_dim_refuses_with_invalid_value_reason():
    """AGE is supported on HVA_EPI_INF_RT, but BOGUS_AGE isn't in the codelist."""
    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="BOGUS_AGE",
    )

    assert "error" in result
    failed = result.get("failed_validation")
    assert failed is not None
    rejected = failed["rejected"]
    assert any(
        r["dim"] == "AGE" and r["reason"] == "invalid_value"
        for r in rejected
    )


# ---------------------------------------------------------------------------
# Tier-2 graceful refusal
# ---------------------------------------------------------------------------


def test_tier2_indicator_unfiltered_refuses_with_tier_reason():
    """v1.2.0 follow-up — earlier the tier-2 refusal only fired when
    `effective_filters` was non-empty, so `get_data('CME', countries=[...])`
    with no filters fell through to the SDMX 404 path and returned a
    generic no-data error. The LLM lost the structured `tier_reason`
    signal it needs to pivot to `search_indicators()`. Refusal must
    fire unconditionally for known tier-2 codes.
    """
    result = get_data(
        indicator="CME",
        countries=["BDI"],
    )
    assert "error" in result
    assert result.get("tier") == 2
    assert result.get("tier_reason") in {
        "no_dataflow_metadata",
        "metadata_only_no_data",
    }


def test_unknown_indicator_with_filters_is_not_mislabeled_as_tier2():
    """v1.2.0 follow-up — the tier-2 refusal must distinguish KNOWN
    tier-2 codes (`CME` has metadata, tier=2) from UNKNOWN codes
    (no metadata at all). Pre-fix the same "no associated dataflow
    metadata" error claimed everything was tier-2; that's misleading
    for codes the user simply mistyped or that aren't in the snapshot.
    """
    result = get_data(
        indicator="BOGUS_NONEXISTENT_CODE",
        countries=["BDI"],
        filters={"WEALTH_QUINTILE": "Q1"},
    )
    assert "error" in result
    # Distinct envelope shape — `metadata_status: 'unknown_code'`, NOT
    # tier=2.
    assert result.get("metadata_status") == "unknown_code"
    assert result.get("tier") is None


def test_tier2_indicator_with_filters_refuses_with_tier_reason():
    """CME is a tier-2 family code (no dataflow metadata). get_data refuses
    structurally, NOT with a downstream SDMX error.
    """
    result = get_data(
        indicator="CME",
        countries=["BDI"],
        filters={"WEALTH_QUINTILE": "Q1"},
    )

    assert "error" in result
    assert result.get("tier") == 2
    # v1.2.0 follow-up: tier_reason is now sourced from the metadata's
    # actual `tier_reason` field (e.g. `metadata_only_no_data` for CME)
    # rather than a hardcoded `no_dataflow_metadata`. Either is a valid
    # tier-2 signal; the metadata-grounded value is more honest.
    assert result.get("tier_reason") in {
        "no_dataflow_metadata",
        "metadata_only_no_data",
    }


# ---------------------------------------------------------------------------
# v1.1.x backward-compat smoke — sex='F' alone is unchanged
# ---------------------------------------------------------------------------


@patch("unicefstats_mcp.server._get_ud")
def test_v1_1_x_sex_only_call_is_first_class_mode(mock_ud):
    """A v1.1.x-shape call (sex='F' only, no other dim filter) stays on
    the first_class path — no raw=True, no post-filter, no mode visible
    to the caller as the noisy 'raw_filtered' signal (it's still set, but
    the value is 'first_class' so semantics are preserved).
    """
    ud = MagicMock()
    ud.unicefData.return_value = _make_nt_df_with_wq()
    mock_ud.return_value = ud

    result = get_data(
        indicator="NT_BF_EXBF",
        countries=["BDI"],
        sex="F",
    )

    assert "error" not in result, result
    assert result["mode"] == "first_class"
    call_kwargs = ud.unicefData.call_args.kwargs
    # No raw=True in first_class mode.
    assert "raw" not in call_kwargs
    # The dataflow is still routed (a v1.2.0 improvement that's
    # backward-compat — the call still succeeds, just with the correct
    # dataflow rather than GLOBAL_DATAFLOW).
    assert call_kwargs.get("dataflow") == "NUTRITION"
    # sex passes through as a typed kwarg.
    assert call_kwargs.get("sex") == "F"
    # applied_filters is NOT set in first_class mode (envelope stays lean).
    assert "applied_filters" not in result


# ---------------------------------------------------------------------------
# Commit 6 — country filter on raw=True (Bug A) + column normalisation
# (Bug B) + dimensions_available envelope + auto-totals fallback
# ---------------------------------------------------------------------------


@patch("unicefstats_mcp.server._get_ud")
def test_raw_filtered_path_post_filters_by_country(mock_ud):
    """v1.2.0 Commit 6 Bug A fix — ud.unicefData(raw=True) silently
    returns ALL countries in the dataflow, ignoring `countries=[...]`.
    The MCP must post-filter by REF_AREA so callers get only their
    requested countries.
    """
    # DataFrame mimicking the raw=True / SDMX shape (REF_AREA in
    # uppercase) with rows for multiple countries.
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["BDI", "BDI", "AFG", "AFG", "GIN"],
            "INDICATOR": ["NT_BF_EXBF"] * 5,
            "TIME_PERIOD": [2020, 2020, 2020, 2020, 2020],
            "OBS_VALUE": [82.1, 71.3, 50.0, 49.5, 60.0],
            "SEX": ["_T"] * 5,
            "AGE": ["Y0T5"] * 5,
            "WEALTH_QUINTILE": ["Q1", "Q5", "Q1", "Q5", "Q1"],
            "RESIDENCE": ["_T"] * 5,
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    result = get_data(
        indicator="NT_BF_EXBF",
        countries=["BDI"],
        filters={"WEALTH_QUINTILE": "Q1"},
    )
    assert "error" not in result, result
    assert result["mode"] == "raw_filtered"
    # The country filter must have dropped AFG + GIN rows.
    # BDI + WEALTH_QUINTILE=Q1 leaves exactly 1 row.
    assert result["rows_returned"] == 1
    assert result["data"][0]["iso3"] == "BDI"


@patch("unicefstats_mcp.server._get_ud")
def test_raw_filtered_path_normalises_sdmx_column_names(mock_ud):
    """v1.2.0 Commit 6 Bug B fix — raw=True returns SDMX-shape columns
    (REF_AREA, OBS_VALUE, TIME_PERIOD, INDICATOR); v1.1.x to_compact
    silently produced 0 records because it only knew about country_code
    / iso3 etc. The fix: add raw-name aliases to COLUMN_ALIASES so the
    LLM-facing keys are the canonical iso3/period/value/indicator.
    """
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["THA", "THA"],
            "INDICATOR": ["HVA_EPI_INF_RT"] * 2,
            "TIME_PERIOD": [2020, 2021],
            "OBS_VALUE": [0.10, 0.09],
            "SEX": ["_T"] * 2,
            "AGE": ["Y15T19"] * 2,
            "WEALTH_QUINTILE": ["_T"] * 2,
            "RESIDENCE": ["_T"] * 2,
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="Y15T19",
        format="compact",
    )
    assert "error" not in result, result
    assert result["mode"] == "raw_filtered"
    assert result["rows_returned"] == 2
    # LLM-facing keys must be the canonical schema, not the SDMX raw shape.
    row = result["data"][0]
    assert "iso3" in row and row["iso3"] == "THA"
    assert "period" in row
    assert "value" in row
    assert "indicator" in row
    # The SDMX-shape keys must NOT appear (no leakage).
    assert "REF_AREA" not in row
    assert "OBS_VALUE" not in row
    assert "TIME_PERIOD" not in row


@patch("unicefstats_mcp.server._get_ud")
def test_dimensions_available_envelope_on_every_successful_response(mock_ud):
    """v1.2.0 Commit 6 — v1.3.0 dim-menu candidate pulled forward.
    Every successful get_data response carries dimensions_available so
    the LLM can pick a valid disaggregation without an extra
    get_indicator_info round-trip.
    """
    raw_df = pd.DataFrame(
        {
            "country_code": ["BDI"] * 2,
            "country_name": ["Burundi"] * 2,
            "indicator_code": ["NT_BF_EXBF"] * 2,
            "period": [2020, 2021],
            "value": [82.0, 83.0],
            "sex": ["_T"] * 2,
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    # First_class mode (sex='_T' default, no filter).
    result = get_data(indicator="NT_BF_EXBF", countries=["BDI"])
    assert "error" not in result, result
    assert result["mode"] == "first_class"
    assert "dimensions_available" in result
    dims = result["dimensions_available"]
    # NT_BF_EXBF's primary dataflow is NUTRITION; AGE / WEALTH_QUINTILE
    # / RESIDENCE etc. must be in the menu.
    assert "AGE" in dims
    assert "WEALTH_QUINTILE" in dims


@patch("unicefstats_mcp.server._get_ud")
def test_auto_totals_fallback_when_filter_yields_zero_rows(mock_ud):
    """v1.2.0 Commit 6 — user-directed UX. When the raw_filtered post-
    filter yields 0 rows, MCP auto-substitutes the totals slice (re-fetch
    without the filter) so the LLM gets data + a menu instead of error
    + retry. Reduces wave count on the unhappy path.
    """
    # First call returns the raw payload (5 rows, NONE match Q1).
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["BDI"] * 5,
            "INDICATOR": ["NT_BF_EXBF"] * 5,
            "TIME_PERIOD": [2020] * 5,
            "OBS_VALUE": [82.0, 81.0, 80.0, 79.0, 78.0],
            "SEX": ["_T"] * 5,
            "AGE": ["Y0T5"] * 5,
            # All rows have WEALTH_QUINTILE='Q5'; filter for Q1 yields 0.
            "WEALTH_QUINTILE": ["Q5"] * 5,
            "RESIDENCE": ["_T"] * 5,
        }
    )
    # Second call (totals fallback) returns simplified totals.
    totals_df = pd.DataFrame(
        {
            "iso3": ["BDI", "BDI"],
            "country": ["Burundi"] * 2,
            "indicator": ["NT_BF_EXBF"] * 2,
            "period": [2020, 2021],
            "value": [82.5, 83.0],
        }
    )
    ud = MagicMock()
    ud.unicefData.side_effect = [raw_df, totals_df]
    mock_ud.return_value = ud

    result = get_data(
        indicator="NT_BF_EXBF",
        countries=["BDI"],
        filters={"WEALTH_QUINTILE": "Q1"},
    )
    assert "error" not in result, result
    assert result["mode"] == "totals_fallback"
    assert result["rows_returned"] == 2
    # The alert must name the substitution and point at dimensions_available.
    alert = result.get("alert", "")
    assert "TOTALS" in alert or "totals" in alert
    assert "dimensions_available" in alert
    # The original request is preserved so the LLM knows what to retry
    # with. v1.2.0 Commit 8 — sex='_T' (default) is also folded into
    # the post-filter on raw_filtered, so it appears in the preserved
    # filter snapshot too.
    assert result["filter_requested_no_data"] == {
        "WEALTH_QUINTILE": "Q1",
        "SEX": "_T",
    }
    # The fallback path must have made exactly 2 unicefData calls.
    assert ud.unicefData.call_count == 2
    # First call has raw=True; second drops it.
    assert ud.unicefData.call_args_list[0].kwargs.get("raw") is True
    assert "raw" not in ud.unicefData.call_args_list[1].kwargs


@patch("unicefstats_mcp.server._get_ud")
def test_totals_fallback_returns_no_data_error_when_indicator_truly_empty(mock_ud):
    """When both raw_filtered AND the totals fallback yield no rows,
    the MCP returns a clean no_data error (not silent empty data) so
    the LLM sees a definitive signal that the indicator+country combo
    is barren.
    """
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["BDI"] * 2,
            "INDICATOR": ["NT_BF_EXBF"] * 2,
            "TIME_PERIOD": [2020, 2021],
            "OBS_VALUE": [82.0, 83.0],
            "SEX": ["_T"] * 2,
            "AGE": ["Y0T5"] * 2,
            "WEALTH_QUINTILE": ["Q5"] * 2,
            "RESIDENCE": ["_T"] * 2,
        }
    )
    empty_totals = pd.DataFrame()
    ud = MagicMock()
    ud.unicefData.side_effect = [raw_df, empty_totals]
    mock_ud.return_value = ud

    result = get_data(
        indicator="NT_BF_EXBF",
        countries=["BDI"],
        filters={"WEALTH_QUINTILE": "Q1"},
    )
    assert "error" in result
    assert (
        "totals fallback also returned no data" in result["error"]
        or "no data" in result["error"].lower()
    )


# ---------------------------------------------------------------------------
# Commit 7 — column normalisation so the raw_filtered envelope matches
# the first_class envelope's field completeness (summary,
# disaggregations_in_data, data_frontier, countries_returned_with_names,
# trend_5yr). Bug C + Bug D.
# ---------------------------------------------------------------------------


@patch("unicefstats_mcp.server._get_ud")
def test_raw_filtered_envelope_has_summary_field_populated(mock_ud):
    """v1.2.0 Commit 7 Bug C — summarize_data was silently no-op on
    raw=True column shape (looked for `value`, found `OBS_VALUE`).
    """
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["BDI"] * 3,
            "INDICATOR": ["NT_BF_EXBF"] * 3,
            "TIME_PERIOD": [2019, 2020, 2021],
            "OBS_VALUE": [82.0, 83.5, 85.0],
            "SEX": ["_T"] * 3,
            "AGE": ["Y0T5"] * 3,
            "WEALTH_QUINTILE": ["Q1"] * 3,
            "RESIDENCE": ["_T"] * 3,
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    result = get_data(
        indicator="NT_BF_EXBF",
        countries=["BDI"],
        filters={"WEALTH_QUINTILE": "Q1"},
    )
    assert "error" not in result, result
    s = result.get("summary", {})
    assert "value_range" in s
    assert s["value_range"]["min"] == 82.0
    assert s["value_range"]["max"] == 85.0
    assert "year_range" in s
    assert s["year_range"]["earliest"] == 2019
    assert s["year_range"]["latest"] == 2021
    assert s["countries_in_result"] == 1


@patch("unicefstats_mcp.server._get_ud")
def test_raw_filtered_value_string_safe_coercion(mock_ud):
    """v1.2.0 Commit 7 Bug D — OBS_VALUE in raw=True is a STRING
    (sometimes `"<0.01"` for below-detection). Pre-Commit 7,
    `summarize_data` crashed with `TypeError: Could not convert string
    '0.350.310.27...' to numeric` because pandas concatenated the
    string values during `.mean()`. The fix: safe-coerce via
    pd.to_numeric(errors='coerce') so censored cells become NaN and
    drop out of the stats without crashing.
    """
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["THA"] * 4,
            "INDICATOR": ["HVA_EPI_INF_RT"] * 4,
            "TIME_PERIOD": [2019, 2020, 2021, 2022],
            # Mix of clean strings, a censored cell, and a clean number
            "OBS_VALUE": ["0.35", "<0.01", "0.27", "0.24"],
            "SEX": ["_T"] * 4,
            "AGE": ["Y15T19"] * 4,
            "WEALTH_QUINTILE": ["_T"] * 4,
            "RESIDENCE": ["_T"] * 4,
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="Y15T19",
    )
    assert "error" not in result, result
    s = result.get("summary", {})
    # 3 numeric values (0.35, 0.27, 0.24) — '<0.01' dropped.
    assert "value_range" in s
    assert s["value_range"]["min"] == 0.24
    assert s["value_range"]["max"] == 0.35


@patch("unicefstats_mcp.server._get_ud")
def test_raw_filtered_envelope_has_disaggregations_in_data(mock_ud):
    """v1.2.0 Commit 7 — summarize_disaggregations now sees lowercase
    `sex`/`age`/`wealth_quintile`/`residence` after normalize_columns.
    """
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["THA"] * 4,
            "INDICATOR": ["HVA_EPI_INF_RT"] * 4,
            "TIME_PERIOD": [2020, 2020, 2020, 2020],
            "OBS_VALUE": [0.10, 0.12, 0.11, 0.09],
            "SEX": ["F", "M", "F", "M"],
            "AGE": ["Y15T19"] * 4,
            "WEALTH_QUINTILE": ["_T"] * 4,
            "RESIDENCE": ["_T"] * 4,
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="Y15T19",
    )
    assert "error" not in result, result
    disagg = result.get("disaggregations_in_data", {})
    assert "sex" in disagg
    assert set(disagg["sex"]) == {"F", "M"}


@patch("unicefstats_mcp.server._get_ud")
def test_raw_filtered_post_filters_sex_default_T_to_totals_only(mock_ud):
    """v1.2.0 Commit 8 — Bug F. When raw_filtered mode engages because
    of age or filters dict, unicefdata's raw=True bypasses the sex=
    kwarg, so the response silently includes EVERY SEX value (F, M, _T)
    rather than the requested slice (default '_T'). The MCP must fold
    sex into the post-filter to preserve v1.1.x sex='_T' totals
    semantics on the raw_filtered path.
    """
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["THA"] * 6,
            "INDICATOR": ["HVA_EPI_INF_RT"] * 6,
            "TIME_PERIOD": [2020] * 6,
            "OBS_VALUE": [0.05, 0.04, 0.045, 0.06, 0.05, 0.055],
            "SEX": ["_T", "F", "M", "_T", "F", "M"],
            "AGE": ["Y15T19"] * 6,
            "WEALTH_QUINTILE": ["_T"] * 6,
            "RESIDENCE": ["_T"] * 6,
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    # Default sex='_T' + age='Y15T19' → only sex='_T' rows.
    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="Y15T19",
    )
    assert "error" not in result, result
    assert result["mode"] == "raw_filtered"
    # 2 raw rows have SEX='_T'; the M and F rows must have been filtered.
    assert result["rows_returned"] == 2
    assert "SEX" in result["applied_filters"]
    assert result["applied_filters"]["SEX"] == "_T"


@patch("unicefstats_mcp.server._get_ud")
def test_filters_dict_SEX_wins_over_typed_sex_default(mock_ud):
    """v1.2.0 Commit 8 — when `filters={'SEX': 'F'}` is passed alongside
    the typed `sex` default ('_T'), the filters-dict value wins. The
    typed `sex` is only folded in when SEX isn't already in the filters
    dict. Otherwise the typed default would silently override an
    explicit user filter — the worst kind of v1.1.x-shaped silent
    drop.
    """
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["THA"] * 6,
            "INDICATOR": ["HVA_EPI_INF_RT"] * 6,
            "TIME_PERIOD": [2020] * 6,
            "OBS_VALUE": [0.05, 0.04, 0.045, 0.06, 0.05, 0.055],
            "SEX": ["_T", "F", "M", "_T", "F", "M"],
            "AGE": ["Y15T19"] * 6,
            "WEALTH_QUINTILE": ["_T"] * 6,
            "RESIDENCE": ["_T"] * 6,
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    # User passes SEX=F via filters; default typed sex='_T' must NOT
    # overwrite. age='Y15T19' is needed to engage raw_filtered mode.
    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="Y15T19",
        filters={"SEX": "F"},
    )
    assert "error" not in result, result
    assert result["applied_filters"]["SEX"] == "F"
    # 2 raw rows have SEX='F'; the _T and M rows must be filtered out.
    assert result["rows_returned"] == 2


@patch("unicefstats_mcp.server._get_ud")
def test_raw_filtered_explicit_sex_F_yields_only_F_rows(mock_ud):
    """Same Bug F coverage but for an explicit sex=F + age combination.
    The MCP must filter to SEX='F' only.
    """
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["THA"] * 6,
            "INDICATOR": ["HVA_EPI_INF_RT"] * 6,
            "TIME_PERIOD": [2020] * 6,
            "OBS_VALUE": [0.05, 0.04, 0.045, 0.06, 0.05, 0.055],
            "SEX": ["_T", "F", "M", "_T", "F", "M"],
            "AGE": ["Y15T19"] * 6,
            "WEALTH_QUINTILE": ["_T"] * 6,
            "RESIDENCE": ["_T"] * 6,
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="Y15T19",
        sex="F",
    )
    assert "error" not in result, result
    assert result["mode"] == "raw_filtered"
    assert result["rows_returned"] == 2
    assert result["applied_filters"]["SEX"] == "F"


@patch("unicefstats_mcp.server._get_ud")
def test_raw_filtered_envelope_populates_countries_returned_with_names(mock_ud):
    """v1.2.0 Commit 7 — countries_returned_with_names is filled via
    lookup_country_name fallback when the raw payload has no country
    name column (defeats the v0.6.1 country-substitution mitigation
    if empty).
    """
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["THA"],
            "INDICATOR": ["HVA_EPI_INF_RT"],
            "TIME_PERIOD": [2020],
            "OBS_VALUE": [0.10],
            "SEX": ["_T"],
            "AGE": ["Y15T19"],
            "WEALTH_QUINTILE": ["_T"],
            "RESIDENCE": ["_T"],
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="Y15T19",
    )
    assert "error" not in result, result
    names = result.get("countries_returned_with_names", {})
    assert "THA" in names
    assert names["THA"]  # canonical name resolved


# ---------------------------------------------------------------------------
# Issue #77 — units envelope field (UNIT_MEASURE + UNIT_MULTIPLIER) so
# the LLM doesn't drift on small-number-with-no-context cases like
# DM_POP_U5 NIU 2001 = 0.188 (= 188 Persons via × 10^3).
# ---------------------------------------------------------------------------


@patch("unicefstats_mcp.server._get_ud")
def test_raw_filtered_envelope_surfaces_units_from_dataframe(mock_ud):
    """raw_filtered mode already has UNIT_MEASURE / UNIT_MULTIPLIER
    columns from the raw=True fetch (normalize_columns renames them
    to lowercase). units must be sourced directly from df without a
    second SDMX round-trip.
    """
    raw_df = pd.DataFrame(
        {
            "REF_AREA": ["THA"] * 2,
            "INDICATOR": ["HVA_EPI_INF_RT"] * 2,
            "TIME_PERIOD": [2020, 2021],
            "OBS_VALUE": ["0.10", "0.12"],
            "SEX": ["_T"] * 2,
            "AGE": ["Y15T19"] * 2,
            "WEALTH_QUINTILE": ["_T"] * 2,
            "RESIDENCE": ["_T"] * 2,
            "UNIT_MEASURE": ["RATE_1000"] * 2,
            "UNIT_MULTIPLIER": [0, 0],
        }
    )
    ud = MagicMock()
    ud.unicefData.return_value = raw_df
    mock_ud.return_value = ud

    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="Y15T19",
    )
    assert "error" not in result, result
    units = result.get("units")
    assert units is not None
    assert units["measure"] == "RATE_1000"
    assert units["measure_name"] == "Rate per 1,000 of Population"
    assert units["multiplier"] == 0
    assert units["multiplier_name"] == "absolute (no multiplier)"
    # No extra SDMX round-trip should fire for raw_filtered units.
    assert ud.unicefData.call_count == 1


def test_units_from_dataframe_returns_none_when_columns_missing():
    """Direct helper test — DataFrame without unit columns returns None."""
    from unicefstats_mcp import dimensions as dims

    df = pd.DataFrame(
        {
            "iso3": ["BDI"],
            "period": [2020],
            "value": [82.0],
        }
    )
    assert dims.units_from_dataframe(df) is None


def test_unit_multiplier_name_covers_dm_pop_u5_case():
    """The DM_POP_U5 case: UNIT_MEASURE='PS', UNIT_MULTIPLIER=3.
    Must surface as 'Persons' / 'thousands' with the explicit
    `interpretation` string the LLM keys off.
    """
    from unicefstats_mcp import dimensions as dims

    df = pd.DataFrame(
        {
            "iso3": ["NIU"],
            "period": [2001],
            "value": [0.188],
            "UNIT_MEASURE": ["PS"],
            "UNIT_MULTIPLIER": [3],
        }
    )
    units = dims.units_from_dataframe(df)
    assert units is not None
    assert units["measure"] == "PS"
    assert units["measure_name"] == "Persons"
    assert units["multiplier"] == 3
    assert units["multiplier_name"] == "thousands"
    assert "10^3 Persons" in units["interpretation"]


# ---------------------------------------------------------------------------
# filters validators — shape checks (semantic checks happen via dimensions)
# ---------------------------------------------------------------------------


def test_filters_wrong_type_is_rejected_at_validator():
    result = get_data(
        indicator="NT_BF_EXBF",
        countries=["BDI"],
        filters="WEALTH_QUINTILE=Q1",  # type: ignore[arg-type]
    )
    assert "error" in result
    assert "filters must be a dict" in result["error"]


def test_filters_oversized_value_is_rejected():
    result = get_data(
        indicator="NT_BF_EXBF",
        countries=["BDI"],
        filters={"WEALTH_QUINTILE": "Q" * 100},
    )
    assert "error" in result
    assert "too long" in result["error"]


def test_age_wrong_type_is_rejected():
    result = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age=["Y15T19", "Y15T24"],  # type: ignore[arg-type]
    )
    assert "error" in result
    assert "age must be a string" in result["error"]
