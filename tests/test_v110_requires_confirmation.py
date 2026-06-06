"""v1.1.0: requires_confirmation + recommended + assistant_guidance + next_step.

Pattern A + B + D — see internal/v1.1.0_pattern_review.md and
internal/v1.1.0_design/.
"""
import pytest

from unicefstats_mcp.server import search_indicators


class TestRequiresConfirmationTrue:
    def test_curated_ambiguous_with_curated_override_picks_canonical(self):
        """v1.1.1 contract: when a query triggers resolver _AMBIGUOUS
        OR the heuristic ambiguity flag AND ALSO matches a curated
        CURATED_PREFERRED entry, the reorder in commit ddc3fcc makes
        the curated pick win — requires_confirmation goes False, the
        ambiguity_flag stays set in the payload for downstream
        inspection, recommended carries the curated canonical pick.

        Both "child mortality" and "school attendance" hit this path:
        resolver _AMBIGUOUS would flag them, but CURATED_PREFERRED
        holds a deliberate default (CME family canonical pick / ED_ANAR_L1).

        v1.1.0's original assertion that the SAME query produces
        requires_confirmation=True is INTENTIONALLY broken by v1.1.1
        — that was the IM_DTP3 forensic motivation (the curated
        catalog must be authoritative when it matches).
        """
        result = search_indicators("child mortality", limit=5)
        assert result["status"] == "ok"
        # Curated catalog matched; ambiguity_flag remains in payload
        # for downstream callers but requires_confirmation is False.
        assert result["requires_confirmation"] is False
        rec = result.get("recommended") or {}
        assert rec.get("code"), "Expected a curated `recommended.code`"
        assert "assistant_guidance" in result
        # next_step is set when curated picks
        assert result.get("next_step", "").startswith("get_indicator_info")

    def test_heuristic_ambiguous_sets_flag_true(self):
        """Novel ambiguity (heuristic path) -> requires_confirmation=True.

        'developmentally on track' is the empirical pathology from the
        v9 Arm B run — the ECD_CHLD_LMPSL family typically has _MERGE
        / _PRXY / _NEW variants all at similar relevance, so the
        resolver gives up (status='unknown') and the heuristic fires
        with ambiguity_source='heuristic'.

        Pip on Python 3.12 has been observed to resolve a unicefdata
        release whose YAML drops the _MERGE / _NEW siblings, leaving
        only 2 non-derived results — below MIN_SIMILAR_CANDIDATES (3).
        When that registry vintage is active the precondition for
        this contract is not in the data, so skip cleanly rather than
        fail (the contract holds; the input doesn't satisfy it).
        """
        result = search_indicators("developmentally on track", limit=10)
        non_derived = [
            r for r in result.get("results", []) if not r["code"].startswith("TRGT_")
        ]
        if len(non_derived) < 3:
            pytest.skip(
                f"Registry vintage exposes only {len(non_derived)} non-derived "
                "ECD_CHLD_LMPSL variants; heuristic precondition cannot hold."
            )

        # v1.5.0 — Tier 1 single-dataflow guard suppresses heuristic
        # ambiguity_flag when every candidate shares one primary dataflow.
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
        assert result["requires_confirmation"] is True
        assert "assistant_guidance" in result
        assert len(result["assistant_guidance"]) < 200


class TestRequiresConfirmationFalse:
    def test_confident_match_sets_flag_false_with_recommended(self):
        """Exact-code query -> deterministic confident-match branch.

        Passing the canonical code as the query makes the top result
        score 90+ (exact-code substring match) and the gap to runner-up
        large enough to satisfy either branch of the threshold check.
        No conditionals: the branch MUST fire.
        """
        result = search_indicators("CME_MRY0T4", limit=5)
        assert result.get("ambiguity_flag", False) is False
        assert result["requires_confirmation"] is False
        assert result["recommended"]["code"] == "CME_MRY0T4"
        # category key always present (value may be empty for some
        # indicators whose metadata lacks a category label)
        assert "category" in result["recommended"]
        assert "why" in result["recommended"]
        assert result["next_step"] == "get_indicator_info(code='CME_MRY0T4')"

    def test_assistant_guidance_is_english_no_markdown(self):
        """Confident-match guidance string contract: <200 chars,
        no markdown, no backticks, no headers."""
        result = search_indicators("CME_MRY0T4", limit=5)
        assert result["requires_confirmation"] is False
        g = result["assistant_guidance"]
        assert "**" not in g and "##" not in g and "`" not in g
        assert len(g) < 200


class TestCuratedPreferred:
    """Pattern B: CURATED_PREFERRED entries surface as canonical picks
    even when the resolver gives up. Wired in commit bc4ce49.
    """

    def test_curated_preferred_pv_chld_hit(self):
        """PV_CHLD gap family ('child income poverty') -> Pattern B
        canonical pick (PV_CHLD_INCM_PL), no ambiguity, with next_step
        derived from the catalog entry."""
        result = search_indicators("child income poverty", limit=5)
        assert result.get("ambiguity_flag", False) is False
        assert result["requires_confirmation"] is False
        assert result["recommended"]["code"] == "PV_CHLD_INCM_PL"
        assert result["recommended"]["category"] == "POVERTY"
        assert "curated canonical pick" in result["recommended"]["why"]
        assert result["next_step"] == "get_indicator_info(code='PV_CHLD_INCM_PL')"
        assert "Curated match" in result["assistant_guidance"]


class TestBackwardCompat:
    def test_v100_response_shape_when_no_signal(self):
        """No-result query -> no new v1.1.0 fields in response."""
        result = search_indicators("xyzzy_no_match_query", limit=5)
        assert result["status"] in ("ok", "no_data")
        assert "requires_confirmation" not in result
        assert "recommended" not in result
        assert "assistant_guidance" not in result
        assert "next_step" not in result

    def test_relevance_still_in_results(self):
        """v0.9.0 contract preserved -- relevance still on each match."""
        result = search_indicators("stunting", limit=5)
        for r in result["results"]:
            assert "relevance" in r
            assert isinstance(r["relevance"], int)
