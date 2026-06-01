"""v1.2.0 Commit 11 — pin Copilot review findings (PR #82 thread).

Each test pins one of the 7 line-level findings Copilot surfaced on
PR #82, so a future refactor can't silently re-open the issue. Comment
IDs are included in the test docstrings for traceability.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from unicefstats_mcp import dimensions as d
from unicefstats_mcp.server import _DIM_TOKEN_MAP, _expand_synonyms, get_data

# ---------------------------------------------------------------------------
# #3328906494 — AGE collision between `age=` and `filters['AGE']`
# ---------------------------------------------------------------------------


def test_age_kwarg_and_filters_AGE_with_same_value_is_accepted() -> None:
    """Same value collision is harmless — both kwargs name the same slice.
    No silent-drop, no error.
    """
    # We can't actually call get_data without an SDMX fetch, but pre-flight
    # accepts before fetching; the collision check fires before fetch.
    # Use HVA_EPI_INF_RT + a real AGE value; we just need to see that no
    # collision error is raised. Patch the SDMX call so we don't hit network.
    with patch("unicefstats_mcp.server._get_ud") as mock_ud:
        ud = MagicMock()
        # Return non-empty raw payload so post-filter / formatters run.
        ud.unicefData.return_value = pd.DataFrame(
            {
                "REF_AREA": ["THA"],
                "INDICATOR": ["HVA_EPI_INF_RT"],
                "TIME_PERIOD": [2020],
                "OBS_VALUE": [0.1],
                "SEX": ["_T"],
                "AGE": ["Y15T19"],
                "WEALTH_QUINTILE": ["_T"],
                "RESIDENCE": ["_T"],
            }
        )
        mock_ud.return_value = ud
        r = get_data(
            indicator="HVA_EPI_INF_RT",
            countries=["THA"],
            age="Y15T19",
            filters={"AGE": "Y15T19"},
        )
    assert "error" not in r, r


def test_age_kwarg_and_filters_AGE_with_different_values_is_rejected() -> None:
    """Different values are a v1.1.x-shaped silent-drop hazard; reject."""
    r = get_data(
        indicator="HVA_EPI_INF_RT",
        countries=["THA"],
        age="Y15T19",
        filters={"AGE": "Y0T14"},
    )
    assert "error" in r
    assert "Conflicting AGE" in r["error"]
    assert r["conflicting_kwargs"]["age"] == "Y15T19"
    assert r["conflicting_kwargs"]["filters.AGE"] == "Y0T14"


# ---------------------------------------------------------------------------
# #3328906506 — `_MOD` substring would over-fire on `_MODEL` / `_MODE` etc.
# ---------------------------------------------------------------------------


def test_method_mod_token_does_not_over_fire_on_hypothetical_codes() -> None:
    """Pure substring `_MOD` would match hypothetical codes like
    `X_MODEL_Y`, `X_MODE_Y`, `X_MODERATE_Y`. The pattern must anchor
    to a segment boundary.
    """
    from unicefstats_mcp.server import _indicator_matches_dim

    hints = {"METHOD_MOD"}
    # Real _MOD codes — must match.
    assert _indicator_matches_dim("NT_ANT_HAZ_NE2_MOD", "", hints)
    assert _indicator_matches_dim("NT_ANT_HAZ_NE2_MOD_NUMTH", "", hints)
    # Hypothetical codes containing _MOD as a non-boundary substring
    # — must NOT match (the Copilot finding).
    assert not _indicator_matches_dim("X_MODEL_Y", "", hints)
    assert not _indicator_matches_dim("X_MODE_Y", "", hints)
    assert not _indicator_matches_dim("X_MODERATE_Y", "", hints)


def test_method_mod_token_map_uses_segment_anchored_pattern() -> None:
    """The pattern in _DIM_TOKEN_MAP itself must be segment-anchored
    (`_MOD_`, NOT `_MOD`). Otherwise even with the boundary check in
    _indicator_matches_dim, a future refactor could silently widen.
    """
    assert _DIM_TOKEN_MAP.get("METHOD_MOD") == ("_MOD_",)


# ---------------------------------------------------------------------------
# #3328906511 — synonym ordering inconsistency
# ---------------------------------------------------------------------------


def test_under_five_mortality_synonyms_all_expand_to_same_phrase() -> None:
    """All five mortality phrasings ('under-5 mortality', 'under 5
    mortality', 'under-five mortality', 'u5mr', etc.) must expand to
    the SAME canonical phrase regardless of insertion order in
    _SYNONYMS. Pre-fix, the `break` after first match combined with
    "under-5 mortality" → "under-five mortality" (not "rate")
    silently produced different expansions per phrasing.
    """
    phrases = [
        "u5mr",
        "under-5 mortality",
        "under 5 mortality",
        "under-five mortality",
    ]
    expansions = [_expand_synonyms(p) for p in phrases]
    # All should include the canonical "under-five mortality rate"
    # phrase since it's the consistent expansion target.
    for e in expansions:
        assert "under-five mortality rate" in e, (
            f"expansion missing canonical 'rate': {e!r}"
        )


# ---------------------------------------------------------------------------
# #3328906514 — removed-kwarg trip-wire must fire BEFORE validate_filters
# ---------------------------------------------------------------------------


def test_v1_1_x_caller_with_malformed_filters_sees_migration_error_first() -> None:
    """A v1.1.x caller passing both the removed `wealth_quintile=`
    kwarg AND a malformed `filters` (wrong type) must see the v1.2.0
    migration guidance, NOT the generic "filters must be a dict" error.
    Migration guidance is the more-actionable signal.
    """
    r = get_data(
        indicator="NT_BF_EXBF",
        countries=["BDI"],
        wealth_quintile="Q1",
        filters="WEALTH_QUINTILE=Q1",  # type: ignore[arg-type]  # malformed
    )
    assert "error" in r
    assert "Removed in v1.2.0" in r["error"]
    assert r.get("removed_kwargs") == ["wealth_quintile"]


def test_v1_1_x_caller_with_malformed_age_sees_migration_error_first() -> None:
    """Same as above but with malformed age=; migration guidance wins."""
    r = get_data(
        indicator="NT_BF_EXBF",
        countries=["BDI"],
        residence="U",
        age=["Y0T4"],  # type: ignore[arg-type]  # malformed (must be str)
    )
    assert "error" in r
    assert "Removed in v1.2.0" in r["error"]
    assert r.get("removed_kwargs") == ["residence"]


# ---------------------------------------------------------------------------
# #3328906531 — dimension_supported must be case-insensitive on value
# ---------------------------------------------------------------------------


def test_dimension_supported_is_case_insensitive_on_value() -> None:
    """`filter_by_dimensions` uppercases both sides; `dimension_supported`
    must do the same. Otherwise the two layers disagree and `filters=
    {'WEALTH_QUINTILE': 'q1'}` is refused at pre-flight even though
    the post-filter would have accepted it.
    """
    # HVA_EPI_INF_RT has WEALTH_QUINTILE in its HIV_AIDS dataflow with
    # codelist values like Q1, Q2, ..., _T.
    assert d.dimension_supported("HVA_EPI_INF_RT", "WEALTH_QUINTILE", "Q1") is True
    assert d.dimension_supported("HVA_EPI_INF_RT", "WEALTH_QUINTILE", "q1") is True
    assert (
        d.dimension_supported("HVA_EPI_INF_RT", "WEALTH_QUINTILE", "q5") is True
    )
    # Genuinely invalid value still rejected.
    assert (
        d.dimension_supported("HVA_EPI_INF_RT", "WEALTH_QUINTILE", "BOGUS")
        is False
    )


def test_get_data_accepts_lowercase_filter_value_after_case_fix() -> None:
    """End-to-end: lowercase filter value no longer trips pre-flight."""
    with patch("unicefstats_mcp.server._get_ud") as mock_ud:
        ud = MagicMock()
        ud.unicefData.return_value = pd.DataFrame(
            {
                "REF_AREA": ["BDI"],
                "INDICATOR": ["NT_BF_EXBF"],
                "TIME_PERIOD": [2020],
                "OBS_VALUE": [82.0],
                "SEX": ["_T"],
                "AGE": ["Y0T5"],
                "WEALTH_QUINTILE": ["Q1"],
                "RESIDENCE": ["_T"],
            }
        )
        mock_ud.return_value = ud
        r = get_data(
            indicator="NT_BF_EXBF",
            countries=["BDI"],
            filters={"WEALTH_QUINTILE": "q1"},  # lowercase
        )
    assert "error" not in r, r
    assert r["mode"] == "raw_filtered"


# ---------------------------------------------------------------------------
# #3328906525 — indicators_supporting / dimensions_for_indicator consistency
# ---------------------------------------------------------------------------


def test_indicators_supporting_includes_tier1_indicators_via_dataflow() -> None:
    """v1.2.0 Commit 11 — indicators_supporting_index now uses
    dimensions_for_indicator (which considers the primary dataflow's
    codelist) rather than the indicator's raw disaggregations field.
    A tier-1 indicator whose own metadata doesn't enumerate AGE in
    disaggregations but whose primary dataflow has an AGE codelist
    must still appear in indicators_supporting('AGE').
    """
    hva_supports_age = d.indicators_supporting("AGE")
    assert "HVA_EPI_INF_RT" in hva_supports_age
    # Tier-2 codes are excluded (no dataflow → no dim menu).
    assert "CME" not in hva_supports_age


def test_indicators_supporting_value_check_is_case_insensitive() -> None:
    """Symmetric to dimension_supported; lowercase values match."""
    upper = d.indicators_supporting("AGE", "Y15T19")
    lower = d.indicators_supporting("AGE", "y15t19")
    assert upper == lower
    assert "HVA_EPI_INF_RT" in upper
