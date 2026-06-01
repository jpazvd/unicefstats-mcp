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


class TestV120YamlGroundedDisaggregations:
    """v1.2.0 Commit 3 — disaggregation_filters now grounded in the
    unicefdata-shipped YAML for the indicator's primary dataflow, NOT the
    v1.1.x hardcoded {sex, wealth_quintile, residence} triple.

    These tests pin the gate-3 invariants and the v1.1.1 forensic finding
    (CME_MRY0T4 must NOT advertise AGE because it's age-restricted by
    construction).
    """

    @patch("unicefstats_mcp.server._get_ud")
    def test_hva_disaggregation_filters_includes_age(self, mock_ud):
        ud = MagicMock()
        ud.get_indicator_info.return_value = {
            "name": "Estimated HIV incidence rate",
            "description": "...",
            "category": "HIV_AIDS",
        }
        mock_ud.return_value = ud

        from unicefstats_mcp.server import get_indicator_info as gii
        result = gii(code="HVA_EPI_INF_RT")
        assert "error" not in result
        # HIV_AIDS dataflow has AGE per HIV_AIDS.yaml
        assert "AGE" in result["disaggregation_filters"]
        assert "SEX" in result["disaggregation_filters"]
        assert result["dimension_source"] == "yaml_grounded"

    @patch("unicefstats_mcp.server._get_ud")
    def test_u5mr_disaggregation_filters_excludes_age(self, mock_ud):
        """Pins the v1.1.1 forensic finding: CME_MRY0T4 (U5MR) is
        age-restricted by code construction and must NOT advertise AGE
        in its disaggregation_filters. The v1.1.x hardcoded triple
        falsely advertised AGE-equivalent through wealth/residence.
        """
        ud = MagicMock()
        ud.get_indicator_info.return_value = {
            "name": "Under-five mortality rate",
            "description": "...",
            "category": "CME",
        }
        mock_ud.return_value = ud

        from unicefstats_mcp.server import get_indicator_info as gii
        result = gii(code="CME_MRY0T4")
        assert "error" not in result
        assert "AGE" not in result["disaggregation_filters"], (
            "CME_MRY0T4 must NOT advertise AGE — pins v1.1.1 forensic finding"
        )

    @patch("unicefstats_mcp.server._get_ud")
    def test_variants_includes_same_family_siblings(self, mock_ud):
        ud = MagicMock()
        ud.get_indicator_info.return_value = {
            "name": "Under-five mortality rate",
            "description": "...",
            "category": "CME",
        }
        mock_ud.return_value = ud

        from unicefstats_mcp.server import get_indicator_info as gii
        result = gii(code="CME_MRY0T4")
        variants = result.get("variants", [])
        # Same-family CME siblings must be present (limited to 10).
        # CME_MRM0 (neonatal), CME_MRY0 (infant), CME_MRY1T4 — at least one
        # of these should appear.
        assert len(variants) > 0
        cme_siblings = [v for v in variants if v.startswith("CME_")]
        assert len(cme_siblings) > 0
        # The indicator itself must NOT appear in its own variants list.
        assert "CME_MRY0T4" not in variants

    @patch("unicefstats_mcp.server._get_ud")
    def test_tier2_returns_fallback_envelope(self, mock_ud):
        ud = MagicMock()
        ud.get_indicator_info.return_value = {
            "name": "Child mortality",
            "description": "Child mortality",
            "category": "",
        }
        mock_ud.return_value = ud

        from unicefstats_mcp.server import get_indicator_info as gii
        result = gii(code="CME")
        assert "error" not in result
        assert result.get("tier") == 2
        assert result.get("dimension_source") == "no_dataflow_metadata"
        assert (
            result["disaggregation_filters"].get("_source") == "fallback_unknown"
        )
        # No siblings for tier-2 family codes (no parent metadata).
        assert result.get("variants") == []

    @patch("unicefstats_mcp.server._get_ud")
    def test_dataflow_uses_primary_not_global(self, mock_ud):
        """v1.1.x called get_dataflow_for_indicator which returned
        GLOBAL_DATAFLOW for HVA_EPI_INF_RT. v1.2.0 surfaces the actual
        primary dataflow (HIV_AIDS) so the LLM sees the real routing.
        """
        ud = MagicMock()
        ud.get_indicator_info.return_value = {
            "name": "Estimated HIV incidence rate",
            "description": "...",
            "category": "HIV_AIDS",
        }
        # Even if v1.1.x's get_dataflow_for_indicator returns GLOBAL,
        # the v1.2.0 path doesn't consult it — it reads dimensions.primary_dataflow.
        ud.get_dataflow_for_indicator.return_value = "GLOBAL_DATAFLOW"
        mock_ud.return_value = ud

        from unicefstats_mcp.server import get_indicator_info as gii
        result = gii(code="HVA_EPI_INF_RT")
        assert result["dataflow"] == "HIV_AIDS"
        assert result["dataflow_used"] == "HIV_AIDS"
        # The SDMX URL must point at HIV_AIDS not GLOBAL_DATAFLOW.
        assert "HIV_AIDS" in result["sdmx_api"]
        assert "GLOBAL_DATAFLOW" not in result["sdmx_api"]


class TestV120GetIndicatorInfoEquivLookupByCode:
    """Pins the gate-3 invariant: get_indicator_info ≡ lookup_by_code for
    the same code on disaggregation_filters (the v1.1.2 copy-paste hazard
    is closed by routing both through _build_indicator_envelope).
    """

    @patch("unicefstats_mcp.server._get_ud")
    def test_both_tools_return_identical_disaggregation_filters(self, mock_ud):
        ud = MagicMock()
        ud.get_indicator_info.return_value = {
            "name": "Estimated HIV incidence rate",
            "description": "...",
            "category": "HIV_AIDS",
        }
        mock_ud.return_value = ud

        from unicefstats_mcp.server import (
            get_indicator_info as gii,
        )
        from unicefstats_mcp.server import (
            lookup_by_code as lbc,
        )
        r_gii = gii(code="HVA_EPI_INF_RT")
        r_lbc = lbc(code="HVA_EPI_INF_RT")
        assert r_gii["disaggregation_filters"] == r_lbc["disaggregation_filters"]
        # And the other shared envelope fields stay in sync.
        assert r_gii["dataflow"] == r_lbc["dataflow"]
        assert r_gii["variants"] == r_lbc["variants"]
        assert r_gii["tier"] == r_lbc["tier"]
        assert r_gii["dimension_source"] == r_lbc["dimension_source"]


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
