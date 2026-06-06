"""Tests for v0.9.0 search_indicators ambiguity_flag + lookup_by_code.

Locks in the two new behaviors introduced in v0.9.0 to close the
v9 Arm B benchmark loop pathology (96.3% of stuck queries looped on
search_indicators because nothing in the response said STOP):

  1. search_indicators returns `ambiguity_flag`, `candidates`,
     `abstain_instruction` when the query matches a curated
     _AMBIGUOUS entry (child mortality, vaccination, child marriage).
     The `relevance` score is no longer dropped.

  2. lookup_by_code is a strict-canonical sibling to get_indicator_info.
     Accepts only exact UNICEF indicator codes; rejects natural-language
     descriptions with an abstain_instruction redirecting to
     search_indicators.

Pairs with:
  - tests/test_search.py — existing search behavior contracts
  - tests/test_issue_64_resolver_disambiguation.py — curated synonym +
    disambiguation_tip mechanism that v0.9.0 builds on
"""

from __future__ import annotations

import pytest

from unicefstats_mcp.server import lookup_by_code, search_indicators


class TestSearchIndicatorsAmbiguityFlag:
    """search_indicators must emit ambiguity_flag + structured candidates
    when the query matches a curated _AMBIGUOUS dict entry."""

    def test_curated_ambiguous_child_mortality_emits_flag(self):
        result = search_indicators("child mortality", limit=10)
        assert result.get("ambiguity_flag") is True
        candidates = result.get("candidates", [])
        # Four canonical age-bracket variants per _AMBIGUOUS["child mortality"]
        assert len(candidates) == 4
        codes = {c["code"] for c in candidates}
        assert codes == {"CME_MRM0", "CME_MRY0", "CME_MRY0T4", "CME_MRY1T4"}
        for c in candidates:
            assert "name" in c and c["name"]
        assert "STOP" in result.get("abstain_instruction", "")

    def test_curated_ambiguous_vaccination_emits_flag(self):
        result = search_indicators("vaccination coverage", limit=10)
        assert result.get("ambiguity_flag") is True
        codes = {c["code"] for c in result.get("candidates", [])}
        # Five vaccine codes per _AMBIGUOUS["vaccination coverage"]
        assert {"IM_BCG", "IM_DTP1", "IM_DTP3", "IM_MCV1", "IM_MCV2"} <= codes

    def test_curated_ambiguous_child_marriage_emits_flag(self):
        """v1.0.0 realigned the curated _AMBIGUOUS['child marriage'] codes
        against the live unicefdata YAML. PT_F_18-19_MRD and PT_F_15-49_MRD_18
        were stale; the actual canonical family is PT_F_15-19_MRD (currently
        married, ages 15-19) + PT_F_20-24_MRD_U15 (married before 15, women
        20-24) + PT_F_20-24_MRD_U18 (married before 18, women 20-24 — SDG
        5.3.1 headline)."""
        result = search_indicators("child marriage", limit=10)
        assert result.get("ambiguity_flag") is True
        codes = {c["code"] for c in result.get("candidates", [])}
        assert {"PT_F_15-19_MRD", "PT_F_20-24_MRD_U15", "PT_F_20-24_MRD_U18"} <= codes

    def test_unambiguous_synonym_does_not_emit_flag(self):
        """'stunting' resolves via _SYNONYMS to NT_ANT_HAZ_NE2 — no flag."""
        result = search_indicators("stunting", limit=10)
        assert result.get("ambiguity_flag", False) is False
        assert "candidates" not in result

    # NOTE: a previous v0.9.0 test asserted that 'breastfeeding' should
    # not emit the flag (it's not in _AMBIGUOUS). v1.0.0 removed that
    # test because the heuristic correctly catches it as a real novel
    # ambiguity — 'breastfeeding' alone surfaces 5 distinct sub-indicators
    # (early initiation, exclusive, continued 12-15/12-23/20-23 months)
    # all at the same relevance, none canonical for the bare keyword.
    # See TestRelevanceBasedHeuristic for the v1.0.0 heuristic contract.

    def test_relevance_score_preserved_in_output(self):
        """v0.9.0: relevance is no longer dropped from results."""
        result = search_indicators("mortality", limit=5)
        assert result.get("status") != "error"
        assert len(result["results"]) > 0
        for r in result["results"]:
            assert "relevance" in r
            assert isinstance(r["relevance"], int)
            assert r["relevance"] > 0


class TestRelevanceBasedHeuristic:
    """v1.0.0 novel-ambiguity heuristic: when the resolver gives up
    ('unknown' status) AND multiple search results have similar
    relevance scores AND no result hits the canonical threshold,
    set ambiguity_flag with ambiguity_source='heuristic'.

    Empirical motivation: the v9 Arm B run observed 130 stuck Sonnet
    queries that called search_indicators 14.7 times on average for
    indicator families like ECD_CHLD_LMPSL (developmentally on track),
    where multiple variants — _MERGE, _PRXY, _NEW — surface at similar
    relevance and no canonical winner exists for the natural-language
    description."""

    def test_novel_ambiguity_fires_heuristic_flag(self):
        """The 'developmentally on track' family (ECD_CHLD_LMPSL +
        variants) is the empirical pathology — heuristic must catch it.

        Depends on the active unicefdata registry vintage having the
        _MERGE / _PRXY / _NEW siblings of ECD_CHLD_LMPSL. Pip on
        Python 3.12 has been observed to resolve a unicefdata release
        whose YAML drops the _MERGE / _NEW siblings, leaving only 2
        non-derived results — below MIN_SIMILAR_CANDIDATES (3). When
        that registry vintage is active the precondition for this
        contract simply isn't present in the data, so skip rather
        than fail."""
        result = search_indicators("developmentally on track", limit=10)
        non_derived = [
            r for r in result.get("results", []) if not r["code"].startswith("TRGT_")
        ]
        if len(non_derived) < 3:
            pytest.skip(
                f"Registry vintage exposes only {len(non_derived)} non-derived "
                "ECD_CHLD_LMPSL variants; heuristic precondition cannot hold."
            )

        # v1.5.0 — the Tier 1 single-dataflow guard suppresses heuristic
        # ambiguity_flag when every candidate shares one primary dataflow.
        # If the ECD_CHLD_LMPSL family is single-dataflow, the v1.5.0
        # contract is "guard suppresses", not "heuristic fires" — skip
        # rather than fail in that case.
        from unicefstats_mcp import dimensions as _dims

        non_derived_dataflows = {
            _dims.primary_dataflow(r["code"]) for r in non_derived[:5]
        }
        non_derived_dataflows.discard(None)
        if len(non_derived_dataflows) <= 1:
            pytest.skip(
                f"v1.5.0 single-dataflow guard suppresses heuristic on this "
                f"family (shared dataflow={non_derived_dataflows!r})."
            )

        assert result.get("ambiguity_flag") is True
        assert result.get("ambiguity_source") == "heuristic"
        candidates = result.get("candidates", [])
        assert len(candidates) >= 3
        # The candidates should be the similar-relevance subset of results
        for c in candidates:
            assert "code" in c and "name" in c

    def test_curated_path_takes_priority_over_heuristic(self):
        """Curated _AMBIGUOUS detection runs before the heuristic; when
        both COULD fire, curated wins. ambiguity_source must reflect that."""
        result = search_indicators("child mortality", limit=10)
        assert result.get("ambiguity_flag") is True
        assert result.get("ambiguity_source") == "curated"

    def test_canonical_code_match_does_not_fire_heuristic(self):
        """Top relevance >= 90 (exact code match) means a canonical
        answer exists; heuristic must NOT flag."""
        result = search_indicators("CME_MRY0T4", limit=10)
        assert result.get("ambiguity_flag", False) is False

    def test_resolver_synonym_match_does_not_fire_heuristic(self):
        """Synonym matches are confident; heuristic must defer to the
        resolver's canonical pick."""
        result = search_indicators("stunting", limit=10)
        assert result.get("ambiguity_flag", False) is False

    def test_few_similar_candidates_does_not_fire(self):
        """Heuristic requires >=3 candidates within the similarity
        window — 1 or 2 candidates is treated as the model finding its
        answer quickly, not as ambiguity."""
        # 'bcg vaccination' is a curated synonym for IM_BCG — would
        # resolve via synonym_match, no heuristic.
        result = search_indicators("bcg coverage", limit=10)
        # Should NOT fire the heuristic (resolved via synonym)
        if result.get("ambiguity_source") == "heuristic":
            pytest.fail(
                "Expected non-heuristic resolution for curated synonym 'bcg coverage'; "
                f"got ambiguity_source={result.get('ambiguity_source')}"
            )


class TestLookupByCodeStrictCanonical:
    """lookup_by_code accepts only exact UNICEF codes; everything else
    returns abstain_instruction without falling back to search."""

    def test_valid_code_returns_canonical_info(self):
        result = lookup_by_code("CME_MRY0T4")
        assert result.get("status") == "ok"
        assert result["code"] == "CME_MRY0T4"
        assert "Under-five" in result["name"]
        assert result.get("ambiguity_flag") is False
        assert "sdmx_api" in result
        assert "disaggregation_filters" in result

    def test_natural_language_input_rejected(self):
        """'child mortality' is words, not a code — must be rejected
        with an abstain_instruction redirecting to search_indicators."""
        result = lookup_by_code("child mortality")
        assert result.get("status") == "error"
        assert result.get("ambiguity_flag") is False
        instruction = result.get("abstain_instruction", "")
        assert "search_indicators" in instruction
        assert "STOP" in instruction
        # The resolver should have flagged this as ambiguous
        assert result.get("resolver_status") == "ambiguous"

    def test_curated_synonym_input_rejected(self):
        """'stunting' is a curated synonym, not a code — strict tool
        must redirect to search_indicators rather than silently
        resolving (which would defeat the two-tool design)."""
        result = lookup_by_code("stunting")
        assert result.get("status") == "error"
        assert result.get("resolver_status") == "synonym_match"
        assert "search_indicators" in result.get("abstain_instruction", "")

    def test_unknown_code_rejected_with_abstain(self):
        """Fabricated codes must be rejected — and the model must NOT
        be told to retry search_indicators with the same fake code."""
        result = lookup_by_code("FAKE_CODE_123")
        assert result.get("status") == "error"
        instruction = result.get("abstain_instruction", "")
        assert "STOP" in instruction
        # Must instruct NOT to retry with variants
        assert "Do NOT retry" in instruction or "do not retry" in instruction.lower()

    def test_empty_input_rejected_by_validator(self):
        result = lookup_by_code("")
        assert result.get("status") == "error"

    @pytest.mark.parametrize(
        "code,expected_name_fragment",
        [
            ("CME_MRY0T4", "Under-five mortality"),
            ("CME_MRM0", "Neonatal mortality"),
            ("IM_DTP3", "DTP"),
            ("NT_BW_LBW", "Low birth"),
        ],
    )
    def test_known_canonical_codes_resolve(self, code, expected_name_fragment):
        result = lookup_by_code(code)
        assert result.get("status") == "ok", f"Expected ok for {code}, got {result}"
        assert expected_name_fragment.lower() in result["name"].lower()


class TestSelfDescribingToolBoundary:
    """The two tools must give the LLM a clean self-describing choice:
    words → search_indicators, codes → lookup_by_code. Test the
    expected behavior at the boundary so future refactors don't blur
    the line."""

    def test_search_indicators_accepts_words(self):
        r = search_indicators("mortality", limit=3)
        assert r.get("status") != "error"

    def test_lookup_by_code_rejects_words(self):
        r = lookup_by_code("mortality")
        assert r.get("status") == "error"

    def test_search_indicators_accepts_code_substring(self):
        """search_indicators historically supported code-substring matches.
        Keep that behavior — it lets users discover full code via partial."""
        r = search_indicators("CME_MR", limit=10)
        assert r.get("status") != "error"
        assert any("CME_MR" in res["code"] for res in r["results"])

    def test_lookup_by_code_rejects_substring(self):
        """Substrings are not exact codes — must be rejected."""
        r = lookup_by_code("CME_MR")
        assert r.get("status") == "error"
