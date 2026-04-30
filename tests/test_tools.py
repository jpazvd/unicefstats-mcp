"""Tests for list_countries, get_api_reference, and get_server_metadata tools."""

from __future__ import annotations

from unittest.mock import patch

from tests.conftest import MOCK_COUNTRIES
from unicefstats_mcp.server import get_api_reference, get_server_metadata, list_countries


class TestListCountries:
    """Tests for list_countries tool."""

    @patch("unicefstats_mcp.server._get_countries", return_value=MOCK_COUNTRIES)
    def test_returns_all_countries(self, _mock):
        result = list_countries()
        assert result["status"] == "ok"
        assert result["total"] == len(MOCK_COUNTRIES)
        codes = [c["iso3"] for c in result["countries"]]
        assert "BRA" in codes
        assert "IND" in codes

    @patch("unicefstats_mcp.server._get_countries", return_value=MOCK_COUNTRIES)
    def test_region_filter(self, _mock):
        result = list_countries(region="bra")
        assert result["status"] == "ok"
        assert result["total"] >= 1
        # Brazil matches "bra" (case-insensitive partial match)
        codes = [c["iso3"] for c in result["countries"]]
        assert "BRA" in codes

    @patch("unicefstats_mcp.server._get_countries", return_value=MOCK_COUNTRIES)
    def test_region_filter_no_match(self, _mock):
        result = list_countries(region="nonexistent_region")
        assert result["status"] == "ok"
        assert result["total"] == 0
        assert result["countries"] == []

    @patch("unicefstats_mcp.server._get_countries", return_value=MOCK_COUNTRIES)
    def test_sorted_by_iso3(self, _mock):
        result = list_countries()
        codes = [c["iso3"] for c in result["countries"]]
        assert codes == sorted(codes)

    @patch(
        "unicefstats_mcp.server._get_countries",
        side_effect=RuntimeError("Load failed"),
    )
    def test_load_error(self, _mock):
        result = list_countries()
        assert result["status"] == "error"


class TestGetApiReference:
    """Tests for get_api_reference tool."""

    def test_python_all_functions(self):
        result = get_api_reference(language="python")
        assert result["status"] == "ok"
        assert result["language"] == "python"
        assert "install" in result
        assert "functions" in result

    def test_r_specific_function(self):
        result = get_api_reference(language="r", function="unicefData")
        assert result["status"] == "ok"
        assert result["language"] == "r"
        assert "signature" in result

    def test_stata(self):
        result = get_api_reference(language="stata")
        assert result["status"] == "ok"

    def test_invalid_language(self):
        result = get_api_reference(language="julia")
        assert result["status"] == "error"
        assert "Unknown language" in result["error"]

    def test_invalid_function(self):
        result = get_api_reference(language="python", function="nonexistent")
        assert result["status"] == "error"
        assert "not found" in result["error"]


class TestGetServerMetadata:
    """Tests for get_server_metadata tool."""

    def test_returns_identity(self):
        result = get_server_metadata()
        assert result["status"] == "ok"
        assert result["name"] == "io.github.jpazvd/unicefstats-mcp"
        assert result["registry_identity"] == "io.github.jpazvd/unicefstats-mcp"

    def test_returns_version(self):
        from unicefstats_mcp import __version__

        result = get_server_metadata()
        assert result["version"] == __version__

    def test_returns_publisher(self):
        result = get_server_metadata()
        publisher = result["publisher"]
        assert publisher["name"] == "Joao Pedro Azevedo"
        assert publisher["github"] == "jpazvd"

    def test_returns_data_source(self):
        result = get_server_metadata()
        ds = result["data_source"]
        assert ds["name"] == "UNICEF Data Warehouse"
        assert ds["protocol"] == "SDMX REST v2.1"
        assert ds["access"] == "public"
        assert ds["authentication"] == "none"

    def test_returns_canonical_urls(self):
        result = get_server_metadata()
        assert "github.com/jpazvd/unicefstats-mcp" in result["canonical_source"]
        assert "pypi.org/project/unicefstats-mcp" in result["pypi_package"]
