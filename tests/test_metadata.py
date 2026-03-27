"""Tests for get_indicator_info and get_temporal_coverage tools."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from unicefstats_mcp.server import get_indicator_info, get_temporal_coverage


class TestGetIndicatorInfo:
    """Tests for get_indicator_info tool."""

    @patch("unicefstats_mcp.server._get_ud")
    def test_valid_indicator(self, mock_ud):
        ud = MagicMock()
        ud.get_indicator_info.return_value = {
            "name": "Under-five mortality rate",
            "description": "Probability of dying...",
            "category": "CME",
        }
        ud.get_dataflow_for_indicator.return_value = "CME"
        mock_ud.return_value = ud

        result = get_indicator_info(code="CME_MRY0T4")
        assert "error" not in result
        assert result["code"] == "CME_MRY0T4"
        assert result["name"] == "Under-five mortality rate"
        assert result["dataflow"] == "CME"
        assert "sdmx_api" in result
        assert "disaggregation_filters" in result

    @patch("unicefstats_mcp.server._get_ud")
    def test_invalid_indicator(self, mock_ud):
        ud = MagicMock()
        ud.get_indicator_info.return_value = None
        mock_ud.return_value = ud

        result = get_indicator_info(code="INVALID_XYZ")
        assert "error" in result
        assert "not found" in result["error"]
        assert "tip" in result


class TestGetTemporalCoverage:
    """Tests for get_temporal_coverage tool."""

    @patch("unicefstats_mcp.server._get_ud")
    def test_valid_indicator(self, mock_ud):
        ud = MagicMock()
        ud.unicefData.return_value = pd.DataFrame(
            {
                "country_code": ["BRA", "BRA", "IND", "IND"],
                "period": [2010, 2020, 2010, 2020],
                "value": [20.1, 14.2, 50.3, 35.1],
            }
        )
        mock_ud.return_value = ud

        result = get_temporal_coverage(code="CME_MRY0T4")
        assert "error" not in result
        assert result["start_year"] == 2010
        assert result["end_year"] == 2020
        assert result["countries_with_data"] == 2

    @patch("unicefstats_mcp.server._get_ud")
    def test_empty_result(self, mock_ud):
        ud = MagicMock()
        ud.unicefData.return_value = pd.DataFrame()
        mock_ud.return_value = ud

        result = get_temporal_coverage(code="CME_MRY0T4")
        assert "error" in result

    @patch("unicefstats_mcp.server._get_ud")
    def test_api_error(self, mock_ud):
        ud = MagicMock()
        ud.unicefData.side_effect = RuntimeError("Connection timeout")
        mock_ud.return_value = ud

        result = get_temporal_coverage(code="CME_MRY0T4")
        assert "error" in result
