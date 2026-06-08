"""v1.5.2 — Curated defaults to custodian-modelled series + other-version warnings.

The v1.5.1 joint-failure forensic (435 cells where both v124 baseline and
v151 returned EQA < 0.1) showed 272 cells (62.5%) abstained on the
`ambiguity_flag` between modelled-vs-raw indicator siblings. The single
biggest cluster was the education completion-rate (ED_CR_L1/L2/L3) and
out-of-school-rate (ED_ROFST_L1/L2/L3) families — UNESCO/UIS (the SDG 4
custodian agency) publishes both administrative and modelled estimates,
and the LLM had no signal to prefer one over the other.

v1.5.2 adds `CURATED_PREFERRED` entries defaulting to the UIS-modelled
series (per custodian convention) with a `dimension_hint` warning listing
the other variants in the data warehouse. Same pattern applied to JMP
water/sanitation headline indicators.

Empirical projection on the 1484-cell sample (search-layer-only diff):
  +6.5pp full-sample EQA lift, net of 14-cell regression on ED_CR_L1
  where the benchmark sample's ground truth is the raw administrative
  series — accepted as the cost of the policy choice.
"""

from __future__ import annotations

import pytest

from unicefstats_mcp.curated import CURATED_PREFERRED, lookup_preferred

# ---------------------------------------------------------------------------
# Education × UIS modelled defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected_code",
    [
        # Completion rate family — all default to UIS modelled
        ("primary completion rate", "ED_CR_L1_UIS_MOD"),
        ("primary school completion rate", "ED_CR_L1_UIS_MOD"),
        ("Completion rate for children of primary school age", "ED_CR_L1_UIS_MOD"),
        ("lower secondary completion rate", "ED_CR_L2_UIS_MOD"),
        (
            "Completion rate for adolescents of lower secondary school age",
            "ED_CR_L2_UIS_MOD",
        ),
        ("upper secondary completion rate", "ED_CR_L3_UIS_MOD"),
        (
            "Completion rate for youth of upper secondary education school age",
            "ED_CR_L3_UIS_MOD",
        ),
        # Out-of-school rate family — all default to UIS modelled
        ("out-of-school rate primary", "ED_ROFST_L1_UIS_MOD"),
        (
            "Out-of-school rate for children of primary school age",
            "ED_ROFST_L1_UIS_MOD",
        ),
        ("out-of-school rate lower secondary", "ED_ROFST_L2_UIS_MOD"),
        (
            "Out-of-school rate for adolescents of lower secondary school age",
            "ED_ROFST_L2_UIS_MOD",
        ),
        ("out-of-school rate upper secondary", "ED_ROFST_L3_UIS_MOD"),
        (
            "Out-of-school rate for youth of upper secondary school age",
            "ED_ROFST_L3_UIS_MOD",
        ),
    ],
)
def test_education_queries_default_to_uis_modelled(
    query: str, expected_code: str
) -> None:
    """v1.5.2 contract: education completion/ROFST queries default to the
    UIS-modelled series (the SDG 4.1.x custodian-agency convention)."""
    result = lookup_preferred(query)
    assert result is not None, f"v1.5.2 regression: {query!r} returned None"
    assert result["code"] == expected_code, (
        f"v1.5.2 regression: {query!r} should default to {expected_code} "
        f"(UIS custodian convention); got {result['code']}"
    )


# ---------------------------------------------------------------------------
# WASH JMP headline defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected_code",
    [
        # Realistic benchmark-style prompts (long enough that the
        # 'improved' substring of 'unimproved' doesn't trap the
        # bidirectional substring matcher)
        (
            "Proportion of population using improved drinking water sources",
            "WS_PPL_W-I",
        ),
        (
            "What was Proportion of population using improved drinking water "
            "sources for X in 2010?",
            "WS_PPL_W-I",
        ),
        ("basic handwashing", "WS_PPL_H-B"),
        ("handwashing facility with soap and water on premises", "WS_PPL_H-B"),
        ("handwashing facility with soap and water available at home", "WS_PPL_H-B"),
    ],
)
def test_wash_queries_route_to_jmp_headline(query: str, expected_code: str) -> None:
    """v1.5.2 contract: realistic-length JMP queries route to the
    headline series.

    Known limitation (documented): short synthetic queries like
    'improved drinking water' (24 chars) ARE a contiguous substring of
    'unimproved drinking water' (25 chars), so the bidirectional
    substring matcher will return WS_PPL_W-UI on those — the v1.5.2
    WS_PPL_W-UI entry is intentionally placed FIRST in
    CURATED_PREFERRED to ensure the antonym separation works on the
    common case (realistic benchmark prompts and natural-language
    queries with the 'Proportion of population using ...' prefix).
    """
    result = lookup_preferred(query)
    assert result is not None
    assert result["code"] == expected_code


# ---------------------------------------------------------------------------
# Antonym separation: 'unimproved' must NOT match the 'improved' default
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "unimproved drinking water sources",
        "unimproved drinking water",
        "Proportion of population using unimproved drinking water",
        "Proportion of population using unimproved drinking water sources",
    ],
)
def test_unimproved_water_takes_precedence_over_improved(query: str) -> None:
    """v1.5.2 — WS_PPL_W-UI must be listed BEFORE WS_PPL_W-I in
    CURATED_PREFERRED so the bidirectional substring match doesn't
    silently route 'unimproved' to the 'improved' default. Critical
    regression check: the v1.5.0 partial-batch had 8 cells where this
    misroute corrupted the result; v1.5.1 added _SYNONYMS entries but
    the curated layer needs its own guard."""
    result = lookup_preferred(query)
    assert result is not None
    assert result["code"] == "WS_PPL_W-UI", (
        f"v1.5.2 antonym separation failed: {query!r} routed to {result['code']!r} "
        f"instead of WS_PPL_W-UI"
    )


def test_unimproved_entry_listed_before_improved_in_dict_order() -> None:
    """Insertion order of CURATED_PREFERRED determines first-match-wins
    in lookup_preferred. WS_PPL_W-UI MUST come before WS_PPL_W-I."""
    keys = list(CURATED_PREFERRED.keys())
    assert "WS_PPL_W-UI" in keys
    assert "WS_PPL_W-I" in keys
    assert keys.index("WS_PPL_W-UI") < keys.index("WS_PPL_W-I"), (
        "v1.5.2 antonym ordering broken: WS_PPL_W-UI must be inserted "
        "before WS_PPL_W-I in CURATED_PREFERRED"
    )


# ---------------------------------------------------------------------------
# dimension_hint must warn about other versions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code,must_mention",
    [
        ("ED_CR_L1_UIS_MOD", ["UNESCO/UIS modelled", "ED_CR_L1"]),
        ("ED_CR_L2_UIS_MOD", ["UNESCO/UIS modelled", "ED_CR_L2"]),
        ("ED_CR_L3_UIS_MOD", ["UNESCO/UIS modelled", "ED_CR_L3"]),
        ("ED_ROFST_L1_UIS_MOD", ["UNESCO/UIS modelled", "ED_ROFST_L1"]),
        ("ED_ROFST_L2_UIS_MOD", ["UNESCO/UIS modelled", "ED_ROFST_L2"]),
        ("ED_ROFST_L3_UIS_MOD", ["UNESCO/UIS modelled", "ED_ROFST_L3"]),
        ("WS_PPL_W-I", ["JMP", "WS_PPL_W-SM", "WS_PPL_W-ALB"]),
        ("WS_PPL_W-UI", ["JMP", "WS_PPL_W-SM", "WS_PPL_W-I"]),
        ("WS_PPL_H-B", ["JMP"]),
    ],
)
def test_dimension_hint_lists_other_versions(
    code: str, must_mention: list[str]
) -> None:
    """v1.5.2 — Every curated default carries a dimension_hint that names
    the alternative versions in the data warehouse, so the LLM can re-route
    if the user explicitly asks for raw / administrative data."""
    entry = CURATED_PREFERRED.get(code)
    assert entry is not None, f"{code} missing from CURATED_PREFERRED"
    hint = entry["dimension_hint"]
    assert hint, f"{code} has empty dimension_hint"
    for token in must_mention:
        assert token in hint, (
            f"v1.5.2: {code}.dimension_hint must mention {token!r} so the "
            f"LLM sees the alternative versions in the data warehouse. Got: "
            f"{hint!r}"
        )


# ---------------------------------------------------------------------------
# v1.5.0/v1.5.1 regressions: pre-existing curated entries still resolve
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected_code",
    [
        ("primary school attendance", "ED_ANAR_L1"),
        ("anemia women", "NT_ANE_WOM_15_49_MOD"),
        ("child income poverty", "PV_CHLD_INCM_PL"),
    ],
)
def test_v151_existing_curated_entries_still_resolve(
    query: str, expected_code: str
) -> None:
    """v1.5.2 must not break the pre-v1.5.2 curated entries."""
    result = lookup_preferred(query)
    assert result is not None
    assert result["code"] == expected_code
