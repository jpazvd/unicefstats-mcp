"""Regression tests for issue #64.

Indicator resolver picks wrong variant for 3 prompts:
  - MNCH_BIRTH18  (Early childbearing — births before age 18)
  - CME_MRY1T4    (Child mortality 1-4)
  - CME_MRY0T4    (Under-five mortality)

The failure had two parts (see issue #64 thread + empirical probe):

1. `indicator_resolver.resolve_indicator` returned `unknown` for several
   common phrasings of MNCH_BIRTH18 and CME_MRY1T4 (only the exact
   canonical name resolved). Without a resolver hit, the model
   typically went through `search_indicators`, which had its own bugs:

2. `search_indicators` (a) surfaced tier-2 category codes like `CME`
   that aren't valid for `get_data`, and (b) ranked derived metrics
   like `CME_ARR_U5MR` (Annual Rate of Reduction) ABOVE the canonical
   `CME_MRY0T4` because the derived metric's code contained the user's
   "U5MR" substring at score 90 while the canonical was only reachable
   via the score-80 name match.

These tests lock in:

  - resolver returns canonical codes for the common natural-language
    phrasings of the 3 problem indicators
  - search_indicators filters out tier-2 codes (no `parent` field)
  - search_indicators applies a -35 penalty to derived metrics, so the
    canonical wins on a generic query like "U5MR"
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.conftest import MOCK_INDICATORS_ISSUE_64
from unicefstats_mcp.indicator_resolver import (
    get_disambiguation_tip,
    resolve_indicator,
)
from unicefstats_mcp.server import _is_derived_metric, search_indicators


class TestResolverSynonymsForBirth18:
    """resolve_indicator must map common 'births before age 18' phrasings
    to MNCH_BIRTH18, not to the adolescent-fertility variant MNCH_ABR.
    """

    @pytest.mark.parametrize("phrasing", [
        "early childbearing",
        "Early childbearing",
        "births before age 18",
        "Births before age 18",
        "births to women under 18",
        "Births to women under 18",
        "births under 18",
        "births under age 18",
        "first birth before age 18",
    ])
    def test_resolves_to_mnch_birth18(self, phrasing):
        r = resolve_indicator(phrasing)
        assert r.status == "synonym_match", (
            f"phrasing {phrasing!r} resolved as {r.status!r}, expected synonym_match"
        )
        assert r.code == "MNCH_BIRTH18"


class TestResolverSynonymsForChildMortality1To4:
    """resolve_indicator must map 'child mortality 1-4' phrasings to
    CME_MRY1T4, not silently fall through to CME_MRY0T4 (under-five)
    via downstream substring-match in search_indicators.
    """

    @pytest.mark.parametrize("phrasing", [
        "child mortality 1-4",
        "Child mortality 1-4",
        "child mortality rate 1-4",
        "Child mortality rate 1-4",
        "child mortality rate aged 1-4 years",
        "Child mortality rate aged 1-4 years",
        "mortality rate aged 1-4",
        "mortality rate 1-4",
    ])
    def test_resolves_to_cme_mry1t4(self, phrasing):
        r = resolve_indicator(phrasing)
        assert r.status in ("synonym_match", "name_index_hit"), (
            f"phrasing {phrasing!r} resolved as {r.status!r}"
        )
        assert r.code == "CME_MRY1T4"


class TestSearchFiltersTier2Categories:
    """search_indicators must NOT surface tier-2 category codes.

    `CME` in the registry is the parent code for all mortality
    indicators; it shows up in `_get_indicators()` because the
    upstream `unicefdata` codelist returns the full code tree. But
    `get_data(indicator="CME")` would fail — `CME` is an aggregate,
    not a data-bearing indicator. The tier-2 filter is the
    distinguishing feature: tier-1 indicators carry a `parent` key
    pointing to their category; tier-2 categories don't.
    """

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS_ISSUE_64)
    def test_cme_category_not_in_results(self, _mock):
        result = search_indicators(query="child mortality", limit=10)
        assert "error" not in result, result
        codes = [r["code"] for r in result["results"]]
        assert "CME" not in codes, (
            "tier-2 category 'CME' surfaced in search_indicators output — "
            "would route get_data() to an aggregate code"
        )

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS_ISSUE_64)
    def test_cme_substring_match_excludes_category(self, _mock):
        # Even when querying directly for "CME" (the category name),
        # the tier-2 filter should keep it out. The tier-1 CME_MR*
        # indicators still surface via code-substring matches.
        result = search_indicators(query="CME", limit=10)
        codes = [r["code"] for r in result["results"]]
        assert "CME" not in codes
        assert "CME_MRY0T4" in codes  # tier-1 still surfaces


class TestSearchDerivedMetricPenalty:
    """search_indicators must rank canonical indicators above derived
    metrics (national targets, annual rates of reduction, projected
    variants) when the user's query is generic.
    """

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS_ISSUE_64)
    def test_u5mr_picks_canonical_not_arr(self, _mock):
        # "U5MR" appears as a substring in BOTH:
        #   - CME_ARR_U5MR (Annual Rate of Reduction — derived metric)
        #   - the synonym expansion of "U5MR" → "under-five mortality"
        # Without the derived-metric penalty, CME_ARR_U5MR scored 90
        # (code substring) and beat the canonical CME_MRY0T4 (56,
        # token match). With the -35 penalty CME_ARR_U5MR drops to 55
        # and CME_MRY0T4 wins.
        result = search_indicators(query="U5MR", limit=5)
        assert "error" not in result
        codes = [r["code"] for r in result["results"]]
        assert codes[0] == "CME_MRY0T4", (
            f"U5MR query top result was {codes[0]!r}, expected CME_MRY0T4. "
            f"All results: {codes}"
        )

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS_ISSUE_64)
    def test_target_indicator_ranks_below_canonical(self, _mock):
        # National targets (TRGT_*) carry the same name tokens as their
        # canonical indicator. A query for "under-five mortality rate"
        # should land on CME_MRY0T4, not TRGT_2030_CME_MRY0T4.
        result = search_indicators(query="under-five mortality rate", limit=5)
        codes = [r["code"] for r in result["results"]]
        assert codes[0] == "CME_MRY0T4", (
            f"top result was {codes[0]!r}, expected CME_MRY0T4. All: {codes}"
        )


class TestDisambiguationTip:
    """get_disambiguation_tip returns curated guidance for known-ambiguous
    queries (data360-mcp anti-hallucination-template pattern). Closes the
    semantic half of issue #64 — "child mortality" is genuinely ambiguous;
    we don't hardwire it to U5MR, we educate the model.
    """

    @pytest.mark.parametrize("query, anchor", [
        ("child mortality", "CME_MRY0T4"),
        ("child mortality rate", "CME_MRY0T4"),
        ("Child Mortality", "CME_MRY0T4"),
        ("what is the child mortality rate in Brazil", "CME_MRY0T4"),
        ("mortality rate", "CME_MRY0T4"),
        ("vaccination coverage", "DTP3"),
        ("vaccination", "DTP3"),
        ("immunization coverage", "DTP3"),
        # v1.0.0: realigned to PT_F_20-24_MRD_U18 (live code; was
        # PT_F_15-49_MRD_18 which never existed in the YAML).
        ("child marriage", "PT_F_20-24_MRD_U18"),
    ])
    def test_returns_canonical_recommendation(self, query, anchor):
        tip = get_disambiguation_tip(query)
        assert tip is not None, f"no tip for {query!r}"
        assert anchor in tip, (
            f"tip for {query!r} missing canonical indicator anchor {anchor!r}: {tip}"
        )

    @pytest.mark.parametrize("query", [
        "under-five mortality rate",   # already specific, no ambiguity
        "stunting prevalence",
        "primary completion rate",
        "early childbearing",
        "literacy rate 15-24",
        "",
        "   ",
    ])
    def test_returns_none_for_unambiguous_or_empty(self, query):
        assert get_disambiguation_tip(query) is None

    def test_returns_none_for_non_string(self):
        assert get_disambiguation_tip(None) is None  # type: ignore[arg-type]
        assert get_disambiguation_tip(123) is None  # type: ignore[arg-type]

    def test_longest_key_wins(self):
        # "child mortality rate" should match its specific tip, not the
        # shorter "child mortality" tip — the longer key is more
        # informative.
        tip_rate = get_disambiguation_tip("child mortality rate")
        tip_general = get_disambiguation_tip("child mortality")
        assert tip_rate is not None
        assert tip_general is not None
        # The rate-specific tip is shorter (fewer age brackets listed)
        # than the general-mortality tip.
        assert tip_rate != tip_general
        assert "1-4" in tip_rate  # mentions 1-4 specifically
        assert "neonatal" in tip_general.lower()  # general lists all 4 brackets

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS_ISSUE_64)
    def test_search_indicators_attaches_disambiguation_tip(self, _mock):
        result = search_indicators(query="child mortality", limit=10)
        assert "error" not in result
        assert "disambiguation_tip" in result, (
            "search_indicators must surface the tip when the query is ambiguous"
        )
        assert "CME_MRY0T4" in result["disambiguation_tip"]
        assert "SDG 3.2" in result["disambiguation_tip"]

    @patch("unicefstats_mcp.server._get_indicators", return_value=MOCK_INDICATORS_ISSUE_64)
    def test_search_indicators_omits_tip_for_unambiguous_query(self, _mock):
        # "under-five mortality rate" is already specific — no tip needed.
        result = search_indicators(query="under-five mortality rate", limit=10)
        assert "error" not in result
        assert "disambiguation_tip" not in result, (
            "tip surfaced on an unambiguous query — that's noise"
        )


class TestIsDerivedMetric:
    """Direct tests of the _is_derived_metric helper. Locks in the
    code/name patterns that count as 'derived' and the patterns that
    do not.
    """

    @pytest.mark.parametrize("code,name", [
        ("TRGT_2030_CME_MRY0T4", "National target (Year 2030) for Under-five mortality rate"),
        ("CME_ARR_U5MR", "Annual Rate of Reduction in Under-five mortality rate"),
        ("CME_ARR_U5MR", "Tasa anual de reducción de la tasa de mortalidad"),
        ("TRGT_CME", "Child mortality National Targets"),
        ("PT_F_20-24_MRD_U15_PRJ", "Projected percentage of women..."),
    ])
    def test_recognises_derived(self, code, name):
        assert _is_derived_metric(code, name), (
            f"{code!r} / {name!r} should be classified as derived"
        )

    @pytest.mark.parametrize("code,name", [
        ("CME_MRY0T4", "Under-five mortality rate"),
        ("CME_MRY1T4", "Child mortality rate (aged 1-4 years)"),
        ("MNCH_BIRTH18", "Early childbearing - percentage of women..."),
        ("NT_ANT_HAZ_NE2", "Height-for-age <-2 SD (stunting)"),
    ])
    def test_canonical_not_classified_as_derived(self, code, name):
        assert not _is_derived_metric(code, name), (
            f"{code!r} should NOT be classified as derived"
        )
