"""Unit tests for formatters module."""

from __future__ import annotations

import pandas as pd

from unicefstats_mcp.formatters import (
    _clean_nans,
    apply_limit,
    compute_trend,
    error,
    ok,
    summarize_data,
    truncate_description,
)


class TestCleanNans:
    """NaN/inf values must be replaced with None for valid JSON."""

    def test_nan_replaced(self):
        records = [{"a": 1.0, "b": float("nan")}]
        cleaned = _clean_nans(records)
        assert cleaned[0]["a"] == 1.0
        assert cleaned[0]["b"] is None

    def test_inf_replaced(self):
        records = [{"a": float("inf"), "b": float("-inf")}]
        cleaned = _clean_nans(records)
        assert cleaned[0]["a"] is None
        assert cleaned[0]["b"] is None

    def test_normal_values_preserved(self):
        records = [{"a": 0.0, "b": "text", "c": None, "d": 42}]
        cleaned = _clean_nans(records)
        assert cleaned[0] == {"a": 0.0, "b": "text", "c": None, "d": 42}

    def test_empty_list(self):
        assert _clean_nans([]) == []


class TestTruncateDescription:
    def test_short_string_unchanged(self):
        assert truncate_description("Hello") == "Hello"

    def test_none_returns_empty(self):
        assert truncate_description(None) == ""

    def test_long_string_truncated(self):
        text = "a" * 200
        result = truncate_description(text, max_len=50)
        assert len(result) <= 51  # 50 + ellipsis char
        assert result.endswith("\u2026")

    def test_exact_limit_not_truncated(self):
        text = "a" * 150
        assert truncate_description(text, max_len=150) == text


class TestApplyLimit:
    def test_under_limit(self):
        records = [{"a": 1}, {"a": 2}]
        result, truncated = apply_limit(records, 5)
        assert result == records
        assert truncated is False

    def test_over_limit(self):
        records = [{"a": i} for i in range(10)]
        result, truncated = apply_limit(records, 3)
        assert len(result) == 3
        assert truncated is True

    def test_exact_limit(self):
        records = [{"a": i} for i in range(5)]
        result, truncated = apply_limit(records, 5)
        assert len(result) == 5
        assert truncated is False


class TestSummarizeData:
    def test_value_range(self):
        df = pd.DataFrame({"value": [10.0, 20.0, 30.0], "period": [2020, 2021, 2022]})
        summary = summarize_data(df)
        assert summary["value_range"]["min"] == 10.0
        assert summary["value_range"]["max"] == 30.0
        assert summary["value_range"]["mean"] == 20.0

    def test_year_range(self):
        df = pd.DataFrame({"value": [1.0], "period": [2015]})
        summary = summarize_data(df)
        assert summary["year_range"]["earliest"] == 2015
        assert summary["year_range"]["latest"] == 2015

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["value", "period"])
        summary = summarize_data(df)
        assert "value_range" not in summary


class TestComputeTrend:
    def test_declining_trend(self):
        df = pd.DataFrame(
            {
                "country_code": ["BRA"] * 6,
                "period": [2016, 2017, 2018, 2019, 2020, 2021],
                "value": [20.0, 19.0, 18.0, 17.0, 16.0, 15.0],
            }
        )
        trend = compute_trend(df, window=5)
        assert trend is not None
        assert "BRA" in trend
        assert trend["BRA"]["direction"] == "declining"
        assert trend["BRA"]["aarc"] < 0

    def test_increasing_trend(self):
        df = pd.DataFrame(
            {
                "country_code": ["IND"] * 6,
                "period": [2016, 2017, 2018, 2019, 2020, 2021],
                "value": [50.0, 52.0, 54.0, 56.0, 58.0, 60.0],
            }
        )
        trend = compute_trend(df, window=5)
        assert trend is not None
        assert trend["IND"]["direction"] == "increasing"

    def test_insufficient_data(self):
        df = pd.DataFrame(
            {"country_code": ["BRA"], "period": [2021], "value": [15.0]}
        )
        trend = compute_trend(df, window=5)
        assert trend is None


class TestOkEnvelope:
    def test_default_fields(self):
        result = ok({"key": "value"})
        assert result["status"] == "ok"
        assert result["source"] == "UNICEF Data Warehouse via SDMX API"
        assert result["data_completeness"] == "complete"
        assert result["key"] == "value"
        assert "warnings" not in result

    def test_with_warnings(self):
        result = ok({"key": "value"}, warnings=["Some caveat"])
        assert result["warnings"] == ["Some caveat"]

    def test_partial_completeness(self):
        result = ok({"key": "value"}, data_completeness="partial")
        assert result["data_completeness"] == "partial"


class TestErrorEnvelope:
    def test_basic_error(self):
        result = error("Something failed")
        assert result["status"] == "error"
        assert result["error"] == "Something failed"
        assert "instruction" not in result

    def test_error_with_tip(self):
        result = error("Failed", tip="Try this instead")
        assert result["tip"] == "Try this instead"

    def test_no_data_error(self):
        result = error("Not found", no_data=True)
        assert result["status"] == "no_data"
        assert result["data_completeness"] == "empty"
        assert "instruction" in result
        # v0.6.0 strengthened the directive — MUST/MUST NOT are now the load-bearing
        # behavioral verbs (concrete behavioral rules, not abstract "do not estimate").
        assert "MUST" in result["instruction"]
        assert "MUST NOT" in result["instruction"]
        # Should name the user-visible refusal text the model has to produce.
        assert "No data is available" in result["instruction"]
        # And list at least one forbidden hedge phrase.
        assert "approximately" in result["instruction"].lower()

    def test_error_with_extra(self):
        """v0.6.0: error() accepts an `extra` dict that gets merged into the result.

        Used by get_data's pre-flight year-frontier check to attach the
        data_frontier metadata + out_of_frontier flag alongside the standard
        no_data envelope.
        """
        result = error(
            "Year exceeds frontier",
            no_data=True,
            extra={
                "data_frontier": {"max_year_observed": 2024, "indicator": "CME_MRY0T4"},
                "out_of_frontier": True,
            },
        )
        assert result["status"] == "no_data"
        assert result["out_of_frontier"] is True
        assert result["data_frontier"]["max_year_observed"] == 2024
        assert result["data_frontier"]["indicator"] == "CME_MRY0T4"
