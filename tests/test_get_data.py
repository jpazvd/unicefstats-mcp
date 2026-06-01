"""Tests for get_data tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from unicefstats_mcp.server import get_data


@pytest.fixture(autouse=True)
def _isolate_frontier_cache(monkeypatch):
    """Give every test a fresh empty `_data_frontier_cache`.

    Replaces the v0.7.1 pattern of mutating the module global directly
    (which leaked between tests). monkeypatch restores the original cache
    object after each test, so any real-process cache survives outside
    the test session.
    """
    monkeypatch.setattr("unicefstats_mcp.server._data_frontier_cache", {})


@pytest.fixture
def mock_df():
    """DataFrame with 10 rows mimicking unicefData output."""
    return pd.DataFrame(
        {
            "country_code": ["BRA"] * 5 + ["ARG"] * 5,
            "country_name": ["Brazil"] * 5 + ["Argentina"] * 5,
            "indicator_code": ["CME_MRY0T4"] * 10,
            "period": list(range(2015, 2020)) * 2,
            "value": [15.0, 14.8, 14.5, 14.2, 13.8, 10.1, 10.0, 9.9, 9.8, 9.5],
            "sex": ["_T"] * 10,
            "age": ["Y0T4"] * 10,
            "wealth_quintile": ["_T"] * 10,
            "residence": ["_T"] * 10,
            "obs_status": ["A"] * 10,
            "data_source": ["IGME"] * 10,
            "lower_bound": [13.5] * 10,
            "upper_bound": [16.5] * 10,
        }
    )


@pytest.fixture
def disagg_df():
    """DataFrame with sex disaggregation."""
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
        }
    )


class TestGetData:
    """Tests for get_data tool."""

    @patch("unicefstats_mcp.server._get_ud")
    def test_compact_format(self, mock_ud, mock_df):
        ud = MagicMock()
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        result = get_data(
            indicator="CME_MRY0T4",
            countries=["BRA", "ARG"],
            format="compact",
        )
        assert "error" not in result
        assert result["format"] == "compact"
        assert result["rows_returned"] == 10
        assert result["rows_truncated"] is False
        assert "summary" in result
        # v1.2.0 Commit 6: to_compact now renames alias columns
        # (country_code/country_name/indicator_code) to the canonical
        # `iso3`/`country`/`indicator` so the LLM-facing schema is
        # consistent whether the source df came from the simplified path
        # or the raw=True path (REF_AREA / OBS_VALUE / TIME_PERIOD).
        assert set(result["data"][0].keys()).issubset(
            {"iso3", "country", "period", "indicator", "value"}
        )

    @patch("unicefstats_mcp.server._get_ud")
    def test_full_format(self, mock_ud, mock_df):
        ud = MagicMock()
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        result = get_data(
            indicator="CME_MRY0T4",
            countries=["BRA"],
            format="full",
        )
        assert "error" not in result
        assert result["format"] == "full"
        assert "sex" in result["data"][0]
        assert "lower_bound" in result["data"][0]

    @patch("unicefstats_mcp.server._get_ud")
    def test_row_truncation(self, mock_ud, mock_df):
        ud = MagicMock()
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        result = get_data(
            indicator="CME_MRY0T4",
            countries=["BRA", "ARG"],
            limit=3,
        )
        assert result["rows_returned"] == 3
        assert result["total_rows_available"] == 10
        assert result["rows_truncated"] is True
        assert result["data_completeness"] == "truncated"
        assert "warnings" in result
        assert any("3 of 10" in w for w in result["warnings"])

    @patch("unicefstats_mcp.server._get_ud")
    def test_disaggregation_summary(self, mock_ud, disagg_df):
        ud = MagicMock()
        ud.unicefData.return_value = disagg_df
        mock_ud.return_value = ud

        result = get_data(
            indicator="CME_MRY0T4",
            countries=["BRA"],
            format="full",
        )
        assert "disaggregations_in_data" in result
        assert "sex" in result["disaggregations_in_data"]
        assert set(result["disaggregations_in_data"]["sex"]) == {"M", "F", "_T"}

    @patch("unicefstats_mcp.server._get_ud")
    def test_data_summary(self, mock_ud, mock_df):
        ud = MagicMock()
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        result = get_data(
            indicator="CME_MRY0T4",
            countries=["BRA", "ARG"],
        )
        assert "summary" in result
        assert "value_range" in result["summary"]
        assert result["summary"]["value_range"]["min"] == 9.5
        assert result["summary"]["value_range"]["max"] == 15.0
        assert result["summary"]["countries_in_result"] == 2

    @patch("unicefstats_mcp.server._get_ud")
    def test_countries_returned_with_names(self, mock_ud, mock_df):
        """v0.6.1: response includes countries_returned_with_names so the model
        can confirm the country name returned matches what the user asked."""
        ud = MagicMock()
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA", "ARG"])
        assert "countries_returned_with_names" in result
        names = result["countries_returned_with_names"]
        assert names == {"BRA": "Brazil", "ARG": "Argentina"}
        # v0.6.2 directive points at country_resolutions + retry-with-name path
        assert "verify_country_directive" in result
        directive = result["verify_country_directive"]
        assert "country_resolutions" in directive
        assert "name" in directive.lower()

    @patch("unicefstats_mcp.server._get_ud")
    def test_country_name_input_resolved(self, mock_ud, mock_df):
        """v0.6.2: passing a country NAME instead of ISO3 should resolve server-side."""
        ud = MagicMock()
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["Brazil", "Argentina"])
        assert "error" not in result
        # Server canonicalised to ISO3 and surfaced the resolution
        assert result["countries_resolved_to"] == ["BRA", "ARG"]
        assert result["country_resolutions"] == {"Brazil": "BRA", "Argentina": "ARG"}
        # And the original input is still echoed back
        assert result["countries_requested"] == ["Brazil", "Argentina"]

    @patch("unicefstats_mcp.server._get_ud")
    def test_country_mixed_iso3_and_name_input(self, mock_ud, mock_df):
        """v0.6.2: mixed ISO3 + name input — only names appear in resolutions."""
        ud = MagicMock()
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA", "Argentina"])
        assert "error" not in result
        assert result["countries_resolved_to"] == ["BRA", "ARG"]
        # Only the name input shows up in the resolutions map; ISO3 codes pass through silently
        assert result["country_resolutions"] == {"Argentina": "ARG"}

    def test_unresolvable_country_returns_error(self):
        """v0.6.2: unresolvable countries surface a helpful error, not a silent fail."""
        result = get_data(indicator="CME_MRY0T4", countries=["NotARealCountry"])
        assert "error" in result
        assert "Could not resolve" in result["error"]
        # And the help mentions list_countries() for discovery
        assert "list_countries" in result.get("tip", "")

    def test_too_many_countries(self):
        countries = [f"C{i:02d}" for i in range(35)]
        result = get_data(indicator="CME_MRY0T4", countries=countries)
        assert "error" in result
        assert "Too many" in result["error"]

    def test_empty_countries(self):
        result = get_data(indicator="CME_MRY0T4", countries=[])
        assert "error" in result

    def test_invalid_country_code(self):
        # v0.6.2: resolver rejects un-resolvable inputs (not an ISO3 code AND
        # not a known country name → error mentions "Could not resolve").
        result = get_data(indicator="CME_MRY0T4", countries=["TOOLONG"])
        assert "error" in result
        assert "Could not resolve" in result["error"]

    def test_invalid_limit(self):
        result = get_data(indicator="CME_MRY0T4", countries=["BRA"], limit=999)
        assert "error" in result

    def test_invalid_sex(self):
        result = get_data(indicator="CME_MRY0T4", countries=["BRA"], sex="X")
        assert "error" in result
        assert "Invalid sex" in result["error"]

    def test_v1_1_x_wealth_quintile_kwarg_routes_to_migration_error(self):
        """v1.1.x callers passing wealth_quintile=Q1 see the structured
        v1.2.0 migration error, NOT a silent acceptance, NOT a silent drop.

        The kwarg is still present in the signature as a deprecation
        trip-wire (FastMCP rejects **kwargs) so it can intercept the
        legacy call shape. The migration message names the new shape
        and surfaces the structured `removed_kwargs` field at top level.
        """
        result = get_data(
            indicator="CME_MRY0T4", countries=["BRA"], wealth_quintile="Q1"
        )
        assert "error" in result
        assert "Removed in v1.2.0" in result["error"]
        assert "filters" in result["error"]
        assert result.get("removed_kwargs") == ["wealth_quintile"]
        assert result.get("v1_2_0") is True

    def test_v1_1_x_residence_kwarg_routes_to_migration_error(self):
        """Same pattern as above for the v1.1.x residence kwarg."""
        result = get_data(
            indicator="CME_MRY0T4", countries=["BRA"], residence="U"
        )
        assert "error" in result
        assert "Removed in v1.2.0" in result["error"]
        assert result.get("removed_kwargs") == ["residence"]

    @patch("unicefstats_mcp.server._get_ud")
    def test_year_range(self, mock_ud, mock_df):
        ud = MagicMock()
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        # mock_df has periods 2015-2019. v0.6.0 pre-flight check uses
        # _get_data_frontier (which calls get_temporal_coverage internally)
        # to learn the indicator's max year. With this mock, frontier=2019.
        # Use a year range that stays within frontier so the pre-flight passes.
        result = get_data(
            indicator="CME_MRY0T4",
            countries=["BRA"],
            start_year=2017,
            end_year=2019,
        )
        assert "error" not in result
        # The pre-flight check makes a separate get_temporal_coverage call before
        # the main fetch; both go through the same mock, so the last call's
        # kwargs are the data fetch.
        call_kwargs = ud.unicefData.call_args.kwargs
        assert call_kwargs["year"] == "2017:2019"

    @patch("unicefstats_mcp.server._get_ud")
    def test_year_range_out_of_frontier(self, mock_ud, mock_df):
        """v0.6.0: requesting end_year > frontier triggers server-side refusal.

        The autouse `_isolate_frontier_cache` fixture handles cache reset.
        """
        ud = MagicMock()
        ud.unicefData.return_value = mock_df  # frontier = 2019
        mock_ud.return_value = ud

        result = get_data(
            indicator="CME_MRY0T4",
            countries=["BRA"],
            start_year=2018,
            end_year=2024,  # exceeds mock's 2019 frontier
        )
        assert result["status"] == "no_data"
        assert result["out_of_frontier"] is True
        assert result["data_frontier"]["max_year_observed"] == 2019
        assert result["data_frontier"]["indicator"] == "CME_MRY0T4"
        # Server should have made the coverage call but NOT the data fetch
        # (or made it once for coverage). The point is the response is a
        # structural refusal, not an SDMX-empty result.
        assert "exceeds the data frontier" in result["error"].lower() or \
               "extends past the data frontier" in result["error"].lower()

    @patch("unicefstats_mcp.server._get_ud")
    def test_api_error_handled(self, mock_ud):
        ud = MagicMock()
        ud.unicefData.side_effect = RuntimeError("SDMX server error")
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA"])
        assert "error" in result
        assert "tip" in result

    @patch("unicefstats_mcp.server._get_ud")
    def test_empty_dataframe(self, mock_ud):
        ud = MagicMock()
        ud.unicefData.return_value = pd.DataFrame()
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA"])
        assert "error" in result
        assert "No data" in result["error"]


class TestIndicatorResolverIntegration:
    """v0.7.0 indicator-resolver wiring inside get_data.

    Verifies that the resolver produces canonicalized codes downstream and
    surfaces the right error shape on ambiguous queries. Resolver itself is
    unit-tested in tests/test_indicator_resolver.py — these tests focus on
    the get_data integration boundary.
    """

    @patch("unicefstats_mcp.server._get_ud")
    def test_code_passthrough_canonicalizes_input(self, mock_ud, mock_df):
        """Lowercase / whitespace-padded code is normalized before SDMX call."""
        ud = MagicMock()
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        result = get_data(indicator="  cme_mry0t4  ", countries=["BRA"])

        assert "error" not in result
        # Echoed indicator field should be canonical, not the user-quirky form
        assert result["indicator"] == "CME_MRY0T4"
        assert result["indicator_resolution"]["status"] == "code_passthrough"
        assert result["indicator_resolution"]["resolved_code"] == "CME_MRY0T4"
        # SDMX call also got the canonical code
        call_kwargs = ud.unicefData.call_args.kwargs
        assert call_kwargs["indicator"] == "CME_MRY0T4"

    @patch("unicefstats_mcp.server._get_ud")
    def test_synonym_match_resolves_to_canonical_code(self, mock_ud, mock_df):
        """Human-readable name is translated to canonical code server-side."""
        ud = MagicMock()
        # mock_df has indicator_code=CME_MRY0T4; the synonym "u5mr" → CME_MRY0T4
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        result = get_data(indicator="U5MR", countries=["BRA"])

        assert "error" not in result
        assert result["indicator"] == "CME_MRY0T4"
        assert result["indicator_resolution"]["status"] == "synonym_match"
        assert result["indicator_resolution"]["original_input"] == "U5MR"
        assert result["indicator_resolution"]["resolved_code"] == "CME_MRY0T4"
        # Downstream SDMX call uses the canonical code, NOT the synonym
        call_kwargs = ud.unicefData.call_args.kwargs
        assert call_kwargs["indicator"] == "CME_MRY0T4"

    @patch("unicefstats_mcp.server._get_ud")
    def test_ambiguous_indicator_refused_with_disambiguation_list(self, mock_ud):
        """`'child mortality'` must refuse server-side and never call SDMX."""
        ud = MagicMock()
        mock_ud.return_value = ud

        result = get_data(indicator="child mortality", countries=["BRA"])

        # Refusal envelope, not a successful response
        assert "error" in result
        assert "ambiguous" in result["error"].lower()
        # SDMX call must NOT have been made — refusal is structural
        ud.unicefData.assert_not_called()
        # Disambiguation list must be present and contain plausible candidates
        assert "indicator_disambiguation" in result
        candidate_codes = [c["code"] for c in result["indicator_disambiguation"]]
        assert "CME_MRM0" in candidate_codes
        assert "CME_MRY0T4" in candidate_codes
        # Each candidate must carry a human-readable name for the model
        for cand in result["indicator_disambiguation"]:
            assert isinstance(cand["name"], str) and cand["name"]


class TestFrontierCacheSeeding:
    """v0.7.3: a successful `get_data` response seeds the per-session frontier
    cache from `df["period"].max()` so subsequent calls with year args don't
    re-issue a totals-only `get_temporal_coverage` round-trip just to learn
    the same frontier we already observed."""

    @patch("unicefstats_mcp.server._get_ud")
    def test_response_seeds_cache(self, mock_ud, mock_df):
        from unicefstats_mcp.server import _data_frontier_cache

        ud = MagicMock()
        ud.unicefData.return_value = mock_df  # max period = 2019
        mock_ud.return_value = ud

        # First call without year args → no pre-flight, no cache lookup.
        result = get_data(indicator="CME_MRY0T4", countries=["BRA"])
        assert "error" not in result
        # The response itself populates the cache from df["period"].max().
        assert _data_frontier_cache.get("CME_MRY0T4") == 2019

    @patch("unicefstats_mcp.server._get_ud")
    def test_seeded_cache_avoids_extra_fetch(self, mock_ud, mock_df):
        """After one successful get_data, a subsequent get_data with year args
        should not need to call get_temporal_coverage — the cache is already
        warm from the response."""
        ud = MagicMock()
        ud.unicefData.return_value = mock_df
        mock_ud.return_value = ud

        # Warm the cache.
        get_data(indicator="CME_MRY0T4", countries=["BRA"])
        first_call_count = ud.unicefData.call_count

        # Second call WITH year args. Pre-flight frontier check should now hit
        # the cache rather than issuing a coverage fetch.
        get_data(
            indicator="CME_MRY0T4",
            countries=["BRA"],
            start_year=2017,
            end_year=2019,
        )
        second_call_count = ud.unicefData.call_count

        # Without cache seeding, this would be +2 (coverage + data). With
        # seeding, it's exactly +1 (data fetch only).
        assert second_call_count - first_call_count == 1

    def test_seed_does_not_lower_existing_frontier(self):
        """Year-bounded queries must not poison the cache with a lower frontier.

        Regression: in the initial v0.7.3 seed implementation, any successful
        get_data response unconditionally overwrote the cache with df["period"].max().
        Because df is filtered by start_year/end_year/country, a query like
        `get_data(CME_MRY0T4, [LBR], 2023, 2023)` would set the cache to 2023
        even when the indicator's true frontier is 2024 — and a subsequent
        `get_data(CME_MRY0T4, [NLD], 2024)` would then be wrongly refused at
        the pre-flight frontier check. The seed must take max(existing, new),
        never lower.
        """
        from unicefstats_mcp.server import (
            _data_frontier_cache,
            _seed_data_frontier_cache,
        )

        _data_frontier_cache["CME_MRY0T4"] = 2024  # true indicator frontier
        bounded_df = pd.DataFrame({"period": [2023]})  # response from year=2023 query

        _seed_data_frontier_cache("CME_MRY0T4", bounded_df)

        assert _data_frontier_cache["CME_MRY0T4"] == 2024  # unchanged

    def test_seed_raises_existing_frontier_when_response_is_higher(self):
        """When the response shows a higher max year than the cache, seed updates."""
        from unicefstats_mcp.server import (
            _data_frontier_cache,
            _seed_data_frontier_cache,
        )

        _data_frontier_cache["CME_MRY0T4"] = 2022
        df = pd.DataFrame({"period": [2024]})

        _seed_data_frontier_cache("CME_MRY0T4", df)

        assert _data_frontier_cache["CME_MRY0T4"] == 2024


class TestUnicefdataCascadeIsNoData:
    """v0.7.3 post-fix: the upstream `unicefdata` package walks a hardcoded
    fallback dataflow chain when the primary dataflow returns 404 or empty.
    Under burst load, intermittent upstream 404s on year-out-of-frontier or
    high-income-country queries trigger the chain walk (extra HTTP requests
    + log noise), ending in `SDMXNotFoundError: Indicator 'X' not found in
    any dataflow.` (lowercase 'not found').

    The MCP's exception handler must classify this as a `no_data` response
    so the model receives an honest "no data" verdict and can refuse cleanly,
    rather than a generic error that destabilises its tool-loop heuristics.

    Tracking issue filed at unicefdata-dev for the upstream behaviour fix.
    """

    @patch("unicefstats_mcp.server._get_ud")
    def test_cascade_exception_returns_no_data(self, mock_ud):
        ud = MagicMock()

        # Simulate unicefdata's cascade-end exception. The package raises
        # SDMXNotFoundError but here a plain Exception with the same message
        # is sufficient — the heuristic match is on the message text.
        ud.unicefData.side_effect = Exception(
            "Indicator 'NT_ANT_HAZ_NE2' not found in any dataflow.\n"
            "  Tried dataflows: NUTRITION, GLOBAL_DATAFLOW, NUTRITION_STUNTING, "
            "NUTRITION_WASTING, CHILD_NUTRITION, HEALTH"
        )
        mock_ud.return_value = ud

        result = get_data(indicator="NT_ANT_HAZ_NE2", countries=["BRA"])

        assert "error" in result
        assert result.get("status") == "no_data", (
            "Cascade-end exception must be classified as no_data so the model "
            "treats it like any other 'no data exists for this combination' "
            "verdict; otherwise it falls through to generic-error tool-loop "
            "behaviour and may hallucinate a value."
        )

    @patch("unicefstats_mcp.server._get_ud")
    def test_lowercase_not_found_classified_as_no_data(self, mock_ud):
        """The pre-fix heuristic only matched 'Not Found' (Title Case);
        unicefdata's message uses lowercase 'not found'. The fix lower-cased
        the comparison."""
        ud = MagicMock()
        ud.unicefData.side_effect = Exception("indicator was not found upstream")
        mock_ud.return_value = ud

        result = get_data(indicator="ED_CR_L1", countries=["CIV"])

        assert "error" in result
        assert result.get("status") == "no_data"


class TestNonNumericPeriods:
    """v0.7.3: gap detection and frontier extraction must tolerate SDMX
    quarterly/monthly periods (e.g. `2019-Q1`) instead of raising ValueError
    on the whole DataFrame."""

    @patch("unicefstats_mcp.server._get_ud")
    def test_quarterly_periods_do_not_crash(self, mock_ud):
        df = pd.DataFrame({
            "country_code": ["BRA"] * 4,
            "country_name": ["Brazil"] * 4,
            "indicator_code": ["CME_MRY0T4"] * 4,
            "period": ["2019-Q1", "2019-Q2", "2019-Q3", "2019-Q4"],
            "value": [14.5, 14.4, 14.3, 14.2],
            "sex": ["_T"] * 4,
            "age": ["Y0T4"] * 4,
            "wealth_quintile": ["_T"] * 4,
            "residence": ["_T"] * 4,
        })
        ud = MagicMock()
        ud.unicefData.return_value = df
        mock_ud.return_value = ud

        # Without the v0.7.3 fix, this raised ValueError inside the gap-detection
        # block and broke the whole successful response.
        result = get_data(
            indicator="CME_MRY0T4",
            countries=["BRA"],
            start_year=2019,
            end_year=2019,
        )

        assert "error" not in result
        # Frontier-from-response should extract 2019 from the year prefix.
        assert result.get("data_frontier", {}).get("max_year_observed") == 2019
