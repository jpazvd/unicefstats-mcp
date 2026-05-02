"""Tests for get_data tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from unicefstats_mcp.server import get_data


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
        assert set(result["data"][0].keys()).issubset(
            {"country_code", "country_name", "period", "indicator_code", "value"}
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

    def test_invalid_wealth_quintile(self):
        result = get_data(
            indicator="CME_MRY0T4", countries=["BRA"], wealth_quintile="Q9"
        )
        assert "error" in result
        assert "Invalid wealth_quintile" in result["error"]

    def test_invalid_residence(self):
        result = get_data(
            indicator="CME_MRY0T4", countries=["BRA"], residence="X"
        )
        assert "error" in result
        assert "Invalid residence" in result["error"]

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
        """v0.6.0: requesting end_year > frontier triggers server-side refusal."""
        from unicefstats_mcp.server import _data_frontier_cache
        _data_frontier_cache.clear()  # ensure fresh lookup

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
