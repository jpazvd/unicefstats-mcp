"""Tests for search_indicators and list_categories tools."""

from __future__ import annotations

from unittest.mock import patch

from tests.conftest import MOCK_INDICATORS
from unicefstats_mcp.server import list_categories, search_indicators


class TestSearchIndicators:
    """Tests for search_indicators tool."""

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_keyword_match(self, _mock):
        result = search_indicators(query="mortality", limit=10)
        assert "error" not in result
        assert result["total_matches"] >= 2
        codes = [r["code"] for r in result["results"]]
        assert "CME_MRY0T4" in codes
        assert "CME_MRY0" in codes

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_exact_code_match(self, _mock):
        result = search_indicators(query="CME_MRY0T4", limit=10)
        assert result["results"][0]["code"] == "CME_MRY0T4"

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_no_results(self, _mock):
        result = search_indicators(query="nonexistentxyz", limit=10)
        assert result["status"] == "no_data"
        assert "No indicators match" in result["error"]

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_limit_applied(self, _mock):
        result = search_indicators(query="mortality", limit=2)
        assert result["showing"] <= 2
        assert len(result["results"]) <= 2

    def test_query_too_short(self):
        result = search_indicators(query="a", limit=10)
        assert "error" in result

    def test_limit_out_of_range(self):
        result = search_indicators(query="mortality", limit=0)
        assert "error" in result

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_case_insensitive(self, _mock):
        result = search_indicators(query="MORTALITY", limit=10)
        assert result["total_matches"] >= 2

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_category_match(self, _mock):
        result = search_indicators(query="NUTRITION", limit=10)
        assert result["total_matches"] >= 1
        codes = [r["code"] for r in result["results"]]
        assert "NT_BF_EXBF" in codes


class TestListCategories:
    """Tests for list_categories tool."""

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_returns_categories(self, _mock):
        result = list_categories()
        assert "error" not in result
        assert result["total_categories"] >= 1
        assert result["total_indicators"] == 5
        names = [c["name"] for c in result["categories"]]
        assert "CME" in names

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_counts_correct(self, _mock):
        result = list_categories()
        cme_cat = next(c for c in result["categories"] if c["name"] == "CME")
        assert cme_cat["indicator_count"] == 2  # CME_MRY0T4 and CME_MRY0
