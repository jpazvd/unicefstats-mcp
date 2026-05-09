"""Unit tests for the four per-source response parsers in
`examples/mcp-smoke-test/mcp-figures.py`.

These guard the data-shape contract for each upstream MCP server's
response. If an upstream changes its response format, the smoke test
silently produces empty/wrong figures — these fixture-based tests
fail loudly first.

Loading via `importlib.util` because the script filename has a hyphen
(`mcp-figures.py`) which makes it un-importable via standard `import`.
The script has matplotlib at module top; we `pytest.importorskip` it
to keep these tests runnable in stripped-down test envs.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

pytest.importorskip("matplotlib")

# Load the script as a module via its file path. This bypasses the
# hyphenated filename problem and keeps the script as-published in the
# public mirror (don't rename to mcp_figures.py — that breaks the
# `uv run --script` entrypoint convention).
_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "examples", "mcp-smoke-test", "mcp-figures.py"
)
_spec = importlib.util.spec_from_file_location("mcp_figures", _SCRIPT_PATH)
mcp_figures = importlib.util.module_from_spec(_spec)
sys.modules["mcp_figures"] = mcp_figures
_spec.loader.exec_module(mcp_figures)


class TestParseUnicefstats:
    """unicefstats response: JSON with `data: [{country, period, value}]`."""

    def test_basic_response(self):
        text = json.dumps({
            "indicator": "CME_MRY0",
            "data": [
                {"country": "India", "period": 2020, "value": 30.5},
                {"country": "India", "period": 2021, "value": 28.0},
                {"country": "Kenya", "period": 2020, "value": 41.2},
            ],
        })
        label, indicator, by_country = mcp_figures.parse_unicefstats(text)
        assert "unicefstats" in label
        assert indicator == "CME_MRY0"
        assert set(by_country) == {"India", "Kenya"}
        # Sorted by year
        assert by_country["India"] == [(2020, 30.5), (2021, 28.0)]
        assert by_country["Kenya"] == [(2020, 41.2)]

    def test_canonical_name_preferred_over_code(self):
        """If `indicator_resolution.canonical_name` is present, prefer it."""
        text = json.dumps({
            "indicator": "CME_MRY0",
            "indicator_resolution": {"canonical_name": "Under-five mortality rate"},
            "data": [{"country": "India", "period": 2020, "value": 30.0}],
        })
        _, indicator, _ = mcp_figures.parse_unicefstats(text)
        assert indicator == "Under-five mortality rate"

    def test_missing_fields_skipped(self):
        text = json.dumps({
            "indicator": "X",
            "data": [
                {"country": "India", "period": 2020, "value": 30.0},
                {"country": "India", "period": None, "value": 31.0},  # skipped
                {"country": "India", "period": "not-a-year", "value": 32.0},  # skipped
                {"country": None, "period": 2021, "value": 33.0},  # skipped
            ],
        })
        _, _, by_country = mcp_figures.parse_unicefstats(text)
        assert by_country == {"India": [(2020, 30.0)]}

    def test_iso3_fallback_for_country_field(self):
        """Some response variants use `iso3` instead of `country`."""
        text = json.dumps({
            "indicator": "X",
            "data": [{"iso3": "IND", "period": 2020, "value": 30.0}],
        })
        _, _, by_country = mcp_figures.parse_unicefstats(text)
        assert by_country == {"IND": [(2020, 30.0)]}

    def test_empty_data_returns_empty_dict(self):
        text = json.dumps({"indicator": "X", "data": []})
        _, _, by_country = mcp_figures.parse_unicefstats(text)
        assert by_country == {}


class TestParseWorldBank:
    """World Bank MCP returns CSV. Header row uses dotted column names."""

    def test_basic_csv(self):
        text = (
            "country.value,countryiso3code,date,value,indicator.value\n"
            "India,IND,2020,32.5,Mortality rate (per 1000)\n"
            "India,IND,2021,30.1,Mortality rate (per 1000)\n"
            "Kenya,KEN,2020,40.0,Mortality rate (per 1000)\n"
        )
        label, indicator, by_country = mcp_figures.parse_world_bank(text)
        assert "world-bank" in label
        assert indicator == "Mortality rate (per 1000)"
        assert by_country["India"] == [(2020, 32.5), (2021, 30.1)]
        assert by_country["Kenya"] == [(2020, 40.0)]

    def test_iso3_fallback_when_country_value_blank(self):
        text = (
            "country.value,countryiso3code,date,value,indicator.value\n"
            ",IND,2020,32.5,X\n"
        )
        _, _, by_country = mcp_figures.parse_world_bank(text)
        assert "IND" in by_country

    def test_empty_value_rows_skipped(self):
        text = (
            "country.value,countryiso3code,date,value,indicator.value\n"
            "India,IND,2020,,X\n"  # missing value
            "India,IND,,32.5,X\n"  # missing date
            "India,IND,2021,30.1,X\n"  # valid
        )
        _, _, by_country = mcp_figures.parse_world_bank(text)
        assert by_country == {"India": [(2021, 30.1)]}


class TestParseData360:
    """data360 returns SDMX-shaped JSON with REF_AREA / TIME_PERIOD / OBS_VALUE."""

    def test_basic_response(self):
        text = json.dumps({
            "data": [
                {"REF_AREA": "IND", "TIME_PERIOD": "2020", "OBS_VALUE": 32.5,
                 "INDICATOR": "WB_WDI_SH_DYN_MORT"},
                {"REF_AREA": "IND", "TIME_PERIOD": "2021", "OBS_VALUE": 30.1,
                 "INDICATOR": "WB_WDI_SH_DYN_MORT"},
            ],
        })
        label, indicator, by_country = mcp_figures.parse_data360(text)
        assert "data360" in label
        assert indicator == "WB_WDI_SH_DYN_MORT"
        assert by_country == {"IND": [(2020, 32.5), (2021, 30.1)]}

    def test_quarterly_period_extracts_year(self):
        """TIME_PERIOD may be 'YYYY-Q1'; year is the first 4 chars."""
        text = json.dumps({
            "data": [
                {"REF_AREA": "USA", "TIME_PERIOD": "2020-Q1", "OBS_VALUE": 3.5},
                {"REF_AREA": "USA", "TIME_PERIOD": "2020-Q2", "OBS_VALUE": 13.0},
            ],
        })
        _, _, by_country = mcp_figures.parse_data360(text)
        # Both rows extract year 2020, so both are kept (parser doesn't dedupe)
        assert by_country == {"USA": [(2020, 3.5), (2020, 13.0)]}

    def test_alternate_time_field_names(self):
        """data360 may use TIME or PERIOD instead of TIME_PERIOD."""
        text = json.dumps({
            "data": [{"REF_AREA": "IND", "TIME": "2020", "OBS_VALUE": 32.5}],
        })
        _, _, by_country = mcp_figures.parse_data360(text)
        assert by_country == {"IND": [(2020, 32.5)]}


class TestParseDataCommons:
    """Google Data Commons: byVariable → byEntity → orderedFacets nested envelope."""

    def test_basic_response(self):
        text = json.dumps({
            "byVariable": {
                "MortalityRate_Person_Upto5Years": {
                    "byEntity": {
                        "country/IND": {
                            "orderedFacets": [{
                                "observations": [
                                    {"date": "2020", "value": 32.5},
                                    {"date": "2021", "value": 30.1},
                                ],
                            }],
                        },
                        "country/KEN": {
                            "orderedFacets": [{
                                "observations": [
                                    {"date": "2020", "value": 41.2},
                                ],
                            }],
                        },
                    },
                },
            },
        })
        label, indicator, by_country = mcp_figures.parse_data_commons(text)
        assert "data-commons" in label
        assert indicator == "MortalityRate_Person_Upto5Years"
        # Entity prefix "country/" stripped so axis lines up with other sources
        assert set(by_country) == {"IND", "KEN"}
        assert by_country["IND"] == [(2020, 32.5), (2021, 30.1)]
        assert by_country["KEN"] == [(2020, 41.2)]

    def test_multiple_facets_flattened(self):
        """Multiple orderedFacets (e.g. WB import + UN import for same variable)
        should both contribute observations — parser doesn't deduplicate."""
        text = json.dumps({
            "byVariable": {
                "X": {
                    "byEntity": {
                        "country/IND": {
                            "orderedFacets": [
                                {"observations": [{"date": "2020", "value": 30.0}]},
                                {"observations": [{"date": "2020", "value": 31.5}]},
                            ],
                        },
                    },
                },
            },
        })
        _, _, by_country = mcp_figures.parse_data_commons(text)
        # Both facets' observations are kept (sorted by year — same year here)
        assert len(by_country["IND"]) == 2

    def test_iso_date_year_extracted(self):
        """date may be 'YYYY-MM' or full ISO; first 4 chars are the year."""
        text = json.dumps({
            "byVariable": {
                "X": {
                    "byEntity": {
                        "country/USA": {
                            "orderedFacets": [{
                                "observations": [
                                    {"date": "2020-01-01", "value": 3.5},
                                    {"date": "2021-Q2", "value": 4.0},
                                ],
                            }],
                        },
                    },
                },
            },
        })
        _, _, by_country = mcp_figures.parse_data_commons(text)
        assert by_country == {"USA": [(2020, 3.5), (2021, 4.0)]}

    def test_missing_value_or_date_skipped(self):
        text = json.dumps({
            "byVariable": {
                "X": {
                    "byEntity": {
                        "country/IND": {
                            "orderedFacets": [{
                                "observations": [
                                    {"date": "2020", "value": 30.0},
                                    {"date": None, "value": 31.0},  # skipped
                                    {"date": "2021", "value": None},  # skipped
                                    {"date": "not-a-year", "value": 32.0},  # skipped
                                ],
                            }],
                        },
                    },
                },
            },
        })
        _, _, by_country = mcp_figures.parse_data_commons(text)
        assert by_country == {"IND": [(2020, 30.0)]}

    def test_empty_byVariable_returns_empty_dict(self):
        text = json.dumps({"byVariable": {}, "facets": {}})
        _, indicator, by_country = mcp_figures.parse_data_commons(text)
        assert indicator == "?"
        assert by_country == {}

    def test_entity_dcid_without_slash_passed_through(self):
        """Defensive: if an entity DCID doesn't have the country/ prefix
        (e.g. 'IND' or 'Earth'), use it verbatim rather than crashing."""
        text = json.dumps({
            "byVariable": {
                "X": {
                    "byEntity": {
                        "Earth": {
                            "orderedFacets": [{
                                "observations": [{"date": "2020", "value": 7800000000}],
                            }],
                        },
                    },
                },
            },
        })
        _, _, by_country = mcp_figures.parse_data_commons(text)
        assert "Earth" in by_country


class TestSanitizeForMarkdown:
    """The --invoked-by label flows from a CLI flag into a markdown report
    rendered by GitHub. Backticks / angle-brackets in the label would break
    the code-span boundary and resume markdown / HTML parsing, so the
    sanitiser strips them. Low-blast-radius (operator runs the script
    themselves) but trivial to harden.
    """

    def test_alphanumeric_passes_through(self):
        assert mcp_figures._sanitize_for_markdown("Claude Opus 4.7") == "Claude Opus 4.7"

    def test_safelist_punctuation_kept(self):
        # Dot, underscore, hyphen, parens, slash, space — all on the safelist
        s = "Claude Opus 4.7 (1M context) via Claude Code"
        assert mcp_figures._sanitize_for_markdown(s) == s

    def test_backtick_stripped(self):
        # Backtick would close the markdown code-span and resume parsing
        assert mcp_figures._sanitize_for_markdown("Claude`Code") == "ClaudeCode"

    def test_angle_brackets_stripped(self):
        # < and > would inject HTML when GitHub renders markdown.
        # Slashes are on the safelist (path-like labels are common), so
        # they survive — only the angle-brackets get dropped.
        out = mcp_figures._sanitize_for_markdown("</script><script>alert(1)</script>")
        assert "<" not in out
        assert ">" not in out
        assert out == "/scriptscriptalert(1)/script"

    def test_newline_stripped(self):
        # Newlines would break the single-line footnote and confuse the
        # markdown report layout
        assert mcp_figures._sanitize_for_markdown("Claude\nCode") == "ClaudeCode"

    def test_truncated_to_max_len(self):
        long_label = "x" * 500
        out = mcp_figures._sanitize_for_markdown(long_label)
        assert len(out) == 120  # default max_len

    def test_empty_returns_empty(self):
        assert mcp_figures._sanitize_for_markdown("") == ""

    def test_idempotent(self):
        # Sanitising already-clean text is a no-op
        s = "Claude Opus 4.7"
        assert mcp_figures._sanitize_for_markdown(
            mcp_figures._sanitize_for_markdown(s)
        ) == s


class TestParseFred:
    """FRED MCP returns JSON with title/units and data: [{date, value}]."""

    def test_basic_response(self):
        text = json.dumps({
            "title": "Unemployment Rate",
            "units": "Percent",
            "series_id": "UNRATE",
            "data": [
                {"date": "2020-01-01", "value": 3.5},
                {"date": "2020-04-01", "value": 14.7},
                {"date": "2020-12-01", "value": 6.7},
            ],
        })
        label, indicator, series = mcp_figures.parse_fred(text)
        assert "fred" in label
        # Title appended with units in parens
        assert "Unemployment Rate" in indicator
        assert "Percent" in indicator
        # Chronologically sorted (already sorted in input, but parser sorts too)
        assert series[0] == ("2020-01-01", 3.5)
        assert series[-1] == ("2020-12-01", 6.7)
        assert len(series) == 3

    def test_falls_back_to_series_id_when_no_title(self):
        text = json.dumps({
            "series_id": "UNRATE",
            "data": [{"date": "2020-01-01", "value": 3.5}],
        })
        _, indicator, _ = mcp_figures.parse_fred(text)
        assert indicator == "UNRATE"

    def test_invalid_value_rows_skipped(self):
        text = json.dumps({
            "title": "X",
            "data": [
                {"date": "2020-01-01", "value": 3.5},
                {"date": "2020-02-01", "value": "."},  # FRED uses "." for missing
                {"date": "2020-03-01", "value": 4.0},
            ],
        })
        _, _, series = mcp_figures.parse_fred(text)
        assert len(series) == 2
        assert series == [("2020-01-01", 3.5), ("2020-03-01", 4.0)]
