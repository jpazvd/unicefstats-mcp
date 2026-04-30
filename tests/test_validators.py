"""Unit tests for validators module."""

from __future__ import annotations

from unicefstats_mcp.validators import (
    validate_countries,
    validate_indicator,
    validate_limit,
    validate_query,
    validate_residence,
    validate_sex,
    validate_wealth_quintile,
    validate_year,
)


class TestValidateIndicator:
    def test_valid(self):
        assert validate_indicator("CME_MRY0T4") is None

    def test_empty(self):
        assert validate_indicator("") is not None

    def test_whitespace(self):
        assert validate_indicator("   ") is not None

    def test_too_long(self):
        assert validate_indicator("A" * 51) is not None

    def test_max_length_ok(self):
        assert validate_indicator("A" * 50) is None


class TestValidateYear:
    def test_valid(self):
        assert validate_year(2020, "start_year") is None

    def test_none_allowed(self):
        assert validate_year(None, "start_year") is None

    def test_too_low(self):
        assert validate_year(1899, "start_year") is not None

    def test_too_high(self):
        assert validate_year(2101, "end_year") is not None

    def test_boundary_low(self):
        assert validate_year(1900, "start_year") is None

    def test_boundary_high(self):
        assert validate_year(2100, "end_year") is None


class TestValidateCountries:
    def test_valid(self):
        assert validate_countries(["BRA", "IND"]) is None

    def test_empty_list(self):
        assert validate_countries([]) is not None

    def test_too_many(self):
        codes = [f"C{i:02}" for i in range(35)]
        assert validate_countries(codes) is not None

    def test_invalid_code_too_long(self):
        assert validate_countries(["TOOLONG"]) is not None

    def test_invalid_code_numeric(self):
        assert validate_countries(["123"]) is not None

    def test_single_country(self):
        assert validate_countries(["BRA"]) is None

    def test_max_countries(self):
        codes = [f"C{chr(65 + i // 26)}{chr(65 + i % 26)}" for i in range(30)]
        assert validate_countries(codes) is None


class TestValidateLimit:
    def test_valid(self):
        assert validate_limit(100) is None

    def test_zero(self):
        assert validate_limit(0) is not None

    def test_negative(self):
        assert validate_limit(-1) is not None

    def test_over_max(self):
        assert validate_limit(501) is not None

    def test_boundary_low(self):
        assert validate_limit(1) is None

    def test_boundary_high(self):
        assert validate_limit(500) is None

    def test_custom_max(self):
        assert validate_limit(50, max_limit=100) is None
        assert validate_limit(101, max_limit=100) is not None


class TestValidateQuery:
    def test_valid(self):
        assert validate_query("mortality") is None

    def test_too_short(self):
        assert validate_query("a") is not None

    def test_whitespace_only(self):
        assert validate_query("  ") is not None

    def test_min_length(self):
        assert validate_query("ab") is None


class TestValidateSex:
    def test_valid_values(self):
        for v in ["_T", "M", "F"]:
            assert validate_sex(v) is None

    def test_invalid(self):
        assert validate_sex("X") is not None

    def test_lowercase_invalid(self):
        assert validate_sex("m") is not None


class TestValidateResidence:
    def test_valid_values(self):
        for v in ["_T", "U", "R"]:
            assert validate_residence(v) is None

    def test_invalid(self):
        assert validate_residence("X") is not None


class TestValidateWealthQuintile:
    def test_valid_quintiles(self):
        for v in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
            assert validate_wealth_quintile(v) is None

    def test_valid_aggregates(self):
        for v in ["_T", "B20", "B40", "B60", "B80", "T20"]:
            assert validate_wealth_quintile(v) is None

    def test_invalid(self):
        assert validate_wealth_quintile("Q9") is not None
