"""Smoke tests for MCP prompts and resources.

These verify that prompts return well-formed strings and resources
return non-empty content. They do NOT test the MCP protocol layer.
"""

from __future__ import annotations

from unittest.mock import patch

from tests.conftest import MOCK_COUNTRIES, MOCK_INDICATORS
from unicefstats_mcp.server import (
    categories_resource,
    compare_indicators,
    context_resource,
    countries_resource,
    country_profile,
    glossary_resource,
    llm_instructions_resource,
    sdg_progress,
    system_prompt_resource,
    trend_analysis,
    write_unicefdata_code,
)


class TestPrompts:
    """MCP prompts return instructional strings for the LLM."""

    def test_compare_indicators(self):
        result = compare_indicators(
            indicator="CME_MRY0T4",
            countries="BRA,IND,NGA",
            start_year="2015",
            end_year="2023",
        )
        assert isinstance(result, str)
        assert "CME_MRY0T4" in result
        assert "BRA" in result
        assert "get_indicator_info" in result
        assert "get_data" in result

    def test_write_unicefdata_code(self):
        result = write_unicefdata_code(
            task="Plot stunting trends for Brazil",
            language="python",
        )
        assert isinstance(result, str)
        assert "python" in result.lower()
        assert "get_api_reference" in result

    def test_trend_analysis(self):
        result = trend_analysis(
            indicator="CME_MRY0T4",
            country="BRA",
        )
        assert isinstance(result, str)
        assert "CME_MRY0T4" in result
        assert "trend" in result.lower()

    def test_country_profile(self):
        result = country_profile(country="BRA")
        assert isinstance(result, str)
        assert "BRA" in result

    def test_sdg_progress(self):
        result = sdg_progress(country="BRA")
        assert isinstance(result, str)
        assert "SDG" in result or "sdg" in result.lower()


class TestResources:
    """MCP resources return non-empty reference content."""

    def test_llm_instructions(self):
        content = llm_instructions_resource()
        assert isinstance(content, str)
        assert len(content) > 100
        # Must include epistemic safety rules
        assert "DO NOT" in content
        assert "data_completeness" in content
        assert "no_data" in content

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS)
    def test_categories_resource(self, _mock):
        content = categories_resource()
        assert isinstance(content, str)
        assert "CME" in content
        assert "NUTRITION" in content

    @patch("unicefstats_mcp.server._get_countries", return_value=MOCK_COUNTRIES)
    def test_countries_resource(self, _mock):
        content = countries_resource()
        assert isinstance(content, str)
        assert "BRA" in content
        assert "Brazil" in content

    def test_glossary_resource(self):
        content = glossary_resource()
        assert isinstance(content, str)
        assert len(content) > 100
        # Must include disaggregation codes
        assert "_T" in content
        assert "Q1" in content

    def test_system_prompt_resource(self):
        """v0.5.0: anti-extrapolation system prompt with temporal-frontier rule."""
        content = system_prompt_resource()
        assert isinstance(content, str)
        assert content.strip()
        # Must define the operating loop
        assert "search_indicators" in content
        assert "get_temporal_coverage" in content
        assert "get_data" in content
        # Must contain the anti-extrapolation rule
        assert "frontier" in content.lower()
        assert "No data is available" in content
        # Must list at least one forbidden phrase
        assert "approximately" in content.lower() or "extrapolat" in content.lower()

    def test_context_resource(self):
        """v0.5.0: runtime context with current_date / current_year."""
        import json
        from datetime import datetime, timezone

        content = context_resource()
        assert isinstance(content, str)
        # Returns valid JSON
        data = json.loads(content)
        # current_year is an int matching today's UTC year
        assert "current_year" in data
        assert isinstance(data["current_year"], int)
        assert data["current_year"] == datetime.now(timezone.utc).year
        # current_date is YYYY-MM-DD string
        assert "current_date" in data
        assert isinstance(data["current_date"], str)
        assert len(data["current_date"]) == 10  # "YYYY-MM-DD"
        # Carries the anti-extrapolation note
        assert "note" in data
        assert "extrapolat" in data["note"].lower()
