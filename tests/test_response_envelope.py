"""Tests for the response envelope: status, source, data_completeness, warnings.

Every tool response should include structured metadata that LLMs use for
epistemic safety decisions. These tests verify the envelope contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from tests.conftest import MOCK_INDICATORS
from unicefstats_mcp.server import (
    get_data,
    get_indicator_info,
    get_temporal_coverage,
    list_categories,
    search_indicators,
)


class TestOkEnvelope:
    """All ok responses must include status, source, data_completeness."""

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_search_envelope(self, _mock):
        result = search_indicators(query="mortality", limit=5)
        assert result["status"] == "ok"
        assert result["source"] == "UNICEF Data Warehouse via SDMX API"
        assert result["data_completeness"] == "complete"

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_list_categories_envelope(self, _mock):
        result = list_categories()
        assert result["status"] == "ok"
        assert "source" in result

    @patch("unicefstats_mcp.server._get_ud")
    def test_get_data_complete(self, mock_ud):
        """When all requested countries return data, data_completeness = complete."""
        ud = MagicMock()
        ud.unicefData.return_value = pd.DataFrame(
            {
                "country_code": ["BRA", "BRA", "IND", "IND"],
                "country_name": ["Brazil", "Brazil", "India", "India"],
                "indicator_code": ["CME_MRY0T4"] * 4,
                "period": [2020, 2021, 2020, 2021],
                "value": [14.2, 13.8, 28.0, 27.0],
                "sex": ["_T"] * 4,
            }
        )
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA", "IND"])
        assert result["status"] == "ok"
        assert result["data_completeness"] == "complete"
        assert "warnings" not in result

    @patch("unicefstats_mcp.server._get_ud")
    def test_get_data_partial_missing_country(self, mock_ud):
        """When a requested country has no data, data_completeness = partial."""
        ud = MagicMock()
        # Only BRA returns data — NGA is missing
        ud.unicefData.return_value = pd.DataFrame(
            {
                "country_code": ["BRA", "BRA"],
                "country_name": ["Brazil", "Brazil"],
                "indicator_code": ["CME_MRY0T4"] * 2,
                "period": [2020, 2021],
                "value": [14.2, 13.8],
                "sex": ["_T"] * 2,
            }
        )
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA", "NGA"])
        assert result["data_completeness"] == "partial"
        assert "warnings" in result
        assert any("NGA" in w for w in result["warnings"])
        # The warning must include anti-hallucination language
        assert any("Do NOT estimate" in w for w in result["warnings"])

    @patch("unicefstats_mcp.server._get_ud")
    def test_get_data_truncated(self, mock_ud):
        """When rows are truncated, data_completeness = truncated."""
        ud = MagicMock()
        ud.unicefData.return_value = pd.DataFrame(
            {
                "country_code": ["BRA"] * 20,
                "country_name": ["Brazil"] * 20,
                "indicator_code": ["CME_MRY0T4"] * 20,
                "period": list(range(2000, 2020)),
                "value": [15.0] * 20,
                "sex": ["_T"] * 20,
            }
        )
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA"], limit=5)
        assert result["data_completeness"] == "truncated"
        assert "warnings" in result


class TestNoDataEnvelope:
    """When data is confirmed absent, status must be no_data."""

    @patch("unicefstats_mcp.server._get_ud")
    def test_empty_dataframe_is_no_data(self, mock_ud):
        ud = MagicMock()
        ud.unicefData.return_value = pd.DataFrame()
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA"])
        assert result["status"] == "no_data"
        assert result["data_completeness"] == "empty"
        assert "instruction" in result

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_search_no_results_is_no_data(self, _mock):
        result = search_indicators(query="zzzznonexistentzzzz", limit=10)
        assert result["status"] == "no_data"
        assert result["data_completeness"] == "empty"

    @patch("unicefstats_mcp.server._get_ud")
    def test_indicator_not_found(self, mock_ud):
        ud = MagicMock()
        ud.get_indicator_info.return_value = None
        mock_ud.return_value = ud

        result = get_indicator_info(code="INVALID_XYZ")
        assert result["status"] == "no_data"
        assert result["data_completeness"] == "empty"
        assert "instruction" in result


class TestErrorEnvelope:
    """Validation errors must use status=error (not no_data)."""

    def test_invalid_indicator_code(self):
        result = get_data(indicator="", countries=["BRA"])
        assert result["status"] == "error"
        assert "error" in result

    def test_invalid_country_code(self):
        result = get_data(indicator="CME_MRY0T4", countries=["TOOLONG"])
        assert result["status"] == "error"

    @patch("unicefstats_mcp.server._get_ud")
    def test_api_error_is_error(self, mock_ud):
        ud = MagicMock()
        ud.unicefData.side_effect = RuntimeError("Network timeout")
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA"])
        assert result["status"] == "error"
        assert "tip" in result


class TestCitationField:
    """get_data responses must include a verifiable citation."""

    @patch("unicefstats_mcp.server._get_ud")
    def test_citation_present(self, mock_ud):
        ud = MagicMock()
        ud.unicefData.return_value = pd.DataFrame(
            {
                "country_code": ["BRA"],
                "country_name": ["Brazil"],
                "indicator_code": ["CME_MRY0T4"],
                "period": [2021],
                "value": [14.0],
                "sex": ["_T"],
            }
        )
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA"])
        assert "citation" in result
        citation = result["citation"]
        assert citation["provider"] == "UNICEF Data Warehouse"
        assert "sdmx.data.unicef.org" in citation["api_url"]
        assert "CME_MRY0T4" in citation["api_url"]
        assert "BRA" in citation["api_url"]
        assert "note" in citation


class TestWarningsField:
    """Warnings must be a list of strings or absent (not empty list)."""

    @patch("unicefstats_mcp.server._get_ud")
    def test_no_warnings_when_complete(self, mock_ud):
        ud = MagicMock()
        ud.unicefData.return_value = pd.DataFrame(
            {
                "country_code": ["BRA"],
                "country_name": ["Brazil"],
                "indicator_code": ["CME_MRY0T4"],
                "period": [2021],
                "value": [14.0],
                "sex": ["_T"],
            }
        )
        mock_ud.return_value = ud

        result = get_data(indicator="CME_MRY0T4", countries=["BRA"])
        # When no issues, warnings key should be absent (not an empty list)
        assert "warnings" not in result

    @patch("unicefstats_mcp.server._get_ud")
    def test_indicator_info_has_warnings(self, mock_ud):
        ud = MagicMock()
        ud.get_indicator_info.return_value = {
            "name": "Under-five mortality rate",
            "description": "Probability of dying...",
            "category": "CME",
        }
        ud.get_dataflow_for_indicator.return_value = "CME"
        mock_ud.return_value = ud

        result = get_indicator_info(code="CME_MRY0T4")
        # Indicator info should always warn about disaggregation availability
        assert "warnings" in result
        assert any("Disaggregation" in w for w in result["warnings"])


class TestTemporalCoverageWarnings:
    """get_temporal_coverage should always include coverage caveats."""

    @patch("unicefstats_mcp.server._get_ud")
    def test_always_has_coverage_warning(self, mock_ud):
        ud = MagicMock()
        ud.unicefData.return_value = pd.DataFrame(
            {
                "country_code": ["BRA", "BRA"],
                "period": [2010, 2020],
                "value": [20.1, 14.2],
            }
        )
        mock_ud.return_value = ud

        result = get_temporal_coverage(code="CME_MRY0T4")
        assert result["status"] == "ok"
        assert "warnings" in result
        assert any("Coverage varies" in w for w in result["warnings"])
