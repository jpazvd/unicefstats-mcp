"""v1.5.4 — Address Copilot review on PR #107.

Two issues flagged by Copilot on the v1.5.3 long-tail curated entries:

1. PT_F_PS-SX_V_PTNR_12MNTH had an `ever-partnered girls aged 15 to 19`
   synonym that, combined with the bidirectional substring matcher,
   would silently route 15-19-explicit queries to the 15-49 SDG 5.2.1
   default — directly contradicting the dimension_hint guidance that
   tells the LLM to use the 15-19 sibling when explicitly requested.

2. HVA_PED_LOST's dimension_hint said "all-cause estimate" — misleading
   because the indicator is AIDS-specific. The "all-cause" framing
   could lead the LLM to use the value as a general orphanhood estimate.

Both fixed in v1.5.4. Tests pin the new contracts.
"""

from __future__ import annotations

from unicefstats_mcp.curated import CURATED_PREFERRED, lookup_preferred


def test_15_19_query_does_not_route_to_15_49_default() -> None:
    """v1.5.4 — a query that explicitly asks for the 15-19 age band must
    NOT silently route to the PT_F_PS-SX_V_PTNR_12MNTH 15-49 default.
    The Copilot-flagged bug was a 'ever-partnered girls aged 15 to 19'
    synonym in the 15-49 entry that would substring-match such queries."""
    queries_explicit_15_19 = [
        "What was Proportion of ever-partnered girls aged 15 to 19 subjected "
        "to physical and/or sexual violence in the previous 12 months for X in 2020?",
        "Percentage of ever-partnered girls aged 15 to 19 years subjected to "
        "intimate partner violence in the past 12 months",
    ]
    for q in queries_explicit_15_19:
        result = lookup_preferred(q)
        # The 15-19 sibling indicator is not yet in CURATED_PREFERRED, so
        # either lookup_preferred returns None (resolver-layer handles it)
        # or it returns a DIFFERENT code that is NOT the 15-49 default.
        assert result is None or result["code"] != "PT_F_PS-SX_V_PTNR_12MNTH", (
            "v1.5.4 regression: 15-19-explicit query routed to "
            "PT_F_PS-SX_V_PTNR_12MNTH (15-49 default) — Copilot bug "
            "on PR #107 reintroduced"
        )


def test_15_19_synonym_not_in_alt_synonyms_list() -> None:
    """Belt-and-braces: confirm the offending synonym string is gone."""
    entry = CURATED_PREFERRED["PT_F_PS-SX_V_PTNR_12MNTH"]
    syns = entry["alt_synonyms"]
    assert "ever-partnered girls aged 15 to 19" not in syns, (
        "v1.5.4: 'ever-partnered girls aged 15 to 19' must NOT appear in "
        "PT_F_PS-SX_V_PTNR_12MNTH.alt_synonyms — that synonym routes "
        "15-19-explicit queries to the 15-49 SDG 5.2.1 default"
    )


def test_15_49_default_query_still_resolves() -> None:
    """v1.5.4 must not break the actual benchmark prompt routing."""
    q = (
        "What was Proportion of ever-partnered women and girls aged 15-49 "
        "years subjected to physical and/or sexual violence by a current or "
        "former intimate partner for X in 2020?"
    )
    result = lookup_preferred(q)
    assert result is not None
    assert result["code"] == "PT_F_PS-SX_V_PTNR_12MNTH"


def test_hva_ped_lost_dimension_hint_specifies_aids_caused() -> None:
    """v1.5.4 — HVA_PED_LOST.dimension_hint must not say 'all-cause'
    (misleading: the indicator is AIDS-specific by definition).
    Must explicitly mention AIDS or 'combined' to clarify the scope
    is AIDS-caused orphanhood, with the combined maternal+paternal
    cut as the default within the AIDS-orphaned series."""
    entry = CURATED_PREFERRED["HVA_PED_LOST"]
    hint = entry["dimension_hint"]
    assert "all-cause" not in hint.lower(), (
        f"v1.5.4: HVA_PED_LOST.dimension_hint must not use 'all-cause' "
        f"language — the indicator is AIDS-specific by definition. Got: {hint!r}"
    )
    # Must clarify the scope is AIDS-caused
    assert "AIDS" in hint, (
        f"v1.5.4: HVA_PED_LOST.dimension_hint must mention 'AIDS' to "
        f"clarify the scope. Got: {hint!r}"
    )
    # And clarify that the default is the combined maternal+paternal cut
    assert "combined" in hint.lower() or "maternal+paternal" in hint, (
        f"v1.5.4: HVA_PED_LOST.dimension_hint should clarify the default "
        f"is the combined maternal+paternal estimate (vs the separate "
        f"breakdowns). Got: {hint!r}"
    )
