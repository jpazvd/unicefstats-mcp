"""v1.1.1: TRGT penalty + dimension-token boost scoring tests.

Pins the new scoring layers (commit 76868fd), the curated catalog
additions (00726d4 / d4127d2), and the decision-logic reorder
(ddc3fcc — curated lookup_preferred wins over heuristic ambiguity).

Tests operate against the LIVE unicefdata registry — no mocking — so
they also serve as a real-catalog smoke after any v1.1.x release.

See:
  - internal/v1.1.0_design/ambiguity_forensic.md (the C-1 IM_DTP3
    pathology these tests close)
  - internal/v1.1.0_design/v111_revised_design.json
"""
from __future__ import annotations

from unicefstats_mcp.curated import lookup_preferred
from unicefstats_mcp.server import search_indicators


def test_trgt_penalty_drops_target_codes_when_no_target_token():
    res = search_indicators(
        query="DTP3 vaccine coverage national programme", limit=10
    )
    results = res.get("results", [])
    assert results, "Expected non-empty results"
    trgt_top = next(
        (r for r in results if r["code"].startswith("TRGT_2030_IM_DTP3")), None
    )
    assert trgt_top is not None
    assert trgt_top["relevance"] <= 55, (
        f"TRGT_2030_IM_DTP3 relevance={trgt_top['relevance']} too high"
    )


def test_trgt_penalty_unmasked_when_target_token_present():
    """When the query carries a target token, TRGT_* codes still
    appear in results (the new -35 penalty is waived). Strict
    score-comparison across two different queries is unreliable
    because token-overlap differs by query — so we only assert
    presence, not relative ranking."""
    with_target = search_indicators(
        query="DTP3 national target 2030 goal", limit=10
    )
    trgt_codes = [
        r["code"] for r in with_target.get("results", [])
        if r["code"].startswith("TRGT_")
    ]
    assert trgt_codes, (
        "Expected at least one TRGT_* code in results when query "
        "explicitly seeks targets."
    )


def test_dtp3_synonym_query_uses_curated_pick():
    res = search_indicators(
        query="DTP3 vaccine coverage national programme", limit=10
    )
    rec = res.get("recommended") or {}
    assert rec.get("code") == "IM_DTP3"
    assert res.get("next_step") == "get_indicator_info(code='IM_DTP3')"
    assert res.get("requires_confirmation") is False


def test_curated_precedence_over_heuristic_ambiguity():
    res = search_indicators(
        query="DTP3 vaccine coverage national programme", limit=10
    )
    assert res.get("requires_confirmation") is False
    assert (res.get("recommended") or {}).get("code") == "IM_DTP3"


def test_lookup_preferred_rejects_short_substring_collisions():
    assert lookup_preferred("imrish") is None
    assert lookup_preferred("imr") is None
    assert lookup_preferred("DTP3 vaccine coverage")["code"] == "IM_DTP3"


def test_dim_token_no_inflate_unrelated_codes():
    res = search_indicators(query="urban planning literature", limit=10)
    results = res.get("results", [])
    if results:
        top_rel = results[0].get("relevance", 0)
        assert top_rel <= 70


def test_hva_consolidated_to_base_code():
    for q in (
        "HIV infection rate",
        "HIV children",
        "HIV 15-19",
        "HIV adolescents 15-19",
    ):
        entry = lookup_preferred(q)
        assert entry is not None, f"lookup_preferred({q!r}) -> None"
        assert entry["code"] == "HVA_EPI_INF_RT"
    hint = lookup_preferred("HIV 15-19")["dimension_hint"]
    assert "Y15T19" in hint, "expected the AGE=Y15T19 filter recipe"
    assert "age='Y15T19'" in hint, "expected the get_data filter syntax"


def test_backward_compat_neutral_query_unchanged():
    res = search_indicators(query="stunting", limit=5)
    assert res.get("ambiguity_flag") is not True
    top_codes = [r["code"] for r in res.get("results", [])[:5]]
    assert "NT_ANT_HAZ_NE2" in top_codes
